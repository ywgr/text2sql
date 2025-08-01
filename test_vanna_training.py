#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Vanna训练功能
验证历史问答对是否被正确训练到Vanna中
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

def test_vanna_training():
    """测试Vanna训练功能"""
    print("=== 测试Vanna训练功能 ===")
    
    # 1. 加载知识库
    print("\n1. 加载知识库...")
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json')
    
    print(f"表结构知识库: {len(table_knowledge)} 个表")
    print(f"表关系定义: {len(relationships.get('relationships', []))} 个关系")
    print(f"业务规则: {len(business_rules)} 条规则")
    print(f"历史问答对: {len(historical_qa)} 条记录")
    
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
    
    # 3. 测试训练功能
    print("\n3. 测试Vanna训练...")
    success = system.train_vanna_with_enterprise_knowledge()
    
    if success:
        print("✅ Vanna训练成功")
        print(f"训练数据数量: {len(vanna.training_data)}")
        
        # 显示训练数据
        print("\n训练数据详情:")
        for i, item in enumerate(vanna.training_data):
            print(f"\n训练项 {i+1}:")
            if 'ddl' in item:
                print(f"  DDL: {item['ddl'][:100]}...")
            if 'documentation' in item:
                print(f"  文档: {item['documentation'][:100]}...")
            if 'question' in item and 'sql' in item:
                print(f"  问答: {item['question'][:50]}... -> {item['sql'][:50]}...")
    else:
        print("❌ Vanna训练失败")
    
    # 4. 测试SQL生成
    print("\n4. 测试SQL生成...")
    test_question = "510S本月全链库存"
    prompt = system.generate_prompt(test_question)
    sql, analysis = system.generate_sql(prompt)
    
    print(f"测试问题: {test_question}")
    print(f"生成的SQL: {sql}")
    print(f"分析结果: {analysis[:200]}...")
    
    return success

if __name__ == "__main__":
    test_vanna_training() 