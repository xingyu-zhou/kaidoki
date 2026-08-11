"""
成色（condition）过滤单测：Mercari 的「新品・未使用」这条腿必须真的走通。

背景（真实踩坑）：用户问 "Braun Pro 只买新品"，agent 一次都没查 Mercari —— 因为
prompt/工具描述把 Mercari 定义成"二手平台"。而 Mercari 上「新品・未使用」= 全新未拆封，
実測比 kakaku 的新品最安値更便宜。另外旧实现对非法 condition **静默丢弃**
（`condition if condition in ENUM else None`），模型传 "新品" 就退化成无过滤搜索且毫无提示。

覆盖：
- _normalize_conditions：字符串 / 数组 / 逗号串 / 非法值 / 去重
- 非法 condition → 显式报错（不静默降级成无过滤搜索）
- 多选成色 → item_condition_id=1,2 真的进到搜索 URL 里
- 返回里回显 condition_filter（trace 可见实际生效的过滤条件）
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kaidoki.tools.mercari_tools import (  # noqa: E402
    PriceStatisticsTool,
    SearchMercariTool,
    _normalize_conditions,
)
from kaidoki.infrastructure.scraping.scraper_service import (  # noqa: E402
    PlaywrightMercariScraper,
    SearchParameterProcessor,
)
from kaidoki.shared.config.app_config import AppConfig  # noqa: E402
from kaidoki.domain.entities.product import ProductEntity  # noqa: E402
from kaidoki.domain.entities.query import QueryEntity  # noqa: E402


class _FakeScraping:
    def __init__(self, products):
        self.products = products
        self.total_found = len(products)


class _RecordingScraper:
    """记录收到的 QueryEntity，验证 condition 有没有真的传下去。"""

    def __init__(self, products=None):
        self.queries = []
        self._products = products if products is not None else [
            ProductEntity(id="m1", title="ブラウン シリーズ9 Pro+ 9517s-V 新品未開封",
                          price=29333, condition="新品・未使用",
                          url="https://jp.mercari.com/item/m1"),
        ]

    async def scrape(self, query, max_products=10):
        self.queries.append(query)
        return _FakeScraping(self._products)


# --------------------------------------------------------------------------- #
# 归一化
# --------------------------------------------------------------------------- #
def test_normalize_accepts_string_list_and_comma():
    assert _normalize_conditions("新品・未使用") == (["新品・未使用"], [])
    assert _normalize_conditions(["新品・未使用", "未使用に近い"]) == (
        ["新品・未使用", "未使用に近い"], [],
    )
    assert _normalize_conditions("新品・未使用,未使用に近い") == (
        ["新品・未使用", "未使用に近い"], [],
    )
    assert _normalize_conditions(None) == ([], [])


def test_normalize_dedupes_and_reports_invalid():
    valid, invalid = _normalize_conditions(["新品・未使用", "新品・未使用", "新品", "未使用"])
    assert valid == ["新品・未使用"]
    assert invalid == ["新品", "未使用"]


# --------------------------------------------------------------------------- #
# 非法值：报错，不静默降级
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_invalid_condition_errors_instead_of_silently_unfiltering():
    scraper = _RecordingScraper()
    tool = SearchMercariTool(scraper)
    res = await tool.call(keyword="ブラウン", condition=["新品"])

    assert not res.is_success()
    assert "新品" in res.error
    assert "新品・未使用" in res.error      # 错误信息里给出正确取值
    assert scraper.queries == []            # 没有退化成无过滤搜索


@pytest.mark.asyncio
async def test_price_stats_invalid_condition_errors_too():
    scraper = _RecordingScraper()
    res = await PriceStatisticsTool(scraper).call(keyword="ブラウン", condition="未使用")
    assert not res.is_success()
    assert scraper.queries == []


# --------------------------------------------------------------------------- #
# 多选成色真的传到下游
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_multiple_conditions_reach_query_and_are_echoed():
    scraper = _RecordingScraper()
    res = await SearchMercariTool(scraper).call(
        keyword="ブラウン シリーズ9 Pro", condition=["新品・未使用", "未使用に近い"],
        price_min=15000, limit=5,
    )

    assert res.is_success()
    assert res.data["condition_filter"] == ["新品・未使用", "未使用に近い"]
    assert res.data["price_min"] == 15000
    assert scraper.queries[0].condition == "新品・未使用,未使用に近い"


def test_conditions_map_to_item_condition_ids():
    proc = SearchParameterProcessor()
    for value in ("新品・未使用,未使用に近い", ["新品・未使用", "未使用に近い"]):
        q = QueryEntity(original_query="x", keywords=["x"], condition=value)
        assert proc.process_query_parameters(q)["status"] == "1,2"
    # 非法成色名不映射（下游 URL 构建也不会带上）
    q = QueryEntity(original_query="x", keywords=["x"], condition="新品")
    assert "status" not in proc.process_query_parameters(q)


def test_status_option_splits_multi_select():
    assert SearchParameterProcessor.map_status_option("1,2") == ["1", "2"]
    assert SearchParameterProcessor.map_status_option("1") == ["1"]
    assert SearchParameterProcessor.map_status_option("") == []


def test_search_url_carries_multi_condition():
    scraper = PlaywrightMercariScraper(AppConfig())
    q = QueryEntity(
        original_query="ブラウン シリーズ9 Pro",
        keywords=["ブラウン シリーズ9 Pro"],
        condition="新品・未使用,未使用に近い",
        price_min=15000,
    )
    url = scraper._build_search_url(q)
    assert "item_condition_id=1%2C2" in url or "item_condition_id=1,2" in url
    assert "price_min=15000" in url

    # 成色名没映射成 ID 时不能带上非数字值（Mercari 只认数字 ID）
    q2 = QueryEntity(original_query="x", keywords=["x"], condition="新品")
    assert "item_condition_id" not in scraper._build_search_url(q2)


# --------------------------------------------------------------------------- #
# 本体行情统计（过滤配件 / 残缺品 / 不同产品 + 价格下限）
# --------------------------------------------------------------------------- #
def _stat_products():
    """真实形状的样本：本体、搭售本体、纯配件、别的机种、残缺品混在一起。"""
    def prod(pid, title, price):
        return ProductEntity(id=pid, title=title, price=price, condition="目立った傷や汚れなし",
                             url=f"https://jp.mercari.com/item/{pid}")
    return [
        prod("b1", "Nikon D850 ボディ 本体", 149800),
        # 本体 + 配件搭售：实测 ¥125,000 这台正是 agent 推荐的那台，被误杀过
        prod("b2", "Nikon D850 デジタル一眼レフカメラ 本体　NPSストラップ", 125000),
        # 标题没有「本体」，只靠「ストラップ付」的「付」才能认出是相机
        prod("b3", "Nikon D850 デジタル一眼レフ ショット約38万 動作確認済 純正ストラップ付", 139800),
        prod("a1", "Nikon D850 純正カメラストラップ", 1390),
        prod("a2", "Nikon D850 用 液晶保護フィルム 2枚セット", 980),
        prod("w1", "D810 AF-S NIKKOR 24-120mm フルサイズ 一眼レフ", 130000),
        prod("d1", "Nikon D850 ジャンク 動作未確認", 60000),
    ]


@pytest.mark.asyncio
async def test_price_statistics_reports_body_only_market():
    """关键词行情对"本体贵不贵"没有参考价值 —— 实测 D850 不过滤时中位数只有 ¥5,000。"""
    tool = PriceStatisticsTool(_RecordingScraper(_stat_products()))
    res = await tool.call(keyword="ニコン D850")
    d = res.data

    assert d["basis"] == "body_only"
    assert d["count"] == 3                      # 三台本体（含两台搭售配件的）
    assert d["min"] == 125000                   # 不是 ¥980 的保护膜
    assert d["max"] == 149800
    # 未过滤的原始统计要留着，让"过滤是不是过头了"查得出来
    assert d["unfiltered"]["count"] == 7
    assert d["unfiltered"]["min"] == 980


@pytest.mark.asyncio
async def test_price_statistics_explains_every_exclusion():
    res = await PriceStatisticsTool(_RecordingScraper(_stat_products())).call(keyword="ニコン D850")
    ex = res.data["excluded"]
    assert ex["count"] == 4
    assert ex["by"] == {"accessory": 2, "wrong_product": 1, "defective": 1}
    assert ex["examples"]                        # 每类留一条样本，误排除才查得出来


@pytest.mark.asyncio
async def test_bundled_accessory_does_not_kill_the_body():
    """**误杀比漏过配件危险得多** —— 它会静默丢掉真正的便宜货。"""
    from kaidoki.shared.utils.item_filters import classify_exclusion

    # 有「本体」→ 保留
    assert classify_exclusion("Nikon D850 デジタル一眼レフカメラ 本体　NPSストラップ") is None
    # 没「本体」但有「ストラップ付」→ 保留
    assert classify_exclusion("Nikon D850 一眼レフ 動作確認済 純正ストラップ付") is None
    # 纯配件 → 排除
    assert classify_exclusion("Nikon D850 純正カメラストラップ")[0] == "accessory"


@pytest.mark.asyncio
async def test_price_min_reaches_the_query_and_gates_survivors():
    """价格下限是**第二道闸**：词表挡不住的"看起来像本体但便宜得离谱"要靠它挡。"""
    products = [
        ProductEntity(id="b", title="Nikon D850 ボディ 本体", price=149800,
                      condition="目立った傷や汚れなし", url="https://jp.mercari.com/item/b"),
        # 标题干净、词表挡不住，但 ¥30,000 买不到 D850 本体（部品取り/诈骗/写错）
        ProductEntity(id="c", title="Nikon D850 本体", price=30000,
                      condition="目立った傷や汚れなし", url="https://jp.mercari.com/item/c"),
    ]
    scraper = _RecordingScraper(products)
    res = await PriceStatisticsTool(scraper).call(keyword="ニコン D850", price_min=90000)

    assert res.data["price_min"] == 90000
    assert scraper.queries[0].price_min == 90000    # 真的传到下游（Mercari 服务端也会过滤）
    assert res.data["excluded"]["by"].get("below_price_min") == 1
    assert res.data["count"] == 1 and res.data["min"] == 149800


@pytest.mark.asyncio
async def test_warns_when_sample_looks_bimodal():
    """没给 price_min 时词表挡不住所有杂物 —— 用 max/median 比值把"该重查"说出来。"""
    tool = PriceStatisticsTool(_RecordingScraper([
        ProductEntity(id=f"x{i}", title="ニコン D850 本体", price=p,
                      condition="目立った傷や汚れなし", url=f"https://jp.mercari.com/item/x{i}")
        for i, p in enumerate([800, 900, 1000, 1100, 250000])
    ]))
    res = await tool.call(keyword="ニコン D850")
    assert res.data["warnings"], res.data
    assert "price_min" in res.data["warnings"][0]

    # 给了 price_min 就不再唠叨
    res2 = await tool.call(keyword="ニコン D850", price_min=90000)
    assert res2.data["warnings"] == []
