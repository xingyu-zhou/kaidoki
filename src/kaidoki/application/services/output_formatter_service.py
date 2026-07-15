"""
输出格式化服务

按 output_format **只**生成所选的一种格式:
- markdown_table / simple_list / json_export: 代码确定性生成(保证只出所选格式、JSON 合法)
- detailed_report: 用 LLM 生成带推荐理由与购买建议的报告,LLM 不可用/失败时回退确定性文本
"""

import json
import time
from typing import Any, List, Optional
from dataclasses import dataclass

from ...domain.entities.query import QueryEntity
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

SUPPORTED_FORMATS = ("markdown_table", "detailed_report", "simple_list", "json_export")


@dataclass
class FormattedOutput:
    """格式化输出"""
    content: str
    format_type: str
    language: str
    processing_time: float


class OutputFormatterService:
    """输出格式化服务:确定性结构格式 + LLM 详细报告"""

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
        """格式化输出:严格只产出 output_format 指定的一种格式。"""
        start_time = time.time()

        if output_format not in SUPPORTED_FORMATS:
            logger.warning(f"未知输出格式 '{output_format}',回退 markdown_table")
            output_format = "markdown_table"

        products = list(getattr(data, "recommendations", None) or [])

        try:
            if not products:
                content = "没有找到符合条件的商品。"
            elif output_format == "detailed_report":
                content = await self._detailed_report(data, query, products, language)
            else:
                content = self._render(products, output_format)
        except Exception as e:
            logger.error(f"格式化失败,回退简单列表: {e}")
            content = self._render(products, "simple_list") if products else "没有找到符合条件的商品。"

        return FormattedOutput(
            content=content,
            format_type=output_format,
            language=language,
            processing_time=time.time() - start_time,
        )

    # ------------------------------------------------------------------ #
    # 确定性渲染(不依赖 LLM)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _product_dicts(products) -> List[dict]:
        out = []
        for i, p in enumerate(products, 1):
            out.append({
                "rank": i,
                "title": p.title,
                "price": p.price,
                "formatted_price": p.formatted_price,
                "condition": p.condition or "不明",
                "seller_name": p.seller_name or "不明",
                "url": p.url,
            })
        return out

    def _render(self, products, output_format: str) -> str:
        """markdown_table / simple_list / json_export 的确定性生成。"""
        if output_format == "json_export":
            return json.dumps(self._product_dicts(products), ensure_ascii=False, indent=2)

        if output_format == "simple_list":
            lines = [
                f"{i}. {p.title} - {p.formatted_price} - {p.condition or '不明'}"
                for i, p in enumerate(products, 1)
            ]
            return "\n".join(lines)

        # markdown_table(默认)
        lines = ["| 排名 | 商品 | 价格 | 状态 | 链接 |",
                 "|------|------|------|------|------|"]
        for i, p in enumerate(products, 1):
            link = f"[查看商品]({p.url})" if p.url else "-"
            title = (p.title or "").replace("|", "\\|")
            lines.append(f"| {i} | {title} | {p.formatted_price} | {p.condition or '不明'} | {link} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # 详细报告(优先 LLM,失败回退确定性文本)
    # ------------------------------------------------------------------ #
    async def _detailed_report(self, data, query, products, language: str) -> str:
        reasoning: Optional[str] = getattr(data, "reasoning", None)

        if self.llm_service:
            try:
                lang_name = {"zh": "简体中文", "ja": "日本語", "en": "English"}.get(language, "简体中文")
                prompt = f"""作为专业购物助手,请用{lang_name}生成一份**详细推荐报告**。
只输出报告正文,不要输出表格、列表或 JSON,不要任何额外说明。

用户查询: {query.original_query}
推荐策略: {getattr(data, 'strategy_used', 'balanced')}
已有推荐理由: {reasoning or '无'}

推荐商品(已按推荐顺序排列):
{self._product_dicts(products)}

报告应包含:整体概述、对每个商品的亮点与性价比点评、明确的购买建议,并提醒下单前查看成色描述与卖家信誉。语调专业而友好。"""
                resp = await self.llm_service.generate_response(prompt)
                if resp and getattr(resp, "content", "") and resp.content.strip():
                    return resp.content.strip()
            except Exception as e:
                logger.warning(f"LLM 详细报告生成失败,回退确定性报告: {e}")

        # 确定性回退
        lines = [f"# 「{query.original_query}」推荐报告", ""]
        if reasoning:
            lines += [f"**推荐理由**: {reasoning}", ""]
        for i, p in enumerate(products, 1):
            lines.append(f"{i}. {p.title} — {p.formatted_price} — 状态: {p.condition or '不明'}")
            if p.url:
                lines.append(f"   链接: {p.url}")
        lines += ["", "提示: 下单前请仔细查看商品成色描述与卖家评价。"]
        return "\n".join(lines)
