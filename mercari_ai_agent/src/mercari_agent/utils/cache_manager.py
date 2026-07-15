"""
缓存管理器模块

该模块提供智能缓存管理功能。
支持多层缓存、TTL管理和自动清理。

主要功能：
- 内存缓存
- 持久化缓存
- TTL管理
- 自动清理
- 缓存统计

Author: Mercari AI Agent Team
"""

import asyncio
import json
import pickle
import time
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
import hashlib
import os

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CacheManager:
    """
    缓存管理器类
    
    提供多层缓存管理功能，支持内存和持久化缓存。
    具备TTL管理和自动清理功能。
    """
    
    def __init__(
        self,
        max_memory_size: int = 100 * 1024 * 1024,  # 100MB
        max_entries: int = 10000,
        default_ttl: int = 3600,  # 1小时
        cleanup_interval: int = 300,  # 5分钟
        persistent_cache_dir: Optional[str] = None
    ):
        """
        初始化缓存管理器
        
        Args:
            max_memory_size: 最大内存使用量（字节）
            max_entries: 最大缓存条目数
            default_ttl: 默认TTL（秒）
            cleanup_interval: 清理间隔（秒）
            persistent_cache_dir: 持久化缓存目录
        """
        self.max_memory_size = max_memory_size
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        # 内存缓存
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._memory_size = 0
        self._lock = Lock()
        
        # 持久化缓存
        self.persistent_cache_dir = persistent_cache_dir
        if self.persistent_cache_dir:
            Path(self.persistent_cache_dir).mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0,
            "total_requests": 0
        }
        
        # 启动清理任务
        self._cleanup_task = None
        self._start_cleanup_task()
        
        logger.info(f"CacheManager initialized - Max size: {max_memory_size} bytes, Max entries: {max_entries}")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值或None
        """
        self._stats["total_requests"] += 1
        
        with self._lock:
            # 检查内存缓存
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                
                # 检查是否过期
                if self._is_expired(entry):
                    del self._memory_cache[key]
                    self._memory_size -= entry.size
                    self._stats["misses"] += 1
                    return None
                
                # 更新访问信息
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                
                self._stats["hits"] += 1
                return entry.value
        
        # 检查持久化缓存
        if self.persistent_cache_dir:
            persistent_value = await self._get_from_persistent(key)
            if persistent_value is not None:
                # 将值加载到内存缓存
                await self.set(key, persistent_value, ttl=self.default_ttl)
                self._stats["hits"] += 1
                return persistent_value
        
        self._stats["misses"] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        persistent: bool = False
    ) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒）
            persistent: 是否持久化
            
        Returns:
            bool: 是否成功
        """
        try:
            ttl = ttl or self.default_ttl
            now = datetime.now()
            expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None
            
            # 计算值的大小
            value_size = self._calculate_size(value)
            
            # 检查是否超出限制
            if value_size > self.max_memory_size:
                logger.warning(f"缓存值过大，跳过缓存: {key}")
                return False
            
            with self._lock:
                # 创建缓存条目
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=now,
                    expires_at=expires_at,
                    size=value_size
                )
                
                # 检查是否需要清理空间
                if self._needs_eviction(value_size):
                    self._evict_entries(value_size)
                
                # 更新内存缓存
                if key in self._memory_cache:
                    self._memory_size -= self._memory_cache[key].size
                
                self._memory_cache[key] = entry
                self._memory_size += value_size
            
            # 持久化缓存
            if persistent and self.persistent_cache_dir:
                await self._save_to_persistent(key, value, expires_at)
            
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败: {key} - {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功
        """
        try:
            with self._lock:
                if key in self._memory_cache:
                    entry = self._memory_cache[key]
                    del self._memory_cache[key]
                    self._memory_size -= entry.size
            
            # 删除持久化缓存
            if self.persistent_cache_dir:
                await self._delete_from_persistent(key)
            
            return True
            
        except Exception as e:
            logger.error(f"删除缓存失败: {key} - {e}")
            return False
    
    async def clear(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            bool: 是否成功
        """
        try:
            with self._lock:
                self._memory_cache.clear()
                self._memory_size = 0
            
            # 清空持久化缓存
            if self.persistent_cache_dir:
                await self._clear_persistent()
            
            logger.info("缓存已清空")
            return True
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        value = await self.get(key)
        return value is not None
    
    async def get_or_set(
        self,
        key: str,
        factory_func,
        ttl: Optional[int] = None,
        persistent: bool = False
    ) -> Any:
        """
        获取缓存值，如果不存在则调用工厂函数
        
        Args:
            key: 缓存键
            factory_func: 工厂函数
            ttl: TTL（秒）
            persistent: 是否持久化
            
        Returns:
            Any: 缓存值
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        # 调用工厂函数
        if asyncio.iscoroutinefunction(factory_func):
            value = await factory_func()
        else:
            value = factory_func()
        
        # 设置缓存
        await self.set(key, value, ttl=ttl, persistent=persistent)
        return value
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查缓存条目是否过期"""
        if entry.expires_at is None:
            return False
        return datetime.now() > entry.expires_at
    
    def _needs_eviction(self, new_size: int) -> bool:
        """检查是否需要清理空间"""
        return (
            self._memory_size + new_size > self.max_memory_size or
            len(self._memory_cache) >= self.max_entries
        )
    
    def _evict_entries(self, required_size: int):
        """清理缓存条目"""
        if not self._memory_cache:
            return
        
        # 按LRU策略清理
        entries = list(self._memory_cache.values())
        entries.sort(key=lambda x: x.last_accessed)
        
        freed_size = 0
        entries_to_remove = []
        
        for entry in entries:
            entries_to_remove.append(entry.key)
            freed_size += entry.size
            
            if freed_size >= required_size:
                break
        
        # 删除条目
        for key in entries_to_remove:
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                del self._memory_cache[key]
                self._memory_size -= entry.size
                self._stats["evictions"] += 1
    
    def _calculate_size(self, value: Any) -> int:
        """计算值的大小"""
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return 8
            elif isinstance(value, (list, dict)):
                return len(pickle.dumps(value))
            else:
                return len(str(value).encode('utf-8'))
        except Exception:
            return 1024  # 默认大小
    
    async def _get_from_persistent(self, key: str) -> Optional[Any]:
        """从持久化缓存获取值"""
        if not self.persistent_cache_dir:
            return None
        
        try:
            cache_file = Path(self.persistent_cache_dir) / f"{self._hash_key(key)}.cache"
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            # 检查是否过期
            if data.get('expires_at') and datetime.now() > data['expires_at']:
                cache_file.unlink()
                return None
            
            return data['value']
            
        except Exception as e:
            logger.error(f"从持久化缓存获取失败: {key} - {e}")
            return None
    
    async def _save_to_persistent(self, key: str, value: Any, expires_at: Optional[datetime]):
        """保存到持久化缓存"""
        if not self.persistent_cache_dir:
            return
        
        try:
            cache_file = Path(self.persistent_cache_dir) / f"{self._hash_key(key)}.cache"
            
            data = {
                'value': value,
                'created_at': datetime.now(),
                'expires_at': expires_at,
                'key': key
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"保存到持久化缓存失败: {key} - {e}")
    
    async def _delete_from_persistent(self, key: str):
        """从持久化缓存删除"""
        if not self.persistent_cache_dir:
            return
        
        try:
            cache_file = Path(self.persistent_cache_dir) / f"{self._hash_key(key)}.cache"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.error(f"从持久化缓存删除失败: {key} - {e}")
    
    async def _clear_persistent(self):
        """清空持久化缓存"""
        if not self.persistent_cache_dir:
            return
        
        try:
            cache_dir = Path(self.persistent_cache_dir)
            for cache_file in cache_dir.glob("*.cache"):
                cache_file.unlink()
        except Exception as e:
            logger.error(f"清空持久化缓存失败: {e}")
    
    def _hash_key(self, key: str) -> str:
        """对键进行哈希处理"""
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务失败: {e}")
    
    async def _cleanup_expired(self):
        """清理过期条目"""
        expired_keys = []
        
        with self._lock:
            for key, entry in self._memory_cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
        
        # 删除过期条目
        for key in expired_keys:
            await self.delete(key)
        
        if expired_keys:
            self._stats["cleanups"] += len(expired_keys)
            logger.debug(f"清理过期缓存: {len(expired_keys)} 个条目")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        hit_rate = (
            self._stats["hits"] / self._stats["total_requests"] * 100
            if self._stats["total_requests"] > 0 else 0
        )
        
        with self._lock:
            memory_usage = self._memory_size
            entry_count = len(self._memory_cache)
        
        return {
            "memory_usage": memory_usage,
            "memory_usage_mb": memory_usage / (1024 * 1024),
            "entry_count": entry_count,
            "hit_rate": hit_rate,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "cleanups": self._stats["cleanups"],
            "total_requests": self._stats["total_requests"]
        }
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """获取所有缓存条目信息"""
        entries = []
        
        with self._lock:
            for key, entry in self._memory_cache.items():
                entries.append({
                    "key": key,
                    "created_at": entry.created_at.isoformat(),
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed.isoformat(),
                    "size": entry.size,
                    "expired": self._is_expired(entry)
                })
        
        return entries
    
    async def close(self):
        """关闭缓存管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("CacheManager closed")
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, '_cleanup_task') and self._cleanup_task:
            self._cleanup_task.cancel()