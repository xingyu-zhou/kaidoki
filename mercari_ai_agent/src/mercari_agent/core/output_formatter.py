"""
输出格式化器模块

该模块负责将推荐结果格式化为用户友好的Markdown输出。
支持多种输出格式和样式，提供专业的购物建议报告。

主要功能：
- 生成结构化的Markdown表格
- 透明化推理过程展示
- 多语言支持（日语/中文）
- 可定制的输出模板

Author: Mercari AI Agent Team
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json

from ..models.recommendation import RecommendationResult, Recommendation
from ..models.product import ProductData
from ..models.query import ParsedQuery
from ..utils.japanese_processor import JapaneseProcessor
from ..utils.price_normalizer import PriceNormalizer
from ..utils.logger import get_logger
from ..config.settings import settings

logger = get_logger(__name__)


class OutputFormat(Enum):
    """输出格式枚举"""
    MARKDOWN_TABLE = "markdown_table"      # Markdown表格
    DETAILED_REPORT = "detailed_report"    # 详细报告
    SIMPLE_LIST = "simple_list"           # 简单列表
    JSON_EXPORT = "json_export"           # JSON导出


class OutputLanguage(Enum):
    """输出语言枚举"""
    JAPANESE = "ja"     # 日语
    CHINESE = "zh"      # 中文
    ENGLISH = "en"      # 英语


@dataclass
class FormattedOutput:
    """格式化输出结果"""
    content: str
    format: OutputFormat
    language: OutputLanguage
    metadata: Dict[str, Any]


class OutputFormatter:
    """
    输出格式化器类
    
    负责将推荐结果转换为用户友好的格式。
    支持多种输出格式和自定义模板。
    """
    
    def __init__(self):
        """初始化输出格式化器"""
        self.japanese_processor = JapaneseProcessor()
        self.price_normalizer = PriceNormalizer()
        self.templates = self._load_templates()
        self.i18n = self._load_i18n()
        
        logger.info("OutputFormatter initialized")
    
    async def format(
        self,
        result: RecommendationResult,
        query: ParsedQuery,
        output_format: OutputFormat = OutputFormat.MARKDOWN_TABLE,
        language: OutputLanguage = OutputLanguage.CHINESE
    ) -> FormattedOutput:
        """
        格式化推荐结果
        
        Args:
            result: 推荐结果
            query: 原始查询
            output_format: 输出格式
            language: 输出语言
            
        Returns:
            FormattedOutput: 格式化输出
            
        Raises:
            ValueError: 输入参数错误
            FormattingError: 格式化失败
        """
        if not result.recommendations:
            raise ValueError("推荐结果为空")
        
        try:
            # 选择格式化方法
            if output_format == OutputFormat.MARKDOWN_TABLE:
                content = await self._format_markdown_table(result, query, language)
            elif output_format == OutputFormat.DETAILED_REPORT:
                content = await self._format_detailed_report(result, query, language)
            elif output_format == OutputFormat.SIMPLE_LIST:
                content = await self._format_simple_list(result, query, language)
            elif output_format == OutputFormat.JSON_EXPORT:
                content = await self._format_json_export(result, query, language)
            else:
                raise ValueError(f"不支持的输出格式: {output_format}")
            
            # 构建输出结果
            formatted_output = FormattedOutput(
                content=content,
                format=output_format,
                language=language,
                metadata={
                    "query": query.original_query,
                    "total_results": len(result.recommendations),
                    "processing_time": result.processing_time,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"输出格式化完成: {output_format.value}, {language.value}")
            return formatted_output
            
        except Exception as e:
            logger.error(f"输出格式化失败: {e}")
            raise
    
    async def _format_markdown_table(
        self,
        result: RecommendationResult,
        query: ParsedQuery,
        language: OutputLanguage
    ) -> str:
        """
        格式化为Markdown表格
        
        Args:
            result: 推荐结果
            query: 原始查询
            language: 输出语言
            
        Returns:
            str: Markdown表格内容
        """
        t = self.i18n[language.value]
        
        # 构建表格标题
        content = [
            f"# {t['title']}",
            f"**{t['query']}**: {query.original_query}",
            f"**{t['strategy']}**: {t['strategies'][result.strategy_used.value]}",
            f"**{t['total_analyzed']}**: {result.total_analyzed}",
            f"**{t['processing_time']}**: {result.processing_time:.2f}s",
            "",
            "## " + t['recommendations'],
            ""
        ]
        
        # 构建表格头部
        headers = [
            t['rank'],
            t['product_name'],
            t['price'],
            t['condition'],
            t['seller_rating'],
            t['recommendation_score'],
            t['confidence'],
            t['reasons']
        ]
        
        content.append("| " + " | ".join(headers) + " |")
        content.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # 构建表格内容
        for rec in result.recommendations:
            row = [
                str(rec.rank),
                self._truncate_text(rec.product.title, 30),
                self._format_price(rec.product.price),
                rec.product.condition or t['unknown'],
                self._format_rating(rec.product.seller_rating),
                f"{rec.score:.2f}",
                f"{rec.confidence:.1%}",
                self._format_reasons(rec.reasons, language)
            ]
            content.append("| " + " | ".join(row) + " |")
        
        # 添加购买建议
        content.extend([
            "",
            "## " + t['purchase_advice'],
            ""
        ])
        
        for i, rec in enumerate(result.recommendations[:5]):  # 只显示前5个
            content.append(f"### {t['rank']} {i+1}: {rec.product.title}")
            content.append(f"**{t['price']}**: {self._format_price(rec.product.price)}")
            content.append(f"**{t['advice']}**: {rec.purchase_advice}")
            content.append("")
        
        return "\n".join(content)
    
    async def _format_detailed_report(
        self,
        result: RecommendationResult,
        query: ParsedQuery,
        language: OutputLanguage
    ) -> str:
        """
        格式化为详细报告
        
        Args:
            result: 推荐结果
            query: 原始查询
            language: 输出语言
            
        Returns:
            str: 详细报告内容
        """
        t = self.i18n[language.value]
        
        content = [
            f"# {t['detailed_report_title']}",
            "",
            f"## {t['query_analysis']}",
            f"- **{t['original_query']}**: {query.original_query}",
            f"- **{t['keywords']}**: {', '.join(query.keywords)}",
            f"- **{t['category']}**: {query.category or t['not_specified']}",
            f"- **{t['price_range']}**: {self._format_price_range(query.price_min, query.price_max)}",
            f"- **{t['condition']}**: {query.condition or t['not_specified']}",
            "",
            f"## {t['analysis_summary']}",
            f"- **{t['total_analyzed']}**: {result.total_analyzed}",
            f"- **{t['strategy_used']}**: {t['strategies'][result.strategy_used.value]}",
            f"- **{t['processing_time']}**: {result.processing_time:.2f}s",
            "",
            f"## {t['top_recommendations']}",
            ""
        ]
        
        # 详细推荐内容
        for rec in result.recommendations:
            content.extend([
                f"### {t['rank']} {rec.rank}: {rec.product.title}",
                "",
                f"**{t['basic_info']}**:",
                f"- {t['price']}: {self._format_price(rec.product.price)}",
                f"- {t['condition']}: {rec.product.condition or t['unknown']}",
                f"- {t['seller_rating']}: {self._format_rating(rec.product.seller_rating)}",
                f"- {t['recommendation_score']}: {rec.score:.2f}",
                f"- {t['confidence']}: {rec.confidence:.1%}",
                "",
                f"**{t['recommendation_reasons']}**:",
            ])
            
            for reason in rec.reasons:
                content.append(f"- {reason.description} ({t['importance']}: {reason.importance:.1f})")
            
            content.extend([
                "",
                f"**{t['purchase_advice']}**: {rec.purchase_advice}",
                "",
                f"**{t['product_link']}**: {rec.product.url}",
                "",
                "---",
                ""
            ])
        
        return "\n".join(content)
    
    async def _format_simple_list(
        self,
        result: RecommendationResult,
        query: ParsedQuery,
        language: OutputLanguage
    ) -> str:
        """
        格式化为简单列表
        
        Args:
            result: 推荐结果
            query: 原始查询
            language: 输出语言
            
        Returns:
            str: 简单列表内容
        """
        t = self.i18n[language.value]
        
        content = [
            f"# {t['search_results']}",
            f"{t['query']}: {query.original_query}",
            ""
        ]
        
        for rec in result.recommendations:
            content.extend([
                f"{rec.rank}. **{rec.product.title}**",
                f"   {t['price']}: {self._format_price(rec.product.price)}",
                f"   {t['condition']}: {rec.product.condition or t['unknown']}",
                f"   {t['score']}: {rec.score:.1f} ({rec.confidence:.1%})",
                ""
            ])
        
        return "\n".join(content)
    
    async def _format_json_export(
        self,
        result: RecommendationResult,
        query: ParsedQuery,
        language: OutputLanguage
    ) -> str:
        """
        格式化为JSON导出
        
        Args:
            result: 推荐结果
            query: 原始查询
            language: 输出语言
            
        Returns:
            str: JSON格式内容
        """
        export_data = {
            "query": {
                "original": query.original_query,
                "keywords": query.keywords,
                "category": query.category,
                "price_range": {
                    "min": query.price_min,
                    "max": query.price_max
                },
                "condition": query.condition
            },
            "result": {
                "total_analyzed": result.total_analyzed,
                "strategy_used": result.strategy_used.value,
                "processing_time": result.processing_time,
                "recommendations": []
            }
        }
        
        for rec in result.recommendations:
            rec_data = {
                "rank": rec.rank,
                "product": {
                    "title": rec.product.title,
                    "price": rec.product.price,
                    "condition": rec.product.condition,
                    "seller_rating": rec.product.seller_rating,
                    "url": rec.product.url
                },
                "score": rec.score,
                "confidence": rec.confidence,
                "reasons": [
                    {
                        "type": reason.type,
                        "description": reason.description,
                        "importance": reason.importance
                    }
                    for reason in rec.reasons
                ],
                "purchase_advice": rec.purchase_advice
            }
            export_data["result"]["recommendations"].append(rec_data)
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        截断文本
        
        Args:
            text: 原始文本
            max_length: 最大长度
            
        Returns:
            str: 截断后的文本
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length-3] + "..."
    
    def _format_price(self, price: Optional[float]) -> str:
        """
        格式化价格
        
        Args:
            price: 价格
            
        Returns:
            str: 格式化后的价格
        """
        if price is None:
            return "N/A"
        
        return f"¥{price:,.0f}"
    
    def _format_price_range(self, min_price: Optional[float], max_price: Optional[float]) -> str:
        """
        格式化价格范围
        
        Args:
            min_price: 最低价格
            max_price: 最高价格
            
        Returns:
            str: 格式化后的价格范围
        """
        if min_price is None and max_price is None:
            return "未指定"
        elif min_price is None:
            return f"≤ {self._format_price(max_price)}"
        elif max_price is None:
            return f"≥ {self._format_price(min_price)}"
        else:
            return f"{self._format_price(min_price)} - {self._format_price(max_price)}"
    
    def _format_rating(self, rating: Optional[float]) -> str:
        """
        格式化评分
        
        Args:
            rating: 评分
            
        Returns:
            str: 格式化后的评分
        """
        if rating is None:
            return "N/A"
        
        return f"{rating:.1f}★"
    
    def _format_reasons(self, reasons: List, language: OutputLanguage) -> str:
        """
        格式化推荐理由
        
        Args:
            reasons: 推荐理由列表
            language: 输出语言
            
        Returns:
            str: 格式化后的理由
        """
        if not reasons:
            return "无"
        
        # 只显示重要性最高的理由
        top_reason = max(reasons, key=lambda r: r.importance)
        return self._truncate_text(top_reason.description, 40)
    
    def _load_templates(self) -> Dict[str, str]:
        """
        加载输出模板
        
        Returns:
            Dict[str, str]: 模板字典
        """
        return {
            "markdown_table": """
# Mercari智能购物推荐

**查询**: {query}
**策略**: {strategy}
**分析商品数**: {total_analyzed}
**处理时间**: {processing_time}s

## 推荐结果

| 排名 | 商品名称 | 价格 | 状态 | 卖家评分 | 推荐分数 | 置信度 | 理由 |
|------|----------|------|------|----------|----------|--------|------|
{recommendations}

## 购买建议

{purchase_advice}
""",
            "detailed_report": """
# Mercari详细购物报告

## 查询分析
- **原始查询**: {original_query}
- **关键词**: {keywords}
- **类别**: {category}
- **价格范围**: {price_range}
- **状态**: {condition}

## 分析总结
- **分析商品数**: {total_analyzed}
- **使用策略**: {strategy_used}
- **处理时间**: {processing_time}s

## 详细推荐

{detailed_recommendations}
"""
        }
    
    def _load_i18n(self) -> Dict[str, Dict[str, str]]:
        """
        加载国际化文本
        
        Returns:
            Dict[str, Dict[str, str]]: 国际化文本字典
        """
        return {
            "zh": {
                "title": "Mercari智能购物推荐",
                "query": "查询",
                "strategy": "策略",
                "total_analyzed": "分析商品数",
                "processing_time": "处理时间",
                "recommendations": "推荐结果",
                "rank": "排名",
                "product_name": "商品名称",
                "price": "价格",
                "condition": "状态",
                "seller_rating": "卖家评分",
                "recommendation_score": "推荐分数",
                "confidence": "置信度",
                "reasons": "理由",
                "purchase_advice": "购买建议",
                "advice": "建议",
                "unknown": "未知",
                "not_specified": "未指定",
                "detailed_report_title": "Mercari详细购物报告",
                "query_analysis": "查询分析",
                "original_query": "原始查询",
                "keywords": "关键词",
                "category": "类别",
                "price_range": "价格范围",
                "analysis_summary": "分析总结",
                "strategy_used": "使用策略",
                "top_recommendations": "推荐结果",
                "basic_info": "基本信息",
                "recommendation_reasons": "推荐理由",
                "importance": "重要性",
                "product_link": "商品链接",
                "search_results": "搜索结果",
                "score": "分数",
                "strategies": {
                    "price_oriented": "价格导向",
                    "quality_oriented": "质量导向",
                    "balanced": "平衡策略",
                    "trending": "趋势导向"
                }
            },
            "ja": {
                "title": "Mercari スマートショッピング推奨",
                "query": "クエリ",
                "strategy": "戦略",
                "total_analyzed": "分析商品数",
                "processing_time": "処理時間",
                "recommendations": "推奨結果",
                "rank": "ランク",
                "product_name": "商品名",
                "price": "価格",
                "condition": "状態",
                "seller_rating": "出品者評価",
                "recommendation_score": "推奨スコア",
                "confidence": "信頼度",
                "reasons": "理由",
                "purchase_advice": "購入アドバイス",
                "advice": "アドバイス",
                "unknown": "不明",
                "not_specified": "指定なし",
                "strategies": {
                    "price_oriented": "価格重視",
                    "quality_oriented": "品質重視",
                    "balanced": "バランス型",
                    "trending": "トレンド重視"
                }
            }
        }