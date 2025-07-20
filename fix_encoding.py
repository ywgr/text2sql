#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复Windows编码问题的脚本
"""

import os
import sys

def set_utf8_encoding():
    """设置UTF-8编码"""
    if sys.platform.startswith('win'):
        # Windows系统设置UTF-8编码
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        # 尝试设置控制台编码
        try:
            import subprocess
            subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
            print("已设置控制台编码为UTF-8")
        except:
            pass

def main():
    """主函数"""
    print("修复Windows编码问题...")
    set_utf8_encoding()
    
    print("现在可以运行以下命令:")
    print("python quick_start.py")

if __name__ == "__main__":
    main()