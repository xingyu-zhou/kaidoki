"""
get_new_and_newer_models 工具单测（零网络 / 零真实 LLM / 零浏览器）。

覆盖：
- 工具输出结构（searched_model / newer_models / newer_lookup / currency）
- 多 backend 依次尝试：第一个 None 时落到第二个
- backend 抛异常不崩、全都拿不到时返回 note（不崩）
- 空 keyword 不崩
- KakakuBackend 的搜索页解析 + 选型 + 新旧判定（喂预设 HTML，不触网）
- **回归**：真实 "Braun Pro" 数据下的两个历史 bug
    1) 跨语种 token 匹配失效 → 打分退化成"名字最短者胜" → 选中 3 店的三年前旧机型
    2) family 锚点用英文 token → newer 恒为空 → 把"匹配失败"报成"没有更新型号"
- 工具已注册进 registry（include_model_compare=True 时）
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.tools.model_compare import (  # noqa: E402
    GetNewAndNewerModelsTool,
    KakakuBackend,
    _family_of,
    _split_name,
    _token_variants,
)
from kaidoki.tools.mercari_tools import build_mercari_tool_registry  # noqa: E402


# --------------------------------------------------------------------------- #
# 替身 backend
# --------------------------------------------------------------------------- #
class _FakeBackend:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def lookup(self, keyword):
        self.calls.append(keyword)
        return self._result


class _NoneBackend:
    def __init__(self):
        self.calls = []

    async def lookup(self, keyword):
        self.calls.append(keyword)
        return None


class _BoomBackend:
    def __init__(self):
        self.calls = []

    async def lookup(self, keyword):
        self.calls.append(keyword)
        raise RuntimeError("backend 炸了")


class _FakeScraper:
    """build_mercari_tool_registry 只需要一个占位 scraper 对象。"""

    scraper = None


_PRESET = {
    "searched_model": {"name": "Bambu Lab A1 mini", "new_price_min": 26000, "source": "us.store.bambulab.com"},
    "newer_models": [
        {"name": "Bambu Lab A2L", "new_price_min": 64800, "note": "A 系列更新机型"},
    ],
    "currency": "JPY",
}


# --------------------------------------------------------------------------- #
# 工具编排 / 输出结构
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_returns_expected_structure():
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])
    result = await tool.call(keyword="Bambu A1 mini")

    assert result.is_success()
    data = result.data
    assert data["keyword"] == "Bambu A1 mini"
    assert data["currency"] == "JPY"
    assert data["searched_model"]["name"] == "Bambu Lab A1 mini"
    assert data["searched_model"]["new_price_min"] == 26000
    assert "source" in data["searched_model"]
    assert data["newer_models"][0]["name"] == "Bambu Lab A2L"
    assert data["newer_models"][0]["new_price_min"] == 64800
    assert "note" in data["newer_models"][0]


@pytest.mark.asyncio
async def test_missing_newer_lookup_defaults_to_unknown():
    """backend 没表态 → 一律按"不知道"处理，绝不让缺失被读成"没有更新型号"。"""
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])  # _PRESET 里没有 newer_lookup
    result = await tool.call(keyword="Bambu A1 mini")
    assert result.data["newer_lookup"] == "unknown"
    assert result.data["newer_lookup_reason"]


@pytest.mark.asyncio
async def test_falls_through_to_second_backend():
    first, second = _NoneBackend(), _FakeBackend(_PRESET)
    tool = GetNewAndNewerModelsTool([first, second])
    result = await tool.call(keyword="Bambu A1 mini")

    assert result.is_success()
    assert result.data["searched_model"]["name"] == "Bambu Lab A1 mini"
    assert first.calls == ["Bambu A1 mini"]  # 第一个被试过
    assert second.calls == ["Bambu A1 mini"]  # 落到第二个


@pytest.mark.asyncio
async def test_backend_exception_does_not_crash():
    boom, good = _BoomBackend(), _FakeBackend(_PRESET)
    tool = GetNewAndNewerModelsTool([boom, good])
    result = await tool.call(keyword="Bambu A1 mini")

    assert result.is_success()  # 异常被吞，落到下一个 backend
    assert result.data["searched_model"]["name"] == "Bambu Lab A1 mini"
    assert boom.calls == ["Bambu A1 mini"]


@pytest.mark.asyncio
async def test_no_data_returns_note():
    tool = GetNewAndNewerModelsTool([_NoneBackend(), _NoneBackend()])
    result = await tool.call(keyword="完全不存在的型号")

    assert result.is_success()
    assert "searched_model" not in result.data
    assert result.data["note"] == "未获取到新品/新型号数据"
    assert result.data["newer_lookup"] == "unknown"
    assert result.data["currency"] == "JPY"


@pytest.mark.asyncio
async def test_empty_keyword_does_not_crash():
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])
    result = await tool.call(keyword="   ")
    assert result.is_success()
    assert result.data["note"] == "未获取到新品/新型号数据"
    assert result.data["newer_lookup"] == "unknown"


@pytest.mark.asyncio
async def test_absorbs_extra_args():
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])
    result = await tool.call(keyword="Bambu A1 mini", bogus="x", extra=1)
    assert result.is_success()


# --------------------------------------------------------------------------- #
# 名称拆解 / 产品线归并 / 品牌别名
# --------------------------------------------------------------------------- #
def test_split_name_extracts_series_and_model_no():
    assert _split_name("ブラウン シリーズ9 Pro 9435s-V") == ("ブラウン シリーズ9 Pro", "9435sv")
    assert _split_name("ブラウン シリーズ9 Pro+ 9660cc [マットブラック]") == (
        "ブラウン シリーズ9 Pro+", "9660cc",
    )
    # 纯数字代际（"3"）留在 series 里，不当型番剥掉
    assert _split_name("AirPods Pro 3 MFHP4J/A") == ("AirPods Pro 3", "mfhp4ja")
    # 半角括号出现在名称中段，不能连带吃掉后面的型番
    assert _split_name("AirPods Pro 2 MagSafe充電ケース(USB-C)付き MTJV3J/A")[1] == "mtjv3ja"


def test_family_merges_tier_suffix():
    # Pro 与 Pro+ 必须归到同一 family，否则 Pro+ 不会被认成 Pro 的更新机型
    assert _family_of("ブラウン シリーズ9 Pro") == "ブラウン シリーズ9"
    assert _family_of("ブラウン シリーズ9 Pro+") == "ブラウン シリーズ9"
    assert _family_of("ブラウン シリーズ9 Sport+") == "ブラウン シリーズ9"
    assert _family_of("ブラウン シリーズ9") == "ブラウン シリーズ9"
    assert _family_of("AirPods Pro 3") == "AirPods"


def test_brand_alias_bridges_romaji_and_japanese():
    # 历史 bug 的根因：kakaku 机型名是 "ブラウン…"，英文 token "braun" 恒不命中
    assert "ブラウン" in _token_variants("braun")
    assert "braun" in _token_variants("ブラウン")


# --------------------------------------------------------------------------- #
# KakakuBackend 解析（喂预设 HTML，不触网）
# --------------------------------------------------------------------------- #
def _row(kcode, name, price, release=None, shops=None, maker="ブラウン",
         category="シェーバー"):
    """目录机型行。class 名照抄真实 kakaku 搜索页 —— `p-item_maker` / `p-item_date` /
    `p-item_shopCounts` 是"这是目录行"的结构标记，解析器靠它区分单店购物行。"""
    rel = f'<p class="p-item_date">発売日：{release}</p>' if release else ""
    sh = (
        f'<span class="p-item_shopCounts">（全 '
        f'<span class="p-item_shopCounts_num">{shops}</span> 店舗）</span>'
        if shops is not None else ""
    )
    return f"""
<div class="p-resultItem_in p-item">
  <p class="p-item_maker">{maker}</p>
  <p class="p-item_name"> <a href="/item/{kcode}/">{name}</a></p>
  {rel}
  <span class="p-item_category">{category}</span>
  <span class="p-item_spec">刃の枚数 4枚刃</span>
  <span class="p-item_price c-num">¥<span class="p-item_priceNum is-value">{price}</span></span>
  {sh}
</div>"""


def _shop_row(kcode, name, price):
    """单店购物行:**也带 /item/K.../ 链接**，但没有目录结构标记。

    实测 "ニコン D850" 页面上 35 个带 K 链接的行里有 29 个是这种；其中
    "ニコン Nikon D850 ボディ D850" 报某一家店的 ¥327,834，而目录最安値是 ¥279,980。
    """
    return f"""
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a href="/item/{kcode}/">{name}</a></p>
  <p class="p-item_summary">送料無料 あす楽対応 メーカー保証付き</p>
  <span class="p-item_price c-num">¥<span class="p-item_priceNum is-value">{price}</span></span>
  <a class="p-resultItem_btnLink" href="/shop/">ショップへ</a>
</div>"""


def _page(rows, total_hits=None):
    hits = f"<p>{total_hits} 件中 1〜40件</p>" if total_hits else ""
    return "<html><body>" + hits + "".join(rows) + "</body></html>"


# 真实数据（2026-08 的 kakaku "Braun Pro" 搜索页；価格/発売日/店舗数均照抄）。
# 刻意把最新的 Pro+ 9660cc 放在**最后一行**：页面顺序是人気順，不能用来判断新旧。
_BRAUN_HTML = _page(
    [
        _row("K0001454549", "ブラウン シリーズ9 Pro 9435s-V", "29,800", "2022年9月", 3),
        _row("K0001557158", "ブラウン シリーズ9 Pro+ 9537s [マットシルバー]", "28,800", "2023年8月", 8),
        _row("K0001490278", "ブラウン シリーズ9 Pro 9450cc-V", "39,298", "2022年9月", 6),
        _row("K0001541614", "ブラウン シリーズ9 Pro 9455cc-V", "29,999", None, 3),
        _row("K0001652259", "ブラウン シリーズ9 Pro+ 9556cc-V [メタリックシルバー]", "34,012", "2024年8月", 8),
        _row("K0001713157", "ブラウン シリーズ9 Pro+ 9660cc [マットブラック]", "45,959", "2025年11月", 20),
    ],
    total_hits=674,
)

# 结构模仿 kakaku 搜索页结果行（発売日：Pro 3 最新、Pro 最老）。
_KAKAKU_HTML = _page(
    [
        _row("K0001709588", "AirPods Pro 3 MFHP4J/A", "32,999", "2025年9月", 33, maker="アップル",
             category="イヤホン・ヘッドホン"),
        _row("K0001566951", "AirPods Pro 2 MTJV3J/A", "28,498", "2023年9月", 13, maker="アップル",
             category="イヤホン・ヘッドホン"),
        _row("K0001206017", "AirPods Pro MWP22J/A", "29,800", "2019年10月", 5, maker="アップル",
             category="イヤホン・ヘッドホン"),
        # 无 /item/K.../ = 购物列表行，必须被跳过
        """
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a>互換 保護ケース for AirPods</a></p>
  <span class="p-item_priceNum is-value">980</span>
</div>""",
    ]
)


class _CannedKakaku(KakakuBackend):
    """用预设 HTML 替换真实网络抓取。"""

    def __init__(self, text):
        super().__init__(delay_seconds=0.0)
        self._text = text

    async def _fetch_text(self, url):
        return self._text


@pytest.mark.asyncio
async def test_kakaku_parses_catalog_models():
    backend = _CannedKakaku(_KAKAKU_HTML)
    res = await backend.lookup("AirPods Pro")

    assert res is not None
    # "AirPods Pro"（无代际数字）→ 被搜机型 = series 恰好等于关键词的那一款
    assert res["searched_model"]["name"] == "AirPods Pro MWP22J/A"
    assert res["searched_model"]["new_price_min"] == 29800
    assert res["searched_model"]["source"] == "kakaku.com"
    # 発売日更新的同产品线机型 = 更新机型
    newer_names = [m["name"] for m in res["newer_models"]]
    assert "AirPods Pro 3 MFHP4J/A" in newer_names
    assert "AirPods Pro 2 MTJV3J/A" in newer_names
    assert res["newer_lookup"] == "ok"
    assert res["currency"] == "JPY"


@pytest.mark.asyncio
async def test_kakaku_specific_model_has_no_newer():
    backend = _CannedKakaku(_KAKAKU_HTML)
    res = await backend.lookup("AirPods Pro 3")
    # 已是最新一代 → 没有更新机型，且这个"没有"是真的比较过発売日得出的
    assert res["searched_model"]["name"] == "AirPods Pro 3 MFHP4J/A"
    assert res["newer_models"] == []
    assert res["newer_lookup"] == "ok"


@pytest.mark.asyncio
async def test_kakaku_non_catalog_returns_none():
    # 无 /item/K.../ 行（纯购物列表）→ 交给下一级 backend
    backend = _CannedKakaku("<html><body><div>no catalog items</div></body></html>")
    assert await backend.lookup("Bambu A1 mini") is None


# --------------------------------------------------------------------------- #
# 回归：真实 "Braun Pro" 数据
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_braun_pro_selects_by_evidence_not_name_length():
    """历史 bug：'braun' 匹配不上 'ブラウン' → 打分退化成"名字最短者胜" → 选中
    3 店的 9435s-V（2022-09、¥29,800，搜索页排第 29 名，用户自己根本找不到）。"""
    res = await _CannedKakaku(_BRAUN_HTML).lookup("Braun Pro")

    s = res["searched_model"]
    # 必须落在 "シリーズ9 Pro" 这条线上（而不是 Pro+）
    assert s["series"] == "ブラウン シリーズ9 Pro"
    # 同代（2022-09）里在售店舗更多的那台胜出，不再是只剩 3 店的 9435s-V
    assert s["shops"] == 6
    assert "9435s-V" not in s["name"]
    assert s["new_price_min"] == 39298


@pytest.mark.asyncio
async def test_braun_pro_finds_newer_models_despite_page_order():
    """历史 bug：family 锚点取最长英文 token（"braun"），对日文名恒不命中
    → newer_models 恒为 [] → 模型把它读成"没有后继型号"（実际有 Pro+ 9660cc）。

    同时验证不靠页面顺序：9660cc 在 fixture 里是**最后一行**。
    """
    res = await _CannedKakaku(_BRAUN_HTML).lookup("Braun Pro")

    assert res["newer_lookup"] == "ok"
    newer = [m["name"] for m in res["newer_models"]]
    assert any("9660cc" in n for n in newer), newer
    assert any("9537s" in n for n in newer), newer
    # 更新机型按発売日倒序（最新在前）
    assert res["newer_models"][0]["release"] == "2025-11"
    # Pro+ 与 Pro 同 family、不同 series
    assert res["newer_models"][0]["relation"] == "same_family"


@pytest.mark.asyncio
async def test_entries_are_verifiable_and_flag_staleness():
    """每个机型都要能被用户核对（url），旧型号/店舗过少要主动示警。"""
    res = await _CannedKakaku(_BRAUN_HTML).lookup("ブラウン シリーズ9 Pro 9435s-V")

    s = res["searched_model"]
    assert s["confidence"] == "high"          # 关键词带型番 → 高置信
    assert s["url"] == "https://kakaku.com/item/K0001454549/"
    assert s["release"] == "2022-09"
    assert s["shops"] == 3
    assert any("旧型号" in w for w in s["warnings"])
    assert any("店" in w for w in s["warnings"])
    for m in res["newer_models"]:
        assert m["url"].startswith("https://kakaku.com/item/")
    # 覆盖范围要交代清楚（只解析了第 1 页）
    assert res["coverage"]["total_hits_reported"] == 674
    assert res["coverage"]["catalog_models_parsed"] == 6


@pytest.mark.asyncio
async def test_low_confidence_exposes_candidates():
    """关键词笼统 → 置信度不为 high 时，必须把其它候选交出来，而不是硬报一个价。"""
    res = await _CannedKakaku(_BRAUN_HTML).lookup("Braun Pro")
    assert res["searched_model"]["confidence"] in ("medium", "low")
    names = [c["name"] for c in res["candidates"]]
    assert any("9435s-V" in n for n in names), names


@pytest.mark.asyncio
async def test_unknown_release_reports_unknown_not_absence():
    """被搜机型発売日未知 → 只能说"未能确认"，不能说"没有更新型号"。"""
    res = await _CannedKakaku(_BRAUN_HTML).lookup("ブラウン シリーズ9 Pro 9455cc-V")
    assert res["searched_model"]["release"] is None
    assert res["newer_lookup"] == "unknown"
    assert "発売日" in res["newer_lookup_reason"]


@pytest.mark.asyncio
async def test_single_model_in_family_is_unknown_not_absence():
    """同产品线只找到 1 个机型 → 无从比较，必须是 unknown。"""
    html = _page([_row("K0001713157", "ブラウン シリーズ9 Pro+ 9660cc", "45,959", "2025年11月", 20)])
    res = await _CannedKakaku(html).lookup("ブラウン シリーズ9 Pro+ 9660cc")
    assert res["newer_models"] == []
    assert res["newer_lookup"] == "unknown"


@pytest.mark.asyncio
async def test_cross_family_newer_model_blocks_false_absence():
    """自检：同 family 内没有更新机型，但搜索结果里有更新的相关机型
    → 说明产品线归类可能切错了，不许报"无后继"。"""
    html = _page([
        _row("K1", "ブラウン シリーズ8 8390cc", "20,000", "2021年8月", 5),
        _row("K2", "ブラウン シリーズ8 8330s", "18,000", "2021年8月", 4),
        _row("K3", "ブラウン シリーズ9 Pro+ 9660cc", "45,959", "2025年11月", 20),
    ])
    res = await _CannedKakaku(html).lookup("ブラウン シリーズ8 8390cc")
    assert res["newer_models"] == []
    assert res["newer_lookup"] == "unknown"
    assert "9660cc" in res["newer_lookup_reason"]


# --------------------------------------------------------------------------- #
# 回归：单店购物行冒充目录机型（真实 "ニコン D850" 数据）
# --------------------------------------------------------------------------- #
# 实测该页 35 个带 /item/K.../ 的行里有 29 个是单店购物行。旧实现全当目录机型，
# 于是被搜机型选中了一条店铺文案标题、报出该店 ¥327,834（目录最安値 ¥279,980），
# 且因为购物行没有発売日/店舗数，"旧型号"警告整个失效。
_D850_HTML = _page(
    [
        _shop_row("K0000991223", "【送料無料】Nikon ニコン D850ボディ一眼レフデジカメ", "349,800"),
        _shop_row("K0000991223", "ニコン Nikon D850 ボディ D850", "327,834"),
        _shop_row("K0000991223", "【長期保証付】ニコン Nikon D850 ボディ D850", "331,000"),
        _row("K0000991223", "D850 ボディ", "279,980", "2017年9月", 27, maker="ニコン",
             category="デジタル一眼カメラ"),
        _row("K0001521905", "Z8 ボディ", "489,800", "2023年5月", 31, maker="ニコン",
             category="デジタル一眼カメラ"),
        _row("K0000940516", "KLP-ND850", "883", "2017年9月", 4, maker="ケンコー",
             category="液晶保護フィルム"),
    ],
    total_hits=738,
)


@pytest.mark.asyncio
async def test_shop_listing_rows_do_not_masquerade_as_catalog_models():
    res = await _CannedKakaku(_D850_HTML).lookup("ニコン D850")

    s = res["searched_model"]
    # 必须是目录行的最安値，而不是某一家店的报价
    assert s["name"] == "D850 ボディ"
    assert s["new_price_min"] == 279980
    assert s["new_price_min"] != 327834
    # 购物行没有这两项，所以旧实现拿不到；目录行有
    assert s["release"] == "2017-09"
    assert s["shops"] == 27
    # 型番在名称**开头**时也要能命中（旧实现只剥尾部 → 型番为空 → 输给购物行）
    assert s["confidence"] == "high"
    # 2017 年的机型 → 鲜度警告必须触发（这正是之前失效的地方）
    assert any("旧型号" in w for w in s["warnings"])


@pytest.mark.asyncio
async def test_single_family_unknown_still_reports_newer_related_models():
    """同 family 只有它自己时，也要把"页面上有更新的相关机型"说出来。

    只回一句"只找到 1 个机型"对用户没用 —— D850 的后继其实在 Z 系列（不同产品线）。
    """
    res = await _CannedKakaku(_D850_HTML).lookup("ニコン D850")
    assert res["newer_lookup"] == "unknown"
    assert "Z8" in res["newer_lookup_reason"]
    assert "2023-05" in res["newer_lookup_reason"]
    # 必须限定同厂商：搜索页里混着第三方配件（ケンコー 的 D850 用保护膜，2018-05 发售），
    # 不加过滤就会把一张保护膜当成"D850 的更新机型"提示给用户。
    assert "KLP" not in res["newer_lookup_reason"]


@pytest.mark.asyncio
async def test_price_basis_is_stated_in_the_data_contract():
    """「最安値」≠「实际支付额」。这个前提必须写进数据契约，不能只写在 prompt 里 ——
    实测 Braun 有 ¥3,500 的本体+替刃キャッシュバック(占 ¥43,960 的 8%)，
    楽天ポイント最高 50% 还元而 kakaku 完全不计入。任何"便宜了多少"不带这个前提就是错的。"""
    res = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro+")
    assert res["price_basis"] == "cash_lowest_excl_campaigns"
    assert "キャッシュバック" in res["price_basis_note"]
    assert "ポイント" in res["price_basis_note"]


def test_model_no_candidates_finds_leading_model_number():
    from kaidoki.tools.model_compare import _model_no_candidates

    assert _model_no_candidates("D850 ボディ") == ["d850"]
    assert _model_no_candidates("ブラウン シリーズ9 Pro 9435s-V") == ["9435sv"]
    assert _model_no_candidates("AirPods Pro 3 MFHP4J/A") == ["mfhp4ja"]
    # "シリーズ9"(片假名+数字) 与 "Pro"(无数字) 都不是型番
    assert "シリーズ9" not in _model_no_candidates("ブラウン シリーズ9 Pro")


# --------------------------------------------------------------------------- #
# 回归：Pro 与 Pro+ 是不同世代；cc / s 是不同配置
# --------------------------------------------------------------------------- #
_PLUS_HTML = _page(
    [
        _row("K1", "ブラウン シリーズ9 Pro 9450cc-V", "39,298", "2022年9月", 6),
        _row("K2", "ブラウン シリーズ9 Pro+ 9617s [マットシルバー]", "35,698", "2025年11月", 19),
        _row("K3", "ブラウン シリーズ9 Pro+ 9657cc [マットシルバー]", "43,999", "2025年11月", 21),
        _row("K4", "ブラウン シリーズ9 Pro+ 9660cc [マットブラック]", "45,863", "2025年11月", 18),
    ]
)


@pytest.mark.asyncio
async def test_plus_tier_is_not_confused_with_base_tier():
    """历史 bug：`_tokens` 把 `+` 当标点删掉 → 查 "Pro+" 命中了 2022 年的 "Pro"。"""
    res = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro+")
    assert res["searched_model"]["series"] == "ブラウン シリーズ9 Pro+"
    assert res["searched_model"]["release"] == "2025-11"

    # 反向：查 "Pro" 不应被 "Pro+" 抢走
    res2 = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro")
    assert res2["searched_model"]["series"] == "ブラウン シリーズ9 Pro"


@pytest.mark.asyncio
async def test_cleaning_station_intent_prefers_cc_variant():
    """要洗浄器付き时不能选到本体のみ —— 9617s(¥35,698) 比 9657cc(¥43,999) 便宜八千，
    但它不含洗浄器，混着比价会让用户以为省了钱。"""
    res = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro+ 洗浄器付き")
    s = res["searched_model"]
    assert s["variant"] == "with_cleaning_station"
    assert "9657cc" in s["name"] or "9660cc" in s["name"]

    body = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro+ 本体のみ")
    assert body["searched_model"]["variant"] == "body_only"


@pytest.mark.asyncio
async def test_variant_is_exposed_on_every_entry():
    """每个条目都带 variant，模型才能只拿同配置的互相比价。"""
    res = await _CannedKakaku(_PLUS_HTML).lookup("ブラウン シリーズ9 Pro")
    variants = {m["name"]: m["variant"] for m in res["newer_models"]}
    assert variants["ブラウン シリーズ9 Pro+ 9617s [マットシルバー]"] == "body_only"
    assert variants["ブラウン シリーズ9 Pro+ 9657cc [マットシルバー]"] == "with_cleaning_station"


def test_variant_only_applies_to_shavers():
    """cc/s 后缀只在シェーバー品类里有"洗浄器"的含义，对相机乱套会胡说。"""
    from kaidoki.tools.model_compare import _variant_of

    assert _variant_of("9660cc", "シェーバー") == "with_cleaning_station"
    assert _variant_of("9617s", "シェーバー") == "body_only"
    assert _variant_of("9660cc", "デジタル一眼カメラ") is None
    assert _variant_of("d850", "シェーバー") is None
    assert _variant_of("9660cc", None) is None


@pytest.mark.asyncio
async def test_noisy_keyword_falls_back_to_core_keyword():
    """关键词塞了规格/意图词时 kakaku 会 0 结果（实测 "…Pro+ 洗浄器付き cc" 就是）。
    降级成"品牌+系列+型番"重试，省掉一整轮 agent 往返。"""
    calls = []

    class _TwoStage(KakakuBackend):
        def __init__(self):
            super().__init__(delay_seconds=0.0)

        async def _fetch_text(self, url):
            calls.append(url)
            # 只有降级后的核心关键词才返回结果
            return _PLUS_HTML if "%E6%B4%97" not in url else "<html><body></body></html>"

    res = await _TwoStage().lookup("ブラウン シリーズ9 Pro+ 洗浄器付き cc 新品 最安値")
    assert res is not None
    assert len(calls) == 2                                  # 原词 + 降级重试
    assert res["searched_model"]["variant"] == "with_cleaning_station"  # 意图仍从原词读


def test_core_keyword_strips_spec_and_intent_words():
    from kaidoki.tools.model_compare import _core_keyword

    assert _core_keyword("ブラウン シリーズ9 Pro+ 洗浄器付き cc 新品 最安値") == "ブラウン シリーズ9 Pro+"
    # 助词残渣无所谓（只用于降级重试的检索词），要紧的是品牌+型番留住、噪声词去掉
    core = _core_keyword("ニコン D850 中古と新品どっちが買い？")
    assert "ニコン" in core and "D850" in core
    assert "中古" not in core and "新品" not in core
    # 已经很干净的关键词不该被改动（否则会白搭一次请求）
    assert _core_keyword("ブラウン シリーズ9 Pro") == "ブラウン シリーズ9 Pro"


# --------------------------------------------------------------------------- #
# 注册进 registry
# --------------------------------------------------------------------------- #
def test_tool_registered_when_enabled():
    reg = build_mercari_tool_registry(
        _FakeScraper(),
        include_model_compare=True,
        model_compare_backends=[_FakeBackend(_PRESET)],
    )
    assert "get_new_and_newer_models" in reg.list_tools()


def test_tool_absent_by_default():
    # 默认不注册，保持既有 registry 行为不变
    reg = build_mercari_tool_registry(_FakeScraper())
    assert "get_new_and_newer_models" not in reg.list_tools()
