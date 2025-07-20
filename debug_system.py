#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试TEXT2SQL系统
"""

import os
import sys
import traceback
from config_local import LocalConfig

def test_deepseek_api():
    """测试DeepSeek API"""
    print("测试DeepSeek API...")
    
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {LocalConfig.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LocalConfig.DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": "Hello, this is a test."}
            ],
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("DeepSeek API测试成功")
            print(f"响应: {result['choices'][0]['message']['content']}")
            return True
        else:
            print(f"DeepSeek API测试失败: {response.status_code}")
            print(f"响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"DeepSeek API测试异常: {e}")
        return False

def test_chromadb():
    """测试ChromaDB"""
    print("测试ChromaDB...")
    
    try:
        import chromadb
        
        # 创建客户端
        client = chromadb.PersistentClient(path=LocalConfig.CHROMA_DB_PATH)
        
        # 创建或获取集合
        collection_name = LocalConfig.CHROMA_COLLECTION_NAME
        try:
            collection = client.get_collection(collection_name)
            print(f"找到现有集合: {collection_name}")
        except:
            collection = client.create_collection(collection_name)
            print(f"创建新集合: {collection_name}")
        
        # 测试添加文档
        collection.add(
            documents=["这是一个测试文档"],
            ids=["test_1"]
        )
        
        # 测试查询
        results = collection.query(
            query_texts=["测试"],
            n_results=1
        )
        
        print("ChromaDB测试成功")
        print(f"查询结果: {results}")
        return True
        
    except Exception as e:
        print(f"ChromaDB测试失败: {e}")
        print(traceback.format_exc())
        return False

def test_vanna_integration():
    """测试Vanna集成"""
    print("测试Vanna集成...")
    
    try:
        from vanna.chromadb import ChromaDB_VectorStore
        from vanna.deepseek import DeepSeekChat
        
        class TestVanna(ChromaDB_VectorStore, DeepSeekChat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                DeepSeekChat.__init__(self, config=config)
        
        # 创建实例
        config = LocalConfig.get_chroma_config()
        print(f"配置: {config}")
        
        vn = TestVanna(config=config)
        print("Vanna实例创建成功")
        
        # 连接SQLite
        vn.connect_to_sqlite(LocalConfig.SQLITE_DB_FILE)
        print("SQLite连接成功")
        
        # 测试训练
        vn.train(ddl="CREATE TABLE test (id INTEGER, name TEXT)")
        print("训练测试成功")
        
        # 测试SQL生成
        sql = vn.generate_sql("显示所有数据")
        print(f"生成的SQL: {sql}")
        
        return True
        
    except Exception as e:
        print(f"Vanna集成测试失败: {e}")
        print(traceback.format_exc())
        return False

def test_sqlite():
    """测试SQLite数据库"""
    print("测试SQLite数据库...")
    
    try:
        import sqlite3
        
        conn = sqlite3.connect(LocalConfig.SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"数据库表: {tables}")
        
        # 检查student表数据
        cursor.execute("SELECT COUNT(*) FROM student")
        count = cursor.fetchone()[0]
        print(f"student表记录数: {count}")
        
        if count > 0:
            cursor.execute("SELECT * FROM student LIMIT 3")
            rows = cursor.fetchall()
            print(f"示例数据: {rows}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"SQLite测试失败: {e}")
        return False

def main():
    """主函数"""
    print("TEXT2SQL系统调试")
    print("=" * 40)
    
    tests = [
        ("SQLite数据库", test_sqlite),
        ("DeepSeek API", test_deepseek_api),
        ("ChromaDB", test_chromadb),
        ("Vanna集成", test_vanna_integration)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{test_name}...")
        try:
            if test_func():
                print(f"{test_name}: 成功")
            else:
                print(f"{test_name}: 失败")
        except Exception as e:
            print(f"{test_name}: 异常 - {e}")
    
    print("\n调试完成")

if __name__ == "__main__":
    main()