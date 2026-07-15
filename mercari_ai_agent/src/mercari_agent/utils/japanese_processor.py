"""
日语处理工具模块

该模块提供专门的日语文本处理功能。
支持分词、词性标注、文本规范化等日语NLP功能。

主要功能：
- 日语分词（支持多种分词器）
- 词性标注
- 文本规范化
- 全角半角转换
- 汉字读音转换

Author: Mercari AI Agent Team
"""

import logging
import unicodedata
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re

from .logger import get_logger

logger = get_logger(__name__)


class TokenizerType(Enum):
    """分词器类型枚举"""
    SUDACHI = "sudachi"
    MECAB = "mecab"
    JANOME = "janome"
    SPACY = "spacy"


@dataclass
class Token:
    """词汇单元"""
    surface: str        # 表层形式
    reading: str        # 读音
    part_of_speech: str # 词性
    base_form: str      # 基本形式
    features: List[str] # 特征列表


@dataclass
class ProcessedText:
    """处理后的文本"""
    original: str       # 原始文本
    normalized: str     # 规范化文本
    tokens: List[Token] # 词汇列表
    sentences: List[str] # 句子列表
    metadata: Dict[str, Any] # 元数据


class JapaneseProcessor:
    """
    日语处理器类 - 单例模式
    
    提供专业的日语文本处理功能。
    支持多种分词器和处理选项。
    """
    
    _instance = None
    _lock = None
    _initialized = False
    
    def __new__(cls, tokenizer_type: TokenizerType = TokenizerType.SUDACHI):
        """单例模式的新建实例方法"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, tokenizer_type: TokenizerType = TokenizerType.SUDACHI):
        """
        初始化日语处理器
        
        Args:
            tokenizer_type: 分词器类型
        """
        # 防止重复初始化
        if self._initialized:
            logger.debug(f"JapaneseProcessor already initialized with {self.tokenizer_type.value}")
            return
        
        self.tokenizer_type = tokenizer_type
        self.tokenizer = None
        self.normalizer = TextNormalizer()
        self.sentence_splitter = SentenceSplitter()
        
        # 添加状态跟踪变量，防止无限递归
        self._initialization_attempted = set()
        self._fallback_in_progress = False
        
        # 初始化分词器
        self._initialize_tokenizer()
        
        # 标记为已初始化
        self._initialized = True
        logger.info(f"JapaneseProcessor initialized with {tokenizer_type.value}")
    
    def _initialize_tokenizer(self):
        """初始化分词器"""
        # 检查是否已经尝试过这个分词器
        if self.tokenizer_type in self._initialization_attempted:
            logger.warning(f"分词器 {self.tokenizer_type.value} 已经尝试过，跳过")
            return
        
        # 标记已尝试
        self._initialization_attempted.add(self.tokenizer_type)
        
        try:
            if self.tokenizer_type == TokenizerType.SUDACHI:
                self.tokenizer = self._init_sudachi()
            elif self.tokenizer_type == TokenizerType.MECAB:
                self.tokenizer = self._init_mecab()
            elif self.tokenizer_type == TokenizerType.JANOME:
                self.tokenizer = self._init_janome()
            elif self.tokenizer_type == TokenizerType.SPACY:
                self.tokenizer = self._init_spacy()
            else:
                raise ValueError(f"不支持的分词器类型: {self.tokenizer_type}")
                
        except ImportError as e:
            logger.warning(f"无法加载 {self.tokenizer_type.value} 分词器: {e}")
            # 回退到备用分词器
            if not self._fallback_in_progress:
                self._fallback_tokenizer()
        except Exception as e:
            logger.error(f"初始化分词器时发生错误: {e}")
            # 回退到备用分词器
            if not self._fallback_in_progress:
                self._fallback_tokenizer()
    
    def _init_sudachi(self):
        """初始化SudachiPy分词器"""
        try:
            from sudachipy import tokenizer, dictionary
            return tokenizer.Tokenizer(dictionary.Dictionary())
        except ImportError:
            raise ImportError("SudachiPy not installed. Install with: pip install sudachipy")
    
    def _init_mecab(self):
        """初始化MeCab分词器"""
        try:
            import MeCab
            return MeCab.Tagger()
        except ImportError:
            raise ImportError("MeCab not installed. Install with: pip install mecab-python3")
    
    def _init_janome(self):
        """初始化Janome分词器"""
        try:
            from janome.tokenizer import Tokenizer
            return Tokenizer()
        except ImportError:
            raise ImportError("Janome not installed. Install with: pip install janome")
    
    def _init_spacy(self):
        """初始化spaCy分词器"""
        try:
            import spacy
            return spacy.load("ja_core_news_sm")
        except ImportError:
            raise ImportError("spaCy not installed. Install with: pip install spacy")
        except OSError:
            raise ImportError("Japanese model not found. Install with: python -m spacy download ja_core_news_sm")
    
    def _fallback_tokenizer(self):
        """回退到备用分词器"""
        # 设置回退进行中标志，防止递归
        if self._fallback_in_progress:
            logger.warning("回退分词器已在进行中，避免重复调用")
            return
        
        self._fallback_in_progress = True
        
        try:
            fallback_order = [TokenizerType.JANOME, TokenizerType.MECAB, TokenizerType.SUDACHI, TokenizerType.SPACY]
            
            for tokenizer_type in fallback_order:
                # 跳过当前分词器和已尝试的分词器
                if tokenizer_type == self.tokenizer_type or tokenizer_type in self._initialization_attempted:
                    continue
                
                try:
                    logger.info(f"尝试回退到 {tokenizer_type.value} 分词器")
                    self.tokenizer_type = tokenizer_type
                    self._initialize_tokenizer()
                    
                    # 如果成功初始化，退出循环
                    if self.tokenizer is not None:
                        logger.info(f"成功回退到 {tokenizer_type.value} 分词器")
                        return
                        
                except (ImportError, ValueError, Exception) as e:
                    logger.debug(f"回退到 {tokenizer_type.value} 失败: {e}")
                    continue
            
            # 如果所有分词器都失败，使用简单分词器
            logger.warning("所有分词器都失败，使用简单分词器作为最后备用")
            self.tokenizer = SimpleTokenizer()
            
        finally:
            # 重置回退进行中标志
            self._fallback_in_progress = False
    
    def preprocess_text(self, text: str) -> str:
        """
        预处理文本（同步方法）
        
        Args:
            text: 输入文本
            
        Returns:
            str: 预处理后的文本
        """
        if not text or not text.strip():
            return ""
        
        try:
            # 基本的文本规范化
            normalized_text = unicodedata.normalize('NFKC', text)
            
            # 去除多余的空格
            normalized_text = re.sub(r'\s+', ' ', normalized_text.strip())
            
            return normalized_text
            
        except Exception as e:
            logger.error(f"文本预处理失败: {e}")
            return text
    
    async def process(self, text: str) -> ProcessedText:
        """
        处理日语文本
        
        Args:
            text: 输入文本
            
        Returns:
            ProcessedText: 处理结果
        """
        if not text or not text.strip():
            return ProcessedText(
                original="",
                normalized="",
                tokens=[],
                sentences=[],
                metadata={}
            )
        
        try:
            # 1. 文本规范化
            normalized_text = await self.normalizer.normalize(text)
            
            # 2. 句子分割
            sentences = await self.sentence_splitter.split(normalized_text)
            
            # 3. 分词和词性标注
            tokens = await self._tokenize(normalized_text)
            
            # 4. 构建结果
            result = ProcessedText(
                original=text,
                normalized=normalized_text,
                tokens=tokens,
                sentences=sentences,
                metadata={
                    "tokenizer_type": self.tokenizer_type.value,
                    "token_count": len(tokens),
                    "sentence_count": len(sentences),
                    "character_count": len(normalized_text)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"日语文本处理失败: {e}")
            # 返回基本结果
            return ProcessedText(
                original=text,
                normalized=text,
                tokens=[],
                sentences=[text],
                metadata={"error": str(e)}
            )
    
    async def _tokenize(self, text: str) -> List[Token]:
        """分词和词性标注"""
        tokens = []
        
        try:
            if self.tokenizer_type == TokenizerType.SUDACHI:
                tokens = await self._tokenize_sudachi(text)
            elif self.tokenizer_type == TokenizerType.MECAB:
                tokens = await self._tokenize_mecab(text)
            elif self.tokenizer_type == TokenizerType.JANOME:
                tokens = await self._tokenize_janome(text)
            elif self.tokenizer_type == TokenizerType.SPACY:
                tokens = await self._tokenize_spacy(text)
            else:
                tokens = await self._tokenize_simple(text)
                
        except Exception as e:
            logger.error(f"分词失败: {e}")
            tokens = await self._tokenize_simple(text)
        
        return tokens
    
    async def _tokenize_sudachi(self, text: str) -> List[Token]:
        """使用SudachiPy分词"""
        tokens = []
        
        try:
            morphemes = self.tokenizer.tokenize(text)
            
            for m in morphemes:
                token = Token(
                    surface=m.surface(),
                    reading=m.reading_form(),
                    part_of_speech=m.part_of_speech()[0],
                    base_form=m.dictionary_form(),
                    features=m.part_of_speech()
                )
                tokens.append(token)
                
        except Exception as e:
            logger.error(f"SudachiPy分词失败: {e}")
        
        return tokens
    
    async def _tokenize_mecab(self, text: str) -> List[Token]:
        """使用MeCab分词"""
        tokens = []
        
        try:
            node = self.tokenizer.parseToNode(text)
            
            while node:
                if node.surface:
                    features = node.feature.split(',')
                    
                    token = Token(
                        surface=node.surface,
                        reading=features[7] if len(features) > 7 else node.surface,
                        part_of_speech=features[0] if features else "不明",
                        base_form=features[6] if len(features) > 6 else node.surface,
                        features=features
                    )
                    tokens.append(token)
                
                node = node.next
                
        except Exception as e:
            logger.error(f"MeCab分词失败: {e}")
        
        return tokens
    
    async def _tokenize_janome(self, text: str) -> List[Token]:
        """使用Janome分词"""
        tokens = []
        
        try:
            morphemes = self.tokenizer.tokenize(text, wakati=False)
            
            for m in morphemes:
                token = Token(
                    surface=m.surface,
                    reading=m.reading if hasattr(m, 'reading') else m.surface,
                    part_of_speech=m.part_of_speech.split(',')[0],
                    base_form=m.base_form if hasattr(m, 'base_form') else m.surface,
                    features=m.part_of_speech.split(',')
                )
                tokens.append(token)
                
        except Exception as e:
            logger.error(f"Janome分词失败: {e}")
        
        return tokens
    
    async def _tokenize_spacy(self, text: str) -> List[Token]:
        """使用spaCy分词"""
        tokens = []
        
        try:
            doc = self.tokenizer(text)
            
            for token in doc:
                token_obj = Token(
                    surface=token.text,
                    reading=token.text,  # spaCy doesn't provide reading
                    part_of_speech=token.pos_,
                    base_form=token.lemma_,
                    features=[token.pos_, token.tag_]
                )
                tokens.append(token_obj)
                
        except Exception as e:
            logger.error(f"spaCy分词失败: {e}")
        
        return tokens
    
    async def _tokenize_simple(self, text: str) -> List[Token]:
        """简单分词（备用）"""
        tokens = []
        
        # 基于空格和标点符号的简单分词
        import re
        words = re.findall(r'\S+', text)
        
        for word in words:
            token = Token(
                surface=word,
                reading=word,
                part_of_speech="不明",
                base_form=word,
                features=["不明"]
            )
            tokens.append(token)
        
        return tokens
    
    def get_supported_tokenizers(self) -> List[TokenizerType]:
        """获取支持的分词器列表"""
        supported = []
        
        for tokenizer_type in TokenizerType:
            try:
                if tokenizer_type == TokenizerType.SUDACHI:
                    import sudachipy
                    supported.append(tokenizer_type)
                elif tokenizer_type == TokenizerType.MECAB:
                    import MeCab
                    supported.append(tokenizer_type)
                elif tokenizer_type == TokenizerType.JANOME:
                    import janome
                    supported.append(tokenizer_type)
                elif tokenizer_type == TokenizerType.SPACY:
                    import spacy
                    supported.append(tokenizer_type)
            except ImportError:
                continue
        
        return supported
    
    def get_info(self) -> Dict[str, Any]:
        """获取处理器信息"""
        return {
            "current_tokenizer": self.tokenizer_type.value,
            "supported_tokenizers": [t.value for t in self.get_supported_tokenizers()],
            "version": "1.0.0"
        }


class TextNormalizer:
    """文本规范化器"""
    
    def __init__(self):
        self.unicode_normalizer = unicodedata.normalize
        
    async def normalize(self, text: str) -> str:
        """
        规范化文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 规范化后的文本
        """
        if not text:
            return ""
        
        # 1. Unicode规范化
        text = self.unicode_normalizer('NFKC', text)
        
        # 2. 全角半角转换
        text = self._convert_width(text)
        
        # 3. 空白字符处理
        text = self._normalize_whitespace(text)
        
        # 4. 价格格式规范化
        text = self._normalize_price_format(text)
        
        return text.strip()
    
    def _convert_width(self, text: str) -> str:
        """全角半角转换"""
        # 数字和英文字母转半角
        full_to_half = str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        )
        
        return text.translate(full_to_half)
    
    def _normalize_whitespace(self, text: str) -> str:
        """空白字符规范化"""
        # 将多个空白字符替换为单个空格
        text = re.sub(r'\s+', ' ', text)
        
        # 移除行首行尾空白
        text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)
        
        return text
    
    def _normalize_price_format(self, text: str) -> str:
        """价格格式规范化"""
        # 统一价格格式
        price_patterns = [
            (r'([￥¥])\s*(\d+(?:,\d{3})*)\s*円?', r'\1\2'),
            (r'(\d+(?:,\d{3})*)\s*円', r'¥\1'),
            (r'(\d+(?:,\d{3})*)\s*yen', r'¥\1')
        ]
        
        for pattern, replacement in price_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text


class SentenceSplitter:
    """句子分割器"""
    
    def __init__(self):
        self.sentence_endings = ['。', '！', '？', '!', '?', '．']
        
    async def split(self, text: str) -> List[str]:
        """
        分割句子
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 句子列表
        """
        if not text:
            return []
        
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            
            if char in self.sentence_endings:
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # 添加最后一个句子
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences


class SimpleTokenizer:
    """简单分词器（备用）"""
    
    def __init__(self):
        """初始化简单分词器"""
        # 日语基本字符模式
        self.word_pattern = re.compile(r'[ぁ-ゖァ-ヾ一-龯0-9a-zA-Z]+|[^\s]')
        
    def tokenize(self, text: str) -> List[str]:
        """
        简单分词
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 分词结果
        """
        if not text:
            return []
        
        # 基于字符类型的简单分词
        tokens = self.word_pattern.findall(text)
        return [token for token in tokens if token.strip()]
    
    def parse(self, text: str) -> List[Token]:
        """
        解析文本并返回Token对象列表
        
        Args:
            text: 输入文本
            
        Returns:
            List[Token]: Token对象列表
        """
        if not text:
            return []
        
        tokens = []
        words = self.tokenize(text)
        
        for word in words:
            token = Token(
                surface=word,
                reading=word,
                part_of_speech="不明",
                base_form=word,
                features=["不明"]
            )
            tokens.append(token)
        
        return tokens
    
    def parseToNode(self, text: str):
        """
        为了与MeCab接口兼容的方法
        
        Args:
            text: 输入文本
            
        Returns:
            SimpleNode: 简单节点对象
        """
        return SimpleNode(self.tokenize(text))


class SimpleNode:
    """简单节点类，用于兼容MeCab接口"""
    
    def __init__(self, tokens: List[str]):
        """
        初始化简单节点
        
        Args:
            tokens: 分词结果
        """
        self.tokens = tokens
        self.index = 0
        self.surface = None
        self.feature = "不明,*,*,*,*,*,*,*,*"
        self.next = None
        
        if tokens:
            self.surface = tokens[0]
            self._build_chain()
    
    def _build_chain(self):
        """构建节点链"""
        current = self
        
        for i in range(1, len(self.tokens)):
            next_node = SimpleNode([])
            next_node.surface = self.tokens[i]
            next_node.feature = "不明,*,*,*,*,*,*,*,*"
            current.next = next_node
            current = next_node
        
        # 最后一个节点
        current.next = SimpleNode([])
        current.next.surface = None

# 便捷的获取单例实例的函数
_global_processor = None

def get_japanese_processor(tokenizer_type: TokenizerType = TokenizerType.SUDACHI) -> JapaneseProcessor:
    """
    获取日语处理器单例实例
    
    Args:
        tokenizer_type: 分词器类型
        
    Returns:
        JapaneseProcessor: 日语处理器实例
    """
    global _global_processor
    
    if _global_processor is None:
        _global_processor = JapaneseProcessor(tokenizer_type)
    
    return _global_processor

def reset_japanese_processor():
    """重置日语处理器单例（用于测试）"""
    global _global_processor
    _global_processor = None
    JapaneseProcessor._instance = None
    JapaneseProcessor._initialized = False