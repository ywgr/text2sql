#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地TEXT2SQL系统配置文件
"""

import os

class LocalConfig:
    """本地部署配置"""
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY = "sk-0e6005b793aa4759bb022b91e9055f86"
    DEEPSEEK_MODEL = "deepseek-chat"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    
    # ChromaDB配置
    CHROMA_DB_PATH = "./chroma_db"
    CHROMA_COLLECTION_NAME = "text2sql_knowledge"
    CHROMA_PERSIST = True
    
    # SQLite数据库配置
    SQLITE_DB_FILE = "test_database.db"
    
    # 系统配置
    LOG_LEVEL = "INFO"
    MAX_TOKENS = 1000
    TEMPERATURE = 0.1
    
    # Streamlit配置
    PAGE_TITLE = "TEXT2SQL系统 - 本地部署版"
    PAGE_ICON = "🏠"
    LAYOUT = "wide"
    
    @classmethod
    def get_chroma_config(cls):
        """获取ChromaDB配置"""
        return {
            "api_key": cls.DEEPSEEK_API_KEY,
            "model": cls.DEEPSEEK_MODEL,
            "path": cls.CHROMA_DB_PATH,
            "collection_name": cls.CHROMA_COLLECTION_NAME
        }
    
    @classmethod
    def get_deepseek_config(cls):
        """获取DeepSeek配置"""
        return {
            "api_key": cls.DEEPSEEK_API_KEY,
            "model": cls.DEEPSEEK_MODEL,
            "base_url": cls.DEEPSEEK_BASE_URL,
            "max_tokens": cls.MAX_TOKENS,
            "temperature": cls.TEMPERATURE
        }
    
    @classmethod
    def create_directories(cls):
        """创建必要的目录"""
        os.makedirs(cls.CHROMA_DB_PATH, exist_ok=True)
        print(f"✅ 创建ChromaDB目录: {cls.CHROMA_DB_PATH}")
    
    @classmethod
    def validate_config(cls):
        """验证配置"""
        errors = []
        
        if not cls.DEEPSEEK_API_KEY or cls.DEEPSEEK_API_KEY == "your_api_key_here":
            errors.append("请设置有效的DeepSeek API Key")
        
        if not cls.CHROMA_DB_PATH:
            errors.append("请设置ChromaDB存储路径")
        
        if not cls.SQLITE_DB_FILE:
            errors.append("请设置SQLite数据库文件名")
        
        return errors

# 环境变量覆盖
if os.getenv("DEEPSEEK_API_KEY"):
    LocalConfig.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if os.getenv("CHROMA_DB_PATH"):
    LocalConfig.CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")

if os.getenv("SQLITE_DB_FILE"):
    LocalConfig.SQLITE_DB_FILE = os.getenv("SQLITE_DB_FILE")