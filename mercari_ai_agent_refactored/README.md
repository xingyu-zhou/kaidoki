# Mercari AI 淘货助手(个人自用)

输入一句话的商品需求,它去 Mercari 抓**真实在售商品**,用 LLM 按性价比重排,给你一份带理由的推荐清单。

> 个人工具,非商业产品。请只用于自己淘货,低频访问。

## 能做什么

- **解析需求**(关键词 / 价格区间 / 类别 / 成色)——LLM 完成
- **抓真实商品**——无头浏览器直接从 jp.mercari.com 取在售商品
- **LLM 重排**——对真实商品按你选的策略(性价比 / 低价 / 品质 / 热度)排序并给出推荐理由
- **多格式输出**——markdown 表格 / 详细报告 / 简单列表 / JSON

## 架构(实际跑通的路径)

分层:`interfaces`(CLI/API) → `application`(services) → `infrastructure`(llm / scraping) → `domain`(entities)。

两个关键层:

- **数据层** `infrastructure/scraping/scraper_service.py`:Playwright 无头 Chromium。
  首屏从渲染后的 DOM(`li[data-testid="item-cell"]`)取,并顺带捕获页面自己发出的那次 `entities:search` 响应用来补全/富化字段(**零额外请求**);需要更多页时,**复用浏览器铸造的 DPoP token** 调 `api.mercari.jp/v2/entities:search`(递增 `pageToken`),遇 401 重新载入页面刷新 token 兜底。
  **没有任何反爬 / 指纹伪装**——Mercari 对这类访问没有 bot 墙。
- **LLM 层** `infrastructure/llm/llm_service.py`:OpenAI(默认 `gpt-4o-mini`),用于查询解析和推荐重排(启用 JSON 模式,解析稳定)。

主流程:`解析查询 → 抓真实商品 → LLM 重排 → 格式化输出`。

## 安装

```bash
cd mercari_ai_agent_refactored
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

在 `.env` 放 OpenAI key(参考 `.env.template`):

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## 使用

```bash
# 完整闭环:解析 → 抓取 → LLM 重排 → 输出
.venv/bin/python main.py search --query "AirPods Pro 中古 2万円以下" --max-results 5

# 只抓不推荐
.venv/bin/python main.py scrape --query "airpods" --max-products 20

# 只看查询解析
.venv/bin/python main.py parse  --query "iPhone 15 128GB 8万円以下"

.venv/bin/python main.py status   # 健康检查(LLM + 爬虫)
.venv/bin/python main.py config   # 查看配置
```

常用选项:`--strategy {price_oriented|quality_oriented|balanced|trending}`、
`--output-format {markdown_table|detailed_report|simple_list|json_export}`、`--language {zh|ja|en}`。

## 测试

```bash
.venv/bin/python -m pytest -q
```

## 说明与边界

- **仅供个人自用**。低频访问、每次一个浏览器会话、翻页有延时、总页数有上限。请勿用于规模化抓取或商用——那会触及 Mercari 服务条款与日本相关法律(個人情報保護法、古物営業法 等)。
- **卖家名当前取不到**:搜索 API 不返回,拿它得逐商品抓详情(额外请求),按克制原则未做。标题 / 价格 / 成色 / 图 / 品牌 / 分类都有。
- **成本可忽略**:每次查询约 2 次 LLM 调用(解析 + 重排),`gpt-4o-mini` 下单次通常 <$0.01。

## 项目历史(给未来的自己)

这是一个搁置约一年的项目的重启。原版堆了 7 万多行代码去对抗一个**并不存在**的反爬墙,数据层因此从未跑通,下游推荐全靠 mock 假数据自欺。

重启只做对了一件事:**先花半天验证"数据到底在哪、墙存不存在"**——确认用无头浏览器几百行就能拿到真实数据,再在干净的重构骨架上把 `解析 → 真实数据 → LLM 重排 → 输出` 这条闭环真正跑通。教训:先验证核心假设,再动手建设。
