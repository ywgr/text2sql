#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的SQL测试，直接查询数据库
"""

import sqlite3
import pandas as pd

def test_direct_sql():
    """直接测试SQL查询"""
    print("直接SQL查询测试")
    print("=" * 30)
    
    try:
        conn = sqlite3.connect("test_database.db")
        
        # 测试查询
        queries = [
            ("显示所有学生", "SELECT * FROM student"),
            ("显示表student", "SELECT * FROM student"),
            ("查询学生姓名", "SELECT name FROM student"),
            ("统计学生数量", "SELECT COUNT(*) as count FROM student")
        ]
        
        for desc, sql in queries:
            print(f"\n{desc}:")
            print(f"SQL: {sql}")
            
            try:
                df = pd.read_sql_query(sql, conn)
                print(f"结果: {len(df)} 行")
                print(df.head())
            except Exception as e:
                print(f"查询失败: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"数据库连接失败: {e}")

if __name__ == "__main__":
    test_direct_sql()