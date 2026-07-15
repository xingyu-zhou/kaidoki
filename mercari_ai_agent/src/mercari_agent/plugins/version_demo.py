"""
插件版本控制演示

该文件演示了插件框架的版本控制和兼容性检查功能：
1. 语义版本解析和比较
2. 插件依赖关系管理
3. 版本兼容性检查
4. 插件升级和回退
5. 依赖冲突解决
6. 循环依赖检测

使用方法：
python version_demo.py

Author: Mercari AI Agent Team
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from .version_control import (
    PluginVersionManager, SemanticVersion, VersionConstraint,
    PluginVersionInfo, PluginDependency, VersionConstraintType,
    VersionCompatibility, UpgradeStrategy
)
from .interfaces import PluginType
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VersionControlDemo:
    """版本控制演示类"""
    
    def __init__(self):
        self.version_manager = PluginVersionManager()
        
        # 演示插件版本信息
        self.demo_versions = self._create_demo_versions()
    
    def _create_demo_versions(self) -> Dict[str, List[PluginVersionInfo]]:
        """创建演示版本信息"""
        versions = {}
        
        # 会话管理插件版本
        session_versions = [
            PluginVersionInfo(
                plugin_id="session_manager",
                plugin_type=PluginType.SESSION_MANAGEMENT,
                version=SemanticVersion.parse("1.0.0"),
                description="Initial release of session manager",
                stability="stable",
                author="Mercari AI Team",
                supported_platforms=["windows", "linux", "macos"]
            ),
            PluginVersionInfo(
                plugin_id="session_manager",
                plugin_type=PluginType.SESSION_MANAGEMENT,
                version=SemanticVersion.parse("1.1.0"),
                description="Added connection pooling support",
                changelog="- Added connection pooling\n- Improved performance\n- Fixed memory leaks",
                stability="stable",
                author="Mercari AI Team",
                supported_platforms=["windows", "linux", "macos"]
            ),
            PluginVersionInfo(
                plugin_id="session_manager",
                plugin_type=PluginType.SESSION_MANAGEMENT,
                version=SemanticVersion.parse("2.0.0-beta.1"),
                description="Major rewrite with async support",
                changelog="- Complete async rewrite\n- Breaking API changes\n- Improved scalability",
                stability="beta",
                author="Mercari AI Team",
                supported_platforms=["windows", "linux", "macos"],
                min_framework_version=SemanticVersion.parse("1.1.0"),
                known_issues=["May have performance issues under high load"]
            )
        ]
        
        # 指纹管理插件版本
        fingerprint_versions = [
            PluginVersionInfo(
                plugin_id="fingerprint_manager",
                plugin_type=PluginType.FINGERPRINT,
                version=SemanticVersion.parse("1.0.0"),
                description="Basic fingerprint management",
                stability="stable",
                author="Mercari AI Team",
                dependencies=[
                    PluginDependency(
                        plugin_id="session_manager",
                        plugin_type=PluginType.SESSION_MANAGEMENT,
                        version_constraint=VersionConstraint.parse(">=1.0.0,<2.0.0"),
                        description="Requires session manager for HTTP requests"
                    )
                ]
            ),
            PluginVersionInfo(
                plugin_id="fingerprint_manager",
                plugin_type=PluginType.FINGERPRINT,
                version=SemanticVersion.parse("1.2.0"),
                description="Added advanced fingerprinting techniques",
                changelog="- Canvas fingerprinting\n- WebGL fingerprinting\n- Audio context fingerprinting",
                stability="stable",
                author="Mercari AI Team",
                dependencies=[
                    PluginDependency(
                        plugin_id="session_manager",
                        plugin_type=PluginType.SESSION_MANAGEMENT,
                        version_constraint=VersionConstraint.parse(">=1.1.0,<2.0.0"),
                        description="Requires session manager v1.1+ for connection pooling"
                    )
                ]
            )
        ]
        
        # 行为模拟插件版本
        behavior_versions = [
            PluginVersionInfo(
                plugin_id="behavior_simulator",
                plugin_type=PluginType.BEHAVIOR_SIMULATION,
                version=SemanticVersion.parse("1.0.0"),
                description="Human-like behavior simulation",
                stability="stable",
                author="Mercari AI Team",
                dependencies=[
                    PluginDependency(
                        plugin_id="session_manager",
                        plugin_type=PluginType.SESSION_MANAGEMENT,
                        version_constraint=VersionConstraint.parse(">=1.0.0"),
                        description="Requires session manager for interactions"
                    ),
                    PluginDependency(
                        plugin_id="fingerprint_manager",
                        plugin_type=PluginType.FINGERPRINT,
                        version_constraint=VersionConstraint.parse(">=1.0.0"),
                        description="Requires fingerprint manager for consistency"
                    )
                ]
            )
        ]
        
        versions["session_manager"] = session_versions
        versions["fingerprint_manager"] = fingerprint_versions
        versions["behavior_simulator"] = behavior_versions
        
        return versions
    
    async def run_demo(self):
        """运行完整演示"""
        logger.info("🚀 开始插件版本控制演示")
        
        try:
            # 1. 演示语义版本解析和比较
            await self.demo_semantic_versioning()
            
            # 2. 演示版本注册和查询
            await self.demo_version_registration()
            
            # 3. 演示依赖关系检查
            await self.demo_dependency_checking()
            
            # 4. 演示版本兼容性检查
            await self.demo_compatibility_checking()
            
            # 5. 演示插件升级
            await self.demo_plugin_upgrade()
            
            # 6. 演示版本回退
            await self.demo_plugin_rollback()
            
            # 7. 演示依赖解析
            await self.demo_dependency_resolution()
            
            logger.info("✅ 版本控制演示完成")
            
        except Exception as e:
            logger.error(f"❌ 演示运行失败: {e}")
    
    async def demo_semantic_versioning(self):
        """演示语义版本功能"""
        logger.info("📋 演示1: 语义版本解析和比较")
        
        # 版本解析
        versions = [
            "1.0.0",
            "1.2.3-alpha.1",
            "2.0.0-beta.2+build.123",
            "1.0.0-rc.1",
            "1.1.0"
        ]
        
        parsed_versions = []
        for version_str in versions:
            try:
                version = SemanticVersion.parse(version_str)
                parsed_versions.append(version)
                logger.info(f"  ✓ 解析版本: {version_str} -> {version}")
            except Exception as e:
                logger.error(f"  ❌ 解析失败: {version_str} - {e}")
        
        # 版本比较
        logger.info("  版本比较:")
        for i, v1 in enumerate(parsed_versions):
            for v2 in parsed_versions[i+1:]:
                if v1 < v2:
                    logger.info(f"    {v1} < {v2}")
                elif v1 > v2:
                    logger.info(f"    {v1} > {v2}")
                else:
                    logger.info(f"    {v1} == {v2}")
        
        # 兼容性检查
        logger.info("  兼容性检查:")
        v1 = SemanticVersion.parse("1.2.0")
        v2 = SemanticVersion.parse("1.2.3")
        v3 = SemanticVersion.parse("2.0.0")
        
        compat = v1.is_compatible_with(v2)
        logger.info(f"    {v1} 与 {v2}: {compat.value}")
        
        compat = v1.is_compatible_with(v3)
        logger.info(f"    {v1} 与 {v3}: {compat.value}")
        
        logger.info("📋 语义版本演示完成\n")
    
    async def demo_version_registration(self):
        """演示版本注册和查询"""
        logger.info("📦 演示2: 版本注册和查询")
        
        # 注册所有演示版本
        for plugin_id, versions in self.demo_versions.items():
            for version_info in versions:
                success = await self.version_manager.register_plugin_version(version_info)
                if success:
                    logger.info(f"  ✓ 注册版本: {plugin_id} v{version_info.version}")
                else:
                    logger.error(f"  ❌ 注册失败: {plugin_id} v{version_info.version}")
        
        # 模拟当前版本
        self.version_manager.current_versions = {
            "session_manager": SemanticVersion.parse("1.0.0"),
            "fingerprint_manager": SemanticVersion.parse("1.0.0"),
            "behavior_simulator": SemanticVersion.parse("1.0.0")
        }
        
        # 查询版本信息
        logger.info("  查询版本信息:")
        for plugin_id in self.demo_versions.keys():
            current_info = await self.version_manager.get_plugin_version(plugin_id)
            if current_info:
                logger.info(f"    {plugin_id}: v{current_info.version} ({current_info.stability})")
            else:
                logger.error(f"    {plugin_id}: 未找到版本信息")
        
        # 版本管理摘要
        summary = self.version_manager.get_version_summary()
        logger.info(f"  版本管理摘要:")
        logger.info(f"    总插件数: {summary['total_plugins']}")
        logger.info(f"    当前版本: {summary['current_versions']}")
        logger.info(f"    总版本数: {summary['total_versions']}")
        
        logger.info("📦 版本注册演示完成\n")
    
    async def demo_dependency_checking(self):
        """演示依赖关系检查"""
        logger.info("🔗 演示3: 依赖关系检查")
        
        # 检查行为模拟插件的依赖
        plugin_id = "behavior_simulator"
        version = SemanticVersion.parse("1.0.0")
        
        version_info = await self.version_manager.get_plugin_version(plugin_id, str(version))
        if version_info:
            logger.info(f"  检查 {plugin_id} v{version} 的依赖:")
            
            for dep in version_info.dependencies:
                logger.info(f"    依赖: {dep.plugin_id} {dep.version_constraint.specifier}")
                
                # 检查当前版本是否满足依赖
                current_dep_version = self.version_manager.current_versions.get(dep.plugin_id)
                if current_dep_version:
                    satisfies = dep.version_constraint.satisfies(current_dep_version)
                    status = "✅" if satisfies else "❌"
                    logger.info(f"      当前版本 {current_dep_version}: {status}")
                else:
                    logger.info(f"      未安装: ❌")
        
        logger.info("🔗 依赖关系演示完成\n")
    
    async def demo_compatibility_checking(self):
        """演示兼容性检查"""
        logger.info("🔍 演示4: 版本兼容性检查")
        
        # 测试不同版本的兼容性
        test_cases = [
            ("session_manager", "1.1.0"),
            ("session_manager", "2.0.0-beta.1"),
            ("fingerprint_manager", "1.2.0")
        ]
        
        for plugin_id, version_str in test_cases:
            version = SemanticVersion.parse(version_str)
            result = await self.version_manager.check_compatibility(plugin_id, version)
            
            status = "✅" if result['compatible'] else "❌"
            logger.info(f"  兼容性检查 {plugin_id} v{version}: {status}")
            
            if result['issues']:
                for issue in result['issues']:
                    logger.info(f"    问题: {issue}")
            
            if result['warnings']:
                for warning in result['warnings']:
                    logger.info(f"    警告: {warning}")
            
            if result['dependency_conflicts']:
                for conflict in result['dependency_conflicts']:
                    logger.info(f"    依赖冲突: {conflict}")
        
        logger.info("🔍 兼容性检查演示完成\n")
    
    async def demo_plugin_upgrade(self):
        """演示插件升级"""
        logger.info("⬆️ 演示5: 插件升级")
        
        # 升级会话管理插件
        plugin_id = "session_manager"
        target_version = SemanticVersion.parse("1.1.0")
        
        logger.info(f"  升级 {plugin_id} 到 v{target_version}")
        
        result = await self.version_manager.upgrade_plugin(plugin_id, target_version)
        
        if result['success']:
            logger.info(f"  ✅ 升级成功: {result['old_version']} -> {result['new_version']}")
            for action in result['actions']:
                logger.info(f"    操作: {action}")
        else:
            logger.error(f"  ❌ 升级失败:")
            for action in result['actions']:
                logger.error(f"    错误: {action}")
        
        # 尝试升级到beta版本
        logger.info(f"  尝试升级到beta版本...")
        beta_version = SemanticVersion.parse("2.0.0-beta.1")
        result = await self.version_manager.upgrade_plugin(plugin_id, beta_version)
        
        if result['success']:
            logger.info(f"  ✅ Beta升级成功: {result['old_version']} -> {result['new_version']}")
        else:
            logger.info(f"  ⚠️ Beta升级跳过（预期行为）")
            for action in result['actions'][:1]:  # 只显示第一个错误
                logger.info(f"    原因: {action}")
        
        logger.info("⬆️ 插件升级演示完成\n")
    
    async def demo_plugin_rollback(self):
        """演示版本回退"""
        logger.info("⬇️ 演示6: 版本回退")
        
        plugin_id = "session_manager"
        current_version = self.version_manager.current_versions.get(plugin_id)
        
        logger.info(f"  当前版本: {plugin_id} v{current_version}")
        logger.info(f"  执行回退...")
        
        result = await self.version_manager.rollback_plugin(plugin_id)
        
        if result['success']:
            logger.info(f"  ✅ 回退成功: {result['old_version']} -> {result['new_version']}")
            for action in result['actions']:
                logger.info(f"    操作: {action}")
        else:
            logger.error(f"  ❌ 回退失败:")
            for action in result['actions']:
                logger.error(f"    错误: {action}")
        
        logger.info("⬇️ 版本回退演示完成\n")
    
    async def demo_dependency_resolution(self):
        """演示依赖解析"""
        logger.info("🧩 演示7: 依赖解析")
        
        # 解析行为模拟插件的依赖
        plugin_id = "behavior_simulator"
        version = SemanticVersion.parse("1.0.0")
        
        logger.info(f"  解析 {plugin_id} v{version} 的依赖...")
        
        result = await self.version_manager.resolve_dependencies(plugin_id, version)
        
        if result['success']:
            logger.info(f"  ✅ 依赖解析成功")
            logger.info(f"  解析计划:")
            for item in result['resolution_plan']:
                logger.info(f"    {item['action']}: {item['plugin_id']} v{item['version']}")
        else:
            logger.error(f"  ❌ 依赖解析失败:")
            for conflict in result['conflicts']:
                logger.error(f"    冲突: {conflict}")
        
        if result['warnings']:
            for warning in result['warnings']:
                logger.info(f"    警告: {warning}")
        
        logger.info("🧩 依赖解析演示完成\n")
    
    def cleanup(self):
        """清理演示数据"""
        try:
            # 清理版本存储目录
            import shutil
            if self.version_manager.version_storage_path.exists():
                shutil.rmtree(self.version_manager.version_storage_path)
            logger.info("🧹 清理演示数据完成")
        except Exception as e:
            logger.warning(f"清理数据失败: {e}")


async def main():
    """主函数"""
    demo = VersionControlDemo()
    
    try:
        await demo.run_demo()
    finally:
        # 可选择是否清理演示数据
        # demo.cleanup()
        pass


if __name__ == "__main__":
    asyncio.run(main())