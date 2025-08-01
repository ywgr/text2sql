#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试时间解析修复
"""

import json
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from text2sql_2_5_query import Text2SQLQueryEngine, DatabaseManager, VannaWrapper

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def test_time_parsing():
    """测试时间解析功能"""
    print("=== 测试时间解析修复 ===")
    
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
    
    # 测试用例
    test_cases = [
        "geek25年7月全链库存",
        "510S 25年6月全链库存",
        "拯救者 25年8月全链库存",
        "小新 25年9月全链库存",
        "geek25年全链库存",
        "510S 7月全链库存",
    ]
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i}: {question} ---")
        
        # 应用业务规则
        processed_question = system.apply_business_rules(question)
        print(f"处理后的问题: {processed_question}")
        
        # 生成提示词
        prompt = system.generate_prompt(processed_question)
        print(f"生成的提示词长度: {len(prompt)} 字符")
        
        # 检查提示词中是否包含正确的时间条件
        if "25年" in question:
            if "自然年=2025" in prompt:
                print("✅ 25年时间条件正确解析")
            else:
                print("❌ 25年时间条件解析失败")
        
        if "7月" in question:
            if "财月='7月'" in prompt:
                print("✅ 7月时间条件正确解析")
            else:
                print("❌ 7月时间条件解析失败")
        
        if "25年7月" in question:
            if "自然年=2025 AND 财月='7月'" in prompt or ("自然年=2025" in prompt and "财月='7月'" in prompt):
                print("✅ 25年7月时间条件正确解析")
            else:
                print("❌ 25年7月时间条件解析失败")

def test_sql_generation():
    """测试SQL生成功能"""
    print("\n=== 测试SQL生成功能 ===")
    
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
    
    # 测试用例
    test_question = "geek25年7月全链库存"
    print(f"测试问题: {test_question}")
    
    # 应用业务规则
    processed_question = system.apply_business_rules(test_question)
    print(f"处理后的问题: {processed_question}")
    
    # 生成提示词
    prompt = system.generate_prompt(processed_question)
    print(f"提示词长度: {len(prompt)} 字符")
    
    # 检查提示词中的关键信息
    key_checks = [
        ("自然年=2025", "25年时间条件"),
        ("财月='7月'", "7月时间条件"),
        ("GEEK", "GEEK产品条件"),
        ("全链库存", "全链库存字段"),
        ("dtsupply_summary", "目标表"),
    ]
    
    for check_text, description in key_checks:
        if check_text in prompt:
            print(f"✅ 提示词包含 {description}: {check_text}")
        else:
            print(f"❌ 提示词缺少 {description}: {check_text}")

def test_business_rules():
    """测试业务规则配置"""
    print("\n=== 测试业务规则配置 ===")
    
    business_rules = load_json('business_rules.json')
    business_rules_meta = load_json('business_rules_meta.json')
    
    # 检查关键业务规则
    key_rules = ["25年", "25 ", "7月"]
    
    for rule in key_rules:
        if rule in business_rules:
            print(f"✅ 业务规则 '{rule}' 存在: {business_rules[rule]}")
        else:
            print(f"❌ 业务规则 '{rule}' 不存在")
    
    # 检查元数据
    for rule in key_rules:
        if rule in business_rules_meta:
            meta = business_rules_meta[rule]
            print(f"✅ 业务规则元数据 '{rule}' 存在: {meta.get('type', 'N/A')} - {meta.get('description', 'N/A')}")
        else:
            print(f"❌ 业务规则元数据 '{rule}' 不存在")

if __name__ == "__main__":
    print("开始测试时间解析修复...")
    
    # 测试业务规则配置
    test_business_rules()
    
    # 测试时间解析
    test_time_parsing()
    
    # 测试SQL生成
    test_sql_generation()
    
    print("\n=== 测试完成 ===")