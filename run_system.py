#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统启动脚本
"""

import subprocess
import sys
import os

def check_requirements():
    """检查必要的依赖包"""
    required_packages = [
        'streamlit', 'vanna', 'pandas', 'mysql.connector', 
        'plotly', 'requests', 'sqlparse'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'mysql.connector':
                import mysql.connector
            else:
                __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n缺少以下包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def run_streamlit():
    """启动Streamlit应用"""
    try:
        print("🚀 启动TEXT2SQL系统...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "text2sql_system.py"])
    except KeyboardInterrupt:
        print("\n👋 系统已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def main():
    """主函数"""
    print("=== TEXT2SQL系统启动器 ===")
    
    # 检查依赖
    if not check_requirements():
        return
    
    # 检查数据库设置文件
    if not os.path.exists("text2sql_system.py"):
        print("❌ 找不到 text2sql_system.py 文件")
        return
    
    print("\n📋 使用说明:")
    print("1. 确保MySQL服务已启动")
    print("2. 如果是首次使用，请先运行 setup_database.py 初始化数据库")
    print("3. 在系统中修改数据库连接参数（用户名、密码等）")
    print("4. 系统将在浏览器中打开")
    
    input("\n按回车键继续启动系统...")
    
    # 启动系统
    run_streamlit()

if __name__ == "__main__":
    main()