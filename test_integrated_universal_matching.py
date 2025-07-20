#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试集成到text2sql_v2.3_enhanced.py的通用产品匹配功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from text2sql_v2.3_enhanced import generate_sql_with_universal_product_matching, test_universal_product_matching

def main():
    """主测试函数"""
    print("=== 测试集成的通用产品匹配功能 ===")
    
    # 测试各种产品
    test_cases = [
        {
            "question": "510S 25年7月全链库存",
            "expected_patterns": ["LIKE '%510S%'", "[Group] = 'ttl'", "[财年] = 2025", "[财月] = '7月'"]
        },
        {
            "question": "geek产品今年的SellOut数据",
            "expected_patterns": ["LIKE '%Geek%'", "[Group] = 'ttl'", "SellOut"]
        },
        {
            "question": "小新系列2025年周转情况",
            "expected_patterns": ["LIKE '%小新%'", "[Group] = 'ttl'", "[财年] = 2025"]
        },
        {
            "question": "拯救者全链库存",
            "expected_patterns": ["LIKE '%拯救者%'", "[Group] = 'ttl'", "全链库存"]
        },
        {
            "question": "AIO产品库存",
            "expected_patterns": ["LIKE '%AIO%'", "[Group] = 'ttl'"]
        }
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        expected_patterns = test_case["expected_patterns"]
        
        print(f"\n{i}. 测试问题: {question}")
        
        try:
            sql = generate_sql_with_universal_product_matching(question)
            print(f"   生成的SQL: {sql}")
            
            # 检查期望的模式
            patterns_found = []
            patterns_missing = []
            
            for pattern in expected_patterns:
                if pattern in sql:
                    patterns_found.append(pattern)
                else:
                    patterns_missing.append(pattern)
            
            if patterns_missing:
                print(f"   ❌ 缺少模式: {patterns_missing}")
            else:
                print(f"   ✅ 所有期望模式都存在")
                success_count += 1
            
            if patterns_found:
                print(f"   ✓ 找到模式: {patterns_found}")
            
        except Exception as e:
            print(f"   ❌ 生成失败: {e}")
        
        print("-" * 60)
    
    print(f"\n=== 测试结果 ===")
    print(f"成功: {success_count}/{total_count}")
    print(f"成功率: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("🎉 所有测试通过！通用产品匹配功能集成成功！")
    else:
        print("⚠️  部分测试失败，需要进一步调试")
    
    # 运行内置测试
    print(f"\n=== 运行内置测试 ===")
    test_universal_product_matching()

if __name__ == "__main__":
    main()