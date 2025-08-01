#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的本地校验功能
验证字段-表从属关系的判断是否正确
"""

import json
import os
from text2sql_2_5_query import Text2SQLQueryEngine, VannaWrapper, DatabaseManager

def load_json(path):
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件 {path} 不存在")
        return {}
    except Exception as e:
        print(f"加载 {path} 失败: {e}")
        return {}

def test_local_validation_fix():
    """测试修复后的本地校验功能"""
    print("=== 测试修复后的本地校验功能 ===")
    
    # 1. 加载知识库
    print("\n1. 加载知识库...")
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json')
    
    # 2. 初始化系统
    print("\n2. 初始化系统...")
    vanna = VannaWrapper()
    db_manager = DatabaseManager()
    
    system = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=relationships,
        business_rules=business_rules,
        product_knowledge=product_knowledge,
        historical_qa=historical_qa,
        vanna=vanna,
        db_manager=db_manager,
        prompt_templates={}
    )
    
    # 3. 测试SQL（模拟截图中的情况）
    print("\n3. 测试SQL...")
    test_sql = """
    SELECT SUM(QTY) AS '消台25年7月供应总量'
    FROM FF_IDSS_Data_CON_BAK.dbo.ConDT_Commit
    WHERE [自然年] = 2025 AND [财月] = '7月' AND [Model] = 'ttl'
    """
    
    print(f"测试SQL:\n{test_sql}")
    
    # 4. 测试字段验证
    print("\n4. 测试字段验证...")
    field_validation = system.validate_sql_fields(test_sql)
    print(f"字段验证结果:")
    print(f"  有效字段: {field_validation['valid_fields']}")
    print(f"  缺失字段: {field_validation['missing_fields']}")
    print(f"  全部有效: {field_validation['all_valid']}")
    
    # 5. 测试本地校验
    print("\n5. 测试本地校验...")
    local_check_result = system.enhanced_local_field_check(test_sql)
    print(f"本地校验结果:\n{local_check_result}")
    
    # 6. 测试另一个SQL
    print("\n6. 测试另一个SQL...")
    test_sql2 = """
    SELECT 
        s.[全链库存],
        b.[本月备货],
        p.[SD PO Open Qty] AS [未清PO数量]
    FROM 
        [FF_IDSS_Dev_FF].[dbo].[dtsupply_summary] s
    JOIN 
        [FF_IDSS_Dev_FF].[dbo].[CONPD] c ON s.[Roadmap Family] = c.[Roadmap Family]
    JOIN 
        [FF_IDSS_Dev_FF].[dbo].[备货NY] b ON c.[PN] = b.[MTM]
    JOIN 
        [FF_IDSS_Data_CON_BAK].[dbo].[ConDT_Open_PO] p ON c.[PN] = p.[PN]
    WHERE 
        s.[Roadmap Family] LIKE '%510S%' 
        AND s.[Group] = 'ttl'
        AND s.[自然年] = 2025
        AND s.[财月] = '7月'
        AND s.[财周] = 'ttl'
    """
    
    print(f"测试SQL2:\n{test_sql2}")
    
    field_validation2 = system.validate_sql_fields(test_sql2)
    print(f"字段验证结果2:")
    print(f"  有效字段: {field_validation2['valid_fields']}")
    print(f"  缺失字段: {field_validation2['missing_fields']}")
    print(f"  全部有效: {field_validation2['all_valid']}")
    
    local_check_result2 = system.enhanced_local_field_check(test_sql2)
    print(f"本地校验结果2:\n{local_check_result2}")

if __name__ == "__main__":
    test_local_validation_fix() 