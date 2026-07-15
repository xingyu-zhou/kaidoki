"""
格式化提示词

该模块包含输出格式化相关的提示词模板，用于生成用户友好的响应。
"""

from typing import Dict, Any, List, Optional
import json


class FormattingPrompts:
    """格式化提示词管理类"""
    
    # 基础格式化提示词
    BASE_FORMATTING_PROMPT = """
以下の情報を、ユーザーにとって読みやすく理解しやすい形式で整理してください。

情報: {content}
出力形式: {format_type}

## 基本要件
- 簡潔で明確な表現
- 重要な情報を強調
- 構造化された見やすいレイアウト
- 適切な日本語表現

## 出力形式に応じた調整
- Markdown: 見出し、リスト、強調を適切に使用
- HTML: セマンティックなタグを使用
- プレーンテキスト: 読みやすい段落構成
- JSON: 構造化された階層形式
"""

    # 商品情報フォーマット用プロンプト
    PRODUCT_INFO_FORMAT_PROMPT = """
以下の商品情報を、魅力的で分かりやすい形式で整理してください。

商品データ: {product_data}

## 表示項目
1. 商品名とメイン画像
2. 価格情報（現在価格、相場比較）
3. 商品状態と詳細
4. 出品者情報
5. 配送・取引条件
6. 商品の特徴・魅力
7. 注意点・リスク

## 出力形式
```markdown
# {商品名}

## 📋 基本情報
- **価格**: ¥{価格} {(相場比較)}
- **状態**: {商品状態}
- **カテゴリー**: {カテゴリー}
- **出品者**: {出品者名} (評価: {評価})

## 🎯 商品の特徴
{商品の魅力的な特徴}

## ⚠️ 注意点
{購入時の注意点}

## 🚚 配送・取引
- **配送方法**: {配送方法}
- **配送料**: {配送料}
- **発送日数**: {発送日数}

## 💡 購入アドバイス
{購入判断のためのアドバイス}
```
"""

    # 検索結果フォーマット用プロンプト
    SEARCH_RESULTS_FORMAT_PROMPT = """
以下の検索結果を、比較しやすい形式で整理してください。

検索結果: {search_results}
検索クエリ: {query}

## 整理方針
1. 関連度の高い順に並べる
2. 価格帯別にグループ化
3. 商品状態別に分類
4. 比較ポイントを明確化

## 出力形式
```markdown
# 検索結果: {query}

## 🔍 検索条件
- キーワード: {キーワード}
- 価格範囲: {価格範囲}
- 商品状態: {商品状態}
- 検索結果数: {件数}

## 💎 おすすめ商品

### 1位: {商品名}
- **価格**: ¥{価格}
- **状態**: {状態}
- **評価**: {評価}
- **おすすめ理由**: {理由}

### 2位: {商品名}
...

## 💰 価格帯別一覧

### 予算重視 (¥{価格帯})
{該当商品リスト}

### バランス重視 (¥{価格帯})
{該当商品リスト}

### 品質重視 (¥{価格帯})
{該当商品リスト}

## 📊 検索結果分析
{検索結果の傾向分析}
```
"""

    # 比較表フォーマット用プロンプト
    COMPARISON_TABLE_FORMAT_PROMPT = """
以下の商品を比較表形式で整理してください。

比較対象: {products}
比較項目: {comparison_fields}

## 比較表作成要件
1. 重要な項目を優先的に表示
2. 違いが明確に分かるように強調
3. 最適な選択肢を示唆
4. 客観的な情報提供

## 出力形式
```markdown
# 商品比較表

| 項目 | 商品A | 商品B | 商品C |
|------|-------|-------|-------|
| **商品名** | {商品名A} | {商品名B} | {商品名C} |
| **価格** | ¥{価格A} | ¥{価格B} | ¥{価格C} |
| **状態** | {状態A} | {状態B} | {状態C} |
| **出品者評価** | {評価A} | {評価B} | {評価C} |
| **配送料** | {配送料A} | {配送料B} | {配送料C} |
| **総合評価** | ⭐{評価A} | ⭐{評価B} | ⭐{評価C} |

## 🏆 推薦ランキング

### 1位: {商品名}
**選出理由**: {理由}

### 2位: {商品名}
**選出理由**: {理由}

### 3位: {商品名}
**選出理由**: {理由}

## 💡 選択指針

### 予算重視なら → {商品名}
### 品質重視なら → {商品名}
### 安全性重視なら → {商品名}
```
"""

    # 分析レポート用プロンプト
    ANALYSIS_REPORT_FORMAT_PROMPT = """
以下の分析結果を包括的なレポート形式で整理してください。

分析データ: {analysis_data}
分析対象: {target}

## レポート構成
1. エグゼクティブサマリー
2. 詳細分析結果
3. 推薦事項
4. リスク・注意点
5. 次のステップ

## 出力形式
```markdown
# 商品分析レポート: {商品名}

## 📊 エグゼクティブサマリー
{分析結果の要約}

**総合評価**: {総合評価}/5.0
**推薦度**: {推薦度}
**主要な強み**: {強み}
**主要な懸念**: {懸念}

## 🔍 詳細分析

### 価格分析
- **現在価格**: ¥{現在価格}
- **市場相場**: ¥{相場価格}
- **価格妥当性**: {価格評価}
- **コスパ評価**: {コスパ評価}

### 商品状態分析
- **記載状態**: {記載状態}
- **実際予想**: {実際予想}
- **状態リスク**: {状態リスク}

### 出品者分析
- **評価**: {出品者評価}
- **取引実績**: {取引実績}
- **信頼度**: {信頼度}

## 💡 推薦事項

### ✅ 購入を推薦する理由
{推薦理由}

### ⚠️ 注意すべき点
{注意点}

### 🎯 最適な購入タイミング
{購入タイミング}

## 🚨 リスク評価

### 高リスク項目
{高リスク項目}

### 中リスク項目
{中リスク項目}

### 低リスク項目
{低リスク項目}

## 🎯 次のステップ

1. {ステップ1}
2. {ステップ2}
3. {ステップ3}

## 📈 代替選択肢
{代替商品の提案}
```
"""

    # 会話応答フォーマット用プロンプト
    CONVERSATION_FORMAT_PROMPT = """
以下の情報を、自然で親しみやすい会話形式で整理してください。

応答内容: {content}
ユーザーの質問: {user_question}
コンテキスト: {context}

## 会話スタイル
- 親しみやすく丁寧な日本語
- 専門用語は分かりやすく説明
- 具体的で実用的な情報提供
- ユーザーの立場に立ったアドバイス

## 構成要素
1. 質問への直接的な回答
2. 補足説明・詳細情報
3. 実用的なアドバイス
4. 次のステップの提案

## 出力例
```
{ユーザー様の質問}について、詳しく説明させていただきますね。

{質問への直接的な回答}

{補足説明}

{実用的なアドバイス}

{次のステップの提案}

他にご不明な点がございましたら、お気軽にお尋ねください。
```
"""

    @classmethod
    def get_product_info_format_prompt(cls, product_data: Dict[str, Any]) -> str:
        """
        商品情報フォーマット用プロンプトを取得
        
        Args:
            product_data: 商品データ
            
        Returns:
            str: フォーマットプロンプト
        """
        return cls.PRODUCT_INFO_FORMAT_PROMPT.format(
            product_data=json.dumps(product_data, ensure_ascii=False, indent=2)
        )
    
    @classmethod
    def get_search_results_format_prompt(cls, search_results: List[Dict[str, Any]], query: str) -> str:
        """
        検索結果フォーマット用プロンプトを取得
        
        Args:
            search_results: 検索結果
            query: 検索クエリ
            
        Returns:
            str: フォーマットプロンプト
        """
        return cls.SEARCH_RESULTS_FORMAT_PROMPT.format(
            search_results=json.dumps(search_results, ensure_ascii=False, indent=2),
            query=query
        )
    
    @classmethod
    def get_comparison_table_format_prompt(cls, products: List[Dict[str, Any]], comparison_fields: List[str]) -> str:
        """
        比較表フォーマット用プロンプトを取得
        
        Args:
            products: 比較対象商品
            comparison_fields: 比較項目
            
        Returns:
            str: フォーマットプロンプト
        """
        return cls.COMPARISON_TABLE_FORMAT_PROMPT.format(
            products=json.dumps(products, ensure_ascii=False, indent=2),
            comparison_fields=comparison_fields
        )
    
    @classmethod
    def get_analysis_report_format_prompt(cls, analysis_data: Dict[str, Any], target: str) -> str:
        """
        分析レポート用プロンプトを取得
        
        Args:
            analysis_data: 分析データ
            target: 分析対象
            
        Returns:
            str: フォーマットプロンプト
        """
        return cls.ANALYSIS_REPORT_FORMAT_PROMPT.format(
            analysis_data=json.dumps(analysis_data, ensure_ascii=False, indent=2),
            target=target
        )
    
    @classmethod
    def get_conversation_format_prompt(cls, content: str, user_question: str, context: str = "") -> str:
        """
        会話応答フォーマット用プロンプトを取得
        
        Args:
            content: 応答内容
            user_question: ユーザーの質問
            context: コンテキスト
            
        Returns:
            str: フォーマットプロンプト
        """
        return cls.CONVERSATION_FORMAT_PROMPT.format(
            content=content,
            user_question=user_question,
            context=context
        )
    
    @classmethod
    def get_summary_format_prompt(cls, data: Dict[str, Any], summary_type: str = "brief") -> str:
        """
        要約フォーマット用プロンプトを取得
        
        Args:
            data: 要約対象データ
            summary_type: 要約タイプ (brief/detailed/executive)
            
        Returns:
            str: フォーマットプロンプト
        """
        summary_styles = {
            "brief": "簡潔で要点のみ",
            "detailed": "詳細で包括的",
            "executive": "意思決定者向けの要約"
        }
        
        style = summary_styles.get(summary_type, "簡潔で要点のみ")
        
        return f"""
以下の情報を{style}な要約形式で整理してください。

データ: {json.dumps(data, ensure_ascii=False, indent=2)}

## 要約要件
- 重要な情報を優先的に表示
- {style}
- 読みやすい構造化
- 適切な日本語表現

## 出力形式
```markdown
# 要約

## 🎯 重要ポイント
{{重要ポイント}}

## 📊 主要データ
{{主要データ}}

## 💡 推薦・提案
{{推薦・提案}}

## ⚠️ 注意事項
{{注意事項}}
```
"""

    @classmethod
    def get_error_message_format_prompt(cls, error_type: str, error_details: str) -> str:
        """
        エラーメッセージフォーマット用プロンプトを取得
        
        Args:
            error_type: エラータイプ
            error_details: エラー詳細
            
        Returns:
            str: フォーマットプロンプト
        """
        return f"""
以下のエラーを、ユーザーにとって分かりやすく親しみやすい形式で説明してください。

エラータイプ: {error_type}
エラー詳細: {error_details}

## 説明要件
- 技術的な専門用語を避ける
- 解決方法を具体的に提示
- 親しみやすく丁寧な口調
- 代替手段の提案

## 出力形式
```markdown
# 申し訳ございません 🙏

{{エラー状況の説明}}

## 🔧 解決方法

### 1. {{解決方法1}}
{{詳細説明}}

### 2. {{解決方法2}}
{{詳細説明}}

### 3. {{解決方法3}}
{{詳細説明}}

## 🆘 それでも解決しない場合

{{追加のサポート案内}}

## 💡 代替方法

{{代替手段の提案}}

ご不便をおかけして申し訳ございません。他にできることがございましたら、お気軽にお声がけください。
```
"""

    @classmethod
    def get_recommendation_format_prompt(cls, recommendations: List[Dict[str, Any]], user_profile: Dict[str, Any]) -> str:
        """
        推薦フォーマット用プロンプトを取得
        
        Args:
            recommendations: 推薦リスト
            user_profile: ユーザープロファイル
            
        Returns:
            str: フォーマットプロンプト
        """
        return f"""
以下の推薦結果を、ユーザーにとって魅力的で説得力のある形式で整理してください。

推薦リスト: {json.dumps(recommendations, ensure_ascii=False, indent=2)}
ユーザープロファイル: {json.dumps(user_profile, ensure_ascii=False, indent=2)}

## 推薦表示要件
- 各推薦の理由を明確に説明
- ユーザーの立場に立った表現
- 比較しやすい構造
- 行動を促す内容

## 出力形式
```markdown
# あなたにおすすめの商品 ✨

## 🎯 最適な選択

### 🥇 第1位: {{商品名}}
**価格**: ¥{{価格}}
**おすすめ理由**: {{理由}}

{{商品の魅力的な説明}}

**👍 こんな方におすすめ**
{{ターゲット説明}}

---

### 🥈 第2位: {{商品名}}
{{同様の形式}}

---

### 🥉 第3位: {{商品名}}
{{同様の形式}}

## 💡 選択のポイント

### 予算を重視するなら
{{予算重視の推薦}}

### 品質を重視するなら
{{品質重視の推薦}}

### 安全性を重視するなら
{{安全性重視の推薦}}

## 🛒 購入に向けて

{{購入前のアドバイス}}

ご質問やご不明な点がございましたら、お気軽にお尋ねください。
```
"""