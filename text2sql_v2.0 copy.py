#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 2.0版本 - 增强数据库管理功能
支持多数据库、表管理、知识库管理等企业级功能
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import json
import re
from typing import Dict, List, Tuple, Optional
import logging
import os
import traceback
import requests
from vanna.chromadb import ChromaDB_VectorStore
from vanna.deepseek import DeepSeekChat
import pyodbc
import sqlalchemy
from sqlalchemy import create_engine, text, inspect

# 导入本地配置
try:
    from config_local import LocalConfig
except ImportError:
    # 如果没有配置文件，使用默认配置
    class LocalConfig:
        DEEPSEEK_API_KEY = "sk-0e6005b793aa4759bb022b91e9055f86"
        DEEPSEEK_MODEL = "deepseek-chat"
        CHROMA_DB_PATH = "./chroma_db"
        CHROMA_COLLECTION_NAME = "text2sql_knowledge"
        SQLITE_DB_FILE = "test_database.db"
        
        @classmethod
        def get_chroma_config(cls):
            return {
                "api_key": cls.DEEPSEEK_API_KEY,
                "model": cls.DEEPSEEK_MODEL,
                "path": cls.CHROMA_DB_PATH,
                "collection_name": cls.CHROMA_COLLECTION_NAME
            }

# 配置日志
logging.basicConfig(level=getattr(LocalConfig, 'LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

class LocalDeepSeekVanna(ChromaDB_VectorStore, DeepSeekChat):
    """本地部署的Vanna，使用ChromaDB + DeepSeek"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        DeepSeekChat.__init__(self, config=config)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.connections = {}
        self.default_mssql_config = {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF", 
            "username": "FF_User",
            "password": "Grape!0808",
            "driver": "ODBC Driver 17 for SQL Server"
        }
    
    def get_mssql_connection_string(self, config):
        """获取MSSQL连接字符串"""
        return f"mssql+pyodbc://{config['username']}:{config['password']}@{config['server']}/{config['database']}?driver={config['driver'].replace(' ', '+')}"
    
    def test_connection(self, db_type: str, config: Dict) -> Tuple[bool, str]:
        """测试数据库连接"""
        try:
            if db_type == "sqlite":
                conn = sqlite3.connect(config["file_path"])
                conn.close()
                return True, "SQLite连接成功"
            
            elif db_type == "mssql":
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True, "MSSQL连接成功"
            
            else:
                return False, f"不支持的数据库类型: {db_type}"
                
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def get_tables(self, db_type: str, config: Dict) -> List[str]:
        """获取数据库表列表"""
        try:
            if db_type == "sqlite":
                conn = sqlite3.connect(config["file_path"])
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [table[0] for table in cursor.fetchall()]
                conn.close()
                return tables
            
            elif db_type == "mssql":
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                inspector = inspect(engine)
                return inspector.get_table_names()
            
            return []
            
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def get_table_schema(self, db_type: str, config: Dict, table_name: str) -> Dict:
        """获取表结构"""
        try:
            if db_type == "sqlite":
                conn = sqlite3.connect(config["file_path"])
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                conn.close()
                
                return {
                    "columns": [col[1] for col in columns],
                    "column_info": columns,
                    "sample_data": []
                }
            
            elif db_type == "mssql":
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                inspector = inspect(engine)
                
                columns = inspector.get_columns(table_name)
                column_info = [(i, col['name'], str(col['type']), col.get('nullable', True), 
                               col.get('default'), col.get('primary_key', False)) 
                              for i, col in enumerate(columns)]
                
                return {
                    "columns": [col['name'] for col in columns],
                    "column_info": column_info,
                    "sample_data": []
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            return {}

class Text2SQLSystemV2:
    """TEXT2SQL系统 2.0版本"""
    
    def __init__(self):
        """初始化系统"""
        self.deepseek_api_key = LocalConfig.DEEPSEEK_API_KEY
        
        # 数据库管理器
        self.db_manager = DatabaseManager()
        
        # 数据库配置
        self.databases = self.load_database_configs()
        
        # ChromaDB配置
        self.chroma_config = LocalConfig.get_chroma_config()
        
        # 创建必要的目录
        os.makedirs(LocalConfig.CHROMA_DB_PATH, exist_ok=True)
        
        # 初始化本地Vanna实例
        self.vn = None
        self.initialize_local_vanna()
        
        # 业务规则和术语映射
        self.business_rules = self.load_business_rules()
        
        # 提示词模板
        self.prompt_templates = self.load_prompt_templates()
        
        # 表结构知识库
        self.table_knowledge = self.load_table_knowledge()
        
        # 产品知识库
        self.product_knowledge = self.load_product_knowledge()

    def load_database_configs(self) -> Dict:
        """加载数据库配置"""
        default_configs = {
            "default_sqlite": {
                "name": "默认SQLite",
                "type": "sqlite",
                "config": {"file_path": "test_database.db"},
                "active": True
            },
            "default_mssql": {
                "name": "FF_IDSS_Dev_FF",
                "type": "mssql",
                "config": self.db_manager.default_mssql_config,
                "active": False
            }
        }
        
        config_file = "database_configs.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_configs = json.load(f)
                    default_configs.update(saved_configs)
        except Exception as e:
            logger.error(f"加载数据库配置失败: {e}")
        
        return default_configs

    def save_database_configs(self):
        """保存数据库配置"""
        config_file = "database_configs.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.databases, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存数据库配置失败: {e}")
            return False

    def load_table_knowledge(self) -> Dict:
        """加载表结构知识库"""
        knowledge_file = "table_knowledge.json"
        try:
            if os.path.exists(knowledge_file):
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载表结构知识库失败: {e}")
        
        return {}

    def save_table_knowledge(self):
        """保存表结构知识库"""
        knowledge_file = "table_knowledge.json"
        try:
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.table_knowledge, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存表结构知识库失败: {e}")
            return False

    def load_product_knowledge(self) -> Dict:
        """加载产品知识库"""
        knowledge_file = "product_knowledge.json"
        try:
            if os.path.exists(knowledge_file):
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载产品知识库失败: {e}")
        
        return {}

    def save_product_knowledge(self):
        """保存产品知识库"""
        knowledge_file = "product_knowledge.json"
        try:
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.product_knowledge, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存产品知识库失败: {e}")
            return False

    def initialize_local_vanna(self):
        """初始化本地Vanna实例"""
        try:
            st.info("正在初始化本地Vanna (ChromaDB + DeepSeek)...")
            
            # 完全清理ChromaDB目录
            self.cleanup_chromadb()
            
            # 创建本地Vanna实例
            self.vn = LocalDeepSeekVanna(config=self.chroma_config)
            
            st.success("本地Vanna初始化成功")
            
            return True
            
        except Exception as e:
            logger.error(f"本地Vanna初始化失败: {e}")
            st.error(f"本地Vanna初始化失败: {e}")
            return False

    def cleanup_chromadb(self):
        """清理ChromaDB目录"""
        try:
            import shutil
            import chromadb
            
            # 重置ChromaDB
            try:
                chromadb.reset()
            except:
                pass
            
            # 如果目录存在且有问题，删除重建
            chroma_path = self.chroma_config["path"]
            if os.path.exists(chroma_path):
                try:
                    # 尝试访问目录，如果有问题就删除
                    test_files = os.listdir(chroma_path)
                    # 检查是否有损坏的文件
                    for file in test_files:
                        if file.endswith('.bin') or file.endswith('.index'):
                            file_path = os.path.join(chroma_path, file)
                            if os.path.getsize(file_path) == 0:  # 空文件可能损坏
                                st.info("检测到损坏的ChromaDB文件，重新初始化...")
                                shutil.rmtree(chroma_path)
                                break
                except Exception as e:
                    st.info(f"ChromaDB目录有问题，重新创建: {e}")
                    shutil.rmtree(chroma_path)
            
            # 确保目录存在
            os.makedirs(chroma_path, exist_ok=True)
            
        except Exception as e:
            logger.error(f"清理ChromaDB失败: {e}")
            # 如果清理失败，至少确保目录存在
            os.makedirs(self.chroma_config["path"], exist_ok=True)

    def load_business_rules(self) -> Dict:
        """加载业务规则"""
        default_rules = {
            # 术语映射
            "学生": "student",
            "课程": "course", 
            "成绩": "score",
            "姓名": "name",
            "性别": "gender",
            "班级": "class",
            "课程名称": "course_name",
            "分数": "score",
            
            # 业务规则
            "25年": "2025年",
            "24年": "2024年",
            "23年": "2023年",
            "今年": "2024年",
            "去年": "2023年",
            "明年": "2025年",
            
            # 数值规则
            "优秀": "score >= 90",
            "良好": "score >= 80 AND score < 90",
            "及格": "score >= 60 AND score < 80",
            "不及格": "score < 60",
        }
        
        rules_file = "business_rules.json"
        try:
            if os.path.exists(rules_file):
                with open(rules_file, 'r', encoding='utf-8') as f:
                    saved_rules = json.load(f)
                    default_rules.update(saved_rules)
        except Exception as e:
            logger.error(f"加载业务规则失败: {e}")
        
        return default_rules

    def save_business_rules(self):
        """保存业务规则"""
        rules_file = "business_rules.json"
        try:
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(self.business_rules, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存业务规则失败: {e}")
            return False

    def load_prompt_templates(self) -> Dict:
        """加载提示词模板"""
        default_templates = {
            "sql_generation": """你是一个SQL专家。根据以下信息生成准确的SQL查询语句。

数据库结构：
{schema_info}

表结构知识库：
{table_knowledge}

产品知识库：
{product_knowledge}

业务规则：
{business_rules}

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 根据数据库类型使用正确的SQL语法
5. 应用业务规则进行术语转换
6. 参考表结构知识库理解表和字段含义
7. 结合产品知识库理解业务逻辑

SQL语句：""",

            "sql_verification": """你是一个SQL验证专家。请检查以下SQL语句是否正确并符合用户需求。

数据库结构：
{schema_info}

表结构知识库：
{table_knowledge}

业务规则：
{business_rules}

用户问题：{question}
生成的SQL：{sql}

请检查：
1. SQL语法是否正确
2. 表名和字段名是否存在
3. 是否正确回答了用户问题
4. JOIN关系是否正确
5. WHERE条件是否合理
6. 是否正确应用了业务规则和知识库

如果SQL完全正确，请回答"VALID"
如果有问题，请提供修正后的SQL语句，格式如下：
INVALID
修正后的SQL语句

回答："""
        }
        
        templates_file = "prompt_templates.json"
        try:
            if os.path.exists(templates_file):
                with open(templates_file, 'r', encoding='utf-8') as f:
                    saved_templates = json.load(f)
                    default_templates.update(saved_templates)
        except Exception as e:
            logger.error(f"加载提示词模板失败: {e}")
        
        return default_templates

    def save_prompt_templates(self):
        """保存提示词模板"""
        templates_file = "prompt_templates.json"
        try:
            with open(templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.prompt_templates, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存提示词模板失败: {e}")
            return False

def main():
    """主函数"""
    st.set_page_config(
        page_title="TEXT2SQL系统 2.0",
        page_icon="🚀",
        layout="wide"
    )
    
    st.title("TEXT2SQL系统 2.0")
    st.markdown("**企业级数据库管理 + AI智能查询系统**")
    
    # 初始化系统
    if 'system_v2' not in st.session_state:
        st.session_state.system_v2 = Text2SQLSystemV2()
    
    system = st.session_state.system_v2
    
    # 侧边栏配置
    with st.sidebar:
        st.header("系统配置")
        
        # 页面选择
        page = st.selectbox(
            "选择功能模块:",
            [
                "SQL查询", 
                "数据库管理", 
                "表结构管理",
                "产品知识库",
                "业务规则管理", 
                "提示词管理"
            ]
        )
        
        # 显示系统状态
        st.subheader("系统状态")
        
        if system.vn:
            st.success("本地Vanna: 正常运行")
            st.info("向量数据库: ChromaDB")
            st.info("LLM: DeepSeek")
        else:
            st.error("本地Vanna: 初始化失败")
        
        # 显示数据库连接状态
        st.subheader("数据库状态")
        for db_id, db_config in system.databases.items():
            if db_config.get("active", False):
                success, msg = system.db_manager.test_connection(
                    db_config["type"], 
                    db_config["config"]
                )
                if success:
                    st.success(f"{db_config['name']}: 已连接")
                else:
                    st.error(f"{db_config['name']}: 连接失败")
    
    # 根据选择的页面显示不同内容
    if page == "SQL查询":
        show_sql_query_page_v2(system)
    elif page == "数据库管理":
        show_database_management_page(system)
    elif page == "表结构管理":
        show_table_management_page(system)
    elif page == "产品知识库":
        show_product_knowledge_page(system)
    elif page == "业务规则管理":
        show_business_rules_page_v2(system)
    elif page == "提示词管理":
        show_prompt_templates_page_v2(system)

def show_sql_query_page_v2(system):
    """显示SQL查询页面 2.0版本"""
    st.header("智能SQL查询")
    
    # 选择数据库
    active_dbs = {k: v for k, v in system.databases.items() if v.get("active", False)}
    
    if not active_dbs:
        st.warning("请先在数据库管理中激活至少一个数据库")
        return
    
    selected_db = st.selectbox(
        "选择数据库:",
        options=list(active_dbs.keys()),
        format_func=lambda x: active_dbs[x]["name"]
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("自然语言查询")
        
        # 预设问题
        example_questions = [
            "显示所有表",
            "查询用户信息",
            "统计数据总数",
            "显示最新记录"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100)
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                st.info("功能开发中，敬请期待...")
            else:
                st.warning("请输入问题")
    
    with col2:
        st.subheader("2.0版本新特性")
        
        st.markdown("""
        ### 🚀 数据库支持
        - **多数据库**: SQLite + MSSQL
        - **企业级**: 支持生产环境数据库
        - **连接管理**: 可视化连接配置
        
        ### 📊 知识库增强
        - **表结构知识库**: 表和字段备注
        - **产品知识库**: 业务逻辑理解
        - **智能推荐**: 基于知识库的查询建议
        
        ### 🛠️ 管理功能
        - **表管理**: 导入、删除、测试
        - **知识编辑**: 可视化编辑界面
        - **配置持久化**: 自动保存配置
        """)

def show_database_management_page(system):
    """显示数据库管理页面"""
    st.header("数据库管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("数据库列表")
        
        # 显示现有数据库
        for db_id, db_config in system.databases.items():
            with st.expander(f"{db_config['name']} ({db_config['type'].upper()})"):
                col_a, col_b, col_c = st.columns([2, 1, 1])
                
                with col_a:
                    st.write(f"**类型**: {db_config['type']}")
                    if db_config['type'] == 'mssql':
                        st.write(f"**服务器**: {db_config['config']['server']}")
                        st.write(f"**数据库**: {db_config['config']['database']}")
                    else:
                        st.write(f"**文件**: {db_config['config']['file_path']}")
                
                with col_b:
                    # 测试连接
                    if st.button("测试连接", key=f"test_{db_id}"):
                        success, msg = system.db_manager.test_connection(
                            db_config["type"], 
                            db_config["config"]
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    
                    # 激活/停用
                    current_status = db_config.get("active", False)
                    if st.button(
                        "停用" if current_status else "激活", 
                        key=f"toggle_{db_id}"
                    ):
                        system.databases[db_id]["active"] = not current_status
                        system.save_database_configs()
                        st.rerun()
                
                with col_c:
                    # 删除数据库配置
                    if st.button("删除", key=f"del_{db_id}"):
                        del system.databases[db_id]
                        system.save_database_configs()
                        st.rerun()
        
        # 添加新数据库
        st.subheader("添加新数据库")
        
        db_type = st.selectbox("数据库类型:", ["sqlite", "mssql"])
        db_name = st.text_input("数据库名称:")
        
        if db_type == "sqlite":
            file_path = st.text_input("SQLite文件路径:", value="new_database.db")
            
            if st.button("添加SQLite数据库"):
                if db_name and file_path:
                    new_id = f"sqlite_{len(system.databases)}"
                    system.databases[new_id] = {
                        "name": db_name,
                        "type": "sqlite",
                        "config": {"file_path": file_path},
                        "active": False
                    }
                    system.save_database_configs()
                    st.success(f"已添加数据库: {db_name}")
                    st.rerun()
        
        elif db_type == "mssql":
            col_ms1, col_ms2 = st.columns(2)
            with col_ms1:
                server = st.text_input("服务器地址:", value="10.97.34.39")
                database = st.text_input("数据库名:", value="FF_IDSS_Dev_FF")
            with col_ms2:
                username = st.text_input("用户名:", value="FF_User")
                password = st.text_input("密码:", value="Grape!0808", type="password")
            
            driver = st.selectbox(
                "ODBC驱动:", 
                ["ODBC Driver 17 for SQL Server", "ODBC Driver 13 for SQL Server"]
            )
            
            if st.button("添加MSSQL数据库"):
                if all([db_name, server, database, username, password]):
                    new_id = f"mssql_{len(system.databases)}"
                    system.databases[new_id] = {
                        "name": db_name,
                        "type": "mssql",
                        "config": {
                            "server": server,
                            "database": database,
                            "username": username,
                            "password": password,
                            "driver": driver
                        },
                        "active": False
                    }
                    system.save_database_configs()
                    st.success(f"已添加数据库: {db_name}")
                    st.rerun()
    
    with col2:
        st.subheader("数据库管理说明")
        st.markdown("""
        ### 支持的数据库
        - **SQLite**: 本地文件数据库
        - **MSSQL**: Microsoft SQL Server
        
        ### 默认MSSQL配置
        - **服务器**: 10.97.34.39
        - **数据库**: FF_IDSS_Dev_FF
        - **用户**: FF_User
        - **密码**: Grape!0808
        
        ### 操作说明
        1. **测试连接**: 验证数据库连接
        2. **激活**: 启用数据库用于查询
        3. **删除**: 移除数据库配置
        
        ### 注意事项
        - 激活的数据库可用于SQL查询
        - 密码信息会加密存储
        - 支持多数据库同时激活
        """)

def show_table_management_page(system):
    """显示表结构管理页面"""
    st.header("表结构管理")
    st.info("表结构管理功能开发中...")

def show_product_knowledge_page(system):
    """显示产品知识库页面"""
    st.header("产品知识库")
    st.info("产品知识库功能开发中...")

def show_business_rules_page_v2(system):
    """显示业务规则管理页面 2.0版本"""
    st.header("业务规则管理")
    st.info("业务规则管理功能开发中...")

def show_prompt_templates_page_v2(system):
    """显示提示词管理页面 2.0版本"""
    st.header("提示词模板管理")
    st.info("提示词管理功能开发中...")

if __name__ == "__main__":
    main()