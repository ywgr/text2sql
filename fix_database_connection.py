#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库连接修复脚本
尝试不同的连接配置来解决登录失败问题
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

def test_different_connections():
    """测试不同的数据库连接配置"""
    print("=== 数据库连接修复测试 ===")
    
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
    
    # 3. 测试不同的连接配置
    print("\n3. 测试不同的连接配置...")
    
    # 配置列表
    configs = [
        {
            "name": "原始配置",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "username": "FF_User",
                "password": "Grape!0808",
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        },
        {
            "name": "尝试不同用户名",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "username": "ff_user",  # 小写
                "password": "Grape!0808",
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        },
        {
            "name": "尝试不同密码",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "username": "FF_User",
                "password": "grape!0808",  # 小写
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        },
        {
            "name": "尝试Windows认证",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes",
                "trusted_connection": "yes"
            }
        },
        {
            "name": "尝试不同数据库",
            "config": {
                "server": "10.97.34.39",
                "database": "master",  # 尝试master数据库
                "username": "FF_User",
                "password": "Grape!0808",
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        },
        {
            "name": "尝试ODBC Driver 17",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "username": "FF_User",
                "password": "Grape!0808",
                "driver": "ODBC Driver 17 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        },
        {
            "name": "尝试启用加密",
            "config": {
                "server": "10.97.34.39",
                "database": "FF_IDSS_Dev_FF", 
                "username": "FF_User",
                "password": "Grape!0808",
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "yes",
                "trust_server_certificate": "yes"
            }
        }
    ]
    
    successful_configs = []
    
    for i, config_info in enumerate(configs, 1):
        print(f"\n{i}. 测试配置: {config_info['name']}")
        print(f"   配置: {config_info['config']}")
        
        try:
            success, message = db_manager.test_connection("mssql", config_info["config"])
            print(f"   结果: {'✅ 成功' if success else '❌ 失败'}")
            print(f"   消息: {message}")
            
            if success:
                successful_configs.append(config_info)
                print("   ✅ 此配置可用！")
                
                # 测试简单SQL
                test_config = {"type": "mssql", "config": config_info["config"]}
                test_sql = "SELECT TOP 1 * FROM CONPD"
                print(f"   测试SQL: {test_sql}")
                
                sql_success, df, sql_message = system.execute_sql(test_sql, test_config)
                print(f"   SQL执行: {'✅ 成功' if sql_success else '❌ 失败'}")
                print(f"   SQL消息: {sql_message}")
                
                if sql_success:
                    print(f"   返回数据行数: {len(df)}")
                    if not df.empty:
                        print("   数据预览:")
                        print(df.head())
                
        except Exception as e:
            print(f"   ❌ 异常: {e}")
    
    # 4. 总结结果
    print(f"\n4. 测试总结...")
    print(f"总共测试了 {len(configs)} 种配置")
    print(f"成功配置数量: {len(successful_configs)}")
    
    if successful_configs:
        print("\n✅ 成功的配置:")
        for config in successful_configs:
            print(f"   - {config['name']}")
            print(f"     配置: {config['config']}")
    else:
        print("\n❌ 所有配置都失败了")
        print("建议:")
        print("1. 联系数据库管理员确认正确的用户名和密码")
        print("2. 确认数据库服务器状态")
        print("3. 检查网络连接和防火墙设置")
        print("4. 确认ODBC驱动安装正确")
    
    # 5. 生成修复建议
    print("\n5. 修复建议...")
    if successful_configs:
        best_config = successful_configs[0]
        print(f"推荐使用配置: {best_config['name']}")
        print("请更新数据库配置文件中的连接信息")
        
        # 生成新的配置文件
        new_config = {
            "type": "mssql",
            "config": best_config["config"]
        }
        
        config_file = "fixed_db_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            print(f"✅ 已生成修复后的配置文件: {config_file}")
        except Exception as e:
            print(f"❌ 生成配置文件失败: {e}")
    else:
        print("需要手动修复数据库连接配置")
        print("请检查:")
        print("1. 用户名和密码是否正确")
        print("2. 数据库名称是否正确")
        print("3. 服务器地址是否正确")
        print("4. 网络连接是否正常")

if __name__ == "__main__":
    test_different_connections() 