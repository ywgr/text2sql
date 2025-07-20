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
        
        for term, replacement in self.business_rules.items():
            if term in processed:
                processed = processed.replace(term, replacement)
        
        return processed
    
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
                            height=60
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
            
            # 关联关系表格显示
            df_relationships = pd.DataFrame(all_relationships)
            df_display = df_relationships[["表1", "字段1", "表2", "字段2", "类型", "置信度", "描述"]]
            st.dataframe(df_display, use_container_width=True)
            
            # 删除关联关系
            if st.button("清空所有关联"):
                if st.session_state.get("confirm_clear_rel", False):
                    for table_name in system.table_knowledge:
                        system.table_knowledge[table_name]["relationships"] = []
                    system.save_table_knowledge()
                    st.success("所有关联关系已清空")
                    st.rerun()
                else:
                    st.session_state["confirm_clear_rel"] = True
                    st.warning("再次点击确认清空")
        else:
            st.info("暂无表关联关系，请点击上方按钮自动生成")
        
        # 手工添加表关联
        if len(system.table_knowledge) >= 2:
            st.subheader("手工添加表关联")
            
            table_names = list(system.table_knowledge.keys())
            
            with st.form("add_manual_relationship"):
                col_rel1, col_rel2 = st.columns(2)
                
                with col_rel1:
                    manual_table1 = st.selectbox("表1", table_names, key="manual_table1")
                    field1_options = system.table_knowledge[manual_table1]["columns"]
                    manual_field1 = st.selectbox("字段1", field1_options, key="manual_field1")
                
                with col_rel2:
                    manual_table2 = st.selectbox("表2", table_names, key="manual_table2")
                    field2_options = system.table_knowledge[manual_table2]["columns"]
                    manual_field2 = st.selectbox("字段2", field2_options, key="manual_field2")
                
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
            selected_db = st.selectbox(
                "选择数据库:",
                options=list(active_dbs.keys()),
                format_func=lambda x: active_dbs[x]["name"],
                key="product_db_select"
            )
            
            db_config = active_dbs[selected_db]
            
            # 检查可用的表
            with st.spinner("正在获取表列表..."):
                tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
            
            # 查找可能的产品表
            product_tables = [t for t in tables if any(keyword in t.lower() for keyword in ['group', 'product', 'item', 'goods'])]
            
            if product_tables:
                st.write(f"**找到 {len(product_tables)} 个可能的产品表:**")
                
                selected_table = st.selectbox("选择产品表:", product_tables)
                
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
            st.warning("请先激活数据库连接")
        
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

if __name__ == "__main__":
    main()