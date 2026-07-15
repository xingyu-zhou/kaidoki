"""
LineupFinder —— 官方/品牌页新品取价（Playwright 渲染 + JSON-LD 抽取）

用途:当某商品**不在 kakaku 比价目录内**(如 Bambu Lab 3D 打印机)时,直接渲染品牌
官方商店的商品页,从页面自带的结构化数据(JSON-LD `Offer`)读新品价。这是新型号发现
链路里"Stage 2 验证/取价"的确定性核心(无 LLM):同一 URL → 同一 JSON-LD → 同一价格。

为什么用 Playwright 而不是 httpx/WebFetch:实测 bambulab.com 对服务端裸抓返回 403,
对本 app 的真实浏览器上下文(真实 JP Chrome UA / locale ja-JP / timezone Asia/Tokyo)
返回 200。因此这里**复用**现有 Playwright 抓取基础设施:优先借用 ScraperService 已启动
的浏览器(传入 context_factory=scraper.scraper._new_context),否则自起一个无头 Chromium。

区域固定:locale=ja-JP + JP 商店路径,使 priceCurrency 稳定为 JPY、结果可复现。

取价优先级:JSON-LD Offer(权威) → <meta itemprop=price>/og:price:amount → 可见文本正则。

Author: Kaidoki Team (model compare feature)
"""

import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright

from ...shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

# 与 ScraperService 同款真实日本 Chrome UA（自起浏览器时用；复用时走 context_factory）
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

# 页面里抽结构化数据:JSON-LD 脚本 + price meta + 少量可见文本(兜底正则)
_EXTRACT_JS = r"""
() => {
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')]
              .map(s => s.textContent);
  const meta = [...document.querySelectorAll(
                 'meta[itemprop="price"],meta[property="og:price:amount"]')]
              .map(m => m.getAttribute('content'));
  const text = (document.body ? document.body.innerText : '').slice(0, 6000);
  return { title: document.title, ld: ld, meta: meta, text: text };
}
"""


def _to_int(value: Any) -> Optional[int]:
    """把 '39,800' / 'US$249' / 39800 之类抽成纯整数日元数值。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _walk_offers(node: Any, out: List[Dict[str, Any]]) -> None:
    """深度遍历 JSON-LD 树，收集所有 {name, price, currency}（Product/Offer/AggregateOffer）。"""
    if isinstance(node, dict):
        if (
            node.get("@type") in ("Offer", "AggregateOffer")
            or "price" in node
            or "lowPrice" in node
        ):
            out.append(
                {
                    "name": node.get("name"),
                    "price": node.get("price") or node.get("lowPrice"),
                    "currency": node.get("priceCurrency"),
                }
            )
        for v in node.values():
            _walk_offers(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_offers(v, out)


class LineupFinder:
    """渲染官方/品牌页并抽取新品价（区域固定 ja-JP / JPY，确定性、可缓存）。"""

    def __init__(
        self,
        context_factory: Optional[Callable[[], Awaitable[Any]]] = None,
        locale: str = "ja-JP",
        timezone_id: str = "Asia/Tokyo",
        settle_seconds: float = 3.0,
        nav_timeout_ms: int = 45000,
    ):
        # context_factory: 无参 async 可调用，返回一个新的 Playwright BrowserContext。
        # 传 ScraperService.scraper._new_context 即可复用 app 已启动的浏览器（推荐）。
        self._context_factory = context_factory
        self.locale = locale
        self.timezone_id = timezone_id
        self.settle_seconds = settle_seconds
        self.nav_timeout_ms = nav_timeout_ms

    async def render(self, url: str) -> Dict[str, Any]:
        """渲染 url，返回 {title, ld[], meta[], text, status}。失败抛异常由调用方兜底。"""
        if self._context_factory is not None:
            context = await self._context_factory()
            try:
                return await self._render_in_context(context, url)
            finally:
                await context.close()

        # 无复用来源时自起无头 Chromium（离线/独立使用）
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=UA,
                    locale=self.locale,
                    timezone_id=self.timezone_id,
                    viewport={"width": 1440, "height": 900},
                    extra_http_headers={
                        "Accept-Language": f"{self.locale},ja;q=0.9,en;q=0.8"
                    },
                )
                return await self._render_in_context(context, url)
            finally:
                await browser.close()

    async def _render_in_context(self, context: Any, url: str) -> Dict[str, Any]:
        page = await context.new_page()
        resp = await page.goto(
            url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms
        )
        await asyncio.sleep(self.settle_seconds)  # 让 SPA hydrate
        data = await page.evaluate(_EXTRACT_JS)
        data["status"] = resp.status if resp else None
        return data

    @staticmethod
    def offers_from(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        """JSON-LD 优先 → meta → 文本正则。返回 (offers, source)。"""
        offers: List[Dict[str, Any]] = []
        for blk in data.get("ld") or []:
            try:
                _walk_offers(json.loads(blk), offers)
            except Exception:  # noqa: BLE001
                continue
        offers = [o for o in offers if o.get("price") not in (None, "")]
        if offers:
            return offers, "json-ld"

        meta = [m for m in (data.get("meta") or []) if m]
        if meta:
            return (
                [{"name": data.get("title"), "price": meta[0], "currency": None}],
                "meta",
            )

        text = data.get("text") or ""
        m = re.findall(r"(?:¥|￥|\$|US\$)\s?[\d,]{3,}", text)
        if m:
            return [{"name": data.get("title"), "price": m[0], "currency": None}], "text-regex"
        return [], "none"

    def min_offer(self, data: Dict[str, Any]) -> Tuple[Optional[int], str, Optional[str]]:
        """取该页最低价(基础机型≈最便宜可购配置)。返回 (price:int|None, source, currency)。"""
        offers, source = self.offers_from(data)
        prices: List[int] = []
        currency: Optional[str] = None
        for o in offers:
            p = _to_int(o.get("price"))
            if p:
                prices.append(p)
                currency = currency or o.get("currency")
        if prices:
            return min(prices), source, currency
        return None, source, currency
