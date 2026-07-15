"""
产品分析器模块

该模块负责对产品数据进行多维度分析。
提供产品特征提取、质量评估和相关性分析等功能。

主要功能：
- 产品特征提取
- 质量评估
- 价格分析
- 相关性计算
- 风险评估

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import re
import math
import statistics

from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..utils.japanese_processor import JapaneseProcessor
from ..utils.price_normalizer import PriceNormalizer
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class AnalysisType(Enum):
    """分析类型枚举"""
    BASIC = "basic"
    DETAILED = "detailed"
    COMPARATIVE = "comparative"
    PREDICTIVE = "predictive"


@dataclass
class AnalysisResult:
    """分析结果"""
    product_id: str
    analysis_type: AnalysisType
    features: Dict[str, Any]
    quality_score: float
    relevance_score: float
    price_analysis: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    metadata: Dict[str, Any]


class ProductAnalyzer:
    """
    产品分析器类
    
    负责对产品数据进行多维度分析和特征提取。
    提供质量评估、价格分析和相关性计算等功能。
    """
    
    def __init__(self):
        """初始化产品分析器"""
        self.japanese_processor = JapaneseProcessor()
        self.price_normalizer = PriceNormalizer()
        self.feature_extractors = self._initialize_extractors()
        self.quality_metrics = self._initialize_quality_metrics()
        self.market_data = {}
        
        logger.info("ProductAnalyzer initialized")
    
    async def analyze_product(
        self,
        product: ProductData,
        query: Optional[ParsedQuery] = None,
        analysis_type: AnalysisType = AnalysisType.BASIC
    ) -> AnalysisResult:
        """
        分析产品
        
        Args:
            product: 产品数据
            query: 查询上下文
            analysis_type: 分析类型
            
        Returns:
            AnalysisResult: 分析结果
        """
        try:
            # 1. 特征提取
            features = await self._extract_features(product)
            
            # 2. 质量评估
            quality_score = await self._assess_quality(product, features)
            
            # 3. 相关性分析
            relevance_score = await self._calculate_relevance(product, query) if query else 0.5
            
            # 4. 价格分析
            price_analysis = await self._analyze_price(product, features)
            
            # 5. 风险评估
            risk_assessment = await self._assess_risks(product, features)
            
            # 6. 构建结果
            result = AnalysisResult(
                product_id=product.url,  # 使用URL作为ID
                analysis_type=analysis_type,
                features=features,
                quality_score=quality_score,
                relevance_score=relevance_score,
                price_analysis=price_analysis,
                risk_assessment=risk_assessment,
                metadata={
                    "analysis_timestamp": datetime.now().isoformat(),
                    "analyzer_version": "1.0.0",
                    "query_keywords": query.keywords if query else []
                }
            )
            
            logger.debug(f"产品分析完成: {product.title[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"产品分析失败: {e}")
            raise
    
    async def _extract_features(self, product: ProductData) -> Dict[str, Any]:
        """
        提取产品特征
        
        Args:
            product: 产品数据
            
        Returns:
            Dict[str, Any]: 特征字典
        """
        features = {}
        
        # 文本特征
        features.update(await self._extract_text_features(product))
        
        # 价格特征
        features.update(await self._extract_price_features(product))
        
        # 卖家特征
        features.update(await self._extract_seller_features(product))
        
        # 图片特征
        features.update(await self._extract_image_features(product))
        
        # 时间特征
        features.update(await self._extract_temporal_features(product))
        
        return features
    
    async def _extract_text_features(self, product: ProductData) -> Dict[str, Any]:
        """提取文本特征"""
        features = {}
        
        # 标题特征
        if product.title:
            title_processed = await self.japanese_processor.process(product.title)
            features.update({
                "title_length": len(product.title),
                "title_word_count": len(title_processed.tokens),
                "title_has_brand": await self._detect_brand_in_text(product.title),
                "title_has_condition": await self._detect_condition_in_text(product.title),
                "title_has_price": await self._detect_price_in_text(product.title),
                "title_sentiment": await self._analyze_sentiment(product.title)
            })
        
        # 描述特征
        if product.description:
            desc_processed = await self.japanese_processor.process(product.description)
            features.update({
                "description_length": len(product.description),
                "description_word_count": len(desc_processed.tokens),
                "description_detail_level": await self._assess_description_detail(product.description),
                "description_has_flaws": await self._detect_flaws_in_text(product.description),
                "description_quality": await self._assess_text_quality(product.description)
            })
        
        return features
    
    async def _extract_price_features(self, product: ProductData) -> Dict[str, Any]:
        """提取价格特征"""
        features = {}
        
        if product.price:
            # 价格基本特征
            features.update({
                "price_value": product.price,
                "price_range": await self._categorize_price_range(product.price),
                "price_digits": len(str(int(product.price))),
                "price_ends_with_zero": product.price % 10 == 0,
                "price_is_round": product.price % 100 == 0
            })
            
            # 价格合理性
            if product.category:
                market_price = await self._get_market_price(product.category)
                if market_price:
                    features.update({
                        "price_vs_market": product.price / market_price,
                        "price_is_below_market": product.price < market_price * 0.8,
                        "price_is_above_market": product.price > market_price * 1.2
                    })
        
        return features
    
    async def _extract_seller_features(self, product: ProductData) -> Dict[str, Any]:
        """提取卖家特征"""
        features = {}
        
        if product.seller_name:
            features.update({
                "seller_name_length": len(product.seller_name),
                "seller_name_type": await self._categorize_seller_name(product.seller_name)
            })
        
        if product.seller_rating:
            features.update({
                "seller_rating_value": product.seller_rating,
                "seller_rating_high": product.seller_rating >= 4.5,
                "seller_rating_low": product.seller_rating < 3.0,
                "seller_is_reliable": product.seller_rating >= 4.0
            })
        
        return features
    
    async def _extract_image_features(self, product: ProductData) -> Dict[str, Any]:
        """提取图片特征"""
        features = {}
        
        if product.images:
            features.update({
                "image_count": len(product.images),
                "has_multiple_images": len(product.images) > 1,
                "image_urls_quality": await self._assess_image_urls_quality(product.images)
            })
        else:
            features.update({
                "image_count": 0,
                "has_multiple_images": False,
                "image_urls_quality": 0.0
            })
        
        return features
    
    async def _extract_temporal_features(self, product: ProductData) -> Dict[str, Any]:
        """提取时间特征"""
        features = {}
        
        if product.scraped_at:
            features.update({
                "scraped_timestamp": product.scraped_at.timestamp(),
                "scraped_hour": product.scraped_at.hour,
                "scraped_day_of_week": product.scraped_at.weekday(),
                "is_scraped_recently": (datetime.now() - product.scraped_at).total_seconds() < 3600
            })
        
        return features
    
    async def _assess_quality(self, product: ProductData, features: Dict[str, Any]) -> float:
        """
        评估产品质量
        
        Args:
            product: 产品数据
            features: 特征字典
            
        Returns:
            float: 质量评分 (0-1)
        """
        quality_factors = []
        
        # 信息完整性
        completeness_score = await self._assess_information_completeness(product)
        quality_factors.append(("completeness", completeness_score, 0.3))
        
        # 描述质量
        description_score = features.get("description_quality", 0.5)
        quality_factors.append(("description", description_score, 0.2))
        
        # 图片质量
        image_score = features.get("image_urls_quality", 0.5)
        quality_factors.append(("images", image_score, 0.2))
        
        # 卖家信誉
        seller_score = await self._assess_seller_quality(product)
        quality_factors.append(("seller", seller_score, 0.2))
        
        # 价格合理性
        price_score = await self._assess_price_reasonableness(product)
        quality_factors.append(("price", price_score, 0.1))
        
        # 加权平均
        weighted_score = sum(score * weight for _, score, weight in quality_factors)
        
        return max(0.0, min(1.0, weighted_score))
    
    async def _calculate_relevance(self, product: ProductData, query: ParsedQuery) -> float:
        """
        计算相关性
        
        Args:
            product: 产品数据
            query: 查询对象
            
        Returns:
            float: 相关性评分 (0-1)
        """
        if not query.keywords:
            return 0.5
        
        relevance_factors = []
        
        # 标题匹配
        title_match = await self._calculate_text_match(product.title, query.keywords)
        relevance_factors.append(("title", title_match, 0.4))
        
        # 描述匹配
        desc_match = await self._calculate_text_match(product.description, query.keywords)
        relevance_factors.append(("description", desc_match, 0.3))
        
        # 类别匹配
        category_match = await self._calculate_category_match(product.category, query.category)
        relevance_factors.append(("category", category_match, 0.2))
        
        # 价格匹配
        price_match = await self._calculate_price_match(product.price, query.price_min, query.price_max)
        relevance_factors.append(("price", price_match, 0.1))
        
        # 加权平均
        weighted_score = sum(score * weight for _, score, weight in relevance_factors)
        
        return max(0.0, min(1.0, weighted_score))
    
    async def _analyze_price(self, product: ProductData, features: Dict[str, Any]) -> Dict[str, Any]:
        """分析价格"""
        if not product.price:
            return {"error": "无价格信息"}
        
        return {
            "price_value": product.price,
            "price_range": features.get("price_range", "unknown"),
            "price_competitiveness": await self._assess_price_competitiveness(product),
            "price_trend": await self._analyze_price_trend(product),
            "value_proposition": await self._assess_value_proposition(product)
        }
    
    async def _assess_risks(self, product: ProductData, features: Dict[str, Any]) -> Dict[str, Any]:
        """评估风险"""
        risks = {}
        
        # 卖家风险
        risks["seller_risk"] = await self._assess_seller_risk(product)
        
        # 价格风险
        risks["price_risk"] = await self._assess_price_risk(product)
        
        # 描述风险
        risks["description_risk"] = await self._assess_description_risk(product)
        
        # 整体风险
        risks["overall_risk"] = await self._calculate_overall_risk(risks)
        
        return risks
    
    # 辅助方法
    async def _detect_brand_in_text(self, text: str) -> bool:
        """检测文本中是否包含品牌"""
        if not text:
            return False
        
        # 常见品牌关键词
        brand_keywords = ["Nike", "Adidas", "Apple", "Sony", "Canon", "Uniqlo", "Zara"]
        
        for keyword in brand_keywords:
            if keyword.lower() in text.lower():
                return True
        
        return False
    
    async def _detect_condition_in_text(self, text: str) -> bool:
        """检测文本中是否包含状态信息"""
        if not text:
            return False
        
        condition_keywords = ["新品", "中古", "美品", "ジャンク", "未使用", "使用感"]
        
        for keyword in condition_keywords:
            if keyword in text:
                return True
        
        return False
    
    async def _detect_price_in_text(self, text: str) -> bool:
        """检测文本中是否包含价格信息"""
        if not text:
            return False
        
        price_pattern = r'[¥￥]\d+|値下げ|価格|円'
        return bool(re.search(price_pattern, text))
    
    async def _analyze_sentiment(self, text: str) -> float:
        """分析文本情感"""
        if not text:
            return 0.5
        
        # 简单的情感分析
        positive_words = ["美品", "良好", "綺麗", "新品", "お得", "限定"]
        negative_words = ["汚れ", "傷", "欠品", "ジャンク", "難あり"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count + negative_count == 0:
            return 0.5
        
        return positive_count / (positive_count + negative_count)
    
    async def _assess_description_detail(self, description: str) -> float:
        """评估描述详细程度"""
        if not description:
            return 0.0
        
        # 基于长度和关键信息
        length_score = min(1.0, len(description) / 500)
        
        detail_keywords = ["サイズ", "状態", "使用感", "付属品", "注意", "詳細"]
        detail_score = sum(1 for keyword in detail_keywords if keyword in description) / len(detail_keywords)
        
        return (length_score + detail_score) / 2
    
    async def _detect_flaws_in_text(self, text: str) -> bool:
        """检测文本中是否提到缺陷"""
        if not text:
            return False
        
        flaw_keywords = ["汚れ", "傷", "欠品", "破損", "不具合", "動作不良"]
        
        for keyword in flaw_keywords:
            if keyword in text:
                return True
        
        return False
    
    async def _assess_text_quality(self, text: str) -> float:
        """评估文本质量"""
        if not text:
            return 0.0
        
        # 长度评分
        length_score = min(1.0, len(text) / 200)
        
        # 结构评分（是否有段落、标点等）
        structure_score = 0.5
        if "。" in text or "！" in text or "？" in text:
            structure_score += 0.2
        if "\n" in text:
            structure_score += 0.2
        
        # 信息量评分
        info_keywords = ["サイズ", "状態", "ブランド", "色", "素材"]
        info_score = sum(1 for keyword in info_keywords if keyword in text) / len(info_keywords)
        
        return (length_score + structure_score + info_score) / 3
    
    async def _categorize_price_range(self, price: float) -> str:
        """分类价格范围"""
        if price < 1000:
            return "very_low"
        elif price < 5000:
            return "low"
        elif price < 20000:
            return "medium"
        elif price < 50000:
            return "high"
        else:
            return "very_high"
    
    async def _get_market_price(self, category: str) -> Optional[float]:
        """获取市场价格"""
        # 这里应该从数据库或API获取市场价格
        # 暂时返回模拟数据
        market_prices = {
            "ファッション": 5000,
            "家電・スマホ・カメラ": 15000,
            "本・音楽・ゲーム": 2000,
            "コスメ・香水・美容": 3000
        }
        
        return market_prices.get(category)
    
    async def _categorize_seller_name(self, seller_name: str) -> str:
        """分类卖家名称类型"""
        if not seller_name:
            return "unknown"
        
        # 简单分类
        if len(seller_name) < 5:
            return "short"
        elif any(char.isdigit() for char in seller_name):
            return "alphanumeric"
        else:
            return "text"
    
    async def _assess_image_urls_quality(self, image_urls: List[str]) -> float:
        """评估图片URL质量"""
        if not image_urls:
            return 0.0
        
        quality_score = 0.0
        
        for url in image_urls:
            # 检查URL格式
            if url.startswith("https://"):
                quality_score += 0.3
            elif url.startswith("http://"):
                quality_score += 0.1
            
            # 检查图片格式
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                quality_score += 0.2
        
        return min(1.0, quality_score / len(image_urls))
    
    async def _assess_information_completeness(self, product: ProductData) -> float:
        """评估信息完整性"""
        score = 0.0
        total_weight = 0.0
        
        # 必需信息
        if product.title:
            score += 0.3
        total_weight += 0.3
        
        if product.price:
            score += 0.2
        total_weight += 0.2
        
        # 重要信息
        if product.description:
            score += 0.2
        total_weight += 0.2
        
        if product.images:
            score += 0.1
        total_weight += 0.1
        
        if product.condition:
            score += 0.1
        total_weight += 0.1
        
        # 额外信息
        if product.seller_name:
            score += 0.05
        total_weight += 0.05
        
        if product.seller_rating:
            score += 0.05
        total_weight += 0.05
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def _initialize_extractors(self) -> Dict[str, Any]:
        """初始化特征提取器"""
        return {
            "text_extractor": self._extract_text_features,
            "price_extractor": self._extract_price_features,
            "seller_extractor": self._extract_seller_features,
            "image_extractor": self._extract_image_features
        }
    
    def _initialize_quality_metrics(self) -> Dict[str, float]:
        """初始化质量指标"""
        return {
            "completeness_weight": 0.3,
            "description_weight": 0.2,
            "image_weight": 0.2,
            "seller_weight": 0.2,
            "price_weight": 0.1
        }
    
    def get_info(self) -> Dict[str, Any]:
        """获取分析器信息"""
        return {
            "version": "1.0.0",
            "extractors": list(self.feature_extractors.keys()),
            "quality_metrics": self.quality_metrics,
            "market_data_size": len(self.market_data)
        }
    
    async def _assess_seller_quality(self, product: ProductData) -> float:
        """评估卖家质量"""
        if not product.seller_rating:
            return 0.5
        
        # 基于评分的简单评估
        if product.seller_rating >= 4.5:
            return 1.0
        elif product.seller_rating >= 4.0:
            return 0.8
        elif product.seller_rating >= 3.5:
            return 0.6
        elif product.seller_rating >= 3.0:
            return 0.4
        else:
            return 0.2
    
    async def _assess_price_reasonableness(self, product: ProductData) -> float:
        """评估价格合理性"""
        if not product.price:
            return 0.5
        
        # 基于价格范围的简单评估
        if product.price < 100:
            return 0.3  # 可能过于便宜
        elif product.price < 1000:
            return 0.8
        elif product.price < 10000:
            return 1.0
        elif product.price < 50000:
            return 0.9
        else:
            return 0.7  # 高价商品风险较高
    
    async def _calculate_text_match(self, text: str, keywords: List[str]) -> float:
        """计算文本匹配度"""
        if not text or not keywords:
            return 0.0
        
        text_lower = text.lower()
        matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
        
        return matches / len(keywords)
    
    async def _calculate_category_match(self, product_category: str, query_category: str) -> float:
        """计算类别匹配度"""
        if not product_category or not query_category:
            return 0.5
        
        return 1.0 if product_category == query_category else 0.0
    
    async def _calculate_price_match(self, price: float, min_price: float, max_price: float) -> float:
        """计算价格匹配度"""
        if not price:
            return 0.5
        
        if min_price and price < min_price:
            return 0.0
        
        if max_price and price > max_price:
            return 0.0
        
        return 1.0
    
    async def _assess_price_competitiveness(self, product: ProductData) -> float:
        """评估价格竞争力"""
        if not product.price:
            return 0.5
        
        # 基于价格的简单竞争力评估
        if product.price < 5000:
            return 0.9  # 低价商品竞争力高
        elif product.price < 20000:
            return 0.8
        elif product.price < 50000:
            return 0.6
        else:
            return 0.4  # 高价商品竞争力较低
    
    async def _analyze_price_trend(self, product: ProductData) -> Dict[str, Any]:
        """分析价格趋势"""
        # 简单的价格趋势分析
        return {
            "trend": "stable",
            "confidence": 0.7,
            "recommendation": "当前价格合理"
        }
    
    async def _assess_value_proposition(self, product: ProductData) -> float:
        """评估性价比"""
        if not product.price:
            return 0.5
        
        # 基于价格和质量的性价比评估
        quality_score = 0.5
        
        if product.condition:
            condition_scores = {
                "新品・未使用": 1.0,
                "未使用に近い": 0.9,
                "目立った傷や汚れなし": 0.8,
                "やや傷や汚れあり": 0.6,
                "傷や汚れあり": 0.4,
                "全体的に状態が悪い": 0.2
            }
            quality_score = condition_scores.get(product.condition, 0.5)
        
        # 简单的性价比计算
        if product.price < 1000:
            price_score = 1.0
        elif product.price < 10000:
            price_score = 0.8
        elif product.price < 50000:
            price_score = 0.6
        else:
            price_score = 0.4
        
        return (quality_score + price_score) / 2
    
    async def _assess_seller_risk(self, product: ProductData) -> float:
        """评估卖家风险"""
        if not product.seller_rating:
            return 0.5  # 中等风险
        
        # 评分越高，风险越低
        if product.seller_rating >= 4.5:
            return 0.1  # 低风险
        elif product.seller_rating >= 4.0:
            return 0.2
        elif product.seller_rating >= 3.5:
            return 0.4
        elif product.seller_rating >= 3.0:
            return 0.6
        else:
            return 0.8  # 高风险
    
    async def _assess_price_risk(self, product: ProductData) -> float:
        """评估价格风险"""
        if not product.price:
            return 0.5
        
        # 价格过低或过高都有风险
        if product.price < 100:
            return 0.8  # 过低价格风险
        elif product.price < 1000:
            return 0.2
        elif product.price < 50000:
            return 0.1
        else:
            return 0.6  # 高价商品风险
    
    async def _assess_description_risk(self, product: ProductData) -> float:
        """评估描述风险"""
        if not product.description:
            return 0.7  # 无描述风险较高
        
        # 检查描述中的风险关键词
        risk_keywords = ["ジャンク", "難あり", "汚れ", "傷", "破損", "動作不良"]
        description_lower = product.description.lower()
        
        risk_count = sum(1 for keyword in risk_keywords if keyword in description_lower)
        
        if risk_count == 0:
            return 0.1  # 低风险
        elif risk_count <= 2:
            return 0.4
        else:
            return 0.8  # 高风险
    
    async def _calculate_overall_risk(self, risks: Dict[str, float]) -> float:
        """计算整体风险"""
        if not risks:
            return 0.5
        
        # 计算风险的加权平均
        weights = {
            "seller_risk": 0.4,
            "price_risk": 0.3,
            "description_risk": 0.3
        }
        
        total_risk = 0.0
        total_weight = 0.0
        
        for risk_type, risk_value in risks.items():
            weight = weights.get(risk_type, 0.1)
            total_risk += risk_value * weight
            total_weight += weight
        
        return total_risk / total_weight if total_weight > 0 else 0.5


# 其他分析相关的辅助函数（保持向后兼容）
async def _assess_seller_quality(product: ProductData) -> float:
    """评估卖家质量（独立函数，保持向后兼容）"""
    if not product.seller_rating:
        return 0.5
    
    # 基于评分的简单评估
    if product.seller_rating >= 4.5:
        return 1.0
    elif product.seller_rating >= 4.0:
        return 0.8
    elif product.seller_rating >= 3.5:
        return 0.6
    elif product.seller_rating >= 3.0:
        return 0.4
    else:
        return 0.2


async def _assess_price_reasonableness(product: ProductData) -> float:
    """评估价格合理性（独立函数，保持向后兼容）"""
    if not product.price:
        return 0.5
    
    # 基于价格范围的简单评估
    if product.price < 100:
        return 0.3  # 可能过于便宜
    elif product.price < 1000:
        return 0.8
    elif product.price < 10000:
        return 1.0
    elif product.price < 50000:
        return 0.9
    else:
        return 0.7  # 高价商品风险较高


async def _calculate_text_match(text: str, keywords: List[str]) -> float:
    """计算文本匹配度（独立函数，保持向后兼容）"""
    if not text or not keywords:
        return 0.0
    
    text_lower = text.lower()
    matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
    
    return matches / len(keywords)


async def _calculate_category_match(product_category: str, query_category: str) -> float:
    """计算类别匹配度（独立函数，保持向后兼容）"""
    if not product_category or not query_category:
        return 0.5
    
    return 1.0 if product_category == query_category else 0.0


async def _calculate_price_match(price: float, min_price: float, max_price: float) -> float:
    """计算价格匹配度（独立函数，保持向后兼容）"""
    if not price:
        return 0.5
    
    if min_price and price < min_price:
        return 0.0
    
    if max_price and price > max_price:
        return 0.0
    
    return 1.0