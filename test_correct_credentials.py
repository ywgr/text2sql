#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试正确的数据库凭据
使用正确的用户名和密码测试数据库连接
"""

import json
import os
import traceback
from text2sql_2_5_query import Text2SQLQueryEngine, VannaWrapper, DatabaseManager

def load_json(path):
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件 {path} 不存在")
        return {}
    except Exception as e:
        print(f"加载 {path} 失败: {e}")
        return {}

def test_correct_credentials():
    """测试正确的数据库凭据"""
    print("=== 测试正确的数据库凭据 ===")
    
    # 1. 加载知识库
    print("\n1. 加载知识库...")
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json')
    
    # 2. 初始化系统
    print("\n2. 初始化系统...")
    vanna = VannaWrapper()
    db_manager = DatabaseManager()
    
    system = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=relationships,
        business_rules=business_rules,
        product_knowledge=product_knowledge,
        historical_qa=historical_qa,
        vanna=vanna,
        db_manager=db_manager,
        prompt_templates={}
    )
    
    # 3. 使用正确的凭据测试连接
    print("\n3. 使用正确的凭据测试连接...")
    
    correct_config = {
        "type": "mssql",
        "config": {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF", 
            "username": "AI_User",  # 正确的用户名
            "password": "D!O$LYHSVNSL",  # 正确的密码
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
    }
    
    print("测试配置:")
    print(f"   服务器: {correct_config['config']['server']}")
    print(f"   数据库: {correct_config['config']['database']}")
    print(f"   用户名: {correct_config['config']['username']}")
    print(f"   密码: {correct_config['config']['password']}")
    print(f"   驱动: {correct_config['config']['driver']}")
    
    try:
        # 测试数据库连接
        print("\n测试数据库连接...")
        success, message = db_manager.test_connection("mssql", correct_config["config"])
        print(f"连接结果: {'✅ 成功' if success else '❌ 失败'}")
        print(f"连接消息: {message}")
        
        if success:
            print("✅ 数据库连接成功！")
            
            # 测试简单SQL查询
            print("\n测试简单SQL查询...")
            test_sql = "SELECT TOP 1 * FROM CONPD"
            print(f"执行SQL: {test_sql}")
            
            sql_success, df, sql_message = system.execute_sql(test_sql, correct_config)
            print(f"SQL执行结果: {'✅ 成功' if sql_success else '❌ 失败'}")
            print(f"SQL消息: {sql_message}")
            
            if sql_success:
                print(f"✅ SQL执行成功！")
                print(f"返回数据行数: {len(df)}")
                if not df.empty:
                    print("数据预览:")
                    print(df.head())
                    
                # 测试更多表
                print("\n测试更多表的访问...")
                test_tables = ["备货NY", "ConDT_Commit", "ConDT_Open_PO"]
                
                for table in test_tables:
                    test_sql = f"SELECT TOP 1 * FROM {table}"
                    print(f"测试表 {table}: {test_sql}")
                    
                    sql_success, df, sql_message = system.execute_sql(test_sql, correct_config)
                    if sql_success:
                        print(f"   ✅ {table} 表访问成功")
                    else:
                        print(f"   ❌ {table} 表访问失败: {sql_message}")
                
                # 生成修复后的配置文件
                print("\n生成修复后的配置文件...")
                fixed_config = {
                    "type": "mssql",
                    "config": correct_config["config"],
                    "description": "使用正确凭据的数据库配置"
                }
                
                config_file = "fixed_db_config.json"
                try:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(fixed_config, f, ensure_ascii=False, indent=2)
                    print(f"✅ 已生成修复后的配置文件: {config_file}")
                except Exception as e:
                    print(f"❌ 生成配置文件失败: {e}")
                    
            else:
                print("❌ SQL执行失败")
                print("可能的原因:")
                print("   - 表不存在")
                print("   - 权限不足")
                print("   - SQL语法错误")
        else:
            print("❌ 数据库连接失败")
            print("请检查:")
            print("   - 用户名和密码是否正确")
            print("   - 数据库名称是否正确")
            print("   - 服务器地址是否正确")
            
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        print("详细错误信息:")
        print(traceback.format_exc())
    
    # 4. 总结
    print("\n4. 测试总结...")
    if success:
        print("✅ 数据库连接问题已解决！")
        print("现在可以使用正确的凭据进行SQL查询了。")
        print("\n下一步:")
        print("1. 在UI中使用新的数据库配置")
        print("2. 测试SQL生成和查询功能")
        print("3. 验证所有功能正常工作")
    else:
        print("❌ 数据库连接仍有问题")
        print("请检查网络连接和服务器状态")

if __name__ == "__main__":
    test_correct_credentials() 