"""
输出格式化服务 - 最简版本
"""

import time
from typing import Any
from dataclasses import dataclass

from ...domain.entities.query import QueryEntity
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


@dataclass
class FormattedOutput:
    """格式化输出"""
    content: str
    format_type: str
    language: str
    processing_time: float


class OutputFormatterService:
    """输出格式化服务 - 集成LLM智能格式化"""
    
    def __init__(self, config, llm_service=None):
        self.config = config
        self.llm_service = llm_service
    
    async def format(
        self,
        data: Any,
        query: QueryEntity,
        output_format: str = "markdown_table",
        language: str = "zh"
    ) -> FormattedOutput:
        """格式化输出 - 集成LLM智能格式化"""
        start_time = time.time()
        
        # 🔧 关键修复：使用LLM进行智能格式化
        try:
            if self.llm_service and hasattr(data, 'recommendations') and data.recommendations:
                # 构建产品数据供LLM格式化
                products = data.recommendations
                product_data = []
                for i, product in enumerate(products):
                    product_info = {
                        "rank": i + 1,
                        "title": product.title,
                        "price": product.price,
                        "formatted_price": product.formatted_price if hasattr(product, 'formatted_price') else f"¥{product.price:,}" if product.price else "价格不明",
                        "condition": product.condition or "未知",
                        "seller_name": product.seller_name or "未知",
                        "url": product.url if hasattr(product, 'url') else None
                    }
                    product_data.append(product_info)
                
                # 构建LLM提示词进行智能格式化
                llm_prompt = f"""
作为智能购物助手，请将以下商品推荐结果格式化为{output_format}格式，使用{language}语言：

用户查询: {query.original_query}
推荐策略: {data.strategy_used if hasattr(data, 'strategy_used') else 'balanced'}
分析商品数: {data.total_analyzed if hasattr(data, 'total_analyzed') else len(products)}
处理时间: {data.processing_time if hasattr(data, 'processing_time') else 0:.2f}秒

推荐商品:
{product_data}

请根据格式要求输出：
- markdown_table: 生成Markdown表格，包含排名、商品名、价格、状态、卖家等信息
- detailed_report: 生成详细报告，包含推荐理由和购买建议
- simple_list: 生成简单列表
- json_export: 生成JSON格式

要求：
1. 保持专业的购物助手语调
2. 突出性价比和推荐理由
3. 包含实用的购买建议
4. 如果是中文输出，使用简体中文

请直接输出格式化结果，不要包含额外说明。
"""
                
                # 调用LLM服务
                logger.info(f"使用LLM服务进行智能格式化，格式: {output_format}, 语言: {language}")
                llm_response = await self.llm_service.generate_response(llm_prompt)
                logger.info(f"LLM格式化响应长度: {len(llm_response.content)}")
                
                # 使用LLM响应作为格式化结果
                content = llm_response.content
                
            else:
                logger.info("LLM服务不可用或无推荐数据，使用备用格式化逻辑")
                content = await self._fallback_format(data, output_format)
        
        except Exception as e:
            logger.error(f"LLM格式化服务调用失败，使用备用逻辑: {e}")
            content = await self._fallback_format(data, output_format)
        
        processing_time = time.time() - start_time
        
        return FormattedOutput(
            content=content,
            format_type=output_format,
            language=language,
            processing_time=processing_time
        )
    
    async def _fallback_format(self, data: Any, output_format: str) -> str:
        """备用格式化逻辑"""
        if hasattr(data, 'recommendations'):
            # 推荐结果格式化
            products = data.recommendations
            return self._format_products(products, output_format)
        else:
            # 其他数据直接转字符串
            return str(data)
    
    def _format_products(self, products, format_type: str) -> str:
        """格式化产品列表"""
        if not products:
            return "没有找到符合条件的商品。"
        
        if format_type == "markdown_table":
            lines = ["| 商品名称 | 价格 | 状态 | 卖家 |"]
            lines.append("|----------|------|------|------|")
            
            for product in products:
                price_str = product.formatted_price if product.price else "价格不明"
                condition = product.condition or "未知"
                seller = product.seller_name or "未知"
                
                lines.append(f"| {product.title} | {price_str} | {condition} | {seller} |")
            
            return "\n".join(lines)
        
        elif format_type == "simple_list":
            lines = []
            for i, product in enumerate(products, 1):
                price_str = product.formatted_price if product.price else "价格不明"
                lines.append(f"{i}. {product.title} - {price_str}")
            
            return "\n".join(lines)
        
        else:
            # 默认格式
            return f"找到 {len(products)} 个商品"