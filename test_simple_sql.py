#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单SQL生成测试
"""

import json
import os

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def test_simple_sql():
    print("🧪 测试简单SQL生成...")
    
    # 加载知识库
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json') if os.path.exists('historical_qa.json') else []
    
    print(f"✅ 知识库加载完成:")
    print(f"   - 表结构: {len(table_knowledge)} 个")
    print(f"   - 表关系: {len(relationships.get('relationships', []))} 个")
    
    # 导入类
    import sys
    sys.path.append('.')
    
    # 创建简单的测试类
    class SimpleVannaWrapper:
        def __init__(self):
            self.api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        
        def generate_sql(self, prompt):
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            print(f"📝 发送提示词: {prompt[:200]}...")
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ API响应: {content[:200]}...")
                return content
            else:
                raise RuntimeError(f"API调用失败: {response.status_code}")
    
    class SimpleDatabaseManager:
        def get_mssql_connection_string(self, config):
            return "test_connection_string"
    
    # 创建引擎
    from text2sql_v2_5 import Text2SQLQueryEngine
    
    vanna = SimpleVannaWrapper()
    db_manager = SimpleDatabaseManager()
    
    engine = Text2SQLQueryEngine(
        table_knowledge, relationships, business_rules,
        product_knowledge, historical_qa, vanna, db_manager, {}
    )
    
    # 测试问题
    test_question = "geek25年7月全链库存"
    print(f"\n❓ 测试问题: {test_question}")
    
    # 生成提示词
    prompt = engine.generate_prompt(test_question)
    print(f"\n📝 生成的提示词长度: {len(prompt)}")
    print(f"📋 提示词预览: {prompt[:300]}...")
    
    # 生成SQL
    print("\n🚀 开始生成SQL...")
    sql, analysis = engine.generate_sql(prompt)
    
    print(f"\n📊 结果:")
    print(f"   - SQL: {sql}")
    print(f"   - 分析: {analysis[:200] if analysis else '无'}...")

if __name__ == "__main__":
    test_simple_sql() 