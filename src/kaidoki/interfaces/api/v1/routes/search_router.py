"""
搜索路由
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import time

from .....shared.utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = 10


class SearchResponse(BaseModel):
    query: str
    results: List[dict]
    total_found: int
    processing_time: float


@router.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """搜索商品"""
    start_time = time.time()
    
    try:
        logger.info(f"搜索请求: {request.query}")
        
        # 这里是最简实现 - 返回模拟数据
        results = [
            {
                "id": f"item_{i}",
                "title": f"商品 {i} - {request.query}",
                "price": 1000 + i * 100,
                "url": f"https://jp.mercari.com/item/{i}",
                "image_url": "",
                "seller": f"seller_{i}"
            }
            for i in range(min(request.limit, 5))  # 最简实现只返回5个结果
        ]
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            query=request.query,
            results=results,
            total_found=len(results),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
