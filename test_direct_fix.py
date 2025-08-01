#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接修复时间条件问题
"""

import re

def fix_time_conditions(sql):
    """直接修复SQL中的时间条件"""
    print("=== 修复前的SQL ===")
    print(sql)
    
    # 修复1：替换错误的自然年条件
    sql = re.sub(
        r'自然年\s*=\s*\(CASE\s+WHEN\s+MONTH\(GETDATE\(\)\)\s*>=\s*4\s+THEN\s+YEAR\(GETDATE\(\)\)\s+ELSE\s+YEAR\(GETDATE\(\)\)\s*-\s*1\s+END\)',
        '自然年 = 2025',
        sql,
        flags=re.IGNORECASE
    )
    
    # 修复2：确保有财月条件
    if '财月' not in sql and '7月' in sql:
        # 在WHERE子句中添加财月条件
        where_match = re.search(r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            if '财月 =' not in where_clause and '财月=' not in where_clause:
                where_clause += " AND 财月 = '7月'"
                sql = sql.replace(where_match.group(1), where_clause)
    
    # 修复3：确保财周条件存在
    if '财周' not in sql:
        where_match = re.search(r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            if '财周 =' not in where_clause and '财周=' not in where_clause:
                where_clause += " AND 财周 = 'ttl'"
                sql = sql.replace(where_match.group(1), where_clause)
    
    print("\n=== 修复后的SQL ===")
    print(sql)
    
    return sql

def test_fix():
    """测试修复功能"""
    # 错误的SQL（用户提供的）
    wrong_sql = """SELECT 
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
    [Roadmap Family]"""
    
    print("开始修复时间条件...")
    fixed_sql = fix_time_conditions(wrong_sql)
    
    # 验证修复结果
    print("\n=== 验证修复结果 ===")
    
    checks = [
        ("自然年 = 2025", "自然年条件"),
        ("财月 = '7月'", "财月条件"),
        ("财周 = 'ttl'", "财周条件"),
        ("[Roadmap Family] LIKE '%geek%'", "产品条件"),
        ("[Group] = 'ttl'", "分组条件")
    ]
    
    for check_text, description in checks:
        if check_text in fixed_sql:
            print(f"✅ {description}: {check_text}")
        else:
            print(f"❌ {description}: {check_text}")

if __name__ == "__main__":
    test_fix()