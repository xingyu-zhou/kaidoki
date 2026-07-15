"""
分析推理提示词

该模块包含产品分析、价格分析、推荐理由生成等提示词模板。
"""

from typing import Dict, Any, List, Optional
import json


class AnalysisPrompts:
    """分析推理提示词管理类"""
    
    # 基础产品分析提示词
    BASE_PRODUCT_ANALYSIS_PROMPT = """
以下の商品情報を詳細に分析し、購入判断に役立つ情報を提供してください。

商品情報: {product_info}

## 分析項目
1. 価格妥当性
2. 商品状態評価
3. 出品者信頼度
4. 市場相場との比較
5. 購入リスク評価

## 出力形式
```json
{{
    "analysis_summary": "分析結果の要約",
    "price_analysis": {{
        "current_price": 現在価格,
        "market_price": 市場相場,
        "price_assessment": "高い|適正|安い",
        "value_score": 0.8,
        "reasoning": "価格評価の理由"
    }},
    "condition_analysis": {{
        "stated_condition": "出品者記載の状態",
        "estimated_condition": "推定実際状態",
        "condition_risk": "low|medium|high",
        "key_concerns": ["注意点1", "注意点2"]
    }},
    "seller_analysis": {{
        "seller_rating": 評価,
        "transaction_count": 取引数,
        "reliability_score": 0.9,
        "risk_factors": ["リスク要因"]
    }},
    "recommendation": {{
        "should_buy": True,
        "confidence": 0.8,
        "reasoning": "推薦理由",
        "alternatives": ["代替選択肢"]
    }}
}}
```
"""

    # 比較分析用プロンプト
    COMPARATIVE_ANALYSIS_PROMPT = """
以下の商品を比較分析し、最適な選択肢を推薦してください。

比較対象商品: {products}

## 比較観点
1. 価格パフォーマンス
2. 商品品質
3. 取引安全性
4. 配送条件
5. 総合評価

## 出力形式
```json
{{
    "comparison_matrix": {{
        "商品ID": {{
            "price_score": 0.8,
            "quality_score": 0.9,
            "safety_score": 0.7,
            "overall_score": 0.8
        }}
    }},
    "ranking": [
        {{
            "rank": 1,
            "product_id": "商品ID",
            "score": 0.85,
            "strengths": ["強み1", "強み2"],
            "weaknesses": ["弱み1", "弱み2"]
        }}
    ],
    "recommendation": {{
        "best_choice": "推薦商品ID",
        "reasoning": "推薦理由",
        "scenario_based": {{
            "budget_conscious": "予算重視の場合の推薦",
            "quality_focused": "品質重視の場合の推薦",
            "safety_first": "安全性重視の場合の推薦"
        }}
    }}
}}
```
"""

    # 価格分析特化プロンプト
    PRICE_ANALYSIS_PROMPT = """
以下の商品の価格を詳細に分析してください。

商品: {product}
価格: {price}円
カテゴリー: {category}
状態: {condition}

## 価格分析要素
1. 同カテゴリー商品との比較
2. 状態を考慮した価格妥当性
3. 値下げ交渉の可能性
4. 価格推移の予測
5. 購入タイミングの評価

## 出力形式
```json
{{
    "price_analysis": {{
        "current_price": {price},
        "market_range": {{
            "min": 最低価格,
            "max": 最高価格,
            "average": 平均価格
        }},
        "price_position": "市場での価格位置",
        "value_assessment": "割高|適正|割安",
        "confidence": 0.85
    }},
    "negotiation_analysis": {{
        "negotiation_potential": "high|medium|low",
        "suggested_offer": 提案価格,
        "negotiation_strategy": "交渉戦略"
    }},
    "timing_analysis": {{
        "buy_urgency": "high|medium|low",
        "price_trend": "上昇|安定|下降",
        "optimal_timing": "購入最適時期"
    }},
    "recommendations": [
        {{
            "action": "推薦アクション",
            "reasoning": "理由",
            "priority": "high|medium|low"
        }}
    ]
}}
```
"""

    # 推薦理由生成プロンプト
    RECOMMENDATION_REASONING_PROMPT = """
以下の商品推薦について、説得力のある理由を生成してください。

推薦商品: {product}
ユーザープロファイル: {user_profile}
推薦スコア: {score}

## 理由生成要素
1. ユーザーニーズとの適合性
2. 価格・品質のバランス
3. 安全性・信頼性
4. 独自の価値提案
5. 代替選択肢との差別化

## 出力形式
```json
{{
    "main_reasoning": "主要な推薦理由",
    "detailed_reasons": [
        {{
            "category": "価格",
            "reason": "具体的な理由",
            "supporting_evidence": "根拠データ"
        }},
        {{
            "category": "品質",
            "reason": "具体的な理由",
            "supporting_evidence": "根拠データ"
        }},
        {{
            "category": "適合性",
            "reason": "具体的な理由",
            "supporting_evidence": "根拠データ"
        }}
    ],
    "user_benefits": [
        {{
            "benefit": "ユーザーへの利益",
            "impact": "high|medium|low",
            "explanation": "詳細説明"
        }}
    ],
    "risk_mitigation": [
        {{
            "risk": "潜在的リスク",
            "mitigation": "対処方法",
            "importance": "high|medium|low"
        }}
    ],
    "call_to_action": "行動喚起メッセージ"
}}
```
"""

    # 市場分析用プロンプト
    MARKET_ANALYSIS_PROMPT = """
以下の商品カテゴリーまたは特定商品について市場分析を実施してください。

分析対象: {target}
分析期間: {period}
データソース: {data_source}

## 市場分析項目
1. 価格動向分析
2. 需要・供給状況
3. 競合商品分析
4. 季節性・トレンド
5. 予測と見通し

## 出力形式
```json
{{
    "market_overview": {{
        "market_size": "市場規模",
        "growth_rate": "成長率",
        "key_trends": ["主要トレンド"],
        "market_maturity": "新興|成長|成熟|衰退"
    }},
    "price_trends": {{
        "current_average": 現在平均価格,
        "price_change": "価格変動率",
        "trend_direction": "上昇|安定|下降",
        "seasonal_patterns": "季節性パターン"
    }},
    "supply_demand": {{
        "supply_level": "供給水準",
        "demand_level": "需要水準",
        "balance": "供給過多|均衡|需要過多",
        "inventory_turnover": "在庫回転率"
    }},
    "competitive_landscape": {{
        "main_competitors": ["主要競合"],
        "differentiation_factors": ["差別化要因"],
        "market_share": "市場シェア情報"
    }},
    "forecast": {{
        "short_term": "短期予測",
        "medium_term": "中期予測",
        "key_factors": ["予測要因"],
        "confidence": 0.7
    }}
}}
```
"""

    # リスク評価用プロンプト
    RISK_ASSESSMENT_PROMPT = """
以下の商品取引に関するリスク評価を実施してください。

商品: {product}
出品者: {seller}
取引条件: {conditions}

## リスク評価項目
1. 商品品質リスク
2. 出品者信頼性リスク
3. 取引プロセスリスク
4. 法的・規制リスク
5. 経済的リスク

## 出力形式
```json
{{
    "overall_risk": "low|medium|high",
    "risk_score": 0.3,
    "risk_categories": {{
        "product_quality": {{
            "risk_level": "low|medium|high",
            "probability": 0.2,
            "impact": "low|medium|high",
            "mitigation": "対策方法"
        }},
        "seller_reliability": {{
            "risk_level": "low|medium|high",
            "probability": 0.1,
            "impact": "low|medium|high",
            "mitigation": "対策方法"
        }},
        "transaction_process": {{
            "risk_level": "low|medium|high",
            "probability": 0.15,
            "impact": "low|medium|high",
            "mitigation": "対策方法"
        }}
    }},
    "key_concerns": [
        {{
            "concern": "主要な懸念事項",
            "severity": "high|medium|low",
            "likelihood": "high|medium|low",
            "recommendation": "推奨対応"
        }}
    ],
    "protective_measures": [
        {{
            "measure": "保護措置",
            "effectiveness": "high|medium|low",
            "implementation": "実装方法"
        }}
    ],
    "decision_recommendation": {{
        "proceed": True,
        "conditions": ["条件1", "条件2"],
        "alternatives": ["代替選択肢"]
    }}
}}
```
"""

    @classmethod
    def get_product_analysis_prompt(cls, product_info: Dict[str, Any]) -> str:
        """
        商品分析用プロンプトを取得
        
        Args:
            product_info: 商品情報
            
        Returns:
            str: 分析プロンプト
        """
        return cls.BASE_PRODUCT_ANALYSIS_PROMPT.format(
            product_info=json.dumps(product_info, ensure_ascii=False, indent=2)
        )
    
    @classmethod
    def get_comparative_analysis_prompt(cls, products: List[Dict[str, Any]]) -> str:
        """
        比較分析用プロンプトを取得
        
        Args:
            products: 比較対象商品リスト
            
        Returns:
            str: 比較分析プロンプト
        """
        return cls.COMPARATIVE_ANALYSIS_PROMPT.format(
            products=json.dumps(products, ensure_ascii=False, indent=2)
        )
    
    @classmethod
    def get_price_analysis_prompt(cls, product: str, price: int, category: str, condition: str) -> str:
        """
        価格分析用プロンプトを取得
        
        Args:
            product: 商品名
            price: 価格
            category: カテゴリー
            condition: 状態
            
        Returns:
            str: 価格分析プロンプト
        """
        return cls.PRICE_ANALYSIS_PROMPT.format(
            product=product,
            price=price,
            category=category,
            condition=condition
        )
    
    @classmethod
    def get_recommendation_reasoning_prompt(cls, product: Dict[str, Any], user_profile: Dict[str, Any], score: float) -> str:
        """
        推薦理由生成用プロンプトを取得
        
        Args:
            product: 推薦商品
            user_profile: ユーザープロファイル
            score: 推薦スコア
            
        Returns:
            str: 推薦理由生成プロンプト
        """
        return cls.RECOMMENDATION_REASONING_PROMPT.format(
            product=json.dumps(product, ensure_ascii=False, indent=2),
            user_profile=json.dumps(user_profile, ensure_ascii=False, indent=2),
            score=score
        )
    
    @classmethod
    def get_market_analysis_prompt(cls, target: str, period: str = "過去3ヶ月", data_source: str = "メルカリ") -> str:
        """
        市場分析用プロンプトを取得
        
        Args:
            target: 分析対象
            period: 分析期間
            data_source: データソース
            
        Returns:
            str: 市場分析プロンプト
        """
        return cls.MARKET_ANALYSIS_PROMPT.format(
            target=target,
            period=period,
            data_source=data_source
        )
    
    @classmethod
    def get_risk_assessment_prompt(cls, product: Dict[str, Any], seller: Dict[str, Any], conditions: Dict[str, Any]) -> str:
        """
        リスク評価用プロンプトを取得
        
        Args:
            product: 商品情報
            seller: 出品者情報
            conditions: 取引条件
            
        Returns:
            str: リスク評価プロンプト
        """
        return cls.RISK_ASSESSMENT_PROMPT.format(
            product=json.dumps(product, ensure_ascii=False, indent=2),
            seller=json.dumps(seller, ensure_ascii=False, indent=2),
            conditions=json.dumps(conditions, ensure_ascii=False, indent=2)
        )
    
    @classmethod
    def get_trend_analysis_prompt(cls, category: str, timeframe: str = "過去6ヶ月") -> str:
        """
        トレンド分析用プロンプトを取得
        
        Args:
            category: カテゴリー
            timeframe: 時間枠
            
        Returns:
            str: トレンド分析プロンプト
        """
        return f"""
カテゴリー「{category}」のトレンド分析を実施してください。

分析期間: {timeframe}

## 分析観点
1. 人気商品の変化
2. 価格帯の変動
3. 新興ブランドの台頭
4. 季節性の影響
5. 消費者行動の変化

## 出力形式
```json
{{
    "trend_summary": "トレンドの要約",
    "popular_items": [
        {{
            "item": "人気商品",
            "growth_rate": "成長率",
            "reason": "人気の理由"
        }}
    ],
    "price_trends": {{
        "average_change": "平均価格変化",
        "price_segments": {{
            "budget": "予算帯の動向",
            "mid_range": "中価格帯の動向",
            "premium": "プレミアム帯の動向"
        }}
    }},
    "emerging_trends": [
        {{
            "trend": "新興トレンド",
            "adoption_rate": "普及率",
            "potential": "将来性"
        }}
    ],
    "seasonal_patterns": {{
        "peak_seasons": ["ピーク季節"],
        "off_seasons": ["オフシーズン"],
        "seasonal_products": ["季節商品"]
    }},
    "forecast": {{
        "next_quarter": "次四半期予測",
        "confidence": 0.8,
        "key_factors": ["予測要因"]
    }}
}}
```
"""

    @classmethod
    def get_sentiment_analysis_prompt(cls, reviews: List[str], product: str) -> str:
        """
        感情分析用プロンプトを取得
        
        Args:
            reviews: レビューリスト
            product: 商品名
            
        Returns:
            str: 感情分析プロンプト
        """
        reviews_text = "\n".join([f"- {review}" for review in reviews])
        
        return f"""
商品「{product}」のレビューを感情分析してください。

レビュー:
{reviews_text}

## 分析項目
1. 全体的な感情傾向
2. 具体的な評価ポイント
3. 改善点・問題点
4. 推薦度合い

## 出力形式
```json
{{
    "overall_sentiment": "positive|neutral|negative",
    "sentiment_score": 0.7,
    "sentiment_distribution": {{
        "positive": 0.6,
        "neutral": 0.3,
        "negative": 0.1
    }},
    "key_topics": [
        {{
            "topic": "価格",
            "sentiment": "positive|neutral|negative",
            "mentions": 5,
            "key_phrases": ["関連フレーズ"]
        }}
    ],
    "strengths": [
        {{
            "strength": "商品の強み",
            "evidence": "根拠となるレビュー",
            "frequency": "言及頻度"
        }}
    ],
    "concerns": [
        {{
            "concern": "懸念事項",
            "evidence": "根拠となるレビュー",
            "severity": "high|medium|low"
        }}
    ],
    "recommendation_confidence": {{
        "would_recommend": 0.8,
        "reasoning": "推薦度合いの理由"
    }}
}}
```
"""