#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动本地TEXT2SQL系统
"""

import subprocess
import sys
import os

def check_dependencies():
    """检查依赖包"""
    required_packages = [
        'streamlit',
        'vanna',
        'pandas',
        'plotly',
        'chromadb',
        'openai'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n缺少以下依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """主函数"""
    print("TEXT2SQL本地部署系统启动器")
    print("=" * 50)
    
    # 检查依赖
    print("检查依赖包...")
    if not check_dependencies():
        sys.exit(1)
    
    print("\n✅ 所有依赖包已安装")
    
    # 检查配置文件
    if not os.path.exists("text2sql_local_deepseek.py"):
        print("❌ 找不到主程序文件: text2sql_local_deepseek.py")
        sys.exit(1)
    
    print("✅ 主程序文件存在")
    
    # 启动Streamlit应用
    print("\n启动本地TEXT2SQL系统...")
    print("浏览器将自动打开 http://localhost:8501")
    print("按 Ctrl+C 停止服务")
    print("-" * 50)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "text2sql_local_deepseek.py",
            "--server.port=8501",
            "--server.address=localhost"
        ])
    except KeyboardInterrupt:
        print("\n系统已停止")

if __name__ == "__main__":
    main()