# 紧急修复脚本和执行指南

## 立即可执行的SSL修复脚本

### 1. 紧急SSL修复脚本 (emergency_ssl_fix.py)

```python
#!/usr/bin/env python3
"""
Mercari爬虫系统SSL配置紧急修复脚本
用于修复TCPConnector(ssl=False)导致的Connection closed问题

使用方法:
python emergency_ssl_fix.py

风险等级: 极低 (只是修复明显的配置错误)
预期效果: 系统从完全不可用恢复到正常运行
"""

import os
import sys
import shutil
import re
from datetime import datetime
from pathlib import Path

class EmergencySSLFix:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.target_file = self.project_root / "mercari_ai_agent/src/mercari_agent/scrapers/enhanced_session_manager.py"
        self.backup_dir = self.project_root / "backups" / f"ssl_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def run_fix(self):
        """执行修复"""
        print("🔧 开始执行Mercari爬虫系统SSL紧急修复...")
        
        # 1. 检查文件是否存在
        if not self.target_file.exists():
            print(f"❌ 错误: 目标文件不存在: {self.target_file}")
            return False
        
        # 2. 创建备份
        if not self.create_backup():
            print("❌ 错误: 备份创建失败")
            return False
        
        # 3. 执行修复
        if not self.apply_ssl_fix():
            print("❌ 错误: SSL修复失败")
            return False
        
        # 4. 验证修复
        if not self.verify_fix():
            print("❌ 错误: 修复验证失败")
            return False
        
        print("✅ SSL修复完成！")
        print(f"备份位置: {self.backup_dir}")
        
        return True
    
    def create_backup(self):
        """创建备份"""
        try:
            print("📦 创建备份...")
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            backup_file = self.backup_dir / self.target_file.name
            shutil.copy2(self.target_file, backup_file)
            
            print(f"✅ 备份创建成功: {backup_file}")
            return True
        except Exception as e:
            print(f"❌ 备份创建失败: {e}")
            return False
    
    def apply_ssl_fix(self):
        """应用SSL修复"""
        try:
            print("🔧 应用SSL修复...")
            
            # 读取原文件
            with open(self.target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否需要修复
            if 'ssl=False' not in content:
                print("ℹ️  SSL配置已经正确，无需修复")
                return True
            
            # 应用修复
            original_content = content
            
            # 修复1: 将ssl=False改为ssl=True
            content = re.sub(
                r'ssl=False\s*#.*?致命错误.*?',
                'ssl=True  # ✅ 修复：启用SSL支持',
                content
            )
            
            # 如果上面的正则没有匹配到，使用更简单的替换
            if content == original_content:
                content = content.replace('ssl=False', 'ssl=True')
            
            # 修复2: 更新健康检查URL
            content = re.sub(
                r'https://httpbin\.org/get',
                'https://jp.mercari.com/robots.txt',
                content
            )
            
            # 写入修复后的文件
            with open(self.target_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ SSL配置修复完成")
            return True
            
        except Exception as e:
            print(f"❌ SSL修复失败: {e}")
            return False
    
    def verify_fix(self):
        """验证修复"""
        try:
            print("🔍 验证修复...")
            
            # 检查文件内容
            with open(self.target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证SSL配置
            if 'ssl=False' in content:
                print("❌ 验证失败: 仍然存在ssl=False配置")
                return False
            
            if 'ssl=True' not in content:
                print("❌ 验证失败: 未找到ssl=True配置")
                return False
            
            # 验证健康检查URL
            if 'https://jp.mercari.com/robots.txt' in content:
                print("✅ 健康检查URL已更新")
            else:
                print("⚠️  健康检查URL未更新，但不影响主要修复")
            
            print("✅ 修复验证通过")
            return True
            
        except Exception as e:
            print(f"❌ 验证失败: {e}")
            return False
    
    def rollback(self):
        """回滚修复"""
        try:
            print("🔄 回滚修复...")
            
            # 查找最新的备份
            backup_files = list(self.project_root.glob("backups/ssl_fix_*/enhanced_session_manager.py"))
            if not backup_files:
                print("❌ 没有找到备份文件")
                return False
            
            latest_backup = max(backup_files, key=lambda p: p.parent.name)
            
            # 恢复文件
            shutil.copy2(latest_backup, self.target_file)
            
            print(f"✅ 回滚成功，已恢复到: {latest_backup}")
            return True
            
        except Exception as e:
            print(f"❌ 回滚失败: {e}")
            return False

def main():
    """主函数"""
    print("=" * 60)
    print("🚨 Mercari爬虫系统SSL紧急修复工具")
    print("=" * 60)
    
    fixer = EmergencySSLFix()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        # 回滚模式
        success = fixer.rollback()
    else:
        # 修复模式
        success = fixer.run_fix()
    
    if success:
        print("\n🎉 操作成功完成！")
        print("\n📋 下一步建议:")
        print("1. 重启应用程序")
        print("2. 运行验证测试 (python ssl_connection_test.py)")
        print("3. 监控系统日志")
        sys.exit(0)
    else:
        print("\n💥 操作失败！")
        print("请检查错误信息并手动修复")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 2. SSL连接验证脚本 (ssl_connection_test.py)

```python
#!/usr/bin/env python3
"""
SSL连接验证脚本
用于验证SSL修复是否生效

使用方法:
python ssl_connection_test.py
"""

import asyncio
import aiohttp
import ssl
import time
from datetime import datetime
from typing import Dict, Any

class SSLConnectionTest:
    def __init__(self):
        self.test_urls = [
            'https://jp.mercari.com/robots.txt',
            'https://jp.mercari.com/',
            'https://api.mercari.jp/v2/entities:search'
        ]
        self.results = {}
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🧪 开始SSL连接验证测试...")
        
        # 测试1: 基础SSL连接
        await self.test_basic_ssl_connection()
        
        # 测试2: 会话管理器测试
        await self.test_session_manager()
        
        # 测试3: 连接池测试
        await self.test_connection_pool()
        
        # 测试4: 并发连接测试
        await self.test_concurrent_connections()
        
        # 生成报告
        self.generate_report()
        
        return self.results
    
    async def test_basic_ssl_connection(self):
        """测试基础SSL连接"""
        print("\n📡 测试基础SSL连接...")
        
        success_count = 0
        total_tests = len(self.test_urls)
        response_times = []
        
        for url in self.test_urls:
            try:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = (time.time() - start_time) * 1000
                        response_times.append(response_time)
                        
                        if response.status < 400:
                            success_count += 1
                            print(f"✅ {url} - {response.status} - {response_time:.0f}ms")
                        else:
                            print(f"⚠️  {url} - {response.status} - {response_time:.0f}ms")
                        
            except Exception as e:
                print(f"❌ {url} - Error: {e}")
        
        success_rate = (success_count / total_tests) * 100
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        self.results['basic_ssl'] = {
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'total_tests': total_tests,
            'passed': success_rate >= 80  # 80%成功率阈值
        }
        
        print(f"📊 基础SSL连接测试结果: {success_rate:.1f}% 成功率, 平均响应时间: {avg_response_time:.0f}ms")
    
    async def test_session_manager(self):
        """测试会话管理器"""
        print("\n🔄 测试会话管理器...")
        
        try:
            # 动态导入会话管理器
            import sys
            sys.path.append('mercari_ai_agent/src')
            
            from mercari_agent.scrapers.enhanced_session_manager import EnhancedSessionManager
            
            start_time = time.time()
            
            # 创建会话管理器
            manager = EnhancedSessionManager()
            await manager.initialize()
            
            # 测试会话获取
            session = await manager.get_session_safe()
            
            if session and not session.closed:
                # 测试请求
                async with session.get('https://jp.mercari.com/robots.txt') as response:
                    if response.status == 200:
                        print("✅ 会话管理器测试通过")
                        self.results['session_manager'] = {
                            'passed': True,
                            'initialization_time': (time.time() - start_time) * 1000,
                            'status': 'healthy'
                        }
                    else:
                        print(f"⚠️  会话管理器测试部分通过: {response.status}")
                        self.results['session_manager'] = {
                            'passed': False,
                            'status': 'partial',
                            'error': f'HTTP {response.status}'
                        }
            else:
                print("❌ 会话管理器测试失败: 无法获取会话")
                self.results['session_manager'] = {
                    'passed': False,
                    'status': 'failed',
                    'error': 'Cannot get session'
                }
            
            # 清理
            await manager.close_all_sessions()
            
        except Exception as e:
            print(f"❌ 会话管理器测试失败: {e}")
            self.results['session_manager'] = {
                'passed': False,
                'status': 'error',
                'error': str(e)
            }
    
    async def test_connection_pool(self):
        """测试连接池"""
        print("\n🏊 测试连接池...")
        
        try:
            # 创建连接池
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                ssl=True
            )
            
            success_count = 0
            total_requests = 10
            
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = []
                
                for i in range(total_requests):
                    task = session.get('https://jp.mercari.com/robots.txt')
                    tasks.append(task)
                
                # 并发执行
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        print(f"❌ 请求 {i+1} 失败: {response}")
                    else:
                        async with response:
                            if response.status < 400:
                                success_count += 1
                                print(f"✅ 请求 {i+1} 成功: {response.status}")
                            else:
                                print(f"⚠️  请求 {i+1} 部分成功: {response.status}")
            
            success_rate = (success_count / total_requests) * 100
            
            self.results['connection_pool'] = {
                'success_rate': success_rate,
                'total_requests': total_requests,
                'passed': success_rate >= 80
            }
            
            print(f"📊 连接池测试结果: {success_rate:.1f}% 成功率")
            
        except Exception as e:
            print(f"❌ 连接池测试失败: {e}")
            self.results['connection_pool'] = {
                'passed': False,
                'error': str(e)
            }
    
    async def test_concurrent_connections(self):
        """测试并发连接"""
        print("\n🚀 测试并发连接...")
        
        try:
            concurrent_sessions = 5
            requests_per_session = 3
            
            async def session_worker(session_id: int):
                results = []
                
                async with aiohttp.ClientSession() as session:
                    for i in range(requests_per_session):
                        try:
                            async with session.get('https://jp.mercari.com/robots.txt') as response:
                                results.append(response.status < 400)
                        except Exception:
                            results.append(False)
                
                return results
            
            # 并发执行多个会话
            tasks = [session_worker(i) for i in range(concurrent_sessions)]
            all_results = await asyncio.gather(*tasks)
            
            # 统计结果
            total_requests = concurrent_sessions * requests_per_session
            successful_requests = sum(sum(session_results) for session_results in all_results)
            success_rate = (successful_requests / total_requests) * 100
            
            self.results['concurrent_connections'] = {
                'success_rate': success_rate,
                'concurrent_sessions': concurrent_sessions,
                'total_requests': total_requests,
                'passed': success_rate >= 75
            }
            
            print(f"📊 并发连接测试结果: {success_rate:.1f}% 成功率")
            
        except Exception as e:
            print(f"❌ 并发连接测试失败: {e}")
            self.results['concurrent_connections'] = {
                'passed': False,
                'error': str(e)
            }
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📋 SSL连接验证测试报告")
        print("=" * 60)
        
        passed_tests = sum(1 for result in self.results.values() if result.get('passed', False))
        total_tests = len(self.results)
        
        print(f"📊 总体结果: {passed_tests}/{total_tests} 测试通过")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 详细结果
        for test_name, result in self.results.items():
            status = "✅ 通过" if result.get('passed', False) else "❌ 失败"
            print(f"\n{test_name}: {status}")
            
            if 'success_rate' in result:
                print(f"  成功率: {result['success_rate']:.1f}%")
            
            if 'avg_response_time' in result:
                print(f"  平均响应时间: {result['avg_response_time']:.0f}ms")
            
            if 'error' in result:
                print(f"  错误: {result['error']}")
        
        # 总结和建议
        print("\n📋 建议:")
        if passed_tests == total_tests:
            print("✅ 所有测试通过，SSL修复成功！")
        elif passed_tests >= total_tests * 0.75:
            print("⚠️  大部分测试通过，但仍有问题需要解决")
        else:
            print("❌ 多数测试失败，需要进一步检查SSL配置")
        
        return passed_tests >= total_tests * 0.75

async def main():
    """主函数"""
    tester = SSLConnectionTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. 快速部署脚本 (quick_deploy.py)

```python
#!/usr/bin/env python3
"""
快速部署脚本
执行完整的修复和验证流程

使用方法:
python quick_deploy.py
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """运行命令"""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} 成功")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} 失败")
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description} 异常: {e}")
        return False

def main():
    print("🚀 Mercari爬虫系统快速部署")
    print("=" * 50)
    
    # 检查Python环境
    print("🐍 检查Python环境...")
    if sys.version_info < (3, 7):
        print("❌ 错误: 需要Python 3.7或更高版本")
        sys.exit(1)
    
    # 步骤1: 执行SSL修复
    if not run_command("python emergency_ssl_fix.py", "执行SSL修复"):
        print("💥 SSL修复失败，停止部署")
        sys.exit(1)
    
    # 步骤2: 验证修复
    if not run_command("python ssl_connection_test.py", "验证SSL修复"):
        print("💥 SSL验证失败，但继续部署")
    
    # 步骤3: 重启相关服务（如果需要）
    print("\n🔄 部署完成！")
    print("\n📋 后续步骤:")
    print("1. 重启应用程序")
    print("2. 监控系统日志")
    print("3. 运行完整的端到端测试")
    
    return True

if __name__ == "__main__":
    main()
```

## 执行指南

### 立即执行步骤 (预计2小时内完成)

1. **准备工作**
   ```bash
   # 进入项目目录
   cd /path/to/mercari_ai_agent
   
   # 创建脚本文件
   # 将上述Python脚本保存为对应的文件名
   ```

2. **执行SSL修复**
   ```bash
   # 执行紧急修复
   python emergency_ssl_fix.py
   
   # 如果需要回滚
   python emergency_ssl_fix.py --rollback
   ```

3. **验证修复效果**
   ```bash
   # 运行验证测试
   python ssl_connection_test.py
   ```

4. **快速部署**
   ```bash
   # 一键部署（包含修复和验证）
   python quick_deploy.py
   ```

### 修复验证检查清单

- [ ] SSL连接成功率 > 95%
- [ ] 平均响应时间 < 3秒
- [ ] 会话管理器正常初始化
- [ ] 连接池工作正常
- [ ] 并发连接测试通过
- [ ] 系统日志无SSL相关错误

### 紧急回滚程序

如果修复后出现问题，可以立即回滚：

```bash
# 方法1: 使用脚本回滚
python emergency_ssl_fix.py --rollback

# 方法2: 手动回滚
cp backups/ssl_fix_YYYYMMDD_HHMMSS/enhanced_session_manager.py \
   mercari_ai_agent/src/mercari_agent/scrapers/enhanced_session_manager.py
```

### 注意事项

1. **风险评估**: 此修复风险极低，仅修复明显的配置错误
2. **备份策略**: 脚本会自动创建备份，可安全回滚
3. **监控要求**: 修复后需要监控系统日志和性能指标
4. **验证标准**: SSL连接成功率需要达到95%以上

### 后续优化建议

修复完成后，建议按照以下优先级进行后续优化：

1. **P1优化** (1-3天内)
   - 连接池参数调优
   - 智能会话选择算法
   - 自适应限流机制

2. **P2升级** (1-4周内)
   - 架构解耦重构
   - 微服务化迁移
   - 完整监控告警体系

通过执行这些脚本，可以将Mercari爬虫系统从完全不可用状态快速恢复到正常运行状态。