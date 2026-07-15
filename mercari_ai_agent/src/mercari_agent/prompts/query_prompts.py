"""
查询解析提示词

该模块包含查询解析相关的提示词模板，用于自然语言理解和参数提取。
"""

from typing import Dict, Any, List, Optional
import json


class QueryPrompts:
    """查询解析提示词管理类"""
    
    # 基础查询解析提示词
    BASE_QUERY_ANALYSIS_PROMPT = """
以下の日本語クエリを分析し、構造化された検索パラメータを抽出してください。

クエリ: {query}

## 抽出すべき情報
1. 商品キーワード（商品名、ブランド名、特徴など）
2. 価格範囲（最低価格、最高価格）
3. 商品カテゴリー
4. 商品状態（新品、中古など）
5. 並び順の希望
6. その他の条件（色、サイズ、ブランドなど）

## 出力形式
以下のJSON形式で回答してください：
```json
{{
    "keywords": ["キーワード1", "キーワード2"],
    "price_range": {{
        "min": 最低価格,
        "max": 最高価格
    }},
    "category": "カテゴリー名",
    "condition": "商品状態",
    "brand": "ブランド名",
    "sort_by": "並び順",
    "other_filters": {{
        "color": "色",
        "size": "サイズ",
        "additional": "その他の条件"
    }},
    "query_intent": "検索意図",
    "confidence": 0.8
}}
```

## 注意事項
- 不明な項目は null にしてください
- 価格は数値で指定してください
- 信頼度（confidence）は0-1の範囲で設定してください
"""

    # 複雑なクエリ解析用プロンプト
    COMPLEX_QUERY_ANALYSIS_PROMPT = """
以下の複雑な日本語クエリを詳細に分析し、構造化された検索パラメータを抽出してください。

クエリ: {query}
コンテキスト: {context}

## 高度な分析項目
1. 複数の商品カテゴリーの識別
2. 条件付き検索パラメータ
3. 優先度の判定
4. 曖昧性の解決
5. 代替検索戦略の提案

## 詳細出力形式
```json
{{
    "primary_search": {{
        "keywords": ["主要キーワード"],
        "price_range": {{"min": 価格, "max": 価格}},
        "category": "メインカテゴリー",
        "condition": "商品状態",
        "brand": "ブランド名",
        "sort_by": "並び順",
        "filters": {{}}
    }},
    "alternative_searches": [
        {{
            "keywords": ["代替キーワード"],
            "reason": "代替理由",
            "confidence": 0.7
        }}
    ],
    "query_complexity": "simple|moderate|complex",
    "ambiguities": [
        {{
            "field": "曖昧な項目",
            "options": ["選択肢1", "選択肢2"],
            "recommendation": "推奨選択肢"
        }}
    ],
    "intent_analysis": {{
        "primary_intent": "主要意図",
        "sub_intents": ["副次意図"],
        "user_type": "初心者|中級者|上級者"
    }},
    "confidence": 0.8
}}
```
"""

    # 意図分類用プロンプト
    INTENT_CLASSIFICATION_PROMPT = """
以下の日本語クエリの意図を分類してください。

クエリ: {query}

## 意図カテゴリー
1. search - 商品検索
2. compare - 商品比較
3. analyze - 商品分析
4. recommend - 推薦依頼
5. question - 質問・相談
6. filter - 絞り込み
7. sort - 並び替え

## 出力形式
```json
{{
    "primary_intent": "主要意図",
    "secondary_intents": ["副次意図"],
    "confidence": 0.9,
    "reasoning": "分類理由",
    "suggested_action": "推奨アクション"
}}
```
"""

    # パラメータ検証用プロンプト
    PARAMETER_VALIDATION_PROMPT = """
以下の検索パラメータを検証し、必要に応じて修正してください。

パラメータ: {parameters}

## 検証項目
1. 価格範囲の妥当性
2. カテゴリーの存在確認
3. 商品状態の正確性
4. キーワードの適切性
5. 矛盾する条件の検出

## 修正提案形式
```json
{{
    "validated_parameters": {{
        "修正後のパラメータ": "値"
    }},
    "corrections": [
        {{
            "field": "修正項目",
            "original": "元の値",
            "corrected": "修正後の値",
            "reason": "修正理由"
        }}
    ],
    "warnings": [
        {{
            "field": "警告項目",
            "message": "警告メッセージ",
            "severity": "low|medium|high"
        }}
    ],
    "suggestions": [
        {{
            "field": "提案項目",
            "suggestion": "提案内容",
            "benefit": "利点"
        }}
    ]
}}
```
"""

    # 日本語処理特化プロンプト
    JAPANESE_PROCESSING_PROMPT = """
以下の日本語テキストを処理し、検索に適した形式に変換してください。

テキスト: {text}

## 処理項目
1. 漢字・ひらがな・カタカナの正規化
2. 同義語・類義語の展開
3. 略語の展開
4. 表記揺れの統一
5. 不要な文字の除去

## 出力形式
```json
{{
    "normalized_text": "正規化されたテキスト",
    "synonyms": ["同義語1", "同義語2"],
    "expanded_terms": ["展開語1", "展開語2"],
    "alternative_readings": ["読み方1", "読み方2"],
    "search_keywords": ["検索キーワード1", "検索キーワード2"],
    "processing_notes": "処理に関する注意点"
}}
```

## 日本語特有の処理
- 送り仮名の統一
- 長音符の正規化
- 半角・全角の統一
- 商品名の表記揺れ対応
"""

    @classmethod
    def get_query_analysis_prompt(cls, query: str, context: str = None, complexity: str = "simple") -> str:
        """
        クエリ分析用プロンプトを取得
        
        Args:
            query: 分析するクエリ
            context: 追加コンテキスト
            complexity: 複雑度レベル
            
        Returns:
            str: 分析プロンプト
        """
        if complexity == "complex":
            return cls.COMPLEX_QUERY_ANALYSIS_PROMPT.format(
                query=query,
                context=context or "なし"
            )
        else:
            return cls.BASE_QUERY_ANALYSIS_PROMPT.format(query=query)
    
    @classmethod
    def get_intent_classification_prompt(cls, query: str) -> str:
        """
        意図分類用プロンプトを取得
        
        Args:
            query: 分類するクエリ
            
        Returns:
            str: 意図分類プロンプト
        """
        return cls.INTENT_CLASSIFICATION_PROMPT.format(query=query)
    
    @classmethod
    def get_parameter_validation_prompt(cls, parameters: Dict[str, Any]) -> str:
        """
        パラメータ検証用プロンプトを取得
        
        Args:
            parameters: 検証するパラメータ
            
        Returns:
            str: 検証プロンプト
        """
        return cls.PARAMETER_VALIDATION_PROMPT.format(
            parameters=json.dumps(parameters, ensure_ascii=False, indent=2)
        )
    
    @classmethod
    def get_japanese_processing_prompt(cls, text: str) -> str:
        """
        日本語処理用プロンプトを取得
        
        Args:
            text: 処理する日本語テキスト
            
        Returns:
            str: 日本語処理プロンプト
        """
        return cls.JAPANESE_PROCESSING_PROMPT.format(text=text)
    
    @classmethod
    def get_category_suggestion_prompt(cls, keywords: List[str]) -> str:
        """
        カテゴリー提案用プロンプトを取得
        
        Args:
            keywords: キーワードリスト
            
        Returns:
            str: カテゴリー提案プロンプト
        """
        keywords_text = ", ".join(keywords)
        
        return f"""
以下のキーワードに基づいて、最適なメルカリのカテゴリーを提案してください。

キーワード: {keywords_text}

## メルカリのメインカテゴリー
- レディース
- メンズ
- ベビー・キッズ
- インテリア・住まい・小物
- 本・音楽・ゲーム
- おもちゃ・ホビー・グッズ
- コスメ・香水・美容
- 家電・スマホ・カメラ
- スポーツ・レジャー
- ハンドメイド
- チケット
- 自動車・オートバイ
- その他

## 出力形式
```json
{{
    "recommended_categories": [
        {{
            "category": "カテゴリー名",
            "confidence": 0.9,
            "reasoning": "推薦理由"
        }}
    ],
    "subcategory_suggestions": [
        {{
            "main_category": "メインカテゴリー",
            "subcategory": "サブカテゴリー",
            "confidence": 0.8
        }}
    ]
}}
```
"""

    @classmethod
    def get_query_expansion_prompt(cls, original_query: str, search_results_count: int = 0) -> str:
        """
        クエリ拡張用プロンプトを取得
        
        Args:
            original_query: 元のクエリ
            search_results_count: 検索結果数
            
        Returns:
            str: クエリ拡張プロンプト
        """
        return f"""
元のクエリ: {original_query}
検索結果数: {search_results_count}

検索結果が少ない場合は、以下の方法でクエリを拡張してください：

## 拡張方法
1. 同義語・類義語の追加
2. 関連キーワードの提案
3. 検索条件の緩和
4. 別の商品カテゴリーの提案
5. 表記揺れの考慮

## 出力形式
```json
{{
    "expanded_queries": [
        {{
            "query": "拡張されたクエリ",
            "expansion_type": "同義語|関連語|条件緩和|カテゴリー変更",
            "expected_results": "期待される結果の改善",
            "confidence": 0.8
        }}
    ],
    "search_strategy": "検索戦略の説明",
    "fallback_options": [
        {{
            "option": "代替選択肢",
            "description": "説明"
        }}
    ]
}}
```
"""

    @classmethod
    def get_query_refinement_prompt(cls, original_query: str, search_results: List[Dict], user_feedback: str = None) -> str:
        """
        クエリ改善用プロンプトを取得
        
        Args:
            original_query: 元のクエリ
            search_results: 検索結果
            user_feedback: ユーザーフィードバック
            
        Returns:
            str: クエリ改善プロンプト
        """
        results_summary = f"検索結果数: {len(search_results)}"
        if search_results:
            results_summary += f"\n最初の3件:\n" + "\n".join([
                f"- {result.get('title', 'タイトル不明')} (¥{result.get('price', 'N/A')})"
                for result in search_results[:3]
            ])
        
        feedback_text = f"\nユーザーフィードバック: {user_feedback}" if user_feedback else ""
        
        return f"""
元のクエリ: {original_query}
{results_summary}{feedback_text}

検索結果とユーザーフィードバックを基に、より適切な検索クエリを提案してください。

## 改善観点
1. 検索精度の向上
2. 結果の多様性確保
3. ユーザーニーズの適合
4. 不要な結果の除外

## 出力形式
```json
{{
    "refined_query": "改善されたクエリ",
    "refinement_reason": "改善理由",
    "expected_improvements": ["改善点1", "改善点2"],
    "additional_filters": {{
        "filter_type": "フィルター値"
    }},
    "confidence": 0.9
}}
```
"""