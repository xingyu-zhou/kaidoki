"""
查询实体
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class QueryIntent(Enum):
    """查询意图"""
    SEARCH = "search"
    COMPARE = "compare"
    RECOMMEND = "recommend"
    ANALYZE = "analyze"


class QueryComplexity(Enum):
    """查询复杂度"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class QueryEntity:
    """查询实体"""
    original_query: str
    normalized_query: str = ""
    keywords: List[str] = None
    intent: QueryIntent = QueryIntent.SEARCH
    category: Optional[str] = None
    brand: Optional[str] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    condition: Optional[str] = None
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    language: str = "ja"
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if not self.normalized_query:
            self.normalized_query = self.original_query.lower()