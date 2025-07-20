#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的启动脚本，避免Unicode字符
"""

import subprocess
import sys
import os

def main():
    print("TEXT2SQL Local System Starter")
    print("=" * 40)
    
    # 检查主程序文件
    if not os.path.exists("text2sql_local_deepseek.py"):
        print("ERROR: Main program file not found: text2sql_local_deepseek.py")
        return
    
    print("Found main program file")
    
    # 检查配置文件
    if not os.path.exists("config_local.py"):
        print("WARNING: Config file not found, using defaults")
    else:
        print("Found config file")
    
    # 创建必要目录
    os.makedirs("chroma_db", exist_ok=True)
    print("Created chroma_db directory")
    
    # 启动Streamlit
    print("Starting Streamlit server...")
    print("Browser will open at http://localhost:8501")
    print("Press Ctrl+C to stop")
    print("-" * 40)
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "text2sql_local_deepseek.py",
            "--server.port=8501",
            "--server.address=localhost"
        ])
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
    except Exception as e:
        print(f"ERROR: Failed to start system: {e}")

if __name__ == "__main__":
    main()