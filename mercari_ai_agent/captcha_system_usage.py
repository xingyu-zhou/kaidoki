"""
CAPTCHA 人机交互系统使用示例

该文件展示了如何在 Mercari 爬虫系统中集成和使用 CAPTCHA 处理系统。
包含了完整的使用示例、最佳实践和常见问题解决方案。
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入 CAPTCHA 系统
from src.mercari_agent.captcha import create_captcha_system, CaptchaInteractionSystem

# 导入现有的 Mercari 组件
from src.mercari_agent.scrapers.mercari_scraper import MercariScraper
from src.mercari_agent.scrapers.anti_bot_handler import AntiBotHandler
from src.mercari_agent.scrapers.session_manager import SessionManager


class CaptchaSystemDemo:
    """CAPTCHA 系统演示类"""
    
    def __init__(self, config_path: str = "config/captcha_system.yaml"):
        self.config_path = config_path
        self.captcha_system: Optional[CaptchaInteractionSystem] = None
        self.scraper: Optional[MercariScraper] = None
        
    async def setup_system(self) -> bool:
        """设置系统"""
        try:
            # 1. 创建 CAPTCHA 系统
            self.captcha_system = await create_captcha_system(config_path=self.config_path)
            
            # 2. 启动系统
            await self.captcha_system.start()
            
            # 3. 创建爬虫实例
            self.scraper = MercariScraper()
            
            # 4. 集成 CAPTCHA 系统到爬虫
            await self._integrate_with_scraper()
            
            logger.info("CAPTCHA 系统设置完成")
            return True
            
        except Exception as e:
            logger.error(f"系统设置失败: {e}")
            return False
    
    async def _integrate_with_scraper(self):
        """集成 CAPTCHA 系统到爬虫"""
        # 增强反机器人处理器
        await self.captcha_system.enhance_anti_bot_handler(self.scraper.anti_bot_handler)
        
        # 增强会话管理器
        await self.captcha_system.enhance_session_manager(self.scraper.session_manager)
        
        logger.info("CAPTCHA 系统已集成到爬虫")
    
    async def basic_usage_example(self):
        """基本使用示例"""
        logger.info("=== 基本使用示例 ===")
        
        try:
            # 模拟爬虫请求
            test_urls = [
                "https://jp.mercari.com/search?keyword=apple",
                "https://jp.mercari.com/item/m12345678901",
                "https://jp.mercari.com/search?keyword=laptop"
            ]
            
            for url in test_urls:
                logger.info(f"处理 URL: {url}")
                
                # 模拟获取页面内容
                html_content = await self._simulate_page_content(url)
                
                # 处理请求（包含 CAPTCHA 检测）
                result = await self.captcha_system.process_request(url, html_content)
                
                if result:
                    logger.info(f"请求成功处理: {url}")
                else:
                    logger.warning(f"请求处理失败: {url}")
                
                # 短暂延迟
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"基本使用示例失败: {e}")
    
    async def _simulate_page_content(self, url: str) -> str:
        """模拟页面内容"""
        # 模拟不同类型的页面内容
        if "search" in url:
            return """
            <html>
                <head><title>Mercari Search</title></head>
                <body>
                    <div class="search-results">
                        <div class="item">商品1</div>
                        <div class="item">商品2</div>
                    </div>
                </body>
            </html>
            """
        elif "item" in url:
            # 模拟包含验证码的页面
            return """
            <html>
                <head><title>Mercari Item</title></head>
                <body>
                    <div class="item-details">
                        <h1>商品详情</h1>
                        <div class="captcha-container">
                            <img src="/captcha/image.jpg" alt="验证码" />
                            <input type="text" name="captcha" placeholder="请输入验证码" />
                            <button type="submit">提交</button>
                        </div>
                    </div>
                </body>
            </html>
            """
        else:
            return """
            <html>
                <head><title>Mercari</title></head>
                <body>
                    <div>普通页面内容</div>
                </body>
            </html>
            """
    
    async def advanced_usage_example(self):
        """高级使用示例"""
        logger.info("=== 高级使用示例 ===")
        
        try:
            # 1. 自定义配置
            custom_config = {
                "detector": {
                    "confidence_threshold": 0.8,
                    "detection_methods": {
                        "rule_based": True,
                        "image_based": True
                    }
                },
                "ui": {
                    "framework": "tkinter",
                    "timeout": 120
                },
                "analytics": {
                    "enabled": True,
                    "reporting": {"enabled": True}
                }
            }
            
            # 2. 使用自定义配置创建系统
            custom_system = await create_captcha_system(config=custom_config)
            await custom_system.start()
            
            # 3. 批量处理示例
            batch_urls = [
                f"https://jp.mercari.com/item/m{i:011d}" for i in range(1, 11)
            ]
            
            # 4. 并发处理
            tasks = []
            for url in batch_urls:
                html_content = await self._simulate_page_content(url)
                task = custom_system.process_request(url, html_content)
                tasks.append(task)
            
            # 5. 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 6. 处理结果
            success_count = sum(1 for r in results if r is True)
            logger.info(f"批量处理完成: {success_count}/{len(results)} 成功")
            
            # 7. 获取系统统计
            stats = await custom_system.get_system_status()
            logger.info(f"系统统计: {stats['system_stats']}")
            
            # 8. 关闭自定义系统
            await custom_system.stop()
            
        except Exception as e:
            logger.error(f"高级使用示例失败: {e}")
    
    async def error_handling_example(self):
        """错误处理示例"""
        logger.info("=== 错误处理示例 ===")
        
        try:
            # 1. 处理超时情况
            logger.info("测试超时处理...")
            
            # 模拟长时间运行的请求
            html_with_captcha = """
            <html>
                <body>
                    <div class="verification-required">
                        <img src="/complex_captcha.jpg" alt="复杂验证码" />
                        <input type="text" name="captcha" />
                    </div>
                </body>
            </html>
            """
            
            try:
                # 设置较短的超时时间
                result = await asyncio.wait_for(
                    self.captcha_system.process_request(
                        "https://jp.mercari.com/timeout_test", 
                        html_with_captcha
                    ),
                    timeout=5.0
                )
                logger.info(f"超时测试结果: {result}")
            except asyncio.TimeoutError:
                logger.warning("请求超时，触发恢复机制")
            
            # 2. 处理系统错误
            logger.info("测试系统错误处理...")
            
            # 检查系统健康状态
            health_status = await self.captcha_system.check_system_health()
            logger.info(f"系统健康状态: {health_status}")
            
            # 3. 处理验证码识别失败
            logger.info("测试验证码识别失败处理...")
            
            # 模拟无法识别的验证码
            invalid_captcha_html = """
            <html>
                <body>
                    <div class="invalid-captcha">
                        <img src="/broken_captcha.jpg" alt="损坏的验证码" />
                        <input type="text" name="captcha" />
                    </div>
                </body>
            </html>
            """
            
            result = await self.captcha_system.process_request(
                "https://jp.mercari.com/invalid_captcha",
                invalid_captcha_html
            )
            logger.info(f"无效验证码处理结果: {result}")
            
        except Exception as e:
            logger.error(f"错误处理示例失败: {e}")
    
    async def monitoring_example(self):
        """监控示例"""
        logger.info("=== 监控示例 ===")
        
        try:
            # 1. 获取实时状态
            status = await self.captcha_system.get_system_status()
            logger.info("=== 系统状态 ===")
            logger.info(f"系统运行: {status['system_running']}")
            logger.info(f"总请求数: {status['system_stats']['total_requests']}")
            logger.info(f"CAPTCHA 检测数: {status['system_stats']['captcha_detected']}")
            logger.info(f"成功解决数: {status['system_stats']['captcha_solved']}")
            
            # 2. 获取分析报告
            if hasattr(self.captcha_system, 'analytics'):
                report = await self.captcha_system.analytics.get_analytics_report()
                logger.info("=== 分析报告 ===")
                logger.info(f"基本统计: {report['basic_stats']}")
                logger.info(f"类型分布: {report['type_breakdown']}")
                logger.info(f"成功率: {report['success_rate']}")
            
            # 3. 生成详细报告
            report_path = "monitoring_report.json"
            success = await self.captcha_system.generate_report(report_path)
            if success:
                logger.info(f"详细报告已生成: {report_path}")
            
            # 4. 监控系统健康
            health = await self.captcha_system.check_system_health()
            logger.info("=== 健康检查 ===")
            logger.info(f"系统健康: {health['healthy']}")
            for component, status in health['components'].items():
                logger.info(f"  {component}: {status}")
            
        except Exception as e:
            logger.error(f"监控示例失败: {e}")
    
    async def integration_example(self):
        """集成示例"""
        logger.info("=== 集成示例 ===")
        
        try:
            # 1. 与现有爬虫集成
            logger.info("集成现有爬虫...")
            
            # 模拟现有爬虫的使用方式
            scraper = MercariScraper()
            
            # 搜索商品
            search_results = await scraper.search_products("MacBook Pro")
            logger.info(f"搜索结果: {len(search_results)} 个商品")
            
            # 2. 处理商品详情（可能遇到验证码）
            if search_results:
                first_item = search_results[0]
                logger.info(f"获取商品详情: {first_item['title']}")
                
                # 这里会自动触发 CAPTCHA 检测和处理
                item_details = await scraper.get_product_details(first_item['url'])
                logger.info(f"商品详情获取{'成功' if item_details else '失败'}")
            
            # 3. 验证集成效果
            logger.info("验证集成效果...")
            
            # 检查增强后的功能
            enhanced_handler = scraper.anti_bot_handler
            if hasattr(enhanced_handler, 'captcha_system'):
                logger.info("反机器人处理器已成功增强")
            
            enhanced_session = scraper.session_manager
            if hasattr(enhanced_session, 'captcha_system'):
                logger.info("会话管理器已成功增强")
            
        except Exception as e:
            logger.error(f"集成示例失败: {e}")
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.captcha_system:
                await self.captcha_system.stop()
                logger.info("CAPTCHA 系统已停止")
            
            if self.scraper:
                # 清理爬虫资源
                await self.scraper.close()
                logger.info("爬虫已关闭")
                
        except Exception as e:
            logger.error(f"清理失败: {e}")


async def main():
    """主函数"""
    logger.info("开始 CAPTCHA 系统使用演示")
    
    # 创建演示实例
    demo = CaptchaSystemDemo()
    
    try:
        # 设置系统
        if not await demo.setup_system():
            logger.error("系统设置失败")
            return
        
        # 运行各种示例
        await demo.basic_usage_example()
        await demo.advanced_usage_example()
        await demo.error_handling_example()
        await demo.monitoring_example()
        await demo.integration_example()
        
        logger.info("所有演示示例完成")
        
    except Exception as e:
        logger.error(f"演示失败: {e}")
    
    finally:
        # 清理资源
        await demo.cleanup()


class BestPracticesGuide:
    """最佳实践指南"""
    
    @staticmethod
    def configuration_tips():
        """配置建议"""
        return """
        配置建议：
        
        1. 检测器配置：
           - 调整 confidence_threshold 以平衡检测准确性和误报率
           - 根据目标网站特征启用适当的检测方法
           
        2. UI 配置：
           - 选择合适的 UI 框架（tkinter 适合简单使用，Qt 适合复杂界面）
           - 设置合理的超时时间避免用户等待过长
           
        3. 性能配置：
           - 根据系统资源调整并发数量
           - 启用缓存以提高响应速度
           
        4. 安全配置：
           - 启用输入验证防止恶意输入
           - 根据需要配置访问控制
        """
    
    @staticmethod
    def troubleshooting_guide():
        """故障排除指南"""
        return """
        常见问题解决：
        
        1. 验证码检测不准确：
           - 检查检测阈值设置
           - 验证目标网站的 HTML 结构
           - 启用调试模式查看检测详情
           
        2. UI 显示问题：
           - 确认 UI 框架已正确安装
           - 检查显示设置和字体配置
           - 验证图像加载路径
           
        3. 性能问题：
           - 调整并发数量
           - 启用缓存机制
           - 优化检测算法配置
           
        4. 集成问题：
           - 确认现有组件兼容性
           - 检查方法替换是否成功
           - 验证钩子配置
        """
    
    @staticmethod
    def optimization_tips():
        """优化建议"""
        return """
        性能优化建议：
        
        1. 检测优化：
           - 优先使用轻量级检测方法
           - 避免不必要的图像处理
           - 缓存检测结果
           
        2. UI 优化：
           - 使用异步 UI 更新
           - 预加载常用资源
           - 优化图像显示
           
        3. 队列优化：
           - 设置合理的队列大小
           - 使用优先级调度
           - 启用持久化存储
           
        4. 内存优化：
           - 定期清理缓存
           - 限制并发任务数
           - 使用内存池
        """


if __name__ == "__main__":
    # 打印使用指南
    print("=== CAPTCHA 系统使用指南 ===")
    print(BestPracticesGuide.configuration_tips())
    print(BestPracticesGuide.troubleshooting_guide())
    print(BestPracticesGuide.optimization_tips())
    
    # 运行演示
    asyncio.run(main())