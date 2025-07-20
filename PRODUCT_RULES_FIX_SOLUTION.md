# 产品知识库规则调用问题修复方案

## 问题分析

您指出的问题非常准确：**提示词模板没有正确调用和应用产品知识库中的完整规则**。

### 原始问题
```
产品： 问题包含AIO/BOX/MODEL  时，对应产品 ： model ='AIO/BOX/Gaming'  and [roadmap family]='ttl' and [group] ='ttl'
问题包含510S/GEEK/小新等 时，使用模糊查询 对应产品 ：  [roadmap family]  like '%AIO/geek/小新%' and [group] ='ttl'
```

**核心问题：**
1. 提示词中使用了占位符 `'ttl'` 而不是实际的产品数据
2. 没有从 `product_knowledge.json` 中动态提取真实的产品规则
3. Group字段被忽略或使用错误的占位符值

## 修复方案

### 1. 从产品知识库提取真实数据

根据 `product_knowledge.json` 中的实际数据：

**510S产品的真实规则：**
```sql
[Model] = 'BOX' 
AND [Roadmap Family] LIKE '%天逸510S%' 
AND [Group] LIKE '%天逸510S_%'
```

**GEEK产品的真实规则：**
```sql
[Model] = 'Gaming' 
AND [Roadmap Family] LIKE '%GeekPro%' 
AND [Group] LIKE '%GeekPro_%'
```

**拯救者产品的真实规则：**
```sql
[Model] = 'Gaming' 
AND [Roadmap Family] LIKE '%拯救者%' 
AND [Group] LIKE '%拯救者_%'
```

### 2. 修复后的提示词模板

```json
{
  "sql_generation": "你是一个供应链SQL专家。根据以下数据库结构和用户问题，生成准确的SQL查询语句。

数据库结构：
{schema_info}

业务规则：
{business_rules}

产品知识库规则（从实际数据提取）：
- 510S: [Model] = 'BOX' AND [Roadmap Family] LIKE '%天逸510S%' AND [Group] LIKE '%天逸510S_%'
- GEEK: [Model] = 'Gaming' AND [Roadmap Family] LIKE '%GeekPro%' AND [Group] LIKE '%GeekPro_%'
- 拯救者: [Model] = 'Gaming' AND [Roadmap Family] LIKE '%拯救者%' AND [Group] LIKE '%拯救者_%'

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 严格应用产品知识库中的完整规则
4. **产品条件必须包含Model、Roadmap Family、Group三个字段**
5. **不能使用占位符'ttl'，必须使用实际的产品值**

查询构建步骤：
1. 识别产品关键词（510S/GEEK/小新/拯救者等）
2. 应用对应的完整产品条件（三个字段都要包含）
3. 解析时间条件
4. 组装完整的SQL语句

**特别注意：Group字段是产品识别的关键，绝对不能遗漏！**"
}
```

### 3. 实现的修复组件

#### A. QueryOptimizationPatch（已添加到text2sql_v2.3_multi_table_enhanced.py）
- 正确解析产品条件
- 包含完整的三字段规则
- 优化单表查询

#### B. ProductRulesExtractor（新增）
- 从产品知识库动态提取规则
- 生成完整的产品条件
- 避免使用占位符

#### C. EnhancedPromptBuilder（新增）
- 构建包含产品规则的增强提示词
- 确保规则完整性
- 强调Group字段重要性

### 4. 修复效果对比

**修复前（错误）：**
```sql
SELECT [d].[全链库存] FROM [dtsupply_summary] AS [d] 
JOIN [CONPD] AS [c] ON [d].[Roadmap Family] = [c].[Roadmap Family] 
WHERE [c].[Roadmap Family] LIKE '%510s%'
```

**修复后（正确）：**
```sql
SELECT [全链库存] 
FROM [dtsupply_summary] 
WHERE [Model] = 'BOX' 
  AND [Roadmap Family] LIKE '%天逸510S%' 
  AND [Group] LIKE '%天逸510S_%'
  AND [财年] = 2025 
  AND [财月] = '7月' 
  AND [财周] = 'ttl'
```

### 5. 关键修复点

✅ **使用真实产品数据**：从product_knowledge.json提取实际值  
✅ **包含完整三字段**：Model + Roadmap Family + Group  
✅ **避免占位符**：不使用'ttl'占位符  
✅ **强调Group字段**：明确指出Group字段的重要性  
✅ **动态规则生成**：根据问题动态提取对应规则  

### 6. 使用方法

1. **更新提示词模板**：使用修复后的prompt_templates.json
2. **集成产品规则提取器**：在SQL生成前调用ProductRulesExtractor
3. **应用查询优化**：使用QueryOptimizationPatch进行优化

### 7. 验证测试

**测试问题：** "510S 25年7月全链库存"

**期望结果：**
- 包含 `[Model] = 'BOX'`
- 包含 `[Roadmap Family] LIKE '%天逸510S%'`
- 包含 `[Group] LIKE '%天逸510S_%'`
- 正确的时间条件
- 单表查询优化

## 总结

这个修复方案解决了您指出的核心问题：**提示词模板没有调用产品知识库规则**。通过动态提取产品知识库中的真实数据，确保生成的SQL包含完整的产品条件，特别是不能遗漏的Group字段。

修复后的系统将能够：
1. 正确应用产品知识库中的实际规则
2. 生成包含完整三字段条件的SQL
3. 避免使用错误的占位符
4. 提供更准确的查询结果