"""
插件版本控制单元测试

测试内容包括：
1. 语义版本解析和比较
2. 版本约束验证
3. 插件版本信息管理
4. 依赖关系解析
5. 兼容性检查
6. 插件升级和回退
7. 循环依赖检测

Author: Mercari AI Agent Team
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

from mercari_agent.plugins.version_control import (
    SemanticVersion, VersionConstraint, VersionConstraintType,
    PluginVersionInfo, PluginDependency, PluginVersionManager,
    VersionCompatibility, UpgradeStrategy, DependencyGraph
)
from mercari_agent.plugins.interfaces import PluginType


class TestSemanticVersion:
    """语义版本测试"""
    
    def test_parse_valid_versions(self):
        """测试有效版本解析"""
        test_cases = [
            ("1.0.0", SemanticVersion(1, 0, 0)),
            ("1.2.3", SemanticVersion(1, 2, 3)),
            ("1.0.0-alpha", SemanticVersion(1, 0, 0, "alpha")),
            ("1.0.0-beta.1", SemanticVersion(1, 0, 0, "beta.1")),
            ("1.0.0+build.1", SemanticVersion(1, 0, 0, "", "build.1")),
            ("1.0.0-alpha+build.1", SemanticVersion(1, 0, 0, "alpha", "build.1")),
            ("10.20.30", SemanticVersion(10, 20, 30)),
            ("1.0.0-x.7.z.92", SemanticVersion(1, 0, 0, "x.7.z.92"))
        ]
        
        for version_str, expected in test_cases:
            result = SemanticVersion.parse(version_str)
            assert result == expected, f"Failed to parse {version_str}"
            assert str(result) == version_str, f"String representation mismatch for {version_str}"
    
    def test_parse_invalid_versions(self):
        """测试无效版本解析"""
        invalid_versions = [
            "1.2",
            "1.2.3.4",
            "1.2.3-",
            "1.2.3+",
            "a.b.c",
            "-1.0.0",
            "1.-1.0",
            "1.0.-1",
            "",
            "1.0.0-"
        ]
        
        for version_str in invalid_versions:
            with pytest.raises(ValueError):
                SemanticVersion.parse(version_str)
    
    def test_version_comparison(self):
        """测试版本比较"""
        versions = [
            SemanticVersion(1, 0, 0, "alpha"),
            SemanticVersion(1, 0, 0, "beta"),
            SemanticVersion(1, 0, 0, "rc.1"),
            SemanticVersion(1, 0, 0),
            SemanticVersion(1, 0, 1),
            SemanticVersion(1, 1, 0),
            SemanticVersion(2, 0, 0),
            SemanticVersion(2, 0, 0, "alpha")
        ]
        
        # 测试递增顺序
        for i in range(len(versions) - 1):
            assert versions[i] < versions[i + 1], f"{versions[i]} should be less than {versions[i + 1]}"
            assert versions[i] <= versions[i + 1]
            assert versions[i + 1] > versions[i]
            assert versions[i + 1] >= versions[i]
            assert versions[i] != versions[i + 1]
    
    def test_version_equality(self):
        """测试版本相等性"""
        v1 = SemanticVersion(1, 2, 3, "alpha", "build.1")
        v2 = SemanticVersion(1, 2, 3, "alpha", "build.2")  # 构建元数据不影响比较
        v3 = SemanticVersion(1, 2, 3, "alpha", "build.1")
        
        assert v1 == v2, "Build metadata should not affect equality"
        assert v1 == v3
        assert not (v1 != v2)
    
    def test_version_compatibility(self):
        """测试版本兼容性"""
        base_version = SemanticVersion(1, 2, 3)
        
        # 兼容版本
        compatible_version = SemanticVersion(1, 2, 4)
        assert base_version.is_compatible_with(compatible_version) == VersionCompatibility.COMPATIBLE
        
        # 向后兼容版本
        backward_compatible = SemanticVersion(1, 3, 0)
        assert base_version.is_compatible_with(backward_compatible) == VersionCompatibility.BACKWARD_COMPATIBLE
        
        # 破坏性变更
        breaking_version = SemanticVersion(2, 0, 0)
        assert base_version.is_compatible_with(breaking_version) == VersionCompatibility.BREAKING_CHANGE
        
        # 不兼容版本
        incompatible_version = SemanticVersion(1, 1, 0)
        assert base_version.is_compatible_with(incompatible_version) == VersionCompatibility.INCOMPATIBLE
    
    def test_version_increment(self):
        """测试版本递增"""
        base_version = SemanticVersion(1, 2, 3)
        
        # 主版本递增
        major_inc = base_version.increment("major")
        assert major_inc == SemanticVersion(2, 0, 0)
        
        # 次版本递增
        minor_inc = base_version.increment("minor")
        assert minor_inc == SemanticVersion(1, 3, 0)
        
        # 补丁版本递增
        patch_inc = base_version.increment("patch")
        assert patch_inc == SemanticVersion(1, 2, 4)
        
        # 无效级别
        with pytest.raises(ValueError):
            base_version.increment("invalid")


class TestVersionConstraint:
    """版本约束测试"""
    
    def test_parse_constraints(self):
        """测试约束解析"""
        test_cases = [
            ("*", VersionConstraintType.LATEST),
            ("latest", VersionConstraintType.LATEST),
            ("==1.0.0", VersionConstraintType.EXACT),
            (">=1.0.0", VersionConstraintType.MINIMUM),
            ("~=1.0.0", VersionConstraintType.COMPATIBLE),
            (">=1.0.0,<2.0.0", VersionConstraintType.RANGE),
            ("1.0.0", VersionConstraintType.EXACT)
        ]
        
        for constraint_str, expected_type in test_cases:
            constraint = VersionConstraint.parse(constraint_str)
            assert constraint.constraint_type == expected_type, f"Failed to parse {constraint_str}"
    
    def test_constraint_satisfaction(self):
        """测试约束满足性"""
        # 精确版本
        exact_constraint = VersionConstraint.parse("==1.0.0")
        assert exact_constraint.satisfies(SemanticVersion(1, 0, 0))
        assert not exact_constraint.satisfies(SemanticVersion(1, 0, 1))
        
        # 最小版本
        min_constraint = VersionConstraint.parse(">=1.0.0")
        assert min_constraint.satisfies(SemanticVersion(1, 0, 0))
        assert min_constraint.satisfies(SemanticVersion(1, 1, 0))
        assert min_constraint.satisfies(SemanticVersion(2, 0, 0))
        assert not min_constraint.satisfies(SemanticVersion(0, 9, 0))
        
        # 兼容版本
        compatible_constraint = VersionConstraint.parse("~=1.2.0")
        assert compatible_constraint.satisfies(SemanticVersion(1, 2, 0))
        assert compatible_constraint.satisfies(SemanticVersion(1, 2, 5))
        assert not compatible_constraint.satisfies(SemanticVersion(1, 3, 0))
        assert not compatible_constraint.satisfies(SemanticVersion(2, 0, 0))
        
        # 最新版本
        latest_constraint = VersionConstraint.parse("*")
        assert latest_constraint.satisfies(SemanticVersion(1, 0, 0))
        assert latest_constraint.satisfies(SemanticVersion(999, 999, 999))


class TestPluginVersionInfo:
    """插件版本信息测试"""
    
    def test_version_info_creation(self):
        """测试版本信息创建"""
        dependencies = [
            PluginDependency(
                plugin_id="dep1",
                plugin_type=PluginType.SESSION_MANAGEMENT,
                version_constraint=VersionConstraint.parse(">=1.0.0"),
                description="Test dependency"
            )
        ]
        
        version_info = PluginVersionInfo(
            plugin_id="test_plugin",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=dependencies,
            description="Test plugin version",
            author="Test Author",
            stability="stable"
        )
        
        assert version_info.plugin_id == "test_plugin"
        assert version_info.plugin_type == PluginType.FINGERPRINT
        assert version_info.version == SemanticVersion(1, 0, 0)
        assert len(version_info.dependencies) == 1
        assert version_info.stability == "stable"
    
    def test_version_info_serialization(self):
        """测试版本信息序列化"""
        version_info = PluginVersionInfo(
            plugin_id="test_plugin",
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            version=SemanticVersion(1, 2, 3),
            description="Test plugin",
            author="Test Author",
            stability="beta"
        )
        
        # 序列化
        data = version_info.to_dict()
        assert data["plugin_id"] == "test_plugin"
        assert data["plugin_type"] == "behavior_simulation"
        assert data["version"] == "1.2.3"
        assert data["stability"] == "beta"
        
        # 反序列化
        restored = PluginVersionInfo.from_dict(data)
        assert restored.plugin_id == version_info.plugin_id
        assert restored.plugin_type == version_info.plugin_type
        assert restored.version == version_info.version
        assert restored.stability == version_info.stability


class TestDependencyGraph:
    """依赖关系图测试"""
    
    def test_add_plugin(self):
        """测试添加插件"""
        graph = DependencyGraph()
        
        # 创建插件版本信息
        plugin_a = PluginVersionInfo(
            plugin_id="plugin_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_b", PluginType.FINGERPRINT, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_b = PluginVersionInfo(
            plugin_id="plugin_b",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[]
        )
        
        graph.add_plugin(plugin_a)
        graph.add_plugin(plugin_b)
        
        assert "plugin_a" in graph.nodes
        assert "plugin_b" in graph.nodes
        assert graph.edges["plugin_a"] == ["plugin_b"]
        assert graph.edges["plugin_b"] == []
    
    def test_cycle_detection(self):
        """测试循环依赖检测"""
        graph = DependencyGraph()
        
        # 创建循环依赖
        plugin_a = PluginVersionInfo(
            plugin_id="plugin_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_b", PluginType.FINGERPRINT, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_b = PluginVersionInfo(
            plugin_id="plugin_b",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_a", PluginType.SESSION_MANAGEMENT, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        graph.add_plugin(plugin_a)
        graph.add_plugin(plugin_b)
        
        has_cycle, cycle_path = graph.has_cycle()
        assert has_cycle
        assert len(cycle_path) > 0
    
    def test_topological_sort(self):
        """测试拓扑排序"""
        graph = DependencyGraph()
        
        # 创建有向无环图
        plugin_a = PluginVersionInfo(
            plugin_id="plugin_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_b", PluginType.FINGERPRINT, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_b = PluginVersionInfo(
            plugin_id="plugin_b",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_c", PluginType.BEHAVIOR_SIMULATION, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_c = PluginVersionInfo(
            plugin_id="plugin_c",
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            version=SemanticVersion(1, 0, 0),
            dependencies=[]
        )
        
        graph.add_plugin(plugin_a)
        graph.add_plugin(plugin_b)
        graph.add_plugin(plugin_c)
        
        sorted_order = graph.topological_sort()
        assert len(sorted_order) == 3
        
        # plugin_c应该在plugin_b之前，plugin_b应该在plugin_a之前
        assert sorted_order.index("plugin_c") < sorted_order.index("plugin_b")
        assert sorted_order.index("plugin_b") < sorted_order.index("plugin_a")


class TestPluginVersionManager:
    """插件版本管理器测试"""
    
    @pytest.fixture
    def version_manager(self):
        """版本管理器实例"""
        return PluginVersionManager()
    
    @pytest.fixture
    def sample_version_info(self):
        """示例版本信息"""
        return PluginVersionInfo(
            plugin_id="test_plugin",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            description="Test plugin",
            author="Test Author",
            stability="stable"
        )
    
    @pytest.mark.asyncio
    async def test_register_plugin_version(self, version_manager, sample_version_info):
        """测试注册插件版本"""
        success = await version_manager.register_plugin_version(sample_version_info)
        assert success
        
        # 验证注册结果
        assert "test_plugin" in version_manager.plugin_versions
        assert "1.0.0" in version_manager.plugin_versions["test_plugin"]
        
        retrieved = await version_manager.get_plugin_version("test_plugin", "1.0.0")
        assert retrieved is not None
        assert retrieved.plugin_id == "test_plugin"
        assert retrieved.version == SemanticVersion(1, 0, 0)
    
    @pytest.mark.asyncio
    async def test_get_plugin_version(self, version_manager, sample_version_info):
        """测试获取插件版本"""
        await version_manager.register_plugin_version(sample_version_info)
        
        # 获取指定版本
        version_info = await version_manager.get_plugin_version("test_plugin", "1.0.0")
        assert version_info is not None
        assert version_info.version == SemanticVersion(1, 0, 0)
        
        # 获取不存在的版本
        missing_version = await version_manager.get_plugin_version("test_plugin", "2.0.0")
        assert missing_version is None
        
        # 获取不存在的插件
        missing_plugin = await version_manager.get_plugin_version("missing_plugin", "1.0.0")
        assert missing_plugin is None
    
    @pytest.mark.asyncio
    async def test_check_compatibility(self, version_manager, sample_version_info):
        """测试兼容性检查"""
        await version_manager.register_plugin_version(sample_version_info)
        
        # 兼容的版本
        result = await version_manager.check_compatibility("test_plugin", SemanticVersion(1, 0, 0))
        assert result["compatible"] is True
        assert len(result["issues"]) == 0
        
        # 不存在的版本
        result = await version_manager.check_compatibility("test_plugin", SemanticVersion(2, 0, 0))
        assert result["compatible"] is False
        assert len(result["issues"]) > 0
    
    @pytest.mark.asyncio
    async def test_resolve_dependencies(self, version_manager):
        """测试依赖解析"""
        # 创建依赖关系
        dependency = PluginDependency(
            plugin_id="dependency_plugin",
            plugin_type=PluginType.FINGERPRINT,
            version_constraint=VersionConstraint.parse(">=1.0.0")
        )
        
        main_plugin = PluginVersionInfo(
            plugin_id="main_plugin",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[dependency]
        )
        
        dep_plugin = PluginVersionInfo(
            plugin_id="dependency_plugin",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0)
        )
        
        await version_manager.register_plugin_version(main_plugin)
        await version_manager.register_plugin_version(dep_plugin)
        
        # 解析依赖
        result = await version_manager.resolve_dependencies("main_plugin", SemanticVersion(1, 0, 0))
        assert result["success"] is True
        assert len(result["resolution_plan"]) == 2  # 主插件 + 依赖插件
    
    @pytest.mark.asyncio
    async def test_upgrade_plugin(self, version_manager):
        """测试插件升级"""
        # 注册多个版本
        v1 = PluginVersionInfo(
            plugin_id="upgrade_test",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            stability="stable"
        )
        
        v2 = PluginVersionInfo(
            plugin_id="upgrade_test",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 1, 0),
            stability="stable"
        )
        
        await version_manager.register_plugin_version(v1)
        await version_manager.register_plugin_version(v2)
        
        # 设置当前版本
        version_manager.current_versions["upgrade_test"] = SemanticVersion(1, 0, 0)
        
        # 升级到新版本
        result = await version_manager.upgrade_plugin("upgrade_test", SemanticVersion(1, 1, 0))
        assert result["success"] is True
        assert result["old_version"] == "1.0.0"
        assert result["new_version"] == "1.1.0"
        assert version_manager.current_versions["upgrade_test"] == SemanticVersion(1, 1, 0)
    
    @pytest.mark.asyncio
    async def test_rollback_plugin(self, version_manager):
        """测试插件回退"""
        # 注册多个版本
        v1 = PluginVersionInfo(
            plugin_id="rollback_test",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            stability="stable"
        )
        
        v2 = PluginVersionInfo(
            plugin_id="rollback_test",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 1, 0),
            stability="stable"
        )
        
        await version_manager.register_plugin_version(v1)
        await version_manager.register_plugin_version(v2)
        
        # 设置当前版本为较新版本
        version_manager.current_versions["rollback_test"] = SemanticVersion(1, 1, 0)
        
        # 回退到较旧版本
        result = await version_manager.rollback_plugin("rollback_test", SemanticVersion(1, 0, 0))
        assert result["success"] is True
        assert result["old_version"] == "1.1.0"
        assert result["new_version"] == "1.0.0"
        assert version_manager.current_versions["rollback_test"] == SemanticVersion(1, 0, 0)
    
    def test_get_version_summary(self, version_manager):
        """测试版本摘要"""
        # 设置一些测试数据
        version_manager.current_versions["test_plugin"] = SemanticVersion(1, 0, 0)
        version_manager.plugin_versions["test_plugin"] = {
            "1.0.0": PluginVersionInfo(
                plugin_id="test_plugin",
                plugin_type=PluginType.SESSION_MANAGEMENT,
                version=SemanticVersion(1, 0, 0)
            )
        }
        
        summary = version_manager.get_version_summary()
        assert summary["total_plugins"] == 1
        assert "test_plugin" in summary["current_versions"]
        assert summary["current_versions"]["test_plugin"] == "1.0.0"
        assert summary["total_versions"] == 1
        assert summary["framework_version"] == "1.0.0"
        assert summary["upgrade_strategy"] == "moderate"


@pytest.mark.integration
class TestVersionControlIntegration:
    """版本控制集成测试"""
    
    @pytest.mark.asyncio
    async def test_complex_dependency_resolution(self):
        """测试复杂依赖解析"""
        version_manager = PluginVersionManager()
        
        # 创建复杂的依赖关系
        # A depends on B and C
        # B depends on D
        # C depends on D
        # D has no dependencies
        
        plugin_d = PluginVersionInfo(
            plugin_id="plugin_d",
            plugin_type=PluginType.CAPTCHA_DETECTION,
            version=SemanticVersion(1, 0, 0)
        )
        
        plugin_c = PluginVersionInfo(
            plugin_id="plugin_c",
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_d", PluginType.CAPTCHA_DETECTION, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_b = PluginVersionInfo(
            plugin_id="plugin_b",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_d", PluginType.CAPTCHA_DETECTION, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        plugin_a = PluginVersionInfo(
            plugin_id="plugin_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_b", PluginType.FINGERPRINT, VersionConstraint.parse(">=1.0.0")),
                PluginDependency("plugin_c", PluginType.BEHAVIOR_SIMULATION, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        # 注册所有版本
        await version_manager.register_plugin_version(plugin_d)
        await version_manager.register_plugin_version(plugin_c)
        await version_manager.register_plugin_version(plugin_b)
        await version_manager.register_plugin_version(plugin_a)
        
        # 解析依赖
        result = await version_manager.resolve_dependencies("plugin_a", SemanticVersion(1, 0, 0))
        assert result["success"] is True
        assert len(result["resolution_plan"]) == 4  # 所有四个插件
        
        # 验证依赖顺序
        plan_ids = [item["plugin_id"] for item in result["resolution_plan"]]
        assert plan_ids.index("plugin_d") < plan_ids.index("plugin_c")
        assert plan_ids.index("plugin_d") < plan_ids.index("plugin_b")
        assert plan_ids.index("plugin_c") < plan_ids.index("plugin_a")
        assert plan_ids.index("plugin_b") < plan_ids.index("plugin_a")
    
    @pytest.mark.asyncio
    async def test_version_conflict_detection(self):
        """测试版本冲突检测"""
        version_manager = PluginVersionManager()
        
        # 创建版本冲突场景
        # A depends on B >=1.0.0
        # A depends on C >=1.0.0
        # B depends on D ==1.0.0
        # C depends on D ==2.0.0  # 冲突！
        
        plugin_d_v1 = PluginVersionInfo(
            plugin_id="plugin_d",
            plugin_type=PluginType.CAPTCHA_DETECTION,
            version=SemanticVersion(1, 0, 0)
        )
        
        plugin_d_v2 = PluginVersionInfo(
            plugin_id="plugin_d",
            plugin_type=PluginType.CAPTCHA_DETECTION,
            version=SemanticVersion(2, 0, 0)
        )
        
        plugin_b = PluginVersionInfo(
            plugin_id="plugin_b",
            plugin_type=PluginType.FINGERPRINT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_d", PluginType.CAPTCHA_DETECTION, VersionConstraint.parse("==1.0.0"))
            ]
        )
        
        plugin_c = PluginVersionInfo(
            plugin_id="plugin_c",
            plugin_type=PluginType.BEHAVIOR_SIMULATION,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_d", PluginType.CAPTCHA_DETECTION, VersionConstraint.parse("==2.0.0"))
            ]
        )
        
        plugin_a = PluginVersionInfo(
            plugin_id="plugin_a",
            plugin_type=PluginType.SESSION_MANAGEMENT,
            version=SemanticVersion(1, 0, 0),
            dependencies=[
                PluginDependency("plugin_b", PluginType.FINGERPRINT, VersionConstraint.parse(">=1.0.0")),
                PluginDependency("plugin_c", PluginType.BEHAVIOR_SIMULATION, VersionConstraint.parse(">=1.0.0"))
            ]
        )
        
        # 注册所有版本
        await version_manager.register_plugin_version(plugin_d_v1)
        await version_manager.register_plugin_version(plugin_d_v2)
        await version_manager.register_plugin_version(plugin_b)
        await version_manager.register_plugin_version(plugin_c)
        await version_manager.register_plugin_version(plugin_a)
        
        # 解析依赖，应该检测到冲突
        result = await version_manager.resolve_dependencies("plugin_a", SemanticVersion(1, 0, 0))
        assert result["success"] is False
        assert len(result["conflicts"]) > 0
        
        # 验证冲突信息包含版本冲突
        conflict_messages = " ".join(result["conflicts"])
        assert "plugin_d" in conflict_messages
        assert "conflict" in conflict_messages.lower()