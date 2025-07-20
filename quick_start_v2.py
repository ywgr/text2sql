#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL V2.0 快速启动脚本
"""

import subprocess
import sys
import os

def print_banner():
    """打印启动横幅"""
    banner = """
================================================================
                TEXT2SQL系统 V2.0 快速启动                      
================================================================
"""
    print(banner)

def check_dependencies():
    """检查依赖包"""
    required_packages = [
        'streamlit', 'vanna', 'pandas', 'plotly', 
        'chromadb', 'pyodbc', 'sqlalchemy'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def check_files():
    """检查必要文件"""
    required_files = [
        'text2sql_v2.0.py',
        'config_local.py'
    ]
    
    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
    
    return missing

def create_basic_config():
    """创建基础配置文件"""
    try:
        # 创建测试数据库
        import sqlite3
        conn = sqlite3.connect("test_database.db")
        cursor = conn.cursor()
        
        # 创建示例表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            age INTEGER
        )
        """)
        
        cursor.execute("""
        INSERT OR REPLACE INTO users VALUES 
        (1, '张三', 'zhangsan@example.com', 25),
        (2, '李四', 'lisi@example.com', 30),
        (3, '王五', 'wangwu@example.com', 28)
        """)
        
        conn.commit()
        conn.close()
        print("✅ 创建测试数据库成功")
        
        # 创建ChromaDB目录
        os.makedirs("chroma_db", exist_ok=True)
        print("✅ 创建ChromaDB目录成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建配置失败: {e}")
        return False

def start_system():
    """启动系统"""
    print("🚀 启动TEXT2SQL V2.0系统...")
    print("🌐 浏览器将自动打开 http://localhost:8501")
    print("⏹️ 按 Ctrl+C 停止服务")
    print("-" * 60)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "text2sql_v2.0.py",
            "--server.port=8501",
            "--server.address=localhost"
        ])
        return True
    except KeyboardInterrupt:
        print("\n👋 系统已停止")
        return True
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

def main():
    """主函数"""
    print_banner()
    
    print("🔍 检查系统环境...")
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"❌ 缺少依赖包: {', '.join(missing_deps)}")
        print("请运行: pip install -r requirements.txt")
        return
    else:
        print("✅ 依赖包检查通过")
    
    # 检查文件
    missing_files = check_files()
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        return
    else:
        print("✅ 文件检查通过")
    
    # 创建基础配置
    if create_basic_config():
        print("✅ 基础配置创建成功")
    else:
        print("⚠️ 基础配置创建失败，但可以继续")
    
    print("\n" + "="*60)
    print("🎉 TEXT2SQL V2.0 准备就绪！")
    print("="*60)
    
    # 启动系统
    start_system()

if __name__ == "__main__":
    main()