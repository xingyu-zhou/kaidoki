"""
验证码解决器模块

该模块提供验证码解决功能，包括：
- 集成UI管理器进行人机交互
- 支持多种验证码类型的解决
- 解决方案验证和应用
- 自动重试和错误处理
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta

from .captcha_types import (
    CaptchaType, CaptchaChallenge, CaptchaSolution, UIResult,
    CaptchaStatus, CAPTCHA_SOLVING_CONFIG
)
from .ui_manager import CaptchaUIManager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CaptchaSolver:
    """验证码解决器"""
    
    def __init__(self, ui_manager: CaptchaUIManager, config: Dict[str, Any] = None):
        """
        初始化验证码解决器
        
        Args:
            ui_manager: UI管理器
            config: 解决器配置
        """
        self.ui_manager = ui_manager
        self.config = config or CAPTCHA_SOLVING_CONFIG
        
        # 解决器策略映射
        self.solver_strategies = {
            CaptchaType.IMAGE_TEXT: self._solve_image_text,
            CaptchaType.SLIDE_PUZZLE: self._solve_slide_puzzle,
            CaptchaType.CLICK_SEQUENCE: self._solve_click_sequence,
            CaptchaType.RECAPTCHA_V2: self._solve_recaptcha_v2,
            CaptchaType.RECAPTCHA_V3: self._solve_recaptcha_v3,
            CaptchaType.HCAPTCHA: self._solve_hcaptcha,
            CaptchaType.GEETEST: self._solve_geetest,
            CaptchaType.FUNCAPTCHA: self._solve_funcaptcha,
            CaptchaType.CUSTOM: self._solve_custom
        }
        
        # 统计信息
        self.total_attempts = 0
        self.successful_solves = 0
        self.failed_solves = 0
        self.solve_times = []
        self.type_stats = {}
        
        logger.info("CaptchaSolver initialized")
    
    async def solve_captcha(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """
        解决验证码
        
        Args:
            challenge: 验证码挑战
            
        Returns:
            CaptchaSolution: 解决方案
            
        Raises:
            ValueError: 不支持的验证码类型
            TimeoutError: 解决超时
        """
        self.total_attempts += 1
        start_time = time.time()
        
        try:
            # 检查挑战是否过期
            if challenge.is_expired():
                raise ValueError(f"Challenge expired: {challenge.challenge_id}")
            
            # 更新挑战状态
            challenge.status = CaptchaStatus.PROCESSING
            
            # 获取对应的解决策略
            solver_func = self.solver_strategies.get(challenge.captcha_type)
            if not solver_func:
                raise ValueError(f"Unsupported captcha type: {challenge.captcha_type}")
            
            # 执行解决策略
            logger.info(f"Solving captcha {challenge.challenge_id} of type {challenge.captcha_type.value}")
            solution = await solver_func(challenge)
            
            # 更新统计信息
            solving_time = time.time() - start_time
            self.successful_solves += 1
            self.solve_times.append(solving_time)
            self._update_type_stats(challenge.captcha_type, "success")
            
            # 更新挑战状态
            challenge.status = CaptchaStatus.SOLVED
            
            logger.info(f"Successfully solved captcha {challenge.challenge_id} in {solving_time:.2f}s")
            return solution
            
        except Exception as e:
            # 更新统计信息
            solving_time = time.time() - start_time
            self.failed_solves += 1
            self._update_type_stats(challenge.captcha_type, "failure")
            
            # 更新挑战状态
            challenge.status = CaptchaStatus.FAILED
            
            logger.error(f"Failed to solve captcha {challenge.challenge_id}: {e}")
            raise
    
    async def _solve_image_text(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决图片文字验证码"""
        max_attempts = self.config.get("max_retry_attempts", 3)
        
        for attempt in range(max_attempts):
            try:
                # 显示验证码界面
                ui_result = await self.ui_manager.show_captcha_ui(challenge)
                
                if ui_result.cancelled:
                    raise ValueError("User cancelled captcha solving")
                
                if not ui_result.success or not ui_result.text_input:
                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                        continue
                    else:
                        raise ValueError("No valid text input received")
                
                # 创建解决方案
                solution = CaptchaSolution(
                    challenge_id=challenge.challenge_id,
                    solution_type=CaptchaType.IMAGE_TEXT,
                    solution_data={"text": ui_result.text_input},
                    confidence=ui_result.confidence,
                    solving_time=ui_result.solving_time,
                    text_result=ui_result.text_input,
                    attempt_count=attempt + 1,
                    refresh_count=ui_result.refresh_count
                )
                
                return solution
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Image text solving attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1)  # 短暂延迟后重试
                else:
                    raise
        
        raise ValueError("Failed to solve image text captcha after all attempts")
    
    async def _solve_slide_puzzle(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决滑块验证码"""
        max_attempts = self.config.get("max_retry_attempts", 3)
        
        for attempt in range(max_attempts):
            try:
                # 显示滑块界面
                ui_result = await self.ui_manager.show_captcha_ui(challenge)
                
                if ui_result.cancelled:
                    raise ValueError("User cancelled captcha solving")
                
                if not ui_result.success or ui_result.slide_distance is None:
                    if attempt < max_attempts - 1:
                        logger.warning(f"Slide attempt {attempt + 1} failed, retrying...")
                        continue
                    else:
                        raise ValueError("No valid slide distance received")
                
                # 创建解决方案
                solution = CaptchaSolution(
                    challenge_id=challenge.challenge_id,
                    solution_type=CaptchaType.SLIDE_PUZZLE,
                    solution_data={"slide_distance": ui_result.slide_distance},
                    confidence=ui_result.confidence,
                    solving_time=ui_result.solving_time,
                    slide_distance=ui_result.slide_distance,
                    attempt_count=attempt + 1
                )
                
                return solution
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Slide puzzle solving attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1)
                else:
                    raise
        
        raise ValueError("Failed to solve slide puzzle captcha after all attempts")
    
    async def _solve_click_sequence(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决点击序列验证码"""
        max_attempts = self.config.get("max_retry_attempts", 3)
        
        for attempt in range(max_attempts):
            try:
                # 显示点击界面
                ui_result = await self.ui_manager.show_captcha_ui(challenge)
                
                if ui_result.cancelled:
                    raise ValueError("User cancelled captcha solving")
                
                if not ui_result.success or not ui_result.click_points:
                    if attempt < max_attempts - 1:
                        logger.warning(f"Click attempt {attempt + 1} failed, retrying...")
                        continue
                    else:
                        raise ValueError("No valid click points received")
                
                # 创建解决方案
                solution = CaptchaSolution(
                    challenge_id=challenge.challenge_id,
                    solution_type=CaptchaType.CLICK_SEQUENCE,
                    solution_data={"click_points": ui_result.click_points},
                    confidence=ui_result.confidence,
                    solving_time=ui_result.solving_time,
                    coordinates=ui_result.click_points,
                    attempt_count=attempt + 1
                )
                
                return solution
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Click sequence solving attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1)
                else:
                    raise
        
        raise ValueError("Failed to solve click sequence captcha after all attempts")
    
    async def _solve_recaptcha_v2(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决reCAPTCHA v2"""
        # reCAPTCHA v2通常需要与JavaScript交互
        # 这里提供一个基本的实现框架
        
        logger.info("Solving reCAPTCHA v2 - requires manual intervention")
        
        # 创建一个简单的通知界面
        challenge.instruction = "请在浏览器中完成Google reCAPTCHA验证，然后点击确认"
        
        # 显示界面（这里可以显示一个确认对话框）
        ui_result = await self.ui_manager.show_captcha_ui(challenge)
        
        if ui_result.cancelled:
            raise ValueError("User cancelled reCAPTCHA solving")
        
        # 创建解决方案
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.RECAPTCHA_V2,
            solution_data={"manual_completion": True},
            confidence=0.9,  # 假设手动完成的置信度较高
            solving_time=ui_result.solving_time,
            token="manual_completion_token"
        )
        
        return solution
    
    async def _solve_recaptcha_v3(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决reCAPTCHA v3"""
        # reCAPTCHA v3通常是后台自动处理
        logger.info("Solving reCAPTCHA v3 - automatic processing")
        
        # 模拟处理时间
        await asyncio.sleep(2)
        
        # 创建解决方案
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.RECAPTCHA_V3,
            solution_data={"automatic_processing": True},
            confidence=0.8,
            solving_time=2.0,
            token="recaptcha_v3_token"
        )
        
        return solution
    
    async def _solve_hcaptcha(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决hCaptcha"""
        logger.info("Solving hCaptcha - requires manual intervention")
        
        challenge.instruction = "请在浏览器中完成hCaptcha验证，然后点击确认"
        
        ui_result = await self.ui_manager.show_captcha_ui(challenge)
        
        if ui_result.cancelled:
            raise ValueError("User cancelled hCaptcha solving")
        
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.HCAPTCHA,
            solution_data={"manual_completion": True},
            confidence=0.9,
            solving_time=ui_result.solving_time,
            token="hcaptcha_token"
        )
        
        return solution
    
    async def _solve_geetest(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决极验验证码"""
        logger.info("Solving GeeTest captcha")
        
        # 极验验证码通常包含多种类型，这里提供一个通用的处理方式
        challenge.instruction = "请完成极验验证码验证"
        
        ui_result = await self.ui_manager.show_captcha_ui(challenge)
        
        if ui_result.cancelled:
            raise ValueError("User cancelled GeeTest solving")
        
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.GEETEST,
            solution_data={"geetest_completion": True},
            confidence=0.8,
            solving_time=ui_result.solving_time,
            token="geetest_token"
        )
        
        return solution
    
    async def _solve_funcaptcha(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决FunCaptcha"""
        logger.info("Solving FunCaptcha")
        
        challenge.instruction = "请完成FunCaptcha验证"
        
        ui_result = await self.ui_manager.show_captcha_ui(challenge)
        
        if ui_result.cancelled:
            raise ValueError("User cancelled FunCaptcha solving")
        
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.FUNCAPTCHA,
            solution_data={"funcaptcha_completion": True},
            confidence=0.8,
            solving_time=ui_result.solving_time,
            token="funcaptcha_token"
        )
        
        return solution
    
    async def _solve_custom(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """解决自定义验证码"""
        logger.info("Solving custom captcha")
        
        # 自定义验证码的处理逻辑
        # 这里可以根据具体的验证码类型进行处理
        
        ui_result = await self.ui_manager.show_captcha_ui(challenge)
        
        if ui_result.cancelled:
            raise ValueError("User cancelled custom captcha solving")
        
        solution = CaptchaSolution(
            challenge_id=challenge.challenge_id,
            solution_type=CaptchaType.CUSTOM,
            solution_data={"custom_completion": True},
            confidence=0.7,
            solving_time=ui_result.solving_time,
            token="custom_token"
        )
        
        return solution
    
    def _update_type_stats(self, captcha_type: CaptchaType, result: str):
        """更新类型统计"""
        if captcha_type not in self.type_stats:
            self.type_stats[captcha_type] = {
                "success": 0,
                "failure": 0,
                "total": 0
            }
        
        self.type_stats[captcha_type][result] += 1
        self.type_stats[captcha_type]["total"] += 1
    
    def get_solver_stats(self) -> Dict[str, Any]:
        """获取解决器统计信息"""
        avg_solve_time = sum(self.solve_times) / len(self.solve_times) if self.solve_times else 0
        success_rate = self.successful_solves / self.total_attempts if self.total_attempts > 0 else 0
        
        # 按类型统计
        type_stats = {}
        for captcha_type, stats in self.type_stats.items():
            type_success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            type_stats[captcha_type.value] = {
                "total": stats["total"],
                "success": stats["success"],
                "failure": stats["failure"],
                "success_rate": f"{type_success_rate * 100:.2f}%"
            }
        
        return {
            "total_attempts": self.total_attempts,
            "successful_solves": self.successful_solves,
            "failed_solves": self.failed_solves,
            "success_rate": f"{success_rate * 100:.2f}%",
            "average_solve_time": f"{avg_solve_time:.2f}s",
            "type_stats": type_stats
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_attempts = 0
        self.successful_solves = 0
        self.failed_solves = 0
        self.solve_times = []
        self.type_stats = {}
        
        logger.info("Solver statistics reset")


class SolutionValidator:
    """解决方案验证器"""
    
    def __init__(self):
        self.validation_rules = {
            CaptchaType.IMAGE_TEXT: self._validate_image_text,
            CaptchaType.SLIDE_PUZZLE: self._validate_slide_puzzle,
            CaptchaType.CLICK_SEQUENCE: self._validate_click_sequence
        }
    
    def validate_solution(self, solution: CaptchaSolution) -> bool:
        """
        验证解决方案
        
        Args:
            solution: 解决方案
            
        Returns:
            bool: 是否有效
        """
        try:
            validator = self.validation_rules.get(solution.solution_type)
            if not validator:
                # 对于没有特定验证器的类型，进行基本验证
                return self._validate_basic(solution)
            
            return validator(solution)
            
        except Exception as e:
            logger.error(f"Solution validation failed: {e}")
            return False
    
    def _validate_basic(self, solution: CaptchaSolution) -> bool:
        """基本验证"""
        # 检查必要字段
        if not solution.challenge_id:
            return False
        
        if not solution.solution_type:
            return False
        
        if not solution.solution_data:
            return False
        
        # 检查置信度范围
        if not (0 <= solution.confidence <= 1):
            return False
        
        # 检查解决时间
        if solution.solving_time < 0:
            return False
        
        return True
    
    def _validate_image_text(self, solution: CaptchaSolution) -> bool:
        """验证图片文字解决方案"""
        if not self._validate_basic(solution):
            return False
        
        # 检查文字结果
        if not solution.text_result:
            return False
        
        # 检查文字长度（通常验证码不会太长）
        if len(solution.text_result) > 20:
            return False
        
        # 检查解决方案数据
        if "text" not in solution.solution_data:
            return False
        
        return True
    
    def _validate_slide_puzzle(self, solution: CaptchaSolution) -> bool:
        """验证滑块解决方案"""
        if not self._validate_basic(solution):
            return False
        
        # 检查滑动距离
        if solution.slide_distance is None:
            return False
        
        # 检查滑动距离范围（通常在0-500像素之间）
        if not (0 <= solution.slide_distance <= 500):
            return False
        
        # 检查解决方案数据
        if "slide_distance" not in solution.solution_data:
            return False
        
        return True
    
    def _validate_click_sequence(self, solution: CaptchaSolution) -> bool:
        """验证点击序列解决方案"""
        if not self._validate_basic(solution):
            return False
        
        # 检查点击坐标
        if not solution.coordinates:
            return False
        
        # 检查坐标格式
        for coord in solution.coordinates:
            if not isinstance(coord, (list, tuple)) or len(coord) != 2:
                return False
            
            x, y = coord
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                return False
        
        # 检查解决方案数据
        if "click_points" not in solution.solution_data:
            return False
        
        return True


class SolutionApplier:
    """解决方案应用器"""
    
    def __init__(self):
        self.application_handlers = {
            CaptchaType.IMAGE_TEXT: self._apply_image_text,
            CaptchaType.SLIDE_PUZZLE: self._apply_slide_puzzle,
            CaptchaType.CLICK_SEQUENCE: self._apply_click_sequence
        }
    
    async def apply_solution(self, solution: CaptchaSolution, 
                           session: Any = None, 
                           form_data: Dict[str, Any] = None) -> bool:
        """
        应用解决方案
        
        Args:
            solution: 解决方案
            session: HTTP会话
            form_data: 表单数据
            
        Returns:
            bool: 是否成功应用
        """
        try:
            handler = self.application_handlers.get(solution.solution_type)
            if not handler:
                logger.warning(f"No handler for solution type: {solution.solution_type}")
                return await self._apply_generic(solution, session, form_data)
            
            return await handler(solution, session, form_data)
            
        except Exception as e:
            logger.error(f"Failed to apply solution: {e}")
            return False
    
    async def _apply_image_text(self, solution: CaptchaSolution, 
                               session: Any = None, 
                               form_data: Dict[str, Any] = None) -> bool:
        """应用图片文字解决方案"""
        if not solution.text_result:
            return False
        
        # 将文字结果添加到表单数据
        if form_data is not None:
            form_data["captcha"] = solution.text_result
            form_data["captcha_text"] = solution.text_result
        
        logger.info(f"Applied image text solution: {solution.text_result}")
        return True
    
    async def _apply_slide_puzzle(self, solution: CaptchaSolution, 
                                 session: Any = None, 
                                 form_data: Dict[str, Any] = None) -> bool:
        """应用滑块解决方案"""
        if solution.slide_distance is None:
            return False
        
        # 将滑动距离添加到表单数据
        if form_data is not None:
            form_data["slide_distance"] = solution.slide_distance
        
        logger.info(f"Applied slide puzzle solution: {solution.slide_distance}")
        return True
    
    async def _apply_click_sequence(self, solution: CaptchaSolution, 
                                   session: Any = None, 
                                   form_data: Dict[str, Any] = None) -> bool:
        """应用点击序列解决方案"""
        if not solution.coordinates:
            return False
        
        # 将点击坐标添加到表单数据
        if form_data is not None:
            form_data["click_points"] = solution.coordinates
        
        logger.info(f"Applied click sequence solution: {len(solution.coordinates)} points")
        return True
    
    async def _apply_generic(self, solution: CaptchaSolution, 
                            session: Any = None, 
                            form_data: Dict[str, Any] = None) -> bool:
        """应用通用解决方案"""
        # 对于其他类型的验证码，将令牌添加到表单数据
        if solution.token and form_data is not None:
            form_data["captcha_token"] = solution.token
        
        logger.info(f"Applied generic solution for {solution.solution_type}")
        return True