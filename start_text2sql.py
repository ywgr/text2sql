#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统启动器
支持选择1.0或2.0版本
"""

import subprocess
import sys
import os

def print_banner():
    """打印启动横幅"""
    banner = """
================================================================
                    TEXT2SQL智能查询系统                          
                      版本选择启动器                             
================================================================
"""
    print(banner)

def show_version_info():
    """显示版本信息"""
    print("📋 版本对比:")
    print()
    print("🔹 1.0版本 (稳定版)")
    print("  - SQLite数据库支持")
    print("  - 基础业务规则管理")
    print("  - Vanna + DeepSeek双AI")
    print("  - 提示词自定义")
    print("  - 适合: 学习、测试、小型项目")
    print()
    print("🔹 2.0版本 (企业版)")
    print("  - 多数据库支持 (SQLite + MSSQL)")
    print("  - 企业级数据库管理")
    print("  - 双知识库系统")
    print("  - 表结构管理")
    print("  - 产品知识库")
    print("  - 适合: 企业环境、生产系统")
    print()

def check_dependencies_v1():
    """检查1.0版本依赖"""
    required_v1 = ['streamlit', 'vanna', 'pandas', 'plotly', 'chromadb']
    missing = []
    
    for package in required_v1:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def check_dependencies_v2():
    """检查2.0版本依赖"""
    required_v2 = ['streamlit', 'vanna', 'pandas', 'plotly', 'chromadb', 'pyodbc', 'sqlalchemy']
    missing = []
    
    for package in required_v2:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def install_dependencies():
    """安装依赖包"""
    print("📦 安装依赖包...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        print("✅ 依赖包安装完成")
        return True
    except subprocess.CalledProcessError:
        print("❌ 依赖包安装失败")
        return False

def start_version(version):
    """启动指定版本"""
    if version == "1.0":
        file_name = "text2sql_v1.0.py"
        if not os.path.exists(file_name):
            file_name = "text2sql_local_deepseek.py"  # 备用文件名
    else:
        file_name = "text2sql_v2.0.py"
    
    if not os.path.exists(file_name):
        print(f"❌ 找不到文件: {file_name}")
        return False
    
    print(f"🚀 启动TEXT2SQL {version}版本...")
    print("🌐 浏览器将自动打开 http://localhost:8501")
    print("⏹️ 按 Ctrl+C 停止服务")
    print("-" * 60)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            file_name,
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
    show_version_info()
    
    while True:
        print("🔧 请选择操作:")
        print("1. 启动 1.0版本 (稳定版)")
        print("2. 启动 2.0版本 (企业版)")
        print("3. 检查依赖包")
        print("4. 安装依赖包")
        print("5. 退出")
        
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == "1":
            # 检查1.0版本依赖
            missing = check_dependencies_v1()
            if missing:
                print(f"❌ 缺少依赖包: {', '.join(missing)}")
                print("请先选择选项4安装依赖包")
                continue
            
            start_version("1.0")
            break
            
        elif choice == "2":
            # 检查2.0版本依赖
            missing = check_dependencies_v2()
            if missing:
                print(f"❌ 缺少依赖包: {', '.join(missing)}")
                print("请先选择选项4安装依赖包")
                continue
            
            start_version("2.0")
            break
            
        elif choice == "3":
            # 检查依赖
            print("\n📋 依赖检查结果:")
            
            missing_v1 = check_dependencies_v1()
            if missing_v1:
                print(f"❌ 1.0版本缺少: {', '.join(missing_v1)}")
            else:
                print("✅ 1.0版本依赖完整")
            
            missing_v2 = check_dependencies_v2()
            if missing_v2:
                print(f"❌ 2.0版本缺少: {', '.join(missing_v2)}")
            else:
                print("✅ 2.0版本依赖完整")
            
            print()
            
        elif choice == "4":
            # 安装依赖
            install_dependencies()
            print()
            
        elif choice == "5":
            print("👋 再见!")
            break
            
        else:
            print("❌ 无效选择，请重新输入")
            print()

if __name__ == "__main__":
    main()