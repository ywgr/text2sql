#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def apply_business_rules_simple(question, business_rules, business_rules_meta):
    """简化的业务规则应用函数"""
    processed_question = question
    where_conditions = []
    
    # 按规则长度排序，确保更具体的规则优先
    sorted_rules = sorted(business_rules.items(), key=lambda x: len(x[0]), reverse=True)
    
    for business_term, rule_info in sorted_rules:
        if isinstance(rule_info, str):
            # 检查元数据
            meta_info = business_rules_meta.get(business_term, {})
            rule_type = meta_info.get('type', '实体')
            
            if business_term in processed_question:
                # 对于时间类型的规则，添加到WHERE条件中
                if rule_type == '时间':
                    where_conditions.append(rule_info)
                    # 从问题中移除业务术语，避免重复
                    processed_question = processed_question.replace(business_term, '')
                else:
                    # 其他类型的规则，直接替换
                    processed_question = processed_question.replace(business_term, rule_info)
    
    # 清理多余的空格
    processed_question = re.sub(r'\s+', ' ', processed_question).strip()
    
    # 如果有WHERE条件，添加到问题中
    if where_conditions:
        where_clause = ' AND '.join(where_conditions)
        where_clause = re.sub(r'where\s+', '', where_clause, flags=re.IGNORECASE)
        where_clause = where_clause.strip()
        if where_clause:
            processed_question += f" WHERE条件: {where_clause}"
    
    return processed_question

def test_time_condition_parsing():
    """测试时间条件解析修复"""
    
    # 加载业务规则
    business_rules = load_json('business_rules.json')
    business_rules_meta = load_json('business_rules_meta.json')
    
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
        processed_question = apply_business_rules_simple(question, business_rules, business_rules_meta)
        print(f"处理后: {processed_question}")
        
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
    
    business_rules = load_json('business_rules.json')
    business_rules_meta = load_json('business_rules_meta.json')
    
    question = "geek25年7月全链库存"
    
    print(f"原始问题: {question}")
    
    # 测试业务规则应用
    processed_question = apply_business_rules_simple(question, business_rules, business_rules_meta)
    print(f"业务规则处理后: {processed_question}")
    
    # 检查业务规则
    print("\n业务规则检查:")
    for rule, value in business_rules.items():
        if rule in question:
            print(f"  {rule} -> {value}")
    
    # 检查关键部分
    if "25年7月" in question and "自然年=2025 AND 财月='7月'" in processed_question:
        print("✅ 时间条件解析正确")
    else:
        print("❌ 时间条件解析错误")
        print(f"期望包含: 自然年=2025 AND 财月='7月'")
        print(f"实际结果: {processed_question}")
        
    if "geek" in question and "roadmap family" in processed_question.lower():
        print("✅ 产品条件解析正确")
    else:
        print("❌ 产品条件解析错误")

def test_rule_priority():
    """测试规则优先级"""
    print("=== 规则优先级测试 ===")
    
    business_rules = load_json('business_rules.json')
    business_rules_meta = load_json('business_rules_meta.json')
    
    # 检查规则排序
    sorted_rules = sorted(business_rules.items(), key=lambda x: len(x[0]), reverse=True)
    
    print("规则按长度排序（优先处理更具体的规则）:")
    for rule, value in sorted_rules[:10]:  # 显示前10个
        print(f"  {rule} -> {value}")
    
    # 测试具体案例
    question = "geek25年7月全链库存"
    print(f"\n测试问题: {question}")
    
    # 找出匹配的规则
    matching_rules = []
    for rule, value in business_rules.items():
        if rule in question:
            matching_rules.append((rule, value))
    
    print("匹配的规则:")
    for rule, value in matching_rules:
        print(f"  {rule} -> {value}")
    
    # 应用规则
    processed_question = apply_business_rules_simple(question, business_rules, business_rules_meta)
    print(f"\n最终结果: {processed_question}")

if __name__ == "__main__":
    test_time_condition_parsing()
    print("\n" + "="*60 + "\n")
    test_specific_case()
    print("\n" + "="*60 + "\n")
    test_rule_priority()