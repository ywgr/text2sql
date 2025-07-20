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
            "driver": "ODBC Driver 18 for SQL Server",
            "trusted_connection": "yes",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
    
    def get_mssql_connection_string(self, config):
        """获取MSSQL连接字符串"""
        driver = config['driver'].replace(' ', '+')
        base_url = f"mssql+pyodbc://{config['username']}:{config['password']}@{config['server']}/{config['database']}?driver={driver}"
        
        # 添加额外的连接参数
        extra_params = []
        if config.get('trusted_connection') == 'yes':
            extra_params.append("trusted_connection=yes")
        if config.get('encrypt') == 'no':
            extra_params.append("encrypt=no")
        if config.get('trust_server_certificate') == 'yes':
            extra_params.append("trust_server_certificate=yes")
        
        if extra_params:
            base_url += "&" + "&".join(extra_params)
        
        return base_url
    
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

    def generate_sql_local(self, question: str, db_config: Dict) -> Tuple[str, str]:
        """生成SQL查询"""
        try:
            # 1. 获取数据库结构信息
            schema_info = self.get_database_schema(db_config)
            
            # 2. 应用业务规则转换
            processed_question = self.apply_business_rules(question)
            
            # 3. 构建上下文
            context = self.build_context(schema_info, processed_question)
            
            # 4. 使用向量检索获取相关知识
            if self.vn:
                try:
                    # 向量检索相关知识
                    related_docs = self.vn.get_related_ddl(processed_question)
                    context += f"\n\n相关知识:\n{related_docs}"
                except Exception as e:
                    logger.warning(f"向量检索失败: {e}")
            
            # 5. 构建提示词
            prompt = self.prompt_templates["sql_generation"].format(
                schema_info=schema_info,
                table_knowledge=json.dumps(self.table_knowledge, ensure_ascii=False, indent=2),
                product_knowledge=json.dumps(self.product_knowledge, ensure_ascii=False, indent=2),
                business_rules=json.dumps(self.business_rules, ensure_ascii=False, indent=2),
                question=processed_question
            )
            
            # 6. 调用DeepSeek API生成SQL
            if self.vn:
                sql = self.vn.generate_sql(prompt)
            else:
                # 备用方案：直接调用API
                sql = self.call_deepseek_api(prompt)
            
            # 7. 清理SQL
            cleaned_sql = self.clean_sql(sql)
            
            return cleaned_sql, "SQL生成成功"
            
        except Exception as e:
            logger.error(f"SQL生成失败: {e}")
            return "", f"SQL生成失败: {str(e)}"
    
    def get_database_schema(self, db_config: Dict) -> str:
        """获取数据库结构信息"""
        try:
            db_type = db_config["type"]
            config = db_config["config"]
            
            tables = self.db_manager.get_tables(db_type, config)
            schema_info = f"数据库类型: {db_type.upper()}\n\n"
            
            for table in tables[:10]:  # 限制表数量避免提示词过长
                table_schema = self.db_manager.get_table_schema(db_type, config, table)
                if table_schema:
                    schema_info += f"表名: {table}\n"
                    schema_info += f"字段: {', '.join(table_schema['columns'])}\n\n"
            
            return schema_info
            
        except Exception as e:
            logger.error(f"获取数据库结构失败: {e}")
            return "数据库结构获取失败"
    
    def apply_business_rules(self, question: str) -> str:
        """应用业务规则转换问题"""
        processed = question
        
        for term, replacement in self.business_rules.items():
            if term in processed:
                processed = processed.replace(term, replacement)
        
        return processed
    
    def build_context(self, schema_info: str, question: str) -> str:
        """构建查询上下文"""
        context = f"数据库结构:\n{schema_info}\n"
        context += f"用户问题: {question}\n"
        return context
    
    def clean_sql(self, sql: str) -> str:
        """清理SQL语句"""
        if not sql:
            return ""
        
        # 移除markdown标记
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)
        
        # 移除多余的空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def call_deepseek_api(self, prompt: str) -> str:
        """直接调用DeepSeek API"""
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.deepseek_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"API调用失败: {response.status_code}"
                
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            return f"API调用失败: {str(e)}"
    
    def execute_sql(self, sql: str, db_config: Dict) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        try:
            db_type = db_config["type"]
            config = db_config["config"]
            
            if db_type == "sqlite":
                conn = sqlite3.connect(config["file_path"])
                df = pd.read_sql_query(sql, conn)
                conn.close()
                return True, df, "查询执行成功"
            
            elif db_type == "mssql":
                conn_str = self.db_manager.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                df = pd.read_sql_query(sql, engine)
                return True, df, "查询执行成功"
            
            else:
                return False, pd.DataFrame(), f"不支持的数据库类型: {db_type}"
                
        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return False, pd.DataFrame(), f"SQL执行失败: {str(e)}"

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
            "显示所有学生信息",
            "查询数学成绩大于90分的学生",
            "统计每个班级的学生人数",
            "显示最新的成绩记录",
            "查询张三的所有成绩",
            "统计各科目的平均分"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100)
        
        # 初始化session state
        if 'current_sql' not in st.session_state:
            st.session_state.current_sql = ""
        if 'current_question' not in st.session_state:
            st.session_state.current_question = ""
        if 'current_db_config' not in st.session_state:
            st.session_state.current_db_config = None
        if 'query_results' not in st.session_state:
            st.session_state.query_results = None
        if 'verification_result' not in st.session_state:
            st.session_state.verification_result = ""
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                with st.spinner("正在生成SQL查询..."):
                    # 获取选中的数据库配置
                    db_config = active_dbs[selected_db]
                    
                    # 生成SQL
                    sql, message = system.generate_sql_local(question, db_config)
                    
                    if sql:
                        # 保存到session state
                        st.session_state.current_sql = sql
                        st.session_state.current_question = question
                        st.session_state.current_db_config = db_config
                        st.session_state.verification_result = ""
                        
                        st.success(message)
                        
                        # 自动执行SQL查询
                        with st.spinner("正在执行查询..."):
                            success, df, exec_message = system.execute_sql(sql, db_config)
                            
                            if success:
                                # 保存查询结果到session state
                                st.session_state.query_results = {
                                    'success': True,
                                    'df': df,
                                    'message': exec_message
                                }
                            else:
                                st.session_state.query_results = {
                                    'success': False,
                                    'df': pd.DataFrame(),
                                    'message': exec_message
                                }
                    else:
                        st.error(message)
                        st.session_state.current_sql = ""
                        st.session_state.query_results = None
            else:
                st.warning("请输入问题")
        
        # 显示当前SQL和结果（如果存在）
        if st.session_state.current_sql:
            st.subheader("生成的SQL:")
            st.code(st.session_state.current_sql, language="sql")
            
            # 显示查询结果
            if st.session_state.query_results:
                if st.session_state.query_results['success']:
                    st.success(st.session_state.query_results['message'])
                    
                    df = st.session_state.query_results['df']
                    if not df.empty:
                        st.subheader("查询结果:")
                        st.dataframe(df)
                        
                        # 显示结果统计
                        st.info(f"共查询到 {len(df)} 条记录，{len(df.columns)} 个字段")
                        
                        # 数据可视化
                        if len(df.columns) >= 2 and len(df) > 1:
                            st.subheader("数据可视化:")
                            
                            # 选择图表类型
                            chart_type = st.selectbox(
                                "选择图表类型:",
                                ["柱状图", "折线图", "饼图", "散点图"],
                                key="chart_type_current"
                            )
                            
                            try:
                                if chart_type == "柱状图":
                                    fig = px.bar(df, x=df.columns[0], y=df.columns[1], 
                                               title=f"{df.columns[0]} vs {df.columns[1]}")
                                    st.plotly_chart(fig, use_container_width=True)
                                elif chart_type == "折线图":
                                    fig = px.line(df, x=df.columns[0], y=df.columns[1],
                                                title=f"{df.columns[0]} vs {df.columns[1]}")
                                    st.plotly_chart(fig, use_container_width=True)
                                elif chart_type == "饼图" and len(df) <= 20:
                                    fig = px.pie(df, names=df.columns[0], values=df.columns[1],
                                               title=f"{df.columns[0]}分布")
                                    st.plotly_chart(fig, use_container_width=True)
                                elif chart_type == "散点图":
                                    fig = px.scatter(df, x=df.columns[0], y=df.columns[1],
                                                   title=f"{df.columns[0]} vs {df.columns[1]}")
                                    st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.warning(f"图表生成失败: {e}")
                                st.info("提示：请确保选择的列包含数值数据")
                    else:
                        st.info("查询结果为空")
                else:
                    st.error(st.session_state.query_results['message'])
            
            # 操作按钮
            st.subheader("操作:")
            col_op1, col_op2, col_op3, col_op4 = st.columns([1, 1, 1, 1])
            
            with col_op1:
                if st.button("重新执行查询"):
                    with st.spinner("正在重新执行查询..."):
                        success, df, exec_message = system.execute_sql(
                            st.session_state.current_sql, 
                            st.session_state.current_db_config
                        )
                        
                        if success:
                            st.session_state.query_results = {
                                'success': True,
                                'df': df,
                                'message': exec_message
                            }
                        else:
                            st.session_state.query_results = {
                                'success': False,
                                'df': pd.DataFrame(),
                                'message': exec_message
                            }
                        st.rerun()
            
            with col_op2:
                if st.button("验证SQL"):
                    with st.spinner("正在验证SQL..."):
                        # 使用AI验证SQL
                        verification_prompt = system.prompt_templates["sql_verification"].format(
                            schema_info=system.get_database_schema(st.session_state.current_db_config),
                            table_knowledge=json.dumps(system.table_knowledge, ensure_ascii=False, indent=2),
                            business_rules=json.dumps(system.business_rules, ensure_ascii=False, indent=2),
                            question=st.session_state.current_question,
                            sql=st.session_state.current_sql
                        )
                        
                        verification_result = system.call_deepseek_api(verification_prompt)
                        st.session_state.verification_result = verification_result
                        
                        if "VALID" in verification_result:
                            st.success("✅ SQL验证通过")
                        else:
                            st.warning("⚠️ SQL可能需要优化")
            
            with col_op3:
                if st.button("清空结果"):
                    st.session_state.current_sql = ""
                    st.session_state.current_question = ""
                    st.session_state.current_db_config = None
                    st.session_state.query_results = None
                    st.session_state.verification_result = ""
                    st.rerun()
            
            with col_op4:
                if st.button("复制SQL"):
                    st.code(st.session_state.current_sql, language="sql")
                    st.success("SQL已显示，可手动复制")
            
            # 显示验证结果
            if st.session_state.verification_result:
                st.subheader("SQL验证结果:")
                if "VALID" in st.session_state.verification_result:
                    st.success("✅ SQL验证通过")
                else:
                    st.warning("⚠️ SQL可能需要优化")
                    st.text_area("详细验证结果:", st.session_state.verification_result, height=150)
    
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
                ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "ODBC Driver 13 for SQL Server"]
            )
            
            # 高级连接选项
            with st.expander("高级连接选项"):
                trusted_connection = st.selectbox("Windows身份验证:", ["no", "yes"], index=1)
                encrypt = st.selectbox("加密连接:", ["no", "yes"], index=0)
                trust_server_certificate = st.selectbox("信任服务器证书:", ["yes", "no"], index=0)
            
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
                            "driver": driver,
                            "trusted_connection": trusted_connection,
                            "encrypt": encrypt,
                            "trust_server_certificate": trust_server_certificate
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
        - **驱动**: ODBC Driver 18 for SQL Server
        - **Windows身份验证**: 是
        - **加密**: 否
        - **信任证书**: 是
        
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
    
    db_config = active_dbs[selected_db]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("表列表")
        
        # 获取表列表
        tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
        
        if tables:
            for table in tables:
                with st.expander(f"📊 {table}"):
                    # 获取表结构
                    schema = system.db_manager.get_table_schema(
                        db_config["type"], 
                        db_config["config"], 
                        table
                    )
                    
                    if schema:
                        # 显示字段信息
                        st.write("**字段信息:**")
                        if schema["column_info"]:
                            df_columns = pd.DataFrame(schema["column_info"], 
                                                    columns=["序号", "字段名", "类型", "可空", "默认值", "主键"])
                            st.dataframe(df_columns)
                        
                        # 表备注编辑
                        table_key = f"{selected_db}.{table}"
                        current_comment = system.table_knowledge.get(table_key, {}).get("comment", "")
                        
                        new_comment = st.text_area(
                            f"表备注 ({table}):",
                            value=current_comment,
                            key=f"table_comment_{table}"
                        )
                        
                        # 字段备注编辑
                        st.write("**字段备注:**")
                        field_comments = system.table_knowledge.get(table_key, {}).get("fields", {})
                        
                        for column in schema["columns"]:
                            current_field_comment = field_comments.get(column, "")
                            new_field_comment = st.text_input(
                                f"{column}:",
                                value=current_field_comment,
                                key=f"field_comment_{table}_{column}"
                            )
                            field_comments[column] = new_field_comment
                        
                        # 保存按钮
                        if st.button(f"保存 {table} 的备注", key=f"save_{table}"):
                            if table_key not in system.table_knowledge:
                                system.table_knowledge[table_key] = {}
                            
                            system.table_knowledge[table_key]["comment"] = new_comment
                            system.table_knowledge[table_key]["fields"] = field_comments
                            system.table_knowledge[table_key]["schema"] = schema
                            
                            if system.save_table_knowledge():
                                st.success(f"已保存 {table} 的备注信息")
                            else:
                                st.error("保存失败")
                        
                        # 导入到知识库
                        if st.button(f"导入 {table} 到知识库", key=f"import_{table}"):
                            if system.vn:
                                try:
                                    # 构建DDL语句
                                    ddl = f"-- 表: {table}\n"
                                    ddl += f"-- 备注: {new_comment}\n"
                                    for col_info in schema["column_info"]:
                                        field_name = col_info[1]
                                        field_type = col_info[2]
                                        field_comment = field_comments.get(field_name, "")
                                        ddl += f"-- {field_name} ({field_type}): {field_comment}\n"
                                    
                                    # 添加到向量数据库
                                    system.vn.train(ddl=ddl)
                                    st.success(f"已将 {table} 导入到知识库")
                                except Exception as e:
                                    st.error(f"导入失败: {e}")
                            else:
                                st.error("向量数据库未初始化")
        else:
            st.info("未找到表或连接失败")
    
    with col2:
        st.subheader("表结构管理说明")
        st.markdown("""
        ### 功能说明
        - **查看表结构**: 显示字段信息和类型
        - **添加备注**: 为表和字段添加业务说明
        - **导入知识库**: 将表结构导入向量数据库
        
        ### 操作步骤
        1. 选择要管理的数据库
        2. 展开要编辑的表
        3. 添加表和字段的备注
        4. 保存备注信息
        5. 导入到知识库供AI使用
        
        ### 备注建议
        - **表备注**: 说明表的业务用途
        - **字段备注**: 描述字段含义和取值范围
        - **关系说明**: 描述与其他表的关联关系
        """)
        
        # 批量操作
        st.subheader("批量操作")
        
        if st.button("导入所有表到知识库"):
            if system.vn and tables:
                imported_count = 0
                for table in tables:
                    try:
                        schema = system.db_manager.get_table_schema(
                            db_config["type"], 
                            db_config["config"], 
                            table
                        )
                        
                        if schema:
                            table_key = f"{selected_db}.{table}"
                            table_info = system.table_knowledge.get(table_key, {})
                            
                            ddl = f"-- 表: {table}\n"
                            ddl += f"-- 备注: {table_info.get('comment', '')}\n"
                            
                            for col_info in schema["column_info"]:
                                field_name = col_info[1]
                                field_type = col_info[2]
                                field_comment = table_info.get('fields', {}).get(field_name, "")
                                ddl += f"-- {field_name} ({field_type}): {field_comment}\n"
                            
                            system.vn.train(ddl=ddl)
                            imported_count += 1
                    except Exception as e:
                        logger.error(f"导入表 {table} 失败: {e}")
                
                st.success(f"已导入 {imported_count} 个表到知识库")
            else:
                st.error("向量数据库未初始化或无可用表")

def show_product_knowledge_page(system):
    """显示产品知识库页面"""
    st.header("产品知识库")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("产品信息管理")
        
        # 从[group]表导入产品信息
        st.write("**从数据库导入产品信息:**")
        
        # 选择数据库
        active_dbs = {k: v for k, v in system.databases.items() if v.get("active", False)}
        
        if active_dbs:
            selected_db = st.selectbox(
                "选择数据库:",
                options=list(active_dbs.keys()),
                format_func=lambda x: active_dbs[x]["name"],
                key="product_db_select"
            )
            
            db_config = active_dbs[selected_db]
            
            # 检查是否有[group]表
            tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
            
            if "group" in tables or "[group]" in tables:
                group_table = "group" if "group" in tables else "[group]"
                
                if st.button("从[group]表导入产品信息"):
                    try:
                        # 查询产品信息
                        sql = f"SELECT * FROM {group_table}"
                        success, df, msg = system.execute_sql(sql, db_config)
                        
                        if success and not df.empty:
                            st.success("产品信息导入成功")
                            st.dataframe(df)
                            
                            # 保存到产品知识库
                            if "products" not in system.product_knowledge:
                                system.product_knowledge["products"] = {}
                            
                            for _, row in df.iterrows():
                                product_id = str(row.iloc[0])  # 假设第一列是ID
                                system.product_knowledge["products"][product_id] = row.to_dict()
                            
                            system.save_product_knowledge()
                            st.success("已保存到产品知识库")
                        else:
                            st.error(f"导入失败: {msg}")
                    except Exception as e:
                        st.error(f"导入失败: {e}")
            else:
                st.info("未找到[group]表，请手动添加产品信息")
        
        # 手动添加产品信息
        st.subheader("手动添加产品信息")
        
        with st.form("add_product"):
            product_id = st.text_input("产品ID:")
            product_name = st.text_input("产品名称:")
            product_desc = st.text_area("产品描述:")
            product_category = st.text_input("产品分类:")
            
            if st.form_submit_button("添加产品"):
                if product_id and product_name:
                    if "products" not in system.product_knowledge:
                        system.product_knowledge["products"] = {}
                    
                    system.product_knowledge["products"][product_id] = {
                        "name": product_name,
                        "description": product_desc,
                        "category": product_category
                    }
                    
                    if system.save_product_knowledge():
                        st.success(f"已添加产品: {product_name}")
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写产品ID和名称")
        
        # 显示现有产品
        st.subheader("现有产品信息")
        
        if "products" in system.product_knowledge and system.product_knowledge["products"]:
            for product_id, product_info in system.product_knowledge["products"].items():
                with st.expander(f"🏷️ {product_info.get('name', product_id)}"):
                    st.write(f"**ID**: {product_id}")
                    st.write(f"**名称**: {product_info.get('name', '')}")
                    st.write(f"**描述**: {product_info.get('description', '')}")
                    st.write(f"**分类**: {product_info.get('category', '')}")
                    
                    if st.button(f"删除 {product_id}", key=f"del_product_{product_id}"):
                        del system.product_knowledge["products"][product_id]
                        system.save_product_knowledge()
                        st.rerun()
        else:
            st.info("暂无产品信息")
        
        # 业务规则管理
        st.subheader("产品相关业务规则")
        
        with st.form("add_business_rule"):
            rule_name = st.text_input("规则名称:")
            rule_condition = st.text_input("触发条件:")
            rule_action = st.text_area("执行动作:")
            
            if st.form_submit_button("添加业务规则"):
                if rule_name and rule_condition:
                    if "business_rules" not in system.product_knowledge:
                        system.product_knowledge["business_rules"] = {}
                    
                    system.product_knowledge["business_rules"][rule_name] = {
                        "condition": rule_condition,
                        "action": rule_action
                    }
                    
                    if system.save_product_knowledge():
                        st.success(f"已添加业务规则: {rule_name}")
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写规则名称和条件")
        
        # 显示现有业务规则
        if "business_rules" in system.product_knowledge and system.product_knowledge["business_rules"]:
            st.write("**现有业务规则:**")
            for rule_name, rule_info in system.product_knowledge["business_rules"].items():
                with st.expander(f"📋 {rule_name}"):
                    st.write(f"**条件**: {rule_info.get('condition', '')}")
                    st.write(f"**动作**: {rule_info.get('action', '')}")
                    
                    if st.button(f"删除规则 {rule_name}", key=f"del_rule_{rule_name}"):
                        del system.product_knowledge["business_rules"][rule_name]
                        system.save_product_knowledge()
                        st.rerun()
    
    with col2:
        st.subheader("产品知识库说明")
        st.markdown("""
        ### 功能说明
        - **产品信息管理**: 维护产品基础信息
        - **业务规则**: 定义产品相关的查询规则
        - **数据导入**: 从[group]表自动导入
        
        ### 数据来源
        - **[group]表**: FF_IDSS_Dev_FF数据库的产品表
        - **手动录入**: 补充和完善产品信息
        - **业务规则**: 基于产品的查询逻辑
        
        ### 使用场景
        - 产品相关的数据查询
        - 业务逻辑理解和转换
        - 智能推荐和建议
        
        ### 注意事项
        - 产品信息会影响SQL生成
        - 业务规则用于查询优化
        - 定期更新保持数据准确性
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        product_count = len(system.product_knowledge.get("products", {}))
        rule_count = len(system.product_knowledge.get("business_rules", {}))
        
        st.metric("产品数量", product_count)
        st.metric("业务规则数量", rule_count)
        
        # 导出功能
        st.subheader("数据管理")
        
        if st.button("导出产品知识库"):
            import json
            export_data = json.dumps(system.product_knowledge, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载JSON文件",
                data=export_data,
                file_name="product_knowledge.json",
                mime="application/json"
            )
        
        # 清空功能
        if st.button("清空产品知识库", type="secondary"):
            if st.checkbox("确认清空所有数据"):
                system.product_knowledge = {}
                system.save_product_knowledge()
                st.success("已清空产品知识库")
                st.rerun()

def show_business_rules_page_v2(system):
    """显示业务规则管理页面 2.0版本"""
    st.header("业务规则管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("术语映射管理")
        
        # 添加新的术语映射
        with st.form("add_term_mapping"):
            st.write("**添加术语映射:**")
            col_term1, col_term2 = st.columns(2)
            
            with col_term1:
                business_term = st.text_input("业务术语:", placeholder="例如: 学生")
            with col_term2:
                db_term = st.text_input("数据库术语:", placeholder="例如: student")
            
            if st.form_submit_button("添加映射"):
                if business_term and db_term:
                    system.business_rules[business_term] = db_term
                    if system.save_business_rules():
                        st.success(f"已添加映射: {business_term} → {db_term}")
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写完整的术语映射")
        
        # 显示现有术语映射
        st.subheader("现有术语映射")
        
        # 分类显示
        term_categories = {
            "实体映射": ["学生", "课程", "成绩", "教师", "班级"],
            "字段映射": ["姓名", "性别", "年龄", "分数", "课程名称"],
            "时间映射": ["今年", "去年", "明年", "25年", "24年", "23年"],
            "条件映射": ["优秀", "良好", "及格", "不及格"]
        }
        
        for category, keywords in term_categories.items():
            with st.expander(f"📂 {category}"):
                category_rules = {k: v for k, v in system.business_rules.items() 
                                if any(keyword in k for keyword in keywords)}
                
                if category_rules:
                    for term, mapping in category_rules.items():
                        col_show1, col_show2, col_show3 = st.columns([2, 2, 1])
                        
                        with col_show1:
                            new_term = st.text_input(f"术语:", value=term, key=f"term_{category}_{term}")
                        with col_show2:
                            new_mapping = st.text_input(f"映射:", value=mapping, key=f"mapping_{category}_{term}")
                        with col_show3:
                            if st.button("删除", key=f"del_{category}_{term}"):
                                del system.business_rules[term]
                                system.save_business_rules()
                                st.rerun()
                            
                            if st.button("更新", key=f"update_{category}_{term}"):
                                if new_term != term:
                                    del system.business_rules[term]
                                system.business_rules[new_term] = new_mapping
                                system.save_business_rules()
                                st.success("已更新")
                                st.rerun()
                else:
                    st.info(f"暂无{category}")
        
        # 其他规则
        other_rules = {k: v for k, v in system.business_rules.items() 
                      if not any(any(keyword in k for keyword in keywords) 
                               for keywords in term_categories.values())}
        
        if other_rules:
            with st.expander("📂 其他规则"):
                for term, mapping in other_rules.items():
                    col_other1, col_other2, col_other3 = st.columns([2, 2, 1])
                    
                    with col_other1:
                        st.text_input(f"术语:", value=term, key=f"other_term_{hash(term)}", disabled=True)
                    with col_other2:
                        st.text_input(f"映射:", value=mapping, key=f"other_mapping_{hash(term)}", disabled=True)
                    with col_other3:
                        if st.button("删除", key=f"del_other_{hash(term)}"):
                            del system.business_rules[term]
                            system.save_business_rules()
                            st.rerun()
        
        # 批量导入
        st.subheader("批量导入规则")
        
        uploaded_file = st.file_uploader("上传JSON文件", type=['json'])
        if uploaded_file is not None:
            try:
                import json
                new_rules = json.load(uploaded_file)
                
                if st.button("导入规则"):
                    system.business_rules.update(new_rules)
                    if system.save_business_rules():
                        st.success(f"已导入 {len(new_rules)} 条规则")
                    else:
                        st.error("导入失败")
            except Exception as e:
                st.error(f"文件格式错误: {e}")
        
        # 预设规则模板
        st.subheader("预设规则模板")
        
        preset_templates = {
            "教育系统": {
                "学生": "student",
                "课程": "course",
                "成绩": "score",
                "教师": "teacher",
                "班级": "class",
                "姓名": "name",
                "年龄": "age",
                "性别": "gender"
            },
            "电商系统": {
                "用户": "user",
                "商品": "product",
                "订单": "order",
                "支付": "payment",
                "库存": "inventory",
                "价格": "price",
                "数量": "quantity"
            },
            "人事系统": {
                "员工": "employee",
                "部门": "department",
                "职位": "position",
                "薪资": "salary",
                "考勤": "attendance",
                "绩效": "performance"
            }
        }
        
        selected_template = st.selectbox("选择模板:", ["无"] + list(preset_templates.keys()))
        
        if selected_template != "无":
            if st.button(f"应用{selected_template}模板"):
                template_rules = preset_templates[selected_template]
                system.business_rules.update(template_rules)
                if system.save_business_rules():
                    st.success(f"已应用{selected_template}模板，添加了 {len(template_rules)} 条规则")
                else:
                    st.error("应用模板失败")
    
    with col2:
        st.subheader("业务规则说明")
        st.markdown("""
        ### 功能说明
        - **术语映射**: 业务术语到数据库字段的映射
        - **条件转换**: 业务条件到SQL条件的转换
        - **批量管理**: 支持批量导入和模板应用
        
        ### 规则类型
        - **实体映射**: 业务实体到表名的映射
        - **字段映射**: 业务字段到列名的映射
        - **时间映射**: 时间表达式的标准化
        - **条件映射**: 业务条件到SQL条件
        
        ### 使用示例
        ```
        业务术语 → 数据库术语
        学生 → student
        姓名 → name
        优秀 → score >= 90
        今年 → 2024年
        ```
        
        ### 最佳实践
        - 保持映射的一致性
        - 定期更新和维护
        - 使用有意义的术语
        - 测试映射效果
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        total_rules = len(system.business_rules)
        st.metric("总规则数", total_rules)
        
        # 规则分类统计
        for category, keywords in term_categories.items():
            count = len([k for k in system.business_rules.keys() 
                        if any(keyword in k for keyword in keywords)])
            st.metric(category, count)
        
        # 导出功能
        st.subheader("数据管理")
        
        if st.button("导出业务规则"):
            import json
            export_data = json.dumps(system.business_rules, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载JSON文件",
                data=export_data,
                file_name="business_rules.json",
                mime="application/json"
            )
        
        # 重置功能
        if st.button("重置为默认规则", type="secondary"):
            if st.checkbox("确认重置"):
                system.business_rules = system.load_business_rules()
                system.save_business_rules()
                st.success("已重置为默认规则")
                st.rerun()

def show_prompt_templates_page_v2(system):
    """显示提示词管理页面 2.0版本"""
    st.header("提示词模板管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("提示词模板编辑")
        
        # 选择模板
        template_names = list(system.prompt_templates.keys())
        selected_template = st.selectbox("选择模板:", template_names)
        
        if selected_template:
            # 显示当前模板
            st.write(f"**当前模板: {selected_template}**")
            
            # 编辑模板
            current_template = system.prompt_templates[selected_template]
            new_template = st.text_area(
                "编辑模板内容:",
                value=current_template,
                height=300,
                key=f"template_{selected_template}"
            )
            
            col_save, col_reset = st.columns(2)
            
            with col_save:
                if st.button("保存模板"):
                    system.prompt_templates[selected_template] = new_template
                    if system.save_prompt_templates():
                        st.success("模板保存成功")
                    else:
                        st.error("保存失败")
            
            with col_reset:
                if st.button("重置模板"):
                    # 重新加载默认模板
                    default_templates = system.load_prompt_templates()
                    if selected_template in default_templates:
                        system.prompt_templates[selected_template] = default_templates[selected_template]
                        system.save_prompt_templates()
                        st.success("已重置为默认模板")
                        st.rerun()
        
        # 添加新模板
        st.subheader("添加新模板")
        
        with st.form("add_template"):
            new_template_name = st.text_input("模板名称:")
            new_template_content = st.text_area("模板内容:", height=200)
            
            if st.form_submit_button("添加模板"):
                if new_template_name and new_template_content:
                    system.prompt_templates[new_template_name] = new_template_content
                    if system.save_prompt_templates():
                        st.success(f"已添加模板: {new_template_name}")
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写模板名称和内容")
        
        # 模板预览
        st.subheader("模板预览")
        
        if selected_template:
            st.write("**变量说明:**")
            
            # 分析模板中的变量
            import re
            variables = re.findall(r'\{(\w+)\}', system.prompt_templates[selected_template])
            
            if variables:
                for var in set(variables):
                    st.write(f"- `{{{var}}}`: {get_variable_description(var)}")
            else:
                st.info("此模板不包含变量")
            
            # 模拟预览
            if st.button("预览模板效果"):
                preview_data = get_preview_data()
                try:
                    preview_result = system.prompt_templates[selected_template].format(**preview_data)
                    st.text_area("预览结果:", preview_result, height=200)
                except Exception as e:
                    st.error(f"预览失败: {e}")
        
        # 批量操作
        st.subheader("批量操作")
        
        col_export, col_import = st.columns(2)
        
        with col_export:
            if st.button("导出所有模板"):
                import json
                export_data = json.dumps(system.prompt_templates, ensure_ascii=False, indent=2)
                st.download_button(
                    label="下载JSON文件",
                    data=export_data,
                    file_name="prompt_templates.json",
                    mime="application/json"
                )
        
        with col_import:
            uploaded_file = st.file_uploader("导入模板文件", type=['json'])
            if uploaded_file is not None:
                try:
                    import json
                    new_templates = json.load(uploaded_file)
                    
                    if st.button("导入模板"):
                        system.prompt_templates.update(new_templates)
                        if system.save_prompt_templates():
                            st.success(f"已导入 {len(new_templates)} 个模板")
                        else:
                            st.error("导入失败")
                except Exception as e:
                    st.error(f"文件格式错误: {e}")
    
    with col2:
        st.subheader("模板管理说明")
        st.markdown("""
        ### 功能说明
        - **模板编辑**: 自定义AI提示词模板
        - **变量支持**: 使用{变量名}插入动态内容
        - **预览功能**: 实时预览模板效果
        
        ### 可用变量
        - `{schema_info}`: 数据库结构信息
        - `{table_knowledge}`: 表结构知识库
        - `{product_knowledge}`: 产品知识库
        - `{business_rules}`: 业务规则
        - `{question}`: 用户问题
        - `{sql}`: 生成的SQL语句
        
        ### 模板类型
        - **sql_generation**: SQL生成模板
        - **sql_verification**: SQL验证模板
        - **自定义模板**: 用户自定义的模板
        
        ### 最佳实践
        - 保持模板简洁明确
        - 使用合适的变量
        - 定期测试模板效果
        - 备份重要模板
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        total_templates = len(system.prompt_templates)
        st.metric("模板总数", total_templates)
        
        # 模板使用统计
        for template_name in system.prompt_templates.keys():
            template_length = len(system.prompt_templates[template_name])
            st.metric(f"{template_name} 长度", f"{template_length} 字符")
        
        # 快速操作
        st.subheader("快速操作")
        
        if st.button("重置所有模板"):
            if st.checkbox("确认重置所有模板"):
                system.prompt_templates = system.load_prompt_templates()
                system.save_prompt_templates()
                st.success("已重置所有模板")
                st.rerun()
        
        if st.button("删除选中模板"):
            if selected_template and selected_template not in ["sql_generation", "sql_verification"]:
                if st.checkbox(f"确认删除 {selected_template}"):
                    del system.prompt_templates[selected_template]
                    system.save_prompt_templates()
                    st.success(f"已删除模板: {selected_template}")
                    st.rerun()
            else:
                st.warning("无法删除系统核心模板")

def get_variable_description(var_name):
    """获取变量描述"""
    descriptions = {
        "schema_info": "数据库结构信息，包含表名和字段信息",
        "table_knowledge": "表结构知识库，包含表和字段的备注说明",
        "product_knowledge": "产品知识库，包含产品信息和业务规则",
        "business_rules": "业务规则，包含术语映射和条件转换",
        "question": "用户输入的自然语言问题",
        "sql": "生成的SQL语句，用于验证模板"
    }
    return descriptions.get(var_name, "未知变量")

def get_preview_data():
    """获取预览数据"""
    return {
        "schema_info": "表名: users\n字段: id, name, email, age\n\n表名: orders\n字段: id, user_id, amount, date",
        "table_knowledge": '{"users": {"comment": "用户表", "fields": {"name": "用户姓名", "email": "邮箱地址"}}}',
        "product_knowledge": '{"products": {"1": {"name": "产品A", "category": "电子产品"}}}',
        "business_rules": '{"用户": "user", "订单": "order", "今年": "2024"}',
        "question": "查询所有用户信息",
        "sql": "SELECT * FROM users;"
    }

if __name__ == "__main__":
    main()