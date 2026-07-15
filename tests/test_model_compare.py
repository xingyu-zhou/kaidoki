"""
get_new_and_newer_models 工具单测（零网络 / 零真实 LLM / 零浏览器）。

覆盖：
- 工具输出结构（searched_model / newer_models / currency）
- 多 backend 依次尝试：第一个 None 时落到第二个
- backend 抛异常不崩、全都拿不到时返回 note（不崩）
- 空 keyword 不崩
- KakakuBackend 的搜索页解析 + 被搜/更新机型切分（喂预设 HTML，不触网）
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
    assert result.data["currency"] == "JPY"


@pytest.mark.asyncio
async def test_empty_keyword_does_not_crash():
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])
    result = await tool.call(keyword="   ")
    assert result.is_success()
    assert result.data["note"] == "未获取到新品/新型号数据"


@pytest.mark.asyncio
async def test_absorbs_extra_args():
    tool = GetNewAndNewerModelsTool([_FakeBackend(_PRESET)])
    result = await tool.call(keyword="Bambu A1 mini", bogus="x", extra=1)
    assert result.is_success()


# --------------------------------------------------------------------------- #
# KakakuBackend 解析（喂预设 HTML，不触网）
# --------------------------------------------------------------------------- #
# 结构模仿 kakaku 搜索页结果行（newest-first：Pro 3 → Pro 2 → Pro）。
_KAKAKU_HTML = """
<html><body>
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a href="/item/K0001709588/">AirPods Pro 3 MFHP4J/A</a></p>
  <span class="p-item_priceNum is-value">32,999</span>
</div>
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a href="/item/K0001566951/">AirPods Pro 2 MTJV3J/A</a></p>
  <span class="p-item_priceNum is-value">28,498</span>
</div>
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a href="/item/K0001206017/">AirPods Pro MWP22J/A</a></p>
  <span class="p-item_priceNum is-value">29,800</span>
</div>
<div class="p-resultItem_in p-item">
  <p class="p-item_name"> <a>互換 保護ケース for AirPods</a></p>
  <span class="p-item_priceNum is-value">980</span>
</div>
</body></html>
"""


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
    # "AirPods Pro"（无代际数字）→ 被搜机型 = 最基础的那一款
    assert res["searched_model"]["name"] == "AirPods Pro MWP22J/A"
    assert res["searched_model"]["new_price_min"] == 29800
    assert res["searched_model"]["source"] == "kakaku.com"
    # 页面里排在它之前的同线机型 = 更新机型
    newer_names = [m["name"] for m in res["newer_models"]]
    assert "AirPods Pro 3 MFHP4J/A" in newer_names
    assert "AirPods Pro 2 MTJV3J/A" in newer_names
    assert res["currency"] == "JPY"


@pytest.mark.asyncio
async def test_kakaku_specific_model_has_no_newer():
    backend = _CannedKakaku(_KAKAKU_HTML)
    res = await backend.lookup("AirPods Pro 3")
    # 已是最新一代 → 没有更新机型
    assert res["searched_model"]["name"] == "AirPods Pro 3 MFHP4J/A"
    assert res["newer_models"] == []


@pytest.mark.asyncio
async def test_kakaku_non_catalog_returns_none():
    # 无 /item/K.../ 行（纯购物列表）→ 交给下一级 backend
    backend = _CannedKakaku("<html><body><div>no catalog items</div></body></html>")
    assert await backend.lookup("Bambu A1 mini") is None


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
