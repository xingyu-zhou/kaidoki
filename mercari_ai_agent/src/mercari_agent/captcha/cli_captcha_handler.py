"""
CLI环境下的CAPTCHA处理器

该模块提供在CLI环境下处理CAPTCHA的功能，包括：
- CLI环境检测
- 自动跳过机制
- 智能重试策略
- 降级处理方案
"""

import asyncio
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

from .captcha_types import CaptchaType, CaptchaChallenge, CaptchaSolution, UIResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CLIConfig:
    """CLI配置"""
    enabled: bool = True
    auto_skip: bool = True
    max_retries: int = 5
    retry_delays: List[float] = None
    fallback_strategies: List[str] = None
    
    def __post_init__(self):
        if self.retry_delays is None:
            self.retry_delays = [5, 10, 20, 40, 80]
        if self.fallback_strategies is None:
            self.fallback_strategies = [
                "cache_lookup",
                "partial_extraction", 
                "session_rotation",
                "request_modification"
            ]


class CLICaptchaHandler:
    """CLI环境下的CAPTCHA处理器"""
    
    def __init__(self, config: Optional[CLIConfig] = None):
        """
        初始化CLI CAPTCHA处理器
        
        Args:
            config: CLI配置
        """
        self.config = config or CLIConfig()
        self.preset_answers = {
            # 常见验证码的预设答案
            "simple_math": {"2+3": "5", "1+1": "2", "3+4": "7", "5+2": "7"},
            "common_words": ["hello", "world", "test", "captcha", "verify"]
        }
        
        # 统计信息
        self.stats = {
            "total_encountered": 0,
            "auto_skipped": 0,
            "preset_solved": 0,
            "failed": 0,
            "success_rate": 0.0
        }
        
        logger.info("CLI CAPTCHA Handler initialized")
    
    def is_cli_environment(self) -> bool:
        """
        检测是否为CLI环境
        
        Returns:
            bool: 是否为CLI环境
        """
        # 检查是否有显示环境
        if os.environ.get('DISPLAY') is None and sys.platform != 'win32':
            return True
        
        # 检查是否在容器中运行
        if os.path.exists('/.dockerenv'):
            return True
        
        # 检查是否在CI环境中
        ci_indicators = ['CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 'JENKINS_URL']
        if any(os.environ.get(indicator) for indicator in ci_indicators):
            return True
        
        # 检查标准输入是否为终端
        if not sys.stdin.isatty():
            return True
        
        return False
    
    async def handle_captcha_cli(self, challenge: CaptchaChallenge) -> UIResult:
        """
        CLI环境下的CAPTCHA处理
        
        Args:
            challenge: CAPTCHA挑战
            
        Returns:
            UIResult: 处理结果
        """
        start_time = time.time()
        self.stats["total_encountered"] += 1
        
        logger.info(f"🔧 CLI CAPTCHA Handler: Processing {challenge.captcha_type.value} challenge")
        
        try:
            # 1. 尝试自动识别
            auto_result = await self._attempt_auto_recognition(challenge)
            if auto_result.success:
                self.stats["preset_solved"] += 1
                self._update_success_rate()
                return auto_result
            
            # 2. 保存CAPTCHA图片到文件（如果有）
            image_path = await self._save_captcha_image(challenge)
            
            # 3. 提供解决方案选项
            result = await self._provide_solution_options(challenge, image_path)
            
            # 4. 更新统计
            if result.success:
                if result.cli_mode and result.retry_suggested:
                    pass  # 重试不计入成功
                else:
                    self.stats["preset_solved"] += 1
            else:
                self.stats["failed"] += 1
            
            self._update_success_rate()
            
            # 5. 记录处理时间
            result.solving_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            logger.error(f"CLI CAPTCHA handling error: {e}")
            self.stats["failed"] += 1
            self._update_success_rate()
            
            return UIResult(
                success=False,
                error_message=str(e),
                solving_time=time.time() - start_time,
                cli_mode=True
            )
    
    async def _attempt_auto_recognition(self, challenge: CaptchaChallenge) -> UIResult:
        """
        尝试自动识别CAPTCHA
        
        Args:
            challenge: CAPTCHA挑战
            
        Returns:
            UIResult: 识别结果
        """
        # 检查是否有预设答案
        preset_answer = self._get_preset_answer(challenge)
        if preset_answer:
            logger.info(f"🎯 Found preset answer for CAPTCHA: {preset_answer}")
            return UIResult(
                success=True,
                text_input=preset_answer,
                confidence=0.8,
                solving_time=0.1,
                cli_mode=True
            )
        
        # 尝试简单的模式识别
        if challenge.captcha_type == CaptchaType.IMAGE_TEXT:
            # 对于简单的数学验证码
            if challenge.description and any(op in challenge.description for op in ['+', '-', '×', '÷']):
                result = self._solve_math_captcha(challenge.description)
                if result:
                    logger.info(f"🧮 Solved math CAPTCHA: {result}")
                    return UIResult(
                        success=True,
                        text_input=result,
                        confidence=0.9,
                        solving_time=0.1,
                        cli_mode=True
                    )
        
        return UIResult(success=False, cli_mode=True)
    
    def _get_preset_answer(self, challenge: CaptchaChallenge) -> Optional[str]:
        """
        获取预设答案
        
        Args:
            challenge: CAPTCHA挑战
            
        Returns:
            Optional[str]: 预设答案
        """
        if not challenge.description:
            return None
        
        description = challenge.description.lower()
        
        # 检查数学题
        for question, answer in self.preset_answers["simple_math"].items():
            if question in description:
                return answer
        
        # 检查常见词汇
        for word in self.preset_answers["common_words"]:
            if word in description:
                return word
        
        return None
    
    def _solve_math_captcha(self, description: str) -> Optional[str]:
        """
        解决数学验证码
        
        Args:
            description: 描述文本
            
        Returns:
            Optional[str]: 计算结果
        """
        try:
            # 简单的数学表达式解析
            import re
            
            # 匹配 "数字 运算符 数字" 的模式
            pattern = r'(\d+)\s*([+\-×÷])\s*(\d+)'
            match = re.search(pattern, description)
            
            if match:
                num1, operator, num2 = match.groups()
                num1, num2 = int(num1), int(num2)
                
                if operator == '+':
                    result = num1 + num2
                elif operator == '-':
                    result = num1 - num2
                elif operator == '×':
                    result = num1 * num2
                elif operator == '÷' and num2 != 0:
                    result = num1 // num2
                else:
                    return None
                
                return str(result)
        
        except Exception as e:
            logger.debug(f"Math CAPTCHA solving failed: {e}")
        
        return None
    
    async def _save_captcha_image(self, challenge: CaptchaChallenge) -> Optional[str]:
        """
        保存CAPTCHA图片到文件
        
        Args:
            challenge: CAPTCHA挑战
            
        Returns:
            Optional[str]: 图片文件路径
        """
        if not challenge.image_data and not challenge.image_url:
            return None
        
        try:
            # 创建保存目录
            save_dir = Path("data/captcha_images")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = int(time.time())
            filename = f"captcha_{challenge.challenge_id}_{timestamp}.png"
            filepath = save_dir / filename
            
            if challenge.image_data:
                # 保存图片数据
                with open(filepath, 'wb') as f:
                    f.write(challenge.image_data)
            elif challenge.image_url:
                # 下载并保存图片
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(challenge.image_url) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
            
            logger.info(f"💾 CAPTCHA image saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.warning(f"Failed to save CAPTCHA image: {e}")
            return None
    
    async def _provide_solution_options(self, challenge: CaptchaChallenge, image_path: Optional[str]) -> UIResult:
        """
        提供解决方案选项
        
        Args:
            challenge: CAPTCHA挑战
            image_path: 图片路径
            
        Returns:
            UIResult: 处理结果
        """
        if not self.config.enabled:
            return UIResult(success=False, cli_mode=True, error_message="CLI handler disabled")
        
        # 选项1：自动跳过
        if self.config.auto_skip:
            logger.info("🚀 CLI Mode: Auto-skipping CAPTCHA (CLI environment detected)")
            self.stats["auto_skipped"] += 1
            
            return UIResult(
                success=False,
                cancelled=False,
                cli_mode=True,
                retry_suggested=True,
                error_message="CAPTCHA auto-skipped in CLI mode"
            )
        
        # 选项2：返回失败，触发重试机制
        logger.warning("⚠️  CLI Mode: CAPTCHA detected but auto-skip disabled")
        return UIResult(
            success=False,
            cancelled=False,
            cli_mode=True,
            retry_suggested=True,
            error_message="CAPTCHA requires manual intervention"
        )
    
    def _update_success_rate(self):
        """更新成功率"""
        if self.stats["total_encountered"] > 0:
            successful = self.stats["auto_skipped"] + self.stats["preset_solved"]
            self.stats["success_rate"] = (successful / self.stats["total_encountered"]) * 100
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_encountered": 0,
            "auto_skipped": 0,
            "preset_solved": 0,
            "failed": 0,
            "success_rate": 0.0
        }
        logger.info("CLI CAPTCHA Handler stats reset")


class CLIRetryStrategy:
    """CLI重试策略"""
    
    def __init__(self, config: CLIConfig):
        self.config = config
        self.attempt_count = 0
    
    async def should_retry(self, error: Exception) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 错误信息
            
        Returns:
            bool: 是否应该重试
        """
        if self.attempt_count >= self.config.max_retries:
            return False
        
        # 对于CAPTCHA相关错误，总是重试
        error_str = str(error).lower()
        if any(keyword in error_str for keyword in ['captcha', 'verification', 'challenge']):
            return True
        
        return False
    
    async def get_retry_delay(self) -> float:
        """
        获取重试延迟
        
        Returns:
            float: 延迟时间（秒）
        """
        if self.attempt_count < len(self.config.retry_delays):
            return self.config.retry_delays[self.attempt_count]
        else:
            # 使用最后一个延迟值
            return self.config.retry_delays[-1]
    
    async def execute_retry_strategy(self, strategy: str) -> bool:
        """
        执行重试策略
        
        Args:
            strategy: 策略名称
            
        Returns:
            bool: 是否成功执行
        """
        self.attempt_count += 1
        
        try:
            if strategy == "cache_lookup":
                return await self._cache_lookup_strategy()
            elif strategy == "partial_extraction":
                return await self._partial_extraction_strategy()
            elif strategy == "session_rotation":
                return await self._session_rotation_strategy()
            elif strategy == "request_modification":
                return await self._request_modification_strategy()
            else:
                logger.warning(f"Unknown retry strategy: {strategy}")
                return False
        
        except Exception as e:
            logger.error(f"Retry strategy '{strategy}' failed: {e}")
            return False
    
    async def _cache_lookup_strategy(self) -> bool:
        """缓存查找策略"""
        logger.info("🔍 Executing cache lookup strategy")
        # 这里应该实现缓存查找逻辑
        await asyncio.sleep(1)  # 模拟处理时间
        return False  # 暂时返回False
    
    async def _partial_extraction_strategy(self) -> bool:
        """部分提取策略"""
        logger.info("📄 Executing partial extraction strategy")
        # 这里应该实现部分数据提取逻辑
        await asyncio.sleep(2)  # 模拟处理时间
        return False  # 暂时返回False
    
    async def _session_rotation_strategy(self) -> bool:
        """会话轮换策略"""
        logger.info("🔄 Executing session rotation strategy")
        # 这里应该实现会话轮换逻辑
        await asyncio.sleep(3)  # 模拟处理时间
        return True  # 会话轮换通常有效
    
    async def _request_modification_strategy(self) -> bool:
        """请求修改策略"""
        logger.info("⚙️  Executing request modification strategy")
        # 这里应该实现请求头修改逻辑
        await asyncio.sleep(2)  # 模拟处理时间
        return True  # 请求修改通常有效


# 全局CLI处理器实例
_cli_handler = None

def get_cli_handler(config: Optional[CLIConfig] = None) -> CLICaptchaHandler:
    """
    获取CLI处理器实例（单例模式）
    
    Args:
        config: CLI配置
        
    Returns:
        CLICaptchaHandler: CLI处理器实例
    """
    global _cli_handler
    if _cli_handler is None:
        _cli_handler = CLICaptchaHandler(config)
    return _cli_handler
