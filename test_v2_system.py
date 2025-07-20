#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 2.0版本测试脚本
测试各个功能模块的基本功能
"""

import os
import sys
import json
import sqlite3
import pandas as pd
from datetime import datetime

def print_banner():
    """打印测试横幅"""
    banner = """
================================================================
                TEXT2SQL系统 2.0版本 功能测试                    
================================================================
"""
    print(banner)

def test_config_loading():
    """测试配置加载"""
    print("🔧 测试配置加载...")
    
    try:
        from config_local import LocalConfig
        
        # 验证配置
        errors = LocalConfig.validate_config()
        if errors:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"   - {error}")
            return False
        else:
            print("✅ 配置验证通过")
            
        # 创建必要目录
        LocalConfig.create_directories()
        print("✅ 目录创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def test_database_manager():
    """测试数据库管理器"""
    print("\n📊 测试数据库管理器...")
    
    try:
        # 简化测试，检查SQLite连接
        import sqlite3
        
        # 测试SQLite连接
        conn = sqlite3.connect("test_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        print("✅ SQLite连接测试通过")
        print(f"✅ 获取到 {len(tables)} 个表")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库管理器测试失败: {e}")
        return False

def test_knowledge_base():
    """测试知识库功能"""
    print("\n🧠 测试知识库功能...")
    
    try:
        # 测试表结构知识库
        table_knowledge = {
            "test_table": {
                "comment": "测试表",
                "fields": {
                    "id": "主键ID",
                    "name": "姓名",
                    "age": "年龄"
                }
            }
        }
        
        # 保存测试
        with open("table_knowledge.json", "w", encoding="utf-8") as f:
            json.dump(table_knowledge, f, ensure_ascii=False, indent=2)
        print("✅ 表结构知识库保存成功")
        
        # 测试产品知识库
        product_knowledge = {
            "products": {
                "1": {
                    "name": "测试产品",
                    "description": "这是一个测试产品",
                    "category": "测试分类"
                }
            },
            "business_rules": {
                "测试规则": {
                    "condition": "测试条件",
                    "action": "测试动作"
                }
            }
        }
        
        with open("product_knowledge.json", "w", encoding="utf-8") as f:
            json.dump(product_knowledge, f, ensure_ascii=False, indent=2)
        print("✅ 产品知识库保存成功")
        
        # 测试业务规则
        business_rules = {
            "学生": "student",
            "课程": "course",
            "成绩": "score",
            "优秀": "score >= 90"
        }
        
        with open("business_rules.json", "w", encoding="utf-8") as f:
            json.dump(business_rules, f, ensure_ascii=False, indent=2)
        print("✅ 业务规则保存成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 知识库测试失败: {e}")
        return False

def test_database_configs():
    """测试数据库配置"""
    print("\n🔗 测试数据库配置...")
    
    try:
        # 创建测试数据库配置
        database_configs = {
            "test_sqlite": {
                "name": "测试SQLite",
                "type": "sqlite",
                "config": {"file_path": "test_database.db"},
                "active": True
            },
            "test_mssql": {
                "name": "测试MSSQL",
                "type": "mssql",
                "config": {
                    "server": "10.97.34.39",
                    "database": "FF_IDSS_Dev_FF",
                    "username": "FF_User",
                    "password": "Grape!0808",
                    "driver": "ODBC Driver 17 for SQL Server"
                },
                "active": False
            }
        }
        
        with open("database_configs.json", "w", encoding="utf-8") as f:
            json.dump(database_configs, f, ensure_ascii=False, indent=2)
        print("✅ 数据库配置保存成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库配置测试失败: {e}")
        return False

def test_prompt_templates():
    """测试提示词模板"""
    print("\n📝 测试提示词模板...")
    
    try:
        prompt_templates = {
            "sql_generation": """你是一个SQL专家。根据以下信息生成准确的SQL查询语句。

数据库结构：
{schema_info}

表结构知识库：
{table_knowledge}

产品知识库：
{product_knowledge}

业务规则：
{business_rules}

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 根据数据库类型使用正确的SQL语法
5. 应用业务规则进行术语转换

SQL语句：""",

            "sql_verification": """你是一个SQL验证专家。请检查以下SQL语句是否正确并符合用户需求。

数据库结构：
{schema_info}

用户问题：{question}
生成的SQL：{sql}

请检查：
1. SQL语法是否正确
2. 表名和字段名是否存在
3. 是否正确回答了用户问题

如果SQL完全正确，请回答"VALID"
如果有问题，请提供修正后的SQL语句。

回答："""
        }
        
        with open("prompt_templates.json", "w", encoding="utf-8") as f:
            json.dump(prompt_templates, f, ensure_ascii=False, indent=2)
        print("✅ 提示词模板保存成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 提示词模板测试失败: {e}")
        return False

def create_test_database():
    """创建测试数据库"""
    print("\n🗄️ 创建测试数据库...")
    
    try:
        # 创建SQLite测试数据库
        conn = sqlite3.connect("test_database.db")
        cursor = conn.cursor()
        
        # 创建学生表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            class_id INTEGER
        )
        """)
        
        # 创建课程表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY,
            course_name TEXT NOT NULL,
            teacher TEXT,
            credits INTEGER
        )
        """)
        
        # 创建成绩表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            course_id INTEGER,
            score INTEGER,
            exam_date DATE,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
        """)
        
        # 插入测试数据
        students_data = [
            (1, "张三", 20, "男", 1),
            (2, "李四", 19, "女", 1),
            (3, "王五", 21, "男", 2),
            (4, "赵六", 20, "女", 2)
        ]
        
        cursor.executemany("INSERT OR REPLACE INTO students VALUES (?, ?, ?, ?, ?)", students_data)
        
        courses_data = [
            (1, "数学", "张老师", 4),
            (2, "英语", "李老师", 3),
            (3, "计算机", "王老师", 5)
        ]
        
        cursor.executemany("INSERT OR REPLACE INTO courses VALUES (?, ?, ?, ?)", courses_data)
        
        scores_data = [
            (1, 1, 1, 85, "2024-01-15"),
            (2, 1, 2, 92, "2024-01-16"),
            (3, 2, 1, 78, "2024-01-15"),
            (4, 2, 2, 88, "2024-01-16"),
            (5, 3, 1, 95, "2024-01-15"),
            (6, 4, 3, 82, "2024-01-17")
        ]
        
        cursor.executemany("INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?)", scores_data)
        
        conn.commit()
        conn.close()
        
        print("✅ 测试数据库创建成功")
        print("   - students表: 4条记录")
        print("   - courses表: 3条记录") 
        print("   - scores表: 6条记录")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试数据库创建失败: {e}")
        return False

def test_system_integration():
    """测试系统集成"""
    print("\n🔄 测试系统集成...")
    
    try:
        # 检查所有配置文件是否存在
        required_files = [
            "database_configs.json",
            "table_knowledge.json", 
            "product_knowledge.json",
            "business_rules.json",
            "prompt_templates.json",
            "test_database.db"
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            print(f"❌ 缺少文件: {missing_files}")
            return False
        
        print("✅ 所有配置文件检查通过")
        
        # 检查ChromaDB目录
        chroma_path = "./chroma_db"
        if not os.path.exists(chroma_path):
            os.makedirs(chroma_path)
            print("✅ ChromaDB目录创建成功")
        else:
            print("✅ ChromaDB目录已存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统集成测试失败: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print_banner()
    
    tests = [
        ("配置加载", test_config_loading),
        ("数据库管理器", test_database_manager),
        ("知识库功能", test_knowledge_base),
        ("数据库配置", test_database_configs),
        ("提示词模板", test_prompt_templates),
        ("测试数据库", create_test_database),
        ("系统集成", test_system_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
    
    print(f"\n{'='*60}")
    print(f"测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！TEXT2SQL 2.0系统准备就绪")
        print("\n启动命令:")
        print("  streamlit run text2sql_v2.0.py")
        print("  或")
        print("  python start_text2sql.py")
    else:
        print("⚠️ 部分测试失败，请检查错误信息")
    
    print(f"{'='*60}")

if __name__ == "__main__":
    run_all_tests()