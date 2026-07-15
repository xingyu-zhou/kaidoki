"""
插件框架测试运行器

该模块提供了统一的测试运行和报告功能，包括：
- 测试套件执行
- 覆盖率报告
- 性能基准测试
- 集成测试协调
- 测试结果汇总

使用方法：
python test_runner.py [options]

Author: Mercari AI Agent Team
"""

import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

# 尝试导入pytest和coverage
try:
    import pytest
    import coverage
    HAS_PYTEST = True
    HAS_COVERAGE = True
except ImportError:
    HAS_PYTEST = False
    HAS_COVERAGE = False
    print("Warning: pytest and coverage not available, using basic test runner")


class TestRunner:
    """测试运行器"""
    
    def __init__(self, test_dir: Optional[Path] = None):
        self.test_dir = test_dir or Path(__file__).parent
        self.results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'duration': 0.0,
            'coverage': None
        }
    
    def run_all_tests(self, verbose: bool = False, coverage_enabled: bool = True) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 开始运行插件框架测试套件")
        print("=" * 60)
        
        start_time = time.time()
        
        if HAS_PYTEST:
            self._run_pytest_tests(verbose, coverage_enabled)
        else:
            self._run_basic_tests(verbose)
        
        self.results['duration'] = time.time() - start_time
        
        self._print_summary()
        return self.results
    
    def _run_pytest_tests(self, verbose: bool, coverage_enabled: bool):
        """使用pytest运行测试"""
        args = [
            str(self.test_dir),
            '-v' if verbose else '-q',
            '--tb=short',
            '-x',  # 遇到第一个失败就停止
        ]
        
        # 添加标记过滤
        args.extend([
            '-m', 'not slow',  # 默认跳过慢速测试
            '--durations=10',  # 显示最慢的10个测试
        ])
        
        if coverage_enabled and HAS_COVERAGE:
            args.extend([
                '--cov=mercari_agent.plugins',
                '--cov-report=term-missing',
                '--cov-report=html:htmlcov',
                '--cov-fail-under=80'
            ])
        
        try:
            result = pytest.main(args)
            self._process_pytest_result(result)
        except Exception as e:
            self.results['errors'].append(f"pytest执行失败: {e}")
            self.results['failed'] += 1
    
    def _run_basic_tests(self, verbose: bool):
        """运行基础测试（无pytest时的fallback）"""
        print("使用基础测试运行器（建议安装pytest获得更好的测试体验）")
        
        test_files = list(self.test_dir.glob("test_*.py"))
        print(f"找到 {len(test_files)} 个测试文件")
        
        for test_file in test_files:
            try:
                print(f"运行测试文件: {test_file.name}")
                result = subprocess.run([
                    sys.executable, str(test_file)
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    self.results['passed'] += 1
                    if verbose:
                        print(f"  ✅ {test_file.name} 通过")
                else:
                    self.results['failed'] += 1
                    error_msg = f"{test_file.name}: {result.stderr}"
                    self.results['errors'].append(error_msg)
                    if verbose:
                        print(f"  ❌ {test_file.name} 失败: {result.stderr}")
                
                self.results['total_tests'] += 1
                
            except subprocess.TimeoutExpired:
                self.results['failed'] += 1
                self.results['errors'].append(f"{test_file.name}: 测试超时")
                print(f"  ⏱️  {test_file.name} 超时")
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append(f"{test_file.name}: {e}")
                print(f"  ❌ {test_file.name} 错误: {e}")
    
    def _process_pytest_result(self, result_code: int):
        """处理pytest结果"""
        if result_code == 0:
            print("✅ 所有测试通过")
        elif result_code == 1:
            print("❌ 有测试失败")
            self.results['failed'] += 1
        elif result_code == 2:
            print("⚠️  测试执行中断")
            self.results['errors'].append("测试执行中断")
        elif result_code == 3:
            print("⚠️  内部错误")
            self.results['errors'].append("pytest内部错误")
        elif result_code == 4:
            print("⚠️  pytest使用错误")
            self.results['errors'].append("pytest使用错误")
        elif result_code == 5:
            print("⚠️  没有找到测试")
            self.results['errors'].append("没有找到测试")
    
    def _print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("📊 测试结果摘要")
        print("=" * 60)
        
        print(f"总测试数: {self.results['total_tests']}")
        print(f"通过: {self.results['passed']}")
        print(f"失败: {self.results['failed']}")
        print(f"跳过: {self.results['skipped']}")
        print(f"执行时间: {self.results['duration']:.2f}秒")
        
        if self.results['errors']:
            print("\n❌ 错误信息:")
            for error in self.results['errors']:
                print(f"  - {error}")
        
        if self.results['coverage']:
            print(f"\n📈 代码覆盖率: {self.results['coverage']:.1f}%")
        
        # 成功率
        if self.results['total_tests'] > 0:
            success_rate = (self.results['passed'] / self.results['total_tests']) * 100
            print(f"🎯 成功率: {success_rate:.1f}%")
            
            if success_rate >= 95:
                print("🎉 优秀的测试结果！")
            elif success_rate >= 80:
                print("👍 良好的测试结果")
            elif success_rate >= 60:
                print("⚠️  测试结果需要改进")
            else:
                print("❌ 测试结果需要立即修复")
    
    def run_specific_tests(self, test_patterns: List[str], verbose: bool = False) -> Dict[str, Any]:
        """运行特定测试"""
        print(f"🎯 运行指定测试: {', '.join(test_patterns)}")
        
        if not HAS_PYTEST:
            print("需要pytest才能运行特定测试")
            return self.results
        
        args = ['-v' if verbose else '-q']
        args.extend(test_patterns)
        
        try:
            result = pytest.main(args)
            self._process_pytest_result(result)
        except Exception as e:
            self.results['errors'].append(f"特定测试执行失败: {e}")
        
        return self.results
    
    def run_integration_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """运行集成测试"""
        print("🔗 运行集成测试")
        
        if not HAS_PYTEST:
            print("需要pytest才能运行集成测试")
            return self.results
        
        args = [
            str(self.test_dir),
            '-v' if verbose else '-q',
            '-m', 'integration',
            '--tb=short'
        ]
        
        try:
            result = pytest.main(args)
            self._process_pytest_result(result)
        except Exception as e:
            self.results['errors'].append(f"集成测试执行失败: {e}")
        
        return self.results
    
    def run_performance_tests(self, verbose: bool = False) -> Dict[str, Any]:
        """运行性能测试"""
        print("⚡ 运行性能测试")
        
        if not HAS_PYTEST:
            print("需要pytest才能运行性能测试")
            return self.results
        
        args = [
            str(self.test_dir),
            '-v' if verbose else '-q',
            '-m', 'slow',
            '--tb=short',
            '--durations=0'  # 显示所有测试的执行时间
        ]
        
        try:
            result = pytest.main(args)
            self._process_pytest_result(result)
        except Exception as e:
            self.results['errors'].append(f"性能测试执行失败: {e}")
        
        return self.results
    
    def generate_report(self, output_file: Optional[Path] = None) -> bool:
        """生成测试报告"""
        try:
            report_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'test_results': self.results,
                'environment': {
                    'python_version': sys.version,
                    'platform': sys.platform,
                    'test_dir': str(self.test_dir),
                    'has_pytest': HAS_PYTEST,
                    'has_coverage': HAS_COVERAGE
                }
            }
            
            if output_file is None:
                output_file = self.test_dir / 'test_report.json'
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            print(f"📄 测试报告已保存到: {output_file}")
            return True
            
        except Exception as e:
            print(f"生成报告失败: {e}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='插件框架测试运行器')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('--no-coverage', action='store_true', help='禁用覆盖率检查')
    parser.add_argument('--integration', action='store_true', help='只运行集成测试')
    parser.add_argument('--performance', action='store_true', help='只运行性能测试')
    parser.add_argument('--pattern', nargs='+', help='运行匹配模式的测试')
    parser.add_argument('--report', type=str, help='生成报告文件路径')
    parser.add_argument('--test-dir', type=str, help='测试目录路径')
    
    args = parser.parse_args()
    
    # 初始化测试运行器
    test_dir = Path(args.test_dir) if args.test_dir else Path(__file__).parent
    runner = TestRunner(test_dir)
    
    # 运行测试
    if args.integration:
        results = runner.run_integration_tests(args.verbose)
    elif args.performance:
        results = runner.run_performance_tests(args.verbose)
    elif args.pattern:
        results = runner.run_specific_tests(args.pattern, args.verbose)
    else:
        results = runner.run_all_tests(args.verbose, not args.no_coverage)
    
    # 生成报告
    if args.report:
        runner.generate_report(Path(args.report))
    
    # 退出代码
    exit_code = 0 if results['failed'] == 0 else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()