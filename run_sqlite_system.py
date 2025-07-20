#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统启动脚本 - SQLite版本
"""

import subprocess
import sys
import os

def main():
    print("🚀 启动TEXT2SQL系统 (SQLite版)")
    print("=" * 40)
    print("✅ 无需MySQL安装")
    print("✅ 数据库自动创建")
    print("✅ 包含测试数据")
    print("✅ 即开即用")
    print()
    
    if not os.path.exists("sqlite_alternative.py"):
        print("❌ 找不到 sqlite_alternative.py 文件")
        return
    
    print("📋 系统功能:")
    print("- 🔍 中文自然语言转SQL")
    print("- 📊 自动数据可视化")
    print("- 🤖 AI驱动查询生成")
    print("- 📈 智能数据分析")
    print()
    
    input("按回车键启动系统...")
    
    try:
        print("🌐 正在启动Web界面...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "sqlite_alternative.py"])
    except KeyboardInterrupt:
        print("\n👋 系统已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()