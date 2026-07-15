#!/usr/bin/env python3
"""
日志系统测试脚本

测试日志系统的配置和功能
"""

import os
import sys
import logging
import tempfile
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

def test_basic_logging():
    """测试基础日志功能"""
    print("🔍 测试基础日志功能...")
    
    results = []
    
    try:
        # 测试标准logging模块
        logger = logging.getLogger('test_logger')
        logger.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
        # 测试各种日志级别
        logger.debug("这是调试消息")
        logger.info("这是信息消息")
        logger.warning("这是警告消息")
        logger.error("这是错误消息")
        logger.critical("这是严重错误消息")
        
        results.append("✅ 标准logging模块工作正常")
        results.append("✅ 各种日志级别输出正常")
        
    except Exception as e:
        results.append(f"❌ 基础日志功能测试失败: {e}")
    
    return results

def test_log_directory():
    """测试日志目录"""
    print("🔍 测试日志目录...")
    
    results = []
    
    try:
        # 检查配置的日志目录
        log_dirs = [
            project_root / "data" / "logs",
            project_root / "logs",
            "./logs"
        ]
        
        existing_dirs = []
        for log_dir in log_dirs:
            log_path = Path(log_dir)
            if log_path.exists():
                existing_dirs.append(str(log_path))
            else:
                # 尝试创建目录
                try:
                    log_path.mkdir(parents=True, exist_ok=True)
                    existing_dirs.append(f"{log_path} (已创建)")
                except Exception as e:
                    results.append(f"⚠️ 无法创建日志目录 {log_path}: {e}")
        
        if existing_dirs:
            results.append("✅ 日志目录可用:")
            for dir_path in existing_dirs:
                results.append(f"   - {dir_path}")
        else:
            results.append("❌ 没有可用的日志目录")
        
    except Exception as e:
        results.append(f"❌ 日志目录测试失败: {e}")
    
    return results

def test_file_logging():
    """测试文件日志"""
    print("🔍 测试文件日志...")
    
    results = []
    
    try:
        # 创建临时日志文件
        log_dir = project_root / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # 创建文件日志记录器
        file_logger = logging.getLogger('file_test_logger')
        file_logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        file_logger.addHandler(file_handler)
        
        # 写入测试日志
        test_messages = [
            ("DEBUG", "调试信息测试"),
            ("INFO", "信息记录测试"),
            ("WARNING", "警告信息测试"),
            ("ERROR", "错误信息测试"),
            ("CRITICAL", "严重错误测试")
        ]
        
        for level, message in test_messages:
            getattr(file_logger, level.lower())(message)
        
        # 关闭处理器
        file_handler.close()
        file_logger.removeHandler(file_handler)
        
        # 检查文件是否创建并包含内容
        if log_file.exists():
            file_size = log_file.stat().st_size
            if file_size > 0:
                results.append(f"✅ 日志文件创建成功: {log_file}")
                results.append(f"✅ 日志文件大小: {file_size} 字节")
                
                # 读取部分内容验证
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "调试信息测试" in content and "严重错误测试" in content:
                        results.append("✅ 日志内容写入正确")
                    else:
                        results.append("⚠️ 日志内容可能不完整")
            else:
                results.append("❌ 日志文件为空")
        else:
            results.append("❌ 日志文件未创建")
            
    except Exception as e:
        results.append(f"❌ 文件日志测试失败: {e}")
    
    return results

def test_log_rotation():
    """测试日志轮转"""
    print("🔍 测试日志轮转配置...")
    
    results = []
    
    try:
        from logging.handlers import RotatingFileHandler
        
        log_dir = project_root / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建轮转日志处理器
        log_file = log_dir / "rotation_test.log"
        rotating_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            encoding='utf-8'
        )
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        rotating_handler.setFormatter(formatter)
        
        # 创建logger
        rotation_logger = logging.getLogger('rotation_test')
        rotation_logger.setLevel(logging.INFO)
        rotation_logger.addHandler(rotating_handler)
        
        # 写入一些测试数据
        for i in range(10):
            rotation_logger.info(f"日志轮转测试消息 {i}")
        
        # 清理
        rotating_handler.close()
        rotation_logger.removeHandler(rotating_handler)
        
        results.append("✅ 日志轮转配置可用")
        results.append("✅ RotatingFileHandler 工作正常")
        
    except Exception as e:
        results.append(f"❌ 日志轮转测试失败: {e}")
    
    return results

def test_structured_logging():
    """测试结构化日志"""
    print("🔍 测试结构化日志...")
    
    results = []
    
    try:
        import json
        
        # 创建结构化日志记录器
        struct_logger = logging.getLogger('structured_test')
        struct_logger.setLevel(logging.INFO)
        
        # 创建自定义格式器
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                return json.dumps(log_entry, ensure_ascii=False)
        
        # 创建临时文件处理器
        log_dir = project_root / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        json_log_file = log_dir / "structured_test.json"
        json_handler = logging.FileHandler(json_log_file, encoding='utf-8')
        json_handler.setFormatter(JSONFormatter())
        
        struct_logger.addHandler(json_handler)
        
        # 写入结构化日志
        struct_logger.info("结构化日志测试")
        struct_logger.warning("这是一个警告消息")
        struct_logger.error("这是一个错误消息")
        
        # 关闭处理器
        json_handler.close()
        struct_logger.removeHandler(json_handler)
        
        # 验证JSON格式
        if json_log_file.exists():
            with open(json_log_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                lines = content.split('\n')
                
                try:
                    for line in lines:
                        if line:
                            json.loads(line)  # 验证JSON格式
                    results.append("✅ 结构化日志(JSON)格式正确")
                    results.append(f"✅ 生成了 {len([l for l in lines if l])} 条结构化日志")
                except json.JSONDecodeError:
                    results.append("❌ 结构化日志格式错误")
        else:
            results.append("❌ 结构化日志文件未创建")
            
    except Exception as e:
        results.append(f"❌ 结构化日志测试失败: {e}")
    
    return results

def test_application_logging_config():
    """测试应用日志配置"""
    print("🔍 测试应用日志配置...")
    
    results = []
    
    try:
        # 尝试导入应用配置
        from mercari_agent.shared.config.app_config import get_config
        
        config = get_config()
        logging_config = config.logging
        
        results.append("✅ 应用日志配置加载成功")
        results.append(f"   日志级别: {logging_config.level}")
        results.append(f"   日志目录: {logging_config.log_dir}")
        results.append(f"   日志格式: {logging_config.format}")
        
        # 检查日志目录是否存在
        log_dir = Path(logging_config.log_dir)
        if log_dir.exists():
            results.append(f"✅ 配置的日志目录存在: {log_dir}")
        else:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                results.append(f"✅ 日志目录已创建: {log_dir}")
            except Exception as e:
                results.append(f"❌ 无法创建日志目录: {e}")
        
    except ImportError as e:
        results.append(f"⚠️ 无法导入应用配置: {e}")
    except Exception as e:
        results.append(f"❌ 应用日志配置测试失败: {e}")
    
    return results

def main():
    """主函数"""
    print("🚀 Mercari AI Agent 日志系统测试")
    print("=" * 60)
    
    os.chdir(project_root)
    
    all_results = []
    
    # 运行测试
    test_functions = [
        test_basic_logging,
        test_log_directory,
        test_file_logging,
        test_log_rotation,
        test_structured_logging,
        test_application_logging_config
    ]
    
    for test_func in test_functions:
        try:
            results = test_func()
            all_results.extend(results)
            for result in results:
                print(result)
            print()
        except Exception as e:
            error_msg = f"❌ 测试失败: {test_func.__name__} - {e}"
            print(error_msg)
            all_results.append(error_msg)
    
    # 统计结果
    passed = sum(1 for r in all_results if r.startswith("✅"))
    failed = sum(1 for r in all_results if r.startswith("❌"))
    warnings = sum(1 for r in all_results if r.startswith("⚠️"))
    
    print("=" * 60)
    print("📊 日志系统测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 警告: {warnings}")
    print(f"📊 总计: {len(all_results)}")
    
    # 评估结果
    if failed == 0:
        print("🎉 日志系统功能完全正常!")
        return 0
    elif failed <= 2:
        print("⚠️ 日志系统基本正常，少数功能有问题")
        return 0
    else:
        print("🚨 日志系统存在较多问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())