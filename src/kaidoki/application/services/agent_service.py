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
- 记录完整 trace：每步调了什么工具、完整入参、**完整返回**、耗时，
  外加每轮模型自己说的话（notes）与完整对话（messages）。
  只留摘要的话，"模型为什么跳过了某个工具""它凭什么下这个结论"是查不出来的。

Author: Kaidoki Team (native tools)
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...infrastructure.llm.llm_service import LLMService
from ...tools.framework.tool_registry import ToolRegistry
from ...shared.utils.item_filters import prompt_category_lines, prompt_keyword_lines
from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

# 单个工具返回在 trace 里保留的上限（防爆内存/日志，同时足够看清全部字段）
_RESULT_FULL_LIMIT = 20000


SYSTEM_PROMPT = f"""你是一个会使用工具的日本购物比价助手（Mercari 个人间交易 + kakaku 新品比价）。

你可以调用以下工具来获取真实数据，绝不要凭空编造商品或价格：
- recommend_deals：一步跑完整推荐流程（理解查询→抓取 Mercari→按策略 LLM 重排），
  直接返回一份现成推荐（含推荐理由）。面对直接明确的"帮我找 X 的好货 / 性价比高的 X"
  请求时，优先用它。
- search_mercari：搜索 Mercari 在售商品，看具体有哪些、价格、成色、链接。
- get_price_statistics：获取某关键词的价格行情（最低/最高/中位数/平均）。
- get_new_and_newer_models：给定型号名，返回它的『新品最安値』以及同产品线里更新的
  型号（及各自新品价，来自 kakaku 新品比价 / 品牌官方商店）。

═══ 硬规则（违反会给出错误结论，务必遵守）═══

【R1】Mercari 不是只有二手。成色「新品・未使用」= 全新未拆封，「未使用に近い」≈ 全新。
  所以**即使用户说"只买新品"，也必须**用 search_mercari + condition=["新品・未使用"]
  查一遍，再和 kakaku 的新品最安値对比 —— Mercari 的全新品经常更便宜。
  不允许因为"Mercari 是二手平台"就跳过它。

【R2】Mercari 搜索里混着大量配件与残缺品陷阱。报出任何 Mercari 商品前，先看标题：
{prompt_keyword_lines()}
  搜本体时建议给一个合理的 price_min（例如新品最安値的 40%）先把配件挡掉，
  并在结论里说明你排除了哪些。

【R3】get_new_and_newer_models 的返回里，`newer_lookup` 决定你能说什么：
  - `"ok"`  → 确实按発売日比较过，此时可以说"有更新型号 X"或"没有更新型号"；
  - `"unknown"` → **禁止**说"没有更新型号 / 后継モデルなし"。必须说
    "未能确认是否有更新型号"，并把 `newer_lookup_reason` 的原因转达给用户。
  空的 `newer_models` 列表**不等于**"没有更新型号"。

【R4】选型置信度：`searched_model.confidence`
  - `"high"` → 关键词命中了具体型番，可以直接下结论；
  - `"medium"` / `"low"` → 关键词太笼统（如只给"Braun Pro"），命中的机型可能不是用户要的。
    必须明确告诉用户"我按 X 这个具体型号查的"，并把 `candidates` 里的其它候选列出来让用户确认。

【R5】每个报出的价格都必须附上来源 url（kakaku 商品页 / Mercari 商品页），让用户能核对。
  同时必须把 `searched_model.warnings` 里的内容转达给用户 —— 例如
  "発売から約 3 年的旧型号"、"在售店舗仅 3 店" 意味着这个最安値是冷门旧货，
  不代表现在该买的东西，而且在搜索页排名很靠后、用户自己不容易找到。

【R6】关键词精度：kakaku 和 Mercari 都是日文站，用日文型号名（如 "ブラウン シリーズ9 Pro"）
  比罗马字（"Braun Pro"）准得多。第一次搜得不对就换更具体的关键词重试，别将就。

【R7】价格接近时优先正规渠道 —— 但**必须先确认是同一型番**。
  - **同型番**且 Mercari 未使用品与 kakaku 新品价差在 5% 以内 → 推荐 kakaku。
    理由：有メーカー保証、可退货、正規流通品、能开发票。几百日元不值得换成个人交易的风险
    （型号不符 / 已激活 / 並行輸入品 / 卖家不发货）。
  - **型番不同** → 禁止只比价格。必须先指出规格差异（発売日 / 世代 / 等级 / 充電端子 / 附属品），
    再说明便宜的那个到底是"旧款低配"还是"只是渠道差价"。
    实测两次近似同价都属于这种情况，而且方向相反：
      · Braun：kakaku ¥29,800 是 2022 年 9435s-V（仅 3 店），Mercari ¥29,333 是 2025 年 Pro+ 9517s-V
        —— 价差 1.6%，但差 3 年 + 一个等级，该买 Mercari 那个。
      · AirPods：kakaku ¥28,000 的 MQD83J/A 是 Lightning 版（2022-09、1 店的尾货价），
        而 USB-C 版 MTJV3J/A 在 kakaku 只要 ¥31,898 且有 13 店 —— 便宜的反而是旧款。
    所以"贵/便宜"必须配上型番与発売日才有意义；只报两个数字是错的。
  - 判断同型番时看型番串（9435s-V / MTJV3J/A），不要只看系列名。
    Mercari 标题常常不写型番 —— 这种情况要明确告诉用户"该商品未注明型番，需向卖家确认"，
    不能假设它是你在比的那一款。

【R8】**二手可不可以，看品类**。不要一律推荐"中古最划算"。
{prompt_category_lines()}
  - 耐用电子 → 二手完全可以，按成色 + 价格推荐，Mercari 中古通常确实最划算
    （实测 D850：中古 ¥125,000 vs kakaku 新品 ¥279,980，中古是合理选择）。
  - 个人护理用品 → **只推新品**，且默认首选 kakaku 正规渠道。理由：直接接触皮肤，
    卫生问题不可逆；而 Mercari 的「新品・未使用」是**个人卖家自述**，无法核实是否真未开封。
    · 这类商品**不要**把 Mercari 中古（目立った傷 等）放进推荐里，连"最便宜的选项"也不要列。
    · Mercari 只在标题明确写「未開封」时可作备选，且必须写明"个人卖家自述、无法核实、
      无メーカー保証"，并说清它比正规渠道便宜多少、值不值得为此承担风险。
  - 需要判断的那类（如カナル型イヤホン）→ 先说明卫生顾虑，再让用户决定，别替他决定。

【R9】同系列里的**配置维度**不可混比。get_new_and_newer_models 返回的 `variant`：
  - `with_cleaning_station`（型番以 cc 结尾）= 洗浄器付き
  - `body_only`（型番以 s 结尾）= 本体のみ
  用户要洗浄器付き时，只能拿 cc 机型互相比价。实测 Pro+ 9617s ¥35,698（本体のみ）与
  9657cc ¥43,999（洗浄器付き）差 ¥8,301 —— 混着报会让用户以为便宜了八千。
  另外 Mercari 标题里「洗浄器**対応**」≠「洗浄器**付き**」：対応 只表示兼容，机器不含洗浄器
  （实测 ¥22,600 的「9577cc 洗浄器対応モデル」就是这种）。报价前必须区分。

【R10】**「最安値」不等于「实际支付额」**。工具返回的 kakaku 价格带着
  `price_basis: "cash_lowest_excl_campaigns"` —— 它是现金最安値，**不含**：
  - メーカーキャッシュバック（实测 Braun 有"本体+替刃 同時購入で ¥3,500"，
    占 ¥43,960 的 8%；D850 在 2025 春有过 ¥50,000）
  - 楽天ポイント / PayPay 等点数还元（最高可达商品价的 50%，kakaku 完全不计入）
  所以给出价格对比时**必须补一句**："以上为现金最安値，未计入メーカーキャッシュバック与
  ポイント还元，实际支付可能更低 —— 购买前请查一下当期活动"。
  两个选项差价在 10% 以内时这句尤其重要：一次キャッシュバック就能把结论反转。
  不要凭记忆编造具体活动名称或金额（活动会过期），只提示用户去查。

【R11】Mercari 的 get_price_statistics 返回的是**本体行情**（`basis: "body_only"`），
  已剔除配件/残缺品/不同产品，`excluded` 里写了剔了多少条、按什么规则。
  - 调用时**尽量给 price_min**（kakaku 新品最安値的 30~40%）。不给的话词表挡不住所有杂物，
    实测 "ニコン D850" 不给下限时中位数只有 ¥5,000（一台十几万的相机）。
  - 返回里若有 `warnings`（样本疑似混着配件与本体），**必须**按提示补上 price_min 重查，
    不要拿那个中位数下结论。
  - `unfiltered` 是未过滤的原始统计，只用于对照，不要拿它当行情。

═══ 工作方式 ═══
1. 直接的"找 X 好货" → 一次 recommend_deals 通常就够。
2. 需要比较、先查行情再判断 → search_mercari + get_price_statistics 组合（可多次）。
3. 尊重用户预算等约束（预算上限用 price_max）。

面对『某型号该怎么买 / 值不值得买 / 买哪个』这类购买决策请求，给出【四选一判断】：
   - 买 Mercari 二手（最划算的在售品，含价格/成色/链接）  ← **个人护理用品直接跳过这项**（R8）
   - 买 Mercari 全新未使用（condition=["新品・未使用"]，含价格/链接）  ← 别漏这一项
   - 买 kakaku 新品（同型号新品最安値 + url）
   - 买更新型号（同线更新型号及其新品价，仅当 newer_lookup=="ok" 且确实有）
每项标出价格与来源链接，各用一句话说明理由（便宜多少、贵多少换来什么）。
按 R8 先判断品类：耐用电子四项都给；个人护理用品只给新品那两三项，并说明为什么不推荐二手。
数据缺失就说明缺失，只在可得数据内给建议，绝不臆造价格。

4. 用中文回答，简洁清晰。
"""


@dataclass
class TraceStep:
    """一次工具调用的 trace 记录。

    result_full 保留**完整**的工具返回（只做防爆上限截断）。摘要好看但会藏掉问题：
    比如 get_new_and_newer_models 的 newer_lookup / confidence / warnings 全在细节里，
    只看摘要就无法判断模型为什么下了那个结论。
    """
    iteration: int
    tool: str
    arguments: Dict[str, Any]
    ok: bool
    result_summary: str
    result_full: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "tool": self.tool,
            "arguments": self.arguments,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
            "result_summary": self.result_summary,
            "result_full": self.result_full,
        }


@dataclass
class AgentResult:
    """agent 运行结果"""
    answer: str
    trace: List[TraceStep] = field(default_factory=list)
    iterations: int = 0
    truncated: bool = False
    # 每轮模型在调工具之前说的话 —— 这是它的可见推理。
    # 复盘"为什么它没去查 Mercari"这类问题时，唯一的线索就在这里。
    notes: List[Dict[str, Any]] = field(default_factory=list)
    # 完整对话（system/user/assistant/tool），供落盘复盘用
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "iterations": self.iterations,
            "truncated": self.truncated,
            "notes": self.notes,
            "trace": [s.to_dict() for s in self.trace],
            "messages": self.messages,
        }


def _summarize_result(data_str: str, limit: int = 400) -> str:
    """把工具返回压成 trace 里的一行摘要（完整内容在 TraceStep.result_full）。"""
    try:
        obj = json.loads(data_str)
    except (ValueError, TypeError):
        return data_str[:limit]
    if not isinstance(obj, dict):
        return data_str[:limit]
    if "error" in obj:
        return f"ERROR: {obj['error']}"

    parts: List[str] = []

    # get_new_and_newer_models：摘要必须带上 confidence / newer_lookup，
    # 否则复盘时看不出"没有更新型号"到底是查过还是没查出来。
    searched = obj.get("searched_model")
    if isinstance(searched, dict):
        parts.append(
            f"searched={searched.get('name')}@¥{searched.get('new_price_min')}"
            f"({searched.get('release')}, {searched.get('shops')}店"
            f", conf={searched.get('confidence')})"
        )
        parts.append(f"newer_lookup={obj.get('newer_lookup')}")
        parts.append(f"newer={len(obj.get('newer_models') or [])}")
        if searched.get("warnings"):
            parts.append(f"warnings={len(searched['warnings'])}")
        if obj.get("candidates"):
            parts.append(f"candidates={len(obj['candidates'])}")
        return ", ".join(parts)

    if obj.get("condition_filter"):
        parts.append(f"condition={obj['condition_filter']}")
    if "count" in obj:
        parts.append(f"count={obj['count']}")
    for k in ("min", "max", "median", "average", "total_found"):
        if k in obj:
            parts.append(f"{k}={obj[k]}")
    prods = obj.get("products")
    if isinstance(prods, list) and prods:
        sample = prods[0]
        parts.append(f"e.g. {sample.get('title', '')[:30]}@¥{sample.get('price')}")
    if obj.get("note"):
        parts.append(f"note={obj['note']}")
    return ", ".join(parts) if parts else data_str[:limit]


class AgentService:
    """原生工具调用 agent。"""

    def __init__(
        self,
        llm_service: LLMService,
        tool_registry: ToolRegistry,
        max_iterations: int = 6,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 4000,
    ):
        self.llm = llm_service
        self.registry = tool_registry
        self.max_iterations = max(1, int(max_iterations))
        self.system_prompt = system_prompt
        # 四选一判断 + 每项都要附 url/警告，回答本身就长；1200 会把结论截断在半句话上
        self.max_tokens = max(256, int(max_tokens))

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
        """跑 agent 循环，返回最终回答 + 完整 trace（含每轮模型的中间推理）。"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_query},
        ]
        tools = self._tool_schemas()
        trace: List[TraceStep] = []
        notes: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            assistant = await self.llm.chat_with_tools(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=self.max_tokens,
            )
            tool_calls = assistant.get("tool_calls") or []
            content = assistant.get("content")

            # 记录模型这一轮的可见推理 + 它选择调用的工具（复盘的主线索）
            notes.append({
                "iteration": iteration,
                "text": content or "",
                "tools_called": [
                    (tc.get("function") or {}).get("name") for tc in tool_calls
                ],
            })

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
                    notes=notes,
                    messages=messages,
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
                    trace.append(TraceStep(
                        iteration, name, {"_raw": raw_args}, False,
                        _summarize_result(result_str), result_full=result_str,
                    ))
                    messages.append({"role": "tool", "tool_call_id": call_id,
                                     "content": result_str})
                    continue

                logger.info(f"[iter {iteration}] LLM 调用工具 {name} args={args}")
                started = time.monotonic()
                ok, result_str = await self._dispatch(name, args)
                elapsed_ms = int((time.monotonic() - started) * 1000)
                trace.append(TraceStep(
                    iteration, name, args, ok,
                    _summarize_result(result_str),
                    result_full=result_str[:_RESULT_FULL_LIMIT],
                    duration_ms=elapsed_ms,
                ))
                messages.append({"role": "tool", "tool_call_id": call_id,
                                 "content": result_str})

        # 达到迭代上限：强制一次不带工具的收尾回答
        logger.warning(f"达到迭代上限 {self.max_iterations}，强制收尾")
        closing = {
            "role": "user",
            "content": "请基于以上已获取的信息直接给出最终推荐，不要再调用工具。",
        }
        final = await self.llm.chat_with_tools(
            messages=messages + [closing],
            tools=tools,
            tool_choice="none",
            temperature=0.3,
            max_tokens=self.max_tokens,
        )
        answer = final.get("content") or ""
        return AgentResult(
            answer=answer,
            trace=trace,
            iterations=self.max_iterations,
            truncated=True,
            notes=notes,
            messages=messages + [closing, {"role": "assistant", "content": answer}],
        )
