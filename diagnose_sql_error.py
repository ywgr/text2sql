#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SQL执行错误诊断脚本
帮助排查"查询失败: 数据库连接或SQL执行错误"的具体原因
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

def diagnose_sql_error():
    """诊断SQL执行错误"""
    print("=== SQL执行错误诊断 ===")
    
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
    
    # 3. 测试数据库连接
    print("\n3. 测试数据库连接...")
    
    # 测试默认MSSQL配置
    default_config = {
        "type": "mssql",
        "config": {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF", 
            "username": "FF_User",
            "password": "Grape!0808",
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
    }
    
    print("测试默认MSSQL配置...")
    try:
        success, message = db_manager.test_connection("mssql", default_config["config"])
        print(f"连接结果: {success}, 消息: {message}")
        
        if success:
            print("✅ 数据库连接成功")
        else:
            print("❌ 数据库连接失败")
            print("可能的原因:")
            print("   - 网络连接问题")
            print("   - 数据库服务器不可达")
            print("   - 用户名/密码错误")
            print("   - 数据库名称错误")
            print("   - ODBC驱动未安装")
            
    except Exception as e:
        print(f"❌ 连接测试异常: {e}")
        print("详细错误信息:")
        print(traceback.format_exc())
    
    # 4. 测试简单SQL执行
    print("\n4. 测试简单SQL执行...")
    if success:
        try:
            test_sql = "SELECT TOP 1 * FROM CONPD"
            print(f"执行测试SQL: {test_sql}")
            
            success, df, message = system.execute_sql(test_sql, default_config)
            print(f"执行结果: {success}")
            print(f"消息: {message}")
            
            if success:
                print("✅ 简单SQL执行成功")
                print(f"返回数据行数: {len(df)}")
                if not df.empty:
                    print("数据预览:")
                    print(df.head())
            else:
                print("❌ 简单SQL执行失败")
                print("可能的原因:")
                print("   - 表不存在")
                print("   - 权限不足")
                print("   - SQL语法错误")
                print("   - 数据库连接中断")
                
        except Exception as e:
            print(f"❌ SQL执行异常: {e}")
            print("详细错误信息:")
            print(traceback.format_exc())
    
    # 5. 检查ODBC驱动
    print("\n5. 检查ODBC驱动...")
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        print("可用的ODBC驱动:")
        for driver in drivers:
            print(f"   - {driver}")
        
        if "ODBC Driver 18 for SQL Server" in drivers:
            print("✅ ODBC Driver 18 for SQL Server 已安装")
        elif "ODBC Driver 17 for SQL Server" in drivers:
            print("⚠️ 使用ODBC Driver 17 for SQL Server (建议升级到18)")
        else:
            print("❌ 未找到SQL Server ODBC驱动")
            print("请安装 Microsoft ODBC Driver for SQL Server")
            
    except ImportError:
        print("❌ pyodbc未安装")
        print("请运行: pip install pyodbc")
    except Exception as e:
        print(f"❌ 检查ODBC驱动失败: {e}")
    
    # 6. 检查网络连接
    print("\n6. 检查网络连接...")
    try:
        import socket
        host = "10.97.34.39"
        port = 1433  # SQL Server默认端口
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ 网络连接正常: {host}:{port}")
        else:
            print(f"❌ 网络连接失败: {host}:{port}")
            print("可能的原因:")
            print("   - 服务器不可达")
            print("   - 防火墙阻止")
            print("   - 端口被占用")
            
    except Exception as e:
        print(f"❌ 网络连接检查失败: {e}")
    
    # 7. 提供解决方案
    print("\n7. 解决方案建议...")
    print("如果遇到'查询失败: 数据库连接或SQL执行错误'，请按以下步骤排查:")
    print("\n1. 检查数据库连接:")
    print("   - 确认服务器地址: 10.97.34.39")
    print("   - 确认数据库名: FF_IDSS_Dev_FF")
    print("   - 确认用户名: FF_User")
    print("   - 确认密码: Grape!0808")
    
    print("\n2. 检查ODBC驱动:")
    print("   - 安装 Microsoft ODBC Driver 18 for SQL Server")
    print("   - 或使用 ODBC Driver 17 for SQL Server")
    
    print("\n3. 检查网络:")
    print("   - 确认能访问 10.97.34.39:1433")
    print("   - 检查防火墙设置")
    
    print("\n4. 检查SQL语法:")
    print("   - 确认表名正确")
    print("   - 确认字段名正确")
    print("   - 确认SQL语法符合SQL Server标准")
    
    print("\n5. 检查权限:")
    print("   - 确认用户有查询权限")
    print("   - 确认用户有访问表的权限")

if __name__ == "__main__":
    diagnose_sql_error() 