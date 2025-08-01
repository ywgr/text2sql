#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from text2sql_2_5_query import Text2SQLQueryEngine, DatabaseManager, VannaWrapper

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def test_time_condition_parsing():
    """测试时间条件解析修复"""
    
    # 初始化系统
    system = Text2SQLQueryEngine(
        table_knowledge=load_json('table_knowledge.json'),
        relationships=load_json('table_relationships.json'),
        business_rules=load_json('business_rules.json'),
        product_knowledge=load_json('product_knowledge.json'),
        historical_qa=load_json('historical_qa.json') if os.path.exists('historical_qa.json') else [],
        vanna=VannaWrapper(),
        db_manager=DatabaseManager(),
        prompt_templates=load_json('prompt_templates.json') if os.path.exists('prompt_templates.json') else {}
    )
    
    # 测试问题
    test_questions = [
        "geek25年7月全链库存",
        "510S25年6月全链库存",
        "小新25年8月全链库存",
        "geek25年全链库存",
        "geek7月全链库存"
    ]
    
    print("=== 时间条件解析测试 ===")
    print()
    
    for i, question in enumerate(test_questions, 1):
        print(f"测试 {i}: {question}")
        
        # 测试业务规则应用
        processed_question = system.apply_business_rules(question)
        print(f"处理后: {processed_question}")
        
        # 生成提示词
        prompt = system.generate_prompt(question)
        print(f"提示词长度: {len(prompt)} 字符")
        
        # 检查是否包含正确的时间条件
        if "自然年=2025" in processed_question:
            print("✅ 正确解析了自然年=2025")
        else:
            print("❌ 未正确解析自然年")
            
        if "财月='7月'" in processed_question or "财月='6月'" in processed_question or "财月='8月'" in processed_question:
            print("✅ 正确解析了财月条件")
        else:
            print("❌ 未正确解析财月条件")
        
        print("-" * 50)
        print()

def test_specific_case():
    """测试特定案例"""
    print("=== 特定案例测试: geek25年7月全链库存 ===")
    
    # 初始化系统
    system = Text2SQLQueryEngine(
        table_knowledge=load_json('table_knowledge.json'),
        relationships=load_json('table_relationships.json'),
        business_rules=load_json('business_rules.json'),
        product_knowledge=load_json('product_knowledge.json'),
        historical_qa=load_json('historical_qa.json') if os.path.exists('historical_qa.json') else [],
        vanna=VannaWrapper(),
        db_manager=DatabaseManager(),
        prompt_templates=load_json('prompt_templates.json') if os.path.exists('prompt_templates.json') else {}
    )
    
    question = "geek25年7月全链库存"
    
    print(f"原始问题: {question}")
    
    # 测试业务规则应用
    processed_question = system.apply_business_rules(question)
    print(f"业务规则处理后: {processed_question}")
    
    # 检查业务规则
    print("\n业务规则检查:")
    business_rules = load_json('business_rules.json')
    for rule, value in business_rules.items():
        if rule in question:
            print(f"  {rule} -> {value}")
    
    # 生成提示词
    prompt = system.generate_prompt(question)
    print(f"\n提示词长度: {len(prompt)} 字符")
    
    # 检查关键部分
    if "25年7月" in question and "自然年=2025 AND 财月='7月'" in processed_question:
        print("✅ 时间条件解析正确")
    else:
        print("❌ 时间条件解析错误")
        
    if "geek" in question and "roadmap family" in processed_question.lower():
        print("✅ 产品条件解析正确")
    else:
        print("❌ 产品条件解析错误")

if __name__ == "__main__":
    test_time_condition_parsing()
    print("\n" + "="*60 + "\n")
    test_specific_case()