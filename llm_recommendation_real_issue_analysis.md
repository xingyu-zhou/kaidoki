# LLM推荐系统真实问题分析报告

## 问题重新定义

既然LLM服务在QueryParser中成功调用，说明LLM基础设施是正常的。真正的问题可能出现在以下几个环节：

## 🔍 真实问题定位

### 1. 模拟数据与查询无关问题

**问题核心**: [`infrastructure/scraping/scraper_service.py:91-109`](mercari_ai_agent_refactored/src/mercari_agent/infrastructure/scraping/scraper_service.py#91-109)

```python
def _generate_mock_products(self) -> List[Dict[str, Any]]:
    """生成模拟产品数据"""
    products = []
    for i in range(10):
        products.append({
            "id": f"m{random.randint(10000000, 99999999)}",
            "title": f"商品示例 {i+1}",  # ❌ 问题：固定模板，完全忽略用户查询
            "price": random.randint(500, 50000),  # ❌ 问题：随机价格，不考虑用户预算
            "condition": random.choice(["新品・未使用", "未使用に近い", "目立った傷や汚れなし"]),
            "seller_name": f"seller_{i+1}",
            # ...
        })
```

**现象**: 无论用户查询什么（iPhone 15 Pro Max、游戏机、汽车等），系统总是返回"商品示例 1"、"商品示例 2"这样的通用商品。

### 2. LLM推荐被无效数据影响

即使LLM服务正常工作，但是当输入数据与查询完全无关时：

```python
# 用户查询：iPhone 15 Pro Max 10万円以下
query.original_query = "iPhone 15 Pro Max 10万円以下"

# 但模拟数据返回的是：
products = [
    {"title": "商品示例 1", "price": 15000},
    {"title": "商品示例 2", "price": 35000},
    {"title": "商品示例 3", "price": 8000},
    # ...
]

# LLM收到的提示词就变成了：
"""
用户查询: iPhone 15 Pro Max 10万円以下
商品列表: [
    {"title": "商品示例 1", "price": 15000},
    {"title": "商品示例 2", "price": 35000},
    ...
]
请进行推荐排序...
"""
```

**结果**: LLM发现所有商品都与iPhone无关，可能：
1. 返回空的推荐列表
2. 返回JSON格式错误的响应
3. 抛出异常

这些情况都会触发回退逻辑，最终使用简单的价格排序。

### 3. 可能的代码执行路径分析

让我们追踪可能的执行路径：

```python
# RecommendationService.recommend()
async def recommend(self, products, query, limit=10, strategy="balanced"):
    try:
        if self.llm_service and products:  # ✅ 两个条件都满足
            # 构建产品数据
            product_list = []
            for i, product in enumerate(products[:20]):
                product_info = {
                    "index": i,
                    "title": product.title,  # "商品示例 1", "商品示例 2", ...
                    "price": product.price,  # 随机价格：15000, 35000, ...
                    "condition": product.condition,
                    "seller_name": product.seller_name
                }
                product_list.append(product_info)
            
            # 调用LLM - 这里可能成功，也可能失败
            llm_response = await self.llm_service.generate_response(llm_prompt)
            
            # JSON解析 - 这里很可能失败，因为LLM可能返回错误格式
            try:
                recommendation_data = json.loads(llm_response.content)
                recommended_indices = recommendation_data.get('recommended_indices', [])
                # ...
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"LLM推荐响应解析失败，使用备用逻辑: {e}")
                # ❌ 问题：回退到这里
                recommendations = await self._fallback_recommend(products, query, limit, strategy)
        
        else:
            # 或者可能直接到这里
            recommendations = await self._fallback_recommend(products, query, limit, strategy)
            
    except Exception as e:
        # 或者任何异常都会到这里
        recommendations = await self._fallback_recommend(products, query, limit, strategy)
```

### 4. 备用推荐算法的问题

[`application/services/recommendation_service.py:135-165`](mercari_ai_agent_refactored/src/mercari_agent/application/services/recommendation_service.py#135-165)

```python
async def _fallback_recommend(self, products, query, limit, strategy):
    """备用推荐逻辑"""
    filtered_products = []
    for product in products:
        # 价格过滤
        if query.price_min and product.price and product.price < query.price_min:
            continue
        if query.price_max and product.price and product.price > query.price_max:
            continue
        
        # 关键词匹配
        if query.keywords:
            title_lower = product.title.lower()  # "商品示例 1"
            keyword_match = any(keyword.lower() in title_lower for keyword in query.keywords)
            if not keyword_match:
                logger.debug(f"产品 '{product.title}' 没有关键词匹配，但通过价格过滤，仍然包含")
            filtered_products.append(product)  # ❌ 问题：即使不匹配也加入了
        else:
            filtered_products.append(product)
    
    # 简单排序：按价格升序
    filtered_products.sort(key=lambda p: p.price or 0)
    return filtered_products[:limit]
```

**问题**: 备用算法即使发现关键词不匹配（iPhone vs "商品示例 1"），但依然把商品加入了推荐列表。

---

## 🛠️ 核心解决方案

### 方案1: 创建查询相关的智能模拟数据生成器

```python
class QueryAwareMockDataGenerator:
    def __init__(self):
        self.product_databases = {
            # iPhone相关
            "iphone": [
                {
                    "title_template": "iPhone 15 Pro Max {storage} {color}",
                    "storage_options": ["128GB", "256GB", "512GB", "1TB"],
                    "color_options": ["スペースブラック", "ディープパープル", "ゴールド", "シルバー"],
                    "price_range": (120000, 200000),
                    "conditions": ["新品・未使用", "未使用に近い", "目立った傷や汚れなし"],
                    "category": "スマートフォン"
                },
                {
                    "title_template": "iPhone 14 Pro {storage} {color}",
                    "storage_options": ["128GB", "256GB", "512GB", "1TB"],
                    "color_options": ["スペースブラック", "ディープパープル", "ゴールド", "シルバー"],
                    "price_range": (80000, 140000),
                    "conditions": ["新品・未使用", "未使用に近い", "目立った傷や汚れなし"],
                    "category": "スマートフォン"
                }
            ],
            # 游戏机相关
            "ゲーム機": [
                {
                    "title_template": "Nintendo Switch (有機ELモデル) {color}",
                    "color_options": ["ホワイト", "ネオンブルー・ネオンレッド"],
                    "price_range": (35000, 45000),
                    "conditions": ["新品・未使用", "未使用に近い", "目立った傷や汚れなし"],
                    "category": "Nintendo Switch"
                },
                {
                    "title_template": "PlayStation 5 {edition}",
                    "edition_options": ["通常版", "デジタル・エディション"],
                    "price_range": (50000, 80000),
                    "conditions": ["新品・未使用", "未使用に近い"],
                    "category": "プレイステーション5"
                }
            ]
        }
    
    def generate_contextual_products(self, query: QueryEntity) -> List[Dict[str, Any]]:
        """根据查询上下文生成相关商品"""
        query_text = query.original_query.lower()
        
        # 识别查询类型
        product_type = self._identify_product_type(query_text)
        templates = self.product_databases.get(product_type, self._get_generic_templates())
        
        products = []
        for i, template in enumerate(templates[:10]):  # 最多10个商品
            product = self._generate_from_template(template, i, query)
            products.append(product)
        
        return products
    
    def _identify_product_type(self, query_text: str) -> str:
        """识别商品类型"""
        if any(keyword in query_text for keyword in ["iphone", "アイフォン", "スマホ"]):
            return "iphone"
        elif any(keyword in query_text for keyword in ["ゲーム", "switch", "playstation", "ps5"]):
            return "ゲーム機"
        else:
            return "generic"
    
    def _generate_from_template(self, template: Dict, index: int, query: QueryEntity) -> Dict:
        """从模板生成具体商品"""
        import random
        
        # 生成标题
        title = template["title_template"]
        if "{storage}" in title and "storage_options" in template:
            storage = random.choice(template["storage_options"])
            title = title.replace("{storage}", storage)
        if "{color}" in title and "color_options" in template:
            color = random.choice(template["color_options"])
            title = title.replace("{color}", color)
        if "{edition}" in title and "edition_options" in template:
            edition = random.choice(template["edition_options"])
            title = title.replace("{edition}", edition)
        
        # 生成价格（考虑查询的价格范围）
        min_price, max_price = template["price_range"]
        if query.price_max and query.price_max < max_price:
            max_price = query.price_max
        if query.price_min and query.price_min > min_price:
            min_price = query.price_min
            
        price = random.randint(min_price, max_price)
        
        return {
            "id": f"ctx_{random.randint(10000000, 99999999)}",
            "title": f"{title}【{random.choice(['正規品', '美品', '完動品'])}】",
            "price": price,
            "condition": random.choice(template["conditions"]),
            "seller_name": random.choice([
                "Apple正規代理店", "スマホ専門店", "ゲーム機専門店", 
                f"優良出品者{index+1}", "認定中古店"
            ]),
            "seller_rating": round(random.uniform(4.2, 4.9), 1),
            "category": template["category"],
            "description": f"【{query.original_query}】に関連する高品質な商品です。",
            "image_url": f"https://static.mercdn.net/item/detail/orig/photos/ctx{random.randint(10000000, 99999999)}_1.jpg",
            "url": f"https://jp.mercari.com/item/ctx{random.randint(10000000, 99999999)}"
        }
    
    def _get_generic_templates(self) -> List[Dict]:
        """通用商品模板"""
        return [{
            "title_template": "おすすめ商品 {index}",
            "price_range": (1000, 50000),
            "conditions": ["新品・未使用", "未使用に近い", "目立った傷や汚れなし"],
            "category": "その他"
        }]
```

### 方案2: 修改scraper_service.py使用智能生成器

```python
# 在 MercariDataParser 类中修改
def parse_search_results(self, html_content: str, query: QueryEntity = None) -> List[Dict[str, Any]]:
    """解析搜索结果页面"""
    try:
        # 使用查询相关的智能模拟数据生成器
        if query:
            generator = QueryAwareMockDataGenerator()
            return generator.generate_contextual_products(query)
        else:
            # 回退到原有逻辑
            return self._generate_mock_products()
    except Exception as e:
        logger.error(f"解析搜索结果失败: {e}")
        return []
```

### 方案3: 增强LLM推荐的错误处理

```python
# 在RecommendationService中增加更详细的调试信息
async def recommend(self, products, query, limit=10, strategy="balanced"):
    logger.info(f"🔍 推荐系统调试信息:")
    logger.info(f"   LLM服务状态: {self.llm_service is not None}")
    logger.info(f"   商品数量: {len(products) if products else 0}")
    logger.info(f"   查询内容: {query.original_query}")
    
    if products:
        logger.info(f"   商品样例: {[p.title for p in products[:3]]}")
    
    try:
        if self.llm_service and products:
            logger.info("🚀 开始LLM智能推荐...")
            
            # 调用LLM
            llm_response = await self.llm_service.generate_response(llm_prompt)
            logger.info(f"📝 LLM原始响应: {llm_response.content[:200]}...")
            
            try:
                recommendation_data = json.loads(llm_response.content)
                logger.info(f"✅ LLM推荐解析成功: {recommendation_data}")
                # 处理推荐结果...
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ LLM响应JSON解析失败: {e}")
                logger.error(f"   原始响应: {llm_response.content}")
                recommendations = await self._fallback_recommend(products, query, limit, strategy)
        else:
            logger.warning(f"⚠️ 使用备用推荐算法")
            recommendations = await self._fallback_recommend(products, query, limit, strategy)
    
    except Exception as e:
        logger.error(f"❌ LLM推荐异常: {e}", exc_info=True)
        recommendations = await self._fallback_recommend(products, query, limit, strategy)
    
    logger.info(f"📊 推荐结果: {len(recommendations)}个商品")
    if recommendations:
        logger.info(f"   推荐商品: {[r.title for r in recommendations[:3]]}")
    
    return RecommendationResult(...)
```

---

## 🎯 立即可执行的解决方案

### 快速修复步骤：

1. **修改模拟数据生成器**，让其根据查询生成相关商品
2. **增加详细日志**，确认LLM调用的每个环节
3. **改进备用推荐算法**，确保关键词不匹配时过滤商品
4. **测试完整流程**，验证LLM推荐是否正常工作

这样可以确保：
- 输入数据与查询相关
- LLM收到有意义的推荐请求
- 即使回退到备用算法，也能返回相关商品
- 整个过程可追踪和调试

### 预期效果：

- 用户查询"iPhone 15 Pro Max 10万円以下"
- 系统生成iPhone相关的模拟商品
- LLM基于相关商品进行智能推荐
- 返回与查询匹配的推荐结果