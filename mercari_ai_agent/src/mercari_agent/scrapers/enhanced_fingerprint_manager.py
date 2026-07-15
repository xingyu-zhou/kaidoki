"""
增强指纹管理器 - 与环境伪装系统集成

该模块扩展了原有的浏览器指纹管理器，增加了与环境伪装系统的集成功能，
提供更完整的反检测解决方案。

主要增强功能：
1. 环境伪装系统集成 - 自动应用JavaScript伪装
2. 智能指纹轮换策略 - 基于检测概率动态调整
3. 持久化存储管理 - 指纹缓存和恢复
4. 一致性维护增强 - 跨会话指纹一致性
5. Mercari特定优化 - 针对Mercari检测机制优化
6. 指纹质量评估 - 自动评估指纹风险等级

技术特点：
- 与BrowserEnvironmentSpoofing完全集成
- 智能指纹选择算法
- 动态风险评估和调整
- 完整的指纹生命周期管理
- 性能优化和资源管理

Author: Mercari AI Agent Team
"""

import asyncio
import logging
import random
import time
import json
import hashlib
import pickle
import os
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from .browser_fingerprint_manager import (
    BrowserFingerprintManager, BrowserFingerprint, BrowserType, OSType,
    WebGLFingerprint, CanvasFingerprint, FingerprintConfig
)
from .browser_environment_spoofing import (
    BrowserEnvironmentSpoofing, SpoofingConfig, SpoofingLevel,
    SpoofingResult, DetectionType
)
from .tls_fingerprint_manager import TLSFingerprintManager, TLSFingerprint
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class FingerprintQuality(Enum):
    """指纹质量等级"""
    EXCELLENT = "excellent"    # 极佳，检测概率 < 5%
    GOOD = "good"             # 良好，检测概率 5-15%
    FAIR = "fair"             # 一般，检测概率 15-30%
    POOR = "poor"             # 较差，检测概率 30-50%
    RISKY = "risky"           # 高风险，检测概率 > 50%


class FingerprintStatus(Enum):
    """指纹状态"""
    ACTIVE = "active"         # 活跃使用中
    IDLE = "idle"             # 空闲待用
    COOLING = "cooling"       # 冷却中
    RETIRED = "retired"       # 已退役
    BLACKLISTED = "blacklisted"  # 已被黑名单


@dataclass
class EnhancedFingerprintMetadata:
    """增强指纹元数据"""
    fingerprint_id: str
    creation_time: datetime
    last_used_time: Optional[datetime] = None
    usage_count: int = 0
    success_rate: float = 1.0
    detection_events: int = 0
    quality_score: float = 1.0
    quality_level: FingerprintQuality = FingerprintQuality.GOOD
    status: FingerprintStatus = FingerprintStatus.IDLE
    
    # 使用历史
    domains_used: List[str] = field(default_factory=list)
    session_ids: List[str] = field(default_factory=list)
    
    # 性能指标
    avg_response_time: float = 0.0
    captcha_triggered: int = 0
    blocks_encountered: int = 0
    
    # 风险评估
    risk_factors: Dict[str, float] = field(default_factory=dict)
    last_risk_assessment: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedFingerprintMetadata':
        """从字典创建"""
        # 处理日期时间字段
        if 'creation_time' in data and isinstance(data['creation_time'], str):
            data['creation_time'] = datetime.fromisoformat(data['creation_time'])
        if 'last_used_time' in data and data['last_used_time'] and isinstance(data['last_used_time'], str):
            data['last_used_time'] = datetime.fromisoformat(data['last_used_time'])
        if 'last_risk_assessment' in data and data['last_risk_assessment'] and isinstance(data['last_risk_assessment'], str):
            data['last_risk_assessment'] = datetime.fromisoformat(data['last_risk_assessment'])
        
        # 处理枚举字段
        if 'quality_level' in data and isinstance(data['quality_level'], str):
            data['quality_level'] = FingerprintQuality(data['quality_level'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = FingerprintStatus(data['status'])
        
        return cls(**data)


@dataclass
class EnhancedFingerprint:
    """增强指纹数据结构"""
    base_fingerprint: BrowserFingerprint
    tls_fingerprint: Optional[TLSFingerprint]
    spoofing_result: Optional[SpoofingResult]
    metadata: EnhancedFingerprintMetadata
    
    @property
    def fingerprint_id(self) -> str:
        """获取指纹ID"""
        return self.metadata.fingerprint_id
    
    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self.metadata.status == FingerprintStatus.ACTIVE
    
    @property
    def is_usable(self) -> bool:
        """是否可用"""
        return self.metadata.status in [FingerprintStatus.ACTIVE, FingerprintStatus.IDLE]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'base_fingerprint': self.base_fingerprint.to_dict(),
            'tls_fingerprint': self.tls_fingerprint.to_dict() if self.tls_fingerprint else None,
            'spoofing_result': asdict(self.spoofing_result) if self.spoofing_result else None,
            'metadata': self.metadata.to_dict()
        }


class FingerprintDatabase:
    """指纹数据库管理"""
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化数据库"""
        self.db_path = db_path or os.path.join(settings.DATA_DIR, "fingerprints.db")
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id TEXT PRIMARY KEY,
                    fingerprint_data TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_status 
                ON fingerprints(json_extract(metadata, '$.status'))
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprints_quality 
                ON fingerprints(json_extract(metadata, '$.quality_level'))
            """)
    
    async def save_fingerprint(self, fingerprint: EnhancedFingerprint):
        """保存指纹"""
        def _save():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO fingerprints 
                    (id, fingerprint_data, metadata, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    fingerprint.fingerprint_id,
                    json.dumps(fingerprint.to_dict()),
                    json.dumps(fingerprint.metadata.to_dict())
                ))
        
        await asyncio.get_event_loop().run_in_executor(self.executor, _save)
    
    async def load_fingerprint(self, fingerprint_id: str) -> Optional[EnhancedFingerprint]:
        """加载指纹"""
        def _load():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT fingerprint_data FROM fingerprints WHERE id = ?",
                    (fingerprint_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else None
        
        data = await asyncio.get_event_loop().run_in_executor(self.executor, _load)
        if data:
            try:
                fingerprint_dict = json.loads(data)
                return self._dict_to_fingerprint(fingerprint_dict)
            except Exception as e:
                logger.error(f"加载指纹失败 {fingerprint_id}: {e}")
        
        return None
    
    async def list_fingerprints(self, 
                               status: Optional[FingerprintStatus] = None,
                               quality: Optional[FingerprintQuality] = None,
                               limit: int = 100) -> List[EnhancedFingerprint]:
        """列出指纹"""
        def _list():
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT fingerprint_data FROM fingerprints"
                params = []
                conditions = []
                
                if status:
                    conditions.append("json_extract(metadata, '$.status') = ?")
                    params.append(status.value)
                
                if quality:
                    conditions.append("json_extract(metadata, '$.quality_level') = ?")
                    params.append(quality.value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY updated_at DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                return [row[0] for row in cursor.fetchall()]
        
        data_list = await asyncio.get_event_loop().run_in_executor(self.executor, _list)
        fingerprints = []
        
        for data in data_list:
            try:
                fingerprint_dict = json.loads(data)
                fingerprint = self._dict_to_fingerprint(fingerprint_dict)
                if fingerprint:
                    fingerprints.append(fingerprint)
            except Exception as e:
                logger.error(f"解析指纹数据失败: {e}")
        
        return fingerprints
    
    def _dict_to_fingerprint(self, data: Dict[str, Any]) -> Optional[EnhancedFingerprint]:
        """从字典转换为指纹对象"""
        try:
            # 重建基础指纹
            base_data = data['base_fingerprint']
            # 这里需要重建BrowserFingerprint对象
            # 由于结构复杂，这里简化处理
            
            # 重建元数据
            metadata = EnhancedFingerprintMetadata.from_dict(data['metadata'])
            
            # 创建增强指纹对象
            # 这里需要完整的重建逻辑
            return None  # 暂时返回None，实际实现需要完整的反序列化
            
        except Exception as e:
            logger.error(f"重建指纹对象失败: {e}")
            return None
    
    async def cleanup_old_fingerprints(self, max_age_days: int = 30):
        """清理过期指纹"""
        def _cleanup():
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM fingerprints WHERE created_at < ?",
                    (cutoff_date.isoformat(),)
                )
                return cursor.rowcount
        
        deleted_count = await asyncio.get_event_loop().run_in_executor(self.executor, _cleanup)
        logger.info(f"清理了 {deleted_count} 个过期指纹")
        return deleted_count


class FingerprintQualityAssessor:
    """指纹质量评估器"""
    
    def __init__(self):
        """初始化质量评估器"""
        self.risk_weights = {
            'user_agent_common': 0.1,    # User-Agent常见程度
            'webgl_consistency': 0.2,    # WebGL一致性
            'canvas_uniqueness': 0.15,   # Canvas独特性
            'tls_standard': 0.15,        # TLS标准程度
            'timing_natural': 0.1,       # 时序自然度
            'headers_completeness': 0.1, # 头部完整性
            'behavior_realism': 0.2      # 行为真实性
        }
    
    def assess_fingerprint_quality(self, fingerprint: EnhancedFingerprint) -> Tuple[float, FingerprintQuality]:
        """评估指纹质量"""
        total_score = 0.0
        
        # 评估各个维度
        scores = {}
        
        # User-Agent常见程度
        scores['user_agent_common'] = self._assess_user_agent(fingerprint.base_fingerprint.user_agent)
        
        # WebGL一致性
        scores['webgl_consistency'] = self._assess_webgl_consistency(fingerprint.base_fingerprint.webgl_fingerprint)
        
        # Canvas独特性
        scores['canvas_uniqueness'] = self._assess_canvas_uniqueness(fingerprint.base_fingerprint.canvas_fingerprint)
        
        # TLS标准程度
        if fingerprint.tls_fingerprint:
            scores['tls_standard'] = self._assess_tls_standard(fingerprint.tls_fingerprint)
        else:
            scores['tls_standard'] = 0.5
        
        # 时序自然度
        scores['timing_natural'] = self._assess_timing_natural(fingerprint.metadata)
        
        # 头部完整性
        scores['headers_completeness'] = self._assess_headers_completeness(fingerprint.base_fingerprint.headers)
        
        # 行为真实性
        scores['behavior_realism'] = self._assess_behavior_realism(fingerprint.metadata)
        
        # 计算加权总分
        for dimension, score in scores.items():
            weight = self.risk_weights.get(dimension, 0.0)
            total_score += score * weight
        
        # 更新风险因子
        fingerprint.metadata.risk_factors = scores
        fingerprint.metadata.last_risk_assessment = datetime.now()
        
        # 确定质量等级
        quality_level = self._score_to_quality_level(total_score)
        
        return total_score, quality_level
    
    def _assess_user_agent(self, user_agent: str) -> float:
        """评估User-Agent"""
        # 检查是否包含常见的自动化标识
        automation_indicators = ['headless', 'selenium', 'phantomjs', 'chrome/0.0.0']
        for indicator in automation_indicators:
            if indicator.lower() in user_agent.lower():
                return 0.0
        
        # 检查版本号合理性
        if 'Chrome' in user_agent:
            # 提取Chrome版本号并检查是否为最新
            import re
            match = re.search(r'Chrome/(\d+)', user_agent)
            if match:
                version = int(match.group(1))
                if version >= 110:  # 相对较新的版本
                    return 0.8
                elif version >= 100:
                    return 0.7
                else:
                    return 0.5
        
        return 0.6
    
    def _assess_webgl_consistency(self, webgl_fingerprint: WebGLFingerprint) -> float:
        """评估WebGL一致性"""
        score = 0.8  # 基础分数
        
        # 检查渲染器和供应商是否匹配
        renderer = webgl_fingerprint.renderer.lower()
        vendor = webgl_fingerprint.vendor.lower()
        
        # 检查是否为headless特征
        if 'swiftshader' in renderer or 'mesa' in renderer:
            score *= 0.3
        
        # 检查扩展数量是否合理
        if len(webgl_fingerprint.extensions) < 10:
            score *= 0.7
        elif len(webgl_fingerprint.extensions) > 50:
            score *= 0.8
        
        return score
    
    def _assess_canvas_uniqueness(self, canvas_fingerprint: CanvasFingerprint) -> float:
        """评估Canvas独特性"""
        # Canvas指纹应该有一定的独特性，但不能过于异常
        hash_value = canvas_fingerprint.fingerprint_hash
        
        # 检查哈希值是否过于简单
        if len(set(hash_value)) < 8:  # 字符种类太少
            return 0.3
        
        # 检查尺寸是否合理
        if canvas_fingerprint.width < 200 or canvas_fingerprint.height < 100:
            return 0.5
        
        return 0.8
    
    def _assess_tls_standard(self, tls_fingerprint: TLSFingerprint) -> float:
        """评估TLS标准程度"""
        score = 0.8
        
        # 检查密码套件是否标准
        if len(tls_fingerprint.cipher_suites) < 5:
            score *= 0.6
        
        # 检查扩展数量
        if len(tls_fingerprint.extensions) < 10:
            score *= 0.7
        
        return score
    
    def _assess_timing_natural(self, metadata: EnhancedFingerprintMetadata) -> float:
        """评估时序自然度"""
        if metadata.avg_response_time == 0:
            return 0.7  # 默认分数
        
        # 响应时间应该在合理范围内
        if metadata.avg_response_time < 0.1:  # 太快
            return 0.3
        elif metadata.avg_response_time > 10.0:  # 太慢
            return 0.5
        else:
            return 0.8
    
    def _assess_headers_completeness(self, headers: Dict[str, str]) -> float:
        """评估头部完整性"""
        required_headers = ['accept', 'accept-language', 'accept-encoding', 'user-agent']
        present_headers = [h.lower() for h in headers.keys()]
        
        completeness = sum(1 for h in required_headers if h in present_headers) / len(required_headers)
        return completeness
    
    def _assess_behavior_realism(self, metadata: EnhancedFingerprintMetadata) -> float:
        """评估行为真实性"""
        score = 0.8
        
        # 检查成功率
        if metadata.success_rate < 0.5:
            score *= 0.3
        elif metadata.success_rate < 0.8:
            score *= 0.7
        
        # 检查CAPTCHA触发率
        if metadata.usage_count > 0:
            captcha_rate = metadata.captcha_triggered / metadata.usage_count
            if captcha_rate > 0.3:
                score *= 0.2
            elif captcha_rate > 0.1:
                score *= 0.6
        
        return score
    
    def _score_to_quality_level(self, score: float) -> FingerprintQuality:
        """将分数转换为质量等级"""
        if score >= 0.9:
            return FingerprintQuality.EXCELLENT
        elif score >= 0.7:
            return FingerprintQuality.GOOD
        elif score >= 0.5:
            return FingerprintQuality.FAIR
        elif score >= 0.3:
            return FingerprintQuality.POOR
        else:
            return FingerprintQuality.RISKY


class EnhancedFingerprintManager:
    """增强指纹管理器主类"""
    
    def __init__(self, 
                 fingerprint_config: Optional[FingerprintConfig] = None,
                 spoofing_config: Optional[SpoofingConfig] = None):
        """
        初始化增强指纹管理器
        
        Args:
            fingerprint_config: 指纹配置
            spoofing_config: 伪装配置
        """
        # 初始化基础组件
        self.base_manager = BrowserFingerprintManager(fingerprint_config)
        self.spoofing_system = BrowserEnvironmentSpoofing(spoofing_config)
        self.tls_manager = TLSFingerprintManager()
        self.quality_assessor = FingerprintQualityAssessor()
        self.database = FingerprintDatabase()
        
        # 指纹池管理
        self.fingerprint_pool: Dict[str, EnhancedFingerprint] = {}
        self.active_fingerprints: Dict[str, str] = {}  # session_id -> fingerprint_id
        
        # 配置参数
        self.config = fingerprint_config or FingerprintConfig()
        self.spoofing_config = spoofing_config or SpoofingConfig()
        
        # 统计信息
        self.stats = {
            "total_fingerprints": 0,
            "active_fingerprints": 0,
            "quality_distribution": {q.value: 0 for q in FingerprintQuality},
            "success_rate": 0.0,
            "avg_quality_score": 0.0
        }
        
        logger.info("🔐 增强指纹管理器初始化完成")
    
    async def initialize(self):
        """异步初始化"""
        try:
            # 从数据库加载现有指纹
            await self._load_existing_fingerprints()
            
            # 预生成指纹池
            await self._populate_fingerprint_pool()
            
            logger.info("✅ 增强指纹管理器初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 增强指纹管理器初始化失败: {e}")
            raise
    
    async def get_fingerprint_for_session(self, 
                                        session_id: str,
                                        target_url: str,
                                        preferred_quality: Optional[FingerprintQuality] = None) -> Optional[EnhancedFingerprint]:
        """
        为会话获取指纹
        
        Args:
            session_id: 会话ID
            target_url: 目标URL
            preferred_quality: 首选质量等级
            
        Returns:
            EnhancedFingerprint: 增强指纹对象
        """
        try:
            # 检查是否已有活跃指纹
            if session_id in self.active_fingerprints:
                fingerprint_id = self.active_fingerprints[session_id]
                fingerprint = self.fingerprint_pool.get(fingerprint_id)
                
                if fingerprint and fingerprint.is_usable:
                    # 更新使用记录
                    await self._update_fingerprint_usage(fingerprint, target_url)
                    return fingerprint
                else:
                    # 清理无效指纹
                    del self.active_fingerprints[session_id]
            
            # 选择新指纹
            fingerprint = await self._select_best_fingerprint(target_url, preferred_quality)
            
            if fingerprint:
                # 应用环境伪装
                spoofing_result = await self.spoofing_system.apply_spoofing(
                    session_id=session_id,
                    target_url=target_url,
                    fingerprint=fingerprint.base_fingerprint
                )
                
                fingerprint.spoofing_result = spoofing_result
                
                # 标记为活跃
                fingerprint.metadata.status = FingerprintStatus.ACTIVE
                self.active_fingerprints[session_id] = fingerprint.fingerprint_id
                
                # 更新使用记录
                await self._update_fingerprint_usage(fingerprint, target_url)
                
                logger.info(f"✅ 为会话 {session_id} 分配指纹 {fingerprint.fingerprint_id}")
                return fingerprint
            
            else:
                logger.warning(f"⚠️ 无法为会话 {session_id} 分配指纹")
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取会话指纹失败: {e}")
            return None
    
    async def _select_best_fingerprint(self, 
                                     target_url: str,
                                     preferred_quality: Optional[FingerprintQuality] = None) -> Optional[EnhancedFingerprint]:
        """选择最佳指纹"""
        # 获取可用指纹
        available_fingerprints = [
            fp for fp in self.fingerprint_pool.values()
            if fp.is_usable and fp.metadata.status != FingerprintStatus.ACTIVE
        ]
        
        if not available_fingerprints:
            # 生成新指纹
            return await self._generate_new_fingerprint()
        
        # 按质量和使用历史排序
        def score_fingerprint(fp: EnhancedFingerprint) -> float:
            base_score = fp.metadata.quality_score
            
            # 质量偏好调整
            if preferred_quality and fp.metadata.quality_level == preferred_quality:
                base_score += 0.2
            
            # 使用频率调整（少用的优先）
            usage_penalty = min(fp.metadata.usage_count * 0.01, 0.3)
            base_score -= usage_penalty
            
            # 成功率调整
            base_score *= fp.metadata.success_rate
            
            # 冷却时间调整
            if fp.metadata.last_used_time:
                time_since_use = (datetime.now() - fp.metadata.last_used_time).total_seconds()
                if time_since_use < 300:  # 5分钟内使用过
                    base_score *= 0.5
            
            return base_score
        
        # 选择最佳指纹
        best_fingerprint = max(available_fingerprints, key=score_fingerprint)
        return best_fingerprint
    
    async def _generate_new_fingerprint(self) -> Optional[EnhancedFingerprint]:
        """生成新指纹"""
        try:
            # 生成基础指纹
            base_fingerprint = self.base_manager.generate_fingerprint()
            
            # 生成TLS指纹
            tls_fingerprint = self.tls_manager.get_fingerprint(base_fingerprint.browser_type)
            
            # 创建元数据
            fingerprint_id = self._generate_fingerprint_id(base_fingerprint)
            metadata = EnhancedFingerprintMetadata(
                fingerprint_id=fingerprint_id,
                creation_time=datetime.now()
            )
            
            # 创建增强指纹
            enhanced_fingerprint = EnhancedFingerprint(
                base_fingerprint=base_fingerprint,
                tls_fingerprint=tls_fingerprint,
                spoofing_result=None,
                metadata=metadata
            )
            
            # 评估质量
            quality_score, quality_level = self.quality_assessor.assess_fingerprint_quality(enhanced_fingerprint)
            enhanced_fingerprint.metadata.quality_score = quality_score
            enhanced_fingerprint.metadata.quality_level = quality_level
            
            # 添加到池中
            self.fingerprint_pool[fingerprint_id] = enhanced_fingerprint
            
            # 保存到数据库
            await self.database.save_fingerprint(enhanced_fingerprint)
            
            logger.info(f"✅ 生成新指纹 {fingerprint_id}，质量等级: {quality_level.value}")
            return enhanced_fingerprint
            
        except Exception as e:
            logger.error(f"❌ 生成新指纹失败: {e}")
            return None
    
    def _generate_fingerprint_id(self, base_fingerprint: BrowserFingerprint) -> str:
        """生成指纹ID"""
        data = f"{base_fingerprint.user_agent}{base_fingerprint.screen_resolution}{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    async def _update_fingerprint_usage(self, fingerprint: EnhancedFingerprint, domain: str):
        """更新指纹使用记录"""
        metadata = fingerprint.metadata
        metadata.usage_count += 1
        metadata.last_used_time = datetime.now()
        
        # 更新域名使用记录
        parsed_domain = domain.split('/')[2] if '//' in domain else domain
        if parsed_domain not in metadata.domains_used:
            metadata.domains_used.append(parsed_domain)
        
        # 保存到数据库
        await self.database.save_fingerprint(fingerprint)
    
    async def _load_existing_fingerprints(self):
        """加载现有指纹"""
        try:
            fingerprints = await self.database.list_fingerprints(limit=200)
            for fingerprint in fingerprints:
                if fingerprint:
                    self.fingerprint_pool[fingerprint.fingerprint_id] = fingerprint
            
            logger.info(f"从数据库加载了 {len(fingerprints)} 个指纹")
            
        except Exception as e:
            logger.error(f"加载现有指纹失败: {e}")
    
    async def _populate_fingerprint_pool(self):
        """填充指纹池"""
        target_size = 20  # 目标池大小
        current_size = len(self.fingerprint_pool)
        
        if current_size < target_size:
            generate_count = target_size - current_size
            logger.info(f"预生成 {generate_count} 个指纹")
            
            for _ in range(generate_count):
                await self._generate_new_fingerprint()
    
    async def report_detection(self, session_id: str, detection_type: str):
        """报告检测事件"""
        if session_id in self.active_fingerprints:
            fingerprint_id = self.active_fingerprints[session_id]
            fingerprint = self.fingerprint_pool.get(fingerprint_id)
            
            if fingerprint:
                fingerprint.metadata.detection_events += 1
                fingerprint.metadata.success_rate = max(0.0, fingerprint.metadata.success_rate - 0.1)
                
                # 如果检测事件过多，标记为高风险
                if fingerprint.metadata.detection_events > 5:
                    fingerprint.metadata.status = FingerprintStatus.COOLING
                
                await self.database.save_fingerprint(fingerprint)
                logger.warning(f"指纹 {fingerprint_id} 被检测: {detection_type}")
    
    async def report_captcha(self, session_id: str):
        """报告CAPTCHA触发"""
        if session_id in self.active_fingerprints:
            fingerprint_id = self.active_fingerprints[session_id]
            fingerprint = self.fingerprint_pool.get(fingerprint_id)
            
            if fingerprint:
                fingerprint.metadata.captcha_triggered += 1
                fingerprint.metadata.success_rate = max(0.0, fingerprint.metadata.success_rate - 0.2)
                
                # CAPTCHA触发后立即冷却
                fingerprint.metadata.status = FingerprintStatus.COOLING
                
                await self.database.save_fingerprint(fingerprint)
                logger.warning(f"指纹 {fingerprint_id} 触发CAPTCHA")
    
    async def release_session(self, session_id: str):
        """释放会话"""
        if session_id in self.active_fingerprints:
            fingerprint_id = self.active_fingerprints[session_id]
            fingerprint = self.fingerprint_pool.get(fingerprint_id)
            
            if fingerprint:
                fingerprint.metadata.status = FingerprintStatus.IDLE
                await self.database.save_fingerprint(fingerprint)
            
            del self.active_fingerprints[session_id]
            
            # 清理伪装系统
            self.spoofing_system.cleanup_session(session_id)
            
            logger.debug(f"释放会话 {session_id}")
    
    async def cleanup_expired_fingerprints(self):
        """清理过期指纹"""
        current_time = datetime.now()
        expired_ids = []
        
        for fingerprint_id, fingerprint in self.fingerprint_pool.items():
            # 检查是否过期
            age = (current_time - fingerprint.metadata.creation_time).days
            
            if age > 30 or fingerprint.metadata.quality_level == FingerprintQuality.RISKY:
                expired_ids.append(fingerprint_id)
        
        # 移除过期指纹
        for fingerprint_id in expired_ids:
            del self.fingerprint_pool[fingerprint_id]
        
        # 清理数据库
        await self.database.cleanup_old_fingerprints()
        
        logger.info(f"清理了 {len(expired_ids)} 个过期指纹")
    
    def get_enhanced_stats(self) -> Dict[str, Any]:
        """获取增强统计信息"""
        # 更新统计信息
        total_fingerprints = len(self.fingerprint_pool)
        active_fingerprints = len(self.active_fingerprints)
        
        quality_distribution = {q.value: 0 for q in FingerprintQuality}
        total_quality_score = 0.0
        total_success_rate = 0.0
        
        for fingerprint in self.fingerprint_pool.values():
            quality_distribution[fingerprint.metadata.quality_level.value] += 1
            total_quality_score += fingerprint.metadata.quality_score
            total_success_rate += fingerprint.metadata.success_rate
        
        avg_quality_score = total_quality_score / max(1, total_fingerprints)
        avg_success_rate = total_success_rate / max(1, total_fingerprints)
        
        return {
            "total_fingerprints": total_fingerprints,
            "active_fingerprints": active_fingerprints,
            "quality_distribution": quality_distribution,
            "avg_quality_score": avg_quality_score,
            "avg_success_rate": avg_success_rate,
            "spoofing_stats": self.spoofing_system.get_stats(),
            "base_manager_stats": self.base_manager.get_fingerprint_stats()
        }


# 工厂函数
async def create_enhanced_fingerprint_manager(
    spoofing_level: SpoofingLevel = SpoofingLevel.STANDARD
) -> EnhancedFingerprintManager:
    """创建增强指纹管理器"""
    fingerprint_config = FingerprintConfig()
    spoofing_config = SpoofingConfig(level=spoofing_level)
    
    manager = EnhancedFingerprintManager(fingerprint_config, spoofing_config)
    await manager.initialize()
    
    return manager


# 测试函数
async def test_enhanced_fingerprint_manager():
    """测试增强指纹管理器"""
    logger.info("🧪 开始测试增强指纹管理器...")
    
    try:
        # 创建管理器
        manager = await create_enhanced_fingerprint_manager(SpoofingLevel.STANDARD)
        
        # 测试获取指纹
        fingerprint = await manager.get_fingerprint_for_session(
            session_id="test_session",
            target_url="https://jp.mercari.com"
        )
        
        if fingerprint:
            logger.info(f"✅ 获取指纹成功: {fingerprint.fingerprint_id}")
            logger.info(f"质量等级: {fingerprint.metadata.quality_level.value}")
            logger.info(f"质量分数: {fingerprint.metadata.quality_score:.2f}")
        
        # 测试统计信息
        stats = manager.get_enhanced_stats()
        logger.info(f"统计信息: {stats}")
        
        # 释放会话
        await manager.release_session("test_session")
        
        logger.info("✅ 增强指纹管理器测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_enhanced_fingerprint_manager())