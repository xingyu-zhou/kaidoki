"""
商品标题过滤：把"配件 / 残缺品"从"本体"里分出来。

为什么需要单一来源:这些关键词原先只以自然语言写在 `agent_service.SYSTEM_PROMPT`
的 R2 规则里。Google 对照基线两侧都要用**同一套**过滤 —— 否则我方一个 ¥2,299 的
替刃会被当成"最低价"赢下比较,记分板直接失去意义。prompt 与打分逻辑必须同源,
不能各写一份慢慢漂。

分三类,语义不同,不要混用:

- `ACCESSORY_KEYWORDS`  —— 根本不是这个产品(替刃、收纳盒、充电线)。硬排除。
- `DEFECTIVE_KEYWORDS`  —— 是这个产品但不完整/不可用(刃無し、ジャンク)。硬排除。
- `AMBIGUOUS_KEYWORDS`  —— 可能可用也可能不(本体のみ、展示品)。**不排除**,只标注,
  让人自己判断。过度过滤会静默丢掉真正的便宜货,比漏过一个配件更危险。

关键词都刻意取得**具体**。反例:不要用裸的 "ケース" —— "AirPods Pro 2
MagSafe充電ケース(USB-C)付き" 是**商品本体的正式名称**,裸匹配会把真商品判成配件。
所以只收 "収納ケース" / "保護ケース" / "ケースのみ" 这类明确指向配件的写法。

Author: Kaidoki Team (google benchmark)
"""

import re
from typing import List, Optional, Tuple

# 不是这个产品:耗材 / 替换件 / 周边
ACCESSORY_KEYWORDS: List[str] = [
    "替刃",
    "替え刃",
    "交換用",
    "網刃",
    "内刃",
    "シェーバーヘッド",
    "美顔ヘッド",
    "収納ケース",
    "保護ケース",
    "ケースのみ",
    "充電スタンド",
    "充電ケーブル",
    "充電器のみ",
    "洗浄液",
    "洗浄カートリッジ",
    "洗浄器のみ",
    "互換品",
    "互換",
    "2個セット",
    "3個セット",
    "4個セット",
    "フィルム",
    "イヤーピース",
    "スキンシール",
    "ステッカー",
    "ストラップ",
    # 只做保护壳的品牌。实测 "casetify ナルト Akatsuki AirPods pro 2 暁" 这类标题
    # 里根本不出现「ケース」，只能靠品牌名识别。
    "casetify",
    "spigen",
    "elago",
    "bottega",
]

# 条件排除:命中 kw 但标题里同时出现任一 exception 时**不**排除。
# 「ケース」必须这样处理 —— "AirPods Pro 2 MagSafe充電ケース(USB-C)付き" 是**商品正式名**，
# 而 "airpods pro ケース Bottega" 是保护壳。裸匹配会误杀真商品，不匹配会放进配件。
CONDITIONAL_ACCESSORY: List[Tuple[str, List[str]]] = [
    ("ケース", ["充電ケース", "ケース付", "充電器付", "ケース欠品"]),
    ("カバー", ["カバー付"]),
]

# 是这个产品但不完整 / 不可用
DEFECTIVE_KEYWORDS: List[str] = [
    "刃無し",
    "刃なし",
    "刃無",
    "ジャンク",
    "部品取り",
    "故障",
    "訳あり",
    "難あり",
    "動作未確認",
    # 单只耳机：实测 "AirPods Pro 第2世代　右耳のみ　…　Apple正規品新品" ¥15,477
    # 会被当成"我方最低价"，直接刷出一个假胜利。
    "右耳のみ",
    "左耳のみ",
    "右耳",
    "左耳",
    "片耳",
]

# 需要人判断,不硬排除
AMBIGUOUS_KEYWORDS: List[str] = [
    "本体のみ",
    "展示品",
    "開封済",
    "箱なし",
    "箱無し",
    # 「洗浄器**対応**」只表示兼容，机器**不含**洗浄器 —— 和「洗浄器付き」差一个洗浄器的钱。
    # 实测 ¥22,600 的「9577cc 洗浄器対応モデル」就是这种写法。
    "洗浄器対応",
    "洗浄機対応",
]


# --------------------------------------------------------------------------- #
# 品类 → 二手可接受度
# --------------------------------------------------------------------------- #
# 不是所有品类的"二手最划算"都成立。相机/PC/手机这类耐用电子，成色好的二手完全可用；
# 但电动剃须刀这类**直接接触皮肤**的个人用品，卫生不可逆，只该买新品 ——
# 而且 Mercari 的「新品・未使用」是个人卖家自述，无法核实是否真未开封。
USED_OK_KEYWORDS: List[str] = [
    "カメラ", "一眼", "ミラーレス", "レンズ", "ボディ", "三脚", "ストロボ",
    "パソコン", "ノートパソコン", "PC", "MacBook", "iMac", "デスクトップ",
    "iPad", "タブレット", "スマホ", "スマートフォン", "iPhone", "Android",
    "モニター", "ディスプレイ", "プリンター", "ゲーム機", "Switch", "PlayStation",
    "スピーカー", "アンプ", "3Dプリンタ", "腕時計", "楽器",
]

NEW_ONLY_KEYWORDS: List[str] = [
    "シェーバー", "髭剃り", "ひげそり", "ヒゲトリマー", "バリカン",
    "電動歯ブラシ", "歯ブラシ", "歯間", "脱毛器", "光美容器", "美顔器",
    "鼻毛カッター", "耳かき", "体温計", "補聴器", "マウスピース",
    "哺乳瓶", "化粧品", "下着", "水着",
]

# 直接接触皮肤/耳道但不在上面两表里 —— 提示卫生顾虑后由用户决定，别替他决定。
JUDGEMENT_CALL_KEYWORDS: List[str] = [
    "イヤホン", "カナル型", "ヘッドホン", "イヤーカフ", "ヘアアイロン", "ドライヤー",
]


def used_acceptability(text: str) -> str:
    """按品类判断二手可接受度: "used_ok" | "new_only" | "judgement_call" | "unknown"。"""
    t = (text or "")
    lower = t.lower()

    def hit(words: List[str]) -> bool:
        return any(w.lower() in lower for w in words)

    if hit(NEW_ONLY_KEYWORDS):
        return "new_only"
    if hit(JUDGEMENT_CALL_KEYWORDS):
        return "judgement_call"
    if hit(USED_OK_KEYWORDS):
        return "used_ok"
    return "unknown"


def prompt_category_lines() -> str:
    """给 SYSTEM_PROMPT 用的品类片段，确保 prompt 与判断逻辑同源。"""
    return (
        f"  - 耐用电子(二手可以):{' / '.join(USED_OK_KEYWORDS[:14])} 等;\n"
        f"  - 个人护理用品(只买新品):{' / '.join(NEW_ONLY_KEYWORDS[:12])} 等;\n"
        f"  - 需要先提示卫生顾虑、由用户决定:{' / '.join(JUDGEMENT_CALL_KEYWORDS)}。"
    )


def classify_exclusion(title: str) -> Optional[Tuple[str, str]]:
    """标题命中硬排除词时返回 (类别, 命中词);否则 None。

    返回命中词而不是只返回 bool —— 记分板要能交代"这条为什么被排除",
    否则误排除会变成查不出来的静默错误。
    """
    t = title or ""
    lower = t.lower()
    for kw in DEFECTIVE_KEYWORDS:  # 残缺优先报告，比"配件"更严重
        if kw in t:
            return ("defective", kw)
    for kw in ACCESSORY_KEYWORDS:
        if kw.lower() in lower:  # 品牌名是拉丁字母，要忽略大小写
            return ("accessory", kw)
    for kw, exceptions in CONDITIONAL_ACCESSORY:
        if kw in t and not any(exc in t for exc in exceptions):
            return ("accessory", kw)
    return None


def ambiguous_flags(title: str) -> List[str]:
    """标题里命中的"需人判断"词(不排除,仅标注)。"""
    t = title or ""
    return [kw for kw in AMBIGUOUS_KEYWORDS if kw in t]


def looks_like_body(
    title: str,
    price: Optional[int] = None,
    floor_price: Optional[int] = None,
) -> bool:
    """这条像不像"完整本体"。

    floor_price:价格下限(通常取新品最安値的一个比例)。低于它的基本是配件 ——
    关键词表永远补不全,价格下限是兜底的第二道闸。
    """
    if classify_exclusion(title) is not None:
        return False
    if floor_price is not None and price is not None and price < floor_price:
        return False
    return True


def prompt_keyword_lines() -> str:
    """给 SYSTEM_PROMPT 用的词表片段，确保 prompt 与打分逻辑同源。"""
    return (
        f"  - 配件(不是本体):{' / '.join(ACCESSORY_KEYWORDS[:12])} 等;\n"
        f"  - 残缺品(不能当完整新品报价):{' / '.join(DEFECTIVE_KEYWORDS[:8])} 等;\n"
        f"  - 需说明清楚再报:{' / '.join(AMBIGUOUS_KEYWORDS)}。"
    )
