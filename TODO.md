# 未完成 / 已知边界

记录时间:2026-08-10。当天定位并修掉 24 个根因(见 git log),下面是**没修**的部分。

分两类:**待办**(该做、只是还没做)与**已知边界**(数据层面无解或刻意不做)。

---

## 待办

### A. `get_price_statistics` 被配件污染

`get_price_statistics("ニコン D850")` 返回 **median ¥5,000 / min ¥370** —— 一台十几万日元的相机,
中位数五千日元,因为样本里全是镜头盖、保护膜、书籍。加 `condition=新品・未使用` 后更糟(median ¥1,880)。

这个统计目前对"本体贵不贵"基本没有参考价值。两次实跑里 agent 都没被误导(它没报 ¥370),
但那是靠模型自己判断绕开的,不是工具给的数据可靠。

**修法**:复用 `shared/utils/item_filters.py` 的配件/残缺品词表 + 价格下限,
并在返回里回报"过滤掉了多少条、按什么规则",让模型知道这是**本体行情**而不是关键词行情。

**没直接做的原因**:这会改变工具语义(关键词行情 → 本体行情),需要先确认要不要这样改。

### B. Google 对照基线还没跑通

代码已完成并有 39 个离线测试,但真实 API 一直没通过:

1. 先报 `Custom Search API has not been used in project ... or it is disabled`
2. 启用后变成 `Requests to this API customsearch method ... are blocked`(= API key 有 API restrictions)
3. 最后又退回第 1 种错误 —— 启用状态似乎没稳定传播

**要做的**:GCP Console → APIs & Services → 确认 Custom Search API 已启用;
→ Credentials → 该 API key → **API restrictions** 里加上 Custom Search API(或选 Don't restrict key)。

失败隔离已验证:取不到数就记 `error` + `verdict: n/a`,不影响推荐输出。

### C. `benchmarks/*.jsonl` 要不要进版本库

它会记下你的检索词与完整 Google 结果。`pyproject.toml` 里的仓库 URL 是公开的
(`github.com/xingyu-zhou/kaidoki`)。目前 `.gitignore` **没有**排除它 ——
按原计划是提交(为了攒长期趋势)。不想让购物记录进 git 就加一行 `benchmarks/`。

---

## 已知边界

### D. kakaku 只解析搜索结果第 1 页

返回里的 `coverage` 会如实交代(`catalog_models_parsed` / `total_hits_reported` / note),
但排名靠后的机型不会纳入比较。实测 "ニコン D850" 命中 738 件,第 1 页只有 6 个目录机型。

翻页会成倍增加请求数,与"低频克制取数"的原则冲突,所以先不做。

### E. 「洗浄器**対応**」≠「洗浄器**付き**」没有硬过滤

`対応` 只表示兼容,机器**不含**洗浄器(实测 ¥22,600 的「9577cc 洗浄器対応モデル」)。
它只进了 `AMBIGUOUS_KEYWORDS`(标注、不排除)和 prompt R9。

**刻意不硬过滤**:硬排除会误杀真商品。过度过滤比漏过一个配件更危险 ——
它会静默丢掉真正的便宜货,而且查不出来。

### F. family 归类对"只差数字"的命名无效

Nikon 的 D850 / D810 / D780 各自成一族(`_family_of` 剥不掉纯数字型号里的世代信息),
所以 D850 的后继型号只能给出 `newer_lookup: unknown`。

结论是**诚实的**(不会假报"无后继"),但要靠人工判断。Braun / Apple 这类有明确系列名
(`シリーズ9 Pro+` / `AirPods Pro 3`)的品牌不受影响。

### G. Mercari 标题不写型番时无法核实是否同款

大量挂牌只写「AirPods Pro (第2世代) 本体」这种,没有 `MTJV3J/A`。
记分板的 `comparability` 会标 `unknown`,prompt R7 要求告诉用户"需向卖家确认",
但数据层面无解 —— 只能提示,不能替用户断定。

### H. 卖家名取不到

Mercari 搜索 API 不返回。标题/价/成色/图/品牌/分类都有。

---

## 顺序上的教训(给未来的自己)

今天在核心比较语义(行类型 / 配置轴 cc-s / 世代轴 Pro-Pro+)还错着的时候,先加了 Google 记分板。
结果它的第一个判定是拿「AirPods Pro 第2世代 **右耳のみ**」(单只右耳 ¥15,477)当我方最低价,
痛快地报了个 `win`。

**先把被衡量的东西弄对,再建衡量工具。** 一个不诚实的基线比没有基线更糟 ——
它会让你以为自己在进步。
