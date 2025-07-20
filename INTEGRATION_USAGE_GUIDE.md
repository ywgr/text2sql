# 通用产品匹配集成使用指南

## ✅ 集成状态确认

已成功集成到 `text2sql_v2.3_enhanced.py` 文件中：

- ✅ **UniversalProductMatcher 类** (第37-115行)
- ✅ **generate_sql_with_universal_product_matching 函数** (第4823-4908行)
- ✅ **test_universal_product_matching 函数** (第4911-4942行)
- ✅ **业务规则已更新** 支持所有产品类型

## 🚀 使用方法

### 1. 直接调用集成函数

```python
from text2sql_v2_3_enhanced import generate_sql_with_universal_product_matching

# 测试510S
sql1 = generate_sql_with_universal_product_matching("510S 25年7月全链库存")
print(sql1)
# 期望输出: SELECT [全链库存] FROM [dtsupply_summary] WHERE [Roadmap Family] LIKE '%510S%' AND [Group] = 'ttl' AND [财年] = 2025 AND [财月] = '7月' AND [财周] = 'ttl'

# 测试geek
sql2 = generate_sql_with_universal_product_matching("geek产品今年的SellOut数据")
print(sql2)
# 期望输出: SELECT [SellOut] FROM [dtsupply_summary] WHERE [Roadmap Family] LIKE '%Geek%' AND [Group] = 'ttl' AND [财年] = 2025

# 测试小新
sql3 = generate_sql_with_universal_product_matching("小新系列2025年周转情况")
print(sql3)
# 期望输出: SELECT [全链库存DOI] FROM [dtsupply_summary] WHERE [Roadmap Family] LIKE '%小新%' AND [Group] = 'ttl' AND [财年] = 2025
```

### 2. 运行内置测试

```python
# 方法1: 命令行测试
python text2sql_v2.3_enhanced.py test

# 方法2: 代码中调用
from text2sql_v2_3_enhanced import test_universal_product_matching
test_universal_product_matching()
```

### 3. 在现有系统中使用

如果您有现有的Text2SQL系统，可以这样集成：

```python
def enhanced_sql_generation(question: str) -> str:
    """增强的SQL生成，支持通用产品匹配"""
    try:
        # 首先尝试通用产品匹配
        sql = generate_sql_with_universal_product_matching(question)
        
        # 如果生成成功且不是默认查询，返回结果
        if sql and "WHERE 1=1" not in sql:
            return sql
        
        # 否则回退到原有逻辑
        return your_original_sql_generation(question)
        
    except Exception as e:
        print(f"通用产品匹配失败，回退到原有逻辑: {e}")
        return your_original_sql_generation(question)
```

## 🎯 支持的产品类型

现在系统支持以下所有产品：

| 关键词 | 匹配模式 | 示例查询 |
|--------|----------|----------|
| 510S | `LIKE '%510S%'` | "510S 25年7月全链库存" |
| geek | `LIKE '%Geek%'` | "geek产品今年的SellOut数据" |
| 小新 | `LIKE '%小新%'` | "小新系列2025年周转情况" |
| 拯救者 | `LIKE '%拯救者%'` | "拯救者全链库存" |
| AIO | `LIKE '%AIO%'` | "AIO产品库存" |

## 📊 核心特性

### 1. **通用产品层级理解**
```
MODEL → [ROADMAP FAMILY] → [GROUP]
```
- 在 ROADMAP FAMILY 层级进行模糊匹配
- GROUP 使用 'ttl' 通配符

### 2. **智能单表查询**
- 自动检测是否所有字段都在 `dtsupply_summary` 表中
- 优先使用单表查询，避免不必要的JOIN

### 3. **正确的时间格式**
- `25年` → `[财年] = 2025`
- `7月` → `[财月] = '7月'` (不是 '20257')

### 4. **字段映射**
- `全链库存` → `[全链库存]`
- `周转/DOI` → `[全链库存DOI]`
- `SellOut` → `[SellOut]`
- `SellIn` → `[SellIn]`

## 🔧 故障排除

### 问题1: 导入错误
```python
# 如果遇到导入问题，检查文件名
import text2sql_v2_3_enhanced  # 注意下划线
# 或者
from text2sql_v2_3_enhanced import generate_sql_with_universal_product_matching
```

### 问题2: 产品未识别
如果某个产品没有被识别，检查：
1. 产品关键词是否在 `UniversalProductMatcher.product_patterns` 中
2. `product_knowledge.json` 中是否有对应的产品数据

### 问题3: SQL格式问题
生成的SQL应该包含：
- `SELECT [字段] FROM [dtsupply_summary]`
- `WHERE [Roadmap Family] LIKE '%产品%' AND [Group] = 'ttl'`
- 正确的时间条件

## 📈 测试验证

### 快速验证脚本
```python
def quick_test():
    questions = [
        "510S 25年7月全链库存",
        "geek产品SellOut",
        "小新库存"
    ]
    
    for q in questions:
        sql = generate_sql_with_universal_product_matching(q)
        print(f"Q: {q}")
        print(f"SQL: {sql}")
        print("-" * 50)

quick_test()
```

## 🎉 成功标志

如果集成成功，您应该看到：
- ✅ geek查询不再报错
- ✅ 所有产品使用相同的逻辑
- ✅ 生成正确的单表SQL
- ✅ 时间格式正确

## 📞 支持

如果遇到问题：
1. 检查 `business_rules.json` 是否包含所有产品规则
2. 确认 `product_knowledge.json` 文件可访问
3. 运行内置测试验证功能