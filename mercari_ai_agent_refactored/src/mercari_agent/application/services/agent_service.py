"""
AgentService - 原生工具调用 agent 循环

与现有写死流水线（parse→scrape→rerank）不同：这里给 LLM 注册工具 schema，
让模型自主决定调用哪些工具、调几次。循环逻辑：

    chat_with_tools(messages, tools)
      ├─ 若返回 tool_calls：逐个通过 registry 派发执行，
      │   把每个结果作为 role:"tool" + 对应 tool_call_id 的消息追加回 messages，再循环
      └─ 若无 tool_calls（最终回答）：返回 content

健壮性：
- 一轮可能多个 tool_calls，全部执行。
- arguments 是 JSON 字符串，解析失败也不崩，把错误回给模型。
- 工具报错把错误字符串回给模型，而不是抛出。
- 迭代上限防失控；达到上限后强制一次 tool_choice="none" 的收尾回答。
- 记录完整 trace（每步调了什么工具、什么参数、返回摘要）。

Author: Mercari AI Agent Team (native tools)
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...infrastructure.llm.llm_service import LLMService
from ...tools.framework.tool_registry import ToolRegistry
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """你是一个会使用工具的 Mercari（日本二手交易平台）购物助手。

你可以调用以下工具来获取真实数据，绝不要凭空编造商品或价格：
- search_mercari：搜索在售商品，看具体有哪些、价格、成色、链接。
- get_price_statistics：获取某关键词的价格行情（最低/最高/中位数/平均），
  用来判断某个价格是不是好价、划不划算。

工作方式：
1. 先想清楚要回答用户的问题需要哪些信息，主动调用工具去查（可以多次、组合调用）。
2. 判断性价比时，建议先用 get_price_statistics 了解行情，再用 search_mercari
   找具体便宜且成色好的商品，对照行情说明为什么划算。
3. 尊重用户预算等约束（如预算上限用 price_max 过滤）。
4. 拿到足够数据后，给出有依据的推荐：列出 2~4 个具体商品（含价格、成色、链接），
   并结合价格行情简要说明推荐理由。用中文回答，简洁清晰。
"""


@dataclass
class TraceStep:
    """一次工具调用的 trace 记录"""
    iteration: int
    tool: str
    arguments: Dict[str, Any]
    ok: bool
    result_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "tool": self.tool,
            "arguments": self.arguments,
            "ok": self.ok,
            "result_summary": self.result_summary,
        }


@dataclass
class AgentResult:
    """agent 运行结果"""
    answer: str
    trace: List[TraceStep] = field(default_factory=list)
    iterations: int = 0
    truncated: bool = False


def _summarize_result(data_str: str, limit: int = 400) -> str:
    """把工具返回压成 trace 里的简短摘要。"""
    try:
        obj = json.loads(data_str)
    except (ValueError, TypeError):
        return data_str[:limit]
    if isinstance(obj, dict):
        if "error" in obj:
            return f"ERROR: {obj['error']}"
        parts = []
        if "count" in obj:
            parts.append(f"count={obj['count']}")
        for k in ("min", "max", "median", "average", "total_found"):
            if k in obj:
                parts.append(f"{k}={obj[k]}")
        prods = obj.get("products")
        if isinstance(prods, list) and prods:
            sample = prods[0]
            parts.append(f"e.g. {sample.get('title', '')[:30]}@¥{sample.get('price')}")
        if parts:
            return ", ".join(parts)
    return data_str[:limit]


class AgentService:
    """原生工具调用 agent。"""

    def __init__(
        self,
        llm_service: LLMService,
        tool_registry: ToolRegistry,
        max_iterations: int = 6,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.llm = llm_service
        self.registry = tool_registry
        self.max_iterations = max(1, int(max_iterations))
        self.system_prompt = system_prompt

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        """把注册的工具转成现代 tools API schema。"""
        return [
            {"type": "function", "function": tool.to_openai_function()}
            for tool in self.registry
        ]

    async def _dispatch(self, name: str, args: Dict[str, Any]) -> tuple:
        """通过 registry 派发执行一个工具。返回 (ok, 可回给模型的字符串)。"""
        tool = self.registry.get_tool(name)
        if tool is None:
            return False, json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        try:
            result = await tool.call(**args)
        except Exception as e:  # noqa: BLE001 —— 工具异常也要回给模型而不是崩
            logger.error(f"工具 {name} 执行异常: {e}")
            return False, json.dumps({"error": f"工具执行异常: {e}"}, ensure_ascii=False)

        if result.is_success():
            return True, json.dumps(result.data, ensure_ascii=False, default=str)
        return False, json.dumps({"error": result.error or "工具执行失败"}, ensure_ascii=False)

    async def run(self, user_query: str) -> AgentResult:
        """跑 agent 循环，返回最终回答 + trace。"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_query},
        ]
        tools = self._tool_schemas()
        trace: List[TraceStep] = []

        for iteration in range(1, self.max_iterations + 1):
            assistant = await self.llm.chat_with_tools(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1200,
            )
            tool_calls = assistant.get("tool_calls") or []
            content = assistant.get("content")

            # 追加 assistant 消息（含 tool_calls，供后续 tool 消息对应）
            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # 无 tool_calls => 最终回答
            if not tool_calls:
                return AgentResult(
                    answer=content or "",
                    trace=trace,
                    iterations=iteration,
                    truncated=False,
                )

            # 逐个执行 tool_calls，结果作为 role:"tool" 消息追加
            for tc in tool_calls:
                call_id = tc.get("id")
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                except (ValueError, TypeError) as e:
                    logger.warning(f"工具 {name} 参数 JSON 解析失败: {raw_args!r}")
                    result_str = json.dumps(
                        {"error": f"参数不是合法 JSON: {e}"}, ensure_ascii=False
                    )
                    trace.append(TraceStep(iteration, name, {"_raw": raw_args}, False,
                                           _summarize_result(result_str)))
                    messages.append({"role": "tool", "tool_call_id": call_id,
                                     "content": result_str})
                    continue

                logger.info(f"[iter {iteration}] LLM 调用工具 {name} args={args}")
                ok, result_str = await self._dispatch(name, args)
                trace.append(TraceStep(iteration, name, args, ok,
                                       _summarize_result(result_str)))
                messages.append({"role": "tool", "tool_call_id": call_id,
                                 "content": result_str})

        # 达到迭代上限：强制一次不带工具的收尾回答
        logger.warning(f"达到迭代上限 {self.max_iterations}，强制收尾")
        final = await self.llm.chat_with_tools(
            messages=messages + [{
                "role": "user",
                "content": "请基于以上已获取的信息直接给出最终推荐，不要再调用工具。",
            }],
            tools=tools,
            tool_choice="none",
            temperature=0.3,
            max_tokens=1200,
        )
        return AgentResult(
            answer=final.get("content") or "",
            trace=trace,
            iterations=self.max_iterations,
            truncated=True,
        )
