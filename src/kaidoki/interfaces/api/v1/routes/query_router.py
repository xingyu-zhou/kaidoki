"""
查询路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import time

from .....shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    language: str = "ja"


class QueryResponse(BaseModel):
    original_query: str
    normalized_query: str
    keywords: List[str]
    intent: str
    category: Optional[str]
    price_min: Optional[int]
    price_max: Optional[int]
    confidence: float
    processing_time: float


@router.post("/query/parse", response_model=QueryResponse)
async def parse_query(request: QueryRequest):
    """解析查询"""
    start_time = time.time()
    
    try:
        logger.info(f"解析查询: {request.query}")
        
        # 这里是最简实现 - 基本的关键词提取
        keywords = [word.strip() for word in request.query.split() if word.strip()]
        
        # 简单的价格提取
        price_min = None
        price_max = None
        for word in keywords:
            if "円" in word or "¥" in word:
                try:
                    price_num = int(''.join(filter(str.isdigit, word)))
                    if "以下" in word or "未満" in word:
                        price_max = price_num
                    elif "以上" in word:
                        price_min = price_num
                except:
                    pass
        
        processing_time = time.time() - start_time
        
        return QueryResponse(
            original_query=request.query,
            normalized_query=request.query.lower(),
            keywords=keywords,
            intent="search",
            category=None,
            price_min=price_min,
            price_max=price_max,
            confidence=0.8,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"查询解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询解析失败: {str(e)}")
