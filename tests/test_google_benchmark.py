"""
Google 对照基线单测（零网络 / 零真实 LLM / 零浏览器）。

这个记分板的价值全靠"诚实"，所以测试重点全在容易静默出错的地方：

- 价格抽取不能把型番当价格（"9435s-V" / "9660cc" / "K0001713157"）
- 配件 / 残缺品必须从**两侧**都排除（否则我方 ¥2,299 的替刃会"赢"下比较）
- 不能过度过滤：AirPods 的正式商品名里就带「充電ケース」
- 「没有更便宜的」与「查不出来」要分开（verdict n/a vs win/tie/loss）
- **无污染**：对照绝不能回写 agent 的 messages，也不能多调一次 LLM
- 失败隔离：没 key / API 报错 / 超时 → 推荐照常，记录里写 error
- rescore：改了打分逻辑能从旧原始数据重算，不需要再打 API
"""

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.application.services.agent_service import AgentResult, TraceStep  # noqa: E402
from kaidoki.application.services.benchmark_service import (  # noqa: E402
    BenchmarkService,
    append_record,
    build_fair_query,
    build_record,
    extract_our_items,
    load_records,
    matches_product,
    product_keyword,
    required_product_tokens,
    rescore_record,
    score,
    summarize,
)
from kaidoki.infrastructure.search.google_search import (  # noqa: E402
    GoogleCseClient,
    extract_jpy_prices,
    parse_cse_response,
)
from kaidoki.shared.utils.item_filters import classify_exclusion, looks_like_body  # noqa: E402


# --------------------------------------------------------------------------- #
# 夹具：真实形状的 trace 与 CSE 响应（数值取自 2026-08 的实跑）
# --------------------------------------------------------------------------- #
def _model_compare_result():
    return {
        "keyword": "ブラウン シリーズ9 Pro",
        "searched_model": {
            "name": "ブラウン シリーズ9 Pro 9450cc-V", "new_price_min": 39298,
            "release": "2022-09", "shops": 6, "confidence": "medium",
            "url": "https://kakaku.com/item/K0001490278/", "source": "kakaku.com",
            "warnings": ["発売から約 3 年（2022-09）的旧型号，价格与在售情况可能已变化"],
        },
        "newer_models": [
            {"name": "ブラウン シリーズ9 Pro+ 9617s [マットシルバー]", "new_price_min": 35698,
             "release": "2025-11", "shops": 19,
             "url": "https://kakaku.com/item/K0001713159/"},
        ],
        "candidates": [
            {"name": "ブラウン シリーズ9 Pro 9435s-V", "new_price_min": 29800,
             "release": "2022-09", "shops": 3,
             "url": "https://kakaku.com/item/K0001454549/"},
        ],
        "newer_lookup": "ok",
        "currency": "JPY",
    }


def _mercari_result():
    return {
        "keyword": "ブラウン シリーズ9 Pro 本体 シェーバー",
        "condition_filter": ["新品・未使用"],
        "count": 4,
        "products": [
            {"id": "m1", "title": "ブラウン FC94M シリーズ9Pro用 交換用替刃 網刃",
             "price": 2299, "condition": "新品・未使用",
             "url": "https://jp.mercari.com/item/m1"},
            {"id": "m2", "title": "ブラウン最高峰最上位S9 Pro+ 9587cc 刃無し本体 新品未使用",
             "price": 22600, "condition": "新品・未使用",
             "url": "https://jp.mercari.com/item/m2"},
            {"id": "m3", "title": "【新品未開封】Braun シリーズ9 Pro+ 9517s-V メンズシェーバー",
             "price": 29333, "condition": "新品・未使用",
             "url": "https://jp.mercari.com/item/m3"},
            {"id": "m4", "title": "Braun シリーズ9 Pro+ 9530s 本体 新品",
             "price": 30500, "condition": "新品・未使用",
             "url": "https://jp.mercari.com/item/m4"},
        ],
    }


def _trace():
    return [
        TraceStep(1, "get_new_and_newer_models", {"keyword": "ブラウン シリーズ9 Pro"},
                  True, "summary",
                  result_full=json.dumps(_model_compare_result(), ensure_ascii=False)),
        TraceStep(2, "search_mercari",
                  {"keyword": "ブラウン シリーズ9 Pro 本体 シェーバー",
                   "condition": ["新品・未使用"]},
                  True, "summary",
                  result_full=json.dumps(_mercari_result(), ensure_ascii=False)),
    ]


def _cse_payload(items):
    return {"searchInformation": {"totalResults": "674"}, "items": items}


_CSE_ITEMS = [
    {   # 结构化价格（pagemap）→ verified
        "title": "ブラウン シリーズ9 Pro+ 9617s 価格比較 - 価格.com",
        "link": "https://kakaku.com/item/K0001713159/",
        "displayLink": "kakaku.com",
        "snippet": "最安価格 35,698円 発売日：2025年11月 全19店舗",
        "pagemap": {"offer": [{"price": "35698", "pricecurrency": "JPY"}]},
    },
    {   # 只有摘要价格 → unverified
        "title": "ブラウン シリーズ9 Pro 9435s-V の最安値をチェック",
        "link": "https://example.jp/braun/9435s-v",
        "displayLink": "example.jp",
        "snippet": "ブラウン シリーズ9 Pro 9435s-V は ¥29,800 から。型番 9435s-V。",
        "pagemap": {},
    },
    {   # 配件页：必须被排除，否则 ¥2,380 会变成"Google 最低价"
        "title": "94M ブラウン シリーズ9 Pro 替刃 互換品 2個セット",
        "link": "https://example.jp/parts/94m",
        "displayLink": "example.jp",
        "snippet": "替刃 2個セット ¥2,380 送料無料",
        "pagemap": {"offer": [{"price": "2380"}]},
    },
]


# --------------------------------------------------------------------------- #
# 价格抽取：不能把型番当价格
# --------------------------------------------------------------------------- #
def test_extract_jpy_requires_currency_anchor():
    assert extract_jpy_prices("最安価格 29,800円") == [29800]
    assert extract_jpy_prices("¥35,698 から") == [35698]
    # 型番 / 型番式编号绝不能被当成价格 —— 一个假价格就毁掉整条比较
    assert extract_jpy_prices("ブラウン シリーズ9 Pro 9435s-V 9660cc") == []
    assert extract_jpy_prices("kakaku.com/item/K0001713157/") == []
    assert extract_jpy_prices("発売日：2025年11月") == []


def test_extract_jpy_ignores_insane_values():
    assert extract_jpy_prices("¥12") == []            # 太小
    assert extract_jpy_prices("¥99,999,999") == []    # 太大


def test_parse_cse_marks_price_provenance():
    items = parse_cse_response(_cse_payload(_CSE_ITEMS))
    assert [i["rank"] for i in items] == [1, 2, 3]

    structured = items[0]["prices"]
    assert {"price": 35698, "source": "pagemap", "verified": True} in structured

    snippet_only = items[1]["prices"]
    assert snippet_only == [{"price": 29800, "source": "snippet", "verified": False}]


# --------------------------------------------------------------------------- #
# 过滤：既不能漏，也不能过度
# --------------------------------------------------------------------------- #
def test_accessories_and_defectives_are_excluded():
    assert classify_exclusion("ブラウン FC94M シリーズ9Pro用 交換用替刃 網刃")[0] == "accessory"
    assert classify_exclusion("S9 Pro+ 9587cc 刃無し本体 新品未使用")[0] == "defective"
    assert classify_exclusion("替刃 2個セット") is not None


def test_filter_does_not_over_reject_real_products():
    """AirPods 的正式商品名里就带「充電ケース」—— 裸匹配 'ケース' 会把真商品判成配件。"""
    assert classify_exclusion("AirPods Pro 2 MagSafe充電ケース(USB-C)付き MTJV3J/A") is None
    assert classify_exclusion("【新品未開封】Braun シリーズ9 Pro+ 9517s-V メンズシェーバー") is None
    assert classify_exclusion("ブラウン シリーズ9 Pro 9450cc-V") is None


def test_partial_earbud_is_defective():
    """实测这条 ¥15,477 曾被当成"我方最低价"，直接刷出一个假胜利。"""
    assert classify_exclusion(
        "AirPods Pro 第2世代　右耳のみ　エアポッズプロ　Apple正規品新品"
    )[0] == "defective"
    assert classify_exclusion("AirPods Pro 片耳 左耳")[0] == "defective"


def test_conditional_case_rule():
    """「ケース」必须条件排除：它既可能是商品正式名的一部分，也可能是保护壳。"""
    # 商品本体（充電ケース付き = 正式名的一部分）→ 保留
    assert classify_exclusion("52●AirPods Pro 2 MagSafe充電ケース付き RI0605-2") is None
    # 保护壳 → 排除
    assert classify_exclusion("airpods pro ケース Bottega レッド ストーン")[0] == "accessory"


def test_case_brand_names_excluded_case_insensitively():
    """实测 "casetify ナルト Akatsuki AirPods pro 2 暁" 标题里根本没有「ケース」。"""
    assert classify_exclusion("casetify ナルト Akatsuki AirPods pro 2 暁")[0] == "accessory"
    assert classify_exclusion("CASETiFY スマホショルダーストラップ AirPods Pro")[0] == "accessory"


def test_price_floor_is_second_gate():
    # 关键词表永远补不全，价格下限兜底
    assert looks_like_body("よくわからない出品", price=900, floor_price=13754) is False
    assert looks_like_body("よくわからない出品", price=29333, floor_price=13754) is True


# --------------------------------------------------------------------------- #
# 从 trace 提取我方候选 + 构造公平 query
# --------------------------------------------------------------------------- #
def test_extract_our_items_covers_both_tools():
    items = extract_our_items(_trace())
    by_role = {}
    for it in items:
        by_role.setdefault(it["role"], []).append(it)

    assert len(by_role["searched"]) == 1
    assert by_role["searched"][0]["price"] == 39298
    assert by_role["searched"][0]["source"] == "kakaku.com"
    assert by_role["newer"][0]["price"] == 35698
    assert by_role["candidate"][0]["price"] == 29800
    assert len(by_role["listing"]) == 4
    assert all(it["source"] == "mercari" for it in by_role["listing"])

    # Mercari 乱标题里也要能猜出型番，用于和 Google 结果对齐
    m3 = next(it for it in by_role["listing"] if it["price"] == 29333)
    assert "9517sv" in m3["model_nos"]


def test_fair_query_uses_japanese_keyword_not_raw_chinese():
    """拿中文口语 query 打 Google 会赢得毫无意义 —— 必须用 agent 自己的日文关键词。"""
    assert build_fair_query(_trace()) == "ブラウン シリーズ9 Pro 最安値"


def test_fair_query_does_not_duplicate_price_intent():
    trace = [TraceStep(1, "get_new_and_newer_models", {"keyword": "ブラウン 最安値"},
                       True, "s", result_full="{}")]
    assert build_fair_query(trace) == "ブラウン 最安値"


def test_fair_query_falls_back_to_mercari_keyword():
    trace = [TraceStep(1, "search_mercari", {"keyword": "AirPods Pro 2"}, True, "s",
                       result_full="{}")]
    assert build_fair_query(trace) == "AirPods Pro 2 最安値"


def test_fair_query_none_when_no_keywords():
    assert build_fair_query([]) is None


def test_product_keyword_strips_price_suffix():
    assert product_keyword(_trace()) == "ブラウン シリーズ9 Pro"
    assert product_keyword([]) is None


# --------------------------------------------------------------------------- #
# 产品线闸：配件词表管不了"不同产品"
# --------------------------------------------------------------------------- #
def test_wrong_product_gate_excludes_different_generation():
    """AirPods 2 不是 AirPods Pro 2，混进来会拉低"我方最低价"一万多日元。"""
    required = required_product_tokens("AirPods Pro 第2世代")
    assert required == ["airpods", "pro", "第2世代"]

    assert matches_product("AirPods Pro（第2世代）新品・未開封 MTJV3J/A", required) is True
    assert matches_product("52●AirPods Pro 2 MagSafe充電ケース付き", required) is True
    assert matches_product("AirPods (第2世代) 早い者勝ち‼️", required) is False   # 缺 pro
    assert matches_product("AirPods 第二世代⭐︎新品⭐︎送料無料", required) is False


def test_wrong_product_gate_bridges_romaji_and_digit_forms():
    """不能因为写法不同就误杀真商品。"""
    required = required_product_tokens("ブラウン シリーズ9 Pro")
    # 标题写的是罗马字 Braun，不是 ブラウン
    assert matches_product("【新品未開封】Braun シリーズ9 Pro+ 9517s-V メンズシェーバー", required)
    # 标题写的是 S9 而不是 シリーズ9 —— 靠数字兜住
    assert matches_product("ブラウン最高峰S9 Pro 9467s-v 新品未使用", required)
    assert matches_product("パナソニック ラムダッシュ ES-LV9V", required) is False


def test_required_tokens_come_from_keyword_not_kakaku_series():
    """回归：曾用 kakaku 的 series 当 token 来源，撞上这种目录标题会产出 12 个 token，
    任何正常挂牌都匹配不全，把**所有** Mercari 商品都误杀。"""
    junk_series = (
        "Apple アップル 純正 AirPods Pro 第2世代 USB-C エアポッズプロ2 "
        "エアーポッズプロ2 メーカー保証付き ラッピング可"
    )
    assert len(required_product_tokens(junk_series)) > 8       # 说明它有多离谱
    assert matches_product("AirPods Pro（第2世代）新品・未開封", required_product_tokens(junk_series)) is False
    # 现在只用 agent 自己的关键词
    assert len(required_product_tokens("AirPods Pro 第2世代")) == 3


def test_gate_is_off_without_keyword():
    """没有关键词时不启用产品线闸 —— 宁可放过，也不要用垃圾 token 全杀。"""
    assert matches_product("随便什么标题", required_product_tokens(None)) is True


# --------------------------------------------------------------------------- #
# 打分
# --------------------------------------------------------------------------- #
def test_score_ignores_our_accessory_and_defective():
    """我方 ¥2,299 替刃 / ¥22,600 刃無し本体 都不能当"最低价"参赛。

    这组真实数值恰好也说明了 2% 阈值的作用：¥29,333 只比 ¥29,800 便宜 1.6%，
    算 tie 而不是 win —— 几十日元的差不该被记成胜利。
    """
    ours = extract_our_items(_trace())
    google = parse_cse_response(_cse_payload(_CSE_ITEMS))
    result = score(ours, google)

    assert result["our_min"] == 29333          # 不是 2299，也不是 22600
    assert result["our_best"]["source"] == "mercari"
    assert result["google_min"] == 29800       # 不是 2380（替刃页被排除）
    assert result["verdict"] == "tie"
    assert result["miss"] == []
    # 排除项要留痕，误排除才查得出来
    reasons = {e["excluded_by"] for e in result["our_excluded"]}
    assert {"accessory", "defective"} <= reasons
    assert any(e["excluded_by"] == "accessory" for e in result["google_excluded"])


def test_score_win_needs_margin_beyond_noise():
    ours = extract_our_items(_trace())
    pricey = dict(_CSE_ITEMS[0])
    pricey["pagemap"] = {"offer": [{"price": "35698"}]}   # 我方 29333 便宜 17.8%
    result = score(ours, parse_cse_response(_cse_payload([pricey])))
    assert result["verdict"] == "win"
    assert "便宜" in result["reason"]


def test_score_loss_when_google_has_cheaper_body():
    """漏项一票判负 —— 这是最有价值的信号。"""
    ours = extract_our_items(_trace())
    cheaper = dict(_CSE_ITEMS[0])
    cheaper["pagemap"] = {"offer": [{"price": "24800"}]}
    google = parse_cse_response(_cse_payload([cheaper]))
    result = score(ours, google)

    assert result["verdict"] == "loss"
    assert result["miss"][0]["price"] == 24800
    assert result["miss"][0]["link"]         # 能一眼核对是真漏还是误报
    assert "更便宜" in result["reason"]


def test_score_tie_within_margin():
    ours = extract_our_items(_trace())
    same = dict(_CSE_ITEMS[0])
    same["pagemap"] = {"offer": [{"price": "29400"}]}   # 与 29333 差距 < 2%
    result = score(ours, parse_cse_response(_cse_payload([same])))
    assert result["verdict"] == "tie"


def test_score_na_distinguishes_unknown_from_absence():
    """任一侧没有可比价格 → n/a，不能假装成 win。"""
    ours = extract_our_items(_trace())
    assert score(ours, [])["verdict"] == "n/a"
    assert score([], parse_cse_response(_cse_payload(_CSE_ITEMS)))["verdict"] == "n/a"


def test_coverage_rank_is_none_for_mercari_picks():
    """Google 几乎不索引单条 Mercari 商品页 → 排名为 None 是常态，不该因此算赢。"""
    ours = extract_our_items(_trace())
    google = parse_cse_response(_cse_payload(_CSE_ITEMS))
    result = score(ours, google)
    assert result["our_best"]["source"] == "mercari"
    assert result["our_pick_google_rank"] is None


def test_coverage_rank_found_by_url_match():
    """我方推荐正好是 Google 收录的 kakaku 页面 → 应报出它在 top-N 的排名。"""
    ours = [it for it in extract_our_items(_trace())
            if it.get("url") == "https://kakaku.com/item/K0001713159/"]
    google = parse_cse_response(_cse_payload(_CSE_ITEMS))
    result = score(ours, google)
    assert result["our_best"]["price"] == 35698
    assert result["our_pick_google_rank"] == 1


def test_coverage_rank_none_when_model_and_host_differ():
    """同域名但型番不同、或型番相同但域名不同 → 不算命中（避免虚假覆盖）。"""
    ours = [it for it in extract_our_items(_trace())
            if it.get("url") == "https://kakaku.com/item/K0001454549/"]   # 9435s-V
    google = parse_cse_response(_cse_payload(_CSE_ITEMS))
    # Google #1 是 kakaku 但机型是 9617s；#2 型番对得上但域名是 example.jp
    assert score(ours, google)["our_pick_google_rank"] is None


# --------------------------------------------------------------------------- #
# 可比性：同型番才谈得上"谁更便宜"
# --------------------------------------------------------------------------- #
def test_comparability_flags_different_model():
    """实测两次"近似同价"都不是同型号 —— 价差里混着规格差异。

    Braun: 我方 ¥29,333 是 2025 年 Pro+ 9517s-V；Google 最低 ¥29,800 是 2022 年 9435s-V。
    只看数字会得出"打平"，实际上该买我方那个（新三年、高一个等级）。
    """
    ours = extract_our_items(_trace())
    google = parse_cse_response(_cse_payload(_CSE_ITEMS))
    result = score(ours, google, keyword="ブラウン シリーズ9 Pro")

    assert result["our_best"]["model_nos"] == ["9517sv"]
    assert result["comparability"] == "different_model"
    assert "并非同一型番" in result["reason"]


def test_comparability_same_model():
    """双方最低价指向同一型番 → 价格可以直接比。"""
    ours = [it for it in extract_our_items(_trace())
            if it.get("url") == "https://kakaku.com/item/K0001713159/"]   # 9617s
    google = parse_cse_response(_cse_payload([_CSE_ITEMS[0]]))            # 也是 9617s
    result = score(ours, google, keyword="ブラウン シリーズ9 Pro")
    assert result["comparability"] == "same_model"
    assert "并非同一型番" not in result["reason"]


def test_comparability_unknown_when_model_no_absent():
    """Mercari 标题常常不写型番 —— 这种情况必须说"不知道"，不能假设是同款。"""
    ours = [{"source": "mercari", "role": "listing", "title": "ブラウン シリーズ9 Pro 新品未開封",
             "price": 28000, "url": "https://jp.mercari.com/item/x", "model_nos": []}]
    google = parse_cse_response(_cse_payload([_CSE_ITEMS[0]]))
    result = score(ours, google, keyword="ブラウン シリーズ9 Pro")
    assert result["comparability"] == "unknown"
    assert "未注明型番" in result["reason"]


def test_comparability_not_computed_without_both_sides():
    ours = extract_our_items(_trace())
    assert score(ours, [])["comparability"] == "unknown"


def test_floor_uses_searched_model_not_most_expensive():
    """用最贵变体推下限会误杀真便宜货（实测有 ¥22,600 的正品 Pro+）。"""
    ours = extract_our_items(_trace())
    result = score(ours, parse_cse_response(_cse_payload(_CSE_ITEMS)))
    assert result["floor_price"] == int(39298 * 0.35)   # 13754
    assert result["floor_price"] < 22600


# --------------------------------------------------------------------------- #
# 记录读写 + rescore
# --------------------------------------------------------------------------- #
def test_record_roundtrip_and_rescore(tmp_path):
    ours = extract_our_items(_trace())
    google = {"fair": {"query": "ブラウン シリーズ9 Pro 最安値",
                       "items": parse_cse_response(_cse_payload(_CSE_ITEMS))}}
    record = build_record("Braun Pro只买新品", "ブラウン シリーズ9 Pro 最安値", ours, google)
    assert record["source"] == "google_cse"        # CSE ≠ google.com，别混
    assert record["comparisons"]["fair"]["verdict"] == "tie"

    path = tmp_path / "b" / "google_compare.jsonl"
    append_record(path, record)
    append_record(path, record)
    loaded = load_records(path)
    assert len(loaded) == 2

    # 原始结果都在，所以能重算 —— 改了判定标准不会丢历史
    again = rescore_record(loaded[0])
    assert again["comparisons"]["fair"]["verdict"] == "tie"
    assert again["our_items"] == loaded[0]["our_items"]


def test_load_records_tolerates_garbage(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"ts":"a","comparisons":{}}\n{ broken\n\n', encoding="utf-8")
    assert len(load_records(path)) == 1


def test_summarize_counts_verdicts():
    recs = [
        {"comparisons": {"fair": {"verdict": "win"}}},
        {"comparisons": {"fair": {"verdict": "loss"}}},
        {"comparisons": {"fair": {"verdict": "win"}}},
        {"comparisons": {"fair": {"verdict": "n/a"}}},
    ]
    stats = summarize(recs, key="fair")
    assert (stats["win"], stats["loss"], stats["n/a"]) == (2, 1, 1)
    assert stats["decided"] == 3
    assert stats["win_rate"] == round(2 / 3, 3)


def test_google_error_becomes_na_not_win():
    record = build_record(
        "q", None, extract_our_items(_trace()),
        {"raw": {"query": "q", "items": [], "error": "HTTP 429: quota"}},
    )
    comp = record["comparisons"]["raw"]
    assert comp["verdict"] == "n/a"
    assert "429" in comp["reason"]


# --------------------------------------------------------------------------- #
# 失败隔离 + 无污染
# --------------------------------------------------------------------------- #
class _FakeGoogle:
    """记录被搜了什么；可注入失败。"""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.queries = []
        self.configured = True

    async def search(self, query):
        self.queries.append(query)
        if self.error:
            return {"query": query, "items": [], "error": self.error}
        return {"query": query, "items": parse_cse_response(_cse_payload(self.payload or []))}


@pytest.mark.asyncio
async def test_compare_does_not_contaminate_agent_result(tmp_path):
    """**核心约束**：对照绝不能回写 messages —— 否则模型下次会抄 Google 的数字。"""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Braun Pro只买新品"},
        {"role": "assistant", "content": "done"},
    ]
    result = AgentResult(answer="推荐 ...", trace=_trace(), iterations=3,
                         notes=[], messages=messages)
    before = json.dumps(result.messages, ensure_ascii=False)

    svc = BenchmarkService(_FakeGoogle(_CSE_ITEMS), tmp_path / "b.jsonl")
    record = await svc.compare("Braun Pro只买新品", result)

    assert json.dumps(result.messages, ensure_ascii=False) == before
    assert len(result.messages) == 3
    assert "google" not in before.lower()
    assert record["comparisons"]["fair"]["verdict"] == "tie"


@pytest.mark.asyncio
async def test_compare_queries_both_raw_and_fair(tmp_path):
    google = _FakeGoogle(_CSE_ITEMS)
    result = AgentResult(answer="a", trace=_trace(), iterations=2)
    record = await BenchmarkService(google, tmp_path / "b.jsonl").compare("Braun Pro只买新品", result)

    assert google.queries == ["Braun Pro只买新品", "ブラウン シリーズ9 Pro 最安値"]
    assert set(record["comparisons"]) == {"raw", "fair"}


@pytest.mark.asyncio
async def test_compare_skips_duplicate_query_to_save_quota(tmp_path):
    trace = [TraceStep(1, "get_new_and_newer_models", {"keyword": "AirPods Pro 2 最安値"},
                       True, "s", result_full=json.dumps(_model_compare_result()))]
    google = _FakeGoogle(_CSE_ITEMS)
    result = AgentResult(answer="a", trace=trace)
    await BenchmarkService(google, tmp_path / "b.jsonl").compare("AirPods Pro 2 最安値", result)
    assert google.queries == ["AirPods Pro 2 最安値"]   # 只打一次


@pytest.mark.asyncio
async def test_api_failure_is_recorded_not_raised(tmp_path):
    google = _FakeGoogle(error="HTTP 429: quota exceeded")
    result = AgentResult(answer="a", trace=_trace())
    record = await BenchmarkService(google, tmp_path / "b.jsonl").compare("q", result)

    assert record["google"]["raw"]["error"].startswith("HTTP 429")
    assert record["comparisons"]["raw"]["verdict"] == "n/a"
    assert load_records(tmp_path / "b.jsonl")      # 依然落盘，便于事后看失败率


@pytest.mark.asyncio
async def test_missing_credentials_is_disabled_not_error():
    client = GoogleCseClient(api_key=None, cse_id=None)
    assert client.configured is False
    out = await client.search("anything")
    assert out["items"] == []
    assert "未配置" in out["error"]
    assert BenchmarkService(client, Path("unused.jsonl")).enabled is False


def test_cert_error_detected_through_exception_chain():
    """httpx 把 ssl.SSLCertVerificationError 包成 ConnectError ——
    直接 `except ssl.SSLCertVerificationError` 抓不到，那条可读提示会静默失效。"""
    import ssl as _ssl

    import httpx as _httpx

    from kaidoki.infrastructure.search.google_search import _is_cert_error

    inner = _ssl.SSLCertVerificationError("certificate verify failed")
    wrapped = _httpx.ConnectError("boom")
    wrapped.__cause__ = inner
    assert _is_cert_error(wrapped) is True
    assert _is_cert_error(inner) is True

    # 纯文本匹配也要兜住（有些包装会丢掉异常链）
    assert _is_cert_error(RuntimeError("[SSL: CERTIFICATE_VERIFY_FAILED] ...")) is True
    assert _is_cert_error(_httpx.ConnectTimeout("timeout")) is False


@pytest.mark.asyncio
async def test_empty_query_short_circuits():
    client = GoogleCseClient(api_key="k", cse_id="c")
    out = await client.search("   ")
    assert out["items"] == [] and out["error"]
