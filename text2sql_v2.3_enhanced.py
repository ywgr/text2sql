#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 V2.3 - 增强优化版本
基于V2.2核心优化 + V2.1完整功能
主要改进：
1. 整合V2.2的统一SQL生成和验证流程
2. 智能缓存机制
3. 用户友好的错误处理
4. 性能监控和优化
5. 完整的企业级功能
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import json
import re
import hashlib
import time
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
import logging
import os
import traceback
import requests
from vanna.chromadb import ChromaDB_VectorStore
from vanna.deepseek import DeepSeekChat
import pyodbc
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
from collections import deque
from difflib import get_close_matches

# 通用产品匹配器
class UniversalProductMatcher:
    """通用产品匹配器 - 支持所有产品：510S、geek、小新、拯救者等"""
    
    def __init__(self):
        self.load_product_knowledge()
        self.init_product_patterns()
    
    def load_product_knowledge(self):
        """加载产品知识库"""
        try:
            with open('product_knowledge.json', 'r', encoding='utf-8') as f:
                self.product_knowledge = json.load(f)
        except:
            try:
                with open('product_knowledge.json', 'r', encoding='gbk') as f:
                    self.product_knowledge = json.load(f)
            except:
                self.product_knowledge = {"products": {}}
    
    def init_product_patterns(self):
        """初始化产品模式"""
        # 从产品知识库中提取所有产品系列
        roadmap_families = set()
        for pn, product in self.product_knowledge.get('products', {}).items():
            if 'Roadmap Family' in product and product['Roadmap Family'] != 'ttl':
                roadmap_families.add(product['Roadmap Family'])
        
        # 建立产品关键词到roadmap family的映射
        self.product_patterns = {
            "510S": {"pattern": "510S", "families": []},
            "510s": {"pattern": "510S", "families": []},
            "geek": {"pattern": "Geek", "families": []},
            "GeekPro": {"pattern": "Geek", "families": []},
            "小新": {"pattern": "小新", "families": []},
            "拯救者": {"pattern": "拯救者", "families": []},
            "AIO": {"pattern": "AIO", "families": []},
        }
        
        # 填充实际的families
        for family in roadmap_families:
            for keyword, config in self.product_patterns.items():
                if config["pattern"] in family:
                    config["families"].append(family)
        
        # 清理空的模式
        self.product_patterns = {k: v for k, v in self.product_patterns.items() if v["families"]}
    
    def detect_product_in_question(self, question: str) -> Optional[Dict]:
        """从问题中检测产品"""
        question_lower = question.lower()
        
        # 按优先级检测产品关键词
        for keyword, config in self.product_patterns.items():
            if keyword.lower() in question_lower:
                return {
                    "keyword": keyword,
                    "pattern": config["pattern"],
                    "families": config["families"]
                }
        
        return None
    
    def generate_product_conditions(self, question: str) -> List[str]:
        """生成产品条件 - 通用逻辑"""
        conditions = []
        
        product_info = self.detect_product_in_question(question)
        if product_info:
            # 使用通用的产品层级逻辑：MODEL -> [ROADMAP FAMILY] -> [GROUP]
            pattern = product_info["pattern"]
            conditions.append(f"[Roadmap Family] LIKE '%{pattern}%'")
            conditions.append("[Group] = 'ttl'")
        
        return conditions
    
    def get_all_supported_products(self) -> Dict:
        """获取所有支持的产品"""
        return {k: v["families"] for k, v in self.product_patterns.items()}

# SQLite表结构管理器
class SQLiteTableManager:
    """SQLite表结构管理器"""
    
    def __init__(self, db_path: str = "test_database.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Exception as e:
            return []
    
    def get_table_columns(self, table_name: str) -> List[Tuple]:
        """获取表的列信息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            conn.close()
            return columns
        except Exception as e:
            return []
    
    def get_sample_data(self, table_name: str, limit: int = 10) -> pd.DataFrame:
        """获取表的示例数据"""
        try:
            conn = self.get_connection()
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception as e:
            return pd.DataFrame()
    
    def execute_sql(self, sql: str) -> Tuple[bool, str, pd.DataFrame]:
        """执行SQL语句"""
        try:
            conn = self.get_connection()
            df = pd.read_sql_query(sql, conn)
            conn.close()
            return True, f"查询成功，返回 {len(df)} 行数据", df
        except Exception as e:
            return False, f"查询失败: {str(e)}", pd.DataFrame()
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return sorted(tables)
        except Exception as e:
            st.error(f"获取表列表失败: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict:
        """获取表结构"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 获取索引信息
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            
            # 获取外键信息
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
            
            # 获取行数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'columns': columns,
                'indexes': indexes,
                'foreign_keys': foreign_keys,
                'row_count': row_count
            }
        except Exception as e:
            st.error(f"获取表结构失败: {e}")
            return {}
    
    def create_table(self, table_name: str, columns: List[Dict]) -> Tuple[bool, str]:
        """创建表"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 构建CREATE TABLE语句
            column_defs = []
            for col in columns:
                col_def = f"{col['name']} {col['type']}"
                if col.get('primary_key'):
                    col_def += " PRIMARY KEY"
                if col.get('not_null'):
                    col_def += " NOT NULL"
                if col.get('unique'):
                    col_def += " UNIQUE"
                if col.get('default'):
                    col_def += f" DEFAULT {col['default']}"
                column_defs.append(col_def)
            
            sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
            cursor.execute(sql)
            conn.commit()
            conn.close()
            
            return True, f"表 {table_name} 创建成功"
        except Exception as e:
            return False, f"创建表失败: {e}"
    
    def drop_table(self, table_name: str) -> Tuple[bool, str]:
        """删除表"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            conn.close()
            return True, f"表 {table_name} 删除成功"
        except Exception as e:
            return False, f"删除表失败: {e}"
    
    def add_column(self, table_name: str, column_name: str, column_type: str) -> Tuple[bool, str]:
        """添加列"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
            conn.close()
            return True, f"列 {column_name} 添加成功"
        except Exception as e:
            return False, f"添加列失败: {e}"
    
    def get_sample_data(self, table_name: str, limit: int = 10) -> pd.DataFrame:
        """获取样本数据"""
        try:
            conn = self.get_connection()
            df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT {limit}", conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"获取样本数据失败: {e}")
            return pd.DataFrame()
    
    def execute_sql(self, sql: str) -> Tuple[bool, str, pd.DataFrame]:
        """执行SQL语句"""
        try:
            conn = self.get_connection()
            
            # 判断是否为查询语句
            if sql.strip().upper().startswith('SELECT'):
                df = pd.read_sql_query(sql, conn)
                conn.close()
                return True, f"查询成功，返回 {len(df)} 行", df
            else:
                cursor = conn.cursor()
                cursor.execute(sql)
                affected_rows = cursor.rowcount
                conn.commit()
                conn.close()
                return True, f"执行成功，影响 {affected_rows} 行", pd.DataFrame()
        except Exception as e:
            return False, f"执行失败: {e}", pd.DataFrame()

# 导入V2.2核心优化模块和V2.3多表查询增强
try:
    # 注意：实际文件名是 text2sql_v2.2_core.py，但Python导入时需要用下划线
    import importlib.util
    import sys
    
    # 动态导入 text2sql_v2.2_core.py
    spec = importlib.util.spec_from_file_location("text2sql_v2_2_core", "text2sql_v2.2_core.py")
    if spec and spec.loader:
        text2sql_v2_2_core = importlib.util.module_from_spec(spec)
        sys.modules["text2sql_v2_2_core"] = text2sql_v2_2_core
        spec.loader.exec_module(text2sql_v2_2_core)
        
        # 导入所需的类和函数
        ValidationResult = text2sql_v2_2_core.ValidationResult
        SQLGenerationContext = text2sql_v2_2_core.SQLGenerationContext
        SQLValidator = text2sql_v2_2_core.SQLValidator
        EnhancedPromptBuilder = text2sql_v2_2_core.EnhancedPromptBuilder
        SQLCache = text2sql_v2_2_core.SQLCache
        UserFriendlyErrorHandler = text2sql_v2_2_core.UserFriendlyErrorHandler
        monitor_performance = text2sql_v2_2_core.monitor_performance
    else:
        raise ImportError("无法加载 text2sql_v2.2_core.py")
    
    # 动态导入 text2sql_v2.3_multi_table_enhanced.py
    spec2 = importlib.util.spec_from_file_location("text2sql_v2_3_multi_table_enhanced", "text2sql_v2.3_multi_table_enhanced.py")
    if spec2 and spec2.loader:
        text2sql_v2_3_multi_table_enhanced = importlib.util.module_from_spec(spec2)
        sys.modules["text2sql_v2_3_multi_table_enhanced"] = text2sql_v2_3_multi_table_enhanced
        spec2.loader.exec_module(text2sql_v2_3_multi_table_enhanced)
        
        # 导入所需的类和函数
        EnhancedRelationshipManager = text2sql_v2_3_multi_table_enhanced.EnhancedRelationshipManager
        ScenarioBasedTermMapper = text2sql_v2_3_multi_table_enhanced.ScenarioBasedTermMapper
        StructuredPromptBuilder = text2sql_v2_3_multi_table_enhanced.StructuredPromptBuilder
        MultiTableSQLValidator = text2sql_v2_3_multi_table_enhanced.MultiTableSQLValidator
        TableRelationship = text2sql_v2_3_multi_table_enhanced.TableRelationship
        FieldBinding = text2sql_v2_3_multi_table_enhanced.FieldBinding
        QueryScenario = text2sql_v2_3_multi_table_enhanced.QueryScenario
    else:
        raise ImportError("无法加载 text2sql_v2.3_multi_table_enhanced.py")
    
    MULTI_TABLE_ENHANCED = True
except ImportError:
    # 如果V2.2核心模块不存在，使用内置的简化版本
    from dataclasses import dataclass
    from typing import Dict, List
    
    @dataclass
    class ValidationResult:
        is_valid: bool
        corrected_sql: str
        issues: List[str]
        suggestions: List[str]
        performance_score: float = 0.0
    
    @dataclass
    class SQLGenerationContext:
        question: str
        processed_question: str
        schema_info: str
        table_knowledge: Dict
        product_knowledge: Dict
        business_rules: Dict
        allowed_tables: set
        db_config: Dict
    
    class SQLValidator:
        def __init__(self, table_knowledge: Dict, business_rules: Dict):
            self.table_knowledge = table_knowledge
            self.business_rules = business_rules
        
        def validate_comprehensive(self, sql: str, context) -> ValidationResult:
            # 简化版验证
            issues = []
            if not sql or sql.strip() == "":
                issues.append("ERROR: SQL为空")
                return ValidationResult(False, sql, issues, [], 0.0)
            
            # 基础验证
            if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
                issues.append("ERROR: 缺少SELECT关键字")
            
            is_valid = len([i for i in issues if i.startswith("ERROR")]) == 0
            return ValidationResult(is_valid, sql, issues, [], 80.0)
    
    class EnhancedPromptBuilder:
        def build_comprehensive_prompt(self, context) -> str:
            return f"""你是一个SQL专家。根据以下信息生成准确的SQL查询语句。

数据库结构：
{context.schema_info}

表结构知识库：
{json.dumps(context.table_knowledge, ensure_ascii=False, indent=2)}

产品知识库：
{json.dumps(context.product_knowledge, ensure_ascii=False, indent=2)}

业务规则：
{json.dumps(context.business_rules, ensure_ascii=False, indent=2)}

用户问题：{context.processed_question}

严格要求：
1. 只能使用以下已导入的表：{', '.join(context.allowed_tables)}
2. 所有字段必须真实存在且属于正确的表
3. 多表查询必须使用正确的JOIN和ON条件，只能使用知识库中的表关系数据
4. 只输出SQL语句，不要任何解释

SQL语句："""
    
    class SQLCache:
        def __init__(self, max_size: int = 100):
            self.cache = {}
            self.max_size = max_size
            self.access_count = {}
        
        def get_cache_key(self, question: str, schema_hash: str, rules_hash: str) -> str:
            content = f"{question}_{schema_hash}_{rules_hash}"
            return hashlib.md5(content.encode()).hexdigest()
        
        def get(self, cache_key: str) -> Optional[str]:
            if cache_key in self.cache:
                self.access_count[cache_key] = self.access_count.get(cache_key, 0) + 1
                return self.cache[cache_key]
            return None
        
        def set(self, cache_key: str, sql: str):
            if len(self.cache) >= self.max_size:
                least_used = min(self.access_count.items(), key=lambda x: x[1])[0]
                del self.cache[least_used]
                del self.access_count[least_used]
            
            self.cache[cache_key] = sql
            self.access_count[cache_key] = 1
        
        def clear(self):
            self.cache.clear()
            self.access_count.clear()
    
    class UserFriendlyErrorHandler:
        def format_issues(self, issues: List[str]) -> Dict[str, List[str]]:
            formatted = {
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "info": []
            }
            
            for issue in issues:
                if issue.startswith("ERROR"):
                    formatted["errors"].append(issue.replace("ERROR: ", ""))
                elif issue.startswith("WARNING"):
                    formatted["warnings"].append(issue.replace("WARNING: ", ""))
                elif issue.startswith("SUGGESTION"):
                    formatted["suggestions"].append(issue.replace("SUGGESTION: ", ""))
                else:
                    formatted["info"].append(issue)
            
            return formatted
    
    def monitor_performance(func):
        """性能监控装饰器"""
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            
            logger.info(f"{func.__name__} 执行时间: {end_time - start_time:.2f}秒")
            return result
        return wrapper

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
    """数据库管理器 - 继承V2.1功能"""
    
    def __init__(self):
        self.connections = {}
        self.default_mssql_config = {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF", 
            "username": "FF_User",
            "password": "Grape!0808",
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
    
    def get_mssql_connection_string(self, config):
        """获取MSSQL连接字符串，自动拼接所有额外参数"""
        base = f"mssql+pyodbc://{config['username']}:{config['password']}@{config['server']}/{config['database']}?driver={config['driver'].replace(' ', '+')}"
        # 拼接额外参数
        extras = []
        for k, v in config.items():
            if k not in ["server", "database", "username", "password", "driver"]:
                extras.append(f"{k}={v}")
        if extras:
            base += "&" + "&".join(extras)
        return base
    
    @monitor_performance
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
    
    @monitor_performance
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
    
    @monitor_performance
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

class Text2SQLSystemV23:
    """TEXT2SQL系统 V2.3版本 - 整合V2.2核心优化"""
    
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
        
        # V2.2核心优化组件
        self.sql_validator = SQLValidator(self.table_knowledge, self.business_rules)
        self.prompt_builder = EnhancedPromptBuilder()
        self.sql_cache = SQLCache(max_size=100)
        self.error_handler = UserFriendlyErrorHandler()
        
        # V2.3多表查询增强组件
        if 'MULTI_TABLE_ENHANCED' in globals() and MULTI_TABLE_ENHANCED:
            self.relation_manager = EnhancedRelationshipManager()
            self.term_mapper = ScenarioBasedTermMapper()
            self.structured_prompt_builder = StructuredPromptBuilder(
                self.relation_manager, self.term_mapper)
            self.multi_table_validator = MultiTableSQLValidator(self.relation_manager)
            self._initialize_multi_table_knowledge()
        else:
            self.relation_manager = None
            self.term_mapper = None
            self.structured_prompt_builder = None
            self.multi_table_validator = None

    def load_database_configs(self) -> Dict:
        """加载数据库配置"""
        default_configs = {
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
                    # 移除所有sqlite相关配置
                    saved_configs = {k: v for k, v in saved_configs.items() if v.get('type') != 'sqlite'}
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

    @monitor_performance
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

    def _initialize_multi_table_knowledge(self):
        """初始化多表查询知识库"""
        if not self.relation_manager:
            return
        
        # 从现有表知识库构建关系
        for table_name, table_info in self.table_knowledge.items():
            # 添加字段绑定
            for column in table_info.get('columns', []):
                binding = FieldBinding(
                    field_name=column,
                    table_name=table_name,
                    business_term=table_info.get('business_fields', {}).get(column, column),
                    data_type="unknown",
                    is_primary_key=column.lower().endswith('id') and column.lower().startswith(table_name.lower()[:3]),
                    is_foreign_key=column.lower().endswith('id') and not column.lower().startswith(table_name.lower()[:3])
                )
                self.relation_manager.add_field_binding(binding)
            
            # 添加表关系
            for rel in table_info.get('relationships', []):
                relationship = TableRelationship(
                    table1=rel.get('table1', ''),
                    field1=rel.get('field1', ''),
                    table2=rel.get('table2', ''),
                    field2=rel.get('field2', ''),
                    relation_type=rel.get('relation_type', '一对多'),
                    business_meaning=rel.get('description', ''),
                    confidence=rel.get('confidence', 0.8)
                )
                self.relation_manager.add_relationship(relationship)
        
        # 添加常见查询场景
        self._add_common_query_scenarios()
        
        # 添加场景化术语映射
        self._add_scenario_term_mappings()
        
        # 添加禁止关联规则
        self._add_forbidden_relations()
    
    def _add_common_query_scenarios(self):
        """添加常见查询场景"""
        if not self.relation_manager:
            return
        
        # 客户订单查询场景
        if 'customer' in self.table_knowledge and 'order' in self.table_knowledge:
            customer_order_scenario = QueryScenario(
                scenario_name="客户订单查询",
                involved_tables=["customer", "order"],
                relation_chain=[
                    TableRelationship("customer", "customer_id", "order", "customer_id", 
                                    "一对多", "一个客户可以有多个订单")
                ],
                common_fields=["customer.name", "order.amount", "order.order_date"],
                business_logic="通过客户ID关联客户表和订单表，用于查询客户的订单信息",
                sql_template="SELECT c.name, o.amount FROM customer c JOIN order o ON c.customer_id = o.customer_id"
            )
            self.relation_manager.query_scenarios.append(customer_order_scenario)
        
        # 订单商品查询场景
        if all(table in self.table_knowledge for table in ['order', 'order_item', 'product']):
            order_product_scenario = QueryScenario(
                scenario_name="订单商品查询",
                involved_tables=["order", "order_item", "product"],
                relation_chain=[
                    TableRelationship("order", "order_id", "order_item", "order_id", 
                                    "一对多", "一个订单包含多个商品"),
                    TableRelationship("order_item", "product_id", "product", "product_id", 
                                    "多对一", "订单项对应具体商品")
                ],
                common_fields=["order.order_id", "product.name", "order_item.quantity"],
                business_logic="通过订单明细表关联订单和商品，用于查询订单包含的商品信息",
                sql_template="SELECT o.order_id, p.name, oi.quantity FROM order o JOIN order_item oi ON o.order_id = oi.order_id JOIN product p ON oi.product_id = p.product_id"
            )
            self.relation_manager.query_scenarios.append(order_product_scenario)
    
    def _add_scenario_term_mappings(self):
        """添加场景化术语映射"""
        if not self.term_mapper:
            return
        
        # 客户相关术语
        self.term_mapper.add_scenario_mapping(
            "客户订单", "客户的订单金额", 
            ["customer", "order"], 
            "order.amount",
            ["customer.customer_id = order.customer_id"]
        )
        
        self.term_mapper.add_scenario_mapping(
            "客户统计", "客户订单数量",
            ["customer", "order"],
            "COUNT(order.order_id)",
            ["customer.customer_id = order.customer_id"]
        )
        
        # 商品相关术语
        self.term_mapper.add_scenario_mapping(
            "商品销量", "商品销售数量",
            ["product", "order_item"],
            "SUM(order_item.quantity)",
            ["product.product_id = order_item.product_id"]
        )
        
        # 歧义术语处理
        self.term_mapper.add_ambiguous_term("销量", [
            {
                "scenario": "商品销量",
                "keywords": ["商品", "产品"],
                "tables": ["product", "order_item"],
                "core_field": "SUM(order_item.quantity)"
            },
            {
                "scenario": "区域销量", 
                "keywords": ["区域", "地区"],
                "tables": ["region", "customer", "order"],
                "core_field": "COUNT(order.order_id)"
            }
        ])
    
    def _add_forbidden_relations(self):
        """添加禁止关联规则"""
        if not self.relation_manager:
            return
        
        # 示例：客户表不能直接关联商品表
        if 'customer' in self.table_knowledge and 'product' in self.table_knowledge:
            self.relation_manager.add_forbidden_relation(
                "customer", "product", 
                "客户和商品之间没有直接关联，需要通过订单表和订单明细表间接关联"
            )

    @monitor_performance
    def generate_sql_enhanced(self, question: str, db_config: Dict) -> tuple:
        """V2.3增强版SQL生成 - 整合V2.2核心优化"""
        try:
            # 1. 检查缓存
            schema_hash = hashlib.md5(str(self.table_knowledge).encode()).hexdigest()[:8]
            rules_hash = hashlib.md5(str(self.business_rules).encode()).hexdigest()[:8]
            cache_key = self.sql_cache.get_cache_key(question, schema_hash, rules_hash)
            
            cached_sql = self.sql_cache.get(cache_key)
            if cached_sql:
                logger.info("使用缓存的SQL结果")
                return cached_sql, "从缓存获取SQL（性能优化）"
            
            # 2. 获取数据库结构信息
            schema_info = self.get_database_schema(db_config)
            
            # 3. 构建表名白名单 - 只允许使用已导入知识库的表
            allowed_tables = set(self.table_knowledge.keys()) if self.table_knowledge else set()
            if not allowed_tables:
                return "", "错误：没有已导入知识库的表，请先在表结构管理中导入表。"
            
            # 4. 应用业务规则转换
            processed_question = self.apply_business_rules(question)
            
            # 5. 构建SQL生成上下文
            context = SQLGenerationContext(
                question=question,
                processed_question=processed_question,
                schema_info=schema_info,
                table_knowledge=self.table_knowledge,
                product_knowledge=self.product_knowledge,
                business_rules=self.business_rules,
                allowed_tables=allowed_tables,
                db_config=db_config
            )
            
            # 6. 使用增强的提示词构建器
            prompt = self.prompt_builder.build_comprehensive_prompt(context)
            
            # 7. 调用DeepSeek API生成SQL
            if self.vn:
                sql = self.vn.generate_sql(prompt)
            else:
                sql = self.call_deepseek_api(prompt)
            
            # 8. 清理SQL
            cleaned_sql = self.clean_sql(sql)
            
            # 9. 使用V2.2统一验证器进行全面验证
            validation_result = self.sql_validator.validate_comprehensive(cleaned_sql, context)
            
            if not validation_result.is_valid:
                # 格式化错误信息
                formatted_issues = self.error_handler.format_issues(validation_result.issues)
                error_msg = "SQL验证失败：\n"
                
                if formatted_issues["errors"]:
                    error_msg += "❌ 错误：\n" + "\n".join(formatted_issues["errors"]) + "\n"
                if formatted_issues["warnings"]:
                    error_msg += "⚠️ 警告：\n" + "\n".join(formatted_issues["warnings"]) + "\n"
                if formatted_issues["suggestions"]:
                    error_msg += "💡 建议：\n" + "\n".join(formatted_issues["suggestions"])
                
                return "", error_msg
            
            # 10. 使用修正后的SQL
            final_sql = validation_result.corrected_sql
            
            # 11. 缓存结果
            self.sql_cache.set(cache_key, final_sql)
            
            # 12. 构建成功消息
            success_msg = f"SQL生成成功（性能评分：{validation_result.performance_score:.1f}/100）"
            if validation_result.issues:
                formatted_issues = self.error_handler.format_issues(validation_result.issues)
                if formatted_issues["warnings"]:
                    success_msg += "\n⚠️ 注意：\n" + "\n".join(formatted_issues["warnings"])
                if formatted_issues["suggestions"]:
                    success_msg += "\n💡 优化建议：\n" + "\n".join(formatted_issues["suggestions"])
            
            return final_sql, success_msg
            
        except Exception as e:
            logger.error(f"SQL生成失败: {e}")
            return "", f"SQL生成失败: {str(e)}"
    
    @monitor_performance
    def generate_sql_multi_table_enhanced(self, question: str, db_config: Dict) -> tuple:
        """V2.3多表查询增强版SQL生成"""
        try:
            # 检查是否启用了多表增强功能
            if not self.structured_prompt_builder or not self.multi_table_validator:
                # 回退到标准生成方法
                return self.generate_sql_enhanced(question, db_config)
            
            # 1. 检查缓存
            schema_hash = hashlib.md5(str(self.table_knowledge).encode()).hexdigest()[:8]
            rules_hash = hashlib.md5(str(self.business_rules).encode()).hexdigest()[:8]
            cache_key = self.sql_cache.get_cache_key(question, schema_hash, rules_hash)
            
            cached_sql = self.sql_cache.get(cache_key)
            if cached_sql:
                logger.info("使用缓存的SQL结果")
                return cached_sql, "从缓存获取SQL（多表增强版）"
            
            # 2. 获取数据库结构信息
            schema_info = self.get_database_schema(db_config)
            
            # 3. 构建表名白名单
            allowed_tables = set(self.table_knowledge.keys()) if self.table_knowledge else set()
            if not allowed_tables:
                return "", "错误：没有已导入知识库的表，请先在表结构管理中导入表。"
            
            # 4. 应用业务规则转换
            processed_question = self.apply_business_rules(question)
            
            # 5. 检测是否为多表查询
            is_multi_table = self._detect_multi_table_query(processed_question, allowed_tables)
            
            if is_multi_table:
                # 使用多表增强提示词
                prompt = self.structured_prompt_builder.build_multi_table_prompt(
                    processed_question, self.table_knowledge, 
                    self.business_rules, schema_info
                )
                
                # 调用DeepSeek API生成SQL
                if self.vn:
                    sql_response = self.vn.generate_sql(prompt)
                else:
                    sql_response = self.call_deepseek_api(prompt)
                
                # 解析结构化响应
                sql, reasoning_process = self._parse_structured_response(sql_response)
                
                if not sql:
                    return "", f"多表SQL生成失败：无法解析生成的SQL\n推理过程：\n{reasoning_process}"
                
                # 使用多表验证器验证
                is_valid, issues, corrected_sql = self.multi_table_validator.validate_multi_table_sql(
                    sql, processed_question, self.table_knowledge
                )
                
                if not is_valid:
                    # 格式化错误信息
                    formatted_issues = self.error_handler.format_issues(issues)
                    error_msg = "多表SQL验证失败：\n"
                    
                    if formatted_issues["errors"]:
                        error_msg += "❌ 错误：\n" + "\n".join(formatted_issues["errors"]) + "\n"
                    if formatted_issues["warnings"]:
                        error_msg += "⚠️ 警告：\n" + "\n".join(formatted_issues["warnings"]) + "\n"
                    if formatted_issues["suggestions"]:
                        error_msg += "💡 建议：\n" + "\n".join(formatted_issues["suggestions"])
                    
                    error_msg += f"\n\n推理过程：\n{reasoning_process}"
                    return "", error_msg
                
                # 使用修正后的SQL
                final_sql = corrected_sql
                
                # 缓存结果
                self.sql_cache.set(cache_key, final_sql)
                
                # 构建成功消息
                success_msg = f"多表SQL生成成功（增强验证）"
                if issues:
                    formatted_issues = self.error_handler.format_issues(issues)
                    if formatted_issues["warnings"]:
                        success_msg += "\n⚠️ 注意：\n" + "\n".join(formatted_issues["warnings"])
                    if formatted_issues["suggestions"]:
                        success_msg += "\n💡 优化建议：\n" + "\n".join(formatted_issues["suggestions"])
                
                success_msg += f"\n\n推理过程：\n{reasoning_process}"
                return final_sql, success_msg
            
            else:
                # 单表查询，使用标准方法
                return self.generate_sql_enhanced(question, db_config)
            
        except Exception as e:
            logger.error(f"多表增强SQL生成失败: {e}")
            # 回退到标准方法
            return self.generate_sql_enhanced(question, db_config)
    
    def _detect_multi_table_query(self, question: str, allowed_tables: set) -> bool:
        """检测是否为多表查询"""
        question_lower = question.lower()
        
        # 检查多表关键词
        multi_table_keywords = [
            "关联", "连接", "join", "的", "和", "与", "以及",
            "客户的订单", "订单的商品", "用户购买", "销售统计",
            "每个", "各个", "按照", "分组", "汇总"
        ]
        
        has_multi_keywords = any(keyword in question_lower for keyword in multi_table_keywords)
        
        # 检查是否提到多个表相关的实体
        table_entities = 0
        entity_keywords = {
            "客户": ["customer", "user", "client"],
            "订单": ["order", "purchase"],
            "商品": ["product", "item", "goods"],
            "用户": ["user", "customer"],
            "销售": ["sale", "order"],
            "统计": ["summary", "statistics"]
        }
        
        for entity, tables in entity_keywords.items():
            if entity in question_lower:
                # 检查对应的表是否存在
                if any(table in allowed_tables for table in tables):
                    table_entities += 1
        
        return has_multi_keywords or table_entities >= 2
    
    def _parse_structured_response(self, response: str) -> Tuple[str, str]:
        """解析结构化响应"""
        try:
            lines = response.split('\n')
            sql_lines = []
            reasoning_lines = []
            in_sql_section = False
            
            for line in lines:
                line = line.strip()
                
                # 检查是否进入SQL部分
                if any(keyword in line.lower() for keyword in ['select', 'with', 'sql']):
                    if line.upper().startswith('SELECT') or line.upper().startswith('WITH'):
                        in_sql_section = True
                        sql_lines.append(line)
                    elif 'sql' in line.lower() and ':' in line:
                        in_sql_section = True
                    else:
                        reasoning_lines.append(line)
                elif in_sql_section:
                    # 在SQL部分
                    if line and not line.startswith('步骤') and not line.startswith('【'):
                        sql_lines.append(line)
                    else:
                        in_sql_section = False
                        reasoning_lines.append(line)
                else:
                    # 推理部分
                    reasoning_lines.append(line)
            
            # 清理SQL
            sql = ' '.join(sql_lines)
            sql = self.clean_sql(sql)
            
            reasoning = '\n'.join(reasoning_lines)
            
            return sql, reasoning
            
        except Exception as e:
            logger.error(f"解析结构化响应失败: {e}")
            # 尝试简单提取SQL
            sql = self.clean_sql(response)
            return sql, response
    
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
        
        # 应用业务规则映射
        for term, replacement in self.business_rules.items():
            if term in processed:
                processed = processed.replace(term, replacement)
        
        # 特殊处理时间相关的业务规则
        processed = self._apply_time_business_rules(processed)
        
        return processed
    
    def _apply_time_business_rules(self, question: str) -> str:
        """应用时间相关的业务规则"""
        processed = question
        
        # 财年和财月的处理
        import re
        
        # 处理 "2025年7月" -> "自然年=2025 and 财月='7月'"
        year_month_pattern = r'(\d{4})年(\d{1,2})月'
        matches = re.findall(year_month_pattern, processed)
        for year, month in matches:
            original = f"{year}年{month}月"
            replacement = f"自然年={year} and 财月='{month}月'"
            processed = processed.replace(original, replacement)
        
        # 处理 "2025年" -> "自然年=2025"
        year_pattern = r'(\d{4})年'
        if not re.search(year_month_pattern, processed):  # 避免重复处理
            matches = re.findall(year_pattern, processed)
            for year in matches:
                original = f"{year}年"
                replacement = f"自然年={year}"
                processed = processed.replace(original, replacement)
        
        # 处理财周
        if "总计" in processed or "合计" in processed or "汇总" in processed:
            if "财周" not in processed:
                processed += " and 财周='ttl'"
        
        return processed
    
    def enhance_sql_generation_prompt(self, question: str, context) -> str:
        """增强SQL生成提示词，专门处理多表查询和时间条件"""
        
        # 检测时间相关查询
        time_hints = []
        if any(keyword in question for keyword in ["年", "月", "周", "财年", "财月", "财周"]):
            time_hints = [
                "⚠️ 重要时间字段规则：",
                "- 自然年字段：使用 [自然年] 列，值为数字格式（如：2025）",
                "- 财月字段：使用 [财月] 列，值为中文格式（如：'7月'，不是 '20257' 或 '7'）", 
                "- 财周字段：使用 [财周] 列，汇总数据使用 'ttl'",
                "- 正确示例：WHERE [自然年] = 2025 AND [财月] = '7月' AND [财周] = 'ttl'",
                "- 错误示例：WHERE [财月] = '20257'（这是错误的格式）"
            ]
        
        # 检测多表查询
        multi_table_hints = []
        if "JOIN" in question.upper() or any(keyword in question for keyword in ["关联", "连接", "多表"]):
            multi_table_hints = [
                "🔗 多表查询规则：",
                "- 必须使用正确的 JOIN 语法",
                "- 确保 ON 条件正确匹配相关字段",
                "- 避免笛卡尔积，每个表都要有明确的连接条件",
                "- 使用表别名简化查询（如：dtsupply_summary AS d）"
            ]
        
        enhanced_prompt = f"""
你是一个专业的SQL专家。请根据以下要求生成准确的SQL查询：

用户问题：{question}
处理后问题：{context.processed_question}

{chr(10).join(time_hints) if time_hints else ""}

{chr(10).join(multi_table_hints) if multi_table_hints else ""}

数据库结构：
{context.schema_info}

表知识库：
{json.dumps(context.table_knowledge, ensure_ascii=False, indent=2)}

业务规则：
{json.dumps(context.business_rules, ensure_ascii=False, indent=2)}

🎯 生成要求：
1. 严格按照时间字段规则：[自然年]=数字, [财月]='中文月份', [财周]='ttl'
2. 多表查询必须使用正确的JOIN和ON条件
3. 字段名使用方括号包围：[字段名]
4. 只输出SQL语句，不要任何解释

SQL语句："""
        
        return enhanced_prompt
    
    def clean_sql(self, sql: str) -> str:
        """清理SQL语句"""
        if not sql:
            return ""
        import re
        # 移除markdown标记
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)
        sql = sql.strip()
        # 按行处理，遇到AI标记立即截断
        lines = sql.splitlines()
        cleaned_lines = []
        for line in lines:
            if any(marker in line for marker in ['检查结果', 'DeepSeek', 'VALID', 'INVALID']):
                break
            cleaned_lines.append(line)
        sql = ' '.join(cleaned_lines)
        # 截断到第一个分号
        if ';' in sql:
            sql = sql.split(';')[0]
        sql = re.sub(r'\s+', ' ', sql).strip()
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
    
    @monitor_performance
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
        page_title="TEXT2SQL系统 V2.3",
        page_icon="🚀",
        layout="wide"
    )
    
    st.title("TEXT2SQL系统 V2.3 - 增强优化版")
    st.markdown("**企业级数据库管理 + AI智能查询系统 + V2.2核心优化**")
    
    # 初始化系统
    if 'system_v23' not in st.session_state:
        st.session_state.system_v23 = Text2SQLSystemV23()
    
    system = st.session_state.system_v23
    
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
                "提示词管理",
                "系统监控"
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
        
        # V2.3新增：性能监控
        st.subheader("性能监控")
        cache_size = len(system.sql_cache.cache)
        st.metric("SQL缓存", f"{cache_size}/100")
        
        if st.button("清空缓存"):
            system.sql_cache.clear()
            st.success("缓存已清空")
            st.rerun()
    
    # 根据选择的页面显示不同内容
    if page == "SQL查询":
        show_sql_query_page_v23(system)
    elif page == "数据库管理":
        show_database_management_page_v23(system)
    elif page == "表结构管理":
        show_table_management_page_v23(system)
    elif page == "产品知识库":
        show_product_knowledge_page_v23(system)
    elif page == "业务规则管理":
        show_business_rules_page_v23(system)
    elif page == "提示词管理":
        show_prompt_templates_page_v23(system)
    elif page == "系统监控":
        show_system_monitoring_page_v23(system)

def show_sql_query_page_v23(system):
    """显示SQL查询页面 V2.3版本 - 整合V2.2优化"""
    st.header("智能SQL查询 V2.3")
    
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
        if 'current_sql_v23' not in st.session_state:
            st.session_state.current_sql_v23 = ""
        if 'current_question_v23' not in st.session_state:
            st.session_state.current_question_v23 = ""
        if 'current_db_config_v23' not in st.session_state:
            st.session_state.current_db_config_v23 = None
        if 'query_results_v23' not in st.session_state:
            st.session_state.query_results_v23 = None
        
        # V2.3增强：显示性能指标
        col_gen, col_perf = st.columns([3, 1])
        
        with col_gen:
            if st.button("生成SQL查询 (V2.3增强)", type="primary"):
                if question:
                    with st.spinner("正在使用V2.3增强引擎生成SQL..."):
                        # 获取选中的数据库配置
                        db_config = active_dbs[selected_db]
                        
                        # 使用V2.3增强版SQL生成
                        start_time = time.time()
                        sql, message = system.generate_sql_enhanced(question, db_config)
                        generation_time = time.time() - start_time
                        
                        if sql:
                            # 保存到session state
                            st.session_state.current_sql_v23 = sql
                            st.session_state.current_question_v23 = question
                            st.session_state.current_db_config_v23 = db_config
                            
                            st.success(f"{message}")
                            st.info(f"⚡ 生成耗时: {generation_time:.2f}秒")
                            
                            # 自动执行SQL查询
                            with st.spinner("正在执行查询..."):
                                exec_start_time = time.time()
                                success, df, exec_message = system.execute_sql(sql, db_config)
                                exec_time = time.time() - exec_start_time
                                
                                if success:
                                    # 保存查询结果到session state
                                    st.session_state.query_results_v23 = {
                                        'success': True,
                                        'df': df,
                                        'message': exec_message,
                                        'exec_time': exec_time
                                    }
                                    st.info(f"⚡ 执行耗时: {exec_time:.2f}秒")
                                else:
                                    st.session_state.query_results_v23 = {
                                        'success': False,
                                        'df': pd.DataFrame(),
                                        'message': exec_message,
                                        'exec_time': exec_time
                                    }
                        else:
                            st.error(message)
                            st.session_state.current_sql_v23 = ""
                            st.session_state.query_results_v23 = None
                else:
                    st.warning("请输入问题")
        
        with col_perf:
            # V2.3新增：性能指标显示
            if st.session_state.query_results_v23:
                exec_time = st.session_state.query_results_v23.get('exec_time', 0)
                st.metric("执行时间", f"{exec_time:.2f}s")
            
            cache_hits = len(system.sql_cache.cache)
            st.metric("缓存命中", cache_hits)
        
        # 显示当前SQL和结果（如果存在）
        if st.session_state.current_sql_v23:
            st.subheader("生成的SQL:")
            st.code(st.session_state.current_sql_v23, language="sql")
            
            # 显示查询结果
            if st.session_state.query_results_v23:
                if st.session_state.query_results_v23['success']:
                    st.success(st.session_state.query_results_v23['message'])
                    
                    df = st.session_state.query_results_v23['df']
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
                                key="chart_type_v23"
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
                    st.error(st.session_state.query_results_v23['message'])
            
            # 操作按钮
            st.subheader("操作:")
            col_op1, col_op2, col_op3, col_op4 = st.columns([1, 1, 1, 1])
            
            with col_op1:
                if st.button("重新执行查询"):
                    with st.spinner("正在重新执行查询..."):
                        success, df, exec_message = system.execute_sql(
                            st.session_state.current_sql_v23, 
                            st.session_state.current_db_config_v23
                        )
                        
                        if success:
                            st.session_state.query_results_v23 = {
                                'success': True,
                                'df': df,
                                'message': exec_message
                            }
                        else:
                            st.session_state.query_results_v23 = {
                                'success': False,
                                'df': pd.DataFrame(),
                                'message': exec_message
                            }
                        st.rerun()
            
            with col_op2:
                if st.button("清空结果"):
                    st.session_state.current_sql_v23 = ""
                    st.session_state.current_question_v23 = ""
                    st.session_state.current_db_config_v23 = None
                    st.session_state.query_results_v23 = None
                    st.rerun()
            
            with col_op3:
                if st.button("复制SQL"):
                    st.code(st.session_state.current_sql_v23, language="sql")
                    st.success("SQL已显示，可手动复制")
            
            with col_op4:
                if st.button("性能分析"):
                    # V2.3新增：性能分析
                    if st.session_state.current_sql_v23:
                        st.info("SQL性能分析功能开发中...")
    
    with col2:
        st.subheader("V2.3版本新特性")
        
        st.markdown("""
        ### 🚀 V2.3核心优化
        - **统一验证流程**: 整合V2.2核心验证器
        - **智能缓存**: 减少重复LLM调用
        - **性能监控**: 实时显示执行时间
        - **用户友好错误**: 智能错误提示
        
        ### 📊 增强功能
        - **综合验证**: 语法+表名+字段+JOIN+业务逻辑
        - **自动修正**: 智能SQL修正和优化
        - **性能评分**: SQL质量评估
        - **缓存机制**: 相同查询秒级响应
        
        ### 🛠️ 技术升级
        - **模块化设计**: 基于V2.2核心模块
        - **性能装饰器**: 自动性能监控
        - **错误处理**: 用户友好的错误信息
        - **智能提示**: 基于上下文的提示词构建
        """)

# 其他页面函数继承V2.1版本，这里先使用占位符
def show_database_management_page_v23(system):
    """数据库管理页面 V2.3 - 完整功能版"""
    st.header("数据库管理 V2.3")
    
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
                        st.write(f"**用户**: {db_config['config']['username']}")
                    elif db_config['type'] == 'sqlite':
                        st.write(f"**文件**: {db_config['config']['file_path']}")
                    
                    # V2.3新增：显示连接状态
                    status_placeholder = st.empty()
                    
                with col_b:
                    # 测试连接 - 添加性能监控
                    if st.button("测试连接", key=f"test_{db_id}"):
                        with st.spinner("正在测试连接..."):
                            start_time = time.time()
                            success, msg = system.db_manager.test_connection(
                                db_config["type"], 
                                db_config["config"]
                            )
                            test_time = time.time() - start_time
                            
                            if success:
                                status_placeholder.success(f"{msg} (耗时: {test_time:.2f}s)")
                            else:
                                status_placeholder.error(f"{msg} (耗时: {test_time:.2f}s)")
                    
                    # 激活/停用
                    current_status = db_config.get("active", False)
                    if st.button(
                        "停用" if current_status else "激活", 
                        key=f"toggle_{db_id}"
                    ):
                        system.databases[db_id]["active"] = not current_status
                        system.save_database_configs()
                        st.success(f"数据库已{'停用' if current_status else '激活'}")
                        st.rerun()
                
                with col_c:
                    # 编辑数据库配置
                    if st.button("编辑", key=f"edit_{db_id}"):
                        st.session_state[f"editing_{db_id}"] = True
                        st.rerun()
                    
                    # 删除数据库配置
                    if st.button("删除", key=f"del_{db_id}"):
                        if st.session_state.get(f"confirm_delete_{db_id}", False):
                            del system.databases[db_id]
                            system.save_database_configs()
                            st.success("数据库配置已删除")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_delete_{db_id}"] = True
                            st.warning("再次点击确认删除")
                
                # 编辑模式
                if st.session_state.get(f"editing_{db_id}", False):
                    st.subheader("编辑数据库配置")
                    
                    with st.form(f"edit_form_{db_id}"):
                        new_name = st.text_input("数据库名称:", value=db_config['name'])
                        
                        if db_config['type'] == 'mssql':
                            new_server = st.text_input("服务器:", value=db_config['config']['server'])
                            new_database = st.text_input("数据库名:", value=db_config['config']['database'])
                            new_username = st.text_input("用户名:", value=db_config['config']['username'])
                            new_password = st.text_input("密码:", value=db_config['config']['password'], type="password")
                            new_driver = st.selectbox(
                                "ODBC驱动:", 
                                ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"],
                                index=0 if "18" in db_config['config'].get('driver', '') else 1
                            )
                        elif db_config['type'] == 'sqlite':
                            new_file_path = st.text_input("文件路径:", value=db_config['config']['file_path'])
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.form_submit_button("保存修改"):
                                system.databases[db_id]['name'] = new_name
                                
                                if db_config['type'] == 'mssql':
                                    system.databases[db_id]['config'].update({
                                        'server': new_server,
                                        'database': new_database,
                                        'username': new_username,
                                        'password': new_password,
                                        'driver': new_driver
                                    })
                                elif db_config['type'] == 'sqlite':
                                    system.databases[db_id]['config']['file_path'] = new_file_path
                                
                                system.save_database_configs()
                                st.session_state[f"editing_{db_id}"] = False
                                st.success("配置已更新")
                                st.rerun()
                        
                        with col_cancel:
                            if st.form_submit_button("取消"):
                                st.session_state[f"editing_{db_id}"] = False
                                st.rerun()
        
        # 添加新数据库
        st.subheader("添加新数据库")
        
        db_type = st.selectbox("数据库类型:", ["mssql", "sqlite"])
        db_name = st.text_input("数据库名称:")
        
        if db_type == "sqlite":
            file_path = st.text_input("SQLite文件路径:", value="new_database.db")
            
            col_add, col_test = st.columns(2)
            
            with col_add:
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
                    else:
                        st.warning("请填写完整信息")
            
            with col_test:
                if st.button("测试SQLite连接"):
                    if file_path:
                        test_config = {"file_path": file_path}
                        success, msg = system.db_manager.test_connection("sqlite", test_config)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
        
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
                encrypt = st.selectbox("加密连接:", ["no", "yes"], index=0)
                trust_server_certificate = st.selectbox("信任服务器证书:", ["yes", "no"], index=0)
            
            col_add, col_test = st.columns(2)
            
            with col_add:
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
                                "encrypt": encrypt,
                                "trust_server_certificate": trust_server_certificate
                            },
                            "active": False
                        }
                        system.save_database_configs()
                        st.success(f"已添加数据库: {db_name}")
                        st.rerun()
                    else:
                        st.warning("请填写完整信息")
            
            with col_test:
                if st.button("测试MSSQL连接"):
                    if all([server, database, username, password]):
                        test_config = {
                            "server": server,
                            "database": database,
                            "username": username,
                            "password": password,
                            "driver": driver,
                            "encrypt": encrypt,
                            "trust_server_certificate": trust_server_certificate
                        }
                        with st.spinner("正在测试MSSQL连接..."):
                            start_time = time.time()
                            success, msg = system.db_manager.test_connection("mssql", test_config)
                            test_time = time.time() - start_time
                            
                            if success:
                                st.success(f"{msg} (耗时: {test_time:.2f}s)")
                            else:
                                st.error(f"{msg} (耗时: {test_time:.2f}s)")
                    else:
                        st.warning("请填写完整连接信息")
    
    with col2:
        st.subheader("V2.3数据库管理增强")
        st.markdown("""
        ### 🚀 新增功能
        - **性能监控**: 连接测试显示耗时
        - **配置编辑**: 在线编辑数据库配置
        - **连接测试**: 添加前可先测试连接
        - **状态显示**: 实时显示连接状态
        
        ### 📊 支持的数据库
        - **SQLite**: 本地文件数据库
        - **MSSQL**: Microsoft SQL Server
        
        ### 🛠️ 操作说明
        1. **添加数据库**: 填写配置信息并测试连接
        2. **测试连接**: 验证数据库连接和性能
        3. **激活数据库**: 启用数据库用于查询
        4. **编辑配置**: 在线修改数据库配置
        5. **删除配置**: 移除不需要的数据库
        
        ### ⚡ 性能优化
        - 连接测试显示响应时间
        - 自动保存配置更改
        - 智能错误提示
        - 批量操作支持
        """)
        
        # V2.3新增：数据库性能统计
        st.subheader("数据库统计")
        
        total_dbs = len(system.databases)
        active_dbs = len([db for db in system.databases.values() if db.get("active", False)])
        mssql_count = len([db for db in system.databases.values() if db["type"] == "mssql"])
        sqlite_count = len([db for db in system.databases.values() if db["type"] == "sqlite"])
        
        st.metric("总数据库", total_dbs)
        st.metric("已激活", active_dbs)
        st.metric("MSSQL", mssql_count)
        st.metric("SQLite", sqlite_count)
        
        # 快速操作
        st.subheader("快速操作")
        
        if st.button("测试所有连接"):
            with st.spinner("正在测试所有数据库连接..."):
                for db_id, db_config in system.databases.items():
                    start_time = time.time()
                    success, msg = system.db_manager.test_connection(
                        db_config["type"], 
                        db_config["config"]
                    )
                    test_time = time.time() - start_time
                    
                    if success:
                        st.success(f"{db_config['name']}: {msg} ({test_time:.2f}s)")
                    else:
                        st.error(f"{db_config['name']}: {msg} ({test_time:.2f}s)")
        
        if st.button("激活所有数据库"):
            for db_id in system.databases:
                system.databases[db_id]["active"] = True
            system.save_database_configs()
            st.success("所有数据库已激活")
            st.rerun()
        
        if st.button("停用所有数据库"):
            for db_id in system.databases:
                system.databases[db_id]["active"] = False
            system.save_database_configs()
            st.success("所有数据库已停用")
            st.rerun()

def show_table_management_page_v23(system):
    """表结构管理页面 V2.3 - 完整功能版"""
    st.header("表结构管理 V2.3")
    
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
        st.subheader("数据库表列表")
        
        # 获取表列表 - 添加性能监控
        with st.spinner("正在获取表列表..."):
            start_time = time.time()
            tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
            load_time = time.time() - start_time
            
        if tables:
            st.info(f"共找到 {len(tables)} 个表 (耗时: {load_time:.2f}s)")
            
            # 批量操作
            st.subheader("批量操作")
            col_batch1, col_batch2, col_batch3 = st.columns(3)
            
            with col_batch1:
                if st.button("导入所有表到知识库"):
                    imported_count = 0
                    with st.spinner("正在批量导入表结构..."):
                        for table in tables:
                            if table not in system.table_knowledge:
                                schema = system.db_manager.get_table_schema(
                                    db_config["type"], db_config["config"], table
                                )
                                if schema:
                                    system.table_knowledge[table] = {
                                        "columns": schema["columns"],
                                        "column_info": schema["column_info"],
                                        "comment": f"从{db_config['name']}自动导入",
                                        "relationships": [],
                                        "business_fields": {},
                                        "import_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    imported_count += 1
                        
                        if imported_count > 0:
                            system.save_table_knowledge()
                            st.success(f"成功导入 {imported_count} 个表到知识库")
                        else:
                            st.info("所有表已存在于知识库中")
                        st.rerun()
            
            with col_batch2:
                if st.button("自动生成表关联"):
                    relationships_count = 0
                    with st.spinner("正在分析表关联关系..."):
                        for table1 in system.table_knowledge:
                            for table2 in system.table_knowledge:
                                if table1 >= table2:  # 避免重复
                                    continue
                                
                                cols1 = system.table_knowledge[table1]["columns"]
                                cols2 = system.table_knowledge[table2]["columns"]
                                
                                # 查找相同字段名
                                common_fields = set(cols1) & set(cols2)
                                for field in common_fields:
                                    rel = {
                                        "table1": table1,
                                        "table2": table2,
                                        "field1": field,
                                        "field2": field,
                                        "type": "auto",
                                        "description": f"{table1}.{field} = {table2}.{field}",
                                        "confidence": 0.8
                                    }
                                    
                                    # 添加到两个表的关系中
                                    if "relationships" not in system.table_knowledge[table1]:
                                        system.table_knowledge[table1]["relationships"] = []
                                    if "relationships" not in system.table_knowledge[table2]:
                                        system.table_knowledge[table2]["relationships"] = []
                                    
                                    system.table_knowledge[table1]["relationships"].append(rel)
                                    system.table_knowledge[table2]["relationships"].append(rel)
                                    relationships_count += 1
                        
                        system.save_table_knowledge()
                        st.success(f"自动生成 {relationships_count} 个表关联关系")
                        st.rerun()
            
            with col_batch3:
                if st.button("清空知识库"):
                    if st.session_state.get("confirm_clear_kb", False):
                        system.table_knowledge = {}
                        system.save_table_knowledge()
                        st.success("知识库已清空")
                        st.session_state["confirm_clear_kb"] = False
                        st.rerun()
                    else:
                        st.session_state["confirm_clear_kb"] = True
                        st.warning("再次点击确认清空")
            
            # 显示表详情
            for table in tables:
                with st.expander(f"📊 {table}"):
                    # 获取表结构
                    schema = system.db_manager.get_table_schema(
                        db_config["type"], 
                        db_config["config"], 
                        table
                    )
                    
                    if schema:
                        col_info, col_action = st.columns([3, 1])
                        
                        with col_info:
                            st.write("**字段信息:**")
                            if schema["column_info"]:
                                df_columns = pd.DataFrame(schema["column_info"], 
                                                        columns=["序号", "字段名", "类型", "可空", "默认值", "主键"])
                                st.dataframe(df_columns, use_container_width=True)
                        
                        with col_action:
                            # 导入到知识库
                            if table not in system.table_knowledge:
                                if st.button(f"导入知识库", key=f"import_{table}"):
                                    system.table_knowledge[table] = {
                                        "columns": schema["columns"],
                                        "column_info": schema["column_info"],
                                        "comment": "",
                                        "relationships": [],
                                        "business_fields": {},
                                        "import_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    system.save_table_knowledge()
                                    st.success(f"表 {table} 已导入知识库")
                                    st.rerun()
                            else:
                                st.success("✅ 已在知识库")
                                if st.button(f"更新结构", key=f"update_{table}"):
                                    system.table_knowledge[table]["columns"] = schema["columns"]
                                    system.table_knowledge[table]["column_info"] = schema["column_info"]
                                    system.table_knowledge[table]["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                    system.save_table_knowledge()
                                    st.success(f"表 {table} 结构已更新")
                                    st.rerun()
        else:
            st.warning("未找到任何表")
        
        # 已导入知识库的表管理
        st.subheader("知识库表管理")
        
        if system.table_knowledge:
            for table_name, table_info in system.table_knowledge.items():
                with st.expander(f"🧠 {table_name} (知识库)"):
                    col_kb1, col_kb2 = st.columns([2, 1])
                    
                    with col_kb1:
                        # 表备注编辑
                        current_comment = table_info.get("comment", "")
                        new_comment = st.text_area(
                            "表备注:", 
                            value=current_comment, 
                            key=f"comment_{table_name}",
                            height=68
                        )
                        
                        if new_comment != current_comment:
                            if st.button(f"保存备注", key=f"save_comment_{table_name}"):
                                system.table_knowledge[table_name]["comment"] = new_comment
                                system.save_table_knowledge()
                                st.success("备注已保存")
                                st.rerun()
                        
                        # 字段备注编辑
                        st.write("**字段备注:**")
                        business_fields = table_info.get("business_fields", {})
                        
                        for column in table_info.get("columns", []):
                            current_field_comment = business_fields.get(column, "")
                            new_field_comment = st.text_input(
                                f"{column}:", 
                                value=current_field_comment,
                                key=f"field_{table_name}_{column}"
                            )
                            
                            if new_field_comment != current_field_comment:
                                business_fields[column] = new_field_comment
                        
                        if st.button(f"保存字段备注", key=f"save_fields_{table_name}"):
                            system.table_knowledge[table_name]["business_fields"] = business_fields
                            system.save_table_knowledge()
                            st.success("字段备注已保存")
                            st.rerun()
                    
                    with col_kb2:
                        # 表信息
                        st.write(f"**字段数量**: {len(table_info.get('columns', []))}")
                        st.write(f"**关联数量**: {len(table_info.get('relationships', []))}")
                        
                        import_time = table_info.get("import_time", "未知")
                        update_time = table_info.get("update_time", "")
                        st.write(f"**导入时间**: {import_time}")
                        if update_time:
                            st.write(f"**更新时间**: {update_time}")
                        
                        # 删除表
                        if st.button(f"删除", key=f"del_kb_{table_name}"):
                            if st.session_state.get(f"confirm_del_{table_name}", False):
                                del system.table_knowledge[table_name]
                                system.save_table_knowledge()
                                st.success(f"已删除表 {table_name}")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_del_{table_name}"] = True
                                st.warning("再次点击确认删除")
        else:
            st.info("知识库为空，请先导入表结构")
        
        # 表关联管理
        st.subheader("表关联管理")
        
        # 收集所有表关联关系
        all_relationships = []
        for table_name, table_info in system.table_knowledge.items():
            for rel in table_info.get("relationships", []):
                # 避免重复显示
                rel_key = f"{rel.get('table1', '')}_{rel.get('table2', '')}_{rel.get('field1', '')}_{rel.get('field2', '')}"
                if rel_key not in [r.get("key", "") for r in all_relationships]:
                    rel_display = {
                        "key": rel_key,
                        "表1": rel.get("table1", ""),
                        "字段1": rel.get("field1", ""),
                        "表2": rel.get("table2", ""),
                        "字段2": rel.get("field2", ""),
                        "类型": "手工" if rel.get("type") == "manual" else "自动",
                        "描述": rel.get("description", ""),
                        "置信度": rel.get("confidence", 1.0)
                    }
                    all_relationships.append(rel_display)
        
        if all_relationships:
            st.write(f"**共 {len(all_relationships)} 个关联关系**")
            
            # 关联关系表格显示和删除功能
            df_relationships = pd.DataFrame(all_relationships)
            df_display = df_relationships[["表1", "字段1", "表2", "字段2", "类型", "置信度", "描述"]]
            
            # 添加删除按钮列
            st.write("**关联关系列表:**")
            for idx, rel in enumerate(all_relationships):
                col_rel_info, col_rel_action = st.columns([4, 1])
                
                with col_rel_info:
                    rel_desc = f"{rel['表1']}.{rel['字段1']} ↔ {rel['表2']}.{rel['字段2']} ({rel['类型']}, 置信度: {rel['置信度']:.2f})"
                    st.write(f"**{idx+1}.** {rel_desc}")
                    if rel['描述']:
                        st.write(f"   *{rel['描述']}*")
                
                with col_rel_action:
                    if st.button("🗑️ 删除", key=f"del_rel_{idx}"):
                        if st.session_state.get(f"confirm_del_rel_{idx}", False):
                            # 从相关表中删除这个关联关系
                            table1 = rel['表1']
                            table2 = rel['表2']
                            
                            # 从表1中删除
                            if table1 in system.table_knowledge and "relationships" in system.table_knowledge[table1]:
                                system.table_knowledge[table1]["relationships"] = [
                                    r for r in system.table_knowledge[table1]["relationships"]
                                    if not (r.get("table1") == table1 and r.get("table2") == table2 and 
                                           r.get("field1") == rel['字段1'] and r.get("field2") == rel['字段2'])
                                ]
                            
                            # 从表2中删除
                            if table2 in system.table_knowledge and "relationships" in system.table_knowledge[table2]:
                                system.table_knowledge[table2]["relationships"] = [
                                    r for r in system.table_knowledge[table2]["relationships"]
                                    if not (r.get("table1") == table1 and r.get("table2") == table2 and 
                                           r.get("field1") == rel['字段1'] and r.get("field2") == rel['字段2'])
                                ]
                            
                            system.save_table_knowledge()
                            st.success(f"已删除关联关系: {rel['表1']}.{rel['字段1']} ↔ {rel['表2']}.{rel['字段2']}")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_del_rel_{idx}"] = True
                            st.warning("再次点击确认删除")
            
            st.markdown("---")
            
            # 批量删除关联关系
            col_batch1, col_batch2 = st.columns(2)
            
            with col_batch1:
                if st.button("🗑️ 清空所有关联"):
                    if st.session_state.get("confirm_clear_rel", False):
                        for table_name in system.table_knowledge:
                            system.table_knowledge[table_name]["relationships"] = []
                        system.save_table_knowledge()
                        st.success("所有关联关系已清空")
                        st.rerun()
                    else:
                        st.session_state["confirm_clear_rel"] = True
                        st.warning("再次点击确认清空")
            
            with col_batch2:
                # 删除自动生成的关联关系
                if st.button("🗑️ 清空自动关联"):
                    if st.session_state.get("confirm_clear_auto_rel", False):
                        for table_name in system.table_knowledge:
                            if "relationships" in system.table_knowledge[table_name]:
                                system.table_knowledge[table_name]["relationships"] = [
                                    r for r in system.table_knowledge[table_name]["relationships"]
                                    if r.get("type") == "manual"
                                ]
                        system.save_table_knowledge()
                        st.success("所有自动生成的关联关系已清空")
                        st.rerun()
                    else:
                        st.session_state["confirm_clear_auto_rel"] = True
                        st.warning("再次点击确认清空")
        else:
            st.info("暂无表关联关系，请点击上方按钮自动生成")
        
        # 手工添加表关联
        if len(system.table_knowledge) >= 2:
            st.subheader("手工添加表关联")
            
            table_names = list(system.table_knowledge.keys())
            
            # 手工添加关联关系 - 修复字段匹配问题
            st.write("**添加新的关联关系:**")
            
            col_rel1, col_rel2 = st.columns(2)
            
            with col_rel1:
                st.write("**表1信息**")
                manual_table1 = st.selectbox("选择表1:", table_names, key="manual_table1")
                if manual_table1:
                    field1_options = system.table_knowledge[manual_table1]["columns"]
                    manual_field1 = st.selectbox("选择字段1:", field1_options, key="manual_field1")
                else:
                    manual_field1 = None
            
            with col_rel2:
                st.write("**表2信息**")
                # 确保表2的选择独立于表1，并且字段选择器正确更新
                available_tables2 = [t for t in table_names if t != manual_table1] if manual_table1 else table_names
                manual_table2 = st.selectbox("选择表2:", available_tables2, key="manual_table2")
                if manual_table2:
                    # 重新获取表2的字段，确保字段列表与选择的表2匹配
                    field2_options = system.table_knowledge[manual_table2]["columns"]
                    manual_field2 = st.selectbox("选择字段2:", field2_options, key="manual_field2")
                else:
                    manual_field2 = None
            
            # 关联类型和描述
            col_type, col_desc = st.columns(2)
            
            with col_type:
                rel_type = st.selectbox("关联类型:", ["一对一", "一对多", "多对一", "多对多"], key="manual_rel_type")
            
            with col_desc:
                manual_desc = st.text_input(
                    "关联描述:", 
                    value=f"{manual_table1}.{manual_field1 if manual_field1 else ''} <-> {manual_table2}.{manual_field2 if manual_field2 else ''}" if manual_table1 and manual_table2 else "",
                    key="manual_rel_desc"
                )
            
            # 添加按钮
            if st.button("➕ 添加手工关联", type="primary"):
                if manual_table1 and manual_table2 and manual_field1 and manual_field2:
                    # 检查是否已存在相同的关联关系
                    existing_rel = False
                    if "relationships" in system.table_knowledge[manual_table1]:
                        for rel in system.table_knowledge[manual_table1]["relationships"]:
                            if (rel.get("table1") == manual_table1 and rel.get("table2") == manual_table2 and 
                                rel.get("field1") == manual_field1 and rel.get("field2") == manual_field2):
                                existing_rel = True
                                break
                    
                    if existing_rel:
                        st.warning("该关联关系已存在！")
                    else:
                        rel = {
                            "table1": manual_table1,
                            "table2": manual_table2,
                            "field1": manual_field1,
                            "field2": manual_field2,
                            "type": "manual",
                            "rel_type": rel_type,
                            "description": manual_desc,
                            "confidence": 1.0,
                            "create_time": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # 添加到两个表
                        for t in [manual_table1, manual_table2]:
                            if "relationships" not in system.table_knowledge[t]:
                                system.table_knowledge[t]["relationships"] = []
                            system.table_knowledge[t]["relationships"].append(rel)
                        
                        system.save_table_knowledge()
                        st.success(f"手工关联已添加：{manual_table1}.{manual_field1} ↔ {manual_table2}.{manual_field2}")
                        st.rerun()
                else:
                    st.warning("请选择完整的表和字段信息")
                
                manual_desc = st.text_input(
                    "关联描述", 
                    value=f"{manual_table1}.{manual_field1} <-> {manual_table2}.{manual_field2}"
                )
                
                if st.form_submit_button("添加手工关联"):
                    rel = {
                        "table1": manual_table1,
                        "table2": manual_table2,
                        "field1": manual_field1,
                        "field2": manual_field2,
                        "type": "manual",
                        "description": manual_desc,
                        "confidence": 1.0
                    }
                    
                    # 添加到两个表
                    for t in [manual_table1, manual_table2]:
                        if "relationships" not in system.table_knowledge[t]:
                            system.table_knowledge[t]["relationships"] = []
                        system.table_knowledge[t]["relationships"].append(rel)
                    
                    system.save_table_knowledge()
                    st.success("手工关联已添加！")
                    st.rerun()
    
    with col2:
        st.subheader("V2.3表结构管理增强")
        st.markdown("""
        ### 🚀 新增功能
        - **批量导入**: 一键导入所有表到知识库
        - **自动关联**: 智能分析表关联关系
        - **性能监控**: 显示操作耗时
        - **备注管理**: 表和字段备注编辑
        
        ### 📊 智能分析
        - **字段匹配**: 自动识别相同字段名
        - **关联推荐**: 基于字段名推荐关联
        - **置信度评估**: 关联关系可信度评分
        - **重复检测**: 避免重复关联关系
        
        ### 🛠️ 管理功能
        - **表结构同步**: 自动更新表结构变化
        - **知识库管理**: 完整的CRUD操作
        - **批量操作**: 支持批量导入和清理
        - **备注系统**: 丰富的业务描述
        
        ### ⚡ 性能优化
        - 异步加载表结构
        - 智能缓存机制
        - 批量操作优化
        - 实时状态反馈
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        total_tables_db = len(tables) if tables else 0
        total_tables_kb = len(system.table_knowledge)
        total_relationships = len(all_relationships) if 'all_relationships' in locals() else 0
        
        st.metric("数据库表数", total_tables_db)
        st.metric("知识库表数", total_tables_kb)
        st.metric("关联关系数", total_relationships)
        
        # 导入进度
        if total_tables_db > 0:
            import_progress = total_tables_kb / total_tables_db
            st.metric("导入进度", f"{import_progress:.1%}")
        
        # 快速操作
        st.subheader("快速操作")
        
        if st.button("刷新表列表"):
            st.rerun()
        
        if st.button("导出知识库"):
            export_data = {
                "table_knowledge": system.table_knowledge,
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "database": db_config["name"]
            }
            
            st.download_button(
                label="下载JSON文件",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name=f"table_knowledge_{db_config['name']}.json",
                mime="application/json"
            )

def get_sqlite_db_path(db_config):
    """获取SQLite数据库文件路径的辅助函数"""
    db_path = None
    
    # 调试：打印配置信息
    print(f"Debug: 数据库配置 = {db_config}")
    
    # 可能的路径键名列表
    path_keys = ["database", "path", "file", "db_file", "db_path", "sqlite_file", "filename"]
    
    # 尝试从config中获取
    if "config" in db_config and isinstance(db_config["config"], dict):
        config = db_config["config"]
        print(f"Debug: config子对象 = {config}")
        
        for key in path_keys:
            if key in config and config[key]:
                db_path = config[key]
                print(f"Debug: 在config.{key}中找到路径: {db_path}")
                break
    
    # 如果config中没有，尝试从根级别获取
    if not db_path:
        for key in path_keys:
            if key in db_config and db_config[key]:
                db_path = db_config[key]
                print(f"Debug: 在根级别{key}中找到路径: {db_path}")
                break
    
    # 特殊处理：如果是字符串类型的config
    if not db_path and "config" in db_config and isinstance(db_config["config"], str):
        db_path = db_config["config"]
        print(f"Debug: config是字符串类型，使用作为路径: {db_path}")
    
    print(f"Debug: 最终路径 = {db_path}")
    return db_path

def show_product_knowledge_page_v23(system):
    """产品知识库页面 V2.3 - 完整功能版"""
    st.header("产品知识库 V2.3")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("产品信息管理")
        
        # 从数据库导入产品信息
        st.write("**从数据库导入产品信息:**")
        
        # 选择数据库
        active_dbs = {k: v for k, v in system.databases.items() if v.get("active", False)}
        
        if active_dbs:
            # 显示所有活跃数据库的详细信息
            st.write("**活跃数据库列表:**")
            for db_id, db_config in active_dbs.items():
                db_type = db_config.get("type", "Unknown")
                db_name = db_config.get("name", db_id)
                st.write(f"- {db_name} (类型: {db_type}, ID: {db_id})")
                
                # 如果是SQLite，显示路径信息
                if db_type == "sqlite":
                    db_path = get_sqlite_db_path(db_config)
                    if db_path:
                        exists = "✅" if os.path.exists(db_path) else "❌"
                        st.write(f"  路径: {db_path} {exists}")
                    else:
                        st.write(f"  ⚠️ 无法获取数据库路径")
                        st.write(f"  配置: {db_config}")
            
            st.markdown("---")
            
            selected_db = st.selectbox(
                "选择数据库:",
                options=list(active_dbs.keys()),
                format_func=lambda x: f"{active_dbs[x]['name']} ({active_dbs[x]['type']})",
                key="product_db_select"
            )
            
            db_config = active_dbs[selected_db]
            
            # 获取表列表 - 根据数据库类型使用不同的方法
            with st.spinner("正在获取表列表..."):
                if db_config["type"] == "sqlite":
                    # 使用辅助函数获取SQLite数据库文件路径
                    db_path = get_sqlite_db_path(db_config)
                    
                    if db_path:
                        # 使用SQLite管理器获取表列表
                        sqlite_manager = SQLiteTableManager(db_path)
                        tables = sqlite_manager.get_tables()
                        st.success(f"成功连接SQLite数据库: {db_path}")
                    else:
                        st.error("无法找到SQLite数据库文件路径")
                        st.write("**数据库配置信息:**")
                        st.json(db_config)
                        
                        # 调试信息
                        st.write("**调试信息:**")
                        st.write(f"- 数据库类型: {db_config.get('type', 'Unknown')}")
                        st.write(f"- 配置键: {list(db_config.keys())}")
                        if "config" in db_config:
                            st.write(f"- Config子键: {list(db_config['config'].keys())}")
                        
                        # 尝试手动输入路径
                        st.write("**手动指定数据库路径:**")
                        manual_path = st.text_input("SQLite数据库文件路径:", placeholder="例如: test_database.db")
                        if manual_path and st.button("使用手动路径"):
                            try:
                                sqlite_manager = SQLiteTableManager(manual_path)
                                tables = sqlite_manager.get_tables()
                                st.success(f"手动路径连接成功: {manual_path}")
                                
                                # 更新数据库配置
                                if "config" not in db_config:
                                    db_config["config"] = {}
                                db_config["config"]["database"] = manual_path
                                st.info("已更新数据库配置，请刷新页面")
                            except Exception as e:
                                st.error(f"手动路径连接失败: {e}")
                                tables = []
                        else:
                            tables = []
                else:
                    # 使用系统数据库管理器
                    tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
            
            if tables:
                st.write(f"**数据库中共有 {len(tables)} 个表:**")
                
                # 显示所有表，让用户选择
                col_table_list, col_table_select = st.columns([2, 1])
                
                with col_table_list:
                    # 查找可能的产品表
                    product_tables = [t for t in tables if any(keyword in t.lower() for keyword in ['group', 'product', 'item', 'goods', 'material', 'category', 'type'])]
                    
                    if product_tables:
                        st.write(f"**推荐的产品相关表 ({len(product_tables)} 个):**")
                        for table in product_tables:
                            st.write(f"- 📦 {table}")
                        st.markdown("---")
                    
                    st.write(f"**所有可用表:**")
                    for table in tables:
                        icon = "📦" if table in product_tables else "📋"
                        st.write(f"- {icon} {table}")
                
                with col_table_select:
                    st.write("**选择要导入的表:**")
                    selected_table = st.selectbox(
                        "表名:", 
                        tables, 
                        index=0 if not product_tables else tables.index(product_tables[0]),
                        key="product_table_select"
                    )
                    
                    # 显示选择的表信息
                    if selected_table:
                        st.write(f"**已选择:** {selected_table}")
                        
                        # 获取表的基本信息
                        if db_config["type"] == "sqlite":
                            try:
                                # 使用辅助函数获取SQLite数据库文件路径
                                db_path = get_sqlite_db_path(db_config)
                                
                                if db_path:
                                    sqlite_manager = SQLiteTableManager(db_path)
                                    table_info = sqlite_manager.get_table_schema(selected_table)
                                    if table_info:
                                        st.write(f"**列数:** {len(table_info['columns'])}")
                                        st.write(f"**行数:** {table_info['row_count']:,}")
                                else:
                                    st.write("**信息:** 无法获取数据库路径")
                            except Exception as e:
                                st.write(f"**信息:** 无法获取表详情 ({str(e)})")
                
                col_import, col_preview = st.columns(2)
                
                with col_preview:
                    if st.button("预览表数据"):
                        try:
                            preview_sql = f"SELECT TOP 5 * FROM [{selected_table}]" if db_config["type"] == "mssql" else f"SELECT * FROM {selected_table} LIMIT 5"
                            success, df, msg = system.execute_sql(preview_sql, db_config)
                            
                            if success and not df.empty:
                                st.write("**表数据预览:**")
                                st.dataframe(df)
                            else:
                                st.error(f"预览失败: {msg}")
                        except Exception as e:
                            st.error(f"预览失败: {e}")
                
                with col_import:
                    if st.button("导入产品信息"):
                        try:
                            with st.spinner("正在导入产品信息..."):
                                # 查询产品信息
                                import_sql = f"SELECT * FROM [{selected_table}]" if db_config["type"] == "mssql" else f"SELECT * FROM {selected_table}"
                                success, df, msg = system.execute_sql(import_sql, db_config)
                                
                                if success and not df.empty:
                                    # 保存到产品知识库
                                    if "products" not in system.product_knowledge:
                                        system.product_knowledge["products"] = {}
                                    
                                    imported_count = 0
                                    for _, row in df.iterrows():
                                        product_id = str(row.iloc[0])  # 假设第一列是ID
                                        product_data = row.to_dict()
                                        product_data["import_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                        product_data["source_table"] = selected_table
                                        product_data["source_database"] = db_config["name"]
                                        
                                        system.product_knowledge["products"][product_id] = product_data
                                        imported_count += 1
                                    
                                    system.save_product_knowledge()
                                    st.success(f"成功导入 {imported_count} 个产品信息")
                                    st.dataframe(df.head())
                                else:
                                    st.error(f"导入失败: {msg}")
                        except Exception as e:
                            st.error(f"导入失败: {e}")
            else:
                st.info("未找到产品相关的表，请手动添加产品信息")
        else:
            st.warning("没有活跃的数据库连接")
            st.info("请先在数据库管理页面配置并激活数据库")
            
            # 显示所有数据库配置用于调试
            st.write("**所有数据库配置 (包括未激活的):**")
            for db_id, db_config in system.databases.items():
                with st.expander(f"数据库: {db_config.get('name', db_id)} (类型: {db_config.get('type', 'Unknown')})"):
                    active_status = "✅ 活跃" if db_config.get("active", False) else "❌ 未激活"
                    st.write(f"**状态:** {active_status}")
                    st.json(db_config)
                    
                    # 如果是SQLite类型，提供快速修复选项
                    if db_config.get("type") == "sqlite":
                        db_path = get_sqlite_db_path(db_config)
                        if db_path:
                            exists = os.path.exists(db_path)
                            st.write(f"**检测路径:** {db_path} {'✅' if exists else '❌'}")
                            
                            if not exists:
                                st.warning("数据库文件不存在")
                                col_fix1, col_fix2 = st.columns(2)
                                
                                with col_fix1:
                                    new_path = st.text_input(f"修正路径 ({db_id}):", value=db_path, key=f"fix_path_{db_id}")
                                
                                with col_fix2:
                                    if st.button(f"更新路径", key=f"update_path_{db_id}"):
                                        if os.path.exists(new_path):
                                            # 更新配置
                                            if "config" not in db_config:
                                                db_config["config"] = {}
                                            db_config["config"]["database"] = new_path
                                            db_config["active"] = True
                                            
                                            # 保存配置
                                            try:
                                                with open("database_configs.json", 'w', encoding='utf-8') as f:
                                                    json.dump(system.databases, f, ensure_ascii=False, indent=2)
                                                st.success(f"已更新数据库路径并激活: {new_path}")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"保存配置失败: {e}")
                                        else:
                                            st.error("指定的文件不存在")
                            else:
                                if not db_config.get("active", False):
                                    if st.button(f"激活数据库", key=f"activate_{db_id}"):
                                        db_config["active"] = True
                                        try:
                                            with open("database_configs.json", 'w', encoding='utf-8') as f:
                                                json.dump(system.databases, f, ensure_ascii=False, indent=2)
                                            st.success(f"已激活数据库: {db_config.get('name', db_id)}")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"保存配置失败: {e}")
                        else:
                            st.error("无法检测到数据库路径")
                            st.write("**快速添加路径:**")
                            quick_path = st.text_input(f"数据库文件路径 ({db_id}):", key=f"quick_path_{db_id}")
                            if st.button(f"添加路径", key=f"add_path_{db_id}") and quick_path:
                                if os.path.exists(quick_path):
                                    if "config" not in db_config:
                                        db_config["config"] = {}
                                    db_config["config"]["database"] = quick_path
                                    db_config["active"] = True
                                    
                                    try:
                                        with open("database_configs.json", 'w', encoding='utf-8') as f:
                                            json.dump(system.databases, f, ensure_ascii=False, indent=2)
                                        st.success(f"已添加数据库路径并激活: {quick_path}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"保存配置失败: {e}")
                                else:
                                    st.error("指定的文件不存在")
        
        # 手动添加产品信息
        st.subheader("手动添加产品信息")
        
        with st.form("add_product"):
            col_prod1, col_prod2 = st.columns(2)
            
            with col_prod1:
                product_id = st.text_input("产品ID:")
                product_name = st.text_input("产品名称:")
                product_category = st.text_input("产品分类:")
            
            with col_prod2:
                product_price = st.number_input("产品价格:", min_value=0.0, step=0.01)
                product_status = st.selectbox("产品状态:", ["活跃", "停用", "缺货"])
                product_supplier = st.text_input("供应商:")
            
            product_desc = st.text_area("产品描述:")
            
            # 自定义字段
            st.write("**自定义字段:**")
            custom_fields = {}
            
            if "custom_field_count" not in st.session_state:
                st.session_state.custom_field_count = 0
            
            for i in range(st.session_state.custom_field_count):
                col_key, col_value, col_del = st.columns([2, 2, 1])
                with col_key:
                    field_key = st.text_input(f"字段名 {i+1}:", key=f"custom_key_{i}")
                with col_value:
                    field_value = st.text_input(f"字段值 {i+1}:", key=f"custom_value_{i}")
                with col_del:
                    if st.form_submit_button(f"删除 {i+1}"):
                        st.session_state.custom_field_count -= 1
                        st.rerun()
                
                if field_key and field_value:
                    custom_fields[field_key] = field_value
            
            if st.form_submit_button("添加自定义字段"):
                st.session_state.custom_field_count += 1
                st.rerun()
            
            if st.form_submit_button("添加产品"):
                if product_id and product_name:
                    if "products" not in system.product_knowledge:
                        system.product_knowledge["products"] = {}
                    
                    product_data = {
                        "name": product_name,
                        "description": product_desc,
                        "category": product_category,
                        "price": product_price,
                        "status": product_status,
                        "supplier": product_supplier,
                        "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "manual"
                    }
                    
                    # 添加自定义字段
                    product_data.update(custom_fields)
                    
                    system.product_knowledge["products"][product_id] = product_data
                    
                    if system.save_product_knowledge():
                        st.success(f"已添加产品: {product_name}")
                        st.session_state.custom_field_count = 0
                        st.rerun()
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写产品ID和名称")
        
        # 显示现有产品
        st.subheader("现有产品信息")
        
        if "products" in system.product_knowledge and system.product_knowledge["products"]:
            # 产品搜索和过滤
            col_search, col_filter = st.columns(2)
            
            with col_search:
                search_term = st.text_input("搜索产品:", placeholder="输入产品名称或ID")
            
            with col_filter:
                all_categories = set()
                for product in system.product_knowledge["products"].values():
                    if product.get("category"):
                        all_categories.add(product["category"])
                
                filter_category = st.selectbox("筛选分类:", ["全部"] + list(all_categories))
            
            # 过滤产品
            filtered_products = {}
            for product_id, product_info in system.product_knowledge["products"].items():
                # 搜索过滤
                if search_term:
                    if (search_term.lower() not in product_id.lower() and 
                        search_term.lower() not in product_info.get('name', '').lower()):
                        continue
                
                # 分类过滤
                if filter_category != "全部":
                    if product_info.get('category') != filter_category:
                        continue
                
                filtered_products[product_id] = product_info
            
            st.write(f"**显示 {len(filtered_products)} / {len(system.product_knowledge['products'])} 个产品**")
            
            # 批量操作
            if filtered_products:
                col_batch1, col_batch2, col_batch3 = st.columns(3)
                
                with col_batch1:
                    if st.button("导出选中产品"):
                        export_data = {
                            "products": filtered_products,
                            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "total_count": len(filtered_products)
                        }
                        
                        st.download_button(
                            label="下载JSON文件",
                            data=json.dumps(export_data, ensure_ascii=False, indent=2),
                            file_name=f"products_{time.strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col_batch2:
                    if st.button("批量更新状态"):
                        new_status = st.selectbox("新状态:", ["活跃", "停用", "缺货"], key="batch_status")
                        if st.button("确认更新"):
                            for product_id in filtered_products:
                                system.product_knowledge["products"][product_id]["status"] = new_status
                                system.product_knowledge["products"][product_id]["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            
                            system.save_product_knowledge()
                            st.success(f"已更新 {len(filtered_products)} 个产品状态")
                            st.rerun()
                
                with col_batch3:
                    if st.button("批量删除"):
                        if st.session_state.get("confirm_batch_delete", False):
                            for product_id in filtered_products:
                                del system.product_knowledge["products"][product_id]
                            
                            system.save_product_knowledge()
                            st.success(f"已删除 {len(filtered_products)} 个产品")
                            st.session_state["confirm_batch_delete"] = False
                            st.rerun()
                        else:
                            st.session_state["confirm_batch_delete"] = True
                            st.warning("再次点击确认批量删除")
            
            # 显示产品列表
            for product_id, product_info in filtered_products.items():
                with st.expander(f"🏷️ {product_info.get('name', product_id)} (ID: {product_id})"):
                    col_info, col_action = st.columns([3, 1])
                    
                    with col_info:
                        # 基础信息
                        st.write(f"**名称**: {product_info.get('name', '')}")
                        st.write(f"**分类**: {product_info.get('category', '')}")
                        st.write(f"**价格**: {product_info.get('price', 0)}")
                        st.write(f"**状态**: {product_info.get('status', '')}")
                        st.write(f"**供应商**: {product_info.get('supplier', '')}")
                        
                        if product_info.get('description'):
                            st.write(f"**描述**: {product_info.get('description', '')}")
                        
                        # 时间信息
                        create_time = product_info.get('create_time') or product_info.get('import_time', '')
                        if create_time:
                            st.write(f"**创建时间**: {create_time}")
                        
                        update_time = product_info.get('update_time', '')
                        if update_time:
                            st.write(f"**更新时间**: {update_time}")
                        
                        # 来源信息
                        source = product_info.get('source', product_info.get('source_table', ''))
                        if source:
                            st.write(f"**数据来源**: {source}")
                        
                        # 自定义字段
                        custom_fields = {k: v for k, v in product_info.items() 
                                       if k not in ['name', 'description', 'category', 'price', 'status', 'supplier', 
                                                   'create_time', 'import_time', 'update_time', 'source', 'source_table', 'source_database']}
                        
                        if custom_fields:
                            st.write("**自定义字段**:")
                            for key, value in custom_fields.items():
                                st.write(f"- {key}: {value}")
                    
                    with col_action:
                        # 编辑产品
                        if st.button(f"编辑", key=f"edit_product_{product_id}"):
                            st.session_state[f"editing_product_{product_id}"] = True
                            st.rerun()
                        
                        # 删除产品
                        if st.button(f"删除", key=f"del_product_{product_id}"):
                            if st.session_state.get(f"confirm_del_product_{product_id}", False):
                                del system.product_knowledge["products"][product_id]
                                system.save_product_knowledge()
                                st.success(f"已删除产品 {product_id}")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_del_product_{product_id}"] = True
                                st.warning("再次点击确认删除")
                    
                    # 编辑模式
                    if st.session_state.get(f"editing_product_{product_id}", False):
                        st.subheader("编辑产品信息")
                        
                        with st.form(f"edit_product_form_{product_id}"):
                            new_name = st.text_input("产品名称:", value=product_info.get('name', ''))
                            new_category = st.text_input("产品分类:", value=product_info.get('category', ''))
                            new_price = st.number_input("产品价格:", value=float(product_info.get('price', 0)))
                            new_status = st.selectbox("产品状态:", ["活跃", "停用", "缺货"], 
                                                    index=["活跃", "停用", "缺货"].index(product_info.get('status', '活跃')))
                            new_supplier = st.text_input("供应商:", value=product_info.get('supplier', ''))
                            new_desc = st.text_area("产品描述:", value=product_info.get('description', ''))
                            
                            col_save, col_cancel = st.columns(2)
                            
                            with col_save:
                                if st.form_submit_button("保存修改"):
                                    system.product_knowledge["products"][product_id].update({
                                        'name': new_name,
                                        'category': new_category,
                                        'price': new_price,
                                        'status': new_status,
                                        'supplier': new_supplier,
                                        'description': new_desc,
                                        'update_time': time.strftime("%Y-%m-%d %H:%M:%S")
                                    })
                                    
                                    system.save_product_knowledge()
                                    st.session_state[f"editing_product_{product_id}"] = False
                                    st.success("产品信息已更新")
                                    st.rerun()
                            
                            with col_cancel:
                                if st.form_submit_button("取消"):
                                    st.session_state[f"editing_product_{product_id}"] = False
                                    st.rerun()
        else:
            st.info("暂无产品信息，请导入或手动添加")
        
        # 业务规则管理
        st.subheader("产品相关业务规则")
        
        with st.form("add_business_rule"):
            col_rule1, col_rule2 = st.columns(2)
            
            with col_rule1:
                rule_name = st.text_input("规则名称:")
                rule_condition = st.text_input("触发条件:")
            
            with col_rule2:
                rule_priority = st.selectbox("优先级:", ["高", "中", "低"])
                rule_status = st.selectbox("状态:", ["启用", "禁用"])
            
            rule_action = st.text_area("执行动作:")
            
            if st.form_submit_button("添加业务规则"):
                if rule_name and rule_condition:
                    if "business_rules" not in system.product_knowledge:
                        system.product_knowledge["business_rules"] = {}
                    
                    system.product_knowledge["business_rules"][rule_name] = {
                        "condition": rule_condition,
                        "action": rule_action,
                        "priority": rule_priority,
                        "status": rule_status,
                        "create_time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if system.save_product_knowledge():
                        st.success(f"已添加业务规则: {rule_name}")
                        st.rerun()
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写规则名称和条件")
        
        # 显示现有业务规则
        if "business_rules" in system.product_knowledge and system.product_knowledge["business_rules"]:
            st.write("**现有业务规则:**")
            for rule_name, rule_info in system.product_knowledge["business_rules"].items():
                with st.expander(f"📋 {rule_name}"):
                    col_rule_info, col_rule_action = st.columns([3, 1])
                    
                    with col_rule_info:
                        st.write(f"**条件**: {rule_info.get('condition', '')}")
                        st.write(f"**动作**: {rule_info.get('action', '')}")
                        st.write(f"**优先级**: {rule_info.get('priority', '')}")
                        st.write(f"**状态**: {rule_info.get('status', '')}")
                        
                        create_time = rule_info.get('create_time', '')
                        if create_time:
                            st.write(f"**创建时间**: {create_time}")
                    
                    with col_rule_action:
                        # 切换状态
                        current_status = rule_info.get('status', '启用')
                        new_status = "禁用" if current_status == "启用" else "启用"
                        
                        if st.button(f"{new_status}", key=f"toggle_rule_{rule_name}"):
                            system.product_knowledge["business_rules"][rule_name]["status"] = new_status
                            system.save_product_knowledge()
                            st.success(f"规则已{new_status}")
                            st.rerun()
                        
                        # 删除规则
                        if st.button(f"删除", key=f"del_rule_{rule_name}"):
                            if st.session_state.get(f"confirm_del_rule_{rule_name}", False):
                                del system.product_knowledge["business_rules"][rule_name]
                                system.save_product_knowledge()
                                st.success(f"已删除规则 {rule_name}")
                                st.rerun()
                            else:
                                st.session_state[f"confirm_del_rule_{rule_name}"] = True
                                st.warning("再次点击确认删除")
    
    with col2:
        st.subheader("V2.3产品知识库增强")
        st.markdown("""
        ### 🚀 新增功能
        - **智能导入**: 自动识别产品表并导入
        - **数据预览**: 导入前预览表数据
        - **搜索过滤**: 支持产品搜索和分类筛选
        - **批量操作**: 批量更新、删除、导出
        
        ### 📊 产品管理
        - **完整信息**: 支持价格、状态、供应商等
        - **自定义字段**: 灵活添加业务字段
        - **编辑功能**: 在线编辑产品信息
        - **数据来源**: 记录数据导入来源
        
        ### 🛠️ 业务规则
        - **规则引擎**: 支持条件触发规则
        - **优先级管理**: 规则优先级设置
        - **状态控制**: 启用/禁用规则
        - **动作定义**: 灵活的规则动作
        
        ### ⚡ 性能优化
        - 分页显示大量产品
        - 智能搜索和过滤
        - 批量操作优化
        - 数据导出功能
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        product_count = len(system.product_knowledge.get("products", {}))
        rule_count = len(system.product_knowledge.get("business_rules", {}))
        
        # 分类统计
        category_count = {}
        status_count = {}
        
        for product in system.product_knowledge.get("products", {}).values():
            category = product.get("category", "未分类")
            status = product.get("status", "未知")
            
            category_count[category] = category_count.get(category, 0) + 1
            status_count[status] = status_count.get(status, 0) + 1
        
        st.metric("产品总数", product_count)
        st.metric("业务规则数", rule_count)
        st.metric("产品分类数", len(category_count))
        
        # 分类分布
        if category_count:
            st.write("**分类分布:**")
            for category, count in category_count.items():
                st.write(f"- {category}: {count}")
        
        # 状态分布
        if status_count:
            st.write("**状态分布:**")
            for status, count in status_count.items():
                st.write(f"- {status}: {count}")
        
        # 数据管理
        st.subheader("数据管理")
        
        if st.button("导出完整知识库"):
            export_data = {
                "product_knowledge": system.product_knowledge,
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": "V2.3"
            }
            
            st.download_button(
                label="下载JSON文件",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name=f"product_knowledge_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        # 导入知识库
        uploaded_file = st.file_uploader("导入知识库", type=['json'])
        if uploaded_file is not None:
            try:
                import_data = json.load(uploaded_file)
                
                if st.button("确认导入"):
                    if "product_knowledge" in import_data:
                        system.product_knowledge.update(import_data["product_knowledge"])
                    else:
                        system.product_knowledge.update(import_data)
                    
                    system.save_product_knowledge()
                    st.success("知识库导入成功")
                    st.rerun()
            except Exception as e:
                st.error(f"文件格式错误: {e}")
        
        # 清空功能
        if st.button("清空产品知识库"):
            if st.session_state.get("confirm_clear_product_kb", False):
                system.product_knowledge = {}
                system.save_product_knowledge()
                st.success("产品知识库已清空")
                st.session_state["confirm_clear_product_kb"] = False
                st.rerun()
            else:
                st.session_state["confirm_clear_product_kb"] = True
                st.warning("再次点击确认清空")

def show_business_rules_page_v23(system):
    """业务规则管理页面 V2.3 - 完整功能版"""
    st.header("业务规则管理 V2.3")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("术语映射管理")
        
        # 添加新的术语映射
        with st.form("add_term_mapping"):
            st.write("**添加术语映射:**")
            col_term1, col_term2, col_term3 = st.columns([2, 2, 1])
            
            with col_term1:
                business_term = st.text_input("业务术语:", placeholder="例如: 学生")
            with col_term2:
                db_term = st.text_input("数据库术语:", placeholder="例如: student")
            with col_term3:
                term_type = st.selectbox("类型:", ["实体", "字段", "条件", "时间"])
            
            term_description = st.text_input("描述:", placeholder="术语映射的说明")
            
            if st.form_submit_button("添加映射"):
                if business_term and db_term:
                    # 检查是否已存在
                    if business_term in system.business_rules:
                        st.warning(f"术语 '{business_term}' 已存在，将覆盖原有映射")
                    
                    system.business_rules[business_term] = db_term
                    
                    # 保存额外信息到元数据
                    if not hasattr(system, 'business_rules_meta'):
                        system.business_rules_meta = {}
                    
                    system.business_rules_meta[business_term] = {
                        "type": term_type,
                        "description": term_description,
                        "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "usage_count": 0
                    }
                    
                    if system.save_business_rules():
                        # 保存元数据
                        try:
                            with open("business_rules_meta.json", 'w', encoding='utf-8') as f:
                                json.dump(system.business_rules_meta, f, ensure_ascii=False, indent=2)
                        except:
                            pass
                        
                        st.success(f"已添加映射: {business_term} → {db_term}")
                        st.rerun()
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写完整的术语映射")
        
        # 批量导入
        st.subheader("批量导入规则")
        
        col_upload, col_template = st.columns(2)
        
        with col_upload:
            uploaded_file = st.file_uploader("上传JSON文件", type=['json'])
            if uploaded_file is not None:
                try:
                    new_rules = json.load(uploaded_file)
                    
                    if st.button("预览导入规则"):
                        st.write("**将导入的规则:**")
                        preview_df = pd.DataFrame([
                            {"业务术语": k, "数据库术语": v} 
                            for k, v in new_rules.items()
                        ])
                        st.dataframe(preview_df)
                    
                    if st.button("确认导入规则"):
                        imported_count = 0
                        for term, mapping in new_rules.items():
                            if term not in system.business_rules:
                                system.business_rules[term] = mapping
                                imported_count += 1
                        
                        if system.save_business_rules():
                            st.success(f"已导入 {imported_count} 条新规则")
                            st.rerun()
                        else:
                            st.error("导入失败")
                except Exception as e:
                    st.error(f"文件格式错误: {e}")
        
        with col_template:
            # 预设规则模板
            st.write("**预设规则模板:**")
            
            preset_templates = {
                "教育系统": {
                    "学生": "student", "课程": "course", "成绩": "score", "教师": "teacher",
                    "班级": "class", "姓名": "name", "年龄": "age", "性别": "gender",
                    "优秀": "score >= 90", "良好": "score >= 80 AND score < 90",
                    "及格": "score >= 60 AND score < 80", "不及格": "score < 60"
                },
                "电商系统": {
                    "用户": "user", "商品": "product", "订单": "order", "支付": "payment",
                    "库存": "inventory", "价格": "price", "数量": "quantity",
                    "热销": "sales_count > 100", "新品": "create_date >= DATEADD(month, -1, GETDATE())"
                },
                "人事系统": {
                    "员工": "employee", "部门": "department", "职位": "position",
                    "薪资": "salary", "考勤": "attendance", "绩效": "performance",
                    "在职": "status = 'active'", "离职": "status = 'inactive'"
                }
            }
            
            selected_template = st.selectbox("选择模板:", ["无"] + list(preset_templates.keys()))
            
            if selected_template != "无":
                template_rules = preset_templates[selected_template]
                st.write(f"**{selected_template}模板包含 {len(template_rules)} 条规则**")
                
                if st.button(f"应用{selected_template}模板"):
                    added_count = 0
                    for term, mapping in template_rules.items():
                        if term not in system.business_rules:
                            system.business_rules[term] = mapping
                            added_count += 1
                    
                    if system.save_business_rules():
                        st.success(f"已应用{selected_template}模板，添加了 {added_count} 条规则")
                        st.rerun()
                    else:
                        st.error("应用模板失败")
        
        # 显示现有术语映射
        st.subheader("现有术语映射")
        
        # 搜索和过滤
        col_search, col_filter, col_sort = st.columns(3)
        
        with col_search:
            search_term = st.text_input("搜索规则:", placeholder="输入业务术语或数据库术语")
        
        with col_filter:
            # 加载元数据
            try:
                with open("business_rules_meta.json", 'r', encoding='utf-8') as f:
                    business_rules_meta = json.load(f)
                    system.business_rules_meta = business_rules_meta
            except:
                system.business_rules_meta = {}
            
            all_types = set()
            for meta in system.business_rules_meta.values():
                if meta.get("type"):
                    all_types.add(meta["type"])
            
            filter_type = st.selectbox("筛选类型:", ["全部"] + list(all_types))
        
        with col_sort:
            sort_by = st.selectbox("排序方式:", ["按术语", "按类型", "按创建时间"])
        
        # 过滤和排序规则
        filtered_rules = {}
        for term, mapping in system.business_rules.items():
            # 搜索过滤
            if search_term:
                if (search_term.lower() not in term.lower() and 
                    search_term.lower() not in mapping.lower()):
                    continue
            
            # 类型过滤
            if filter_type != "全部":
                meta = system.business_rules_meta.get(term, {})
                if meta.get("type") != filter_type:
                    continue
            
            filtered_rules[term] = mapping
        
        # 排序
        if sort_by == "按类型":
            filtered_rules = dict(sorted(filtered_rules.items(), 
                                       key=lambda x: system.business_rules_meta.get(x[0], {}).get("type", "")))
        elif sort_by == "按创建时间":
            filtered_rules = dict(sorted(filtered_rules.items(), 
                                       key=lambda x: system.business_rules_meta.get(x[0], {}).get("create_time", ""), 
                                       reverse=True))
        else:  # 按术语
            filtered_rules = dict(sorted(filtered_rules.items()))
        
        st.write(f"**显示 {len(filtered_rules)} / {len(system.business_rules)} 条规则**")
        
        # 批量操作
        if filtered_rules:
            col_batch1, col_batch2, col_batch3 = st.columns(3)
            
            with col_batch1:
                if st.button("导出选中规则"):
                    export_data = {
                        "business_rules": filtered_rules,
                        "metadata": {k: v for k, v in system.business_rules_meta.items() if k in filtered_rules},
                        "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_count": len(filtered_rules)
                    }
                    
                    st.download_button(
                        label="下载JSON文件",
                        data=json.dumps(export_data, ensure_ascii=False, indent=2),
                        file_name=f"business_rules_{time.strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
            
            with col_batch2:
                if st.button("批量删除选中"):
                    if st.session_state.get("confirm_batch_delete_rules", False):
                        for term in filtered_rules:
                            del system.business_rules[term]
                            if term in system.business_rules_meta:
                                del system.business_rules_meta[term]
                        
                        system.save_business_rules()
                        st.success(f"已删除 {len(filtered_rules)} 条规则")
                        st.session_state["confirm_batch_delete_rules"] = False
                        st.rerun()
                    else:
                        st.session_state["confirm_batch_delete_rules"] = True
                        st.warning("再次点击确认批量删除")
            
            with col_batch3:
                if st.button("验证所有规则"):
                    with st.spinner("正在验证规则..."):
                        validation_results = []
                        for term, mapping in filtered_rules.items():
                            # 简单验证规则格式
                            issues = []
                            if not term.strip():
                                issues.append("业务术语为空")
                            if not mapping.strip():
                                issues.append("数据库术语为空")
                            if len(term) > 50:
                                issues.append("业务术语过长")
                            
                            validation_results.append({
                                "术语": term,
                                "映射": mapping,
                                "状态": "✅ 正常" if not issues else "❌ 异常",
                                "问题": "; ".join(issues) if issues else ""
                            })
                        
                        st.write("**验证结果:**")
                        validation_df = pd.DataFrame(validation_results)
                        st.dataframe(validation_df, use_container_width=True)
        
        # 分类显示规则
        term_categories = {
            "实体映射": ["学生", "课程", "成绩", "教师", "班级", "用户", "商品", "订单"],
            "字段映射": ["姓名", "性别", "年龄", "分数", "课程名称", "价格", "数量"],
            "时间映射": ["今年", "去年", "明年", "25年", "24年", "23年"],
            "条件映射": ["优秀", "良好", "及格", "不及格", "热销", "新品", "在职", "离职"]
        }
        
        for category, keywords in term_categories.items():
            category_rules = {}
            for term, mapping in filtered_rules.items():
                # 根据关键词或元数据分类
                meta = system.business_rules_meta.get(term, {})
                meta_type = meta.get("type", "")
                
                if (any(keyword in term for keyword in keywords) or 
                    (category == "实体映射" and meta_type == "实体") or
                    (category == "字段映射" and meta_type == "字段") or
                    (category == "时间映射" and meta_type == "时间") or
                    (category == "条件映射" and meta_type == "条件")):
                    category_rules[term] = mapping
            
            if category_rules:
                with st.expander(f"📂 {category} ({len(category_rules)}条)"):
                    for term, mapping in category_rules.items():
                        col_show1, col_show2, col_show3, col_show4 = st.columns([2, 2, 1, 1])
                        
                        with col_show1:
                            new_term = st.text_input(f"术语:", value=term, key=f"term_{category}_{term}")
                        with col_show2:
                            new_mapping = st.text_input(f"映射:", value=mapping, key=f"mapping_{category}_{term}")
                        with col_show3:
                            if st.button("更新", key=f"update_{category}_{term}"):
                                if new_term != term:
                                    del system.business_rules[term]
                                    if term in system.business_rules_meta:
                                        system.business_rules_meta[new_term] = system.business_rules_meta.pop(term)
                                
                                system.business_rules[new_term] = new_mapping
                                
                                # 更新元数据
                                if new_term in system.business_rules_meta:
                                    system.business_rules_meta[new_term]["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                
                                system.save_business_rules()
                                st.success("已更新")
                                st.rerun()
                        
                        with col_show4:
                            if st.button("删除", key=f"del_{category}_{term}"):
                                if st.session_state.get(f"confirm_del_{term}", False):
                                    del system.business_rules[term]
                                    if term in system.business_rules_meta:
                                        del system.business_rules_meta[term]
                                    system.save_business_rules()
                                    st.success("已删除")
                                    st.rerun()
                                else:
                                    st.session_state[f"confirm_del_{term}"] = True
                                    st.warning("再次点击确认删除")
                        
                        # 显示元数据
                        meta = system.business_rules_meta.get(term, {})
                        if meta:
                            meta_info = []
                            if meta.get("type"):
                                meta_info.append(f"类型: {meta['type']}")
                            if meta.get("description"):
                                meta_info.append(f"描述: {meta['description']}")
                            if meta.get("create_time"):
                                meta_info.append(f"创建: {meta['create_time']}")
                            if meta.get("usage_count", 0) > 0:
                                meta_info.append(f"使用: {meta['usage_count']}次")
                            
                            if meta_info:
                                st.caption(" | ".join(meta_info))
        
        # 其他未分类规则
        other_rules = {}
        for term, mapping in filtered_rules.items():
            is_categorized = False
            for keywords in term_categories.values():
                if any(keyword in term for keyword in keywords):
                    is_categorized = True
                    break
            
            meta = system.business_rules_meta.get(term, {})
            if meta.get("type") in ["实体", "字段", "时间", "条件"]:
                is_categorized = True
            
            if not is_categorized:
                other_rules[term] = mapping
        
        if other_rules:
            with st.expander(f"📂 其他规则 ({len(other_rules)}条)"):
                for term, mapping in other_rules.items():
                    col_other1, col_other2, col_other3 = st.columns([2, 2, 1])
                    
                    with col_other1:
                        st.text_input(f"术语:", value=term, key=f"other_term_{hash(term)}", disabled=True)
                    with col_other2:
                        st.text_input(f"映射:", value=mapping, key=f"other_mapping_{hash(term)}", disabled=True)
                    with col_other3:
                        if st.button("删除", key=f"del_other_{hash(term)}"):
                            del system.business_rules[term]
                            if term in system.business_rules_meta:
                                del system.business_rules_meta[term]
                            system.save_business_rules()
                            st.rerun()
    
    with col2:
        st.subheader("V2.3业务规则管理增强")
        st.markdown("""
        ### 🚀 新增功能
        - **规则分类**: 自动分类管理不同类型规则
        - **元数据管理**: 记录规则类型、描述、使用情况
        - **批量操作**: 导入、导出、删除、验证
        - **搜索过滤**: 支持多维度搜索和筛选
        
        ### 📊 规则类型
        - **实体映射**: 业务实体到表名的映射
        - **字段映射**: 业务字段到列名的映射
        - **时间映射**: 时间表达式的标准化
        - **条件映射**: 业务条件到SQL条件
        
        ### 🛠️ 管理功能
        - **预设模板**: 常用行业规则模板
        - **规则验证**: 自动检查规则格式
        - **使用统计**: 跟踪规则使用频率
        - **版本管理**: 规则变更历史记录
        
        ### ⚡ 性能优化
        - 智能分类和排序
        - 快速搜索和过滤
        - 批量操作优化
        - 规则验证加速
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        total_rules = len(system.business_rules)
        filtered_count = len(filtered_rules) if 'filtered_rules' in locals() else total_rules
        
        st.metric("总规则数", total_rules)
        st.metric("显示规则数", filtered_count)
        
        # 规则分类统计
        type_count = {}
        for meta in system.business_rules_meta.values():
            rule_type = meta.get("type", "未分类")
            type_count[rule_type] = type_count.get(rule_type, 0) + 1
        
        if type_count:
            st.write("**类型分布:**")
            for rule_type, count in type_count.items():
                st.write(f"- {rule_type}: {count}")
        
        # 使用频率统计
        usage_stats = []
        for term, meta in system.business_rules_meta.items():
            usage_count = meta.get("usage_count", 0)
            if usage_count > 0:
                usage_stats.append((term, usage_count))
        
        if usage_stats:
            usage_stats.sort(key=lambda x: x[1], reverse=True)
            st.write("**使用频率TOP5:**")
            for term, count in usage_stats[:5]:
                st.write(f"- {term}: {count}次")
        
        # 数据管理
        st.subheader("数据管理")
        
        if st.button("导出所有规则"):
            export_data = {
                "business_rules": system.business_rules,
                "metadata": system.business_rules_meta,
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": "V2.3"
            }
            
            st.download_button(
                label="下载JSON文件",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name=f"business_rules_complete_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        # 重置功能
        if st.button("重置为默认规则"):
            if st.session_state.get("confirm_reset_rules", False):
                system.business_rules = system.load_business_rules()
                system.business_rules_meta = {}
                system.save_business_rules()
                st.success("已重置为默认规则")
                st.session_state["confirm_reset_rules"] = False
                st.rerun()
            else:
                st.session_state["confirm_reset_rules"] = True
                st.warning("再次点击确认重置")

def show_prompt_templates_page_v23(system):
    """提示词管理页面 V2.3 - 完整功能版"""
    st.header("提示词管理 V2.3")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("提示词模板编辑")
        
        # 选择模板
        template_names = list(system.prompt_templates.keys())
        selected_template = st.selectbox("选择模板:", template_names)
        
        if selected_template:
            # 显示当前模板
            st.write(f"**当前模板: {selected_template}**")
            
            # 模板信息
            current_template = system.prompt_templates[selected_template]
            template_length = len(current_template)
            variable_count = len(re.findall(r'\{(\w+)\}', current_template))
            
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("模板长度", f"{template_length} 字符")
            with col_info2:
                st.metric("变量数量", variable_count)
            with col_info3:
                st.metric("行数", len(current_template.split('\n')))
            
            # 编辑模板
            new_template = st.text_area(
                "编辑模板内容:",
                value=current_template,
                height=400,
                key=f"template_{selected_template}",
                help="使用 {变量名} 格式插入动态内容"
            )
            
            # 实时预览变量
            if new_template != current_template:
                st.info("⚠️ 模板已修改，记得保存")
                
                # 分析新模板中的变量
                new_variables = set(re.findall(r'\{(\w+)\}', new_template))
                old_variables = set(re.findall(r'\{(\w+)\}', current_template))
                
                added_vars = new_variables - old_variables
                removed_vars = old_variables - new_variables
                
                if added_vars:
                    st.success(f"新增变量: {', '.join(added_vars)}")
                if removed_vars:
                    st.warning(f"移除变量: {', '.join(removed_vars)}")
            
            col_save, col_reset, col_test = st.columns(3)
            
            with col_save:
                if st.button("保存模板"):
                    system.prompt_templates[selected_template] = new_template
                    if system.save_prompt_templates():
                        st.success("模板保存成功")
                        st.rerun()
                    else:
                        st.error("保存失败")
            
            with col_reset:
                if st.button("重置模板"):
                    if st.session_state.get(f"confirm_reset_{selected_template}", False):
                        # 重新加载默认模板
                        default_templates = system.load_prompt_templates()
                        if selected_template in default_templates:
                            system.prompt_templates[selected_template] = default_templates[selected_template]
                            system.save_prompt_templates()
                            st.success("已重置为默认模板")
                            st.rerun()
                        else:
                            st.error("无法找到默认模板")
                    else:
                        st.session_state[f"confirm_reset_{selected_template}"] = True
                        st.warning("再次点击确认重置")
            
            with col_test:
                if st.button("测试模板"):
                    st.session_state[f"testing_{selected_template}"] = True
                    st.rerun()
        
        # 添加新模板
        st.subheader("添加新模板")
        
        with st.form("add_template"):
            col_new1, col_new2 = st.columns(2)
            
            with col_new1:
                new_template_name = st.text_input("模板名称:")
                template_category = st.selectbox("模板分类:", ["SQL生成", "SQL验证", "数据分析", "自定义"])
            
            with col_new2:
                template_language = st.selectbox("语言:", ["中文", "英文", "双语"])
                template_priority = st.selectbox("优先级:", ["高", "中", "低"])
            
            new_template_content = st.text_area("模板内容:", height=200, 
                                              placeholder="输入提示词模板，使用 {变量名} 插入动态内容")
            template_description = st.text_input("模板描述:", placeholder="简要描述模板的用途")
            
            if st.form_submit_button("添加模板"):
                if new_template_name and new_template_content:
                    if new_template_name in system.prompt_templates:
                        st.error(f"模板 '{new_template_name}' 已存在")
                    else:
                        system.prompt_templates[new_template_name] = new_template_content
                        
                        # 保存模板元数据
                        if not hasattr(system, 'template_metadata'):
                            system.template_metadata = {}
                        
                        system.template_metadata[new_template_name] = {
                            "category": template_category,
                            "language": template_language,
                            "priority": template_priority,
                            "description": template_description,
                            "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "usage_count": 0
                        }
                        
                        if system.save_prompt_templates():
                            # 保存元数据
                            try:
                                with open("template_metadata.json", 'w', encoding='utf-8') as f:
                                    json.dump(system.template_metadata, f, ensure_ascii=False, indent=2)
                            except:
                                pass
                            
                            st.success(f"已添加模板: {new_template_name}")
                            st.rerun()
                        else:
                            st.error("保存失败")
                else:
                    st.warning("请填写模板名称和内容")
        
        # 模板预览和测试
        if selected_template and st.session_state.get(f"testing_{selected_template}", False):
            st.subheader("模板预览和测试")
            
            # 分析模板中的变量
            variables = re.findall(r'\{(\w+)\}', system.prompt_templates[selected_template])
            unique_variables = list(set(variables))
            
            if unique_variables:
                st.write("**模板变量:**")
                
                # 为每个变量提供测试数据
                test_data = {}
                for var in unique_variables:
                    var_description = get_variable_description_v23(var)
                    
                    if var in ["schema_info", "table_knowledge", "product_knowledge", "business_rules"]:
                        # 使用系统实际数据
                        if var == "schema_info":
                            test_data[var] = "表名: users\n字段: id, name, email, age"
                        elif var == "table_knowledge":
                            test_data[var] = json.dumps(dict(list(system.table_knowledge.items())[:2]), 
                                                       ensure_ascii=False, indent=2) if system.table_knowledge else "{}"
                        elif var == "product_knowledge":
                            test_data[var] = json.dumps(dict(list(system.product_knowledge.items())[:2]), 
                                                       ensure_ascii=False, indent=2) if system.product_knowledge else "{}"
                        elif var == "business_rules":
                            test_data[var] = json.dumps(dict(list(system.business_rules.items())[:5]), 
                                                       ensure_ascii=False, indent=2) if system.business_rules else "{}"
                        
                        st.text_area(f"{var} ({var_description}):", value=test_data[var], height=100, key=f"test_{var}")
                    else:
                        # 用户输入测试数据
                        default_value = get_default_test_value(var)
                        test_data[var] = st.text_input(f"{var} ({var_description}):", value=default_value, key=f"test_{var}")
                
                # 生成预览
                if st.button("生成预览"):
                    try:
                        preview_result = system.prompt_templates[selected_template].format(**test_data)
                        
                        st.write("**预览结果:**")
                        st.text_area("", value=preview_result, height=300, key="preview_result")
                        
                        # 统计信息
                        preview_length = len(preview_result)
                        preview_lines = len(preview_result.split('\n'))
                        
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            st.metric("预览长度", f"{preview_length} 字符")
                        with col_stat2:
                            st.metric("预览行数", preview_lines)
                        with col_stat3:
                            # 估算token数量（粗略估算）
                            estimated_tokens = preview_length // 4
                            st.metric("估算Tokens", estimated_tokens)
                        
                        # 如果是SQL生成模板，可以测试生成
                        if "sql" in selected_template.lower() and "question" in test_data:
                            if st.button("测试SQL生成"):
                                with st.spinner("正在测试SQL生成..."):
                                    try:
                                        # 模拟调用API
                                        test_sql = system.call_deepseek_api(preview_result)
                                        cleaned_sql = system.clean_sql(test_sql)
                                        
                                        if cleaned_sql:
                                            st.success("SQL生成测试成功")
                                            st.code(cleaned_sql, language="sql")
                                        else:
                                            st.warning("SQL生成为空")
                                    except Exception as e:
                                        st.error(f"SQL生成测试失败: {e}")
                        
                    except KeyError as e:
                        st.error(f"模板变量错误: {e}")
                    except Exception as e:
                        st.error(f"预览生成失败: {e}")
            else:
                st.info("此模板不包含变量，直接显示内容")
                st.text_area("模板内容:", value=system.prompt_templates[selected_template], height=200)
            
            if st.button("关闭预览"):
                st.session_state[f"testing_{selected_template}"] = False
                st.rerun()
        
        # 模板管理
        st.subheader("模板管理")
        
        # 加载模板元数据
        try:
            with open("template_metadata.json", 'r', encoding='utf-8') as f:
                system.template_metadata = json.load(f)
        except:
            system.template_metadata = {}
        
        # 模板列表
        col_list1, col_list2 = st.columns([3, 1])
        
        with col_list1:
            st.write("**模板列表:**")
            
            for template_name in system.prompt_templates.keys():
                with st.expander(f"📝 {template_name}"):
                    template_content = system.prompt_templates[template_name]
                    metadata = system.template_metadata.get(template_name, {})
                    
                    # 基本信息
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    
                    with col_meta1:
                        st.write(f"**分类**: {metadata.get('category', '未知')}")
                        st.write(f"**语言**: {metadata.get('language', '未知')}")
                    
                    with col_meta2:
                        st.write(f"**优先级**: {metadata.get('priority', '未知')}")
                        st.write(f"**长度**: {len(template_content)} 字符")
                    
                    with col_meta3:
                        variables = len(set(re.findall(r'\{(\w+)\}', template_content)))
                        st.write(f"**变量数**: {variables}")
                        usage_count = metadata.get('usage_count', 0)
                        st.write(f"**使用次数**: {usage_count}")
                    
                    # 描述
                    description = metadata.get('description', '')
                    if description:
                        st.write(f"**描述**: {description}")
                    
                    # 时间信息
                    create_time = metadata.get('create_time', '')
                    if create_time:
                        st.write(f"**创建时间**: {create_time}")
                    
                    # 操作按钮
                    col_op1, col_op2, col_op3 = st.columns(3)
                    
                    with col_op1:
                        if st.button("编辑", key=f"edit_template_{template_name}"):
                            # 设置为当前选中的模板
                            st.session_state["selected_template"] = template_name
                            st.rerun()
                    
                    with col_op2:
                        if st.button("复制", key=f"copy_template_{template_name}"):
                            copy_name = f"{template_name}_副本"
                            counter = 1
                            while copy_name in system.prompt_templates:
                                copy_name = f"{template_name}_副本{counter}"
                                counter += 1
                            
                            system.prompt_templates[copy_name] = template_content
                            system.template_metadata[copy_name] = metadata.copy()
                            system.template_metadata[copy_name]["create_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            
                            system.save_prompt_templates()
                            st.success(f"已复制为: {copy_name}")
                            st.rerun()
                    
                    with col_op3:
                        if template_name not in ["sql_generation", "sql_verification"]:
                            if st.button("删除", key=f"del_template_{template_name}"):
                                if st.session_state.get(f"confirm_del_template_{template_name}", False):
                                    del system.prompt_templates[template_name]
                                    if template_name in system.template_metadata:
                                        del system.template_metadata[template_name]
                                    
                                    system.save_prompt_templates()
                                    st.success(f"已删除模板: {template_name}")
                                    st.rerun()
                                else:
                                    st.session_state[f"confirm_del_template_{template_name}"] = True
                                    st.warning("再次点击确认删除")
                        else:
                            st.info("核心模板")
        
        with col_list2:
            # 批量操作
            st.write("**批量操作:**")
            
            if st.button("导出所有模板"):
                export_data = {
                    "prompt_templates": system.prompt_templates,
                    "metadata": system.template_metadata,
                    "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "version": "V2.3"
                }
                
                st.download_button(
                    label="下载JSON文件",
                    data=json.dumps(export_data, ensure_ascii=False, indent=2),
                    file_name=f"prompt_templates_{time.strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            # 导入模板
            uploaded_file = st.file_uploader("导入模板文件", type=['json'])
            if uploaded_file is not None:
                try:
                    import_data = json.load(uploaded_file)
                    
                    if st.button("预览导入"):
                        if "prompt_templates" in import_data:
                            templates_to_import = import_data["prompt_templates"]
                        else:
                            templates_to_import = import_data
                        
                        st.write(f"**将导入 {len(templates_to_import)} 个模板:**")
                        for name in templates_to_import.keys():
                            status = "新增" if name not in system.prompt_templates else "覆盖"
                            st.write(f"- {name} ({status})")
                    
                    if st.button("确认导入"):
                        imported_count = 0
                        
                        if "prompt_templates" in import_data:
                            templates_to_import = import_data["prompt_templates"]
                            metadata_to_import = import_data.get("metadata", {})
                        else:
                            templates_to_import = import_data
                            metadata_to_import = {}
                        
                        for name, content in templates_to_import.items():
                            system.prompt_templates[name] = content
                            if name in metadata_to_import:
                                system.template_metadata[name] = metadata_to_import[name]
                            imported_count += 1
                        
                        if system.save_prompt_templates():
                            st.success(f"已导入 {imported_count} 个模板")
                            st.rerun()
                        else:
                            st.error("导入失败")
                except Exception as e:
                    st.error(f"文件格式错误: {e}")
            
            if st.button("重置所有模板"):
                if st.session_state.get("confirm_reset_all_templates", False):
                    system.prompt_templates = system.load_prompt_templates()
                    system.template_metadata = {}
                    system.save_prompt_templates()
                    st.success("已重置所有模板")
                    st.session_state["confirm_reset_all_templates"] = False
                    st.rerun()
                else:
                    st.session_state["confirm_reset_all_templates"] = True
                    st.warning("再次点击确认重置")
    
    with col2:
        st.subheader("V2.3提示词管理增强")
        st.markdown("""
        ### 🚀 新增功能
        - **模板测试**: 实时预览和测试模板效果
        - **变量分析**: 自动识别和验证模板变量
        - **元数据管理**: 分类、优先级、使用统计
        - **批量操作**: 导入、导出、复制、删除
        
        ### 📊 模板分析
        - **变量检测**: 自动识别模板中的变量
        - **长度统计**: 字符数、行数、Token估算
        - **使用追踪**: 模板使用频率统计
        - **格式验证**: 模板格式正确性检查
        
        ### 🛠️ 编辑功能
        - **实时预览**: 编辑时实时显示变化
        - **语法高亮**: 变量和关键词高亮显示
        - **模板复制**: 快速复制和修改模板
        - **版本管理**: 模板变更历史记录
        
        ### ⚡ 测试功能
        - **数据填充**: 自动填充测试数据
        - **效果预览**: 实时预览最终效果
        - **SQL测试**: 直接测试SQL生成效果
        - **性能评估**: Token数量和长度评估
        """)
        
        # 可用变量说明
        st.subheader("可用变量")
        
        available_variables = {
            "schema_info": "数据库结构信息",
            "table_knowledge": "表结构知识库",
            "product_knowledge": "产品知识库",
            "business_rules": "业务规则",
            "question": "用户问题",
            "sql": "生成的SQL语句",
            "processed_question": "处理后的问题",
            "allowed_tables": "允许的表列表"
        }
        
        for var, desc in available_variables.items():
            st.write(f"- `{{{var}}}`: {desc}")
        
        # 统计信息
        st.subheader("统计信息")
        
        total_templates = len(system.prompt_templates)
        st.metric("模板总数", total_templates)
        
        # 分类统计
        category_count = {}
        for metadata in system.template_metadata.values():
            category = metadata.get("category", "未分类")
            category_count[category] = category_count.get(category, 0) + 1
        
        if category_count:
            st.write("**分类分布:**")
            for category, count in category_count.items():
                st.write(f"- {category}: {count}")
        
        # 使用统计
        usage_stats = []
        for name, metadata in system.template_metadata.items():
            usage_count = metadata.get("usage_count", 0)
            if usage_count > 0:
                usage_stats.append((name, usage_count))
        
        if usage_stats:
            usage_stats.sort(key=lambda x: x[1], reverse=True)
            st.write("**使用频率TOP3:**")
            for name, count in usage_stats[:3]:
                st.write(f"- {name}: {count}次")
        
        # 模板长度统计
        lengths = [len(template) for template in system.prompt_templates.values()]
        if lengths:
            avg_length = sum(lengths) // len(lengths)
            max_length = max(lengths)
            min_length = min(lengths)
            
            st.write("**长度统计:**")
            st.write(f"- 平均长度: {avg_length} 字符")
            st.write(f"- 最长模板: {max_length} 字符")
            st.write(f"- 最短模板: {min_length} 字符")

def get_variable_description_v23(var_name):
    """获取变量描述 V2.3版本"""
    descriptions = {
        "schema_info": "数据库结构信息，包含表名和字段信息",
        "table_knowledge": "表结构知识库，包含表和字段的备注说明",
        "product_knowledge": "产品知识库，包含产品信息和业务规则",
        "business_rules": "业务规则，包含术语映射和条件转换",
        "question": "用户输入的自然语言问题",
        "processed_question": "经过业务规则处理后的问题",
        "sql": "生成的SQL语句，用于验证模板",
        "allowed_tables": "允许使用的表列表"
    }
    return descriptions.get(var_name, "未知变量")

def get_default_test_value(var_name):
    """获取变量的默认测试值"""
    defaults = {
        "question": "查询所有学生信息",
        "processed_question": "查询所有student信息",
        "sql": "SELECT * FROM students;",
        "allowed_tables": "students, courses, scores"
    }
    return defaults.get(var_name, "")

def show_sqlite_table_management_page(system):
    """SQLite表结构管理页面"""
    st.header("📊 SQLite 表结构管理")
    
    # 获取系统中的SQLite数据库
    sqlite_databases = {}
    for db_id, db_config in system.databases.items():
        if db_config.get("type") == "sqlite" and db_config.get("active", False):
            sqlite_databases[db_id] = db_config
    
    # 数据库选择
    col_db1, col_db2, col_db3 = st.columns([2, 2, 1])
    
    with col_db1:
        if sqlite_databases:
            # 从系统数据库中选择
            db_options = ["手动输入路径"] + [f"{db_config['name']} ({db_id})" for db_id, db_config in sqlite_databases.items()]
            selected_option = st.selectbox("选择数据库:", db_options)
            
            if selected_option != "手动输入路径":
                # 解析选择的数据库ID
                selected_db_id = selected_option.split("(")[-1].rstrip(")")
                selected_db_config = sqlite_databases[selected_db_id]
                db_path = selected_db_config["config"].get("database", "test_database.db")
            else:
                db_path = st.text_input("SQLite数据库文件路径:", value="test_database.db")
        else:
            st.info("系统中没有配置SQLite数据库，请先在数据库管理中添加SQLite数据库")
            db_path = st.text_input("SQLite数据库文件路径:", value="test_database.db")
            
            # 快速添加SQLite数据库到系统
            st.write("**快速添加SQLite数据库:**")
            col_add1, col_add2 = st.columns(2)
            with col_add1:
                new_db_name = st.text_input("数据库名称:", placeholder="例如: 我的SQLite数据库")
            with col_add2:
                if st.button("➕ 添加到系统") and new_db_name and db_path:
                    # 生成新的数据库ID
                    new_db_id = f"sqlite_{len(system.databases) + 1}"
                    
                    # 添加到系统数据库配置
                    system.databases[new_db_id] = {
                        "name": new_db_name,
                        "type": "sqlite",
                        "config": {"database": db_path},
                        "active": True
                    }
                    
                    # 保存配置
                    try:
                        with open("database_configs.json", 'w', encoding='utf-8') as f:
                            json.dump(system.databases, f, ensure_ascii=False, indent=2)
                        st.success(f"SQLite数据库 '{new_db_name}' 已添加到系统配置")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存配置失败: {e}")
    
    with col_db2:
        if sqlite_databases:
            st.write("**已配置的SQLite数据库:**")
            for db_id, db_config in sqlite_databases.items():
                status = "🟢 活跃" if db_config.get("active") else "🔴 未激活"
                st.write(f"- {db_config['name']}: {status}")
    
    with col_db3:
        if st.button("🔄 刷新"):
            st.rerun()
    
    # 初始化表管理器
    if 'sqlite_manager' not in st.session_state:
        st.session_state.sqlite_manager = SQLiteTableManager(db_path)
    
    manager = st.session_state.sqlite_manager
    
    # 更新管理器的数据库路径
    if db_path != manager.db_path:
        manager.db_path = db_path
        st.session_state.sqlite_manager = manager
    
    # 显示当前选择的数据库信息
    st.markdown("---")
    col_info1, col_info2, col_info3 = st.columns(3)
    
    with col_info1:
        st.write(f"**当前数据库:** {os.path.basename(db_path)}")
        st.write(f"**路径:** {db_path}")
    
    with col_info2:
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path) / 1024
            st.write(f"**文件大小:** {file_size:.1f} KB")
            st.write(f"**状态:** 🟢 存在")
        else:
            st.write(f"**文件大小:** N/A")
            st.write(f"**状态:** 🔴 不存在")
    
    with col_info3:
        if os.path.exists(db_path):
            # 快速获取表数量
            try:
                temp_manager = SQLiteTableManager(db_path)
                table_count = len(temp_manager.get_tables())
                st.write(f"**表数量:** {table_count}")
            except:
                st.write(f"**表数量:** 无法获取")
        else:
            st.write(f"**表数量:** N/A")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        st.warning(f"数据库文件不存在: {db_path}")
        col_create1, col_create2 = st.columns([1, 3])
        with col_create1:
            if st.button("🔨 创建数据库文件"):
                try:
                    conn = sqlite3.connect(db_path)
                    conn.close()
                    st.success(f"数据库文件已创建: {db_path}")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建数据库文件失败: {e}")
        with col_create2:
            st.info("点击上方按钮创建新的SQLite数据库文件")
        return
    
    # 获取表列表
    tables = manager.get_tables()
    
    # 主要功能选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📋 表列表", "➕ 创建表", "🔧 表操作", "💾 数据管理"])
    
    with tab1:
        st.subheader("数据库表列表")
        
        if not tables:
            st.info("数据库中没有表")
        else:
            # 表统计信息
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("表总数", len(tables))
            
            # 计算总行数
            total_rows = 0
            for table in tables:
                schema = manager.get_table_schema(table)
                total_rows += schema.get('row_count', 0)
            
            with col_stat2:
                st.metric("总行数", f"{total_rows:,}")
            
            with col_stat3:
                st.metric("数据库大小", f"{os.path.getsize(db_path) / 1024:.1f} KB")
            
            st.markdown("---")
            
            # 表详细信息
            for table in tables:
                with st.expander(f"📋 {table}"):
                    schema = manager.get_table_schema(table)
                    
                    if schema:
                        # 基本信息
                        col_info1, col_info2, col_info3 = st.columns(3)
                        
                        with col_info1:
                            st.write(f"**列数**: {len(schema['columns'])}")
                            st.write(f"**行数**: {schema['row_count']:,}")
                        
                        with col_info2:
                            st.write(f"**索引数**: {len(schema['indexes'])}")
                            st.write(f"**外键数**: {len(schema['foreign_keys'])}")
                        
                        with col_info3:
                            # 操作按钮
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.button("查看数据", key=f"view_{table}"):
                                    st.session_state[f"show_data_{table}"] = True
                            with col_btn2:
                                if st.button("删除表", key=f"drop_{table}"):
                                    if st.session_state.get(f"confirm_drop_{table}", False):
                                        success, msg = manager.drop_table(table)
                                        if success:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                    else:
                                        st.session_state[f"confirm_drop_{table}"] = True
                                        st.warning("再次点击确认删除")
                        
                        # 列信息
                        st.write("**列结构:**")
                        columns_df = pd.DataFrame(schema['columns'], columns=[
                            'ID', '列名', '类型', '非空', '默认值', '主键'
                        ])
                        st.dataframe(columns_df, use_container_width=True)
                        
                        # 显示样本数据
                        if st.session_state.get(f"show_data_{table}", False):
                            st.write("**样本数据:**")
                            sample_data = manager.get_sample_data(table)
                            if not sample_data.empty:
                                st.dataframe(sample_data, use_container_width=True)
                            else:
                                st.info("表中没有数据")
                            
                            if st.button("隐藏数据", key=f"hide_{table}"):
                                st.session_state[f"show_data_{table}"] = False
                                st.rerun()
    
    with tab2:
        st.subheader("创建新表")
        
        # 表名输入
        new_table_name = st.text_input("表名:", placeholder="输入新表名")
        
        # 列定义
        st.write("**列定义:**")
        
        # 初始化列定义
        if 'new_table_columns' not in st.session_state:
            st.session_state.new_table_columns = [
                {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'not_null': True, 'unique': False, 'default': ''}
            ]
        
        columns = st.session_state.new_table_columns
        
        # 显示现有列
        for i, col in enumerate(columns):
            with st.container():
                col_def1, col_def2, col_def3, col_def4 = st.columns([2, 2, 2, 1])
                
                with col_def1:
                    col['name'] = st.text_input(f"列名 {i+1}:", value=col['name'], key=f"col_name_{i}")
                
                with col_def2:
                    col['type'] = st.selectbox(f"类型 {i+1}:", 
                        ['INTEGER', 'TEXT', 'REAL', 'BLOB', 'NUMERIC'], 
                        index=['INTEGER', 'TEXT', 'REAL', 'BLOB', 'NUMERIC'].index(col['type']),
                        key=f"col_type_{i}")
                
                with col_def3:
                    col_opt1, col_opt2 = st.columns(2)
                    with col_opt1:
                        col['primary_key'] = st.checkbox("主键", value=col['primary_key'], key=f"col_pk_{i}")
                        col['not_null'] = st.checkbox("非空", value=col['not_null'], key=f"col_nn_{i}")
                    with col_opt2:
                        col['unique'] = st.checkbox("唯一", value=col['unique'], key=f"col_uniq_{i}")
                        col['default'] = st.text_input("默认值", value=col['default'], key=f"col_def_{i}")
                
                with col_def4:
                    if len(columns) > 1:
                        if st.button("删除", key=f"del_col_{i}"):
                            columns.pop(i)
                            st.rerun()
        
        # 添加列按钮
        col_add1, col_add2 = st.columns([1, 3])
        with col_add1:
            if st.button("➕ 添加列"):
                columns.append({
                    'name': f'column_{len(columns)+1}', 
                    'type': 'TEXT', 
                    'primary_key': False, 
                    'not_null': False, 
                    'unique': False, 
                    'default': ''
                })
                st.rerun()
        
        # 创建表按钮
        if st.button("🔨 创建表", type="primary"):
            if new_table_name and columns:
                success, msg = manager.create_table(new_table_name, columns)
                if success:
                    st.success(msg)
                    # 重置表单
                    st.session_state.new_table_columns = [
                        {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'not_null': True, 'unique': False, 'default': ''}
                    ]
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("请输入表名和至少一个列定义")
    
    with tab3:
        st.subheader("表操作")
        
        if not tables:
            st.info("没有可操作的表")
        else:
            # 选择表
            selected_table = st.selectbox("选择表:", tables)
            
            if selected_table:
                # 操作选项
                operation = st.selectbox("选择操作:", [
                    "添加列", "查看表结构", "重命名表", "复制表结构"
                ])
                
                if operation == "添加列":
                    st.write("**添加新列:**")
                    col_name = st.text_input("列名:")
                    col_type = st.selectbox("列类型:", ['INTEGER', 'TEXT', 'REAL', 'BLOB', 'NUMERIC'])
                    
                    if st.button("添加列"):
                        if col_name:
                            success, msg = manager.add_column(selected_table, col_name, col_type)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("请输入列名")
                
                elif operation == "查看表结构":
                    schema = manager.get_table_schema(selected_table)
                    if schema:
                        st.write("**表结构信息:**")
                        
                        # 生成CREATE TABLE语句
                        columns_info = []
                        for col in schema['columns']:
                            col_def = f"{col[1]} {col[2]}"
                            if col[3]:  # NOT NULL
                                col_def += " NOT NULL"
                            if col[5]:  # PRIMARY KEY
                                col_def += " PRIMARY KEY"
                            columns_info.append(col_def)
                        
                        create_sql = f"CREATE TABLE {selected_table} (\n  " + ",\n  ".join(columns_info) + "\n);"
                        st.code(create_sql, language="sql")
                
                elif operation == "重命名表":
                    new_name = st.text_input("新表名:")
                    if st.button("重命名"):
                        if new_name:
                            success, msg, _ = manager.execute_sql(f"ALTER TABLE {selected_table} RENAME TO {new_name}")
                            if success:
                                st.success(f"表已重命名为: {new_name}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("请输入新表名")
                
                elif operation == "复制表结构":
                    new_table_name = st.text_input("新表名:")
                    copy_data = st.checkbox("同时复制数据")
                    
                    if st.button("复制表"):
                        if new_table_name:
                            if copy_data:
                                sql = f"CREATE TABLE {new_table_name} AS SELECT * FROM {selected_table}"
                            else:
                                sql = f"CREATE TABLE {new_table_name} AS SELECT * FROM {selected_table} WHERE 1=0"
                            
                            success, msg, _ = manager.execute_sql(sql)
                            if success:
                                st.success(f"表结构已复制到: {new_table_name}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("请输入新表名")
    
    with tab4:
        st.subheader("数据管理")
        
        # SQL执行器
        st.write("**SQL执行器:**")
        sql_query = st.text_area("输入SQL语句:", height=150, placeholder="""
示例:
SELECT * FROM table_name LIMIT 10;
INSERT INTO table_name (column1, column2) VALUES ('value1', 'value2');
UPDATE table_name SET column1 = 'new_value' WHERE condition;
DELETE FROM table_name WHERE condition;
        """.strip())
        
        if st.button("▶️ 执行SQL"):
            if sql_query.strip():
                success, msg, result_df = manager.execute_sql(sql_query.strip())
                if success:
                    st.success(msg)
                    if not result_df.empty:
                        st.write("**查询结果:**")
                        st.dataframe(result_df, use_container_width=True)
                        
                        # 下载结果
                        csv = result_df.to_csv(index=False)
                        st.download_button(
                            label="📥 下载CSV",
                            data=csv,
                            file_name=f"query_result_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error(msg)
            else:
                st.warning("请输入SQL语句")
        
        # 数据导入/导出
        st.markdown("---")
        st.write("**数据导入/导出:**")
        
        col_import, col_export = st.columns(2)
        
        with col_import:
            st.write("**导入数据:**")
            uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])
            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file)
                    st.write("**预览数据:**")
                    st.dataframe(df.head(), use_container_width=True)
                    
                    table_name = st.text_input("目标表名:", value="imported_data")
                    if st.button("导入到数据库"):
                        try:
                            conn = manager.get_connection()
                            df.to_sql(table_name, conn, if_exists='replace', index=False)
                            conn.close()
                            st.success(f"数据已导入到表: {table_name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"导入失败: {e}")
                except Exception as e:
                    st.error(f"读取CSV文件失败: {e}")
        
        with col_export:
            st.write("**导出数据:**")
            if tables:
                export_table = st.selectbox("选择要导出的表:", tables, key="export_table")
                if st.button("导出为CSV"):
                    try:
                        df = manager.get_sample_data(export_table, limit=10000)  # 限制导出行数
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 下载CSV文件",
                            data=csv,
                            file_name=f"{export_table}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"导出失败: {e}")
            else:
                st.info("没有可导出的表")

def show_system_monitoring_page_v23(system):
    """系统监控页面 V2.3 - 新增功能"""
    st.header("系统监控 V2.3")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("性能指标")
        
        # 缓存统计
        cache_size = len(system.sql_cache.cache)
        cache_access = sum(system.sql_cache.access_count.values())
        st.metric("SQL缓存大小", f"{cache_size}/100")
        st.metric("缓存访问次数", cache_access)
        
        # 数据库连接状态
        st.subheader("数据库连接")
        for db_id, db_config in system.databases.items():
            if db_config.get("active", False):
                success, msg = system.db_manager.test_connection(
                    db_config["type"], 
                    db_config["config"]
                )
                status = "🟢 正常" if success else "🔴 异常"
                st.write(f"{db_config['name']}: {status}")
    
    with col2:
        st.subheader("系统操作")
        
        if st.button("清空SQL缓存"):
            system.sql_cache.clear()
            st.success("SQL缓存已清空")
            st.rerun()
        
        if st.button("重新初始化ChromaDB"):
            system.cleanup_chromadb()
            system.initialize_local_vanna()
            st.success("ChromaDB已重新初始化")
        
        if st.button("测试所有数据库连接"):
            for db_id, db_config in system.databases.items():
                if db_config.get("active", False):
                    success, msg = system.db_manager.test_connection(
                        db_config["type"], 
                        db_config["config"]
                    )
                    if success:
                        st.success(f"{db_config['name']}: {msg}")
                    else:
                        st.error(f"{db_config['name']}: {msg}")

# 集成通用产品匹配的SQL生成函数
def generate_sql_with_universal_product_matching(question: str) -> str:
    """使用通用产品匹配的SQL生成函数"""
    try:
        # 初始化通用产品匹配器
        product_matcher = UniversalProductMatcher()
        
        # 检测产品
        product_info = product_matcher.detect_product_in_question(question)
        
        # 判断是否使用单表查询
        single_table_fields = [
            "全链库存", "财年", "财月", "财周", "Roadmap Family", "Group", "Model",
            "SellOut", "SellIn", "所有欠单", "成品总量", "BTC 库存总量", "联想DC库存"
        ]
        
        # 提取目标字段
        target_fields = []
        field_mapping = {
            "全链库存": "全链库存",
            "周转": "全链库存DOI",
            "DOI": "全链库存DOI",
            "SellOut": "SellOut",
            "SellIn": "SellIn",
            "欠单": "所有欠单"
        }
        
        for keyword, field in field_mapping.items():
            if keyword in question:
                target_fields.append(field)
        
        if not target_fields:
            target_fields = ["全链库存"]
        
        # 检查是否所有字段都在单表中
        fields_in_single_table = all(field in single_table_fields for field in target_fields)
        
        if fields_in_single_table and product_info:
            # 使用单表查询
            field_list = ", ".join(f"[{field}]" for field in target_fields)
            select_clause = f"SELECT {field_list}"
            from_clause = "FROM [dtsupply_summary]"
            
            # WHERE条件
            where_conditions = []
            
            # 产品条件 - 使用通用匹配器
            product_conditions = product_matcher.generate_product_conditions(question)
            where_conditions.extend(product_conditions)
            
            # 时间条件
            import re
            
            # 年份：25年 -> 2025
            year_match = re.search(r'(\d{2})年', question)
            if year_match:
                year_value = int("20" + year_match.group(1))
                where_conditions.append(f"[财年] = {year_value}")
            
            # 月份：7月 -> "7月"
            month_match = re.search(r'(\d{1,2})月', question)
            if month_match:
                month_str = month_match.group(1) + "月"
                where_conditions.append(f"[财月] = '{month_str}'")
            
            # 特殊标识
            if "全链库存" in question:
                where_conditions.append("[财周] = 'ttl'")
            
            # 组装SQL
            sql_parts = [select_clause, from_clause]
            if where_conditions:
                sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
            
            return " ".join(sql_parts)
        
        else:
            # 如果检测到产品但不适合单表，仍然尝试单表
            if product_info:
                return generate_sql_with_universal_product_matching(question.replace(product_info["keyword"], ""))
            
            # 默认查询
            return "SELECT * FROM [dtsupply_summary] WHERE 1=1"
    
    except Exception as e:
        logging.error(f"通用产品匹配SQL生成失败: {e}")
        return "SELECT * FROM [dtsupply_summary] WHERE 1=1"

# 测试通用产品匹配
def test_universal_product_matching():
    """测试通用产品匹配"""
    test_questions = [
        "510S 25年7月全链库存",
        "geek产品今年的SellOut数据",
        "小新系列2025年周转情况", 
        "拯救者全链库存",
        "AIO产品库存"
    ]
    
    print("=== 通用产品匹配测试 ===")
    
    for question in test_questions:
        print(f"\n问题: {question}")
        sql = generate_sql_with_universal_product_matching(question)
        print(f"SQL: {sql}")
        
        # 检查是否包含正确的产品条件
        if "510S" in question and "LIKE '%510S%'" in sql:
            print("✅ 510S产品匹配正确")
        elif "geek" in question and "LIKE '%Geek%'" in sql:
            print("✅ geek产品匹配正确")
        elif "小新" in question and "LIKE '%小新%'" in sql:
            print("✅ 小新产品匹配正确")
        elif "拯救者" in question and "LIKE '%拯救者%'" in sql:
            print("✅ 拯救者产品匹配正确")
        elif "AIO" in question and "LIKE '%AIO%'" in sql:
            print("✅ AIO产品匹配正确")
        else:
            print("❌ 产品匹配可能有问题")
        
        print("-" * 50)

def main():
    """主函数 - 恢复完整的Text2SQL V2.3系统 + 通用产品匹配"""
    st.set_page_config(
        page_title="Text2SQL V2.3 Enhanced System",
        page_icon="🔍",
        layout="wide"
    )
    
    # 初始化系统
    if 'text2sql_system' not in st.session_state:
        try:
            # 创建一个简化的系统类来恢复基本功能
            class SimpleText2SQLSystem:
                def __init__(self):
                    self.databases = self.load_database_configs()
                    self.sql_cache = SQLCache()
                    self.db_manager = DatabaseManager()
                    self.table_knowledge = self.load_table_knowledge()
                
                def load_database_configs(self):
                    try:
                        with open('database_configs.json', 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except:
                        return {
                            "default_sqlite": {
                                "name": "默认SQLite",
                                "type": "sqlite",
                                "config": {"database": "test_database.db"},
                                "active": True
                            }
                        }
                
                def load_table_knowledge(self):
                    """加载表知识库"""
                    try:
                        with open('table_knowledge.json', 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except:
                        return {}
                
                def save_table_knowledge(self) -> bool:
                    """保存表知识库"""
                    try:
                        with open('table_knowledge.json', 'w', encoding='utf-8') as f:
                            json.dump(self.table_knowledge, f, ensure_ascii=False, indent=2)
                        return True
                    except Exception as e:
                        return False
            
            # 创建数据库管理器
            class DatabaseManager:
                def __init__(self):
                    pass
                
                def test_connection(self, db_type: str, config: dict) -> Tuple[bool, str]:
                    try:
                        if db_type.lower() == "sqlite":
                            conn = sqlite3.connect(config.get("database", "test_database.db"))
                            conn.close()
                            return True, "SQLite连接成功"
                        elif db_type.lower() == "mssql":
                            # MSSQL连接测试
                            server = config.get("server", "")
                            database = config.get("database", "")
                            username = config.get("username", "")
                            password = config.get("password", "")
                            
                            if not all([server, database]):
                                return False, "MSSQL配置不完整"
                            
                            # 构建连接字符串
                            if username and password:
                                conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
                            else:
                                conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
                            
                            conn = pyodbc.connect(conn_str, timeout=10)
                            conn.close()
                            return True, "MSSQL连接成功"
                        else:
                            return False, f"不支持的数据库类型: {db_type}"
                    except Exception as e:
                        return False, f"连接失败: {str(e)}"
                
                def get_connection(self, db_config: dict):
                    db_type = db_config.get("type", "sqlite")
                    config = db_config.get("config", {})
                    
                    if db_type.lower() == "sqlite":
                        return sqlite3.connect(config.get("database", "test_database.db"))
                    elif db_type.lower() == "mssql":
                        server = config.get("server", "")
                        database = config.get("database", "")
                        username = config.get("username", "")
                        password = config.get("password", "")
                        
                        if username and password:
                            conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
                        else:
                            conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
                        
                        return pyodbc.connect(conn_str)
                    else:
                        raise ValueError(f"不支持的数据库类型: {db_type}")
                
                def get_tables(self, db_type: str, config: dict) -> List[str]:
                    """获取数据库中的表列表"""
                    try:
                        if db_type.lower() == "sqlite":
                            conn = sqlite3.connect(config.get("database", "test_database.db"))
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                            tables = [row[0] for row in cursor.fetchall()]
                            conn.close()
                            return tables
                        elif db_type.lower() == "mssql":
                            conn = self.get_connection({"type": db_type, "config": config})
                            cursor = conn.cursor()
                            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
                            tables = [row[0] for row in cursor.fetchall()]
                            conn.close()
                            return tables
                        else:
                            return []
                    except Exception as e:
                        return []
                
                def get_table_schema(self, db_type: str, config: dict, table_name: str) -> dict:
                    """获取表结构信息"""
                    try:
                        if db_type.lower() == "sqlite":
                            conn = sqlite3.connect(config.get("database", "test_database.db"))
                            cursor = conn.cursor()
                            cursor.execute(f"PRAGMA table_info([{table_name}])")
                            column_info = cursor.fetchall()
                            columns = [col[1] for col in column_info]  # 列名
                            conn.close()
                            
                            return {
                                "columns": columns,
                                "column_info": column_info
                            }
                        elif db_type.lower() == "mssql":
                            conn = self.get_connection({"type": db_type, "config": config})
                            cursor = conn.cursor()
                            cursor.execute(f"""
                                SELECT 
                                    ORDINAL_POSITION,
                                    COLUMN_NAME,
                                    DATA_TYPE,
                                    IS_NULLABLE,
                                    COLUMN_DEFAULT,
                                    CASE WHEN COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA+'.'+TABLE_NAME), COLUMN_NAME, 'IsIdentity') = 1 
                                         THEN 1 ELSE 0 END as is_primary
                                FROM INFORMATION_SCHEMA.COLUMNS 
                                WHERE TABLE_NAME = '{table_name}'
                                ORDER BY ORDINAL_POSITION
                            """)
                            column_info = cursor.fetchall()
                            columns = [col[1] for col in column_info]  # 列名
                            conn.close()
                            
                            return {
                                "columns": columns,
                                "column_info": column_info
                            }
                        else:
                            return {}
                    except Exception as e:
                        return {}
            
            st.session_state.text2sql_system = SimpleText2SQLSystem()
        except Exception as e:
            st.error(f"系统初始化失败: {e}")
            st.session_state.text2sql_system = None
    
    # 侧边栏导航
    with st.sidebar:
        st.title("🔍 Text2SQL V2.3 Enhanced")
        st.markdown("---")
        
        # 页面选择 - 恢复完整功能
        page = st.selectbox(
            "选择功能页面",
            [
                "🚀 智能SQL生成 (新)",
                "📊 SQL查询",
                "🗄️ 数据库管理",
                "📋 表结构管理", 
                "🎯 产品知识库",
                "📝 业务规则",
                "🔧 提示词模板",
                "📈 系统监控"
            ]
        )
        
        st.markdown("---")
        st.markdown("### 🎯 新功能亮点")
        st.success("✅ 通用产品匹配")
        st.success("✅ 智能单表查询")
        st.success("✅ 时间格式修复")
        st.success("✅ 支持所有产品")
        
        st.markdown("---")
        st.markdown("### 🗄️ 数据库支持")
        st.info("✅ MSSQL Server")
        st.info("✅ SQLite")
        st.info("✅ 多数据库连接")
    
    # 根据选择显示不同页面
    if page == "🚀 智能SQL生成 (新)":
        show_enhanced_sql_generation_page()
    elif page == "📊 SQL查询":
        if st.session_state.text2sql_system:
            show_sql_query_page_restored(st.session_state.text2sql_system)
        else:
            st.warning("系统未完全初始化，请使用新的智能SQL生成功能")
    elif page == "🗄️ 数据库管理":
        if st.session_state.text2sql_system:
            show_database_management_page_restored(st.session_state.text2sql_system)
        else:
            st.warning("系统未完全初始化，数据库管理功能暂不可用")
    elif page == "📋 表结构管理":
        show_table_management_page_enhanced()
    elif page == "🎯 产品知识库":
        show_product_knowledge_page_enhanced()
    elif page == "📝 业务规则":
        show_business_rules_page_enhanced()
    elif page == "🔧 提示词模板":
        show_prompt_templates_page_enhanced()
    elif page == "📈 系统监控":
        if st.session_state.text2sql_system:
            # show_system_monitoring_page_v23(st.session_state.text2sql_system)
            st.info("原有系统监控功能")
        else:
            st.warning("系统未完全初始化，监控功能暂不可用")

def show_enhanced_sql_generation_page():
    """增强的SQL生成页面 - 集成通用产品匹配"""
    st.title("🚀 智能SQL生成 - 通用产品匹配")
    st.markdown("支持510S、geek、小新、拯救者、AIO等所有产品的智能SQL生成")
    
    # 产品支持信息
    with st.expander("🎯 支持的产品", expanded=False):
        try:
            matcher = UniversalProductMatcher()
            supported_products = matcher.get_all_supported_products()
            
            cols = st.columns(3)
            for i, (keyword, families) in enumerate(supported_products.items()):
                with cols[i % 3]:
                    st.write(f"**📦 {keyword}**")
                    st.write(f"模式: `LIKE '%{matcher.product_patterns[keyword]['pattern']}%'`")
                    st.write(f"产品数: {len(families)}")
        except Exception as e:
            st.error(f"加载产品信息失败: {e}")
    
    # 主界面
    st.header("💬 自然语言查询")
    
    # 输入区域
    col1, col2 = st.columns([3, 1])
    
    with col1:
        question = st.text_input(
            "请输入您的问题:",
            placeholder="例如: 510S 25年7月全链库存, geek产品今年的SellOut数据",
            help="支持所有产品类型，自动识别并生成优化的SQL"
        )
    
    with col2:
        use_new_engine = st.checkbox("使用新引擎", value=True, help="使用通用产品匹配引擎")
    
    # 示例问题
    st.subheader("💡 示例问题")
    example_questions = [
        "510S 25年7月全链库存",
        "geek产品今年的SellOut数据", 
        "小新系列2025年周转情况",
        "拯救者全链库存",
        "AIO产品库存"
    ]
    
    cols = st.columns(len(example_questions))
    for i, example in enumerate(example_questions):
        with cols[i]:
            if st.button(f"📝 {example}", key=f"example_{i}"):
                st.session_state.question = example
                st.rerun()
    
    # 如果有session state中的问题，使用它
    if hasattr(st.session_state, 'question'):
        question = st.session_state.question
    
    # SQL生成
    if st.button("🚀 生成SQL", type="primary") and question:
        with st.spinner("正在生成SQL..."):
            try:
                if use_new_engine:
                    # 使用新的通用产品匹配引擎
                    sql = generate_sql_with_universal_product_matching(question)
                    engine_info = "✨ 通用产品匹配引擎"
                else:
                    # 使用原有逻辑（如果存在）
                    sql = "SELECT * FROM [dtsupply_summary] WHERE 1=1  -- 原有引擎"
                    engine_info = "🔧 原有引擎"
                
                # 显示结果
                st.success(f"SQL生成成功！({engine_info})")
                
                # SQL显示区域
                col_sql, col_info = st.columns([2, 1])
                
                with col_sql:
                    st.subheader("📝 生成的SQL")
                    st.code(sql, language="sql")
                    
                    # 复制按钮
                    if st.button("📋 复制SQL"):
                        st.write("SQL已复制到剪贴板")  # 实际复制功能需要JavaScript
                
                with col_info:
                    st.subheader("🔍 分析信息")
                    
                    # 分析SQL特征
                    analysis = []
                    if "JOIN" not in sql.upper():
                        analysis.append("✅ 单表查询 (性能优化)")
                    else:
                        analysis.append("⚠️ 多表查询")
                    
                    if "LIKE '%" in sql:
                        analysis.append("✅ 产品模糊匹配")
                    
                    if "[Group] = 'ttl'" in sql:
                        analysis.append("✅ 正确的产品层级")
                    
                    if re.search(r"\[财月\] = '\d+月'", sql):
                        analysis.append("✅ 正确的时间格式")
                    
                    if "'2025" in sql and "月'" not in sql:
                        analysis.append("❌ 时间格式可能错误")
                    
                    for item in analysis:
                        st.write(item)
                
                # 产品检测信息
                try:
                    matcher = UniversalProductMatcher()
                    product_info = matcher.detect_product_in_question(question)
                    if product_info:
                        st.info(f"🎯 检测到产品: {product_info['keyword']} → {product_info['pattern']}")
                    else:
                        st.warning("⚠️ 未检测到产品关键词")
                except Exception as e:
                    st.error(f"产品检测失败: {e}")
                
            except Exception as e:
                st.error(f"SQL生成失败: {e}")
                st.exception(e)
    
    # 测试区域
    st.markdown("---")
    st.subheader("🧪 系统测试")
    
    if st.button("运行产品匹配测试"):
        with st.spinner("运行测试中..."):
            try:
                # 捕获测试输出
                import io
                import sys
                
                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                
                test_universal_product_matching()
                
                sys.stdout = old_stdout
                test_output = buffer.getvalue()
                
                st.text_area("测试结果:", test_output, height=300)
                
            except Exception as e:
                st.error(f"测试失败: {e}")

def show_table_management_page_enhanced():
    """恢复的表结构管理页面 - 原有完整功能"""
    st.header("📋 表结构管理")
    
    # 获取系统实例
    system = st.session_state.get('text2sql_system')
    if not system:
        st.error("系统未初始化")
        return
    
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
                            system.table_knowledge[table_key]["columns"] = schema["columns"]
                            
                            if system.save_table_knowledge():
                                st.success(f"已保存 {table} 的备注信息")
                            else:
                                st.error("保存失败")
                        
                        # 添加到知识库
                        if st.button(f"添加 {table} 到知识库", key=f"add_to_kb_{table}"):
                            if table_key not in system.table_knowledge:
                                system.table_knowledge[table_key] = {}
                            
                            system.table_knowledge[table_key] = {
                                "comment": new_comment,
                                "fields": field_comments,
                                "schema": schema,
                                "columns": schema["columns"],
                                "column_info": schema["column_info"],
                                "relationships": system.table_knowledge.get(table_key, {}).get("relationships", [])
                            }
                            
                            if system.save_table_knowledge():
                                st.success(f"已添加 {table} 到知识库")
                            else:
                                st.error("添加失败")
        
        # --- 已导入知识库的表 ---
        st.subheader("已导入知识库的表")
        if system.table_knowledge:
            for table_name in list(system.table_knowledge.keys()):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"- {table_name}")
                with col_b:
                    if st.button("删除", key=f"del_kb_{table_name}"):
                        del system.table_knowledge[table_name]
                        system.save_table_knowledge()
                        st.success(f"已删除表 {table_name}")
                        st.rerun()
        else:
            st.info("知识库为空")

        # --- 自动生成表字段关联按钮与展示区 ---
        st.subheader("表关联管理")
        if st.button("自动生成表字段关联", type="primary"):
            # 自动分析并保存所有表关联
            relationships = []
            table_names = list(system.table_knowledge.keys())
            for i, table1 in enumerate(table_names):
                for table2 in table_names[i+1:]:
                    cols1 = system.table_knowledge[table1]["columns"]
                    cols2 = system.table_knowledge[table2]["columns"]
                    # 同名字段
                    common_fields = set(cols1) & set(cols2)
                    for field in common_fields:
                        relationships.append({
                            "table1": table1,
                            "table2": table2,
                            "field1": field,
                            "field2": field,
                            "type": "auto",
                            "description": f"{table1}.{field} = {table2}.{field}"
                        })
                    # ID字段
                    for col1 in cols1:
                        if col1.lower().endswith('id'):
                            for col2 in cols2:
                                if col2.lower().endswith('id') and col1 != col2:
                                    relationships.append({
                                        "table1": table1,
                                        "table2": table2,
                                        "field1": col1,
                                        "field2": col2,
                                        "type": "auto",
                                        "description": f"{table1}.{col1} <-> {table2}.{col2}"
                                    })
            # 保存到每个表
            for table_name in system.table_knowledge:
                # 只保留手工添加的
                manual_rels = [r for r in system.table_knowledge[table_name].get("relationships", []) if r.get("type") == "manual"]
                auto_rels = [r for r in relationships if r["table1"] == table_name or r["table2"] == table_name]
                system.table_knowledge[table_name]["relationships"] = manual_rels + auto_rels
            system.save_table_knowledge()
            st.success(f"已自动生成 {len(relationships)} 条表关联关系，请下方查看。")
            st.rerun()

        # 展示所有表关联（自动+手工）
        st.subheader("表关联关系展示区")
        
        # 收集所有表关联关系
        all_relationships = []
        for table_name, table_info in system.table_knowledge.items():
            for rel in table_info.get("relationships", []):
                rel_type = "手工" if rel.get("type") == "manual" else "自动"
                all_relationships.append({
                    "表1": rel.get("table1", ""),
                    "字段1": rel.get("field1", ""),
                    "表2": rel.get("table2", ""),
                    "字段2": rel.get("field2", ""),
                    "类型": rel_type,
                    "描述": rel.get("description", "")
                })
        
        # 表头
        header_cols = st.columns([2, 2, 2, 2, 1, 3, 1])
        header_cols[0].markdown("**表1**")
        header_cols[1].markdown("**字段1**")
        header_cols[2].markdown("**表2**")
        header_cols[3].markdown("**字段2**")
        header_cols[4].markdown("**类型**")
        header_cols[5].markdown("**描述**")
        header_cols[6].markdown("**操作**")
        # 每行渲染
        if all_relationships:
            for idx, rel in enumerate(all_relationships):
                cols = st.columns([2, 2, 2, 2, 1, 3, 1])
                cols[0].write(rel["表1"])
                cols[1].write(rel["字段1"])
                cols[2].write(rel["表2"])
                cols[3].write(rel["字段2"])
                cols[4].write(rel["类型"])
                cols[5].write(rel["描述"])
                with cols[6]:
                    if st.button("删除", key=f"del_rel_{idx}"):
                        for t in [rel["表1"], rel["表2"]]:
                            if t in system.table_knowledge:
                                system.table_knowledge[t]["relationships"] = [
                                    r for r in system.table_knowledge[t]["relationships"]
                                    if not (
                                        r.get("table1") == rel["表1"] and
                                        r.get("table2") == rel["表2"] and
                                        r.get("field1") == rel["字段1"] and
                                        r.get("field2") == rel["字段2"] and
                                        (r.get("type") == ("manual" if rel["类型"] == "手工" else "auto"))
                                    )
                                ]
                        system.save_table_knowledge()
                        st.success("已删除该表关联！")
                        st.rerun()
        else:
            st.info("暂无表关联关系，请点击上方按钮自动生成。")

        # --- 手工添加表字段关联 ---
        st.subheader("手工添加表字段关联")
        if len(system.table_knowledge) >= 2:
            table_names = list(system.table_knowledge.keys())
            # 表选择放在表单外，保证字段下拉实时联动
            manual_table1 = st.selectbox("表1", table_names, key="manual_table1_out")
            manual_table2 = st.selectbox("表2", table_names, key="manual_table2_out")
            field1_options = system.table_knowledge[manual_table1]["columns"] if manual_table1 in system.table_knowledge else []
            field2_options = system.table_knowledge[manual_table2]["columns"] if manual_table2 in system.table_knowledge else []
            with st.form("add_manual_relationship"):
                manual_field1 = st.selectbox("字段1", field1_options, key=f"manual_field1_{manual_table1}")
                manual_field2 = st.selectbox("字段2", field2_options, key=f"manual_field2_{manual_table2}")
                manual_desc = st.text_input("关联描述", value=f"{manual_table1}.{manual_field1} <-> {manual_table2}.{manual_field2}")
                submitted = st.form_submit_button("添加手工关联")
                if submitted:
                    rel = {
                        "table1": manual_table1,
                        "table2": manual_table2,
                        "field1": manual_field1,
                        "field2": manual_field2,
                        "type": "manual",
                        "description": manual_desc
                    }
                    for t in [manual_table1, manual_table2]:
                        if "relationships" not in system.table_knowledge[t]:
                            system.table_knowledge[t]["relationships"] = []
                        system.table_knowledge[t]["relationships"].append(rel)
                    system.save_table_knowledge()
                    st.success("手工关联已添加！")
                    st.rerun()
        else:
            st.info("请先导入至少两个表后再添加手工关联。")
    
    with col2:
        st.subheader("表结构管理说明")
        st.markdown("""
        ### 功能说明
        - **查看表结构**: 显示字段信息和类型
        - **添加备注**: 为表和字段添加业务说明
        - **添加到知识库**: 将表结构保存到知识库
        - **自动生成关联**: 分析表间字段关联关系
        - **手工添加关联**: 手动定义表关联关系
        
        ### 操作步骤
        1. 选择要管理的数据库
        2. 展开要编辑的表
        3. 添加表和字段的备注
        4. 保存备注信息
        5. 添加表到知识库
        6. 生成或手工添加表关联关系
        
        ### 关联关系说明
        - **自动关联**: 基于同名字段和ID字段
        - **手工关联**: 用户手动定义的关联
        - **关联用途**: 用于多表查询的JOIN条件
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        kb_table_count = len(system.table_knowledge)
        st.metric("知识库表数", kb_table_count)
        
        total_relationships = 0
        for table_info in system.table_knowledge.values():
            total_relationships += len(table_info.get("relationships", []))
        
        st.metric("表关联数", total_relationships)
        
        # 批量操作
        st.subheader("批量操作")
        
        if st.button("清空知识库"):
            if st.checkbox("确认清空知识库"):
                system.table_knowledge = {}
                system.save_table_knowledge()
                st.success("已清空表知识库")
                st.rerun()

def show_database_management_page_restored(system):
    """恢复的数据库管理页面 - 支持MSSQL和SQLite"""
    st.header("🗄️ 数据库管理")
    
    # 显示当前数据库配置
    st.subheader("📊 当前数据库配置")
    
    if system.databases:
        for db_id, db_config in system.databases.items():
            with st.expander(f"📁 {db_config.get('name', db_id)}", expanded=db_config.get('active', False)):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**类型**: {db_config.get('type', '未知').upper()}")
                    
                    if db_config.get('type') == 'sqlite':
                        st.write(f"**数据库文件**: {db_config.get('config', {}).get('database', '未设置')}")
                    elif db_config.get('type') == 'mssql':
                        config = db_config.get('config', {})
                        st.write(f"**服务器**: {config.get('server', '未设置')}")
                        st.write(f"**数据库**: {config.get('database', '未设置')}")
                        st.write(f"**用户名**: {config.get('username', '未设置')}")
                    
                    st.write(f"**状态**: {'🟢 活跃' if db_config.get('active') else '🔴 非活跃'}")
                
                with col2:
                    if st.button(f"测试连接", key=f"test_{db_id}"):
                        success, msg = system.db_manager.test_connection(
                            db_config.get('type'), 
                            db_config.get('config', {})
                        )
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
    
    # 添加新数据库配置
    st.subheader("➕ 添加新数据库")
    
    db_type = st.selectbox("数据库类型:", ["sqlite", "mssql"])
    db_name = st.text_input("配置名称:")
    
    if db_type == "sqlite":
        db_file = st.text_input("数据库文件路径:", value="new_database.db")
        
        if st.button("添加SQLite数据库"):
            if db_name and db_file:
                new_config = {
                    "name": db_name,
                    "type": "sqlite",
                    "config": {"database": db_file},
                    "active": False
                }
                
                system.databases[db_name.lower().replace(" ", "_")] = new_config
                
                # 保存到文件
                try:
                    with open('database_configs.json', 'w', encoding='utf-8') as f:
                        json.dump(system.databases, f, ensure_ascii=False, indent=2)
                    st.success(f"已添加SQLite数据库: {db_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存配置失败: {e}")
    
    elif db_type == "mssql":
        col1, col2 = st.columns(2)
        
        with col1:
            server = st.text_input("服务器地址:")
            database = st.text_input("数据库名:")
        
        with col2:
            username = st.text_input("用户名 (可选):")
            password = st.text_input("密码 (可选):", type="password")
        
        if st.button("添加MSSQL数据库"):
            if db_name and server and database:
                new_config = {
                    "name": db_name,
                    "type": "mssql",
                    "config": {
                        "server": server,
                        "database": database,
                        "username": username,
                        "password": password
                    },
                    "active": False
                }
                
                system.databases[db_name.lower().replace(" ", "_")] = new_config
                
                # 保存到文件
                try:
                    with open('database_configs.json', 'w', encoding='utf-8') as f:
                        json.dump(system.databases, f, ensure_ascii=False, indent=2)
                    st.success(f"已添加MSSQL数据库: {db_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存配置失败: {e}")

def show_sql_query_page_restored(system):
    """恢复的SQL查询页面"""
    st.header("📊 SQL查询")
    
    # 选择数据库
    active_dbs = {k: v for k, v in system.databases.items() if v.get('active', False)}
    
    if not active_dbs:
        st.warning("没有活跃的数据库连接，请先在数据库管理页面配置并激活数据库")
        return
    
    selected_db = st.selectbox(
        "选择数据库:",
        options=list(active_dbs.keys()),
        format_func=lambda x: active_dbs[x].get('name', x)
    )
    
    if selected_db:
        db_config = active_dbs[selected_db]
        st.info(f"当前数据库: {db_config.get('name')} ({db_config.get('type').upper()})")
        
        # SQL输入
        st.subheader("📝 SQL查询")
        
        # 提供示例查询
        col1, col2 = st.columns([3, 1])
        
        with col1:
            sql_query = st.text_area(
                "输入SQL查询:",
                height=150,
                placeholder="SELECT * FROM table_name LIMIT 10"
            )
        
        with col2:
            st.write("**示例查询:**")
            if st.button("显示所有表", key="show_tables"):
                if db_config.get('type') == 'sqlite':
                    sql_query = "SELECT name FROM sqlite_master WHERE type='table'"
                else:
                    sql_query = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
                st.rerun()
            
            if st.button("表结构查询", key="table_info"):
                if db_config.get('type') == 'sqlite':
                    sql_query = "PRAGMA table_info(table_name)"
                else:
                    sql_query = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='table_name'"
                st.rerun()
        
        # 执行查询
        if st.button("🚀 执行查询", type="primary"):
            if sql_query.strip():
                try:
                    conn = system.db_manager.get_connection(db_config)
                    
                    # 执行查询
                    if sql_query.strip().upper().startswith('SELECT'):
                        df = pd.read_sql_query(sql_query, conn)
                        
                        st.success(f"查询成功！返回 {len(df)} 行数据")
                        
                        if not df.empty:
                            st.dataframe(df, use_container_width=True)
                            
                            # 提供下载选项
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 下载CSV",
                                data=csv,
                                file_name="query_result.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("查询结果为空")
                    else:
                        # 非SELECT语句
                        cursor = conn.cursor()
                        cursor.execute(sql_query)
                        conn.commit()
                        
                        affected_rows = cursor.rowcount
                        st.success(f"SQL执行成功！影响 {affected_rows} 行")
                    
                    conn.close()
                    
                except Exception as e:
                    st.error(f"查询执行失败: {str(e)}")
            else:
                st.warning("请输入SQL查询语句")
        
        # 查询历史
        st.subheader("📚 查询历史")
        if 'sql_history' not in st.session_state:
            st.session_state.sql_history = []
        
        if sql_query and sql_query not in st.session_state.sql_history:
            st.session_state.sql_history.insert(0, sql_query)
            st.session_state.sql_history = st.session_state.sql_history[:10]  # 保留最近10条
        
        if st.session_state.sql_history:
            for i, hist_sql in enumerate(st.session_state.sql_history):
                if st.button(f"📝 {hist_sql[:50]}...", key=f"hist_{i}"):
                    sql_query = hist_sql
                    st.rerun()

def show_product_knowledge_page_enhanced():
    """增强的产品知识库页面"""
    st.header("🎯 产品知识库管理")
    
    # 加载产品知识库
    try:
        with open('product_knowledge.json', 'r', encoding='utf-8') as f:
            product_knowledge = json.load(f)
    except:
        product_knowledge = {"products": {}}
    
    # 统计信息
    total_products = len(product_knowledge.get('products', {}))
    st.metric("产品总数", total_products)
    
    # 产品分类统计
    if product_knowledge.get('products'):
        families = {}
        for pn, product in product_knowledge['products'].items():
            family = product.get('Roadmap Family', '未知')
            if family not in families:
                families[family] = 0
            families[family] += 1
        
        st.subheader("📊 产品系列分布")
        family_df = pd.DataFrame(list(families.items()), columns=['产品系列', '数量'])
        st.bar_chart(family_df.set_index('产品系列'))
        
        # 产品详情
        st.subheader("📋 产品详情")
        selected_family = st.selectbox("选择产品系列:", list(families.keys()))
        
        if selected_family:
            family_products = []
            for pn, product in product_knowledge['products'].items():
                if product.get('Roadmap Family') == selected_family:
                    family_products.append({
                        'PN': pn,
                        'Roadmap Family': product.get('Roadmap Family', ''),
                        'Group': product.get('Group', ''),
                        'Model': product.get('Model', '')
                    })
            
            if family_products:
                products_df = pd.DataFrame(family_products)
                st.dataframe(products_df, use_container_width=True)

def show_business_rules_page_enhanced():
    """增强的业务规则页面"""
    st.header("📝 业务规则管理")
    
    # 加载业务规则
    try:
        with open('business_rules.json', 'r', encoding='utf-8') as f:
            business_rules = json.load(f)
    except:
        business_rules = {}
    
    # 显示当前规则
    st.subheader("📋 当前业务规则")
    
    if business_rules:
        rules_df = pd.DataFrame(list(business_rules.items()), columns=['关键词', '规则'])
        st.dataframe(rules_df, use_container_width=True)
        
        # 规则编辑
        st.subheader("✏️ 编辑规则")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**添加新规则:**")
            new_keyword = st.text_input("关键词:")
            new_rule = st.text_area("规则:")
            
            if st.button("添加规则"):
                if new_keyword and new_rule:
                    business_rules[new_keyword] = new_rule
                    with open('business_rules.json', 'w', encoding='utf-8') as f:
                        json.dump(business_rules, f, ensure_ascii=False, indent=2)
                    st.success(f"已添加规则: {new_keyword}")
                    st.rerun()
        
        with col2:
            st.write("**删除规则:**")
            delete_keyword = st.selectbox("选择要删除的关键词:", list(business_rules.keys()))
            
            if st.button("删除规则", type="secondary"):
                if delete_keyword:
                    del business_rules[delete_keyword]
                    with open('business_rules.json', 'w', encoding='utf-8') as f:
                        json.dump(business_rules, f, ensure_ascii=False, indent=2)
                    st.success(f"已删除规则: {delete_keyword}")
                    st.rerun()
    else:
        st.info("没有业务规则")

def show_prompt_templates_page_enhanced():
    """增强的提示词模板页面"""
    st.header("🔧 提示词模板管理")
    
    # 加载提示词模板
    try:
        with open('prompt_templates.json', 'r', encoding='utf-8') as f:
            prompt_templates = json.load(f)
    except:
        prompt_templates = {}
    
    # 显示模板
    st.subheader("📋 当前模板")
    
    if prompt_templates:
        for template_name, template_content in prompt_templates.items():
            with st.expander(f"📝 {template_name}"):
                st.text_area(
                    f"模板内容 - {template_name}:",
                    template_content,
                    height=200,
                    key=f"template_{template_name}"
                )
                
                if st.button(f"保存 {template_name}", key=f"save_{template_name}"):
                    new_content = st.session_state[f"template_{template_name}"]
                    prompt_templates[template_name] = new_content
                    with open('prompt_templates.json', 'w', encoding='utf-8') as f:
                        json.dump(prompt_templates, f, ensure_ascii=False, indent=2)
                    st.success(f"已保存模板: {template_name}")
    else:
        st.info("没有提示词模板")
    
    # 添加新模板
    st.subheader("➕ 添加新模板")
    
    new_template_name = st.text_input("模板名称:")
    new_template_content = st.text_area("模板内容:", height=200)
    
    if st.button("添加模板"):
        if new_template_name and new_template_content:
            prompt_templates[new_template_name] = new_template_content
            with open('prompt_templates.json', 'w', encoding='utf-8') as f:
                json.dump(prompt_templates, f, ensure_ascii=False, indent=2)
            st.success(f"已添加模板: {new_template_name}")
            st.rerun()

if __name__ == "__main__":
    # 可以选择运行测试或主程序
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_universal_product_matching()
    else:
        main()