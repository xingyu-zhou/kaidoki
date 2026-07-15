"""
原生工具调用 agent 循环的确定性单测。

被测对象：AgentService（真正的 native function-calling agent 循环）+ 真实的
Mercari 工具（SearchMercariTool / PriceStatisticsTool，经 build_mercari_tool_registry
注册），后端接一个 **假的 ScraperService**。

铁律（本文件绝不触网 / 绝不启动浏览器 / 绝不调真实 OpenAI）：
  - LLM 用 FakeLLM 替身：脚本化返回带 tool_calls 的 assistant 消息 / 无 tool_calls
    的最终文本，据此断言循环行为、消息顺序、tool_call_id 匹配。
  - ScraperService 用 FakeScraperService 替身：scrape() 直接返回预设 ProductEntity
    列表（或抛异常），不发请求、不开浏览器。

覆盖：
  - 两轮闭环：第 1 轮 LLM 触发工具 → 执行 → role:"tool" 回传 → 第 2 轮拿最终答案。
  - 消息 plumbing：role/顺序、tool_call_id 精确匹配、工具结果为真实工具产出的 JSON。
  - 真·原生：走 assistant.tool_calls 分支（content=None 也能触发工具），而非解析
    prompt / content 里的 JSON；且传给 LLM 的是现代 tools schema。
  - 一轮多个 tool_calls 全部执行。
  - 健壮性：工具抛异常 / 未知工具 / arguments 非法 JSON —— 循环都不崩，把错误回给模型。
  - 迭代上限：安全终止 + 强制一次 tool_choice="none" 收尾。
"""

import copy
import json
import sys
import types
from pathlib import Path

import pytest

# 该包未以 editable 方式安装，测试时把 src 加入 import 路径
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mercari_agent.application.services.agent_service import (  # noqa: E402
    AgentService,
    AgentResult,
    TraceStep,
)
from mercari_agent.tools.mercari_tools import (  # noqa: E402
    build_mercari_tool_registry,
    SearchMercariTool,
    PriceStatisticsTool,
)
from mercari_agent.domain.entities.product import ProductEntity  # noqa: E402


# --------------------------------------------------------------------------- #
# 替身（fakes）：零网络、零浏览器、零真实 OpenAI
# --------------------------------------------------------------------------- #
class FakeScraperService:
    """ScraperService 替身：scrape() 返回预设商品（或抛异常），并记录调用。

    真实工具只读取 result.products 与 result.total_found，用 SimpleNamespace 即可，
    从而让真实的 SearchMercariTool / PriceStatisticsTool 逻辑（排序、过滤 sold、
    压缩字段、统计）在测试里真实执行，但完全不触网。
    """

    def __init__(self, products, total_found=0, raise_exc=None):
        self._products = products
        self._total_found = total_found
        self._raise_exc = raise_exc
        self.scrape_calls = []  # [(query, max_products), ...]

    async def scrape(self, query, max_products=10):
        self.scrape_calls.append((query, max_products))
        if self._raise_exc is not None:
            raise self._raise_exc
        return types.SimpleNamespace(
            products=list(self._products),
            total_found=self._total_found,
        )


class FakeLLM:
    """LLMService 替身：AgentService 只用到 chat_with_tools。

    脚本化：按顺序弹出预置响应；同时把每次收到的 messages / tools / tool_choice
    做快照，供测试断言消息顺序与 plumbing。响应耗尽即断言失败（可捕获意外的无限循环）。
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []  # [{"messages": [...], "tools": [...], "tool_choice": ...}]

    async def chat_with_tools(
        self,
        messages,
        tools,
        tool_choice="auto",
        max_tokens=None,
        temperature=None,
        **kwargs,
    ):
        # 深拷贝快照：messages 列表被 agent 持续 append，必须冻结当次状态
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": copy.deepcopy(tools),
                "tool_choice": tool_choice,
            }
        )
        assert self._responses, "FakeLLM 脚本响应已耗尽（可能是循环失控 / 意外的额外调用）"
        return self._responses.pop(0)


# --------------------------------------------------------------------------- #
# 响应构造器 & 商品夹具
# --------------------------------------------------------------------------- #
def _assistant_tool_call(call_id, name, arguments, content=None):
    """构造一个带单个 tool_call 的 assistant 响应（现代 tools API 结构）。"""
    return {
        "content": content,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
        "model": "fake-model",
        "usage": {},
        "metadata": {},
    }


def _assistant_final(text):
    """构造一个无 tool_calls 的最终回答响应。"""
    return {
        "content": text,
        "tool_calls": [],
        "model": "fake-model",
        "usage": {},
        "metadata": {},
    }


def _products():
    """预设商品：含不同价格与一个已售出商品（用于验证排序 + 过滤 sold）。"""
    return [
        ProductEntity(
            id="m1", title="AirPods Pro A", price=5000,
            condition="目立った傷や汚れなし", url="https://jp.mercari.com/item/m1",
        ),
        ProductEntity(
            id="m2", title="AirPods Pro B 本体", price=600,
            condition="やや傷や汚れあり", url="https://jp.mercari.com/item/m2",
        ),
        ProductEntity(
            id="m3", title="AirPods Pro C", price=8999,
            condition="未使用に近い", url="https://jp.mercari.com/item/m3",
        ),
        ProductEntity(
            id="m4", title="AirPods Pro SOLD", price=2180,
            condition="新品・未使用", url="https://jp.mercari.com/item/m4", sold=True,
        ),
    ]


# --------------------------------------------------------------------------- #
# 1) 两轮闭环：触发工具 → 执行 → 最终答案
# --------------------------------------------------------------------------- #
async def test_agent_runs_tool_then_returns_final_answer():
    scraper = FakeScraperService(_products(), total_found=15000)
    registry = build_mercari_tool_registry(scraper)
    args_json = '{"keyword": "AirPods Pro", "price_max": 10000, "sort": "price_asc", "limit": 5}'
    llm = FakeLLM(
        [
            _assistant_tool_call("call_abc", "search_mercari", args_json, content=None),
            _assistant_final("为你推荐 3 款高性价比 AirPods Pro ..."),
        ]
    )
    agent = AgentService(llm, registry, max_iterations=6)

    result = await agent.run("帮我找性价比高的二手 AirPods Pro，预算 1 万円以内")

    # 最终答案 + 循环元信息
    assert isinstance(result, AgentResult)
    assert result.answer == "为你推荐 3 款高性价比 AirPods Pro ..."
    assert result.iterations == 2
    assert result.truncated is False

    # 工具真的被执行了（原生路径）：scraper 被命中一次，参数从 tool_call JSON 流转到工具再到 scraper
    assert len(scraper.scrape_calls) == 1
    query, max_products = scraper.scrape_calls[0]
    assert query.price_max == 10000
    assert query.keywords == ["AirPods Pro"]
    # sort=price_asc 会先抓更大样本(60)再排序截断到 limit，因此 scraper 收到的是样本量而非 limit
    assert max_products == 60

    # trace 记录了这次工具调用（含解析后的 arguments）
    assert len(result.trace) == 1
    step = result.trace[0]
    assert isinstance(step, TraceStep)
    assert step.tool == "search_mercari"
    assert step.iteration == 1
    assert step.ok is True
    assert step.arguments == {
        "keyword": "AirPods Pro",
        "price_max": 10000,
        "sort": "price_asc",
        "limit": 5,
    }
    assert "count=3" in step.result_summary


# --------------------------------------------------------------------------- #
# 2) 消息 plumbing：role:"tool" 带正确 tool_call_id + 顺序 + 真实工具产出的 JSON
# --------------------------------------------------------------------------- #
async def test_tool_result_fed_back_with_matching_id_and_order():
    scraper = FakeScraperService(_products(), total_found=15000)
    registry = build_mercari_tool_registry(scraper)
    llm = FakeLLM(
        [
            _assistant_tool_call(
                "call_XYZ", "search_mercari",
                '{"keyword": "AirPods Pro", "sort": "price_asc"}', content=None,
            ),
            _assistant_final("done"),
        ]
    )
    agent = AgentService(llm, registry)

    # 注意：user query 是纯自然语言、不含任何 JSON —— 工具能被执行只可能来自 tool_calls 分支
    await agent.run("帮我找便宜的 AirPods Pro，这句话里没有任何 JSON")

    # 第二轮 LLM 调用必须已看到追加的工具结果
    assert len(llm.calls) == 2
    second_messages = llm.calls[1]["messages"]
    roles = [m["role"] for m in second_messages]
    assert roles == ["system", "user", "assistant", "tool"]

    assistant_msg = second_messages[2]
    # 真·原生：assistant 携带结构化 tool_calls，content 为 None（prompt 里没有 JSON 可解析）
    assert assistant_msg["content"] is None
    assert assistant_msg["tool_calls"][0]["id"] == "call_XYZ"

    tool_msg = second_messages[3]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_XYZ"  # tool_call_id 与请求精确匹配

    # 工具结果是真实工具产出的紧凑 JSON：按价格升序、排除已售出 m4
    payload = json.loads(tool_msg["content"])
    assert payload["keyword"] == "AirPods Pro"
    assert payload["count"] == 3
    assert payload["total_found"] == 15000
    prices = [p["price"] for p in payload["products"]]
    assert prices == [600, 5000, 8999]  # price_asc
    ids = [p["id"] for p in payload["products"]]
    assert "m4" not in ids  # 已售出被过滤


# --------------------------------------------------------------------------- #
# 3) 真·原生：传给 LLM 的是现代 tools schema，且默认 tool_choice="auto"
# --------------------------------------------------------------------------- #
async def test_passes_native_tool_schemas_to_llm():
    scraper = FakeScraperService(_products(), total_found=1)
    registry = build_mercari_tool_registry(scraper)
    llm = FakeLLM([_assistant_final("直接回答，无需工具")])
    agent = AgentService(llm, registry)

    await agent.run("随便问问")

    assert len(llm.calls) == 1
    first_call = llm.calls[0]
    tools = first_call["tools"]
    # 现代格式：[{"type":"function","function":{"name","description","parameters"}}]
    assert all(t["type"] == "function" for t in tools)
    names = {t["function"]["name"] for t in tools}
    assert names == {"search_mercari", "get_price_statistics"}
    # 每个 function schema 带 parameters（可被 OpenAI tools API 识别）
    for t in tools:
        assert "parameters" in t["function"]
        assert t["function"]["parameters"]["type"] == "object"
    # 默认让模型自主决定
    assert first_call["tool_choice"] == "auto"

    # LLM 一上来就没要工具 → 一轮结束返回最终答案，工具零执行
    assert scraper.scrape_calls == []


# --------------------------------------------------------------------------- #
# 4) 一轮内多个 tool_calls：全部执行，两条 tool 消息 id 依序匹配
# --------------------------------------------------------------------------- #
async def test_multiple_tool_calls_in_one_round_all_execute():
    scraper = FakeScraperService(_products(), total_found=15000)
    registry = build_mercari_tool_registry(scraper)
    multi = {
        "content": None,
        "tool_calls": [
            {
                "id": "c1", "type": "function",
                "function": {
                    "name": "get_price_statistics",
                    "arguments": '{"keyword": "AirPods Pro"}',
                },
            },
            {
                "id": "c2", "type": "function",
                "function": {
                    "name": "search_mercari",
                    "arguments": '{"keyword": "AirPods Pro", "sort": "price_asc", "limit": 3}',
                },
            },
        ],
        "model": "fake-model",
        "usage": {},
        "metadata": {},
    }
    llm = FakeLLM([multi, _assistant_final("综合行情与在售商品，推荐如下 ...")])
    agent = AgentService(llm, registry)

    result = await agent.run("先看行情再找便宜货")

    assert result.answer.startswith("综合行情")
    # 两个工具都在第 1 轮执行
    assert len(result.trace) == 2
    assert {s.tool for s in result.trace} == {"get_price_statistics", "search_mercari"}
    assert all(s.iteration == 1 for s in result.trace)
    assert all(s.ok for s in result.trace)
    assert len(scraper.scrape_calls) == 2

    # 第二轮消息里有两条 tool 消息，tool_call_id 依序匹配 c1 / c2
    msgs = llm.calls[1]["messages"]
    tool_msgs = [m for m in msgs if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]

    # 价格统计结果正确（排除已售出 m4）：min=600 / max=8999 / count=3
    stats = json.loads(tool_msgs[0]["content"])
    assert stats["count"] == 3
    assert stats["min"] == 600
    assert stats["max"] == 8999


# --------------------------------------------------------------------------- #
# 5) 健壮性：工具抛异常 —— 循环不崩，把错误回给模型继续
# --------------------------------------------------------------------------- #
async def test_tool_exception_does_not_crash_and_is_returned_to_model():
    scraper = FakeScraperService([], raise_exc=RuntimeError("boom scrape failure"))
    registry = build_mercari_tool_registry(scraper)
    llm = FakeLLM(
        [
            _assistant_tool_call("call_err", "search_mercari", '{"keyword": "AirPods"}', content=None),
            _assistant_final("抱歉，检索时出错，请稍后再试。"),
        ]
    )
    agent = AgentService(llm, registry)

    result = await agent.run("找 AirPods")

    # 没有崩溃，下一轮给出最终答案
    assert result.answer == "抱歉，检索时出错，请稍后再试。"
    assert result.iterations == 2
    assert result.truncated is False

    # trace 标记该次失败
    assert len(result.trace) == 1
    assert result.trace[0].ok is False

    # 错误作为 role:"tool" 消息回传给模型（id 匹配、含原始异常信息）
    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_err"
    err = json.loads(tool_msg["content"])
    assert "error" in err
    assert "boom scrape failure" in err["error"]


# --------------------------------------------------------------------------- #
# 6) 健壮性：未知工具名 —— 返回错误、循环继续、scraper 不被调用
# --------------------------------------------------------------------------- #
async def test_unknown_tool_returns_error_and_continues():
    scraper = FakeScraperService(_products(), total_found=1)
    registry = build_mercari_tool_registry(scraper)
    llm = FakeLLM(
        [
            _assistant_tool_call("call_u", "nonexistent_tool", '{"x": 1}', content=None),
            _assistant_final("已回退，改用其它方式帮助你。"),
        ]
    )
    agent = AgentService(llm, registry)

    result = await agent.run("q")

    assert result.answer == "已回退，改用其它方式帮助你。"
    assert result.trace[0].ok is False
    assert scraper.scrape_calls == []  # 未知工具不会触达 scraper

    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_u"
    err = json.loads(tool_msg["content"])
    assert "未知工具" in err["error"]


# --------------------------------------------------------------------------- #
# 7) 健壮性：arguments 非法 JSON —— 不崩，把解析错误回给模型，工具不执行
# --------------------------------------------------------------------------- #
async def test_invalid_json_arguments_handled_gracefully():
    scraper = FakeScraperService(_products(), total_found=1)
    registry = build_mercari_tool_registry(scraper)
    llm = FakeLLM(
        [
            _assistant_tool_call("call_bad", "search_mercari", "{not valid json", content=None),
            _assistant_final("参数解析失败，已忽略该次调用。"),
        ]
    )
    agent = AgentService(llm, registry)

    result = await agent.run("q")

    assert result.answer == "参数解析失败，已忽略该次调用。"
    assert result.iterations == 2
    # 参数没解析成功 → 工具没执行
    assert scraper.scrape_calls == []
    assert result.trace[0].ok is False

    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_bad"
    err = json.loads(tool_msg["content"])
    assert "error" in err


# --------------------------------------------------------------------------- #
# 8) 迭代上限：安全终止 + 强制一次 tool_choice="none" 收尾
# --------------------------------------------------------------------------- #
async def test_max_iterations_forces_safe_termination():
    scraper = FakeScraperService(_products(), total_found=15000)
    registry = build_mercari_tool_registry(scraper)
    # 模型每轮都要工具（永不主动收尾）；max_iterations=2 → 2 轮工具 + 1 次强制收尾
    llm = FakeLLM(
        [
            _assistant_tool_call("call_1", "search_mercari", '{"keyword": "AirPods Pro"}', content=None),
            _assistant_tool_call("call_2", "get_price_statistics", '{"keyword": "AirPods Pro"}', content=None),
            _assistant_final("已达迭代上限，基于已有信息给出最终推荐 ..."),
        ]
    )
    agent = AgentService(llm, registry, max_iterations=2)

    result = await agent.run("找 AirPods Pro")

    # 安全终止：标记 truncated、迭代数为上限、返回收尾答案
    assert result.truncated is True
    assert result.iterations == 2
    assert result.answer.startswith("已达迭代上限")

    # 恰好执行两次工具（每轮一次），trace 两条
    assert len(scraper.scrape_calls) == 2
    assert len(result.trace) == 2

    # 一共 3 次 LLM 调用，最后一次是强制收尾：tool_choice="none"
    assert len(llm.calls) == 3
    assert llm.calls[0]["tool_choice"] == "auto"
    assert llm.calls[1]["tool_choice"] == "auto"
    assert llm.calls[2]["tool_choice"] == "none"
