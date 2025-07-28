#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细日志记录测试脚本
用于验证修复后的日志记录功能
"""

import json
import os

def load_json(path):
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 文件 {path} 不存在")
        return {}
    except Exception as e:
        print(f"错误: 加载文件 {path} 失败: {e}")
        return {}

def test_detailed_logging():
    """测试详细日志记录功能"""
    print("🧪 开始测试详细日志记录功能...")
    
    # 导入主模块
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # 直接导入类
    from text2sql_2_5_query import DatabaseManager, VannaWrapper, Text2SQLQueryEngine
    
    # 加载知识库
    print("\n📚 加载知识库...")
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json') if os.path.exists('historical_qa.json') else []
    prompt_templates = load_json('prompt_templates.json') if os.path.exists('prompt_templates.json') else {}
    
    print(f"✅ 知识库加载完成:")
    print(f"   - 表结构: {len(table_knowledge)} 个")
    print(f"   - 表关系: {len(relationships.get('relationships', []))} 个")
    print(f"   - 业务规则: {len(business_rules)} 个")
    print(f"   - 产品知识: {len(product_knowledge)} 个")
    print(f"   - 历史问答: {len(historical_qa)} 个")
    
    # 初始化组件
    print("\n🔧 初始化组件...")
    db_manager = DatabaseManager()
    vanna = VannaWrapper()
    
    # 创建引擎
    engine = Text2SQLQueryEngine(
        table_knowledge, relationships, business_rules,
        product_knowledge, historical_qa, vanna, db_manager, prompt_templates
    )
    
    # 测试问题
    test_question = "geek25年7月全链库存"
    print(f"\n❓ 测试问题: {test_question}")
    
    # 生成提示词
    print("\n📝 生成提示词...")
    prompt = engine.generate_prompt(test_question)
    print(f"✅ 提示词生成完成，长度: {len(prompt)} 字符")
    
    # 生成SQL
    print("\n🚀 开始生成SQL...")
    sql, analysis = engine.generate_sql(prompt)
    
    # 显示结果
    print("\n📊 测试结果:")
    print(f"   - SQL生成: {'成功' if sql else '失败'}")
    print(f"   - SQL长度: {len(sql) if sql else 0}")
    print(f"   - 分析长度: {len(analysis) if analysis else 0}")
    
    if sql:
        print(f"   - 生成的SQL: {sql}")
    else:
        print("   - 未生成SQL")
    
    # 显示API统计
    stats = vanna.get_stats()
    print(f"\n📈 API调用统计:")
    print(f"   - 总调用次数: {stats.get('api_calls', 0)}")
    print(f"   - 错误次数: {stats.get('error_count', 0)}")
    print(f"   - 成功率: {((stats.get('api_calls', 0) - stats.get('error_count', 0)) / max(stats.get('api_calls', 1), 1)) * 100:.1f}%")
    
    if stats.get('errors'):
        print("   - 最近错误:")
        for error in stats['errors'][-3:]:
            print(f"     * {error}")
    
    print("\n🎉 测试完成!")

if __name__ == "__main__":
    test_detailed_logging() 