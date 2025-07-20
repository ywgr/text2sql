#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行集成的Text2SQL系统
包含Streamlit界面和命令行测试
"""

import streamlit as st
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from text2sql_integrated_system import IntegratedText2SQLSystem, create_streamlit_interface

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 命令行测试模式
        test_system()
    else:
        # Streamlit界面模式
        create_streamlit_interface()

def test_system():
    """测试系统"""
    print("=== Text2SQL集成系统测试 ===")
    
    system = IntegratedText2SQLSystem()
    
    # 测试原始错误的SQL
    print("\n1. 测试原始错误SQL的识别:")
    error_sql = """SELECT [d].[全链库存] FROM [dtsupply_summary] AS [d] 
    JOIN [CONPD] AS [c] ON [d].[Roadmap Family] = [c].[Roadmap Family] 
    WHERE [c].[Roadmap Family] LIKE '%510S%' AND [c].[Group] = 'ttl' AND [d].[财月] = '20257'"""
    
    question = "510S 25年7月全链库存"
    evaluation = system._evaluate_sql(error_sql, question)
    
    print(f"错误SQL评分: {evaluation['score']:.1f}")
    print("发现的问题:")
    for issue in evaluation['issues']:
        print(f"  - {issue}")
    
    # 测试正确的SQL生成
    print(f"\n2. 测试正确SQL生成:")
    result = system.generate_sql(question)
    
    print(f"问题: {question}")
    print(f"生成的SQL: {result.sql}")
    print(f"评分: {result.score:.1f}")
    print(f"是否正确: {result.is_correct}")
    print(f"来源: {'缓存' if result.from_cache else '新生成'}")
    
    if result.issues:
        print("问题:")
        for issue in result.issues:
            print(f"  - {issue}")
    
    # 测试缓存功能
    print(f"\n3. 测试缓存功能:")
    result2 = system.generate_sql(question)
    print(f"第二次查询来源: {'缓存命中' if result2.from_cache else '新生成'}")
    
    # 测试用户反馈
    print(f"\n4. 测试用户反馈:")
    result3 = system.generate_sql("510S产品SellOut数据", "correct")
    print(f"用户反馈'正确'后是否缓存: {result3.score >= 80}")
    
    # 显示统计
    print(f"\n5. 系统统计:")
    stats = system.get_statistics()
    for key, value in stats.items():
        if key != "product_hierarchy":
            print(f"  {key}: {value}")
    
    print(f"\n6. 产品层级理解:")
    for product, config in stats["product_hierarchy"].items():
        print(f"  {product}: {config['description']}")
    
    print(f"\n=== 测试完成 ===")

if __name__ == "__main__":
    main()