# Text2SQL集成系统 - 使用说明

## 🎯 系统特性

### ✅ 已修复的问题
1. **正确的产品层级理解**: MODEL → [ROADMAP FAMILY] → [GROUP]
2. **单表查询优化**: 避免不必要的多表JOIN
3. **时间格式修复**: 25年7月 → 财年=2025, 财月='7月' (不是'20257')
4. **SQL评价和缓存**: 好的SQL自动进入缓存，坏的不缓存
5. **用户反馈机制**: 支持手动纠正SQL评价

### 🔧 核心修复

**产品查询规则**:
- ✅ **正确**: `[Roadmap Family] LIKE '%510S%' AND [Group] = 'ttl'`
- ❌ **错误**: `[Group] LIKE '%天逸510S_%'` (过于具体)

**时间格式**:
- ✅ **正确**: `[财月] = '7月'`
- ❌ **错误**: `[财月] = '20257'`

**查询优化**:
- ✅ **单表优先**: 供应链数据优先使用 `dtsupply_summary` 单表
- ❌ **避免**: 不必要的多表JOIN

## 🚀 使用方法

### 1. 命令行测试
```bash
python run_integrated_system.py test
```

### 2. Streamlit界面
```bash
streamlit run run_integrated_system.py
```

### 3. 直接调用API
```python
from text2sql_integrated_system import IntegratedText2SQLSystem

# 初始化系统
system = IntegratedText2SQLSystem()

# 生成SQL
result = system.generate_sql("510S 25年7月全链库存")

print(f"SQL: {result.sql}")
print(f"评分: {result.score}")
print(f"是否正确: {result.is_correct}")
```

## 📊 系统架构

### 核心组件
1. **IntegratedText2SQLSystem**: 主系统类
2. **SQL生成器**: 支持单表/多表智能选择
3. **评价系统**: 多维度SQL质量评估
4. **缓存系统**: SQLite数据库存储
5. **用户反馈**: 手动纠正机制

### 数据流程
```
用户问题 → 缓存检查 → SQL生成 → 质量评价 → 缓存决策 → 返回结果
                ↓
            用户反馈 → 更新评价 → 重新缓存
```

## 🎯 测试示例

### 输入问题
```
"510S 25年7月全链库存"
```

### 期望输出
```sql
SELECT [全链库存] FROM [dtsupply_summary] 
WHERE [Roadmap Family] LIKE '%510S%' 
AND [Group] = 'ttl' 
AND [财年] = 2025 
AND [财月] = '7月' 
AND [财周] = 'ttl'
```

### 评价结果
- **评分**: 95分
- **是否正确**: True
- **是否缓存**: True
- **问题**: 无
- **建议**: 无

## 📈 系统统计

系统会自动跟踪：
- 总评价次数
- 平均评分
- 准确率
- 缓存大小
- 缓存命中率

## 🔧 配置文件

### business_rules.json
```json
{
  "510S": "where [roadmap family] LIKE '%510S%' and [group]='ttl'"
}
```

### prompt_templates.json
更新了提示词，强调：
- 单表查询优先
- 正确的产品层级理解
- 时间格式规范

## 🎯 关键理解

### 产品层级
```
MODEL (如: BOX, Gaming)
  ↓
[ROADMAP FAMILY] (如: 天逸510S, GeekPro)
  ↓  
[GROUP] (如: 天逸510S_I5, 天逸510S_I7)
```

### 查询策略
- **产品系列查询**: 在 ROADMAP FAMILY 层级匹配
- **通配符使用**: GROUP = 'ttl' 表示该系列下所有group
- **模糊匹配**: LIKE '%510S%' 匹配所有包含510S的产品

## 🚨 常见问题

### Q: 为什么使用 'ttl' 而不是具体的group值？
A: 'ttl' 是通配符，表示查询该产品系列下的所有group，这符合业务查询的常见需求。

### Q: 什么时候使用单表查询？
A: 当所有需要的字段都在 dtsupply_summary 表中，且查询包含产品信息时。

### Q: 如何提高SQL评分？
A: 确保时间格式正确、使用单表查询、应用正确的产品规则。

## 📝 更新日志

### v1.0 (当前版本)
- ✅ 修复产品层级理解
- ✅ 实现单表查询优化  
- ✅ 修复时间格式问题
- ✅ 添加SQL评价和缓存系统
- ✅ 支持用户反馈机制
- ✅ 集成Streamlit界面

## 🔮 后续计划

1. 添加更多产品规则 (GEEK, 小新等)
2. 支持更复杂的多表查询场景
3. 增强自然语言理解能力
4. 添加SQL执行和结果验证
5. 支持查询历史和模板管理