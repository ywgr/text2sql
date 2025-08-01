#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试时间字段检查功能
验证系统是否能正确识别表的时间字段，并在生成SQL时避免在不包含时间字段的表中添加时间条件
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

def test_time_field_validation():
    """测试时间字段检查功能"""
    print("=== 测试时间字段检查功能 ===")
    
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
    
    # 3. 检查每个表的时间字段情况
    print("\n3. 检查表的时间字段情况...")
    for table_name in table_knowledge:
        has_time_fields = system.check_table_has_time_fields(table_name)
        status = "✅ 包含时间字段" if has_time_fields else "❌ 不包含时间字段"
        print(f"表 [{table_name}]: {status}")
    
    # 4. 获取不包含时间字段的表
    print("\n4. 不包含时间字段的表:")
    tables_without_time = system.get_tables_without_time_fields()
    for table in tables_without_time:
        print(f"  - {table}")
    
    # 5. 测试SQL时间条件验证
    print("\n5. 测试SQL时间条件验证...")
    
    # 测试SQL 1：包含时间条件的SQL
    test_sql1 = """
    SELECT SUM(QTY) AS '消台25年7月供应总量'
    FROM FF_IDSS_Data_CON_BAK.dbo.ConDT_Commit
    WHERE [自然年] = 2025 AND [财月] = '7月' AND [Model] = 'ttl'
    """
    
    print(f"测试SQL1 (包含时间条件):\n{test_sql1}")
    tables1 = system.extract_tables_from_sql(test_sql1)
    validation1 = system.validate_time_conditions(test_sql1, tables1)
    print(f"时间条件验证结果:\n{validation1}")
    
    # 测试SQL 2：不包含时间条件的SQL
    test_sql2 = """
    SELECT SUM(QTY) AS '供应总量'
    FROM FF_IDSS_Data_CON_BAK.dbo.ConDT_Commit
    WHERE [Model] = 'ttl'
    """
    
    print(f"\n测试SQL2 (不包含时间条件):\n{test_sql2}")
    tables2 = system.extract_tables_from_sql(test_sql2)
    validation2 = system.validate_time_conditions(test_sql2, tables2)
    print(f"时间条件验证结果:\n{validation2}")
    
    # 6. 测试提示词生成
    print("\n6. 测试提示词生成...")
    test_question = "消台本月销售目标65K，供应gap多少？"
    prompt = system.generate_prompt(test_question)
    print("生成的提示词中包含时间字段警告:")
    if "无时间字段的表" in prompt:
        print("✅ 提示词正确包含了时间字段警告")
    else:
        print("❌ 提示词中缺少时间字段警告")
    
    # 7. 测试SQL校验
    print("\n7. 测试SQL校验...")
    validated_sql, validation_analysis = system.llm_validate_sql(test_sql1, prompt)
    print(f"SQL校验结果:\n{validation_analysis}")

if __name__ == "__main__":
    test_time_field_validation() 