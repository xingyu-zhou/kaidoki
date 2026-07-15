#!/usr/bin/env python3
"""
测试搜索功能
"""

import sys
import asyncio
from urllib.parse import urlencode, parse_qs, urlparse

# 添加模块路径
sys.path.insert(0, '.')

from src.mercari_agent.utils.logger import get_logger
from src.mercari_agent.scrapers.mercari_scraper import (
    MercariScraper, SearchFilters, SearchSortOrder, PriceRange
)
from src.mercari_agent.scrapers.base_scraper import ScrapingStrategy

logger = get_logger(__name__)


def test_search_filters():
    """测试搜索过滤器"""
    logger.info("🔍 测试搜索过滤器...")
    
    # 基本搜索
    basic_filter = SearchFilters(
        keywords="iPhone 13",
        page=1,
        limit=20
    )
    
    params = basic_filter.to_params()
    logger.info(f"基本搜索参数: {params}")
    
    # 高级搜索
    advanced_filter = SearchFilters(
        keywords="iPhone 13",
        category_id=1084,  # 电子产品分类
        price_min=50000,
        price_max=100000,
        condition="新品・未使用",
        sort_order=SearchSortOrder.PRICE_LOW,
        page=1,
        limit=40
    )
    
    params = advanced_filter.to_params()
    logger.info(f"高级搜索参数: {params}")
    
    # 品牌搜索
    brand_filter = SearchFilters(
        keywords="MacBook",
        brand_id=33,  # Apple品牌ID
        price_min=100000,
        sort_order=SearchSortOrder.NEWEST,
        page=1
    )
    
    params = brand_filter.to_params()
    logger.info(f"品牌搜索参数: {params}")
    
    return True


def test_search_url_building():
    """测试搜索URL构建"""
    logger.info("🔗 测试搜索URL构建...")
    
    # 创建爬虫实例
    scraper = MercariScraper(ScrapingStrategy.REQUESTS)
    
    # 测试不同的搜索条件
    test_cases = [
        # 基本搜索
        SearchFilters(
            keywords="Nintendo Switch",
            page=1
        ),
        
        # 价格范围搜索
        SearchFilters(
            keywords="カメラ",
            price_min=10000,
            price_max=50000,
            sort_order=SearchSortOrder.PRICE_LOW
        ),
        
        # 分类搜索
        SearchFilters(
            keywords="洋服",
            category_id=1,
            condition="目立った傷や汚れなし",
            sort_order=SearchSortOrder.NEWEST
        ),
        
        # 复合搜索
        SearchFilters(
            keywords="iPhone",
            category_id=1084,
            price_min=30000,
            price_max=80000,
            condition="未使用に近い",
            sort_order=SearchSortOrder.POPULARITY,
            page=2,
            limit=60
        )
    ]
    
    for i, filters in enumerate(test_cases, 1):
        try:
            url = scraper._build_search_url(filters)
            logger.info(f"测试用例 {i}: {url}")
            
            # 解析URL参数
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            logger.info(f"  解析的参数: {params}")
            
            # 验证必要参数
            assert 'keyword' in params, "缺少keyword参数"
            assert 'page' in params, "缺少page参数"
            
            logger.info(f"  ✅ 测试用例 {i} 通过")
            
        except Exception as e:
            logger.error(f"  ❌ 测试用例 {i} 失败: {e}")
            return False
    
    return True


def test_search_sort_orders():
    """测试搜索排序选项"""
    logger.info("📊 测试搜索排序选项...")
    
    scraper = MercariScraper(ScrapingStrategy.REQUESTS)
    
    # 测试所有排序选项
    sort_orders = [
        SearchSortOrder.RELEVANCE,
        SearchSortOrder.PRICE_LOW,
        SearchSortOrder.PRICE_HIGH,
        SearchSortOrder.NEWEST,
        SearchSortOrder.OLDEST,
        SearchSortOrder.POPULARITY
    ]
    
    for sort_order in sort_orders:
        try:
            filters = SearchFilters(
                keywords="テスト",
                sort_order=sort_order
            )
            
            url = scraper._build_search_url(filters)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            sort_param = params.get('sort', [''])[0]
            expected_sort = sort_order.value if hasattr(sort_order, 'value') else str(sort_order)
            
            logger.info(f"  排序: {sort_order} -> {sort_param}")
            assert sort_param == expected_sort, f"排序参数不匹配: {sort_param} != {expected_sort}"
            
        except Exception as e:
            logger.error(f"  ❌ 排序测试失败 ({sort_order}): {e}")
            return False
    
    logger.info("  ✅ 所有排序选项测试通过")
    return True


def test_price_ranges():
    """测试价格范围"""
    logger.info("💰 测试价格范围...")
    
    scraper = MercariScraper(ScrapingStrategy.REQUESTS)
    
    # 测试价格范围
    price_tests = [
        (0, 1000),
        (1000, 5000),
        (5000, 10000),
        (10000, 50000),
        (50000, None)  # 无上限
    ]
    
    for price_min, price_max in price_tests:
        try:
            filters = SearchFilters(
                keywords="商品",
                price_min=price_min,
                price_max=price_max
            )
            
            url = scraper._build_search_url(filters)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # 验证价格参数
            if price_min is not None:
                assert 'price_min' in params, f"缺少price_min参数"
                assert int(params['price_min'][0]) == price_min, f"price_min参数不匹配"
            
            if price_max is not None:
                assert 'price_max' in params, f"缺少price_max参数"
                assert int(params['price_max'][0]) == price_max, f"price_max参数不匹配"
            
            logger.info(f"  价格范围: {price_min} - {price_max} ✅")
            
        except Exception as e:
            logger.error(f"  ❌ 价格范围测试失败 ({price_min}-{price_max}): {e}")
            return False
    
    logger.info("  ✅ 价格范围测试通过")
    return True


def test_pagination():
    """测试分页功能"""
    logger.info("📄 测试分页功能...")
    
    scraper = MercariScraper(ScrapingStrategy.REQUESTS)
    
    # 测试不同页码和限制
    pagination_tests = [
        (1, 20),
        (2, 40),
        (3, 60),
        (5, 100)
    ]
    
    for page, limit in pagination_tests:
        try:
            filters = SearchFilters(
                keywords="テスト商品",
                page=page,
                limit=limit
            )
            
            url = scraper._build_search_url(filters)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # 验证分页参数
            assert 'page' in params, f"缺少page参数"
            assert int(params['page'][0]) == page, f"page参数不匹配: {params['page'][0]} != {page}"
            
            assert 'limit' in params, f"缺少limit参数"
            assert int(params['limit'][0]) == limit, f"limit参数不匹配: {params['limit'][0]} != {limit}"
            
            logger.info(f"  分页: 第{page}页，每页{limit}条 ✅")
            
        except Exception as e:
            logger.error(f"  ❌ 分页测试失败 (page={page}, limit={limit}): {e}")
            return False
    
    logger.info("  ✅ 分页功能测试通过")
    return True


def test_japanese_keywords():
    """测试日语关键词"""
    logger.info("🇯🇵 测试日语关键词...")
    
    scraper = MercariScraper(ScrapingStrategy.REQUESTS)
    
    # 测试各种日语关键词
    japanese_keywords = [
        "iPhone アイフォン",
        "カメラ デジタル",
        "洋服 レディース",
        "本 漫画",
        "ゲーム Nintendo",
        "時計 腕時計",
        "バッグ ハンドバッグ",
        "靴 スニーカー"
    ]
    
    for keyword in japanese_keywords:
        try:
            filters = SearchFilters(
                keywords=keyword,
                page=1
            )
            
            url = scraper._build_search_url(filters)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # 验证关键词参数
            assert 'keyword' in params, f"缺少keyword参数"
            decoded_keyword = params['keyword'][0]
            
            logger.info(f"  关键词: '{keyword}' -> '{decoded_keyword}' ✅")
            
        except Exception as e:
            logger.error(f"  ❌ 日语关键词测试失败 ('{keyword}'): {e}")
            return False
    
    logger.info("  ✅ 日语关键词测试通过")
    return True


async def main():
    """主测试函数"""
    logger.info("🚀 开始搜索功能测试...")
    
    success = True
    
    # 测试1: 搜索过滤器
    logger.info("\n" + "="*50)
    logger.info("测试1: 搜索过滤器")
    logger.info("="*50)
    
    if not test_search_filters():
        logger.error("❌ 搜索过滤器测试失败")
        success = False
    else:
        logger.info("✅ 搜索过滤器测试通过")
    
    # 测试2: 搜索URL构建
    logger.info("\n" + "="*50)
    logger.info("测试2: 搜索URL构建")
    logger.info("="*50)
    
    if not test_search_url_building():
        logger.error("❌ 搜索URL构建测试失败")
        success = False
    else:
        logger.info("✅ 搜索URL构建测试通过")
    
    # 测试3: 搜索排序选项
    logger.info("\n" + "="*50)
    logger.info("测试3: 搜索排序选项")
    logger.info("="*50)
    
    if not test_search_sort_orders():
        logger.error("❌ 搜索排序选项测试失败")
        success = False
    else:
        logger.info("✅ 搜索排序选项测试通过")
    
    # 测试4: 价格范围
    logger.info("\n" + "="*50)
    logger.info("测试4: 价格范围")
    logger.info("="*50)
    
    if not test_price_ranges():
        logger.error("❌ 价格范围测试失败")
        success = False
    else:
        logger.info("✅ 价格范围测试通过")
    
    # 测试5: 分页功能
    logger.info("\n" + "="*50)
    logger.info("测试5: 分页功能")
    logger.info("="*50)
    
    if not test_pagination():
        logger.error("❌ 分页功能测试失败")
        success = False
    else:
        logger.info("✅ 分页功能测试通过")
    
    # 测试6: 日语关键词
    logger.info("\n" + "="*50)
    logger.info("测试6: 日语关键词")
    logger.info("="*50)
    
    if not test_japanese_keywords():
        logger.error("❌ 日语关键词测试失败")
        success = False
    else:
        logger.info("✅ 日语关键词测试通过")
    
    # 总结
    logger.info("\n" + "="*50)
    logger.info("测试总结")
    logger.info("="*50)
    
    if success:
        logger.info("🎉 所有搜索功能测试通过！")
        print("✅ 搜索功能测试成功")
    else:
        logger.error("❌ 部分搜索功能测试失败")
        print("❌ 搜索功能测试失败")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())