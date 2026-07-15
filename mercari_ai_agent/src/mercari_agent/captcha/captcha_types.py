"""
验证码类型定义模块

该模块定义了系统支持的各种验证码类型和相关数据结构。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CaptchaType(Enum):
    """验证码类型枚举"""
    UNKNOWN = "unknown"               # 未知类型验证码
    IMAGE_TEXT = "image_text"         # 图片文字验证码
    SLIDE_PUZZLE = "slide_puzzle"     # 滑块验证码
    CLICK_SEQUENCE = "click_sequence"  # 点击序列验证码
    RECAPTCHA_V2 = "recaptcha_v2"     # Google reCAPTCHA v2
    RECAPTCHA_V3 = "recaptcha_v3"     # Google reCAPTCHA v3
    HCAPTCHA = "hcaptcha"             # hCaptcha
    FUNCAPTCHA = "funcaptcha"         # FunCaptcha
    GEETEST = "geetest"               # 极验验证码
    CUSTOM = "custom"                 # 自定义验证码


class CaptchaStatus(Enum):
    """验证码状态枚举"""
    DETECTED = "detected"     # 已检测
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    SOLVED = "solved"         # 已解决
    FAILED = "failed"         # 失败
    TIMEOUT = "timeout"       # 超时
    CANCELLED = "cancelled"   # 已取消


@dataclass
class CaptchaChallenge:
    """验证码挑战数据"""
    challenge_id: str
    captcha_type: CaptchaType
    status: CaptchaStatus = CaptchaStatus.DETECTED
    
    # 图片相关
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    
    # 挑战参数
    challenge_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # 验证码特定参数
    slide_track: Optional[List[Tuple[int, int]]] = None  # 滑块轨迹
    click_points: Optional[List[Tuple[int, int]]] = None  # 点击坐标
    text_answer: Optional[str] = None                    # 文字答案
    
    # 提示信息
    instruction: Optional[str] = None
    hint: Optional[str] = None
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def get_age(self) -> float:
        """获取挑战年龄（秒）"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "challenge_id": self.challenge_id,
            "captcha_type": self.captcha_type.value,
            "status": self.status.value,
            "image_url": self.image_url,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "challenge_params": self.challenge_params,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "instruction": self.instruction,
            "hint": self.hint,
            "slide_track": self.slide_track,
            "click_points": self.click_points,
            "text_answer": self.text_answer
        }


@dataclass
class CaptchaSolution:
    """验证码解决方案"""
    challenge_id: str
    solution_type: CaptchaType
    solution_data: Dict[str, Any]
    confidence: float
    solving_time: float
    solved_at: datetime = field(default_factory=datetime.now)
    
    # 解决方案数据
    text_result: Optional[str] = None
    coordinates: Optional[List[Tuple[int, int]]] = None
    slide_distance: Optional[int] = None
    slide_trajectory: Optional[List[Tuple[int, int]]] = None
    token: Optional[str] = None
    
    # 用户交互数据
    user_id: Optional[str] = None
    attempt_count: int = 1
    refresh_count: int = 0
    
    def __post_init__(self):
        """后初始化验证"""
        if not (0 <= self.confidence <= 1):
            raise ValueError("置信度必须在0-1之间")
        
        if self.solving_time < 0:
            raise ValueError("解决时间不能为负数")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "challenge_id": self.challenge_id,
            "solution_type": self.solution_type.value,
            "solution_data": self.solution_data,
            "confidence": self.confidence,
            "solving_time": self.solving_time,
            "solved_at": self.solved_at.isoformat(),
            "text_result": self.text_result,
            "coordinates": self.coordinates,
            "slide_distance": self.slide_distance,
            "slide_trajectory": self.slide_trajectory,
            "token": self.token,
            "user_id": self.user_id,
            "attempt_count": self.attempt_count,
            "refresh_count": self.refresh_count
        }


@dataclass
class CaptchaDetectionResult:
    """验证码检测结果"""
    detected: bool
    captcha_type: Optional[CaptchaType] = None
    confidence: float = 0.0
    detection_method: str = "unknown"
    challenge: Optional[CaptchaChallenge] = None
    
    # 检测详情
    patterns_matched: List[str] = field(default_factory=list)
    dom_elements: List[str] = field(default_factory=list)
    ml_score: Optional[float] = None
    
    # 元数据
    detection_time: float = 0.0
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "detected": self.detected,
            "captcha_type": self.captcha_type.value if self.captcha_type else None,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "challenge": self.challenge.to_dict() if self.challenge else None,
            "patterns_matched": self.patterns_matched,
            "dom_elements": self.dom_elements,
            "ml_score": self.ml_score,
            "detection_time": self.detection_time,
            "detected_at": self.detected_at.isoformat()
        }


@dataclass
class UIResult:
    """用户界面结果"""
    success: bool
    text_input: Optional[str] = None
    slide_distance: Optional[int] = None
    click_points: Optional[List[Tuple[int, int]]] = None
    confidence: float = 0.0
    solving_time: float = 0.0
    cancelled: bool = False
    
    # 用户行为数据
    refresh_count: int = 0
    retry_count: int = 0
    input_history: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "text_input": self.text_input,
            "slide_distance": self.slide_distance,
            "click_points": self.click_points,
            "confidence": self.confidence,
            "solving_time": self.solving_time,
            "cancelled": self.cancelled,
            "refresh_count": self.refresh_count,
            "retry_count": self.retry_count,
            "input_history": self.input_history
        }


class ChallengeBuilder:
    """验证码挑战构造器 - 智能创建CaptchaChallenge对象"""
    
    @staticmethod
    def create_challenge(captcha_type: CaptchaType,
                        detection_result: Optional['UnifiedDetectionResult'] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> CaptchaChallenge:
        """
        创建验证码挑战对象
        
        Args:
            captcha_type: 验证码类型
            detection_result: 检测结果（可选）
            metadata: 元数据（可选）
            
        Returns:
            CaptchaChallenge: 验证码挑战对象
        """
        import uuid
        from datetime import datetime, timedelta
        
        # 生成唯一的挑战ID
        challenge_id = f"challenge_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # 基础挑战对象
        challenge = CaptchaChallenge(
            challenge_id=challenge_id,
            captcha_type=captcha_type,
            status=CaptchaStatus.DETECTED,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),  # 5分钟过期
            metadata=metadata or {}
        )
        
        # 根据检测结果丰富挑战对象
        if detection_result:
            challenge.metadata.update({
                'detection_method': detection_result.detection_method,
                'confidence': detection_result.confidence,
                'patterns_matched': detection_result.patterns_matched,
                'dom_elements': detection_result.dom_elements,
                'detection_time': detection_result.detection_time
            })
            
            # 从检测结果推断更多信息
            if detection_result.details:
                challenge.metadata.update(detection_result.details)
        
        # 根据验证码类型设置特定参数
        challenge = ChallengeBuilder._configure_type_specific_params(challenge, detection_result)
        
        return challenge
    
    @staticmethod
    def _configure_type_specific_params(challenge: CaptchaChallenge,
                                       detection_result: Optional['UnifiedDetectionResult'] = None) -> CaptchaChallenge:
        """根据验证码类型配置特定参数"""
        
        captcha_type = challenge.captcha_type
        
        if captcha_type == CaptchaType.IMAGE_TEXT:
            challenge.instruction = "请输入图片中的文字"
            challenge.hint = "仔细观察图片中的字符，注意大小写"
            challenge.challenge_params = {
                'input_type': 'text',
                'max_length': 10,
                'case_sensitive': True
            }
            
        elif captcha_type == CaptchaType.SLIDE_PUZZLE:
            challenge.instruction = "请拖动滑块完成验证"
            challenge.hint = "拖动滑块到正确位置"
            challenge.challenge_params = {
                'input_type': 'slide',
                'slide_direction': 'horizontal',
                'max_distance': 300
            }
            
        elif captcha_type == CaptchaType.CLICK_SEQUENCE:
            challenge.instruction = "请按顺序点击指定图片"
            challenge.hint = "按照提示的顺序点击图片"
            challenge.challenge_params = {
                'input_type': 'click_sequence',
                'max_clicks': 5,
                'click_timeout': 30
            }
            
        elif captcha_type == CaptchaType.RECAPTCHA_V2:
            challenge.instruction = "请完成reCAPTCHA验证"
            challenge.hint = "勾选'我不是机器人'复选框"
            challenge.challenge_params = {
                'input_type': 'checkbox',
                'requires_callback': True,
                'site_key': ChallengeBuilder._extract_site_key(detection_result)
            }
            
        elif captcha_type == CaptchaType.RECAPTCHA_V3:
            challenge.instruction = "reCAPTCHA v3验证进行中"
            challenge.hint = "系统正在自动验证，请稍等"
            challenge.challenge_params = {
                'input_type': 'automatic',
                'requires_token': True,
                'site_key': ChallengeBuilder._extract_site_key(detection_result)
            }
            
        elif captcha_type == CaptchaType.HCAPTCHA:
            challenge.instruction = "请完成hCaptcha验证"
            challenge.hint = "解决验证问题"
            challenge.challenge_params = {
                'input_type': 'interactive',
                'requires_callback': True,
                'site_key': ChallengeBuilder._extract_site_key(detection_result)
            }
            
        elif captcha_type == CaptchaType.GEETEST:
            challenge.instruction = "请完成极验验证"
            challenge.hint = "按照提示完成验证"
            challenge.challenge_params = {
                'input_type': 'interactive',
                'requires_callback': True,
                'provider': 'geetest'
            }
            
        elif captcha_type == CaptchaType.FUNCAPTCHA:
            challenge.instruction = "请完成FunCaptcha验证"
            challenge.hint = "按照游戏规则完成验证"
            challenge.challenge_params = {
                'input_type': 'game',
                'requires_callback': True,
                'provider': 'funcaptcha'
            }
            
        elif captcha_type == CaptchaType.CUSTOM:
            challenge.instruction = "请完成自定义验证"
            challenge.hint = "按照页面提示完成验证"
            challenge.challenge_params = {
                'input_type': 'custom',
                'requires_analysis': True
            }
            
        else:  # UNKNOWN or other types
            challenge.instruction = "检测到验证码，请手动完成验证"
            challenge.hint = "请按照页面提示完成验证"
            challenge.challenge_params = {
                'input_type': 'manual',
                'requires_user_input': True
            }
        
        return challenge
    
    @staticmethod
    def _extract_site_key(detection_result: Optional['UnifiedDetectionResult']) -> Optional[str]:
        """从检测结果中提取site key"""
        if not detection_result:
            return None
            
        # 从dom_elements中查找site key
        for element in detection_result.dom_elements:
            if 'data-sitekey' in element:
                # 简单的正则提取
                import re
                match = re.search(r'data-sitekey="([^"]+)"', element)
                if match:
                    return match.group(1)
        
        # 从details中查找
        if detection_result.details:
            return detection_result.details.get('site_key')
        
        return None
    
    @staticmethod
    def create_emergency_challenge(task_id: str,
                                 captcha_type: CaptchaType = CaptchaType.UNKNOWN,
                                 reason: str = "Emergency challenge creation") -> CaptchaChallenge:
        """
        创建紧急挑战对象（当检测到CAPTCHA但无法创建常规挑战时）
        
        Args:
            task_id: 任务ID
            captcha_type: 验证码类型
            reason: 创建原因
            
        Returns:
            CaptchaChallenge: 紧急挑战对象
        """
        import uuid
        from datetime import datetime, timedelta
        
        challenge_id = f"emergency_{task_id}_{uuid.uuid4().hex[:8]}"
        
        challenge = CaptchaChallenge(
            challenge_id=challenge_id,
            captcha_type=captcha_type,
            status=CaptchaStatus.DETECTED,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=10),  # 紧急挑战10分钟过期
            metadata={
                'emergency_creation': True,
                'creation_reason': reason,
                'task_id': task_id
            },
            instruction="检测到验证码，请手动完成验证",
            hint="系统无法自动确定验证码类型，请根据页面提示手动完成验证"
        )
        
        challenge.challenge_params = {
            'input_type': 'manual',
            'requires_user_input': True,
            'emergency_mode': True
        }
        
        return challenge


# 验证码检测模式配置
CAPTCHA_PATTERNS = {
    CaptchaType.IMAGE_TEXT: [
        r'<img[^>]*captcha[^>]*>',
        r'verification.*image',
        r'验证码.*图片',
        r'captcha.*img',
        r'verifycode',
        r'authcode'
    ],
    CaptchaType.SLIDE_PUZZLE: [
        r'slide.*verify',
        r'滑动.*验证',
        r'拖动.*滑块',
        r'slide.*puzzle',
        r'slider.*captcha',
        r'drag.*verify'
    ],
    CaptchaType.CLICK_SEQUENCE: [
        r'click.*sequence',
        r'点击.*顺序',
        r'按顺序.*点击',
        r'click.*order',
        r'sequential.*click'
    ],
    CaptchaType.RECAPTCHA_V2: [
        r'g-recaptcha',
        r'recaptcha.*v2',
        r'data-sitekey',
        r'grecaptcha\.render'
    ],
    CaptchaType.RECAPTCHA_V3: [
        r'recaptcha.*v3',
        r'grecaptcha\.execute',
        r'recaptcha.*action'
    ],
    CaptchaType.HCAPTCHA: [
        r'h-captcha',
        r'hcaptcha',
        r'data-sitekey.*hcaptcha'
    ],
    CaptchaType.GEETEST: [
        r'geetest',
        r'gt-captcha',
        r'极验',
        r'initGeetest'
    ]
}

# 验证码检测配置
CAPTCHA_DETECTION_CONFIG = {
    "confidence_threshold": 0.7,
    "detection_timeout": 10.0,
    "max_detection_attempts": 3,
    "enable_ml_detection": True,
    "enable_dom_detection": True,
    "enable_image_analysis": True
}

# 验证码解决配置
CAPTCHA_SOLVING_CONFIG = {
    "max_solving_time": 300,  # 5分钟
    "max_retry_attempts": 3,
    "auto_refresh_enabled": True,
    "input_validation": True,
    "save_user_history": True,
    "ui_timeout": 300
}