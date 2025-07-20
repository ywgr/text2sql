#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动增强版Text2SQL V2.3系统
包含通用产品匹配功能
"""

import subprocess
import sys
import os

def main():
    """启动系统"""
    print("🚀 启动Text2SQL V2.3 Enhanced - 通用产品匹配系统")
    print("=" * 60)
    
    # 检查文件是否存在
    if not os.path.exists("text2sql_v2.3_enhanced.py"):
        print("❌ 错误: text2sql_v2.3_enhanced.py 文件不存在")
        return
    
    print("✅ 系统特性:")
    print("   - 支持所有产品: 510S、geek、小新、拯救者、AIO等")
    print("   - 智能单表查询优化")
    print("   - 正确的时间格式处理")
    print("   - 产品层级理解: MODEL → [ROADMAP FAMILY] → [GROUP]")
    print("   - 实时SQL分析和验证")
    
    print("\n🌐 启动Streamlit界面...")
    
    try:
        # 启动Streamlit应用
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "text2sql_v2.3_enhanced.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
    except KeyboardInterrupt:
        print("\n👋 系统已停止")

if __name__ == "__main__":
    main()