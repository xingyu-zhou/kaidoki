# 贡献指南

感谢您对Mercari AI Agent项目的关注！我们欢迎所有形式的贡献，包括但不限于：

- 🐛 Bug报告
- 💡 功能建议
- 📝 文档改进
- 🔧 代码贡献
- 🧪 测试用例
- 🌐 本地化翻译

## 目录

- [开发环境设置](#开发环境设置)
- [贡献流程](#贡献流程)
- [代码规范](#代码规范)
- [测试规范](#测试规范)
- [文档规范](#文档规范)
- [提交信息规范](#提交信息规范)
- [问题报告](#问题报告)
- [功能请求](#功能请求)
- [代码审查](#代码审查)
- [社区准则](#社区准则)

## 开发环境设置

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/mercari-ai-agent.git
cd mercari-ai-agent
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
# 安装生产依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt

# 或者安装所有依赖
pip install -e .[dev]
```

### 4. 配置环境变量

```bash
# 复制环境变量模板
cp config/.env.template config/.env

# 编辑配置文件，填入必要的API密钥
vim config/.env
```

### 5. 运行测试

```bash
# 运行所有测试
python run_tests.py --all

# 运行单元测试
python run_tests.py --unit

# 运行集成测试
python run_tests.py --integration
```

### 6. 安装预提交钩子

```bash
pre-commit install
```

## 贡献流程

### 1. 创建Issue

在开始开发之前，请先创建一个Issue来描述您要解决的问题或实现的功能。

### 2. Fork项目

点击GitHub上的"Fork"按钮，创建您自己的项目副本。

### 3. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix-name
```

### 4. 进行开发

- 遵循代码规范
- 编写测试用例
- 确保所有测试通过
- 更新相关文档

### 5. 提交更改

```bash
git add .
git commit -m "feat: add new feature description"
git push origin feature/your-feature-name
```

### 6. 创建Pull Request

1. 前往GitHub页面
2. 点击"New Pull Request"
3. 填写PR模板
4. 等待代码审查

### 7. 代码审查

- 响应审查意见
- 修复发现的问题
- 更新代码直到通过审查

### 8. 合并

审查通过后，维护者会合并您的PR。

## 代码规范

### Python代码风格

我们使用以下工具来保持代码风格一致：

```bash
# 代码格式化
black src/mercari_agent tests/

# 导入排序
isort src/mercari_agent tests/

# 代码检查
flake8 src/mercari_agent tests/

# 类型检查
mypy src/mercari_agent
```

### 代码质量要求

- **可读性**: 代码应该清晰易懂
- **模块化**: 函数和类应该有明确的职责
- **文档化**: 重要的函数和类需要docstring
- **类型注解**: 使用类型提示提高代码质量
- **错误处理**: 适当的异常处理和错误消息

### 命名规范

- **变量和函数**: 使用snake_case
- **类名**: 使用PascalCase
- **常量**: 使用UPPER_CASE
- **私有成员**: 使用单下划线前缀
- **模块**: 使用小写字母和下划线

### 示例代码

```python
from typing import List, Optional
import asyncio
from dataclasses import dataclass


@dataclass
class ProductData:
    """产品数据模型"""
    product_id: str
    title: str
    price: float
    currency: str = "JPY"
    
    def get_formatted_price(self) -> str:
        """获取格式化价格"""
        return f"¥{self.price:,.0f}"


class ProductAnalyzer:
    """产品分析器"""
    
    def __init__(self, config: dict):
        self.config = config
        self._cache = {}
    
    async def analyze_product(self, product: ProductData) -> dict:
        """分析产品
        
        Args:
            product: 产品数据
            
        Returns:
            分析结果字典
            
        Raises:
            ValueError: 当产品数据无效时
        """
        if not product.product_id:
            raise ValueError("产品ID不能为空")
        
        # 实现分析逻辑
        result = await self._perform_analysis(product)
        return result
    
    async def _perform_analysis(self, product: ProductData) -> dict:
        """执行分析（私有方法）"""
        # 具体实现
        pass
```

## 测试规范

### 测试类型

- **单元测试**: 测试单个函数或方法
- **集成测试**: 测试组件间的交互
- **端到端测试**: 测试完整的用户流程

### 测试命名

```python
def test_should_return_formatted_price_when_valid_product():
    """测试：当产品有效时应返回格式化价格"""
    pass

def test_should_raise_error_when_invalid_product_id():
    """测试：当产品ID无效时应抛出错误"""
    pass
```

### 测试结构

```python
import pytest
from unittest.mock import Mock, patch
from mercari_agent.models import ProductData
from mercari_agent.analyzers import ProductAnalyzer


class TestProductAnalyzer:
    """产品分析器测试"""
    
    @pytest.fixture
    def sample_product(self):
        """样本产品数据"""
        return ProductData(
            product_id="test123",
            title="测试产品",
            price=1000.0
        )
    
    @pytest.fixture
    def analyzer(self):
        """分析器实例"""
        return ProductAnalyzer(config={"test": True})
    
    @pytest.mark.asyncio
    async def test_analyze_product_success(self, analyzer, sample_product):
        """测试产品分析成功"""
        # Given
        expected_result = {"score": 8.5}
        
        # When
        result = await analyzer.analyze_product(sample_product)
        
        # Then
        assert result["score"] > 0
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_analyze_product_invalid_id(self, analyzer):
        """测试无效产品ID"""
        # Given
        invalid_product = ProductData(
            product_id="",
            title="测试产品",
            price=1000.0
        )
        
        # When & Then
        with pytest.raises(ValueError, match="产品ID不能为空"):
            await analyzer.analyze_product(invalid_product)
```

### 测试覆盖率

- 目标覆盖率：80%以上
- 关键模块覆盖率：90%以上
- 运行覆盖率检查：`python run_tests.py --coverage`

## 文档规范

### Docstring格式

使用Google风格的docstring：

```python
def process_query(query: str, language: str = "ja") -> ParsedQuery:
    """处理用户查询
    
    Args:
        query: 用户输入的查询字符串
        language: 查询语言，默认为日语
        
    Returns:
        解析后的查询对象
        
    Raises:
        ValueError: 当查询为空或无效时
        
    Examples:
        >>> processor = QueryProcessor()
        >>> result = processor.process_query("iPhone ケース")
        >>> print(result.keywords)
        ['iPhone', 'ケース']
    """
```

### 文档更新

- 添加新功能时更新README.md
- 更新API文档
- 添加使用示例
- 更新CHANGELOG.md

## 提交信息规范

使用[Conventional Commits](https://www.conventionalcommits.org/)格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### 提交类型

- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 重构代码
- `test`: 添加测试
- `chore`: 构建过程或辅助工具变动

### 示例

```bash
git commit -m "feat(parser): add support for price range queries"
git commit -m "fix(scraper): handle timeout errors gracefully"
git commit -m "docs: update installation instructions"
```

## 问题报告

### Bug报告模板

```markdown
**Bug描述**
简要描述bug的现象

**复现步骤**
1. 执行操作A
2. 执行操作B
3. 观察到错误

**期望行为**
描述期望的正确行为

**实际行为**
描述实际发生的错误行为

**环境信息**
- 操作系统: [e.g. macOS 14.0]
- Python版本: [e.g. 3.9.0]
- 项目版本: [e.g. 1.0.0]

**额外信息**
提供任何其他相关信息
```

### 性能问题报告

```markdown
**性能问题描述**
描述性能问题的具体表现

**性能指标**
- 响应时间: [e.g. 30秒]
- 内存使用: [e.g. 2GB]
- CPU使用率: [e.g. 90%]

**测试环境**
- 数据规模: [e.g. 1000个产品]
- 并发数: [e.g. 10个请求]
- 硬件配置: [e.g. 8GB RAM, 4核CPU]

**复现步骤**
1. 准备测试数据
2. 执行性能测试
3. 观察性能指标
```

## 功能请求

### 功能请求模板

```markdown
**功能描述**
清晰描述请求的功能

**用例场景**
描述使用场景和用户需求

**建议实现**
提供可能的实现方案（可选）

**优先级**
- [ ] 紧急
- [ ] 高
- [ ] 中
- [ ] 低

**影响范围**
描述功能对现有系统的影响
```

## 代码审查

### 审查清单

**功能性**
- [ ] 功能是否按预期工作
- [ ] 是否处理了边界情况
- [ ] 错误处理是否完善

**代码质量**
- [ ] 代码是否易于理解
- [ ] 是否遵循项目规范
- [ ] 是否有适当的注释

**测试**
- [ ] 是否有足够的测试覆盖
- [ ] 测试是否有意义
- [ ] 是否测试了错误情况

**性能**
- [ ] 是否有性能问题
- [ ] 是否有内存泄漏
- [ ] 是否有不必要的计算

**安全性**
- [ ] 是否有安全漏洞
- [ ] 输入验证是否完善
- [ ] 是否泄露敏感信息

### 审查反馈

- 使用建设性的语言
- 提供具体的改进建议
- 解释问题的原因
- 承认好的代码实践

## 社区准则

### 行为准则

我们致力于创建一个开放、友好的社区环境：

- **友善**: 对所有参与者保持友善和尊重
- **包容**: 欢迎不同背景的贡献者
- **建设性**: 提供有用的反馈和建议
- **专业**: 保持专业的沟通方式

### 不当行为

以下行为是不被接受的：

- 骚扰、歧视或仇恨言论
- 恶意攻击或人身攻击
- 发布不当内容
- 违反项目规则

### 举报机制

如果您遇到不当行为，请联系：
- 邮箱: team@mercari-ai-agent.com
- 私信项目维护者

## 获得帮助

### 资源

- [项目文档](https://mercari-ai-agent.readthedocs.io/)
- [API参考](https://mercari-ai-agent.readthedocs.io/api/)
- [常见问题](https://github.com/your-org/mercari-ai-agent/wiki/FAQ)

### 沟通渠道

- [GitHub Discussions](https://github.com/your-org/mercari-ai-agent/discussions)
- [GitHub Issues](https://github.com/your-org/mercari-ai-agent/issues)
- 邮箱: team@mercari-ai-agent.com

### 开发者会议

我们定期举行在线开发者会议：
- 时间: 每月第一个周六 10:00 AM JST
- 平台: Zoom/Google Meet
- 议题: 项目进展、技术讨论、问题解答

## 许可证

通过向本项目贡献代码，您同意在[MIT许可证](LICENSE)下分发您的贡献。

## 致谢

感谢所有为本项目做出贡献的开发者！

---

**再次感谢您的贡献！** 🎉

如果您有任何问题或建议，请随时联系我们。