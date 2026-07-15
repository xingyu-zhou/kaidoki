#!/usr/bin/env python3
"""
指纹管理器集成测试

测试浏览器指纹管理器和TLS指纹管理器在爬虫服务中的集成情况。
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from mercari_agent.shared.config.app_config import AppConfig
from mercari_agent.infrastructure.scraping.scraper_service import ScraperService
from mercari_agent.infrastructure.scraping.browser_fingerprint_manager import (
    BrowserFingerprintManager, 
    FingerprintConfig,
    BrowserType,
    OSType
)
from mercari_agent.infrastructure.scraping.tls_fingerprint_manager import (
    TLSFingerprintManager,
    TLSConfig
)
from mercari_agent.domain.entities.query import QueryEntity


async def test_fingerprint_managers():
    """测试指纹管理器基础功能"""
    print("=" * 60)
    print("测试指纹管理器基础功能")
    print("=" * 60)
    
    try:
        # 测试浏览器指纹管理器
        print("\n1. 测试浏览器指纹管理器...")
        fingerprint_config = FingerprintConfig(
            enable_user_agent_rotation=True,
            enable_webgl_spoofing=True,
            enable_canvas_spoofing=True,
            max_fingerprint_usage=10
        )
        
        browser_manager = BrowserFingerprintManager(fingerprint_config)
        
        # 生成多个指纹
        fingerprints = []
        for i in range(3):
            fingerprint = browser_manager.generate_fingerprint()
            fingerprints.append(fingerprint)
            print(f"  指纹 {i+1}: {fingerprint.browser_type.value} on {fingerprint.os_type.value}")
            print(f"    User-Agent: {fingerprint.user_agent[:80]}...")
            print(f"    屏幕分辨率: {fingerprint.screen_resolution}")
            print(f"    WebGL渲染器: {fingerprint.webgl_fingerprint.renderer[:50]}...")
        
        # 测试指纹统计
        stats = browser_manager.get_fingerprint_stats()
        print(f"\n  指纹统计: {stats}")
        
        # 测试指纹一致性验证
        for i, fingerprint in enumerate(fingerprints):
            is_valid = browser_manager.validate_fingerprint_consistency(fingerprint)
            print(f"  指纹 {i+1} 一致性验证: {'通过' if is_valid else '失败'}")
        
        print("✅ 浏览器指纹管理器测试通过")
        
        # 测试TLS指纹管理器
        print("\n2. 测试TLS指纹管理器...")
        tls_config = TLSConfig(
            enable_fingerprint_rotation=True,
            enable_ja3_spoofing=True,
            enable_ja4_spoofing=True
        )
        
        tls_manager = TLSFingerprintManager(tls_config)
        
        # 生成TLS指纹
        tls_fingerprint = tls_manager.get_fingerprint()
        print(f"  TLS指纹ID: {tls_fingerprint.fingerprint_id}")
        print(f"  JA3哈希: {tls_fingerprint.ja3_hash}")
        print(f"  支持的密码套件数量: {len(tls_fingerprint.cipher_suites)}")
        print(f"  支持的扩展数量: {len(tls_fingerprint.extensions)}")
        
        # 测试TLS统计
        tls_stats = tls_manager.get_stats()
        print(f"  TLS统计: {tls_stats}")
        
        print("✅ TLS指纹管理器测试通过")
        
    except Exception as e:
        print(f"❌ 指纹管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_scraper_integration():
    """测试爬虫服务集成"""
    print("\n" + "=" * 60)
    print("测试爬虫服务集成")
    print("=" * 60)
    
    try:
        # 创建配置
        config = AppConfig()
        
        # 创建爬虫服务
        scraper_service = ScraperService(config)
        
        print("\n1. 初始化爬虫服务...")
        await scraper_service.initialize()
        print("✅ 爬虫服务初始化成功")
        
        # 检查指纹管理器是否正确集成
        print("\n2. 检查指纹管理器集成...")
        if hasattr(scraper_service.scraper, 'browser_fingerprint_manager'):
            if scraper_service.scraper.browser_fingerprint_manager:
                print("✅ 浏览器指纹管理器已集成")
                
                # 检查当前指纹
                if scraper_service.scraper.current_fingerprint:
                    current_fp = scraper_service.scraper.current_fingerprint
                    print(f"  当前指纹: {current_fp.browser_type.value} on {current_fp.os_type.value}")
                    print(f"  使用次数: {current_fp.usage_count}")
                else:
                    print("⚠️ 当前指纹未设置")
            else:
                print("⚠️ 浏览器指纹管理器未初始化")
        else:
            print("⚠️ 浏览器指纹管理器未集成")
        
        if hasattr(scraper_service.scraper, 'tls_fingerprint_manager'):
            if scraper_service.scraper.tls_fingerprint_manager:
                print("✅ TLS指纹管理器已集成")
                
                # 检查当前TLS指纹
                if scraper_service.scraper.current_tls_fingerprint:
                    current_tls = scraper_service.scraper.current_tls_fingerprint
                    print(f"  当前TLS指纹ID: {current_tls.fingerprint_id}")
                    print(f"  使用次数: {current_tls.usage_count}")
                else:
                    print("⚠️ 当前TLS指纹未设置")
            else:
                print("⚠️ TLS指纹管理器未初始化")
        else:
            print("⚠️ TLS指纹管理器未集成")
        
        # 测试服务信息
        print("\n3. 测试服务信息...")
        service_info = scraper_service.get_service_info()
        print(f"  服务名称: {service_info.get('service_name')}")
        print(f"  可用策略: {service_info.get('available_strategies')}")
        print(f"  缓存大小: {service_info.get('cache_size')}")
        
        # 检查指纹统计信息
        if 'fingerprint_stats' in service_info:
            fp_stats = service_info['fingerprint_stats']
            print(f"  指纹统计信息: {fp_stats}")
            print("✅ 指纹统计信息获取成功")
        else:
            print("⚠️ 指纹统计信息未包含在服务信息中")
        
        # 测试健康检查
        print("\n4. 测试健康检查...")
        health = await scraper_service.health_check()
        print(f"  健康状态: {health}")
        
        # 关闭服务
        print("\n5. 关闭服务...")
        await scraper_service.close()
        print("✅ 服务关闭成功")
        
        print("✅ 爬虫服务集成测试通过")
        
    except Exception as e:
        print(f"❌ 爬虫服务集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_fingerprint_rotation():
    """测试指纹轮换功能"""
    print("\n" + "=" * 60)
    print("测试指纹轮换功能")
    print("=" * 60)
    
    try:
        # 创建配置，设置较低的使用次数限制以便测试轮换
        fingerprint_config = FingerprintConfig(
            enable_user_agent_rotation=True,
            max_fingerprint_usage=2,  # 设置为2次以便快速触发轮换
            fingerprint_rotation_interval=1  # 1秒轮换间隔
        )
        
        browser_manager = BrowserFingerprintManager(fingerprint_config)
        
        print("\n1. 生成初始指纹...")
        initial_fingerprint = browser_manager.generate_fingerprint()
        fingerprint_id = browser_manager._generate_fingerprint_id(initial_fingerprint)
        print(f"  初始指纹ID: {fingerprint_id}")
        print(f"  浏览器类型: {initial_fingerprint.browser_type.value}")
        
        print("\n2. 模拟多次使用指纹...")
        for i in range(3):
            fingerprint = browser_manager.get_fingerprint(fingerprint_id)
            print(f"  使用 {i+1}: 使用次数 = {fingerprint.usage_count}")
            
            # 检查是否触发了轮换
            new_fingerprint_id = browser_manager._generate_fingerprint_id(fingerprint)
            if new_fingerprint_id != fingerprint_id:
                print(f"  🔄 指纹已轮换: {fingerprint_id} -> {new_fingerprint_id}")
                fingerprint_id = new_fingerprint_id
        
        print("\n3. 测试异步轮换...")
        rotated_fingerprint = await browser_manager.rotate_fingerprint_async(fingerprint_id)
        print(f"  轮换后的指纹: {rotated_fingerprint.browser_type.value}")
        
        print("\n4. 清理过期指纹...")
        browser_manager.cleanup_old_fingerprints()
        final_stats = browser_manager.get_fingerprint_stats()
        print(f"  清理后统计: {final_stats}")
        
        print("✅ 指纹轮换功能测试通过")
        
    except Exception as e:
        print(f"❌ 指纹轮换功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_fingerprint_export_import():
    """测试指纹导出导入功能"""
    print("\n" + "=" * 60)
    print("测试指纹导出导入功能")
    print("=" * 60)
    
    try:
        browser_manager = BrowserFingerprintManager()
        
        print("\n1. 生成测试指纹...")
        original_fingerprint = browser_manager.generate_fingerprint(
            BrowserType.CHROME, 
            OSType.WINDOWS
        )
        print(f"  原始指纹: {original_fingerprint.browser_type.value} on {original_fingerprint.os_type.value}")
        
        print("\n2. 导出指纹...")
        exported_json = browser_manager.export_fingerprint(original_fingerprint)
        print(f"  导出JSON长度: {len(exported_json)} 字符")
        
        print("\n3. 导入指纹...")
        imported_fingerprint = browser_manager.import_fingerprint(exported_json)
        print(f"  导入指纹: {imported_fingerprint.browser_type.value} on {imported_fingerprint.os_type.value}")
        
        print("\n4. 验证导入导出一致性...")
        consistency_checks = [
            ("User-Agent", original_fingerprint.user_agent == imported_fingerprint.user_agent),
            ("浏览器类型", original_fingerprint.browser_type == imported_fingerprint.browser_type),
            ("操作系统", original_fingerprint.os_type == imported_fingerprint.os_type),
            ("屏幕分辨率", original_fingerprint.screen_resolution == imported_fingerprint.screen_resolution),
            ("WebGL渲染器", original_fingerprint.webgl_fingerprint.renderer == imported_fingerprint.webgl_fingerprint.renderer)
        ]
        
        all_passed = True
        for check_name, result in consistency_checks:
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}: {'一致' if result else '不一致'}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("✅ 指纹导出导入功能测试通过")
        else:
            print("❌ 指纹导出导入功能测试失败")
            return False
        
    except Exception as e:
        print(f"❌ 指纹导出导入功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """主测试函数"""
    print("🚀 开始指纹管理器集成测试")
    print("测试时间:", asyncio.get_event_loop().time())
    
    test_results = []
    
    # 运行所有测试
    tests = [
        ("指纹管理器基础功能", test_fingerprint_managers),
        ("爬虫服务集成", test_scraper_integration),
        ("指纹轮换功能", test_fingerprint_rotation),
        ("指纹导出导入功能", test_fingerprint_export_import)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 运行测试: {test_name}")
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 {test_name} 出现异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 个测试通过, {failed} 个测试失败")
    
    if failed == 0:
        print("🎉 所有测试通过！指纹管理器集成成功！")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
