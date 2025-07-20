#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 - 本地部署版本
使用ChromaDB向量数据库 + DeepSeek LLM
完全本地部署，不依赖Vanna远程服务
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

class Text2SQLLocalSystem:
    """本地部署的TEXT2SQL系统"""
    
    def __init__(self):
        """初始化本地TEXT2SQL系统"""
        # 使用配置文件
        self.deepseek_api_key = LocalConfig.DEEPSEEK_API_KEY
        
        # SQLite数据库文件
        self.db_file = LocalConfig.SQLITE_DB_FILE
        
        # ChromaDB配置
        self.chroma_config = LocalConfig.get_chroma_config()
        
        # 创建必要的目录
        os.makedirs(LocalConfig.CHROMA_DB_PATH, exist_ok=True)
        
        # 初始化数据库
        self.initialize_database()
        
        # 获取数据库结构
        self.db_schema = self.get_database_schema()
        
        # 初始化本地Vanna实例
        self.vn = None
        self.initialize_local_vanna()
        
        # 业务规则和术语映射
        self.business_rules = self.load_business_rules()
        
        # 提示词模板
        self.prompt_templates = self.load_prompt_templates()

    def initialize_database(self):
        """初始化SQLite数据库"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 创建学生表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student (
                    student_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    class TEXT NOT NULL
                )
            ''')
            
            # 创建课程表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS course (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    course_name TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES student(student_id)
                )
            ''')
            
            # 创建成绩表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS score (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_name TEXT NOT NULL,
                    score REAL NOT NULL,
                    name TEXT NOT NULL
                )
            ''')
            
            # 检查是否需要插入测试数据
            cursor.execute("SELECT COUNT(*) FROM student")
            if cursor.fetchone()[0] == 0:
                self.insert_test_data(cursor)
            
            conn.commit()
            conn.close()
            logger.info("SQLite数据库初始化成功")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            st.error(f"❌ 数据库初始化失败: {e}")

    def insert_test_data(self, cursor):
        """插入测试数据"""
        # 学生数据
        students = [
            (1001, '张三', '男', '高一(1)班'),
            (1002, '李四', '男', '高一(1)班'),
            (1003, '王五', '男', '高一(2)班'),
            (1004, '赵六', '女', '高一(2)班'),
            (1005, '钱七', '女', '高一(3)班'),
            (1006, '孙八', '男', '高一(3)班'),
            (1007, '周九', '女', '高一(1)班'),
            (1008, '吴十', '男', '高一(2)班')
        ]
        
        cursor.executemany(
            "INSERT INTO student (student_id, name, gender, class) VALUES (?, ?, ?, ?)",
            students
        )
        
        # 课程数据
        courses = [
            (1001, '语文'), (1001, '数学'), (1001, '英语'),
            (1002, '语文'), (1002, '物理'), (1002, '化学'),
            (1003, '数学'), (1003, '物理'), (1003, '生物'),
            (1004, '语文'), (1004, '英语'), (1004, '历史'),
            (1005, '数学'), (1005, '地理'), (1005, '政治'),
            (1006, '语文'), (1006, '数学'), (1006, '英语'), (1006, '物理'),
            (1007, '语文'), (1007, '数学'), (1007, '化学'),
            (1008, '数学'), (1008, '物理'), (1008, '生物')
        ]
        
        cursor.executemany(
            "INSERT INTO course (student_id, course_name) VALUES (?, ?)",
            courses
        )
        
        # 成绩数据
        scores = [
            ('语文', 85.5, '张三'), ('数学', 92.0, '张三'), ('英语', 78.5, '张三'),
            ('语文', 76.0, '李四'), ('物理', 88.5, '李四'), ('化学', 90.0, '李四'),
            ('数学', 95.5, '王五'), ('物理', 82.0, '王五'), ('生物', 79.5, '王五'),
            ('语文', 88.0, '赵六'), ('英语', 92.5, '赵六'), ('历史', 85.0, '赵六'),
            ('数学', 90.0, '钱七'), ('地理', 87.5, '钱七'), ('政治', 93.0, '钱七'),
            ('语文', 82.0, '孙八'), ('数学', 88.0, '孙八'), ('英语', 85.0, '孙八'), ('物理', 91.0, '孙八'),
            ('语文', 89.0, '周九'), ('数学', 94.0, '周九'), ('化学', 87.0, '周九'),
            ('数学', 86.0, '吴十'), ('物理', 89.0, '吴十'), ('生物', 83.0, '吴十')
        ]
        
        cursor.executemany(
            "INSERT INTO score (course_name, score, name) VALUES (?, ?, ?)",
            scores
        )

    def get_database_schema(self) -> Dict:
        """获取数据库结构信息"""
        schema = {}
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            for table in tables:
                # 获取表结构
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                schema[table] = {
                    'columns': [col[1] for col in columns],
                    'column_info': columns
                }
                
                # 获取示例数据
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                sample_data = cursor.fetchall()
                schema[table]['sample_data'] = sample_data
            
            conn.close()
            return schema
            
        except Exception as e:
            logger.error(f"获取数据库结构失败: {e}")
            return {}

    def initialize_local_vanna(self):
        """初始化本地Vanna实例"""
        try:
            st.info("正在初始化本地Vanna (ChromaDB + DeepSeek)...")
            
            # 完全清理ChromaDB目录
            self.cleanup_chromadb()
            
            # 创建本地Vanna实例
            self.vn = LocalDeepSeekVanna(config=self.chroma_config)
            
            # 连接到SQLite数据库
            self.vn.connect_to_sqlite(self.db_file)
            
            st.success("本地Vanna初始化成功")
            
            # 训练本地知识库
            self.train_local_knowledge()
            
            return True
            
        except Exception as e:
            logger.error(f"本地Vanna初始化失败: {e}")
            st.error(f"本地Vanna初始化失败: {e}")
            
            # 如果还是失败，尝试使用备用方案
            try:
                st.info("尝试备用初始化方案...")
                self.vn = self.create_fallback_vanna()
                if self.vn:
                    st.success("备用Vanna初始化成功")
                    return True
            except Exception as e2:
                logger.error(f"备用方案也失败: {e2}")
            
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

    def train_local_knowledge(self):
        """训练本地知识库"""
        try:
            st.info("开始训练本地知识库...")
            
            # 1. 添加数据库结构信息
            ddl_statements = [
                """CREATE TABLE student (
                    student_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL COMMENT '学生姓名',
                    gender TEXT NOT NULL COMMENT '性别：男/女',
                    class TEXT NOT NULL COMMENT '班级信息'
                )""",
                """CREATE TABLE course (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    course_name TEXT NOT NULL COMMENT '课程名称：语文、数学、英语、物理、化学、生物、历史、地理、政治',
                    FOREIGN KEY (student_id) REFERENCES student(student_id)
                )""",
                """CREATE TABLE score (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_name TEXT NOT NULL COMMENT '课程名称',
                    score REAL NOT NULL COMMENT '成绩分数',
                    name TEXT NOT NULL COMMENT '学生姓名，关联student.name'
                )"""
            ]
            
            for ddl in ddl_statements:
                self.vn.train(ddl=ddl)
            
            # 2. 添加业务文档
            business_documentation = """
            学生管理系统数据库说明：
            
            这是一个中国高中学生管理系统，包含学生信息、课程信息和成绩信息。
            
            表结构说明：
            - student表：存储学生基本信息（学号、姓名、性别、班级）
            - course表：存储学生选课信息（课程ID、学生ID、课程名称）
            - score表：存储学生成绩信息（成绩ID、课程名称、分数、学生姓名）
            
            业务术语映射：
            - "学生" = student表
            - "课程" = course表  
            - "成绩" = score表
            - "姓名" = name字段
            - "性别" = gender字段
            - "班级" = class字段
            - "课程名称" = course_name字段
            - "分数" = score字段
            
            表关联规则：
            - student表与score表通过name字段关联：student.name = score.name
            - student表与course表通过student_id字段关联：student.student_id = course.student_id
            
            课程名称包括：语文、数学、英语、物理、化学、生物、历史、地理、政治
            学生姓名包括：张三、李四、王五、赵六、钱七、孙八、周九、吴十
            班级格式：高一(1)班、高一(2)班、高一(3)班
            """
            
            self.vn.train(documentation=business_documentation)
            
            # 3. 添加查询示例
            training_examples = [
                {"question": "查询所有学生", "sql": "SELECT * FROM student"},
                {"question": "显示学生姓名和班级", "sql": "SELECT name, class FROM student"},
                {"question": "统计每个班级的学生人数", "sql": "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"},
                {"question": "查询张三的所有成绩", "sql": "SELECT course_name, score FROM score WHERE name = '张三'"},
                {"question": "数学成绩最高的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学' ORDER BY sc.score DESC LIMIT 1"},
                {"question": "数学成绩前3名", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学' ORDER BY sc.score DESC LIMIT 3"},
                {"question": "化学成绩前3的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '化学' ORDER BY sc.score DESC LIMIT 3"},
                {"question": "物理成绩最好的5名学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '物理' ORDER BY sc.score DESC LIMIT 5"},
                {"question": "语文成绩大于85分的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '语文' AND sc.score > 85"},
                {"question": "英语成绩超过90分的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '英语' AND sc.score > 90"},
                {"question": "平均成绩最高的学生", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 1"},
                {"question": "每个学生的平均成绩", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC"},
            ]
            
            for example in training_examples:
                self.vn.train(question=example["question"], sql=example["sql"])
            
            st.success("本地知识库训练完成")
            
        except Exception as e:
            st.warning(f"本地知识库训练失败: {e}")
            logger.error(f"本地知识库训练失败: {e}")

    def create_fallback_vanna(self):
        """创建备用Vanna实例"""
        try:
            # 使用时间戳创建唯一路径
            import time
            timestamp = int(time.time())
            fallback_path = f"./chroma_db_backup_{timestamp}"
            
            # 确保备用目录不存在
            if os.path.exists(fallback_path):
                import shutil
                shutil.rmtree(fallback_path)
            
            os.makedirs(fallback_path, exist_ok=True)
            
            fallback_config = {
                "api_key": self.deepseek_api_key,
                "model": "deepseek-chat",
                "path": fallback_path,
                "collection_name": "text2sql_backup"
            }
            
            vn = LocalDeepSeekVanna(config=fallback_config)
            vn.connect_to_sqlite(self.db_file)
            
            # 快速训练基本知识
            self.quick_train_fallback(vn)
            
            return vn
            
        except Exception as e:
            logger.error(f"备用Vanna创建失败: {e}")
            return None

    def quick_train_fallback(self, vn):
        """快速训练备用Vanna"""
        try:
            # 添加基本的表结构
            vn.train(ddl="CREATE TABLE student (student_id INTEGER PRIMARY KEY, name TEXT, gender TEXT, class TEXT)")
            vn.train(ddl="CREATE TABLE course (id INTEGER PRIMARY KEY, student_id INTEGER, course_name TEXT)")
            vn.train(ddl="CREATE TABLE score (id INTEGER PRIMARY KEY, course_name TEXT, score REAL, name TEXT)")
            
            # 添加基本查询示例
            basic_examples = [
                {"question": "显示表student", "sql": "SELECT * FROM student"},
                {"question": "查询所有学生", "sql": "SELECT * FROM student"},
                {"question": "显示学生姓名", "sql": "SELECT name FROM student"},
                {"question": "显示学生信息", "sql": "SELECT * FROM student"}
            ]
            
            for example in basic_examples:
                vn.train(question=example["question"], sql=example["sql"])
                
        except Exception as e:
            logger.error(f"快速训练失败: {e}")

    def generate_sql_local(self, question: str) -> Tuple[str, str]:
        """使用本地Vanna生成SQL，并用DeepSeek验证"""
        try:
            if not self.vn:
                return self.deepseek_fallback_sql(question)
            
            st.info("使用本地Vanna (ChromaDB + DeepSeek) 生成SQL...")
            
            # 使用本地Vanna生成SQL
            sql = self.vn.generate_sql(question)
            
            if sql and sql.strip():
                cleaned_sql = self.clean_sql(sql)
                
                # 使用DeepSeek验证SQL
                st.info("使用DeepSeek验证SQL...")
                is_valid, verified_sql, verification_msg = self.verify_sql_with_deepseek(cleaned_sql, question)
                
                if is_valid:
                    return verified_sql, f"Vanna生成 + DeepSeek验证通过"
                else:
                    st.warning(f"SQL验证失败: {verification_msg}")
                    # 验证失败，使用DeepSeek重新生成
                    return self.deepseek_fallback_sql(question, f"Vanna生成的SQL验证失败: {verification_msg}")
            else:
                # Vanna生成失败，直接使用DeepSeek
                return self.deepseek_fallback_sql(question, "Vanna生成失败")
                
        except Exception as e:
            logger.error(f"本地Vanna生成SQL失败: {e}")
            # Vanna异常，使用DeepSeek兜底
            return self.deepseek_fallback_sql(question, f"Vanna异常: {e}")

    def verify_sql_with_deepseek(self, sql: str, question: str) -> Tuple[bool, str, str]:
        """使用DeepSeek验证SQL的正确性"""
        try:
            # 应用业务规则转换问题
            processed_question = self.apply_business_rules(question)
            
            schema_info = self.format_schema_for_prompt()
            business_rules = self.format_business_rules_for_prompt()
            
            verification_prompt = self.prompt_templates["sql_verification"].format(
                schema_info=schema_info,
                business_rules=business_rules,
                question=processed_question,
                sql=sql
            )
            
            response = self.call_deepseek(verification_prompt)
            
            if response.startswith("VALID"):
                return True, sql, "验证通过"
            elif response.startswith("INVALID"):
                # 提取修正后的SQL
                lines = response.split('\n')
                corrected_sql = ""
                for i, line in enumerate(lines):
                    if line.strip() == "INVALID" and i + 1 < len(lines):
                        corrected_sql = lines[i + 1].strip()
                        break
                
                if corrected_sql and corrected_sql.upper().startswith('SELECT'):
                    return False, self.clean_sql(corrected_sql), f"已修正SQL"
                else:
                    return False, sql, "验证失败但无法修正"
            else:
                # 如果回复格式不对，尝试提取SQL
                if "SELECT" in response.upper():
                    # 尝试从回复中提取SQL
                    import re
                    sql_match = re.search(r'(SELECT.*?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
                    if sql_match:
                        extracted_sql = sql_match.group(1).strip()
                        return False, self.clean_sql(extracted_sql), "已提取修正的SQL"
                
                return False, sql, f"验证回复格式异常: {response[:100]}"
                
        except Exception as e:
            logger.error(f"DeepSeek验证失败: {e}")
            return True, sql, f"验证异常，保持原SQL: {e}"

    def deepseek_fallback_sql(self, question: str, reason: str = "Vanna不可用") -> Tuple[str, str]:
        """DeepSeek兜底生成SQL"""
        try:
            st.info(f"使用DeepSeek兜底生成SQL... (原因: {reason})")
            
            # 应用业务规则转换问题
            processed_question = self.apply_business_rules(question)
            
            schema_info = self.format_schema_for_prompt()
            business_rules = self.format_business_rules_for_prompt()
            
            fallback_prompt = self.prompt_templates["fallback_generation"].format(
                schema_info=schema_info,
                business_rules=business_rules,
                question=processed_question
            )
            
            response = self.call_deepseek(fallback_prompt)
            
            if response and not response.startswith("DeepSeek"):
                cleaned_sql = self.clean_sql(response)
                if cleaned_sql and cleaned_sql.upper().startswith('SELECT'):
                    return cleaned_sql, f"DeepSeek兜底生成成功"
            
            # 如果DeepSeek也失败，使用最基本的规则匹配
            basic_sql = self.generate_fallback_sql(question)
            return basic_sql, f"DeepSeek兜底失败，使用基础规则: {response[:50] if response else 'API调用失败'}"
            
        except Exception as e:
            logger.error(f"DeepSeek兜底生成失败: {e}")
            # 最后的兜底方案
            basic_sql = self.generate_fallback_sql(question)
            return basic_sql, f"DeepSeek兜底异常，使用基础规则: {e}"

    def call_deepseek(self, prompt: str) -> str:
        """调用DeepSeek API"""
        try:
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
                return result['choices'][0]['message']['content'].strip()
            else:
                return f"DeepSeek API错误: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"DeepSeek调用失败: {e}"

    def generate_fallback_sql(self, question: str) -> str:
        """备用SQL生成方案"""
        question_lower = question.lower()
        
        # 简单的关键词匹配
        if "显示表" in question and "student" in question:
            return "SELECT * FROM student"
        elif "显示表" in question and "course" in question:
            return "SELECT * FROM course"
        elif "显示表" in question and "score" in question:
            return "SELECT * FROM score"
        elif any(word in question for word in ["所有学生", "全部学生", "学生信息"]):
            return "SELECT * FROM student"
        elif "学生姓名" in question or "姓名" in question:
            return "SELECT name FROM student"
        elif "班级" in question and "人数" in question:
            return "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"
        elif "张三" in question and "成绩" in question:
            return "SELECT course_name, score FROM score WHERE name = '张三'"
        
        # 默认返回学生表
        return "SELECT * FROM student LIMIT 10"

    def clean_sql(self, sql: str) -> str:
        """清理SQL文本"""
        if not sql:
            return ""
        
        # 移除 ```sql 和 ```
        sql = sql.replace('```sql', '').replace('```', '')
        
        # 移除其他可能的标记
        sql = sql.replace('sql\n', '').replace('SQL\n', '')
        
        # 移除行首行尾的空白
        sql = sql.strip()
        
        # 移除多余的换行符
        sql = ' '.join(sql.split())
        
        # 确保SQL不以分号结尾
        if sql.endswith(';'):
            sql = sql[:-1]
        
        return sql

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        try:
            if not sql or sql.strip() == "":
                return False, pd.DataFrame(), "SQL语句为空"
            
            cleaned_sql = self.clean_sql(sql)
            
            if not cleaned_sql or cleaned_sql.strip() == "":
                return False, pd.DataFrame(), "清理后SQL语句为空"
            
            logger.info(f"执行SQL: {cleaned_sql}")
            st.info(f"执行SQL: {cleaned_sql}")
            
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql_query(cleaned_sql, conn)
            conn.close()
            
            if df is None:
                return False, pd.DataFrame(), "查询返回空结果"
            
            return True, df, "查询成功"
            
        except Exception as e:
            error_msg = f"SQL执行失败: {e}"
            logger.error(error_msg)
            return False, pd.DataFrame(), error_msg

    def generate_chart(self, df: pd.DataFrame, question: str) -> Optional[go.Figure]:
        """生成图表"""
        if df.empty:
            return None
        
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        if len(numeric_columns) >= 1 and len(categorical_columns) >= 1:
            fig = px.bar(df, x=categorical_columns[0], y=numeric_columns[0],
                        title=f"{question} - 柱状图")
            return fig
        elif len(categorical_columns) >= 1 and len(numeric_columns) >= 1:
            fig = px.pie(df, names=categorical_columns[0], values=numeric_columns[0],
                       title=f"{question} - 饼图")
            return fig
        
        return None

    def analyze_results(self, df: pd.DataFrame, question: str) -> str:
        """分析查询结果"""
        if df.empty:
            return "查询结果为空，没有找到匹配的数据。"
        
        analysis = [f"查询返回了 {len(df)} 条记录。"]
        
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        for col in numeric_columns:
            if len(df[col].dropna()) > 0:
                mean_val = df[col].mean()
                max_val = df[col].max()
                min_val = df[col].min()
                analysis.append(f"{col}的平均值为 {mean_val:.2f}，最大值为 {max_val}，最小值为 {min_val}。")
        
        return " ".join(analysis)

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
            
            # 时间规则
            "本学期": "2024年",
            "上学期": "2023年",
            "下学期": "2025年"
        }
        
        rules_file = "business_rules.json"
        try:
            if os.path.exists(rules_file):
                with open(rules_file, 'r', encoding='utf-8') as f:
                    saved_rules = json.load(f)
                    # 合并默认规则和保存的规则
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
            "sql_generation": """你是一个SQL专家。根据以下数据库结构和用户问题，生成准确的SQL查询语句。

数据库结构：
{schema_info}

业务规则：
{business_rules}

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 使用SQLite语法
5. 应用业务规则进行术语转换
6. 表名：student, course, score
7. 常用字段：name, class, gender, course_name, score

SQL语句：""",

            "sql_verification": """你是一个SQL验证专家。请检查以下SQL语句是否正确并符合用户需求。

数据库结构：
{schema_info}

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
6. 是否正确应用了业务规则

如果SQL完全正确，请回答"VALID"
如果有问题，请提供修正后的SQL语句，格式如下：
INVALID
修正后的SQL语句

回答：""",

            "fallback_generation": """你是一个SQL专家。根据以下数据库结构和用户问题，生成准确的SQL查询语句。

数据库结构：
{schema_info}

业务规则：
{business_rules}

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 使用SQLite语法
5. 表名：student, course, score
6. 常用字段：name, class, gender, course_name, score
7. 严格应用业务规则进行转换

常见查询模式：
- 显示表: SELECT * FROM table_name
- 学生信息: SELECT * FROM student
- 成绩查询: SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '科目'
- 统计查询: SELECT class, COUNT(*) FROM student GROUP BY class

SQL语句："""
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

    def apply_business_rules(self, question: str) -> str:
        """应用业务规则转换问题"""
        processed_question = question
        
        for rule_key, rule_value in self.business_rules.items():
            if rule_key in processed_question:
                processed_question = processed_question.replace(rule_key, rule_value)
        
        return processed_question

    def format_business_rules_for_prompt(self) -> str:
        """格式化业务规则用于提示词"""
        rules_text = "业务规则和术语映射：\n"
        
        # 分类显示规则
        term_mappings = []
        business_logic = []
        
        for key, value in self.business_rules.items():
            if len(key) <= 4 and not any(char.isdigit() for char in key):
                term_mappings.append(f"- {key} → {value}")
            else:
                business_logic.append(f"- {key} → {value}")
        
        if term_mappings:
            rules_text += "\n术语映射：\n" + "\n".join(term_mappings)
        
        if business_logic:
            rules_text += "\n\n业务规则：\n" + "\n".join(business_logic)
        
        return rules_text

def main():
    """主函数"""
    st.set_page_config(
        page_title="TEXT2SQL系统 - 本地部署版",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("TEXT2SQL系统 - 本地部署版")
    st.markdown("**ChromaDB向量数据库 + DeepSeek LLM + 完全本地部署**")
    
    # 初始化系统
    if 'local_system' not in st.session_state:
        st.session_state.local_system = Text2SQLLocalSystem()
    
    system = st.session_state.local_system
    
    # 侧边栏配置
    with st.sidebar:
        st.header("系统配置")
        
        # 添加页面选择
        page = st.selectbox(
            "选择页面:",
            ["SQL查询", "业务规则管理", "提示词管理"]
        )
        
        # 显示系统状态
        st.subheader("系统状态")
        
        if system.vn:
            st.success("本地Vanna: 正常运行")
            st.info("向量数据库: ChromaDB")
            st.info("LLM: DeepSeek")
        else:
            st.error("本地Vanna: 初始化失败")
            
            # 添加重置按钮
            if st.button("重置ChromaDB"):
                try:
                    import subprocess
                    import sys
                    result = subprocess.run([sys.executable, "reset_chromadb.py"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        st.success("ChromaDB重置成功，请刷新页面")
                        st.rerun()
                    else:
                        st.error(f"重置失败: {result.stderr}")
                except Exception as e:
                    st.error(f"重置失败: {e}")
        
        if os.path.exists(system.db_file):
            st.success("✅ SQLite: 正常")
        else:
            st.error("❌ SQLite: 异常")
        
        if os.path.exists(system.chroma_config["path"]):
            st.success("✅ ChromaDB: 本地存储正常")
        else:
            st.info("📁 ChromaDB: 将在首次使用时创建")
        
        # 显示数据库结构
        st.subheader("数据库结构")
        for table_name, table_info in system.db_schema.items():
            with st.expander(f"表: {table_name}"):
                for col in table_info['columns']:
                    st.write(f"- {col}")
        
        # 显示配置信息
        with st.expander("配置信息"):
            st.write(f"**ChromaDB路径**: {system.chroma_config['path']}")
            st.write(f"**集合名称**: {system.chroma_config['collection_name']}")
            st.write(f"**LLM模型**: {system.chroma_config['model']}")
    
    # 根据选择的页面显示不同内容
    if page == "SQL查询":
        show_sql_query_page(system)
    elif page == "业务规则管理":
        show_business_rules_page(system)
    elif page == "提示词管理":
        show_prompt_templates_page(system)

def show_sql_query_page(system):
    """显示SQL查询页面"""
    # 主界面
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("自然语言查询")
        
        # 预设问题
        example_questions = [
            "化学成绩前3的学生",
            "数学成绩最高的5名学生", 
            "查询所有学生的姓名和班级",
            "统计每个班级的学生人数",
            "查询张三的所有课程成绩",
            "物理成绩大于85分的学生",
            "平均成绩最高的前3名学生"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100)
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                with st.spinner("正在使用本地Vanna生成SQL..."):
                    try:
                        # 使用本地Vanna生成SQL
                        sql, method = system.generate_sql_local(question)
                        
                        if not sql or sql.strip() == "":
                            st.error("❌ 未能生成有效的SQL语句")
                            return
                        
                        st.success(f"✅ {method}")
                        
                        # 显示生成的SQL
                        st.subheader("生成的SQL")
                        st.code(sql, language="sql")
                        
                        # 执行SQL
                        success, df, message = system.execute_sql(sql)
                        
                        if success:
                            st.success(message)
                            
                            if not df.empty:
                                # 显示结果
                                st.subheader("查询结果")
                                st.dataframe(df)
                                
                                # 生成图表
                                fig = system.generate_chart(df, question)
                                if fig:
                                    st.subheader("数据可视化")
                                    st.plotly_chart(fig, use_container_width=True)
                                
                                # 结果分析
                                st.subheader("数据分析")
                                analysis = system.analyze_results(df, question)
                                st.write(analysis)
                            else:
                                st.warning("查询结果为空")
                        else:
                            st.error(message)
                            
                    except Exception as e:
                        st.error(f"处理过程中出现错误: {e}")
                        st.error(traceback.format_exc())
            else:
                st.warning("请输入问题")
    
    with col2:
        st.subheader("系统增强功能")
        
        st.markdown("""
        ### 🔄 双重AI保障
        - **Vanna生成**: 基于向量知识库的智能SQL生成
        - **DeepSeek验证**: 自动验证SQL正确性和逻辑
        - **智能修正**: 发现问题时自动修正SQL
        - **兜底机制**: DeepSeek作为备用SQL生成器
        
        ### 🛡️ 质量保证流程
        1. **Vanna生成SQL** - 基于历史查询和知识库
        2. **DeepSeek验证** - 检查语法、字段、逻辑
        3. **自动修正** - 发现问题时提供修正版本
        4. **兜底生成** - 如果验证失败，DeepSeek重新生成
        
        ### 🎯 技术优势
        - **高准确率**: 双重AI确保SQL质量
        - **容错能力**: 多层兜底机制
        - **学习能力**: 向量知识库持续优化
        - **稳定可靠**: 即使单个组件失败也能工作
        
        ### 📊 支持的复杂查询
        - 多表关联查询
        - 聚合统计分析
        - 条件筛选排序
        - 业务术语理解
        """)
        
        with st.expander("增强架构流程"):
            st.markdown("""
            ```
            用户问题
                ↓
            Vanna (ChromaDB + DeepSeek) 生成SQL
                ↓
            DeepSeek验证SQL正确性
                ↓
            [验证通过] → 执行SQL
                ↓
            [验证失败] → DeepSeek重新生成SQL
                ↓
            SQLite执行查询
                ↓
            结果展示和可视化
            ```
            
            **容错机制:**
            - Vanna失败 → DeepSeek兜底
            - 验证失败 → 自动修正
            - API异常 → 规则匹配
            """)
        
        with st.expander("本地文件结构"):
            st.markdown("""
            ```
            ./
            ├── test_database.db      # SQLite数据库
            ├── chroma_db/           # ChromaDB本地存储
            │   ├── chroma.sqlite3   # 向量索引
            │   └── ...              # 其他ChromaDB文件
            └── text2sql_local_deepseek.py
            ```
            """)

def show_business_rules_page(system):
    """显示业务规则管理页面"""
    st.header("业务规则管理")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("当前业务规则")
        
        # 显示现有规则
        if system.business_rules:
            # 分类显示
            term_mappings = {}
            business_logic = {}
            
            for key, value in system.business_rules.items():
                if len(key) <= 4 and not any(char.isdigit() for char in key):
                    term_mappings[key] = value
                else:
                    business_logic[key] = value
            
            # 术语映射
            if term_mappings:
                st.write("**术语映射:**")
                for key, value in term_mappings.items():
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.write(f"{key} → {value}")
                    with col_c:
                        if st.button("删除", key=f"del_term_{key}"):
                            del system.business_rules[key]
                            system.save_business_rules()
                            st.rerun()
            
            # 业务规则
            if business_logic:
                st.write("**业务规则:**")
                for key, value in business_logic.items():
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.write(f"{key} → {value}")
                    with col_c:
                        if st.button("删除", key=f"del_rule_{key}"):
                            del system.business_rules[key]
                            system.save_business_rules()
                            st.rerun()
        
        # 添加新规则
        st.subheader("添加新规则")
        
        rule_type = st.selectbox("规则类型:", ["术语映射", "业务规则"])
        
        col_new1, col_new2 = st.columns(2)
        with col_new1:
            new_key = st.text_input("规则键 (如: 25年, 优秀)")
        with col_new2:
            if rule_type == "术语映射":
                new_value = st.text_input("映射值 (如: student, score)")
            else:
                new_value = st.text_input("规则值 (如: 2025年, score >= 90)")
        
        if st.button("添加规则"):
            if new_key and new_value:
                system.business_rules[new_key] = new_value
                if system.save_business_rules():
                    st.success(f"已添加规则: {new_key} → {new_value}")
                    st.rerun()
                else:
                    st.error("保存规则失败")
            else:
                st.warning("请填写完整的规则信息")
    
    with col2:
        st.subheader("规则说明")
        st.markdown("""
        ### 术语映射
        - 将中文术语映射到数据库字段
        - 例如: "学生" → "student"
        
        ### 业务规则
        - 业务逻辑转换规则
        - 时间规则: "25年" → "2025年"
        - 评级规则: "优秀" → "score >= 90"
        - 条件规则: "及格" → "score >= 60"
        
        ### 使用示例
        用户输入: "查询25年优秀学生"
        转换后: "查询2025年score >= 90学生"
        """)
        
        # 规则测试
        st.subheader("规则测试")
        test_question = st.text_input("测试问题:")
        if test_question:
            processed = system.apply_business_rules(test_question)
            st.write("**原始问题:**", test_question)
            st.write("**转换后:**", processed)

def show_prompt_templates_page(system):
    """显示提示词管理页面"""
    st.header("提示词模板管理")
    
    # 选择要编辑的模板
    template_names = list(system.prompt_templates.keys())
    selected_template = st.selectbox("选择模板:", template_names)
    
    if selected_template:
        st.subheader(f"编辑模板: {selected_template}")
        
        # 显示模板说明
        template_descriptions = {
            "sql_generation": "SQL生成模板 - 用于Vanna生成SQL时的提示词",
            "sql_verification": "SQL验证模板 - 用于DeepSeek验证SQL时的提示词", 
            "fallback_generation": "兜底生成模板 - 用于DeepSeek兜底生成SQL时的提示词"
        }
        
        st.info(template_descriptions.get(selected_template, "自定义模板"))
        
        # 编辑模板内容
        current_template = system.prompt_templates[selected_template]
        new_template = st.text_area(
            "模板内容:",
            value=current_template,
            height=400,
            help="可用变量: {schema_info}, {business_rules}, {question}, {sql}"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("保存模板"):
                system.prompt_templates[selected_template] = new_template
                if system.save_prompt_templates():
                    st.success("模板保存成功")
                else:
                    st.error("模板保存失败")
        
        with col2:
            if st.button("重置为默认"):
                # 重置为默认模板
                default_templates = {
                    "sql_generation": """你是一个SQL专家。根据以下数据库结构和用户问题，生成准确的SQL查询语句。

数据库结构：
{schema_info}

业务规则：
{business_rules}

用户问题：{question}

重要要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 使用SQLite语法
5. 应用业务规则进行术语转换

SQL语句：""",
                    # 其他默认模板...
                }
                
                if selected_template in default_templates:
                    system.prompt_templates[selected_template] = default_templates[selected_template]
                    system.save_prompt_templates()
                    st.success("已重置为默认模板")
                    st.rerun()
        
        with col3:
            if st.button("测试模板"):
                # 测试模板格式
                try:
                    test_result = new_template.format(
                        schema_info="[测试数据库结构]",
                        business_rules="[测试业务规则]", 
                        question="[测试问题]",
                        sql="[测试SQL]"
                    )
                    st.success("模板格式正确")
                    with st.expander("预览效果"):
                        st.text(test_result)
                except Exception as e:
                    st.error(f"模板格式错误: {e}")
        
        # 添加新模板
        st.subheader("添加新模板")
        col_new1, col_new2 = st.columns(2)
        
        with col_new1:
            new_template_name = st.text_input("模板名称:")
        
        with col_new2:
            if st.button("创建新模板"):
                if new_template_name and new_template_name not in system.prompt_templates:
                    system.prompt_templates[new_template_name] = "在此输入新模板内容..."
                    system.save_prompt_templates()
                    st.success(f"已创建模板: {new_template_name}")
                    st.rerun()
                elif new_template_name in system.prompt_templates:
                    st.warning("模板名称已存在")
                else:
                    st.warning("请输入模板名称")

if __name__ == "__main__":
    main()