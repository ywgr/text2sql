#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试Vanna连接和SQL生成
"""

from vanna.remote import VannaDefault
import traceback

def test_vanna():
    print("=== 测试Vanna AI连接 ===")
    
    api_key = "35d688e1655847838c9d0e318168d4f0"
    vanna_model = "chinook"
    
    try:
        print(f"API Key: {api_key}")
        print(f"Model: {vanna_model}")
        
        # 初始化Vanna
        print("正在初始化Vanna...")
        vn = VannaDefault(model=vanna_model, api_key=api_key)
        print("✅ Vanna初始化成功")
        
        # 测试SQL生成
        test_questions = [
            "Show all students",
            "List student names and classes",
            "查询所有学生",
            "显示学生姓名和班级"
        ]
        
        for question in test_questions:
            print(f"\n🔍 测试问题: {question}")
            try:
                sql = vn.generate_sql(question=question)
                print(f"✅ 生成的SQL: {sql}")
            except Exception as e:
                print(f"❌ SQL生成失败: {e}")
                traceback.print_exc()
        
        return vn
        
    except Exception as e:
        print(f"❌ Vanna初始化失败: {e}")
        traceback.print_exc()
        return None

def test_sqlite_data():
    print("\n=== 测试SQLite数据 ===")
    
    import sqlite3
    import pandas as pd
    
    try:
        conn = sqlite3.connect("test_database.db")
        
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"数据库中的表: {[t[0] for t in tables]}")
        
        # 检查每个表的数据
        for table in ['student', 'course', 'score']:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
                print(f"\n表 {table} 的数据 (前5行):")
                print(df)
                
                count_df = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table}", conn)
                print(f"表 {table} 总记录数: {count_df['count'].iloc[0]}")
                
            except Exception as e:
                print(f"❌ 查询表 {table} 失败: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ SQLite测试失败: {e}")

if __name__ == "__main__":
    # 测试Vanna
    vn = test_vanna()
    
    # 测试SQLite数据
    test_sqlite_data()
    
    if vn:
        print("\n🎉 Vanna连接正常，可以生成SQL")
    else:
        print("\n❌ Vanna连接有问题，需要检查API密钥或网络")