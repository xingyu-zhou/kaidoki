"""
插件版本控制和兼容性检查

该模块实现了完整的插件版本管理系统，提供：
1. 语义版本控制（Semantic Versioning）
2. 插件依赖关系管理
3. 版本兼容性自动检查
4. 插件升级和回退机制
5. 依赖冲突解决策略
6. 版本历史和变更跟踪

核心设计原则：
- 基于语义化版本规范（SemVer）
- 自动化依赖解析和冲突检测
- 支持多版本并存和渐进式升级
- 提供版本回退和安全降级
- 集成配置兼容性验证

Author: Mercari AI Agent Team
"""

import re
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Set, Union, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import hashlib
import weakref

from .interfaces import PluginType, PluginConfiguration
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入packaging库，如果不存在则使用简单实现
try:
    from packaging import version as pkg_version
    from packaging.specifiers import SpecifierSet
    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False
    logger.warning("packaging library not available, using simple version comparison")


class VersionConstraintType(Enum):
    """版本约束类型"""
    EXACT = "exact"           # 精确版本 ==1.2.3
    MINIMUM = "minimum"       # 最小版本 >=1.2.3
    COMPATIBLE = "compatible" # 兼容版本 ~=1.2.3 (1.2.x)
    RANGE = "range"          # 版本范围 >=1.2.0,<2.0.0
    LATEST = "latest"        # 最新版本 *


class VersionCompatibility(Enum):
    """版本兼容性等级"""
    COMPATIBLE = "compatible"           # 完全兼容
    BACKWARD_COMPATIBLE = "backward"    # 向后兼容
    BREAKING_CHANGE = "breaking"        # 破坏性变更
    INCOMPATIBLE = "incompatible"       # 不兼容


class UpgradeStrategy(Enum):
    """升级策略"""
    CONSERVATIVE = "conservative"  # 保守升级（只升级补丁版本）
    MODERATE = "moderate"         # 适中升级（升级次版本）
    AGGRESSIVE = "aggressive"     # 激进升级（升级主版本）
    MANUAL = "manual"            # 手动升级


@dataclass
class SemanticVersion:
    """语义化版本"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: str = ""
    build_metadata: str = ""
    
    def __post_init__(self):
        """验证版本格式"""
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative integers")
    
    @classmethod
    def parse(cls, version_string: str) -> 'SemanticVersion':
        """解析版本字符串"""
        # 使用正则表达式解析语义化版本
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        match = re.match(pattern, version_string.strip())
        
        if not match:
            raise ValueError(f"Invalid semantic version format: {version_string}")
        
        major, minor, patch, prerelease, build = match.groups()
        
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease or "",
            build_metadata=build or ""
        )
    
    def __str__(self) -> str:
        """转换为字符串"""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build_metadata:
            version_str += f"+{self.build_metadata}"
        return version_str
    
    def __eq__(self, other) -> bool:
        """版本相等比较"""
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major == other.major and 
                self.minor == other.minor and 
                self.patch == other.patch and 
                self.prerelease == other.prerelease)
    
    def __lt__(self, other) -> bool:
        """版本小于比较"""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        
        # 比较主版本、次版本、补丁版本
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        
        # 处理预发布版本
        if not self.prerelease and not other.prerelease:
            return False
        if not self.prerelease and other.prerelease:
            return False  # 正式版本大于预发布版本
        if self.prerelease and not other.prerelease:
            return True
        
        # 比较预发布版本
        return self._compare_prerelease(self.prerelease, other.prerelease)
    
    def _compare_prerelease(self, pre1: str, pre2: str) -> bool:
        """比较预发布版本"""
        parts1 = pre1.split('.')
        parts2 = pre2.split('.')
        
        for i in range(max(len(parts1), len(parts2))):
            p1 = parts1[i] if i < len(parts1) else ""
            p2 = parts2[i] if i < len(parts2) else ""
            
            # 数字部分比较
            if p1.isdigit() and p2.isdigit():
                if int(p1) != int(p2):
                    return int(p1) < int(p2)
            elif p1.isdigit():
                return True  # 数字部分小于字母部分
            elif p2.isdigit():
                return False
            else:
                if p1 != p2:
                    return p1 < p2
        
        return len(parts1) < len(parts2)
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        return not self <= other
    
    def __ge__(self, other) -> bool:
        return not self < other
    
    def is_compatible_with(self, other: 'SemanticVersion') -> VersionCompatibility:
        """检查与另一个版本的兼容性"""
        if self.major != other.major:
            if self.major > other.major:
                return VersionCompatibility.BREAKING_CHANGE
            else:
                return VersionCompatibility.INCOMPATIBLE
        
        if self.minor > other.minor:
            return VersionCompatibility.BACKWARD_COMPATIBLE
        elif self.minor < other.minor:
            return VersionCompatibility.INCOMPATIBLE
        
        if self.patch >= other.patch:
            return VersionCompatibility.COMPATIBLE
        else:
            return VersionCompatibility.INCOMPATIBLE
    
    def increment(self, level: str) -> 'SemanticVersion':
        """递增版本号"""
        if level == "major":
            return SemanticVersion(self.major + 1, 0, 0)
        elif level == "minor":
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif level == "patch":
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        else:
            raise ValueError(f"Invalid version level: {level}")


@dataclass
class VersionConstraint:
    """版本约束"""
    constraint_type: VersionConstraintType
    version: Optional[SemanticVersion] = None
    min_version: Optional[SemanticVersion] = None
    max_version: Optional[SemanticVersion] = None
    specifier: Optional[str] = None
    
    @classmethod
    def parse(cls, constraint_str: str) -> 'VersionConstraint':
        """解析版本约束字符串"""
        constraint_str = constraint_str.strip()
        
        if constraint_str == "*" or constraint_str.lower() == "latest":
            return cls(VersionConstraintType.LATEST)
        
        # 精确版本
        if constraint_str.startswith("=="):
            version_str = constraint_str[2:].strip()
            return cls(VersionConstraintType.EXACT, SemanticVersion.parse(version_str))
        
        # 最小版本
        if constraint_str.startswith(">="):
            version_str = constraint_str[2:].strip()
            return cls(VersionConstraintType.MINIMUM, min_version=SemanticVersion.parse(version_str))
        
        # 兼容版本
        if constraint_str.startswith("~="):
            version_str = constraint_str[2:].strip()
            base_version = SemanticVersion.parse(version_str)
            return cls(VersionConstraintType.COMPATIBLE, min_version=base_version, 
                      max_version=SemanticVersion(base_version.major, base_version.minor + 1, 0))
        
        # 版本范围
        if "," in constraint_str:
            return cls(VersionConstraintType.RANGE, specifier=constraint_str)
        
        # 默认为精确版本
        return cls(VersionConstraintType.EXACT, SemanticVersion.parse(constraint_str))
    
    def satisfies(self, version: SemanticVersion) -> bool:
        """检查版本是否满足约束"""
        if self.constraint_type == VersionConstraintType.LATEST:
            return True
        elif self.constraint_type == VersionConstraintType.EXACT:
            return version == self.version
        elif self.constraint_type == VersionConstraintType.MINIMUM:
            return version >= self.min_version
        elif self.constraint_type == VersionConstraintType.COMPATIBLE:
            return self.min_version <= version < self.max_version
        elif self.constraint_type == VersionConstraintType.RANGE:
            if HAS_PACKAGING:
                try:
                    spec = SpecifierSet(self.specifier)
                    return pkg_version.Version(str(version)) in spec
                except Exception:
                    return False
            else:
                # 简单的范围解析
                return self._simple_range_check(version)
        
        return False
    
    def _simple_range_check(self, version: SemanticVersion) -> bool:
        """简单的版本范围检查（当packaging不可用时）"""
        try:
            constraints = self.specifier.split(',')
            for constraint in constraints:
                constraint = constraint.strip()
                if constraint.startswith('>='):
                    min_ver = SemanticVersion.parse(constraint[2:])
                    if version < min_ver:
                        return False
                elif constraint.startswith('<='):
                    max_ver = SemanticVersion.parse(constraint[2:])
                    if version > max_ver:
                        return False
                elif constraint.startswith('>'):
                    min_ver = SemanticVersion.parse(constraint[1:])
                    if version <= min_ver:
                        return False
                elif constraint.startswith('<'):
                    max_ver = SemanticVersion.parse(constraint[1:])
                    if version >= max_ver:
                        return False
            return True
        except Exception:
            return False


@dataclass
class PluginDependency:
    """插件依赖"""
    plugin_id: str
    plugin_type: PluginType
    version_constraint: VersionConstraint
    required: bool = True
    description: str = ""
    
    def __str__(self) -> str:
        return f"{self.plugin_id} {self.version_constraint.specifier or str(self.version_constraint.version)}"


@dataclass
class PluginVersionInfo:
    """插件版本信息"""
    plugin_id: str
    plugin_type: PluginType
    version: SemanticVersion
    dependencies: List[PluginDependency] = field(default_factory=list)
    
    # 版本元数据
    release_date: datetime = field(default_factory=datetime.now)
    author: str = ""
    description: str = ""
    changelog: str = ""
    
    # 兼容性信息
    min_framework_version: Optional[SemanticVersion] = None
    max_framework_version: Optional[SemanticVersion] = None
    supported_platforms: List[str] = field(default_factory=list)
    
    # 安全和稳定性
    stability: str = "stable"  # stable, beta, alpha, experimental
    security_fixes: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'plugin_id': self.plugin_id,
            'plugin_type': self.plugin_type.value,
            'version': str(self.version),
            'dependencies': [
                {
                    'plugin_id': dep.plugin_id,
                    'plugin_type': dep.plugin_type.value,
                    'constraint': dep.version_constraint.specifier or str(dep.version_constraint.version),
                    'required': dep.required,
                    'description': dep.description
                }
                for dep in self.dependencies
            ],
            'release_date': self.release_date.isoformat(),
            'author': self.author,
            'description': self.description,
            'changelog': self.changelog,
            'min_framework_version': str(self.min_framework_version) if self.min_framework_version else None,
            'max_framework_version': str(self.max_framework_version) if self.max_framework_version else None,
            'supported_platforms': self.supported_platforms,
            'stability': self.stability,
            'security_fixes': self.security_fixes,
            'known_issues': self.known_issues
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginVersionInfo':
        """从字典创建"""
        dependencies = []
        for dep_data in data.get('dependencies', []):
            dep = PluginDependency(
                plugin_id=dep_data['plugin_id'],
                plugin_type=PluginType(dep_data['plugin_type']),
                version_constraint=VersionConstraint.parse(dep_data['constraint']),
                required=dep_data.get('required', True),
                description=dep_data.get('description', '')
            )
            dependencies.append(dep)
        
        return cls(
            plugin_id=data['plugin_id'],
            plugin_type=PluginType(data['plugin_type']),
            version=SemanticVersion.parse(data['version']),
            dependencies=dependencies,
            release_date=datetime.fromisoformat(data.get('release_date', datetime.now().isoformat())),
            author=data.get('author', ''),
            description=data.get('description', ''),
            changelog=data.get('changelog', ''),
            min_framework_version=SemanticVersion.parse(data['min_framework_version']) if data.get('min_framework_version') else None,
            max_framework_version=SemanticVersion.parse(data['max_framework_version']) if data.get('max_framework_version') else None,
            supported_platforms=data.get('supported_platforms', []),
            stability=data.get('stability', 'stable'),
            security_fixes=data.get('security_fixes', []),
            known_issues=data.get('known_issues', [])
        )


@dataclass
class DependencyGraph:
    """依赖关系图"""
    nodes: Dict[str, PluginVersionInfo] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    
    def add_plugin(self, plugin_info: PluginVersionInfo):
        """添加插件到依赖图"""
        self.nodes[plugin_info.plugin_id] = plugin_info
        self.edges[plugin_info.plugin_id] = [dep.plugin_id for dep in plugin_info.dependencies]
    
    def has_cycle(self) -> Tuple[bool, List[str]]:
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        cycle_path = []
        
        def dfs(node: str, path: List[str]) -> bool:
            if node in rec_stack:
                # 找到循环，记录路径
                cycle_start = path.index(node)
                cycle_path.extend(path[cycle_start:] + [node])
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.edges.get(node, []):
                if dfs(neighbor, path):
                    return True
            
            rec_stack.remove(node)
            path.pop()
            return False
        
        for node in self.nodes:
            if node not in visited:
                if dfs(node, []):
                    return True, cycle_path
        
        return False, []
    
    def topological_sort(self) -> List[str]:
        """拓扑排序"""
        in_degree = {node: 0 for node in self.nodes}
        
        # 计算入度
        for node in self.edges:
            for neighbor in self.edges[node]:
                in_degree[neighbor] += 1
        
        # 队列初始化
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in self.edges.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result if len(result) == len(self.nodes) else []


class PluginVersionManager:
    """插件版本管理器"""
    
    def __init__(self, framework_ref: Optional[weakref.ref] = None):
        self.framework_ref = framework_ref
        
        # 版本信息存储
        self.plugin_versions: Dict[str, Dict[str, PluginVersionInfo]] = {}  # plugin_id -> version -> info
        self.current_versions: Dict[str, SemanticVersion] = {}  # plugin_id -> current_version
        self.dependency_graph = DependencyGraph()
        
        # 版本控制设置
        self.version_storage_path = Path("data/plugin_versions")
        self.version_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 升级策略
        self.upgrade_strategy = UpgradeStrategy.MODERATE
        self.auto_resolve_conflicts = True
        self.rollback_on_failure = True
        
        # 框架版本
        self.framework_version = SemanticVersion(1, 0, 0)
        
        logger.info("PluginVersionManager initialized")
    
    async def register_plugin_version(self, version_info: PluginVersionInfo) -> bool:
        """注册插件版本"""
        try:
            plugin_id = version_info.plugin_id
            version_str = str(version_info.version)
            
            # 存储版本信息
            if plugin_id not in self.plugin_versions:
                self.plugin_versions[plugin_id] = {}
            
            self.plugin_versions[plugin_id][version_str] = version_info
            
            # 更新依赖图
            self.dependency_graph.add_plugin(version_info)
            
            # 保存到文件
            await self._save_version_info(version_info)
            
            logger.info(f"Registered plugin version: {plugin_id} v{version_str}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plugin version: {e}")
            return False
    
    async def get_plugin_version(self, plugin_id: str, version_str: Optional[str] = None) -> Optional[PluginVersionInfo]:
        """获取插件版本信息"""
        if plugin_id not in self.plugin_versions:
            return None
        
        if version_str is None:
            # 返回当前版本
            current_version = self.current_versions.get(plugin_id)
            if current_version:
                version_str = str(current_version)
            else:
                # 返回最新版本
                versions = list(self.plugin_versions[plugin_id].keys())
                if versions:
                    latest_version = max(versions, key=lambda v: SemanticVersion.parse(v))
                    version_str = latest_version
        
        return self.plugin_versions[plugin_id].get(version_str)
    
    async def check_compatibility(self, plugin_id: str, 
                                target_version: SemanticVersion,
                                check_dependencies: bool = True) -> Dict[str, Any]:
        """检查版本兼容性"""
        result = {
            'compatible': True,
            'issues': [],
            'warnings': [],
            'dependency_conflicts': [],
            'required_updates': []
        }
        
        try:
            # 检查插件版本是否存在
            version_info = await self.get_plugin_version(plugin_id, str(target_version))
            if not version_info:
                result['compatible'] = False
                result['issues'].append(f"Plugin version {plugin_id} v{target_version} not found")
                return result
            
            # 检查框架兼容性
            if version_info.min_framework_version and self.framework_version < version_info.min_framework_version:
                result['compatible'] = False
                result['issues'].append(f"Requires framework version >= {version_info.min_framework_version}")
            
            if version_info.max_framework_version and self.framework_version > version_info.max_framework_version:
                result['compatible'] = False
                result['issues'].append(f"Incompatible with framework version > {version_info.max_framework_version}")
            
            # 检查依赖关系
            if check_dependencies:
                dependency_result = await self._check_dependencies(version_info)
                result['dependency_conflicts'].extend(dependency_result['conflicts'])
                result['required_updates'].extend(dependency_result['required_updates'])
                
                if dependency_result['conflicts']:
                    result['compatible'] = False
            
            # 检查安全性和稳定性
            if version_info.stability in ['alpha', 'experimental']:
                result['warnings'].append(f"Plugin version is marked as {version_info.stability}")
            
            if version_info.known_issues:
                result['warnings'].extend([f"Known issue: {issue}" for issue in version_info.known_issues])
            
            return result
            
        except Exception as e:
            logger.error(f"Compatibility check failed: {e}")
            result['compatible'] = False
            result['issues'].append(f"Compatibility check error: {str(e)}")
            return result
    
    async def resolve_dependencies(self, plugin_id: str, 
                                 target_version: SemanticVersion) -> Dict[str, Any]:
        """解析和解决依赖关系"""
        result = {
            'success': True,
            'resolution_plan': [],
            'conflicts': [],
            'warnings': []
        }
        
        try:
            # 获取目标版本信息
            version_info = await self.get_plugin_version(plugin_id, str(target_version))
            if not version_info:
                result['success'] = False
                result['conflicts'].append(f"Plugin version not found: {plugin_id} v{target_version}")
                return result
            
            # 构建依赖解析计划
            resolution_queue = [(plugin_id, target_version)]
            resolved = {}
            
            while resolution_queue:
                current_plugin, current_version = resolution_queue.pop(0)
                
                # 检查是否已解析
                if current_plugin in resolved:
                    if resolved[current_plugin] != current_version:
                        result['conflicts'].append(
                            f"Version conflict for {current_plugin}: "
                            f"{resolved[current_plugin]} vs {current_version}"
                        )
                    continue
                
                resolved[current_plugin] = current_version
                current_info = await self.get_plugin_version(current_plugin, str(current_version))
                
                if not current_info:
                    result['conflicts'].append(f"Plugin version not found: {current_plugin} v{current_version}")
                    continue
                
                # 添加到解析计划
                result['resolution_plan'].append({
                    'plugin_id': current_plugin,
                    'version': str(current_version),
                    'action': 'install' if current_plugin not in self.current_versions else 'upgrade'
                })
                
                # 处理依赖
                for dependency in current_info.dependencies:
                    if not dependency.required:
                        continue
                    
                    # 查找满足约束的最佳版本
                    best_version = await self._find_best_version(dependency)
                    if best_version:
                        resolution_queue.append((dependency.plugin_id, best_version))
                    else:
                        result['conflicts'].append(
                            f"Cannot satisfy dependency: {dependency.plugin_id} {dependency.version_constraint.specifier}"
                        )
            
            # 检查循环依赖
            test_graph = DependencyGraph()
            for item in result['resolution_plan']:
                info = await self.get_plugin_version(item['plugin_id'], item['version'])
                if info:
                    test_graph.add_plugin(info)
            
            has_cycle, cycle_path = test_graph.has_cycle()
            if has_cycle:
                result['success'] = False
                result['conflicts'].append(f"Circular dependency detected: {' -> '.join(cycle_path)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Dependency resolution failed: {e}")
            result['success'] = False
            result['conflicts'].append(f"Resolution error: {str(e)}")
            return result
    
    async def upgrade_plugin(self, plugin_id: str, 
                           target_version: Optional[SemanticVersion] = None,
                           strategy: Optional[UpgradeStrategy] = None) -> Dict[str, Any]:
        """升级插件"""
        result = {
            'success': True,
            'old_version': None,
            'new_version': None,
            'actions': [],
            'rollback_info': None
        }
        
        try:
            # 获取当前版本
            current_version = self.current_versions.get(plugin_id)
            if not current_version:
                result['success'] = False
                result['actions'].append(f"Plugin {plugin_id} not currently installed")
                return result
            
            result['old_version'] = str(current_version)
            
            # 确定目标版本
            if target_version is None:
                target_version = await self._find_upgrade_target(plugin_id, current_version, strategy or self.upgrade_strategy)
            
            if target_version is None:
                result['success'] = False
                result['actions'].append(f"No upgrade target found for {plugin_id}")
                return result
            
            result['new_version'] = str(target_version)
            
            # 检查兼容性
            compat_result = await self.check_compatibility(plugin_id, target_version)
            if not compat_result['compatible']:
                result['success'] = False
                result['actions'].extend(compat_result['issues'])
                return result
            
            # 解析依赖
            dep_result = await self.resolve_dependencies(plugin_id, target_version)
            if not dep_result['success']:
                result['success'] = False
                result['actions'].extend(dep_result['conflicts'])
                return result
            
            # 创建回退信息
            result['rollback_info'] = {
                'plugin_id': plugin_id,
                'previous_version': str(current_version),
                'timestamp': datetime.now().isoformat()
            }
            
            # 执行升级
            self.current_versions[plugin_id] = target_version
            result['actions'].append(f"Upgraded {plugin_id} from {current_version} to {target_version}")
            
            return result
            
        except Exception as e:
            logger.error(f"Plugin upgrade failed: {e}")
            result['success'] = False
            result['actions'].append(f"Upgrade error: {str(e)}")
            return result
    
    async def rollback_plugin(self, plugin_id: str, 
                            target_version: Optional[SemanticVersion] = None) -> Dict[str, Any]:
        """回退插件版本"""
        result = {
            'success': True,
            'old_version': None,
            'new_version': None,
            'actions': []
        }
        
        try:
            # 获取当前版本
            current_version = self.current_versions.get(plugin_id)
            if not current_version:
                result['success'] = False
                result['actions'].append(f"Plugin {plugin_id} not currently installed")
                return result
            
            result['old_version'] = str(current_version)
            
            # 确定目标版本
            if target_version is None:
                # 找到最近的稳定版本
                available_versions = list(self.plugin_versions.get(plugin_id, {}).keys())
                stable_versions = []
                
                for version_str in available_versions:
                    version = SemanticVersion.parse(version_str)
                    if version < current_version:
                        version_info = self.plugin_versions[plugin_id][version_str]
                        if version_info.stability == 'stable':
                            stable_versions.append(version)
                
                if stable_versions:
                    target_version = max(stable_versions)
                else:
                    result['success'] = False
                    result['actions'].append(f"No stable version available for rollback")
                    return result
            
            result['new_version'] = str(target_version)
            
            # 检查兼容性
            compat_result = await self.check_compatibility(plugin_id, target_version)
            if not compat_result['compatible']:
                result['success'] = False
                result['actions'].extend(compat_result['issues'])
                return result
            
            # 执行回退
            self.current_versions[plugin_id] = target_version
            result['actions'].append(f"Rolled back {plugin_id} from {current_version} to {target_version}")
            
            return result
            
        except Exception as e:
            logger.error(f"Plugin rollback failed: {e}")
            result['success'] = False
            result['actions'].append(f"Rollback error: {str(e)}")
            return result
    
    async def _check_dependencies(self, version_info: PluginVersionInfo) -> Dict[str, Any]:
        """检查依赖关系"""
        result = {
            'conflicts': [],
            'required_updates': []
        }
        
        for dependency in version_info.dependencies:
            if not dependency.required:
                continue
            
            # 检查依赖是否已安装
            current_dep_version = self.current_versions.get(dependency.plugin_id)
            if not current_dep_version:
                result['required_updates'].append(f"Install {dependency.plugin_id}")
                continue
            
            # 检查版本约束
            if not dependency.version_constraint.satisfies(current_dep_version):
                result['conflicts'].append(
                    f"Dependency conflict: {dependency.plugin_id} "
                    f"requires {dependency.version_constraint.specifier} "
                    f"but {current_dep_version} is installed"
                )
        
        return result
    
    async def _find_best_version(self, dependency: PluginDependency) -> Optional[SemanticVersion]:
        """查找满足约束的最佳版本"""
        plugin_id = dependency.plugin_id
        constraint = dependency.version_constraint
        
        if plugin_id not in self.plugin_versions:
            return None
        
        available_versions = [
            SemanticVersion.parse(v) for v in self.plugin_versions[plugin_id].keys()
        ]
        
        # 过滤满足约束的版本
        compatible_versions = [v for v in available_versions if constraint.satisfies(v)]
        
        if not compatible_versions:
            return None
        
        # 返回最新的稳定版本
        stable_versions = []
        for version in compatible_versions:
            version_info = self.plugin_versions[plugin_id][str(version)]
            if version_info.stability == 'stable':
                stable_versions.append(version)
        
        if stable_versions:
            return max(stable_versions)
        else:
            return max(compatible_versions)
    
    async def _find_upgrade_target(self, plugin_id: str, 
                                 current_version: SemanticVersion,
                                 strategy: UpgradeStrategy) -> Optional[SemanticVersion]:
        """根据策略查找升级目标"""
        if plugin_id not in self.plugin_versions:
            return None
        
        available_versions = [
            SemanticVersion.parse(v) for v in self.plugin_versions[plugin_id].keys()
        ]
        
        # 过滤大于当前版本的版本
        newer_versions = [v for v in available_versions if v > current_version]
        
        if not newer_versions:
            return None
        
        # 根据策略选择
        if strategy == UpgradeStrategy.CONSERVATIVE:
            # 只升级补丁版本
            patch_versions = [v for v in newer_versions 
                            if v.major == current_version.major and v.minor == current_version.minor]
            return max(patch_versions) if patch_versions else None
        
        elif strategy == UpgradeStrategy.MODERATE:
            # 升级次版本
            minor_versions = [v for v in newer_versions if v.major == current_version.major]
            return max(minor_versions) if minor_versions else None
        
        elif strategy == UpgradeStrategy.AGGRESSIVE:
            # 升级到最新版本
            return max(newer_versions)
        
        return None
    
    async def _save_version_info(self, version_info: PluginVersionInfo):
        """保存版本信息到文件"""
        try:
            file_path = self.version_storage_path / f"{version_info.plugin_id}_v{version_info.version}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(version_info.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save version info: {e}")
    
    async def load_version_info(self, plugin_id: str, version: str) -> Optional[PluginVersionInfo]:
        """从文件加载版本信息"""
        try:
            file_path = self.version_storage_path / f"{plugin_id}_v{version}.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return PluginVersionInfo.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load version info: {e}")
        
        return None
    
    def get_version_summary(self) -> Dict[str, Any]:
        """获取版本管理摘要"""
        return {
            'total_plugins': len(self.plugin_versions),
            'current_versions': {k: str(v) for k, v in self.current_versions.items()},
            'total_versions': sum(len(versions) for versions in self.plugin_versions.values()),
            'framework_version': str(self.framework_version),
            'upgrade_strategy': self.upgrade_strategy.value,
            'auto_resolve_conflicts': self.auto_resolve_conflicts,
            'rollback_on_failure': self.rollback_on_failure
        }


# 全局版本管理器实例
_global_version_manager: Optional[PluginVersionManager] = None

def get_version_manager() -> PluginVersionManager:
    """获取全局版本管理器实例"""
    global _global_version_manager
    if _global_version_manager is None:
        _global_version_manager = PluginVersionManager()
    return _global_version_manager
