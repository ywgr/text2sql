#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地TEXT2SQL系统测试脚本
"""

import os
import sys
import sqlite3
import traceback
from config_local import LocalConfig

def test_sqlite_database():
    """测试SQLite数据库"""
    print("测试SQLite数据库...")
    
    try:
        # 检查数据库文件是否存在
        if not os.path.exists(LocalConfig.SQLITE_DB_FILE):
            print(f"❌ 数据库文件不存在: {LocalConfig.SQLITE_DB_FILE}")
            return False
        
        # 连接数据库
        conn = sqlite3.connect(LocalConfig.SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        
        expected_tables = ['student', 'course', 'score']
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ 缺少表: {missing_tables}")
            conn.close()
            return False
        
        # 检查数据
        for table in expected_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✅ 表 {table}: {count} 条记录")
        
        conn.close()
        print("✅ SQLite数据库测试通过")
        return True
        
    except Exception as e:
        print(f"❌ SQLite数据库测试失败: {e}")
        return False

def test_chromadb_setup():
    """测试ChromaDB设置"""
    print("测试ChromaDB设置...")
    
    try:
        import chromadb
        
        # 检查ChromaDB目录
        if not os.path.exists(LocalConfig.CHROMA_DB_PATH):
            print(f"创建ChromaDB目录: {LocalConfig.CHROMA_DB_PATH}")
            os.makedirs(LocalConfig.CHROMA_DB_PATH, exist_ok=True)
        
        # 测试ChromaDB连接
        client = chromadb.PersistentClient(path=LocalConfig.CHROMA_DB_PATH)
        
        # 尝试创建或获取集合
        collection_name = LocalConfig.CHROMA_COLLECTION_NAME
        try:
            collection = client.get_collection(collection_name)
            count = collection.count()
            print(f"  ✅ 现有集合 {collection_name}: {count} 个向量")
        except:
            collection = client.create_collection(collection_name)
            print(f"  ✅ 创建新集合: {collection_name}")
        
        print("✅ ChromaDB设置测试通过")
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB设置测试失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        return False

def test_deepseek_api():
    """测试DeepSeek API"""
    print("测试DeepSeek API...")
    
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {LocalConfig.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 简单的API测试
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
            if 'choices' in result and len(result['choices']) > 0:
                print("  ✅ API响应正常")
                print("✅ DeepSeek API测试通过")
                return True
            else:
                print("❌ API响应格式异常")
                return False
        else:
            print(f"❌ API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ DeepSeek API测试失败: {e}")
        return False

def test_vanna_integration():
    """测试Vanna集成"""
    print("测试Vanna集成...")
    
    try:
        from vanna.chromadb import ChromaDB_VectorStore
        from vanna.deepseek import DeepSeekChat
        
        # 测试类定义
        class TestVanna(ChromaDB_VectorStore, DeepSeekChat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                DeepSeekChat.__init__(self, config=config)
        
        # 创建测试实例
        config = LocalConfig.get_chroma_config()
        vn = TestVanna(config=config)
        
        print("  ✅ Vanna类创建成功")
        
        # 测试SQLite连接
        vn.connect_to_sqlite(LocalConfig.SQLITE_DB_FILE)
        print("  ✅ SQLite连接成功")
        
        print("✅ Vanna集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Vanna集成测试失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        return False

def test_dependencies():
    """测试依赖包"""
    print("测试依赖包...")
    
    required_packages = [
        'streamlit',
        'vanna',
        'pandas',
        'plotly',
        'chromadb',
        'openai',
        'sqlite3'
    ]
    
    failed_packages = []
    
    for package in required_packages:
        try:
            if package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            failed_packages.append(package)
    
    if failed_packages:
        print(f"❌ 缺少依赖包: {failed_packages}")
        return False
    else:
        print("✅ 所有依赖包测试通过")
        return True

def test_configuration():
    """测试配置"""
    print("测试配置...")
    
    try:
        # 检查关键配置
        if not LocalConfig.DEEPSEEK_API_KEY or LocalConfig.DEEPSEEK_API_KEY == "your_api_key_here":
            print("❌ DeepSeek API Key未设置")
            return False
        
        if not LocalConfig.CHROMA_DB_PATH:
            print("❌ ChromaDB路径未设置")
            return False
        
        if not LocalConfig.SQLITE_DB_FILE:
            print("❌ SQLite数据库文件未设置")
            return False
        
        print(f"  ✅ DeepSeek API Key: {LocalConfig.DEEPSEEK_API_KEY[:10]}...")
        print(f"  ✅ ChromaDB路径: {LocalConfig.CHROMA_DB_PATH}")
        print(f"  ✅ SQLite文件: {LocalConfig.SQLITE_DB_FILE}")
        print(f"  ✅ 模型: {LocalConfig.DEEPSEEK_MODEL}")
        
        print("✅ 配置测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def run_comprehensive_test():
    """运行完整测试"""
    print("TEXT2SQL本地系统完整测试")
    print("=" * 60)
    
    tests = [
        ("配置测试", test_configuration),
        ("依赖包测试", test_dependencies),
        ("SQLite数据库测试", test_sqlite_database),
        ("ChromaDB设置测试", test_chromadb_setup),
        ("DeepSeek API测试", test_deepseek_api),
        ("Vanna集成测试", test_vanna_integration)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}...")
        try:
            if test_func():
                passed_tests += 1
            else:
                print(f"❌ {test_name}失败")
        except Exception as e:
            print(f"❌ {test_name}异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed_tests}/{total_tests} 通过")
    
    if passed_tests == total_tests:
        print("所有测试通过！系统可以正常使用")
        print("\n下一步:")
        print("1. 运行: python run_local_system.py")
        print("2. 或直接运行: streamlit run text2sql_local_deepseek.py")
        return True
    else:
        print("⚠️ 部分测试失败，请检查错误信息")
        print("\n建议:")
        print("1. 检查配置文件 config_local.py")
        print("2. 确认所有依赖包已安装: pip install -r requirements.txt")
        print("3. 检查DeepSeek API密钥是否有效")
        return False

def main():
    """主函数"""
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        
        test_map = {
            'config': test_configuration,
            'deps': test_dependencies,
            'sqlite': test_sqlite_database,
            'chroma': test_chromadb_setup,
            'deepseek': test_deepseek_api,
            'vanna': test_vanna_integration
        }
        
        if test_name in test_map:
            print(f"运行单项测试: {test_name}")
            test_map[test_name]()
        else:
            print(f"未知测试: {test_name}")
            print(f"可用测试: {list(test_map.keys())}")
    else:
        run_comprehensive_test()

if __name__ == "__main__":
    main()