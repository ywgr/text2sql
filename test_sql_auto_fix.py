#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试SQL自动修正功能
验证当SQL校验发现问题时，LLM能够自动修正
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

def test_sql_auto_fix():
    """测试SQL自动修正功能"""
    print("=== 测试SQL自动修正功能 ===")
    
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
    
    # 3. 测试有问题的SQL
    print("\n3. 测试有问题的SQL...")
    problematic_sql = """
    SELECT 
        s.[全链库存],
        b.[本月备货],
        p.[未清PO数量]  -- 这个字段可能不存在
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
    
    original_question = "510S本月全链库存、本月备货、未清PO"
    
    print(f"原始SQL:\n{problematic_sql}")
    
    # 4. 进行字段验证
    print("\n4. 进行字段验证...")
    field_validation = system.validate_sql_fields(problematic_sql)
    print(f"字段验证结果: {field_validation}")
    
    if not field_validation['all_valid']:
        print(f"发现无效字段: {field_validation['missing_fields']}")
        
        # 5. 调用LLM修正
        print("\n5. 调用LLM修正...")
        validation_errors = f"字段验证失败：\n"
        for field in field_validation['missing_fields']:
            validation_errors += f"- 字段 '{field}' 不存在于表结构中\n"
        
        fixed_sql, fix_analysis = system.llm_fix_sql(problematic_sql, validation_errors, original_question)
        
        print(f"修正后的SQL:\n{fixed_sql}")
        print(f"修正分析:\n{fix_analysis}")
        
        # 6. 重新验证修正后的SQL
        print("\n6. 重新验证修正后的SQL...")
        re_validation = system.validate_sql_fields(fixed_sql)
        print(f"重新验证结果: {re_validation}")
        
        if re_validation['all_valid']:
            print("✅ 修正成功！")
        else:
            print("❌ 修正后仍有问题")
    else:
        print("✅ 原始SQL验证通过，无需修正")
    
    # 7. 测试本地校验
    print("\n7. 测试本地校验...")
    local_check_result = system.enhanced_local_field_check(problematic_sql)
    print(f"本地校验结果:\n{local_check_result}")
    
    if "发现问题" in local_check_result:
        print("本地校验发现问题，进行修正...")
        fixed_sql2, fix_analysis2 = system.llm_fix_sql(problematic_sql, local_check_result, original_question)
        print(f"本地校验修正后的SQL:\n{fixed_sql2}")
        print(f"本地校验修正分析:\n{fix_analysis2}")

if __name__ == "__main__":
    test_sql_auto_fix() 