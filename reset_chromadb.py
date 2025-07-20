#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重置ChromaDB的脚本
"""

import os
import shutil

def reset_chromadb():
    """完全重置ChromaDB"""
    print("重置ChromaDB...")
    
    # 要清理的目录列表
    directories_to_clean = [
        "./chroma_db",
        "./chroma_db_fallback",
        "./chroma_db_backup"
    ]
    
    # 查找所有可能的ChromaDB目录
    for item in os.listdir("."):
        if item.startswith("chroma_db"):
            directories_to_clean.append(f"./{item}")
    
    # 删除所有ChromaDB目录
    for directory in directories_to_clean:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"已删除目录: {directory}")
            except Exception as e:
                print(f"删除目录失败 {directory}: {e}")
    
    # 重新创建主目录
    os.makedirs("./chroma_db", exist_ok=True)
    print("已重新创建 ./chroma_db 目录")
    
    # 重置ChromaDB内存状态
    try:
        import chromadb
        chromadb.reset()
        print("已重置ChromaDB内存状态")
    except Exception as e:
        print(f"重置ChromaDB内存状态失败: {e}")
    
    print("ChromaDB重置完成！")

if __name__ == "__main__":
    reset_chromadb()