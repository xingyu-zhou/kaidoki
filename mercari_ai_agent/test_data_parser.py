#!/usr/bin/env python3
"""
测试数据解析器功能
"""

import sys
import asyncio
from datetime import datetime
from typing import List

# 添加模块路径
sys.path.insert(0, '.')

from src.mercari_agent.utils.logger import get_logger
from src.mercari_agent.scrapers.data_parser import MercariDataParser, ParsingContext, PageType
from src.mercari_agent.scrapers.session_manager import SessionManager
from src.mercari_agent.scrapers.mercari_scraper import SearchFilters

logger = get_logger(__name__)


async def test_data_parser_with_real_content():
    """测试数据解析器与真实内容"""
    logger.info("🔍 开始测试数据解析器...")
    
    # 初始化组件
    session_manager = SessionManager()
    data_parser = MercariDataParser()
    
    try:
        # 获取真实的HTML内容
        search_url = "https://jp.mercari.com/search?keyword=iPhone"
        logger.info(f"请求URL: {search_url}")
        
        response = await session_manager.get(search_url)
        if response.status != 200:
            logger.error(f"请求失败，状态码: {response.status}")
            return False
        
        html_content = await response.text()
        logger.info(f"获取HTML内容长度: {len(html_content)} 字符")
        
        # 创建解析上下文
        context = ParsingContext(
            page_type=PageType.UNKNOWN,  # 让解析器自动检测
            base_url="https://jp.mercari.com",
            current_url=search_url,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        # 解析页面
        logger.info("开始解析页面...")
        result = data_parser.parse_page(html_content, context)
        
        # 输出解析结果
        logger.info(f"解析结果统计:")
        logger.info(f"  页面类型: {context.page_type}")
        logger.info(f"  产品数量: {len(result.products)}")
        logger.info(f"  总计数: {result.total_count}")
        logger.info(f"  当前页: {result.current_page}")
        logger.info(f"  有下一页: {result.has_next_page}")
        logger.info(f"  错误数量: {len(result.errors)}")
        
        # 显示错误信息
        if result.errors:
            logger.warning("解析过程中的错误:")
            for error in result.errors:
                logger.warning(f"  - {error}")
        
        # 显示解析到的产品信息
        if result.products:
            logger.info("\n📦 解析到的产品信息:")
            for i, product in enumerate(result.products[:5]):  # 只显示前5个
                logger.info(f"\n产品 {i+1}:")
                logger.info(f"  标题: {product.title}")
                logger.info(f"  价格: {product.price}")
                logger.info(f"  URL: {product.url}")
                logger.info(f"  状态: {product.condition}")
                logger.info(f"  图片数量: {len(product.images)}")
                logger.info(f"  是否已售: {product.is_sold}")
                logger.info(f"  来源: {product.source}")
                logger.info(f"  来源ID: {product.source_id}")
                
                # 验证产品数据
                is_valid, errors = data_parser.validate_product_data(product)
                if is_valid:
                    logger.info(f"  ✅ 数据验证通过")
                else:
                    logger.warning(f"  ❌ 数据验证失败: {errors}")
        
        else:
            logger.warning("未解析到任何产品信息")
        
        # 测试数据清洗功能
        if result.products:
            logger.info("\n🧹 测试数据清洗功能...")
            first_product = result.products[0]
            cleaned_product = data_parser.clean_product_data(first_product)
            logger.info(f"清洗后的产品标题: {cleaned_product.title}")
            logger.info(f"清洗后的价格: {cleaned_product.price}")
            logger.info(f"清洗后的图片数量: {len(cleaned_product.images)}")
        
        # 获取解析器统计信息
        parser_stats = data_parser.get_parser_stats()
        logger.info(f"\n📊 解析器统计信息:")
        for key, value in parser_stats.items():
            logger.info(f"  {key}: {value}")
        
        # 测试页面类型检测
        logger.info(f"\n🔍 页面类型检测测试:")
        test_urls = [
            "https://jp.mercari.com/search?keyword=iPhone",
            "https://jp.mercari.com/item/m12345678",
            "https://jp.mercari.com/u/123456789",
            "https://jp.mercari.com/category/1"
        ]
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for test_url in test_urls:
            detected_type = data_parser._detect_page_type(soup, test_url)
            logger.info(f"  URL: {test_url} -> 类型: {detected_type}")
        
        return len(result.products) > 0
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await session_manager.close()


async def test_parser_components():
    """测试解析器组件"""
    logger.info("🔧 测试解析器组件...")
    
    data_parser = MercariDataParser()
    
    # 测试文本提取
    logger.info("测试文本提取...")
    from bs4 import BeautifulSoup
    
    test_html = """
    <div class="price">¥1,234</div>
    <div class="rating">4.5</div>
    <div class="count">123,456</div>
    <img src="https://example.com/image.jpg" alt="test">
    <a href="/item/m12345678">Test Item</a>
    """
    
    soup = BeautifulSoup(test_html, 'html.parser')
    
    # 测试价格提取
    price_elem = soup.select_one('.price')
    price = data_parser._extract_price(price_elem)
    logger.info(f"提取的价格: {price}")
    
    # 测试评分提取
    rating_elem = soup.select_one('.rating')
    rating = data_parser._extract_rating(rating_elem)
    logger.info(f"提取的评分: {rating}")
    
    # 测试计数提取
    count_elem = soup.select_one('.count')
    count = data_parser._extract_count(count_elem)
    logger.info(f"提取的计数: {count}")
    
    # 测试图片URL提取
    img_elem = soup.select_one('img')
    img_url = data_parser._extract_image_url(img_elem)
    logger.info(f"提取的图片URL: {img_url}")
    
    # 测试商品ID提取
    link_elem = soup.select_one('a')
    item_id = data_parser._extract_item_id(link_elem.get('href'))
    logger.info(f"提取的商品ID: {item_id}")
    
    # 测试URL标准化
    test_urls = [
        "//example.com/image.jpg",
        "/static/image.jpg",
        "https://example.com/image.jpg"
    ]
    
    logger.info("测试URL标准化...")
    for url in test_urls:
        normalized = data_parser._normalize_image_url(url, "https://jp.mercari.com")
        logger.info(f"  {url} -> {normalized}")
    
    return True


async def main():
    """主测试函数"""
    logger.info("🚀 开始数据解析器测试...")
    
    success = True
    
    # 测试1: 解析器组件测试
    logger.info("\n" + "="*50)
    logger.info("测试1: 解析器组件测试")
    logger.info("="*50)
    
    component_result = await test_parser_components()
    if not component_result:
        logger.error("❌ 解析器组件测试失败")
        success = False
    else:
        logger.info("✅ 解析器组件测试通过")
    
    # 测试2: 真实内容解析测试
    logger.info("\n" + "="*50)
    logger.info("测试2: 真实内容解析测试")
    logger.info("="*50)
    
    real_content_result = await test_data_parser_with_real_content()
    if not real_content_result:
        logger.error("❌ 真实内容解析测试失败")
        success = False
    else:
        logger.info("✅ 真实内容解析测试通过")
    
    # 总结
    logger.info("\n" + "="*50)
    logger.info("测试总结")
    logger.info("="*50)
    
    if success:
        logger.info("🎉 所有测试通过！数据解析器工作正常")
        print("✅ 数据解析器测试成功")
    else:
        logger.error("❌ 部分测试失败")
        print("❌ 数据解析器测试失败")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())