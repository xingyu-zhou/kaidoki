"""
基准测试报告生成器

生成详细的基准测试报告，包括HTML、PDF、Markdown等格式，
提供可视化图表和分析结果。

Author: Mercari AI Agent Team
"""

import os
import json
import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
import base64
import io

from .benchmark_runner import BenchmarkResult, BenchmarkRunner
from .performance_monitor import PerformanceMonitor, PerformanceAlert
from .memory_profiler import MemoryProfiler, MemoryLeak
from .load_tester import LoadTester, LoadTestResult
from .metrics_collector import BenchmarkMetricsCollector


@dataclass
class ReportConfig:
    """报告配置"""
    title: str = "插件框架性能基准测试报告"
    subtitle: str = "Performance Benchmark Report"
    author: str = "Mercari AI Agent Team"
    include_charts: bool = True
    include_raw_data: bool = False
    theme: str = "default"  # default, dark, light
    output_dir: str = "reports"
    timestamp: datetime = field(default_factory=datetime.now)


class BenchmarkReportGenerator:
    """基准测试报告生成器"""
    
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.logger = logging.getLogger("report_generator")
        
        # 确保输出目录存在
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def generate_comprehensive_report(
        self,
        benchmark_results: List[BenchmarkResult],
        load_test_results: List[LoadTestResult],
        metrics_collector: BenchmarkMetricsCollector,
        performance_monitor: Optional[PerformanceMonitor] = None,
        memory_profiler: Optional[MemoryProfiler] = None
    ) -> Dict[str, str]:
        """生成综合报告"""
        
        self.logger.info("开始生成综合基准测试报告")
        
        # 收集数据
        report_data = self._collect_report_data(
            benchmark_results, load_test_results, metrics_collector,
            performance_monitor, memory_profiler
        )
        
        # 生成不同格式的报告
        report_files = {}
        
        # HTML报告
        html_content = self._generate_html_report(report_data)
        html_file = os.path.join(self.config.output_dir, "benchmark_report.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        report_files["html"] = html_file
        
        # Markdown报告
        md_content = self._generate_markdown_report(report_data)
        md_file = os.path.join(self.config.output_dir, "benchmark_report.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        report_files["markdown"] = md_file
        
        # JSON数据
        json_content = json.dumps(report_data, indent=2, default=str)
        json_file = os.path.join(self.config.output_dir, "benchmark_data.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_content)
        report_files["json"] = json_file
        
        # CSV数据
        csv_content = self._generate_csv_report(report_data)
        csv_file = os.path.join(self.config.output_dir, "benchmark_data.csv")
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        report_files["csv"] = csv_file
        
        self.logger.info(f"报告生成完成，输出目录: {self.config.output_dir}")
        return report_files
    
    def _collect_report_data(
        self,
        benchmark_results: List[BenchmarkResult],
        load_test_results: List[LoadTestResult],
        metrics_collector: BenchmarkMetricsCollector,
        performance_monitor: Optional[PerformanceMonitor],
        memory_profiler: Optional[MemoryProfiler]
    ) -> Dict[str, Any]:
        """收集报告数据"""
        
        report_data = {
            "metadata": {
                "title": self.config.title,
                "subtitle": self.config.subtitle,
                "author": self.config.author,
                "generated_at": self.config.timestamp.isoformat(),
                "report_version": "1.0.0"
            },
            "summary": {},
            "benchmark_results": [],
            "load_test_results": [],
            "metrics": {},
            "performance_monitoring": {},
            "memory_profiling": {},
            "analysis": {}
        }
        
        # 基准测试结果
        if benchmark_results:
            report_data["benchmark_results"] = [
                {
                    "test_name": result.test_name,
                    "plugin_id": result.plugin_id,
                    "duration": result.duration,
                    "memory_peak": result.memory_peak,
                    "memory_avg": result.memory_avg,
                    "success": result.success,
                    "error": result.error,
                    "timestamp": result.timestamp.isoformat(),
                    "metadata": result.metadata
                }
                for result in benchmark_results
            ]
        
        # 负载测试结果
        if load_test_results:
            report_data["load_test_results"] = [
                {
                    "test_type": result.test_type.value,
                    "duration": result.duration,
                    "total_requests": result.total_requests,
                    "successful_requests": result.successful_requests,
                    "failed_requests": result.failed_requests,
                    "avg_response_time": result.avg_response_time,
                    "throughput": result.throughput,
                    "error_rate": result.error_rate,
                    "concurrent_users": result.concurrent_users,
                    "success": result.success,
                    "start_time": result.start_time.isoformat(),
                    "end_time": result.end_time.isoformat()
                }
                for result in load_test_results
            ]
        
        # 指标数据
        if metrics_collector:
            report_data["metrics"] = {
                "summary": metrics_collector.get_summary_statistics(),
                "current_snapshot": metrics_collector.get_current_snapshot(),
                "export_data": json.loads(metrics_collector.export_metrics("json", hours=24))
            }
        
        # 性能监控数据
        if performance_monitor:
            report_data["performance_monitoring"] = {
                "current_metrics": performance_monitor.get_current_metrics(),
                "performance_report": performance_monitor.get_performance_report(),
                "alerts": performance_monitor.get_alerts(hours=24)
            }
        
        # 内存分析数据
        if memory_profiler:
            report_data["memory_profiling"] = {
                "current_usage": memory_profiler.get_current_memory_usage(),
                "memory_trend": memory_profiler.get_memory_trend(hours=24),
                "object_growth": memory_profiler.get_object_growth_analysis(),
                "leak_report": memory_profiler.get_leak_report(),
                "gc_analysis": memory_profiler.get_gc_analysis(),
                "comprehensive_report": memory_profiler.get_comprehensive_report()
            }
        
        # 生成摘要
        report_data["summary"] = self._generate_summary(report_data)
        
        # 生成分析
        report_data["analysis"] = self._generate_analysis(report_data)
        
        return report_data
    
    def _generate_summary(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成摘要"""
        summary = {
            "total_benchmark_tests": len(report_data["benchmark_results"]),
            "total_load_tests": len(report_data["load_test_results"]),
            "benchmark_success_rate": 0.0,
            "load_test_success_rate": 0.0,
            "avg_response_time": 0.0,
            "avg_throughput": 0.0,
            "memory_usage": {},
            "performance_score": 0.0,
            "key_findings": []
        }
        
        # 基准测试摘要
        if report_data["benchmark_results"]:
            successful_benchmarks = sum(1 for r in report_data["benchmark_results"] if r["success"])
            summary["benchmark_success_rate"] = successful_benchmarks / len(report_data["benchmark_results"])
        
        # 负载测试摘要
        if report_data["load_test_results"]:
            successful_load_tests = sum(1 for r in report_data["load_test_results"] if r["success"])
            summary["load_test_success_rate"] = successful_load_tests / len(report_data["load_test_results"])
            
            # 平均响应时间和吞吐量
            response_times = [r["avg_response_time"] for r in report_data["load_test_results"]]
            throughputs = [r["throughput"] for r in report_data["load_test_results"]]
            
            if response_times:
                summary["avg_response_time"] = statistics.mean(response_times)
            if throughputs:
                summary["avg_throughput"] = statistics.mean(throughputs)
        
        # 内存使用摘要
        if report_data["memory_profiling"]:
            memory_data = report_data["memory_profiling"]
            summary["memory_usage"] = {
                "current_mb": memory_data.get("current_usage", {}).get("process_memory_mb", 0),
                "trend": memory_data.get("memory_trend", {}).get("growth_trend", "unknown"),
                "leak_count": len(memory_data.get("leak_report", {}).get("detected_leaks", {}))
            }
        
        # 性能评分（简化版）
        score = 100.0
        if summary["benchmark_success_rate"] < 0.9:
            score -= 20
        if summary["load_test_success_rate"] < 0.9:
            score -= 20
        if summary["avg_response_time"] > 1.0:
            score -= 15
        if summary["memory_usage"].get("leak_count", 0) > 0:
            score -= 25
        
        summary["performance_score"] = max(0, score)
        
        # 关键发现
        findings = []
        if summary["benchmark_success_rate"] < 0.9:
            findings.append("基准测试成功率低于90%，需要关注插件稳定性")
        if summary["load_test_success_rate"] < 0.9:
            findings.append("负载测试成功率低于90%，系统在高负载下不稳定")
        if summary["avg_response_time"] > 1.0:
            findings.append("平均响应时间超过1秒，需要性能优化")
        if summary["memory_usage"].get("leak_count", 0) > 0:
            findings.append(f"检测到 {summary['memory_usage']['leak_count']} 个内存泄漏")
        if summary["performance_score"] > 80:
            findings.append("整体性能表现良好")
        
        summary["key_findings"] = findings
        
        return summary
    
    def _generate_analysis(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成分析"""
        analysis = {
            "performance_trends": {},
            "bottlenecks": [],
            "recommendations": [],
            "risk_assessment": {}
        }
        
        # 性能趋势分析
        if report_data["load_test_results"]:
            response_times = [r["avg_response_time"] for r in report_data["load_test_results"]]
            throughputs = [r["throughput"] for r in report_data["load_test_results"]]
            
            analysis["performance_trends"] = {
                "response_time_trend": "increasing" if len(response_times) > 1 and response_times[-1] > response_times[0] else "stable",
                "throughput_trend": "increasing" if len(throughputs) > 1 and throughputs[-1] > throughputs[0] else "stable",
                "response_time_variance": statistics.stdev(response_times) if len(response_times) > 1 else 0,
                "throughput_variance": statistics.stdev(throughputs) if len(throughputs) > 1 else 0
            }
        
        # 瓶颈分析
        bottlenecks = []
        
        # 从基准测试结果中识别瓶颈
        if report_data["benchmark_results"]:
            slow_operations = [r for r in report_data["benchmark_results"] if r["duration"] > 1.0]
            if slow_operations:
                bottlenecks.append({
                    "type": "slow_operations",
                    "description": f"发现 {len(slow_operations)} 个慢操作",
                    "details": [f"{op['test_name']}: {op['duration']:.3f}s" for op in slow_operations[:5]]
                })
        
        # 从负载测试结果中识别瓶颈
        if report_data["load_test_results"]:
            high_error_rate_tests = [r for r in report_data["load_test_results"] if r["error_rate"] > 0.05]
            if high_error_rate_tests:
                bottlenecks.append({
                    "type": "high_error_rate",
                    "description": f"发现 {len(high_error_rate_tests)} 个高错误率测试",
                    "details": [f"{test['test_type']}: {test['error_rate']:.2%}" for test in high_error_rate_tests]
                })
        
        analysis["bottlenecks"] = bottlenecks
        
        # 优化建议
        recommendations = []
        
        # 基于分析结果生成建议
        if analysis["performance_trends"].get("response_time_trend") == "increasing":
            recommendations.append("响应时间呈上升趋势，建议检查资源使用情况和优化算法")
        
        if bottlenecks:
            recommendations.append("发现性能瓶颈，建议优化慢操作和降低错误率")
        
        if report_data["memory_profiling"].get("leak_report", {}).get("detected_leaks"):
            recommendations.append("检测到内存泄漏，建议检查对象生命周期和资源清理")
        
        if not recommendations:
            recommendations.append("系统性能表现良好，建议继续监控和定期测试")
        
        analysis["recommendations"] = recommendations
        
        # 风险评估
        risk_level = "低"
        risk_factors = []
        
        if report_data["summary"]["benchmark_success_rate"] < 0.8:
            risk_level = "高"
            risk_factors.append("基准测试成功率过低")
        
        if report_data["summary"]["load_test_success_rate"] < 0.8:
            risk_level = "高"
            risk_factors.append("负载测试成功率过低")
        
        if report_data["summary"]["memory_usage"].get("leak_count", 0) > 5:
            risk_level = "中" if risk_level == "低" else "高"
            risk_factors.append("内存泄漏较多")
        
        analysis["risk_assessment"] = {
            "level": risk_level,
            "factors": risk_factors,
            "mitigation_actions": [
                "增加测试覆盖率",
                "优化资源使用",
                "加强监控告警",
                "定期性能回归测试"
            ]
        }
        
        return analysis
    
    def _generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """生成HTML报告"""
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 10px;
        }}
        .subtitle {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
        }}
        .summary {{
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        .metric {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            margin: 5px;
            border-radius: 5px;
            min-width: 120px;
            text-align: center;
        }}
        .metric.success {{
            background-color: #27ae60;
        }}
        .metric.warning {{
            background-color: #f39c12;
        }}
        .metric.error {{
            background-color: #e74c3c;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .success {{
            color: #27ae60;
            font-weight: bold;
        }}
        .failure {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .findings {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .findings ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .chart-placeholder {{
            background-color: #f8f9fa;
            border: 2px dashed #dee2e6;
            height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #6c757d;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
        <div class="subtitle">生成时间: {generated_at}</div>
        
        <div class="summary">
            <h2>📊 摘要</h2>
            <div class="metric success">
                <div>性能评分</div>
                <div>{performance_score:.1f}/100</div>
            </div>
            <div class="metric {benchmark_success_class}">
                <div>基准测试成功率</div>
                <div>{benchmark_success_rate:.1%}</div>
            </div>
            <div class="metric {load_test_success_class}">
                <div>负载测试成功率</div>
                <div>{load_test_success_rate:.1%}</div>
            </div>
            <div class="metric">
                <div>平均响应时间</div>
                <div>{avg_response_time:.3f}s</div>
            </div>
            <div class="metric">
                <div>平均吞吐量</div>
                <div>{avg_throughput:.1f} RPS</div>
            </div>
        </div>
        
        <div class="findings">
            <h3>🔍 关键发现</h3>
            <ul>
                {key_findings}
            </ul>
        </div>
        
        <div class="section">
            <h2>🏃‍♂️ 基准测试结果</h2>
            {benchmark_table}
        </div>
        
        <div class="section">
            <h2>⚡ 负载测试结果</h2>
            {load_test_table}
        </div>
        
        <div class="section">
            <h2>💾 内存使用情况</h2>
            {memory_info}
        </div>
        
        <div class="section">
            <h2>📈 性能趋势</h2>
            <div class="chart-placeholder">
                性能趋势图表 (需要集成图表库)
            </div>
        </div>
        
        <div class="section">
            <h2>🔧 优化建议</h2>
            <ul>
                {recommendations}
            </ul>
        </div>
        
        <div class="section">
            <h2>⚠️ 风险评估</h2>
            <p><strong>风险级别:</strong> {risk_level}</p>
            <p><strong>风险因素:</strong></p>
            <ul>
                {risk_factors}
            </ul>
        </div>
        
        <div class="footer">
            <p>报告由 {author} 生成</p>
        </div>
    </div>
</body>
</html>
        """
        
        # 准备数据
        summary = report_data["summary"]
        analysis = report_data["analysis"]
        
        # 生成表格
        benchmark_table = self._generate_benchmark_table(report_data["benchmark_results"])
        load_test_table = self._generate_load_test_table(report_data["load_test_results"])
        memory_info = self._generate_memory_info(report_data["memory_profiling"])
        
        # 样式类
        benchmark_success_class = "success" if summary["benchmark_success_rate"] > 0.9 else "warning" if summary["benchmark_success_rate"] > 0.7 else "error"
        load_test_success_class = "success" if summary["load_test_success_rate"] > 0.9 else "warning" if summary["load_test_success_rate"] > 0.7 else "error"
        
        # 格式化数据
        return html_template.format(
            title=report_data["metadata"]["title"],
            subtitle=report_data["metadata"]["subtitle"],
            generated_at=report_data["metadata"]["generated_at"],
            author=report_data["metadata"]["author"],
            performance_score=summary["performance_score"],
            benchmark_success_rate=summary["benchmark_success_rate"],
            load_test_success_rate=summary["load_test_success_rate"],
            avg_response_time=summary["avg_response_time"],
            avg_throughput=summary["avg_throughput"],
            benchmark_success_class=benchmark_success_class,
            load_test_success_class=load_test_success_class,
            key_findings="\n".join(f"<li>{finding}</li>" for finding in summary["key_findings"]),
            benchmark_table=benchmark_table,
            load_test_table=load_test_table,
            memory_info=memory_info,
            recommendations="\n".join(f"<li>{rec}</li>" for rec in analysis["recommendations"]),
            risk_level=analysis["risk_assessment"]["level"],
            risk_factors="\n".join(f"<li>{factor}</li>" for factor in analysis["risk_assessment"]["factors"])
        )
    
    def _generate_benchmark_table(self, benchmark_results: List[Dict[str, Any]]) -> str:
        """生成基准测试表格"""
        if not benchmark_results:
            return "<p>没有基准测试结果</p>"
        
        table = """
        <table>
            <tr>
                <th>测试名称</th>
                <th>插件ID</th>
                <th>持续时间 (s)</th>
                <th>内存峰值 (MB)</th>
                <th>状态</th>
            </tr>
        """
        
        for result in benchmark_results:
            status_class = "success" if result["success"] else "failure"
            status_text = "✅ 成功" if result["success"] else "❌ 失败"
            
            table += f"""
            <tr>
                <td>{result['test_name']}</td>
                <td>{result['plugin_id']}</td>
                <td>{result['duration']:.3f}</td>
                <td>{result['memory_peak']:.2f}</td>
                <td class="{status_class}">{status_text}</td>
            </tr>
            """
        
        table += "</table>"
        return table
    
    def _generate_load_test_table(self, load_test_results: List[Dict[str, Any]]) -> str:
        """生成负载测试表格"""
        if not load_test_results:
            return "<p>没有负载测试结果</p>"
        
        table = """
        <table>
            <tr>
                <th>测试类型</th>
                <th>总请求数</th>
                <th>成功请求数</th>
                <th>平均响应时间 (s)</th>
                <th>吞吐量 (RPS)</th>
                <th>错误率</th>
                <th>状态</th>
            </tr>
        """
        
        for result in load_test_results:
            status_class = "success" if result["success"] else "failure"
            status_text = "✅ 成功" if result["success"] else "❌ 失败"
            
            table += f"""
            <tr>
                <td>{result['test_type']}</td>
                <td>{result['total_requests']}</td>
                <td>{result['successful_requests']}</td>
                <td>{result['avg_response_time']:.3f}</td>
                <td>{result['throughput']:.1f}</td>
                <td>{result['error_rate']:.2%}</td>
                <td class="{status_class}">{status_text}</td>
            </tr>
            """
        
        table += "</table>"
        return table
    
    def _generate_memory_info(self, memory_profiling: Dict[str, Any]) -> str:
        """生成内存信息"""
        if not memory_profiling:
            return "<p>没有内存分析数据</p>"
        
        current_usage = memory_profiling.get("current_usage", {})
        trend = memory_profiling.get("memory_trend", {})
        leak_report = memory_profiling.get("leak_report", {})
        
        info = f"""
        <div>
            <p><strong>当前内存使用:</strong> {current_usage.get('process_memory_mb', 0):.2f} MB</p>
            <p><strong>内存趋势:</strong> {trend.get('growth_trend', 'unknown')}</p>
            <p><strong>内存泄漏:</strong> {len(leak_report.get('detected_leaks', {}))} 个</p>
        </div>
        """
        
        return info
    
    def _generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """生成Markdown报告"""
        summary = report_data["summary"]
        analysis = report_data["analysis"]
        
        md_content = f"""# {report_data['metadata']['title']}

## 摘要

- **性能评分:** {summary['performance_score']:.1f}/100
- **基准测试成功率:** {summary['benchmark_success_rate']:.1%}
- **负载测试成功率:** {summary['load_test_success_rate']:.1%}
- **平均响应时间:** {summary['avg_response_time']:.3f}s
- **平均吞吐量:** {summary['avg_throughput']:.1f} RPS

## 关键发现

"""
        
        for finding in summary["key_findings"]:
            md_content += f"- {finding}\n"
        
        md_content += "\n## 基准测试结果\n\n"
        
        if report_data["benchmark_results"]:
            md_content += "| 测试名称 | 插件ID | 持续时间(s) | 内存峰值(MB) | 状态 |\n"
            md_content += "|---------|-------|------------|-------------|------|\n"
            
            for result in report_data["benchmark_results"]:
                status = "✅ 成功" if result["success"] else "❌ 失败"
                md_content += f"| {result['test_name']} | {result['plugin_id']} | {result['duration']:.3f} | {result['memory_peak']:.2f} | {status} |\n"
        
        md_content += "\n## 负载测试结果\n\n"
        
        if report_data["load_test_results"]:
            md_content += "| 测试类型 | 总请求数 | 成功请求数 | 平均响应时间(s) | 吞吐量(RPS) | 错误率 | 状态 |\n"
            md_content += "|---------|---------|-----------|----------------|------------|-------|---------|\n"
            
            for result in report_data["load_test_results"]:
                status = "✅ 成功" if result["success"] else "❌ 失败"
                md_content += f"| {result['test_type']} | {result['total_requests']} | {result['successful_requests']} | {result['avg_response_time']:.3f} | {result['throughput']:.1f} | {result['error_rate']:.2%} | {status} |\n"
        
        md_content += "\n## 优化建议\n\n"
        
        for rec in analysis["recommendations"]:
            md_content += f"- {rec}\n"
        
        md_content += f"\n## 风险评估\n\n"
        md_content += f"**风险级别:** {analysis['risk_assessment']['level']}\n\n"
        md_content += f"**风险因素:**\n"
        
        for factor in analysis["risk_assessment"]["factors"]:
            md_content += f"- {factor}\n"
        
        md_content += f"\n---\n\n"
        md_content += f"报告生成时间: {report_data['metadata']['generated_at']}\n"
        md_content += f"报告作者: {report_data['metadata']['author']}\n"
        
        return md_content
    
    def _generate_csv_report(self, report_data: Dict[str, Any]) -> str:
        """生成CSV报告"""
        lines = []
        
        # 基准测试结果
        if report_data["benchmark_results"]:
            lines.append("基准测试结果")
            lines.append("测试名称,插件ID,持续时间(s),内存峰值(MB),内存平均(MB),状态,错误信息")
            
            for result in report_data["benchmark_results"]:
                error_msg = result.get("error", "").replace(",", ";") if result.get("error") else ""
                lines.append(f"{result['test_name']},{result['plugin_id']},{result['duration']},{result['memory_peak']},{result['memory_avg']},{result['success']},{error_msg}")
            
            lines.append("")
        
        # 负载测试结果
        if report_data["load_test_results"]:
            lines.append("负载测试结果")
            lines.append("测试类型,持续时间(s),总请求数,成功请求数,失败请求数,平均响应时间(s),吞吐量(RPS),错误率,并发用户数,状态")
            
            for result in report_data["load_test_results"]:
                lines.append(f"{result['test_type']},{result['duration']},{result['total_requests']},{result['successful_requests']},{result['failed_requests']},{result['avg_response_time']},{result['throughput']},{result['error_rate']},{result['concurrent_users']},{result['success']}")
            
            lines.append("")
        
        # 摘要统计
        lines.append("摘要统计")
        lines.append("指标,值")
        summary = report_data["summary"]
        lines.append(f"性能评分,{summary['performance_score']:.1f}")
        lines.append(f"基准测试成功率,{summary['benchmark_success_rate']:.2%}")
        lines.append(f"负载测试成功率,{summary['load_test_success_rate']:.2%}")
        lines.append(f"平均响应时间(s),{summary['avg_response_time']:.3f}")
        lines.append(f"平均吞吐量(RPS),{summary['avg_throughput']:.1f}")
        
        return "\n".join(lines)


# 使用示例
async def report_generator_example():
    """报告生成器示例"""
    from .benchmark_runner import BenchmarkRunner, BenchmarkConfig
    from .load_tester import LoadTester, LoadTestConfig
    from .metrics_collector import BenchmarkMetricsCollector
    
    # 创建测试数据
    print("=== 生成示例测试数据 ===")
    
    # 模拟基准测试结果
    benchmark_results = [
        BenchmarkResult(
            test_name="plugin_initialize_test",
            plugin_id="test_plugin_1",
            duration=0.125,
            memory_peak=15.2,
            memory_avg=12.8,
            success=True,
            timestamp=datetime.now()
        ),
        BenchmarkResult(
            test_name="plugin_health_check_test",
            plugin_id="test_plugin_1",
            duration=0.045,
            memory_peak=14.1,
            memory_avg=13.2,
            success=True,
            timestamp=datetime.now()
        )
    ]
    
    # 模拟负载测试结果
    from .load_tester import LoadTestType
    load_test_results = [
        LoadTestResult(
            test_type=LoadTestType.CONSTANT_LOAD,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration=30.0,
            total_requests=1000,
            successful_requests=985,
            failed_requests=15,
            avg_response_time=0.156,
            min_response_time=0.089,
            max_response_time=0.892,
            p95_response_time=0.234,
            p99_response_time=0.567,
            throughput=32.8,
            error_rate=0.015,
            concurrent_users=5,
            success=True
        )
    ]
    
    # 创建指标收集器
    metrics_collector = BenchmarkMetricsCollector()
    
    # 添加一些示例指标
    metrics_collector.record_gauge("system.cpu.usage", 65.4)
    metrics_collector.record_gauge("system.memory.usage", 78.2)
    metrics_collector.record_counter("plugin.requests.total", 1000)
    
    # 创建报告生成器
    config = ReportConfig(
        title="插件框架性能基准测试报告",
        subtitle="Performance Benchmark Report - Example",
        author="Mercari AI Agent Team",
        output_dir="example_reports"
    )
    
    generator = BenchmarkReportGenerator(config)
    
    # 生成报告
    print("\n=== 生成报告 ===")
    
    report_files = generator.generate_comprehensive_report(
        benchmark_results=benchmark_results,
        load_test_results=load_test_results,
        metrics_collector=metrics_collector
    )
    
    print("报告生成完成:")
    for format_type, file_path in report_files.items():
        print(f"  {format_type.upper()}: {file_path}")
    
    # 显示HTML报告路径
    html_file = report_files.get("html")
    if html_file:
        print(f"\n在浏览器中打开查看: file://{os.path.abspath(html_file)}")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(report_generator_example())