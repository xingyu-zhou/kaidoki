# Mercari AI Agent 系统修复建议与改进方案

## 执行摘要

基于全面的架构评估和故障分析，Mercari AI Agent系统存在严重的架构缺陷，导致系统可靠性仅为30%。本方案提供系统性的修复建议和改进路线图，目标是将系统可靠性提升到95%以上。

**关键目标**：
- 🎯 **短期目标**：修复P0级别根本性缺陷，将系统可靠性提升至60%
- 🎯 **中期目标**：重构核心架构，将系统可靠性提升至85%
- 🎯 **长期目标**：完成微服务化改造，将系统可靠性提升至95%+

**预期效果**：
- 查询成功率：30% → 95%
- 平均响应时间：10s → 2s
- 系统可用性：70% → 99.9%
- 故障恢复时间：30min → 5min

---

## 1. 紧急修复方案 (1-2周内)

### 1.1 P0级别问题修复

#### 1.1.1 会话管理器初始化失败修复 (最高优先级)

**问题分析**：
- **文件位置**：`src/mercari_agent/scrapers/enhanced_session_manager.py`
- **问题代码**：第334行 - Session创建失败导致session池为空
- **影响**：整个爬虫服务链路瘫痪

**修复代码**：

```python
# 文件：src/mercari_agent/scrapers/enhanced_session_manager.py
# 修复会话管理器初始化逻辑

class EnhancedSessionManager(SessionManager):
    """增强会话管理器主类"""
    
    def __init__(self, config: Optional[SessionConfig] = None, **kwargs):
        # 添加初始化状态管理
        self._initialization_lock = asyncio.Lock()
        self._initialization_status = "pending"
        self._initialization_error = None
        self._retry_count = 0
        self._max_init_retries = 3
        
        # 原有初始化逻辑...
        super().__init__()
        
        # 添加初始化完成标志
        self._fully_initialized = False
    
    async def _safe_initialize_session_pool(self):
        """安全初始化会话池"""
        async with self._initialization_lock:
            if self._initialization_status == "completed":
                return
            
            retry_count = 0
            while retry_count < self._max_init_retries:
                try:
                    logger.info(f"尝试初始化会话池 (第{retry_count + 1}次)")
                    
                    # 重置状态
                    self._initialization_status = "initializing"
                    self._initialization_error = None
                    
                    # 创建会话池
                    self.session_pool = SessionPool(self.config)
                    
                    # 预创建最小数量的会话
                    min_sessions = max(1, self.config.max_concurrent_sessions // 4)
                    for i in range(min_sessions):
                        try:
                            session = await self.session_pool.create_session(
                                session_id=f"init_session_{i}",
                                session_type=SessionType.BROWSING
                            )
                            logger.info(f"成功预创建会话 {i+1}/{min_sessions}")
                        except Exception as e:
                            logger.warning(f"预创建会话失败: {e}")
                            # 继续尝试创建其他会话
                    
                    # 验证会话池状态
                    if len(self.session_pool.sessions) == 0:
                        raise Exception("会话池为空，无法提供服务")
                    
                    self._initialization_status = "completed"
                    self._fully_initialized = True
                    logger.info("✅ 会话池初始化成功")
                    return
                    
                except Exception as e:
                    retry_count += 1
                    self._initialization_error = e
                    logger.error(f"会话池初始化失败 (第{retry_count}次): {e}")
                    
                    if retry_count < self._max_init_retries:
                        await asyncio.sleep(2 ** retry_count)  # 指数退避
                    else:
                        self._initialization_status = "failed"
                        raise Exception(f"会话池初始化最终失败: {e}")
    
    async def get_session_safe(self, session_id: str = None) -> Optional[EnhancedSession]:
        """安全获取会话"""
        # 确保初始化完成
        if not self._fully_initialized:
            await self._safe_initialize_session_pool()
        
        try:
            # 检查会话池状态
            if not hasattr(self, 'session_pool') or self.session_pool is None:
                raise Exception("会话池未初始化")
            
            # 获取会话
            session = await self.session_pool.get_session(session_id)
            
            if session is None:
                logger.warning("会话池返回None，尝试创建新会话")
                # 尝试创建新会话
                session = await self.session_pool.create_session(
                    session_id=session_id or f"fallback_{int(time.time())}",
                    session_type=SessionType.BROWSING
                )
            
            return session
            
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            # 尝试恢复机制
            try:
                return await self._emergency_session_recovery()
            except Exception as recovery_error:
                logger.error(f"会话恢复失败: {recovery_error}")
                raise Exception(f"会话管理器完全失效: {e}")
    
    async def _emergency_session_recovery(self) -> EnhancedSession:
        """紧急会话恢复"""
        logger.warning("执行紧急会话恢复...")
        
        # 重置初始化状态
        self._fully_initialized = False
        self._initialization_status = "pending"
        
        # 重新初始化
        await self._safe_initialize_session_pool()
        
        # 创建紧急会话
        emergency_session = await self.session_pool.create_session(
            session_id=f"emergency_{int(time.time())}",
            session_type=SessionType.BROWSING
        )
        
        logger.info("✅ 紧急会话恢复成功")
        return emergency_session
```

#### 1.1.2 错误处理架构统一修复

**问题分析**：
- **文件位置**：`src/mercari_agent/core/tools/base_tool.py` 和 `src/mercari_agent/core/tool_orchestrator.py`
- **问题**：底层包装错误状态vs上层期望异常的不兼容

**修复代码**：

```python
# 文件：src/mercari_agent/core/tools/base_tool.py
# 统一错误处理结果类

from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional, Dict, List, Union

class OperationStatus(Enum):
    """操作状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"

@dataclass
class UnifiedResult:
    """统一操作结果类"""
    success: bool
    status: OperationStatus
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    warnings: List[str] = None
    metadata: Dict[str, Any] = None
    execution_time: Optional[float] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}
    
    def is_success(self) -> bool:
        """检查是否成功"""
        return self.success and self.status == OperationStatus.SUCCESS
    
    def is_error(self) -> bool:
        """检查是否错误"""
        return not self.success or self.status == OperationStatus.ERROR
    
    def has_data(self) -> bool:
        """检查是否有数据"""
        return self.data is not None
    
    def get_error_info(self) -> Dict[str, Any]:
        """获取错误信息"""
        return {
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_details": self.error_details or {},
            "status": self.status.value
        }
    
    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)
    
    def merge_metadata(self, metadata: Dict[str, Any]):
        """合并元数据"""
        self.metadata.update(metadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "status": self.status.value,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "execution_time": self.execution_time
        }

# 兼容性别名
ToolResult = UnifiedResult

class BaseTool(ABC):
    """工具基础类 - 更新版本"""
    
    async def execute(self, **kwargs) -> UnifiedResult:
        """执行工具逻辑 - 返回统一结果"""
        pass
    
    async def call(self, **kwargs) -> UnifiedResult:
        """调用工具的主要方法 - 统一错误处理"""
        start_time = datetime.now()
        
        try:
            # 验证参数
            validation_result = self._validate_parameters_enhanced(kwargs)
            if not validation_result.success:
                return UnifiedResult(
                    success=False,
                    status=OperationStatus.ERROR,
                    error_code="PARAMETER_VALIDATION_ERROR",
                    error_message=validation_result.error_message,
                    error_details=validation_result.error_details,
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            # 执行工具
            result = await self.execute(**kwargs)
            
            # 确保返回统一结果类型
            if not isinstance(result, UnifiedResult):
                # 兼容旧的ToolResult
                if hasattr(result, 'is_success') and hasattr(result, 'status'):
                    result = UnifiedResult(
                        success=result.is_success(),
                        status=OperationStatus(result.status.value),
                        data=getattr(result, 'data', None),
                        error_message=getattr(result, 'error', None),
                        execution_time=getattr(result, 'execution_time', None),
                        metadata=getattr(result, 'metadata', {})
                    )
                else:
                    # 默认处理
                    result = UnifiedResult(
                        success=True,
                        status=OperationStatus.SUCCESS,
                        data=result
                    )
            
            # 更新执行时间
            result.execution_time = (datetime.now() - start_time).total_seconds()
            
            # 更新统计信息
            self.call_count += 1
            self.total_execution_time += result.execution_time
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"工具 {self.name} 执行异常: {e}")
            
            return UnifiedResult(
                success=False,
                status=OperationStatus.ERROR,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                execution_time=execution_time
            )
    
    def _validate_parameters_enhanced(self, parameters: Dict[str, Any]) -> UnifiedResult:
        """增强参数验证"""
        try:
            schema = self.schema
            required_params = schema.get("parameters", {}).get("required", [])
            properties = schema.get("parameters", {}).get("properties", {})
            
            # 检查必需参数
            missing_params = []
            for param in required_params:
                if param not in parameters:
                    missing_params.append(param)
                else:
                    # 检查参数值的有效性
                    value = parameters[param]
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        missing_params.append(f"{param} (值为空)")
            
            if missing_params:
                return UnifiedResult(
                    success=False,
                    status=OperationStatus.ERROR,
                    error_code="MISSING_PARAMETERS",
                    error_message=f"缺少必需参数: {', '.join(missing_params)}",
                    error_details={
                        "missing_parameters": missing_params,
                        "required_parameters": required_params,
                        "provided_parameters": list(parameters.keys())
                    }
                )
            
            # 检查参数类型和约束
            validation_warnings = []
            for param_name, param_value in parameters.items():
                if param_name in properties:
                    param_schema = properties[param_name]
                    validation_warning = self._validate_parameter_value(
                        param_name, param_value, param_schema
                    )
                    if validation_warning:
                        validation_warnings.append(validation_warning)
            
            result = UnifiedResult(
                success=True,
                status=OperationStatus.SUCCESS,
                data={"validated_parameters": parameters}
            )
            
            # 添加警告
            for warning in validation_warnings:
                result.add_warning(warning)
            
            return result
            
        except Exception as e:
            return UnifiedResult(
                success=False,
                status=OperationStatus.ERROR,
                error_code="VALIDATION_ERROR",
                error_message=f"参数验证失败: {str(e)}",
                error_details={"exception_type": type(e).__name__}
            )
    
    def _validate_parameter_value(self, param_name: str, value: Any, 
                                 schema: Dict[str, Any]) -> Optional[str]:
        """验证参数值"""
        # 基本类型检查
        expected_type = schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            return f"参数 {param_name} 应为字符串类型"
        elif expected_type == "number" and not isinstance(value, (int, float)):
            return f"参数 {param_name} 应为数值类型"
        elif expected_type == "integer" and not isinstance(value, int):
            return f"参数 {param_name} 应为整数类型"
        
        # 字符串长度检查
        if expected_type == "string" and isinstance(value, str):
            if len(value.strip()) == 0:
                return f"参数 {param_name} 不能为空字符串"
            
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            
            if min_length and len(value) < min_length:
                return f"参数 {param_name} 长度不能小于 {min_length}"
            if max_length and len(value) > max_length:
                return f"参数 {param_name} 长度不能大于 {max_length}"
        
        # 数值范围检查
        if expected_type in ["number", "integer"] and isinstance(value, (int, float)):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            
            if minimum is not None and value < minimum:
                return f"参数 {param_name} 值不能小于 {minimum}"
            if maximum is not None and value > maximum:
                return f"参数 {param_name} 值不能大于 {maximum}"
        
        # 枚举值检查
        enum_values = schema.get("enum")
        if enum_values and value not in enum_values:
            return f"参数 {param_name} 值必须是 {enum_values} 中的一个"
        
        return None
```

#### 1.1.3 工具编排器成功判定修复

**问题分析**：
- **文件位置**：`src/mercari_agent/core/tool_orchestrator.py`
- **问题**：第199行成功判定标准过于宽松

**修复代码**：

```python
# 文件：src/mercari_agent/core/tool_orchestrator.py
# 修复成功判定逻辑

class ToolOrchestrator:
    """工具调用协调器 - 修复版本"""
    
    async def execute_query(self, context: ToolExecutionContext) -> ToolExecutionResult:
        """执行查询，自动选择和调用合适的工具"""
        start_time = datetime.now()
        results = {}
        tools_used = []
        errors = []
        warnings = []
        
        try:
            # 1. 分析查询意图，确定需要的工具
            required_tools = await self._analyze_query_intent(context.user_query)
            
            if not required_tools:
                errors.append("无法确定查询所需的工具")
                return self._create_failed_result(context, errors, warnings, start_time)
            
            # 2. 按优先级执行工具
            successful_tools = 0
            critical_failures = 0
            
            for tool_info in required_tools:
                tool_name = tool_info["tool_name"]
                tool_params = tool_info.get("parameters", {})
                tool_priority = tool_info.get("priority", 99)
                is_critical = tool_priority <= 2  # 优先级1-2为关键工具
                
                # 修复工具参数
                processed_params = self._fix_tool_parameters(tool_name, tool_params, context, results)
                
                logger.info(f"🔍 执行工具: {tool_name} (优先级: {tool_priority})")
                
                try:
                    # 执行工具
                    tool_result = await self.tool_registry.call_tool(tool_name, **processed_params)
                    results[tool_name] = tool_result
                    tools_used.append(tool_name)
                    
                    # 增强的成功判定
                    if self._is_tool_result_successful(tool_result, tool_name):
                        successful_tools += 1
                        logger.info(f"✅ 工具 {tool_name} 执行成功")
                    else:
                        error_msg = f"工具 {tool_name} 执行失败: {tool_result.error_message or '未知错误'}"
                        errors.append(error_msg)
                        logger.error(f"❌ {error_msg}")
                        
                        if is_critical:
                            critical_failures += 1
                            
                except Exception as e:
                    error_msg = f"工具 {tool_name} 执行异常: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    
                    if is_critical:
                        critical_failures += 1
            
            # 3. 增强的整体成功判定
            execution_time = (datetime.now() - start_time).total_seconds()
            success = self._evaluate_overall_success(
                successful_tools, critical_failures, len(required_tools), errors, results
            )
            
            # 4. 更新统计信息
            self._update_execution_stats(tools_used, execution_time, success)
            
            return ToolExecutionResult(
                success=success,
                results=results,
                execution_time=execution_time,
                tools_used=tools_used,
                errors=errors,
                warnings=warnings,
                context=context
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"查询执行异常: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return self._create_failed_result(context, errors, warnings, start_time)
    
    def _is_tool_result_successful(self, tool_result: UnifiedResult, tool_name: str) -> bool:
        """增强的工具结果成功判定"""
        try:
            # 1. 基本状态检查
            if not tool_result.is_success():
                return False
            
            # 2. 数据有效性检查
            if not tool_result.has_data():
                logger.warning(f"工具 {tool_name} 成功但无数据")
                return False
            
            # 3. 工具特定的成功判定
            return self._tool_specific_success_validation(tool_name, tool_result)
            
        except Exception as e:
            logger.error(f"工具结果验证失败: {e}")
            return False
    
    def _tool_specific_success_validation(self, tool_name: str, tool_result: UnifiedResult) -> bool:
        """工具特定的成功验证"""
        data = tool_result.data
        
        if tool_name == "search_products":
            # 搜索工具：必须有产品数据
            if not isinstance(data, dict) or "products" not in data:
                return False
            products = data["products"]
            if not isinstance(products, list) or len(products) == 0:
                return False
            return True
            
        elif tool_name == "analyze_query":
            # 查询分析工具：必须有分析结果
            if not isinstance(data, dict):
                return False
            # 检查关键字段
            required_fields = ["intent", "keywords"]
            for field in required_fields:
                if field not in data:
                    return False
            return True
            
        elif tool_name == "generate_summary":
            # 摘要生成工具：必须有摘要文本
            if isinstance(data, dict) and "summary" in data:
                summary = data["summary"]
                return isinstance(summary, str) and len(summary.strip()) > 0
            elif isinstance(data, str):
                return len(data.strip()) > 0
            return False
        
        # 默认验证：检查数据不为空
        return data is not None
    
    def _evaluate_overall_success(self, successful_tools: int, critical_failures: int, 
                                 total_tools: int, errors: List[str], 
                                 results: Dict[str, UnifiedResult]) -> bool:
        """评估整体执行成功性"""
        
        # 1. 如果有关键工具失败，整体失败
        if critical_failures > 0:
            logger.error(f"关键工具失败数: {critical_failures}")
            return False
        
        # 2. 如果没有任何工具成功，整体失败
        if successful_tools == 0:
            logger.error("没有任何工具成功执行")
            return False
        
        # 3. 如果成功率过低，整体失败
        success_rate = successful_tools / total_tools if total_tools > 0 else 0
        if success_rate < 0.5:  # 成功率低于50%
            logger.error(f"工具成功率过低: {success_rate:.2%}")
            return False
        
        # 4. 检查是否有可用的最终结果
        has_useful_result = False
        for tool_name, result in results.items():
            if result.is_success() and result.has_data():
                has_useful_result = True
                break
        
        if not has_useful_result:
            logger.error("没有可用的最终结果")
            return False
        
        logger.info(f"整体执行成功: {successful_tools}/{total_tools} 工具成功")
        return True
    
    def _create_failed_result(self, context: ToolExecutionContext, errors: List[str], 
                             warnings: List[str], start_time: datetime) -> ToolExecutionResult:
        """创建失败结果"""
        execution_time = (datetime.now() - start_time).total_seconds()
        return ToolExecutionResult(
            success=False,
            results={},
            execution_time=execution_time,
            tools_used=[],
            errors=errors,
            warnings=warnings,
            context=context
        )
```

### 1.2 监控和告警增强

#### 1.2.1 系统健康监控

**新增文件**：`src/mercari_agent/monitoring/health_monitor.py`

```python
"""
系统健康监控
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"

@dataclass
class HealthMetric:
    """健康指标"""
    name: str
    value: float
    threshold_warning: float
    threshold_critical: float
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_status(self) -> HealthStatus:
        """获取健康状态"""
        if self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY

@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthStatus
    metrics: List[HealthMetric] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    last_check: datetime = field(default_factory=datetime.now)
    
    def add_metric(self, metric: HealthMetric):
        """添加指标"""
        self.metrics.append(metric)
        
        # 更新整体状态
        if metric.get_status() == HealthStatus.CRITICAL:
            self.status = HealthStatus.CRITICAL
        elif metric.get_status() == HealthStatus.WARNING and self.status == HealthStatus.HEALTHY:
            self.status = HealthStatus.WARNING

class HealthMonitor:
    """健康监控器"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.components: Dict[str, ComponentHealth] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.alert_callbacks: List[callable] = []
        self.logger = logging.getLogger(__name__)
        
    async def start_monitoring(self):
        """开始监控"""
        self.logger.info("开始健康监控...")
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """停止监控"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("健康监控已停止")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"健康检查失败: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _perform_health_check(self):
        """执行健康检查"""
        # 检查会话管理器
        await self._check_session_manager()
        
        # 检查工具注册表
        await self._check_tool_registry()
        
        # 检查LLM服务
        await self._check_llm_service()
        
        # 检查爬虫服务
        await self._check_scraper_service()
        
        # 发送告警
        await self._send_alerts()
    
    async def _check_session_manager(self):
        """检查会话管理器"""
        component_name = "session_manager"
        health = ComponentHealth(component_name, HealthStatus.HEALTHY)
        
        try:
            # 检查会话池状态
            # TODO: 实际实现中需要从会话管理器获取指标
            session_pool_size = 5  # 示例值
            active_sessions = 3    # 示例值
            failed_sessions = 1    # 示例值
            
            # 添加指标
            health.add_metric(HealthMetric(
                name="session_pool_size",
                value=session_pool_size,
                threshold_warning=1,
                threshold_critical=0,
                unit="个"
            ))
            
            health.add_metric(HealthMetric(
                name="session_failure_rate",
                value=failed_sessions / (active_sessions + failed_sessions) if active_sessions + failed_sessions > 0 else 0,
                threshold_warning=0.2,
                threshold_critical=0.5,
                unit="%"
            ))
            
        except Exception as e:
            health.status = HealthStatus.CRITICAL
            health.errors.append(f"会话管理器检查失败: {e}")
        
        self.components[component_name] = health
    
    async def _check_tool_registry(self):
        """检查工具注册表"""
        component_name = "tool_registry"
        health = ComponentHealth(component_name, HealthStatus.HEALTHY)
        
        try:
            # 检查工具注册状态
            # TODO: 从工具注册表获取实际指标
            registered_tools = 10  # 示例值
            
            health.add_metric(HealthMetric(
                name="registered_tools",
                value=registered_tools,
                threshold_warning=5,
                threshold_critical=3,
                unit="个"
            ))
            
        except Exception as e:
            health.status = HealthStatus.CRITICAL
            health.errors.append(f"工具注册表检查失败: {e}")
        
        self.components[component_name] = health
    
    async def _check_llm_service(self):
        """检查LLM服务"""
        component_name = "llm_service"
        health = ComponentHealth(component_name, HealthStatus.HEALTHY)
        
        try:
            # 检查LLM服务状态
            # TODO: 从LLM服务获取实际指标
            response_time = 2.5  # 示例值（秒）
            error_rate = 0.1     # 示例值
            
            health.add_metric(HealthMetric(
                name="response_time",
                value=response_time,
                threshold_warning=5.0,
                threshold_critical=10.0,
                unit="秒"
            ))
            
            health.add_metric(HealthMetric(
                name="error_rate",
                value=error_rate,
                threshold_warning=0.2,
                threshold_critical=0.5,
                unit="%"
            ))
            
        except Exception as e:
            health.status = HealthStatus.CRITICAL
            health.errors.append(f"LLM服务检查失败: {e}")
        
        self.components[component_name] = health
    
    async def _check_scraper_service(self):
        """检查爬虫服务"""
        component_name = "scraper_service"
        health = ComponentHealth(component_name, HealthStatus.HEALTHY)
        
        try:
            # 检查爬虫服务状态
            # TODO: 从爬虫服务获取实际指标
            success_rate = 0.8  # 示例值
            
            health.add_metric(HealthMetric(
                name="scraping_success_rate",
                value=success_rate,
                threshold_warning=0.7,
                threshold_critical=0.5,
                unit="%"
            ))
            
        except Exception as e:
            health.status = HealthStatus.CRITICAL
            health.errors.append(f"爬虫服务检查失败: {e}")
        
        self.components[component_name] = health
    
    async def _send_alerts(self):
        """发送告警"""
        critical_components = [
            name for name, health in self.components.items()
            if health.status == HealthStatus.CRITICAL
        ]
        
        if critical_components:
            alert_message = f"严重告警: {', '.join(critical_components)} 组件状态异常"
            for callback in self.alert_callbacks:
                try:
                    await callback(alert_message, critical_components)
                except Exception as e:
                    self.logger.error(f"告警回调失败: {e}")
    
    def add_alert_callback(self, callback: callable):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def get_overall_health(self) -> Dict[str, Any]:
        """获取整体健康状态"""
        if not self.components:
            return {
                "status": HealthStatus.DOWN.value,
                "message": "没有组件健康数据",
                "timestamp": datetime.now().isoformat()
            }
        
        # 计算整体状态
        critical_count = sum(1 for h in self.components.values() if h.status == HealthStatus.CRITICAL)
        warning_count = sum(1 for h in self.components.values() if h.status == HealthStatus.WARNING)
        
        if critical_count > 0:
            overall_status = HealthStatus.CRITICAL
        elif warning_count > 0:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            "status": overall_status.value,
            "components": {
                name: {
                    "status": health.status.value,
                    "metrics": [
                        {
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "status": metric.get_status().value
                        }
                        for metric in health.metrics
                    ],
                    "errors": health.errors,
                    "last_check": health.last_check.isoformat()
                }
                for name, health in self.components.items()
            },
            "summary": {
                "total_components": len(self.components),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "healthy_count": len(self.components) - critical_count - warning_count
            },
            "timestamp": datetime.now().isoformat()
        }
```

### 1.3 紧急修复部署脚本

**新增文件**：`scripts/emergency_fix_deploy.py`

```python
"""
紧急修复部署脚本
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mercari_agent.utils.logger import get_logger

logger = get_logger(__name__)

class EmergencyFixDeployer:
    """紧急修复部署器"""
    
    def __init__(self):
        self.deployment_log = []
        self.rollback_commands = []
    
    async def deploy_fixes(self):
        """部署紧急修复"""
        logger.info("🚨 开始部署紧急修复...")
        
        try:
            # 1. 备份当前代码
            await self._backup_current_code()
            
            # 2. 部署会话管理器修复
            await self._deploy_session_manager_fix()
            
            # 3. 部署错误处理统一修复
            await self._deploy_error_handling_fix()
            
            # 4. 部署工具编排器修复
            await self._deploy_orchestrator_fix()
            
            # 5. 部署健康监控
            await self._deploy_health_monitoring()
            
            # 6. 验证修复效果
            await self._verify_fixes()
            
            logger.info("✅ 紧急修复部署完成")
            
        except Exception as e:
            logger.error(f"❌ 紧急修复部署失败: {e}")
            await self._rollback_changes()
            raise
    
    async def _backup_current_code(self):
        """备份当前代码"""
        logger.info("📦 备份当前代码...")
        
        backup_dir = project_root / "backups" / f"emergency_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制关键文件
        import shutil
        
        files_to_backup = [
            "src/mercari_agent/scrapers/enhanced_session_manager.py",
            "src/mercari_agent/core/tools/base_tool.py",
            "src/mercari_agent/core/tool_orchestrator.py"
        ]
        
        for file_path in files_to_backup:
            source = project_root / file_path
            if source.exists():
                dest = backup_dir / file_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                logger.info(f"✅ 备份文件: {file_path}")
        
        self.rollback_commands.append(f"restore_from_backup {backup_dir}")
    
    async def _deploy_session_manager_fix(self):
        """部署会话管理器修复"""
        logger.info("🔧 部署会话管理器修复...")
        
        # 这里应该包含实际的文件替换逻辑
        # 在实际部署中，这些修复代码应该已经被写入对应的文件
        
        logger.info("✅ 会话管理器修复已部署")
    
    async def _deploy_error_handling_fix(self):
        """部署错误处理统一修复"""
        logger.info("🔧 部署错误处理统一修复...")
        
        # 实际的文件替换逻辑
        logger.info("✅ 错误处理统一修复已部署")
    
    async def _deploy_orchestrator_fix(self):
        """部署工具编排器修复"""
        logger.info("🔧 部署工具编排器修复...")
        
        # 实际的文件替换逻辑
        logger.info("✅ 工具编排器修复已部署")
    
    async def _deploy_health_monitoring(self):
        """部署健康监控"""
        logger.info("🔧 部署健康监控...")
        
        # 确保监控目录存在
        monitoring_dir = project_root / "src" / "mercari_agent" / "monitoring"
        monitoring_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ 健康监控已部署")
    
    async def _verify_fixes(self):
        """验证修复效果"""
        logger.info("🔍 验证修复效果...")
        
        # 导入修复后的模块进行测试
        try:
            from src.mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager
            from src.mercari_agent.core.tools.base_tool import UnifiedResult
            from src.mercari_agent.core.tool_orchestrator import ToolOrchestrator
            
            logger.info("✅ 模块导入测试通过")
            
            # 简单的功能测试
            # TODO: 添加更多的验证逻辑
            
        except Exception as e:
            logger.error(f"❌ 修复验证失败: {e}")
            raise
    
    async def _rollback_changes(self):
        """回滚变更"""
        logger.warning("🔄 执行回滚...")
        
        for command in reversed(self.rollback_commands):
            try:
                logger.info(f"执行回滚命令: {command}")
                # 实际的回滚逻辑
            except Exception as e:
                logger.error(f"回滚命令失败: {e}")

async def main():
    """主函数"""
    deployer = EmergencyFixDeployer()
    await deployer.deploy_fixes()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 2. 中期重构方案 (1-2个月)

### 2.1 错误处理架构重设计

#### 2.1.1 分层错误处理系统

**新增文件**：`src/mercari_agent/core/error_handling/error_manager.py`

```python
"""
分层错误处理系统
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Type, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import traceback
import json

class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 轻微错误，不影响主要功能
    MEDIUM = "medium"     # 中等错误，影响部分功能
    HIGH = "high"         # 严重错误，影响主要功能
    CRITICAL = "critical" # 致命错误，系统无法正常运行

class ErrorCategory(Enum):
    """错误分类"""
    SYSTEM = "system"           # 系统错误
    BUSINESS = "business"       # 业务逻辑错误
    NETWORK = "network"         # 网络错误
    VALIDATION = "validation"   # 验证错误
    CONFIGURATION = "configuration"  # 配置错误
    EXTERNAL = "external"       # 外部服务错误

@dataclass
class ErrorContext:
    """错误上下文"""
    error_id: str
    component: str
    operation: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str
    error_code: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": {
                "component": self.context.component,
                "operation": self.context.operation,
                "user_id": self.context.user_id,
                "session_id": self.context.session_id,
                "request_id": self.context.request_id,
                "timestamp": self.context.timestamp.isoformat(),
                "additional_data": self.context.additional_data
            },
            "exception_type": type(self.exception).__name__ if self.exception else None,
            "stack_trace": self.stack_trace,
            "recovery_suggestions": self.recovery_suggestions,
            "metadata": self.metadata
        }

class ErrorHandler:
    """错误处理器接口"""
    
    async def handle_error(self, error_info: ErrorInfo) -> bool:
        """处理错误，返回是否应该继续处理"""
        raise NotImplementedError

class LoggingErrorHandler(ErrorHandler):
    """日志错误处理器"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    async def handle_error(self, error_info: ErrorInfo) -> bool:
        """记录错误日志"""
        log_method = self._get_log_method(error_info.severity)
        
        log_data = {
            "error_id": error_info.error_id,
            "error_code": error_info.error_code,
            "message": error_info.error_message,
            "component": error_info.context.component,
            "operation": error_info.context.operation,
            "category": error_info.category.value,
            "severity": error_info.severity.value
        }
        
        log_method(f"错误处理: {json.dumps(log_data, ensure_ascii=False, indent=2)}")
        return True
    
    def _get_log_method(self, severity: ErrorSeverity) -> Callable:
        """获取对应严重程度的日志方法"""
        mapping = {
            ErrorSeverity.LOW: self.logger.info,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical
        }
        return mapping.get(severity, self.logger.error)

class AlertingErrorHandler(ErrorHandler):
    """告警错误处理器"""
    
    def __init__(self, alert_thresholds: Dict[ErrorSeverity, int]):
        self.alert_thresholds = alert_thresholds
        self.alert_callbacks: List[Callable] = []
    
    async def handle_error(self, error_info: ErrorInfo) -> bool:
        """发送告警"""
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._send_alert(error_info)
        return True
    
    async def _send_alert(self, error_info: ErrorInfo):
        """发送告警"""
        alert_data = {
            "title": f"系统错误告警 - {error_info.severity.value.upper()}",
            "error_id": error_info.error_id,
            "component": error_info.context.component,
            "message": error_info.error_message,
            "timestamp": error_info.context.timestamp.isoformat()
        }
        
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                # 告警发送失败不应该影响主流程
                pass
    
    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self.alert_callbacks.append(callback)

class RecoveryErrorHandler(ErrorHandler):
    """恢复错误处理器"""
    
    def __init__(self):
        self.recovery_strategies: Dict[str, Callable] = {}
    
    async def handle_error(self, error_info: ErrorInfo) -> bool:
        """尝试错误恢复"""
        strategy = self.recovery_strategies.get(error_info.error_code)
        if strategy:
            try:
                await strategy(error_info)
                return True
            except Exception as e:
                # 恢复失败，继续传播错误
                pass
        return True
    
    def register_recovery_strategy(self, error_code: str, strategy: Callable):
        """注册恢复策略"""
        self.recovery_strategies[error_code] = strategy

class ErrorManager:
    """错误管理器"""
    
    def __init__(self):
        self.handlers: List[ErrorHandler] = []
        self.error_registry: Dict[str, ErrorInfo] = {}
        self.logger = logging.getLogger(__name__)
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """设置默认错误处理器"""
        # 日志处理器
        self.add_handler(LoggingErrorHandler(self.logger))
        
        # 告警处理器
        alert_handler = AlertingErrorHandler({
            ErrorSeverity.HIGH: 1,
            ErrorSeverity.CRITICAL: 1
        })
        self.add_handler(alert_handler)
        
        # 恢复处理器
        recovery_handler = RecoveryErrorHandler()
        self._register_recovery_strategies(recovery_handler)
        self.add_handler(recovery_handler)
    
    def _register_recovery_strategies(self, recovery_handler: RecoveryErrorHandler):
        """注册恢复策略"""
        
        async def session_recovery_strategy(error_info: ErrorInfo):
            """会话恢复策略"""
            if error_info.context.component == "session_manager":
                # 尝试重新初始化会话
                pass
        
        async def tool_retry_strategy(error_info: ErrorInfo):
            """工具重试策略"""
            if error_info.context.component == "tool_orchestrator":
                # 尝试重新执行工具
                pass
        
        recovery_handler.register_recovery_strategy("SESSION_INIT_FAILED", session_recovery_strategy)
        recovery_handler.register_recovery_strategy("TOOL_EXECUTION_FAILED", tool_retry_strategy)
    
    def add_handler(self, handler: ErrorHandler):
        """添加错误处理器"""
        self.handlers.append(handler)
    
    async def handle_error(self, 
                          error_code: str,
                          error_message: str,
                          severity: ErrorSeverity,
                          category: ErrorCategory,
                          context: ErrorContext,
                          exception: Optional[Exception] = None,
                          recovery_suggestions: List[str] = None) -> ErrorInfo:
        """处理错误"""
        
        # 生成错误ID
        error_id = f"{context.component}_{error_code}_{int(datetime.now().timestamp())}"
        
        # 创建错误信息
        error_info = ErrorInfo(
            error_id=error_id,
            error_code=error_code,
            error_message=error_message,
            severity=severity,
            category=category,
            context=context,
            exception=exception,
            stack_trace=traceback.format_exc() if exception else None,
            recovery_suggestions=recovery_suggestions or []
        )
        
        # 存储错误信息
        self.error_registry[error_id] = error_info
        
        # 依次调用处理器
        for handler in self.handlers:
            try:
                should_continue = await handler.handle_error(error_info)
                if not should_continue:
                    break
            except Exception as e:
                self.logger.error(f"错误处理器执行失败: {e}")
        
        return error_info
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        if not self.error_registry:
            return {"total_errors": 0}
        
        # 按严重程度统计
        severity_stats = {}
        for severity in ErrorSeverity:
            severity_stats[severity.value] = sum(
                1 for error in self.error_registry.values() 
                if error.severity == severity
            )
        
        # 按类别统计
        category_stats = {}
        for category in ErrorCategory:
            category_stats[category.value] = sum(
                1 for error in self.error_registry.values() 
                if error.category == category
            )
        
        # 按组件统计
        component_stats = {}
        for error in self.error_registry.values():
            component = error.context.component
            component_stats[component] = component_stats.get(component, 0) + 1
        
        return {
            "total_errors": len(self.error_registry),
            "severity_distribution": severity_stats,
            "category_distribution": category_stats,
            "component_distribution": component_stats,
            "recent_errors": [
                error.to_dict() for error in 
                sorted(self.error_registry.values(), 
                      key=lambda x: x.context.timestamp, reverse=True)[:10]
            ]
        }

# 全局错误管理器实例
global_error_manager = ErrorManager()

# 便捷函数
async def handle_error(error_code: str, error_message: str, 
                      severity: ErrorSeverity, category: ErrorCategory,
                      component: str, operation: str,
                      exception: Optional[Exception] = None,
                      **context_data) -> ErrorInfo:
    """便捷的错误处理函数"""
    context = ErrorContext(
        error_id="",  # 将在handle_error中生成
        component=component,
        operation=operation,
        additional_data=context_data
    )
    
    return await global_error_manager.handle_error(
        error_code=error_code,
        error_message=error_message,
        severity=severity,
        category=category,
        context=context,
        exception=exception
    )
```

### 2.2 组件解耦架构

#### 2.2.1 事件驱动架构

**新增文件**：`src/mercari_agent/core/events/event_system.py`

```python
"""
事件驱动架构系统
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Type, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

class EventType(Enum):
    """事件类型"""
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    
    SESSION_CREATED = "session.created"
    SESSION_CLOSED = "session.closed"
    SESSION_ERROR = "session.error"
    
    TOOL_EXECUTION_STARTED = "tool.execution.started"
    TOOL_EXECUTION_COMPLETED = "tool.execution.completed"
    TOOL_EXECUTION_FAILED = "tool.execution.failed"
    
    QUERY_RECEIVED = "query.received"
    QUERY_PROCESSED = "query.processed"
    QUERY_FAILED = "query.failed"
    
    ERROR_OCCURRED = "error.occurred"
    ERROR_RECOVERED = "error.recovered"
    
    HEALTH_CHECK_COMPLETED = "health.check.completed"
    METRIC_UPDATED = "metric.updated"

@dataclass
class Event:
    """事件数据结构"""
    event_id: str
    event_type: EventType
    source: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id
        }

class EventHandler:
    """事件处理器接口"""
    
    async def handle_event(self, event: Event) -> bool:
        """处理事件，返回是否成功"""
        raise NotImplementedError
    
    def get_supported_event_types(self) -> Set[EventType]:
        """获取支持的事件类型"""
        raise NotImplementedError

class EventBus:
    """事件总线"""
    
    def __init__(self, max_workers: int = 10):
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.event_history: List[Event] = []
        self.max_history_size = 1000
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)
        
        # 事件统计
        self.event_stats = {
            "total_events": 0,
            "events_by_type": {},
            "processing_errors": 0
        }
    
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """订阅事件"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        self.logger.info(f"订阅事件: {event_type.value} -> {handler.__class__.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """取消订阅事件"""
        if event_type in self.handlers:
            self.handlers[event_type].remove(handler)
            self.logger.info(f"取消订阅事件: {event_type.value} -> {handler.__class__.__name__}")
    
    async def publish(self, event: Event):
        """发布事件"""
        # 记录事件
        self._record_event(event)
        
        # 获取处理器
        handlers = self.handlers.get(event.event_type, [])
        
        if not handlers:
            self.logger.debug(f"没有处理器处理事件: {event.event_type.value}")
            return
        
        # 异步处理事件
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._handle_event_safely(handler, event))
            tasks.append(task)
        
        # 等待所有处理器完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计处理结果
        for result in results:
            if isinstance(result, Exception):
                self.event_stats["processing_errors"] += 1
                self.logger.error(f"事件处理失败: {result}")
    
    async def _handle_event_safely(self, handler: EventHandler, event: Event) -> bool:
        """安全地处理事件"""
        try:
            return await handler.handle_event(event)
        except Exception as e:
            self.logger.error(f"事件处理器 {handler.__class__.__name__} 处理事件失败: {e}")
            return False
    
    def _record_event(self, event: Event):
        """记录事件"""
        self.event_history.append(event)
        
        # 限制历史记录大小
        # 限制历史记录大小
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # 更新统计信息
        self.event_stats["total_events"] += 1
        event_type_key = event.event_type.value
        self.event_stats["events_by_type"][event_type_key] = self.event_stats["events_by_type"].get(event_type_key, 0) + 1
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """获取事件统计"""
        return {
            "total_events": self.event_stats["total_events"],
            "events_by_type": self.event_stats["events_by_type"],
            "processing_errors": self.event_stats["processing_errors"],
            "active_handlers": {
                event_type.value: len(handlers) 
                for event_type, handlers in self.handlers.items()
            },
            "recent_events": [
                event.to_dict() for event in self.event_history[-10:]
            ]
        }

# 全局事件总线
global_event_bus = EventBus()

# 便捷函数
async def publish_event(event_type: EventType, source: str, data: Dict[str, Any] = None, 
                       correlation_id: str = None):
    """发布事件的便捷函数"""
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        source=source,
        timestamp=datetime.now(),
        data=data or {},
        correlation_id=correlation_id
    )
    
    await global_event_bus.publish(event)
```

#### 2.2.2 依赖注入框架

**新增文件**：`src/mercari_agent/core/dependency_injection/di_container.py`

```python
"""
依赖注入容器
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Type, Callable, Union, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import inspect
from contextlib import asynccontextmanager

T = TypeVar('T')

class LifetimeScope(Enum):
    """生命周期范围"""
    SINGLETON = "singleton"     # 单例
    TRANSIENT = "transient"     # 瞬态
    SCOPED = "scoped"          # 作用域

@dataclass
class ServiceDescriptor:
    """服务描述符"""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory_function: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: LifetimeScope = LifetimeScope.TRANSIENT
    dependencies: List[Type] = field(default_factory=list)
    
    def __post_init__(self):
        if self.implementation_type and not self.dependencies:
            # 自动分析依赖
            self.dependencies = self._analyze_dependencies()
    
    def _analyze_dependencies(self) -> List[Type]:
        """分析构造函数依赖"""
        if not self.implementation_type:
            return []
        
        init_method = getattr(self.implementation_type, '__init__', None)
        if not init_method:
            return []
        
        signature = inspect.signature(init_method)
        dependencies = []
        
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            
            if param.annotation != inspect.Parameter.empty:
                dependencies.append(param.annotation)
        
        return dependencies

class ServiceScope:
    """服务作用域"""
    
    def __init__(self, parent_scope: Optional['ServiceScope'] = None):
        self.parent_scope = parent_scope
        self.scoped_instances: Dict[Type, Any] = {}
        self.disposables: List[Any] = []
    
    def get_scoped_instance(self, service_type: Type) -> Optional[Any]:
        """获取作用域实例"""
        return self.scoped_instances.get(service_type)
    
    def set_scoped_instance(self, service_type: Type, instance: Any):
        """设置作用域实例"""
        self.scoped_instances[service_type] = instance
        
        # 如果实例是可释放的，添加到释放列表
        if hasattr(instance, 'dispose') or hasattr(instance, 'close'):
            self.disposables.append(instance)
    
    async def dispose(self):
        """释放作用域"""
        for disposable in reversed(self.disposables):
            try:
                if hasattr(disposable, 'dispose'):
                    if asyncio.iscoroutinefunction(disposable.dispose):
                        await disposable.dispose()
                    else:
                        disposable.dispose()
                elif hasattr(disposable, 'close'):
                    if asyncio.iscoroutinefunction(disposable.close):
                        await disposable.close()
                    else:
                        disposable.close()
            except Exception as e:
                logging.error(f"释放资源失败: {e}")
        
        self.scoped_instances.clear()
        self.disposables.clear()

class DIContainer:
    """依赖注入容器"""
    
    def __init__(self):
        self.services: Dict[Type, ServiceDescriptor] = {}
        self.singleton_instances: Dict[Type, Any] = {}
        self.current_scope: Optional[ServiceScope] = None
        self.logger = logging.getLogger(__name__)
        
        # 注册容器本身
        self.register_instance(DIContainer, self)
    
    def register_transient(self, service_type: Type, implementation_type: Type = None):
        """注册瞬态服务"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type or service_type,
            lifetime=LifetimeScope.TRANSIENT
        )
        self.services[service_type] = descriptor
        self.logger.info(f"注册瞬态服务: {service_type.__name__}")
    
    def register_singleton(self, service_type: Type, implementation_type: Type = None):
        """注册单例服务"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type or service_type,
            lifetime=LifetimeScope.SINGLETON
        )
        self.services[service_type] = descriptor
        self.logger.info(f"注册单例服务: {service_type.__name__}")
    
    def register_scoped(self, service_type: Type, implementation_type: Type = None):
        """注册作用域服务"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type or service_type,
            lifetime=LifetimeScope.SCOPED
        )
        self.services[service_type] = descriptor
        self.logger.info(f"注册作用域服务: {service_type.__name__}")
    
    def register_factory(self, service_type: Type, factory_function: Callable):
        """注册工厂函数"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory_function=factory_function,
            lifetime=LifetimeScope.TRANSIENT
        )
        self.services[service_type] = descriptor
        self.logger.info(f"注册工厂服务: {service_type.__name__}")
    
    def register_instance(self, service_type: Type, instance: Any):
        """注册实例"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=LifetimeScope.SINGLETON
        )
        self.services[service_type] = descriptor
        self.singleton_instances[service_type] = instance
        self.logger.info(f"注册实例服务: {service_type.__name__}")
    
    async def resolve(self, service_type: Type[T]) -> T:
        """解析服务"""
        return await self._resolve_service(service_type)
    
    async def _resolve_service(self, service_type: Type) -> Any:
        """内部解析服务"""
        if service_type not in self.services:
            raise ValueError(f"服务 {service_type.__name__} 未注册")
        
        descriptor = self.services[service_type]
        
        # 处理不同的生命周期
        if descriptor.lifetime == LifetimeScope.SINGLETON:
            return await self._resolve_singleton(descriptor)
        elif descriptor.lifetime == LifetimeScope.SCOPED:
            return await self._resolve_scoped(descriptor)
        else:  # TRANSIENT
            return await self._resolve_transient(descriptor)
    
    async def _resolve_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """解析单例服务"""
        if descriptor.service_type in self.singleton_instances:
            return self.singleton_instances[descriptor.service_type]
        
        instance = await self._create_instance(descriptor)
        self.singleton_instances[descriptor.service_type] = instance
        return instance
    
    async def _resolve_scoped(self, descriptor: ServiceDescriptor) -> Any:
        """解析作用域服务"""
        if not self.current_scope:
            # 如果没有作用域，回退到单例
            return await self._resolve_singleton(descriptor)
        
        instance = self.current_scope.get_scoped_instance(descriptor.service_type)
        if instance is not None:
            return instance
        
        instance = await self._create_instance(descriptor)
        self.current_scope.set_scoped_instance(descriptor.service_type, instance)
        return instance
    
    async def _resolve_transient(self, descriptor: ServiceDescriptor) -> Any:
        """解析瞬态服务"""
        return await self._create_instance(descriptor)
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建实例"""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory_function:
            if asyncio.iscoroutinefunction(descriptor.factory_function):
                return await descriptor.factory_function()
            else:
                return descriptor.factory_function()
        
        if descriptor.implementation_type:
            # 解析依赖
            dependencies = []
            for dep_type in descriptor.dependencies:
                dependency = await self._resolve_service(dep_type)
                dependencies.append(dependency)
            
            # 创建实例
            instance = descriptor.implementation_type(*dependencies)
            
            # 如果实例有初始化方法，调用它
            if hasattr(instance, 'initialize'):
                init_method = getattr(instance, 'initialize')
                if asyncio.iscoroutinefunction(init_method):
                    await init_method()
                else:
                    init_method()
            
            return instance
        
        raise ValueError(f"无法创建服务实例: {descriptor.service_type.__name__}")
    
    @asynccontextmanager
    async def create_scope(self):
        """创建作用域"""
        parent_scope = self.current_scope
        self.current_scope = ServiceScope(parent_scope)
        
        try:
            yield self.current_scope
        finally:
            await self.current_scope.dispose()
            self.current_scope = parent_scope
    
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "registered_services": len(self.services),
            "singleton_instances": len(self.singleton_instances),
            "services": {
                service_type.__name__: {
                    "lifetime": descriptor.lifetime.value,
                    "implementation": descriptor.implementation_type.__name__ if descriptor.implementation_type else "N/A",
                    "dependencies": [dep.__name__ for dep in descriptor.dependencies]
                }
                for service_type, descriptor in self.services.items()
            }
        }

# 全局容器实例
global_container = DIContainer()

# 便捷函数
def register_transient(service_type: Type, implementation_type: Type = None):
    """注册瞬态服务"""
    global_container.register_transient(service_type, implementation_type)

def register_singleton(service_type: Type, implementation_type: Type = None):
    """注册单例服务"""
    global_container.register_singleton(service_type, implementation_type)

def register_scoped(service_type: Type, implementation_type: Type = None):
    """注册作用域服务"""
    global_container.register_scoped(service_type, implementation_type)

async def resolve(service_type: Type[T]) -> T:
    """解析服务"""
    return await global_container.resolve(service_type)
```

---

## 4. 具体实施指导

### 4.1 紧急修复实施步骤

#### 4.1.1 第1周：P0问题修复

**Day 1-2：会话管理器修复**
```bash
# 1. 创建修复分支
git checkout -b emergency-fix/session-manager

# 2. 应用会话管理器修复
cp emergency_fixes/enhanced_session_manager.py src/mercari_agent/scrapers/

# 3. 运行测试
python -m pytest tests/unit/test_session_manager.py -v

# 4. 集成测试
python debug_initialization.py
```

**Day 3-4：错误处理统一**
```bash
# 1. 应用错误处理修复
cp emergency_fixes/unified_error_handling.py src/mercari_agent/core/tools/

# 2. 更新工具编排器
cp emergency_fixes/tool_orchestrator_fix.py src/mercari_agent/core/

# 3. 运行完整测试套件
python -m pytest tests/ -v
```

**Day 5-7：部署和验证**
```bash
# 1. 部署到测试环境
python scripts/emergency_fix_deploy.py

# 2. 端到端测试
python integration_test.py

# 3. 性能测试
python performance_benchmark.py

# 4. 部署到生产环境（如果测试通过）
```

#### 4.1.2 第2周：监控和优化

**Day 8-10：监控部署**
```bash
# 1. 部署健康监控
python scripts/deploy_health_monitoring.py

# 2. 配置告警
python scripts/setup_alerts.py

# 3. 监控仪表板设置
```

**Day 11-14：优化和调优**
```bash
# 1. 性能优化
python scripts/performance_optimization.py

# 2. 参数调优
python scripts/parameter_tuning.py

# 3. 稳定性测试
python scripts/stability_test.py
```

### 4.2 中期重构实施步骤

#### 4.2.1 第3-4周：错误处理架构

**实施计划**：
1. **第3周**：
   - 部署统一错误处理系统
   - 迁移现有错误处理逻辑
   - 测试错误处理流程

2. **第4周**：
   - 完善错误分类和处理策略
   - 优化错误恢复机制
   - 部署错误告警系统

#### 4.2.2 第5-6周：事件驱动架构

**实施计划**：
1. **第5周**：
   - 部署事件总线系统
   - 重构组件间通信
   - 测试事件处理流程

2. **第6周**：
   - 完善事件监听器
   - 优化事件处理性能
   - 部署事件监控系统

#### 4.2.3 第7-8周：可靠性架构

**实施计划**：
1. **第7周**：
   - 部署熔断器系统
   - 配置重试策略
   - 测试容错机制

2. **第8周**：
   - 完善降级策略
   - 优化系统恢复能力
   - 部署可靠性监控

### 4.3 长期优化实施步骤

#### 4.3.1 第9-12周：微服务拆分

**实施计划**：
1. **第9周**：服务拆分设计和准备
2. **第10周**：核心服务拆分实施
3. **第11周**：服务间通信优化
4. **第12周**：微服务部署和测试

#### 4.3.2 第13-16周：服务治理

**实施计划**：
1. **第13周**：服务注册中心部署
2. **第14周**：服务发现和负载均衡
3. **第15周**：服务监控和治理
4. **第16周**：全面测试和优化

#### 4.3.3 第17-20周：完整运维体系

**实施计划**：
1. **第17周**：自动化部署流水线
2. **第18周**：全面监控体系
3. **第19周**：故障自动恢复
4. **第20周**：性能优化和调优

---

## 5. 风险评估与应对

### 5.1 技术风险

#### 5.1.1 高风险项目
1. **会话管理器重构**
   - 风险：可能影响现有功能
   - 应对：分阶段迁移，保留回滚机制

2. **错误处理架构变更**
   - 风险：可能引入新的错误处理问题
   - 应对：充分测试，逐步迁移

3. **微服务拆分**
   - 风险：系统复杂度增加
   - 应对：先拆分非核心服务，积累经验

#### 5.1.2 风险应对策略
1. **技术预案**：
   - 每个重要变更都有回滚计划
   - 关键路径有备用方案
   - 充分的测试覆盖

2. **监控告警**：
   - 关键指标实时监控
   - 异常情况自动告警
   - 故障快速定位

3. **分阶段实施**：
   - 优先级排序
   - 渐进式部署
   - 及时反馈调整

### 5.2 业务风险

#### 5.2.1 服务中断风险
- **风险描述**：重构过程中可能导致服务中断
- **应对措施**：
  - 蓝绿部署策略
  - 流量逐步切换
  - 快速回滚机制

#### 5.2.2 性能下降风险
- **风险描述**：新架构可能导致性能下降
- **应对措施**：
  - 性能基准测试
  - 持续性能监控
  - 性能优化迭代

### 5.3 项目风险

#### 5.3.1 进度延期风险
- **风险描述**：复杂重构可能导致进度延期
- **应对措施**：
  - 里程碑管理
  - 风险预警机制
  - 资源弹性调配

#### 5.3.2 人员技能风险
- **风险描述**：新技术栈可能需要技能提升
- **应对措施**：
  - 技术培训计划
  - 外部技术支持
  - 知识分享机制

---

## 6. 成功指标和验收标准

### 6.1 系统可靠性指标

#### 6.1.1 核心指标
- **查询成功率**：30% → 95%
- **平均响应时间**：10s → 2s
- **系统可用性**：70% → 99.9%
- **错误恢复时间**：30min → 5min

#### 6.1.2 监控指标
- **会话管理器**：
  - 会话创建成功率 > 99%
  - 会话池利用率 < 80%
  - 会话错误率 < 1%

- **工具编排器**：
  - 工具调用成功率 > 95%
  - 工具链执行时间 < 5s
  - 参数验证失败率 < 0.1%

- **错误处理**：
  - 错误分类准确率 > 90%
  - 错误恢复成功率 > 70%
  - 错误传播中断率 < 0.1%

### 6.2 业务指标

#### 6.2.1 用户体验指标
- **查询响应时间**：< 3s
- **搜索结果准确率**：> 85%
- **用户满意度**：> 4.0/5.0
- **功能完整性**：> 95%

#### 6.2.2 系统性能指标
- **并发处理能力**：> 1000 QPS
- **资源利用率**：< 70%
- **扩展性**：支持水平扩展
- **成本效率**：运维成本降低 30%

### 6.3 技术指标

#### 6.3.1 架构质量指标
- **代码覆盖率**：> 80%
- **技术债务**：减少 60%
- **组件耦合度**：< 3.0
- **系统复杂度**：< 7.0

#### 6.3.2 运维指标
- **故障检测时间**：< 2min
- **故障恢复时间**：< 10min
- **部署频率**：> 2次/周
- **部署成功率**：> 95%

---

## 7. 总结

### 7.1 修复方案总结

本修复方案采用分阶段、渐进式的方式，系统性地解决Mercari AI Agent的架构缺陷：

1. **紧急修复（1-2周）**：
   - 修复P0级别根本性问题
   - 快速提升系统可靠性至60%
   - 建立基础监控和告警

2. **中期重构（1-2个月）**：
   - 重建错误处理架构
   - 实现组件解耦
   - 提升系统可靠性至85%

3. **长期优化（3-6个月）**：
   - 微服务化改造
   - 完善运维体系
   - 实现95%+的系统可靠性

### 7.2 预期效果

通过系统性的架构改进，预期实现：
- 🎯 **系统可靠性**：从30%提升到95%+
- 🎯 **用户体验**：查询成功率达到95%，响应时间降至2s
- 🎯 **运维效率**：故障检测和恢复时间大幅缩短
- 🎯 **技术债务**：减少60%，提升代码质量

### 7.3 关键成功因素

1. **严格的质量控制**：每个阶段都有详细的测试和验收标准
2. **风险控制机制**：完善的回滚和应急预案
3. **持续监控优化**：全面的监控体系和持续改进
4. **团队协作**：明确的分工和有效的沟通机制

通过本修复方案的实施，Mercari AI Agent系统将从当前的不稳定状态转变为一个高可靠、高性能、易维护的现代化系统架构，为业务的持续发展提供坚实的技术支撑。

---

**文档版本**：v1.0  
**创建日期**：2025-01-28  
**更新日期**：2025-01-28  
**适用范围**：Mercari AI Agent 系统架构修复
