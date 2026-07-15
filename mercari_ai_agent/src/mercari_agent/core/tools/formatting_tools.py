"""
格式化工具

该模块包含与数据格式化、输出生成和展示相关的工具实现。
"""

from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
import logging
from datetime import datetime
import json
from dataclasses import asdict

from .base_tool import BaseTool, ToolResult, ToolStatus
from ...models.product import ProductData
from ...models.recommendation import RecommendationResult
from ...core.output_formatter import OutputFormatter
from ...utils.logger import get_logger

if TYPE_CHECKING:
    from ...services.llm_service import LLMService

logger = get_logger(__name__)


class ProductSummaryTool(BaseTool):
    """产品摘要工具"""
    
    def __init__(self, llm_service: 'LLMService'):
        super().__init__(
            name="generate_summary",
            description="生成产品的简洁摘要，包含关键信息和亮点"
        )
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "description": "产品数据列表",
                        "items": {"type": "object"}
                    },
                    "summary_style": {
                        "type": "string",
                        "description": "摘要风格",
                        "enum": ["brief", "detailed", "bullet_points", "narrative"],
                        "default": "brief"
                    },
                    "include_analysis": {
                        "type": "boolean",
                        "description": "是否包含分析信息",
                        "default": false
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "目标受众",
                        "enum": ["general", "expert", "beginner"],
                        "default": "general"
                    }
                },
                "required": ["products"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            products = kwargs["products"]
            summary_style = kwargs.get("summary_style", "brief")
            include_analysis = kwargs.get("include_analysis", False)
            target_audience = kwargs.get("target_audience", "general")
            
            # 生成摘要提示
            summary_prompt = f"""
            为以下产品生成{summary_style}风格的摘要：
            
            产品数据: {json.dumps(products, ensure_ascii=False, indent=2)}
            
            要求：
            - 目标受众: {target_audience}
            - 摘要风格: {summary_style}
            - 包含分析: {include_analysis}
            
            请生成清晰、简洁的日语摘要，突出产品的关键特征和价值点。
            """
            
            # 生成摘要
            summary = await self.llm_service.generate_response(summary_prompt)
            
            # 构建结果
            result_data = {
                "summary": summary,
                "product_count": len(products),
                "summary_style": summary_style,
                "target_audience": target_audience,
                "generated_at": datetime.now().isoformat()
            }
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=result_data,
                metadata={
                    "summary_style": summary_style,
                    "product_count": len(products),
                    "include_analysis": include_analysis
                }
            )
            
        except Exception as e:
            logger.error(f"Product summary generation failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"产品摘要生成失败: {str(e)}"
            )


class ComparisonTableTool(BaseTool):
    """比较表格工具"""
    
    def __init__(self, output_formatter: OutputFormatter):
        super().__init__(
            name="format_comparison_table",
            description="生成产品比较表格，以结构化格式展示多个产品的对比信息"
        )
        self.output_formatter = output_formatter
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "description": "产品数据列表",
                        "items": {"type": "object"}
                    },
                    "comparison_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "比较字段",
                        "default": ["title", "price", "condition", "seller_rating"]
                    },
                    "format_type": {
                        "type": "string",
                        "description": "输出格式",
                        "enum": ["table", "cards", "list"],
                        "default": "table"
                    },
                    "highlight_best": {
                        "type": "boolean",
                        "description": "是否突出显示最佳选项",
                        "default": True
                    }
                },
                "required": ["products"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            products = kwargs["products"]
            comparison_fields = kwargs.get("comparison_fields", 
                                         ["title", "price", "condition", "seller_rating"])
            format_type = kwargs.get("format_type", "table")
            highlight_best = kwargs.get("highlight_best", True)
            
            # 生成比较表格
            if format_type == "table":
                formatted_result = self.output_formatter.format_comparison_table(
                    products, comparison_fields, highlight_best
                )
            elif format_type == "cards":
                formatted_result = self.output_formatter.format_product_cards(
                    products, comparison_fields
                )
            else:  # list
                formatted_result = self.output_formatter.format_product_list(
                    products, comparison_fields
                )
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "formatted_output": formatted_result,
                    "format_type": format_type,
                    "comparison_fields": comparison_fields,
                    "product_count": len(products)
                },
                metadata={
                    "format_type": format_type,
                    "fields_count": len(comparison_fields),
                    "highlight_best": highlight_best
                }
            )
            
        except Exception as e:
            logger.error(f"Comparison table generation failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"比较表格生成失败: {str(e)}"
            )


class RecommendationReportTool(BaseTool):
    """推荐报告工具"""
    
    def __init__(self, llm_service: 'LLMService', output_formatter: OutputFormatter):
        super().__init__(
            name="format_recommendation_report",
            description="生成完整的推荐报告，包含分析、理由和建议"
        )
        self.llm_service = llm_service
        self.output_formatter = output_formatter
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendations": {
                        "type": "array",
                        "description": "推荐数据列表",
                        "items": {"type": "object"}
                    },
                    "user_query": {
                        "type": "string",
                        "description": "用户原始查询"
                    },
                    "analysis_data": {
                        "type": "object",
                        "description": "分析数据",
                        "default": {}
                    },
                    "report_style": {
                        "type": "string",
                        "description": "报告风格",
                        "enum": ["executive", "detailed", "casual"],
                        "default": "detailed"
                    },
                    "include_alternatives": {
                        "type": "boolean",
                        "description": "是否包含替代选项",
                        "default": True
                    }
                },
                "required": ["recommendations", "user_query"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            recommendations = kwargs["recommendations"]
            user_query = kwargs["user_query"]
            analysis_data = kwargs.get("analysis_data", {})
            report_style = kwargs.get("report_style", "detailed")
            include_alternatives = kwargs.get("include_alternatives", True)
            
            # 生成报告提示
            report_prompt = f"""
            基于以下信息生成推荐报告：
            
            用户查询: {user_query}
            推荐结果: {json.dumps(recommendations, ensure_ascii=False, indent=2)}
            分析数据: {json.dumps(analysis_data, ensure_ascii=False, indent=2)}
            
            报告要求：
            - 风格: {report_style}
            - 包含替代选项: {include_alternatives}
            
            请生成结构化的日语报告，包含：
            1. 查询理解和分析
            2. 推荐产品详情
            3. 推荐理由
            4. 购买建议
            {"5. 替代选项" if include_alternatives else ""}
            """
            
            # 生成报告
            report_content = await self.llm_service.generate_response(report_prompt)
            
            # 格式化输出
            formatted_report = self.output_formatter.format_recommendation_report(
                report_content, recommendations, user_query
            )
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "report": formatted_report,
                    "raw_content": report_content,
                    "user_query": user_query,
                    "recommendation_count": len(recommendations),
                    "report_style": report_style
                },
                metadata={
                    "report_style": report_style,
                    "include_alternatives": include_alternatives,
                    "generation_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Recommendation report generation failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"推荐报告生成失败: {str(e)}"
            )


class DataVisualizationTool(BaseTool):
    """数据可视化工具"""
    
    def __init__(self, output_formatter: OutputFormatter):
        super().__init__(
            name="format_data_visualization",
            description="生成数据可视化图表和图形，用于展示价格趋势、分析结果等"
        )
        self.output_formatter = output_formatter
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "要可视化的数据"
                    },
                    "chart_type": {
                        "type": "string",
                        "description": "图表类型",
                        "enum": ["bar", "line", "pie", "scatter", "histogram"],
                        "default": "bar"
                    },
                    "title": {
                        "type": "string",
                        "description": "图表标题"
                    },
                    "x_axis": {
                        "type": "string",
                        "description": "X轴字段"
                    },
                    "y_axis": {
                        "type": "string",
                        "description": "Y轴字段"
                    },
                    "color_scheme": {
                        "type": "string",
                        "description": "颜色方案",
                        "enum": ["default", "modern", "pastel", "vibrant"],
                        "default": "default"
                    }
                },
                "required": ["data", "chart_type"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            data = kwargs["data"]
            chart_type = kwargs["chart_type"]
            title = kwargs.get("title", "数据可视化")
            x_axis = kwargs.get("x_axis")
            y_axis = kwargs.get("y_axis")
            color_scheme = kwargs.get("color_scheme", "default")
            
            # 生成可视化配置
            viz_config = {
                "chart_type": chart_type,
                "title": title,
                "x_axis": x_axis,
                "y_axis": y_axis,
                "color_scheme": color_scheme,
                "data": data
            }
            
            # 生成图表数据
            chart_data = self.output_formatter.format_chart_data(viz_config)
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "chart_data": chart_data,
                    "config": viz_config,
                    "data_points": len(data) if isinstance(data, list) else 1
                },
                metadata={
                    "chart_type": chart_type,
                    "title": title,
                    "color_scheme": color_scheme
                }
            )
            
        except Exception as e:
            logger.error(f"Data visualization failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"数据可视化失败: {str(e)}"
            )


class TextFormattingTool(BaseTool):
    """文本格式化工具"""
    
    def __init__(self, llm_service: 'LLMService'):
        super().__init__(
            name="format_text",
            description="格式化文本输出，支持多种格式和样式"
        )
        self.llm_service = llm_service
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要格式化的内容"
                    },
                    "format_type": {
                        "type": "string",
                        "description": "格式类型",
                        "enum": ["markdown", "html", "plain_text", "json"],
                        "default": "markdown"
                    },
                    "style": {
                        "type": "string",
                        "description": "格式风格",
                        "enum": ["formal", "casual", "technical", "friendly"],
                        "default": "formal"
                    },
                    "add_structure": {
                        "type": "boolean",
                        "description": "是否添加结构化标题和段落",
                        "default": True
                    }
                },
                "required": ["content"]
            }
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            content = kwargs["content"]
            format_type = kwargs.get("format_type", "markdown")
            style = kwargs.get("style", "formal")
            add_structure = kwargs.get("add_structure", True)
            
            # 生成格式化提示
            if add_structure:
                format_prompt = f"""
                将以下内容格式化为{format_type}格式，风格为{style}：
                
                原始内容: {content}
                
                要求：
                - 添加适当的标题和段落结构
                - 使用{format_type}格式语法
                - 保持{style}风格
                - 确保可读性和专业性
                """
            else:
                format_prompt = f"""
                将以下内容转换为{format_type}格式：
                
                原始内容: {content}
                
                保持原有结构，只进行格式转换。
                """
            
            # 生成格式化内容
            formatted_content = await self.llm_service.generate_response(format_prompt)
            
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "formatted_content": formatted_content,
                    "original_content": content,
                    "format_type": format_type,
                    "style": style,
                    "structure_added": add_structure
                },
                metadata={
                    "format_type": format_type,
                    "style": style,
                    "content_length": len(content)
                }
            )
            
        except Exception as e:
            logger.error(f"Text formatting failed: {e}")
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"文本格式化失败: {str(e)}"
            )


class FormattingTools:
    """格式化工具集合"""
    
    def __init__(self, llm_service: 'LLMService', output_formatter: OutputFormatter):
        self.product_summary = ProductSummaryTool(llm_service)
        self.comparison_table = ComparisonTableTool(output_formatter)
        self.recommendation_report = RecommendationReportTool(llm_service, output_formatter)
        self.data_visualization = DataVisualizationTool(output_formatter)
        self.text_formatting = TextFormattingTool(llm_service)
    
    def get_tools(self) -> List[BaseTool]:
        """获取所有格式化工具"""
        return [
            self.product_summary,
            self.comparison_table,
            self.recommendation_report,
            self.data_visualization,
            self.text_formatting
        ]