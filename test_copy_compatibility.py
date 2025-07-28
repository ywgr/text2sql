#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试与text2sql_v2.5 copy.py的兼容性
"""

import json
import os

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def test_copy_compatibility():
    print("🧪 测试与copy.py的兼容性...")
    
    # 加载知识库
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json') if os.path.exists('historical_qa.json') else []
    prompt_templates = load_json('prompt_templates.json') if os.path.exists('prompt_templates.json') else {}
    
    print(f"✅ 知识库加载完成:")
    print(f"   - 表结构: {len(table_knowledge)} 个")
    print(f"   - 表关系: {len(relationships.get('relationships', []))} 个")
    print(f"   - 提示词模板: {len(prompt_templates)} 个")
    
    # 检查prompt_templates
    if 'sql_generation' in prompt_templates:
        template = prompt_templates['sql_generation']
        print(f"📝 SQL生成模板长度: {len(template)}")
        print(f"📋 模板预览: {template[:200]}...")
        
        # 检查模板中是否有问题
        if "只返回SQL语句" in template:
            print("✅ 模板包含SQL生成要求")
        else:
            print("⚠️ 模板可能缺少SQL生成要求")
    else:
        print("❌ 未找到sql_generation模板")
    
    # 测试问题
    test_question = "geek25年7月全链库存"
    print(f"\n❓ 测试问题: {test_question}")
    
    # 导入类并测试
    import sys
    sys.path.append('.')
    
    # 创建简单的测试类
    class TestVannaWrapper:
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
            
            print(f"📝 发送提示词长度: {len(prompt)}")
            print(f"📋 提示词预览: {prompt[:300]}...")
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ API响应长度: {len(content)}")
                print(f"📄 响应预览: {content[:300]}...")
                return content
            else:
                raise RuntimeError(f"API调用失败: {response.status_code}")
    
    class TestDatabaseManager:
        def get_mssql_connection_string(self, config):
            return "test_connection_string"
    
    # 导入引擎类
    from text2sql_2_5_query import Text2SQLQueryEngine
    
    vanna = TestVannaWrapper()
    db_manager = TestDatabaseManager()
    
    # 创建引擎（与copy.py完全一致）
    engine = Text2SQLQueryEngine(
        table_knowledge, relationships, business_rules,
        product_knowledge, historical_qa, vanna, db_manager, prompt_templates
    )
    
    # 生成提示词
    prompt = engine.generate_prompt(test_question)
    print(f"\n📝 生成的提示词长度: {len(prompt)}")
    
    # 生成SQL
    print("\n🚀 开始生成SQL...")
    sql, analysis = engine.generate_sql(prompt)
    
    print(f"\n📊 结果:")
    print(f"   - SQL: {sql}")
    print(f"   - 分析长度: {len(analysis) if analysis else 0}")

if __name__ == "__main__":
    test_copy_compatibility() 