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

- `search_mercari` — 按关键词/价格/成色搜 Mercari 在售商品(id/标题/价/成色/链接)。成色可多选;
  **「新品・未使用」= 全新未拆封** —— Mercari 不只有二手,"只买新品"也要搜这一档(常比 kakaku 便宜)。
- `get_price_statistics` — 抓一批算 count/min/max/median/average,判断"贵不贵、是不是好价"。
  返回的是**本体行情**(`basis: body_only`):自动剔除配件/残缺品/不同产品,并回报 `excluded`
  (剔了多少条、按什么规则、每类一条样本)与 `unfiltered`(未过滤原始统计,用于对照)。
  建议同时给 `price_min` —— 实测 "ニコン D850" 不给下限时中位数只有 ¥5,000(一台十几万的相机)。
- `recommend_deals` — 把整条固定流水线(解析→抓取→重排)包成一步,直接出成品推荐。
- `get_new_and_newer_models` — **查新品最低价 + 发现同产品线的更新型号及其价格**(实时数据,不靠模型记忆)。
  每个机型带 `url / release(発売日) / shops(在售店舗数) / variant(cc=洗浄器付き / s=本体のみ)`,
  外加 `confidence`(选型置信度)、`candidates`(关键词笼统时的其它候选)、
  `newer_lookup`(`ok`=真比较过発売日 / `unknown`=数据不足)、
  `price_basis`(=`cash_lowest_excl_campaigns`,**现金最安値,不含キャッシュバック与ポイント还元**)。

## 架构(实际跑通的路径)

分层:`interfaces`(CLI/API) → `application`(services:query_parser / recommendation / output_formatter / **agent**) → `infrastructure`(llm / scraping) → `domain`(entities);工具在 `tools/`。

关键组件:

- **数据层** `infrastructure/scraping/scraper_service.py`:Playwright 无头 Chromium。首屏从渲染后的 DOM(`li[data-testid="item-cell"]`)取,并捕获页面自己发出的 `entities:search` 响应补全字段(**零额外请求**);翻页复用浏览器铸造的 DPoP token 调 `api.mercari.jp/v2/entities:search`,遇 401 重载刷新。**无反爬/指纹伪装**——Mercari 对这类访问没有 bot 墙。
- **新品/新型号** `tools/model_compare.py` + `infrastructure/scraping/lineup_finder.py`:kakaku.com(httpx / shift_jis)取新品最安値与目录机型 + 官方店 JSON-LD;发现同线更新型号复用已启动的浏览器。**取的是结构化数据,不解析渲染层**。
  选型按 型番命中 > 系列尾部精确 > 配置(cc/s)匹配 > 命中 token 数 > 発売日新 > 在售店舗多 排序
  (带罗马字↔片假名品牌别名表,`braun` 能匹配 `ブラウン`;保留 `+` 以区分 Pro 与 Pro+);
  新旧一律用行内 `発売日` 判定 —— **kakaku 搜索页是人気順,页面顺序不代表新旧**。
  **只收目录机型行**(靠 `p-item_maker`/`p-item_date`/`p-item_shopCounts` 结构标记):单店购物行也会链到目录页,
  实测 "ニコン D850" 的 35 个带 K 链接的行里 29 个是购物行,误收会报出某一家店的 ¥327,834 而非目录最安値 ¥279,980。
  关键词塞了规格词导致 0 结果时,会降级成"品牌+系列+型番"重试一次。
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
`agent` 选项:`--max-iterations N`、`--result-chars N`(终端上每次工具返回打印多少字符)、
`--trace-file PATH`(把**完整过程**写成 JSON:system prompt / 每轮模型推理 / 每次工具调用的完整入参与返回 / 完整对话)、
`--google-benchmark`(开启 Google 对照基线,**默认关闭**)。
`--trace-file` 是复盘工具:结论错了先看它,能区分"工具取错数"和"模型误读数据"。

**无来源价格检查**:每次跑完会扫一遍回答里的金额,凡是**任何工具返回里都查不到**的
(差额与和已排除)就打出来提醒。prompt 规则管不住模型编价格 —— 实测两次工具返回"无数据"后
它仍凭自有知识写了价(WF-1000XM5 估成 ¥30,000,真实 ¥24,605;Switch 2 写 ¥49,980)。
规则靠不住,检查才靠得住。注意它是**信号不是证明**:恰好等于某个差额的数字会漏报。

## Google 对照基线(记分板)——**当前默认关闭**

> 默认关闭(`--google-benchmark` 才开)。原因见 `TODO.md`:Custom Search API 侧还没跑通,
> 而且核心比较语义仍在打磨中 —— 不能让一个未验证的记分板产生误导性的战绩。
> 代码与 39 个离线测试都保留着,等 API 通了再打开。
>
> 在此期间用**人工审计**代替:让带联网能力的 Claude 跑一遍同样的查询,核对结论对不对。
> 实测这比 CSE 有用得多 —— CSE 只能正则抽价格,审计能发现"这个价没算キャッシュバック"这类问题。

回答一个问题:**我们有没有比自己上网搜更强?** 开启后每次 `agent` 跑完记一条,
`uv run kaidoki benchmark` 看累计战绩(`--rescore` 用当前判定标准重算历史,不再打 API)。

三条设计约束,都是踩过才定下来的:

- **Google 结果绝不进 agent 的 `messages`**。一旦进去模型会抄 Google 的数字,基线失去独立性,
  记分板变成自证。有专门的测试断言 `messages` 与 LLM 调用次数都不变。
- **不能拿原始中文 query 打 Google**。`"Braun Pro只买新品"` 送给 Google 会得到很差的结果,
  那样赢了没意义。所以同时评两份:原样 query 与**公平 query**(agent 自己用的日文型号 + 最安値)。
- **打分在读取时算**。JSONL 存双方原始结果 + verdict 快照;判定标准一定会变,
  只存结论就等于每次改标准都丢掉全部历史。

判定:`loss`(Google 上有更便宜的同类本体 = 漏项,**最有价值的信号**)> `win`(便宜超过 2%)>
`tie` > `n/a`(任一侧没有可比价格)。覆盖率只作记录、不单独构成 win —— Google 几乎不索引
单条 Mercari 商品页,否则会刷出无意义的连胜。

**`comparability` 比 verdict 更该先看**:`same_model` / `different_model` / `unknown`。
只有同型番时"谁更便宜"才有意义。实测两次近似同价**都不是同型号**,而且方向相反 ——
Braun 那次便宜的是新三年的 Pro+(该买),AirPods 那次便宜的反而是只剩 1 店的 Lightning 版旧款尾货。
所以不同型号之间的 win/tie 会在 `reason` 里直接带上警示,不允许被当成性价比结论。

**比较前必须过滤配件**,否则一个 ¥2,299 的替刃会"赢"下比较。实测踩到的坑都在
`shared/utils/item_filters.py`(与 prompt 的 R2 同源,防止两边漂):「右耳のみ」单只耳机、
标题不含「ケース」的 casetify 保护壳、以及 **AirPods 2 冒充 AirPods Pro 2** ——
最后这类不是配件,靠词表挡不住,得用 agent 自己关键词的 token 闸。

启用见 `.env.template` 的 `GOOGLE_API_KEY` / `GOOGLE_CSE_ID`(免费 100 次/天,
每次运行最多消耗 2 次)。没配就静默跳过。注:CSE 的排序与真实 google.com 有差异,
记录里一律标 `source: google_cse`。

> `benchmarks/*.jsonl` 会记下检索词与完整 Google 结果,而仓库 URL 是公开的 ——
> 所以它**已加进 `.gitignore`**。想让记分板历史进版本库就删掉那一行。

运行前确保当前 shell 有 AWS 凭证

## 测试

```bash
uv run pytest tests/ -q -o addopts=""
```

当前 171 个测试(数据层解析、LLM 重排/JSON、输出格式、agent 循环与 trace、Bedrock 适配、
新旧型号对比与选型回归、目录行/购物行区分、Pro 与 Pro+ 世代区分、cc/s 配置区分、
成色多选过滤、本体行情统计与搭售商品保护、无来源价格检查、Google 对照基线与配件过滤、
同型番可比性),全部离线、零网络、零真实 LLM。

## 说明与边界

- **仅供个人自用**。低频、每次一个浏览器会话、翻页/取数有延时与上限。请勿规模化抓取或商用——会触及 Mercari 服务条款与日本相关法律(個人情報保護法、古物営業法 等)。
- **关键词精度**:agent 的搜索有时会先匹配到无关商品(Mercari 上尤其多替刃/配件),靠换更精确的关键词与 `price_min` 自纠;结论通常正确,但这是可打磨点。
- **二手可不可以按品类分**(prompt R8,词表在 `shared/utils/item_filters.py`):相机/PC/手机这类耐用电子,
  成色好的二手完全可以(实测 D850 中古 ¥125,000 vs 新品 ¥279,980);而**电动剃须刀这类个人护理用品只推新品**,
  且默认首选 kakaku 正规渠道 —— Mercari 的「新品・未使用」是个人卖家自述,无法核实是否真未开封。
  入耳式耳机这类介于两者之间的,先提示卫生顾虑再让用户决定。
- **「最安値」≠「实际支付额」**(prompt R10):kakaku 价格是**现金**最安値,不含
  メーカーキャッシュバック(实测 Braun 有 ¥3,500 的本体+替刃活动,占 8%)与楽天ポイント还元
  (最高 50%,kakaku 完全不计入)。工具用 `price_basis` 把这个前提写进数据契约,
  prompt 要求每次价格对比都必须声明,且不许凭记忆编造具体活动。**不建模キャンペーン** ——
  会过时、要长期维护,提示用户去查更可靠。
- **kakaku 搜索页有时根本不返回目录行**:实测 `search.kakaku.com/WF-1000XM5/` 给的是通販商品页
  (40 行 0 目录行)。此时跟进购物行里的 `/item/K.../` 链接直接读目录页,能拿到准确的
  ¥24,605 / 2023-09 / 23店 —— 否则工具报"无数据",模型就会自己估价(估过 ¥30,000)。
- **未発売商品必须警告**:kakaku 会提前登记発売预定品并显示预约价与店铺数。
  实测 ドルツ EW-DA19(発売予定 2026-09)被当成"现在就能买"推荐过。
- **关键词全命中 ≠ 同一个产品**:查 "Nintendo Switch 2" 时 40 条目录行**全是游戏软件**,
  三个 token 全命中却都只落在 `[Nintendo Switch 2]` 这个平台后缀里。所以要求有实义的 token
  必须落在**机型名**(series)上,否则宁可报无数据 —— 报 ¥6,666 的游戏当主机价更糟。
- **过度过滤比漏过配件危险得多**:加配件过滤时曾把 `D850 …本体 NPSストラップ` ¥125,000
  当配件剔掉 —— 而它正是 agent 推荐的那台。所以配件名改为**条件排除**(标题含 `本体/ボディ`
  或配件名后跟 `付/込/同梱` 就不算配件),且每个排除项都留原因与样本。
- **同系列里还有"配置"这一维**(prompt R9):Braun 型番以 `cc` 结尾=洗浄器付き、以 `s` 结尾=本体のみ,
  工具返回的 `variant` 字段标出这一点。实测 Pro+ `9617s` ¥35,698 与 `9657cc` ¥43,999 差 ¥8,301,
  混着比价会让人以为便宜了八千。另外 Mercari 标题里「洗浄器**対応**」≠「洗浄器**付き**」。
- **kakaku 只解析搜索结果第 1 页**:返回里的 `coverage` 会交代这一点;排名靠后的机型可能没纳入比较。
- **"没有更新型号"必须看 `newer_lookup`**:`unknown` 只代表查不出来。空的 `newer_models` 不等于没有 ——
  历史上就是这个混淆让 agent 报出过"後継モデルなし"的错误结论。
- **卖家名取不到**(搜索 API 不返回);标题/价/成色/图/品牌/分类都有。
- **kakaku 覆盖分品类**:电子/数码/家电覆盖好,新品锚点干净;服饰/杂货覆盖薄,新旧对比会退化为纯二手。
- **成本**:Bedrock Claude Sonnet 4.6,单次查询数美分级(cost table 已登记,日志可见近似成本)。

## 项目历史(给未来的自己)

搁置约一年的项目的重启。原版用LLM堆了 7 万多行代码去对抗一个**并不存在**的反爬墙,数据层从未跑通,下游全靠 mock 假数据自欺。

重启只做对了一件事,后来反复受用:**先验证核心假设,再动手建设**。半天的 spike 就能确认"数据在哪、墙存不存在";之后每加一层(Playwright 数据层、原生工具调用、Bedrock/Claude、新旧型号对比)都是先 spike 验证数据路径、再实现、再实跑核对。反复印证的两条:**取结构化数据别跟渲染层较劲;"最新型号/价格"这类会过时的东西必须实时查、别信模型记忆。**

后来补上第三条:**"查不出来"和"不存在"必须在数据结构里区分开**。一次真实的错误结论
(「Braun Pro ¥29,800、後継モデルなし」)不是模型幻觉,而是工具的静默失败:跨语种 token 匹配全废,
打分退化成"名字最短者胜",于是选中一个只剩 3 家店的三年前旧型号;family 匹配同样失效,
newer 恒为空列表,模型把空列表读成了"确认无后继"。修法是给工具加 `newer_lookup` / `confidence`
这类**自述可信度的字段**,并把完整过程落盘(`--trace-file`)——静默降级比报错危险得多。

第四条来自加 Google 对照基线时:**衡量工具本身也会静默作弊**。第一次实跑,记分板拿
「AirPods Pro 第2世代 右耳のみ」(单只右耳,¥15,477)当我方最低价,痛快地判了 win。
一个不诚实的基线比没有基线更糟 —— 它会让你以为自己在进步。所以对照的每个排除项都
带原因留痕(`accessory` / `defective` / `wrong_product` / `below_floor`),
`loss` 的每条漏项都带 title 和 url,让人一眼看出是真漏还是误报。
