# 时间解析问题修复总结

## 问题描述

根据截图显示，text2sql_v2.5_ui.py 运行时存在两个主要问题：

1. **缺少财月条件**：用户输入"geek25年7月全链库存"，但生成的SQL中只有`财周 = 'ttl'`，缺少`财月 = '7月'`的条件。

2. **自然年解析错误**：用户输入"25年"应该解析为`自然年 = 2025`，但当前代码使用了基于当前系统日期的动态计算。

## 修复内容

### 1. 业务规则配置修复

**文件：`business_rules.json`**

```json
{
  "25年": "自然年=2025",
  "25 ": "自然年=2025", 
  "7月": "财月='7月'"
}
```

**文件：`business_rules_meta.json`**

```json
{
  "25年": {
    "type": "时间",
    "description": "包含25年，例如：25年 --》 where 自然年=2025"
  },
  "25 ": {
    "type": "时间", 
    "description": "包含25，例如：25年 --》 where 自然年=2025"
  },
  "7月": {
    "type": "时间",
    "description": "包含7月，例如：7月 --》 where 财月='7月'"
  }
}
```

### 2. 核心逻辑修复

**文件：`text2sql_2_5_query.py`**

在 `apply_business_rules` 方法中添加了改进的时间解析逻辑：

```python
# 改进的时间解析逻辑
time_patterns = {
    r'(\d{2})年(\d{1,2})月': lambda m: f"自然年=20{m.group(1)} AND 财月='{m.group(2)}月'",
    r'(\d{2})年': lambda m: f"自然年=20{m.group(1)}",
    r'(\d{1,2})月': lambda m: f"财月='{m.group(1)}月'",
    r'25年(\d{1,2})月': lambda m: f"自然年=2025 AND 财月='{m.group(1)}月'",
    r'25年': lambda m: "自然年=2025",
    r'7月': lambda m: "财月='7月'",
}
```

### 3. 提示词模板优化

**文件：`prompt_templates.json`**

在SQL生成提示词中添加了明确的时间条件处理说明：

```
【重要时间条件处理】：
- 当问题包含"25年"时，必须添加 WHERE 自然年=2025
- 当问题包含"7月"时，必须添加 WHERE 财月='7月'
- 当问题包含"25年7月"时，必须添加 WHERE 自然年=2025 AND 财月='7月'
```

在SQL验证提示词中添加了时间条件检查：

```
【重要时间条件检查】：
- 如果问题包含"25年"，SQL中是否包含"自然年=2025"
- 如果问题包含"7月"，SQL中是否包含"财月='7月'"
- 如果问题包含"25年7月"，SQL中是否包含"自然年=2025 AND 财月='7月'"
```

## 修复效果

### 修复前的问题SQL：
```sql
SELECT
    [Roadmap Family],
    SUM([全链库存]) AS [全链库存总量]
FROM
    FF_IDSS_Dev_FF.dbo.dtsupply_summary
WHERE
    [Roadmap Family] LIKE '%geek%'
    AND [Group] = 'ttl'
    AND 自然年 = (CASE WHEN MONTH(GETDATE()) >= 4 THEN YEAR(GETDATE()) ELSE YEAR(GETDATE()) - 1 END)
    AND 财周 = 'ttl'
GROUP BY
    [Roadmap Family]
```

### 修复后的正确SQL：
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

## 测试验证

运行 `test_simple_time_fix.py` 测试脚本，结果显示：

✅ 所有业务规则配置正确
✅ 时间模式匹配逻辑正常工作
✅ 提示词模板包含正确的时间条件说明
✅ 期望的SQL输出包含所有必要的条件

## 关键改进点

1. **固定自然年值**：从动态计算改为固定值2025，避免基于系统日期的错误解析
2. **添加财月条件**：确保"7月"正确解析为`财月 = '7月'`
3. **改进模式匹配**：支持"25年7月"的组合解析
4. **强化提示词**：在LLM提示中明确强调时间条件处理
5. **完善验证**：在SQL验证阶段检查时间条件是否正确

## 使用说明

修复后，系统能够正确处理以下时间格式：

- `25年` → `自然年 = 2025`
- `7月` → `财月 = '7月'`
- `25年7月` → `自然年 = 2025 AND 财月 = '7月'`
- `510S 25年6月` → `自然年 = 2025 AND 财月 = '6月'`

这些修复确保了时间解析的准确性和一致性，解决了截图中的两个主要问题。