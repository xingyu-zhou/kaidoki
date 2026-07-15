#!/usr/bin/env python3
"""
Mercari AI Agent 安装脚本

该脚本用于安装Mercari AI Agent包。
支持pip install和开发安装。

Author: Mercari AI Agent Team
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# 确保Python版本兼容
if sys.version_info < (3, 8):
    sys.exit("Python 3.8 or higher is required")

# 项目根目录
ROOT_DIR = Path(__file__).parent.absolute()

# 读取版本信息
def get_version():
    """获取版本信息"""
    version_file = ROOT_DIR / "src" / "mercari_agent" / "__init__.py"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    version = line.split('=')[1].strip().strip('"\'')
                    return version
    return "1.0.0"

# 读取README
def get_long_description():
    """获取长描述"""
    readme_file = ROOT_DIR / "README.md"
    if readme_file.exists():
        with open(readme_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# 读取依赖
def get_requirements(filename):
    """读取依赖文件"""
    requirements_file = ROOT_DIR / filename
    if requirements_file.exists():
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-r'):
                    requirements.append(line)
            return requirements
    return []

# 获取包数据
def get_package_data():
    """获取包数据文件"""
    package_data = {
        'mercari_agent': [
            'config/*.yaml',
            'config/*.yml',
            'config/*.json',
            'data/*.json',
            'data/*.yaml',
            'templates/*.html',
            'templates/*.txt',
            'static/*',
        ]
    }
    return package_data

# 获取数据文件
def get_data_files():
    """获取数据文件"""
    data_files = [
        ('config', ['config/development.yaml', 'config/production.yaml']),
        ('scripts', ['scripts/deploy.sh']),
        ('docs', ['README.md']),
    ]
    return data_files

# 获取入口点
def get_entry_points():
    """获取入口点"""
    entry_points = {
        'console_scripts': [
            'mercari-agent=mercari_agent.main:main',
            'mercari-ai-agent=mercari_agent.main:main',
        ],
    }
    return entry_points

# 获取分类器
def get_classifiers():
    """获取分类器"""
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Office/Business :: Financial :: Shopping',
        'Framework :: AsyncIO',
        'Framework :: FastAPI',
    ]
    return classifiers

# 主要依赖
install_requires = get_requirements('requirements.txt')

# 额外依赖
extras_require = {
    'dev': get_requirements('requirements-dev.txt'),
    'test': [
        'pytest>=7.0.0',
        'pytest-asyncio>=0.21.0',
        'pytest-mock>=3.10.0',
        'pytest-cov>=4.0.0',
        'coverage>=7.0.0',
    ],
    'docs': [
        'sphinx>=7.0.0',
        'sphinx-rtd-theme>=1.3.0',
        'myst-parser>=2.0.0',
    ],
    'performance': [
        'line-profiler>=4.0.0',
        'memory-profiler>=0.60.0',
        'py-spy>=0.3.0',
    ],
    'monitoring': [
        'prometheus-client>=0.19.0',
        'sentry-sdk>=1.38.0',
        'grafana-api>=1.0.0',
    ],
    'all': [],
}

# 合并所有额外依赖
extras_require['all'] = list(set(
    sum((deps for key, deps in extras_require.items() if key != 'all'), [])
))

# 安装配置
setup(
    # 基本信息
    name='mercari-ai-agent',
    version=get_version(),
    description='Mercari日本智能购物AI代理系统',
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    
    # 作者信息
    author='Mercari AI Agent Team',
    author_email='team@mercari-ai-agent.com',
    maintainer='Mercari AI Agent Team',
    maintainer_email='team@mercari-ai-agent.com',
    
    # 项目信息
    url='https://github.com/your-org/mercari-ai-agent',
    project_urls={
        'Documentation': 'https://mercari-ai-agent.readthedocs.io/',
        'Source': 'https://github.com/your-org/mercari-ai-agent',
        'Tracker': 'https://github.com/your-org/mercari-ai-agent/issues',
        'Changelog': 'https://github.com/your-org/mercari-ai-agent/blob/main/CHANGELOG.md',
    },
    
    # 许可证
    license='MIT',
    
    # 包信息
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    package_data=get_package_data(),
    data_files=get_data_files(),
    include_package_data=True,
    
    # 依赖
    python_requires='>=3.8',
    install_requires=install_requires,
    extras_require=extras_require,
    
    # 入口点
    entry_points=get_entry_points(),
    
    # 分类器
    classifiers=get_classifiers(),
    
    # 关键词
    keywords=[
        'ai', 'agent', 'mercari', 'shopping', 'recommendation',
        'scraping', 'nlp', 'japanese', 'e-commerce', 'analysis'
    ],
    
    # 平台
    platforms=['any'],
    
    # Zip安全
    zip_safe=False,
    
    # 测试
    test_suite='tests',
    tests_require=extras_require['test'],
    
    # 选项
    options={
        'build_scripts': {
            'executable': '/usr/bin/python3',
        },
        'egg_info': {
            'tag_build': '',
            'tag_date': False,
        },
        'bdist_wheel': {
            'universal': False,
        },
    },
    
    # 命令类
    cmdclass={},
    
    # 扩展
    ext_modules=[],
    
    # 脚本
    scripts=[],
)