# Kaidoki 淘货助手(个人自用)

输入一句话的购物需求,它从 Mercari 抓**真实在售二手商品**,再结合 kakaku.com 和官方商店查**新品价**与**同产品线的更新型号**,用 Claude 给你一份"该买二手 / 买新品 / 买新型号"的判断。

> 个人工具,非商业产品。仅供自己淘货,低频访问。

## 两种入口

| 命令 | 是什么 | 什么时候用 |
|---|---|---|
| `agent` | **原生工具调用 agent**:Claude 自主决定调哪些工具、调几次 | 开放式 / 需要比较 / 需要"该不该买、买哪个"判断 |
| `search` | **固定流水线**:解析 → 抓取 → LLM 重排 → 格式化 | 直接明确的"找 X 的好货",要可预测、便宜、快 |

设计取舍:**控制流已知就用固定流程(`search`),控制流动态才用 agent**。两者并存,不互相替代。

## agent 能调用的工具

- `search_mercari` — 按关键词/价格/成色搜 Mercari 在售商品(id/标题/价/成色/链接)。
- `get_price_statistics` — 抓一批算 count/min/max/median/average,判断"贵不贵、是不是好价"。
- `recommend_deals` — 把整条固定流水线(解析→抓取→重排)包成一步,直接出成品推荐。
- `get_new_and_newer_models` — **查新品最低价 + 发现同产品线的更新型号及其价格**(实时数据,不靠模型记忆)。

## 架构(实际跑通的路径)

分层:`interfaces`(CLI/API) → `application`(services:query_parser / recommendation / output_formatter / **agent**) → `infrastructure`(llm / scraping) → `domain`(entities);工具在 `tools/`。

关键组件:

- **数据层** `infrastructure/scraping/scraper_service.py`:Playwright 无头 Chromium。首屏从渲染后的 DOM(`li[data-testid="item-cell"]`)取,并捕获页面自己发出的 `entities:search` 响应补全字段(**零额外请求**);翻页复用浏览器铸造的 DPoP token 调 `api.mercari.jp/v2/entities:search`,遇 401 重载刷新。**无反爬/指纹伪装**——Mercari 对这类访问没有 bot 墙。
- **新品/新型号** `tools/model_compare.py` + `infrastructure/scraping/lineup_finder.py`:kakaku.com(httpx / shift_jis)取新品最安値与目录机型 + 官方店 JSON-LD;发现同线更新型号复用已启动的浏览器。**取的是结构化数据,不解析渲染层**。
- **LLM 层** `infrastructure/llm/llm_service.py`:**AWS Bedrock + Claude(默认 `us.anthropic.claude-sonnet-4-6`)**。用于查询解析、重排、以及 agent 的原生工具调用。`chat_with_tools` 内部做 OpenAI↔Anthropic 工具格式适配,所以 agent 循环与 CLI 无需改动。OpenAI 保留为 fallback。
- **agent** `application/services/agent_service.py`:原生 tool-calling 循环(多工具/错误回灌/迭代上限/trace),system prompt 含"买二手 / 买新品 / 买新型号"三选一判断。

## 安装

```bash
uv sync --locked
uv run playwright install chromium
```

依赖统一声明在 `pyproject.toml`,精确版本由已提交的 `uv.lock` 固定。需要启用可选的
OpenAI fallback 时运行 `uv sync --locked --extra openai`。

LLM 走 AWS Bedrock(浏览器交互):

```bash
aws login
```

`.env`(参考 `.env.template`):

```
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6   # 可换 us.anthropic.claude-sonnet-5 / ...-haiku-4-5-...
BEDROCK_REGION=us-west-2
# OPENAI_API_KEY=sk-...   # 可选,作为 fallback
```

> Bedrock 的模型 ID 会随版本变化;用 `aws bedrock list-inference-profiles --profile <profile>` 核对账号实际可用的再填。

## 使用

```bash
# 原生工具调用 agent(会自主查行情/新品价/新型号,给三选一判断)
uv run kaidoki agent --query "Bambu A1 mini 现在该买二手还是新品?有没有更新型号?"

# 固定流水线:解析 → 抓取 → LLM 重排 → 输出
uv run kaidoki search --query "AirPods Pro 中古 2万円以下" --max-results 5

uv run kaidoki scrape --query "airpods" --max-products 20   # 只抓不推荐
uv run kaidoki parse  --query "iPhone 15 128GB 8万円以下"    # 只看解析
uv run kaidoki status                                        # 健康检查
uv run kaidoki config                                        # 查看配置
```

`search` 选项:`--strategy {price_oriented|quality_oriented|balanced|trending}`、
`--output-format {markdown_table|detailed_report|simple_list|json_export}`、`--language {zh|ja|en}`。
`agent` 选项:`--max-iterations N`。

运行前确保当前 shell 有 AWS 凭证

## 测试

```bash
uv run pytest tests/ -q -o addopts=""
```

当前 86 个测试(数据层解析、LLM 重排/JSON、输出格式、agent 循环、Bedrock 适配、新旧型号对比),全部离线、零网络、零真实 LLM。

## 说明与边界

- **仅供个人自用**。低频、每次一个浏览器会话、翻页/取数有延时与上限。请勿规模化抓取或商用——会触及 Mercari 服务条款与日本相关法律(個人情報保護法、古物営業法 等)。
- **关键词精度**:agent 的搜索有时会先匹配到无关商品,靠换更精确的关键词自纠;结论通常正确,但这是可打磨点。
- **卖家名取不到**(搜索 API 不返回);标题/价/成色/图/品牌/分类都有。
- **kakaku 覆盖分品类**:电子/数码/家电覆盖好,新品锚点干净;服饰/杂货覆盖薄,新旧对比会退化为纯二手。
- **成本**:Bedrock Claude Sonnet 4.6,单次查询数美分级(cost table 已登记,日志可见近似成本)。

## 项目历史(给未来的自己)

搁置约一年的项目的重启。原版用LLM堆了 7 万多行代码去对抗一个**并不存在**的反爬墙,数据层从未跑通,下游全靠 mock 假数据自欺。

重启只做对了一件事,后来反复受用:**先验证核心假设,再动手建设**。半天的 spike 就能确认"数据在哪、墙存不存在";之后每加一层(Playwright 数据层、原生工具调用、Bedrock/Claude、新旧型号对比)都是先 spike 验证数据路径、再实现、再实跑核对。反复印证的两条:**取结构化数据别跟渲染层较劲;"最新型号/价格"这类会过时的东西必须实时查、别信模型记忆。**
