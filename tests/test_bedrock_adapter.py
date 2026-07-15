"""
BedrockClaudeLLM 适配层的确定性离线单测。

被测对象：infrastructure/llm/llm_service.py 里新增的 BedrockClaudeLLM —— 把 LLM 层
迁到 AWS Bedrock 上的 Claude（anthropic SDK 的 AsyncAnthropicBedrock），作为新增主
provider，与 OpenAI 并存。核心是 provider 内部的 OpenAI<->Anthropic 格式适配，让
AgentService / interfaces 一行不改即可切换。

铁律（本文件绝不触网 / 绝不调真实 Bedrock / 不需要 AWS 凭证）：
  - 用 FakeBedrockClient 替身：.messages.create 返回预设的假 response（SimpleNamespace
    造 text block / tool_use block、model、usage、stop_reason），并记录调用 kwargs 以
    断言翻译结果。
  - BedrockClaudeLLM 实例用 __new__ 构造（跳过 __init__ 里的 boto3/SSO），直接注入
    fake client；翻译逻辑另有纯函数（静态方法）单测。

覆盖：
  1. chat_with_tools：带 tool_use 的响应 -> OpenAI 风格 tool_calls（arguments 是能
     json.loads 的字符串）；纯 text -> content；无 text -> content=None。
  2. 消息翻译：system 抽出单独传；assistant(tool_calls) + 连续多个 role:tool ->
     assistant(tool_use blocks) + 一个合并的 user(多个 tool_result)；id 对应。
  3. tools：function.parameters -> input_schema（兼容裸 / 已包裹）。
  4. tool_choice="none" 不传 tools。
  5. generate_response(response_format="json")：设了 JSON system、返回 dict 形状对。
  6. 配置：Bedrock 默认值 + BEDROCK_MODEL_ID 可被 env 覆盖 + has_bedrock_config。
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 该包未以 editable 方式安装，测试时把 src 加入 import 路径
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mercari_agent.infrastructure.llm.llm_service import BedrockClaudeLLM  # noqa: E402


DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"


# --------------------------------------------------------------------------- #
# 替身（fakes）：零网络、零 AWS 凭证、零真实 Bedrock
# --------------------------------------------------------------------------- #
class _FakeMessages:
    """假的 client.messages：create 是 async，返回预设 response 并记录 kwargs。"""

    def __init__(self, response):
        self._response = response
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeBedrockClient:
    """假的 AsyncAnthropicBedrock 客户端。"""

    def __init__(self, response):
        self.messages = _FakeMessages(response)
        self.closed = False

    async def close(self):
        self.closed = True


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(block_id, name, inp):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=inp)


def fake_response(blocks, model=DEFAULT_MODEL, input_tokens=12,
                  output_tokens=7, stop_reason="end_turn"):
    return SimpleNamespace(
        content=list(blocks),
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )


def make_llm(client):
    """跳过 __init__（boto3/SSO），直接注入 fake client。"""
    llm = BedrockClaudeLLM.__new__(BedrockClaudeLLM)
    llm.model_id = DEFAULT_MODEL
    llm.region = "us-west-2"
    llm.profile = "test-profile"
    llm.client = client
    return llm


# --------------------------------------------------------------------------- #
# 1. chat_with_tools 响应适配（Anthropic -> OpenAI）
# --------------------------------------------------------------------------- #
async def test_chat_with_tools_tool_use_becomes_openai_tool_calls():
    resp = fake_response([
        text_block("让我搜索一下"),
        tool_use_block("toolu_1", "search_mercari",
                       {"keywords": "任天堂 switch", "max_results": 5}),
    ])
    client = FakeBedrockClient(resp)
    llm = make_llm(client)

    out = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "帮我找 switch"}],
        tools=[{
            "type": "function",
            "function": {
                "name": "search_mercari",
                "description": "搜索",
                "parameters": {"type": "object", "properties": {"keywords": {"type": "string"}}},
            },
        }],
        tool_choice="auto",
    )

    assert out["content"] == "让我搜索一下"
    assert len(out["tool_calls"]) == 1
    tc = out["tool_calls"][0]
    assert tc["id"] == "toolu_1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "search_mercari"
    # arguments 必须是能 json.loads 的字符串
    args = json.loads(tc["function"]["arguments"])
    assert args == {"keywords": "任天堂 switch", "max_results": 5}
    # usage / metadata 形状
    assert out["usage"] == {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19}
    assert out["model"] == DEFAULT_MODEL
    assert out["metadata"]["stop_reason"] == "end_turn"


async def test_chat_with_tools_pure_text_sets_content_no_tool_calls():
    llm = make_llm(FakeBedrockClient(fake_response([text_block("这是最终答案")])))
    out = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "hi"}], tools=[]
    )
    assert out["content"] == "这是最终答案"
    assert out["tool_calls"] == []


async def test_chat_with_tools_no_text_block_content_is_none():
    resp = fake_response([tool_use_block("t1", "search_mercari", {"q": "x"})])
    llm = make_llm(FakeBedrockClient(resp))
    out = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "hi"}], tools=[]
    )
    assert out["content"] is None
    assert len(out["tool_calls"]) == 1
    assert out["tool_calls"][0]["function"]["name"] == "search_mercari"


# --------------------------------------------------------------------------- #
# 2. 消息翻译（OpenAI -> Anthropic）
# --------------------------------------------------------------------------- #
def test_translate_messages_system_extracted_and_tool_results_merged():
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "system", "content": "只用中文"},
        {"role": "user", "content": "找 switch"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_a", "type": "function",
             "function": {"name": "search_mercari", "arguments": '{"keywords":"switch"}'}},
            {"id": "call_b", "type": "function",
             "function": {"name": "price_stats", "arguments": '{"keywords":"switch"}'}},
        ]},
        {"role": "tool", "tool_call_id": "call_a", "content": '{"items":[]}'},
        {"role": "tool", "tool_call_id": "call_b", "content": '{"avg":100}'},
        {"role": "user", "content": "继续"},
    ]

    system_text, translated = BedrockClaudeLLM._translate_messages(messages)

    # system 被抽出单独传（两个 system 合并成一个字符串）
    assert "你是助手" in system_text and "只用中文" in system_text
    # translated 里不再有 system role
    assert all(m["role"] != "system" for m in translated)

    # 结构：user -> assistant(tool_use) -> user(合并 tool_result) -> user
    assert [m["role"] for m in translated] == ["user", "assistant", "user", "user"]

    # assistant.content 为 block 列表；content=None 所以没有 text block，仅两个 tool_use
    assistant_blocks = translated[1]["content"]
    assert [b["type"] for b in assistant_blocks] == ["tool_use", "tool_use"]
    assert assistant_blocks[0]["id"] == "call_a"
    assert assistant_blocks[0]["name"] == "search_mercari"
    # arguments 字符串 -> input dict
    assert assistant_blocks[0]["input"] == {"keywords": "switch"}

    # 连续两个 tool 结果合并进同一个 user turn
    merged = translated[2]["content"]
    assert [b["type"] for b in merged] == ["tool_result", "tool_result"]
    # tool_call_id <-> tool_use_id 精确对应
    assert merged[0]["tool_use_id"] == "call_a"
    assert merged[1]["tool_use_id"] == "call_b"
    assert merged[0]["content"] == '{"items":[]}'
    assert merged[1]["content"] == '{"avg":100}'


def test_translate_messages_assistant_text_and_tool_calls_text_block_first():
    _, translated = BedrockClaudeLLM._translate_messages([
        {"role": "assistant", "content": "先想一下", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}},
        ]},
    ])
    blocks = translated[0]["content"]
    assert blocks[0] == {"type": "text", "text": "先想一下"}
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["input"] == {}


def test_translate_messages_plain_assistant_and_user_stay_strings():
    _, translated = BedrockClaudeLLM._translate_messages([
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "答案"},
    ])
    assert translated[0] == {"role": "user", "content": "问题"}
    assert translated[1] == {"role": "assistant", "content": "答案"}


def test_translate_messages_no_system_returns_none():
    system_text, _ = BedrockClaudeLLM._translate_messages([
        {"role": "user", "content": "hi"},
    ])
    assert system_text is None


async def test_chat_with_tools_passes_system_string_and_strips_system_role():
    client = FakeBedrockClient(fake_response([text_block("ok")]))
    llm = make_llm(client)
    await llm.chat_with_tools(
        messages=[
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "hi"},
        ],
        tools=[],
    )
    kwargs = client.messages.calls[0]
    assert kwargs["system"] == "系统提示"
    assert all(m["role"] != "system" for m in kwargs["messages"])


# --------------------------------------------------------------------------- #
# 3. tools 翻译：parameters -> input_schema
# --------------------------------------------------------------------------- #
async def test_tools_parameters_translated_to_input_schema():
    client = FakeBedrockClient(fake_response([text_block("ok")]))
    llm = make_llm(client)
    params = {
        "type": "object",
        "properties": {"keywords": {"type": "string"}},
        "required": ["keywords"],
    }
    await llm.chat_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{
            "type": "function",
            "function": {"name": "search_mercari", "description": "搜索商品", "parameters": params},
        }],
        tool_choice="auto",
    )
    kwargs = client.messages.calls[0]
    assert "tools" in kwargs
    t = kwargs["tools"][0]
    assert t["name"] == "search_mercari"
    assert t["description"] == "搜索商品"
    assert t["input_schema"] == params
    assert "parameters" not in t
    # tool_choice="auto" -> {"type": "auto"}
    assert kwargs["tool_choice"] == {"type": "auto"}


def test_translate_tools_accepts_bare_and_wrapped_and_defaults():
    fn = {"name": "f", "description": "d",
          "parameters": {"type": "object", "properties": {}}}
    out_bare = BedrockClaudeLLM._translate_tools([fn])
    out_wrapped = BedrockClaudeLLM._translate_tools([{"type": "function", "function": fn}])
    assert out_bare == out_wrapped
    assert out_bare[0]["input_schema"] == {"type": "object", "properties": {}}

    # 缺 parameters / description -> 使用默认空 schema / 空描述
    out_default = BedrockClaudeLLM._translate_tools([{"name": "g"}])
    assert out_default[0]["input_schema"] == {"type": "object", "properties": {}}
    assert out_default[0]["description"] == ""


# --------------------------------------------------------------------------- #
# 4. tool_choice="none" 不传 tools
# --------------------------------------------------------------------------- #
async def test_tool_choice_none_omits_tools():
    client = FakeBedrockClient(fake_response([text_block("最终推荐")]))
    llm = make_llm(client)
    out = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "收尾"}],
        tools=[{"type": "function", "function": {"name": "f", "parameters": {}}}],
        tool_choice="none",
    )
    kwargs = client.messages.calls[0]
    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs
    assert out["content"] == "最终推荐"


async def test_tool_choice_dict_maps_to_anthropic_tool():
    client = FakeBedrockClient(fake_response([text_block("ok")]))
    llm = make_llm(client)
    await llm.chat_with_tools(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "search_mercari", "parameters": {}}}],
        tool_choice={"type": "function", "function": {"name": "search_mercari"}},
    )
    kwargs = client.messages.calls[0]
    assert kwargs["tool_choice"] == {"type": "tool", "name": "search_mercari"}


# --------------------------------------------------------------------------- #
# 5. generate_response(response_format="json")
# --------------------------------------------------------------------------- #
async def test_generate_response_json_sets_system_and_shape():
    client = FakeBedrockClient(fake_response([text_block('{"ok": true}')]))
    llm = make_llm(client)
    out = await llm.generate_response("给我 JSON", response_format="json")

    kwargs = client.messages.calls[0]
    # JSON system 已设
    assert "JSON" in kwargs["system"]
    assert kwargs["messages"] == [{"role": "user", "content": "给我 JSON"}]

    # 返回 dict 形状
    assert out["content"] == '{"ok": true}'
    assert out["model"] == DEFAULT_MODEL
    assert out["usage"] == {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19}
    assert out["metadata"]["stop_reason"] == "end_turn"
    assert out["tool_calls"] == []


async def test_generate_response_text_no_system_and_concats_text_blocks():
    client = FakeBedrockClient(fake_response([text_block("hello "), text_block("world")]))
    llm = make_llm(client)
    out = await llm.generate_response("hi")
    kwargs = client.messages.calls[0]
    assert "system" not in kwargs
    # 拼接所有 text block
    assert out["content"] == "hello world"


async def test_generate_response_passes_stop_sequences():
    client = FakeBedrockClient(fake_response([text_block("x")]))
    llm = make_llm(client)
    await llm.generate_response("hi", stop=["\n\n"], max_tokens=256, temperature=0.1)
    kwargs = client.messages.calls[0]
    assert kwargs["stop_sequences"] == ["\n\n"]
    assert kwargs["max_tokens"] == 256
    assert kwargs["temperature"] == 0.1


async def test_close_is_defensive():
    client = FakeBedrockClient(fake_response([text_block("x")]))
    llm = make_llm(client)
    await llm.close()
    assert client.closed is True


# --------------------------------------------------------------------------- #
# 6. 配置：默认值 + env 覆盖 + has_bedrock_config
# --------------------------------------------------------------------------- #
def test_bedrock_config_defaults():
    from mercari_agent.shared.config.app_config import LLMConfig
    c = LLMConfig()
    assert c.bedrock_model_id == DEFAULT_MODEL
    assert c.bedrock_region == "us-west-2"
    assert c.aws_profile == "sandbox-Oregon"
    assert c.has_bedrock_config() is True


def test_bedrock_model_id_env_override(monkeypatch):
    from mercari_agent.shared.config.app_config import AppConfig
    monkeypatch.setenv("BEDROCK_MODEL_ID", "apac.anthropic.custom-model-v9:0")
    monkeypatch.setenv("BEDROCK_REGION", "ap-northeast-1")
    monkeypatch.setenv("AWS_PROFILE", "custom-profile")
    app = AppConfig()
    assert app.llm.bedrock_model_id == "apac.anthropic.custom-model-v9:0"
    assert app.llm.bedrock_region == "ap-northeast-1"
    assert app.llm.aws_profile == "custom-profile"
    assert app.has_bedrock_config() is True
