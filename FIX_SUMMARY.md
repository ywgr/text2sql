# Text2SQL V2.5 时间条件解析修复总结

## 问题描述

根据用户提供的截图，系统在处理 "geek25年7月全链库存" 这个问题时存在以下问题：

1. **缺少财月条件**：生成的SQL中只有 `财周 = 'ttl'`，缺少 `财月 = '7月'` 条件
2. **自然年解析错误**：系统使用了动态计算 `自然年 = (CASE WHEN MONTH(GETDATE()) >= 4 THEN YEAR(GETDATE()) ELSE YEAR(GETDATE()) - 1 END)`，而不是从问题中解析出 "25" 并设置为 `自然年 = 2025`

## 根本原因分析

1. **业务规则不完整**：原有的 `business_rules.json` 中只有 `"25 ": "2025"` 这样的简单替换规则，没有针对 "25年7月" 这种完整时间格式的规则
2. **规则优先级问题**：系统没有正确处理更具体的时间规则（如 "25年7月"）优先于通用规则（如 "25年"）
3. **时间条件处理逻辑缺陷**：`apply_business_rules` 方法没有正确识别和处理时间类型的规则

## 修复方案

### 1. 完善业务规则

在 `business_rules.json` 中添加了完整的时间规则：

```json
{
  "25年": "自然年=2025",
  "25年7月": "自然年=2025 AND 财月='7月'",
  "25年8月": "自然年=2025 AND 财月='8月'",
  // ... 其他月份
  "7月": "财月='7月'",
  "8月": "财月='8月'",
  // ... 其他月份
  "geek": "[roadmap family] like '%geek%' and [group]='ttl'"
}
```

### 2. 更新业务规则元数据

在 `business_rules_meta.json` 中添加了对应的元数据：

```json
{
  "25年": {
    "type": "时间",
    "description": "包含25年，例如：25年 --》 where 自然年=2025"
  },
  "25年7月": {
    "type": "时间", 
    "description": "包含25年7月，例如：25年7月 --》 where 自然年=2025 AND 财月='7月'"
  }
  // ... 其他规则
}
```

### 3. 优化规则处理逻辑

在 `text2sql_2_5_query.py` 的 `apply_business_rules` 方法中：

1. **按规则长度排序**：确保更具体的规则（如 "25年7月"）优先于通用规则（如 "25年"）
2. **正确识别时间规则**：根据元数据中的 `type` 字段识别时间规则
3. **优化WHERE条件处理**：将时间规则添加到WHERE条件中，而不是简单的文本替换

```python
# 按规则长度排序，确保更具体的规则优先
sorted_rules = sorted(self.business_rules.items(), key=lambda x: len(x[0]), reverse=True)

for business_term, rule_info in sorted_rules:
    if isinstance(rule_info, str):
        meta_info = business_rules_meta.get(business_term, {})
        rule_type = meta_info.get('type', '实体')
        
        if business_term in processed_question:
            if rule_type == '时间':
                where_conditions.append(rule_info)
                processed_question = processed_question.replace(business_term, '')
            else:
                processed_question = processed_question.replace(business_term, rule_info)
```

## 修复效果验证

通过测试脚本验证，修复后的系统能够正确处理：

### 测试案例 1: "geek25年7月全链库存"
- ✅ 正确解析自然年=2025
- ✅ 正确解析财月='7月'
- ✅ 正确解析产品条件 [roadmap family] like '%geek%'

### 测试案例 2: "510S25年6月全链库存"
- ✅ 正确解析自然年=2025
- ✅ 正确解析财月='6月'

### 测试案例 3: "小新25年8月全链库存"
- ✅ 正确解析自然年=2025
- ✅ 正确解析财月='8月'

## 预期SQL输出

修复后，对于问题 "geek25年7月全链库存"，系统应该生成类似以下的SQL：

```sql
SELECT
    [Roadmap Family],
    SUM([全链库存]) AS [全链库存总量]
FROM
    FF_IDSS_Dev_FF.dbo.dtsupply_summary
WHERE
    [Roadmap Family] LIKE '%geek%'
    AND [Group] = 'ttl'
    AND 自然年 = 2025
    AND 财月 = '7月'
    AND 财周 = 'ttl'
GROUP BY
    [Roadmap Family]
```

## 修复文件列表

1. `business_rules.json` - 添加完整的时间规则
2. `business_rules_meta.json` - 添加规则元数据
3. `text2sql_2_5_query.py` - 优化 `apply_business_rules` 方法

## 兼容性说明

- 修复保持了向后兼容性
- 原有的业务规则仍然有效
- 新增的规则不会影响现有功能
- 系统会自动选择最匹配的规则

## 使用建议

1. 重启系统以加载新的业务规则
2. 测试各种时间格式以确保正常工作
3. 如有需要，可以继续添加更多的时间规则
4. 建议定期备份业务规则配置文件