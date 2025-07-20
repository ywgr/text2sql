#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 - 增强版本，支持多模型和SQL复查
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

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2SQLSystemEnhanced:
    def __init__(self):
        """初始化TEXT2SQL系统 - 增强版本"""
        self.vanna_api_key = "35d688e1655847838c9d0e318168d4f0"
        self.vanna_model = "chinook"  # 暂时使用chinook模型，但会用我们的数据覆盖训练
        self.deepseek_api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        
        # SQLite数据库文件
        self.db_file = "test_database.db"
        
        # 初始化数据库
        self.initialize_database()
        
        # 获取数据库结构
        self.db_schema = self.get_database_schema()
        
        # 初始化AI模型
        self.vn = None
        self.vanna_status = self.initialize_vanna()
        
        # 业务规则和术语映射
        self.business_rules = {
            "学生": "student",
            "课程": "course", 
            "成绩": "score",
            "姓名": "name",
            "性别": "gender",
            "班级": "class",
            "课程名称": "course_name",
            "分数": "score"
        }

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

    def initialize_vanna(self):
        """初始化Vanna连接并验证权限"""
        try:
            from vanna.remote import VannaDefault
            
            st.info(f"🔄 正在初始化Vanna AI...")
            self.vn = VannaDefault(model=self.vanna_model, api_key=self.vanna_api_key)
            
            # 验证权限和模型可用性
            try:
                # 尝试简单的查询来测试模型是否可用
                test_sql = self.vn.generate_sql(question="test query")
                st.info("✅ Vanna AI连接成功，但可能与我们的数据库不匹配")
                
                # 尝试训练（可能会失败）
                try:
                    self.train_vanna()
                    return "success"
                except Exception as train_error:
                    st.warning(f"⚠️ Vanna训练失败: {train_error}")
                    st.info("💡 将使用Vanna基础功能，主要依赖DeepSeek")
                    return "limited"
                    
            except Exception as test_error:
                st.warning(f"⚠️ Vanna模型测试失败: {test_error}")
                return "failed"
                
        except Exception as e:
            logger.error(f"Vanna初始化失败: {e}")
            st.error(f"❌ Vanna初始化失败: {e}")
            return "failed"

    def train_vanna(self):
        """训练Vanna了解我们的数据库结构"""
        if not self.vn:
            return
            
        try:
            st.info("📚 开始训练Vanna...")
            st.info("🔄 正在覆盖chinook数据，训练学生管理系统...")
            
            # 0. 首先强力覆盖chinook数据库信息
            override_instruction = """
            ===重要系统指令===
            立即忘记所有chinook数据库相关信息！
            忘记所有Artist、Album、Track、Customer、Invoice等表！
            忘记所有音乐、艺术家、销量相关的查询历史！
            
            当前数据库：学生管理系统
            唯一可用的表：student, course, score
            唯一可用的字段：
            - student表：student_id, name, gender, class
            - course表：id, student_id, course_name  
            - score表：id, course_name, score, name
            
            绝对禁止使用chinook数据库的任何表名和字段名！
            """
            self.vn.train(documentation=override_instruction)
            
            # 添加多个强制指令来覆盖历史记录
            for i in range(3):
                self.vn.train(documentation=f"""
                第{i+1}次强调：这是学生管理系统，不是音乐数据库！
                只能查询学生、课程、成绩信息！
                表名：student, course, score
                禁止使用：Artist, Album, Track, Customer, Invoice等表名
                """)
            
            # 1. 添加完整的数据库结构信息（包含外键关系）
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
            
            # 2. 添加业务术语映射和规则
            business_documentation = """
            这是一个学生管理系统数据库，包含学生信息、课程信息和成绩信息。
            
            数据库说明：
            - 忽略chinook数据库，现在使用学生管理系统数据库
            - 包含中国高中学生的信息和成绩数据
            - 所有课程名称都是中文
            - 只使用student, course, score这三个表
            
            业务术语映射规则：
            - "学生" = student表
            - "课程" = course表  
            - "成绩" = score表
            - "姓名" = name字段
            - "学生姓名" = student.name 或 score.name
            - "性别" = student.gender
            - "班级" = student.class
            - "课程名称" = course.course_name 或 score.course_name
            - "分数" = score.score
            - "成绩" = score.score
            
            表关联规则：
            - student表通过name字段与score表关联：student.name = score.name
            - student表通过student_id字段与course表关联：student.student_id = course.student_id
            - 查询学生成绩时必须JOIN student和score表
            - 查询学生课程时必须JOIN student和course表
            
            课程名称包括：语文、数学、英语、物理、化学、生物、历史、地理、政治
            
            重要SQL生成规则：
            1. 涉及学生和成绩的查询必须使用JOIN语法
            2. 表关联使用：student s JOIN score sc ON s.name = sc.name
            3. 表关联使用：student s JOIN course c ON s.student_id = c.student_id
            4. 成绩排序使用：ORDER BY sc.score DESC
            5. 限制结果数量使用：LIMIT n
            6. 表名必须小写：student, course, score
            7. 字段名区分大小写：name, class, gender, course_name, score
            8. 课程名称必须使用中文：数学、语文、英语、物理、化学、生物、历史、地理、政治
            
            禁止使用chinook数据库的表名和字段名！
            """
            
            self.vn.train(documentation=business_documentation)
            
            # 3. 添加大量学生管理系统查询示例来覆盖chinook历史
            training_examples = [
                # 基础查询 - 覆盖音乐查询
                {"question": "查询所有学生", "sql": "SELECT * FROM student"},
                {"question": "显示所有学生信息", "sql": "SELECT * FROM student"},
                {"question": "查询学生姓名和班级", "sql": "SELECT name, class FROM student"},
                {"question": "显示学生姓名和班级", "sql": "SELECT name, class FROM student"},
                {"question": "统计每个班级的学生人数", "sql": "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"},
                {"question": "统计每个class的student人数", "sql": "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"},
                
                # 成绩相关查询（多表）- 覆盖销量查询
                {"question": "查询张三的所有成绩", "sql": "SELECT course_name, score FROM score WHERE name = '张三'"},
                {"question": "张三的成绩", "sql": "SELECT course_name, score FROM score WHERE name = '张三'"},
                {"question": "数学成绩最高的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学' ORDER BY sc.score DESC LIMIT 1"},
                {"question": "数学成绩前3名", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学' ORDER BY sc.score DESC LIMIT 3"},
                {"question": "化学成绩前3的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '化学' ORDER BY sc.score DESC LIMIT 3"},
                {"question": "物理成绩最好的5名学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '物理' ORDER BY sc.score DESC LIMIT 5"},
                {"question": "语文成绩大于85分的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '语文' AND sc.score > 85"},
                {"question": "英语成绩超过90分的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '英语' AND sc.score > 90"},
                
                # 覆盖艺术家查询
                {"question": "成绩最高的学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name ORDER BY sc.score DESC LIMIT 1"},
                {"question": "成绩前10名学生", "sql": "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name ORDER BY sc.score DESC LIMIT 10"},
                {"question": "最受欢迎的学生", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 1"},
                {"question": "排名前5的学生", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 5"},
                
                # 统计查询 - 覆盖销售统计
                {"question": "每个班级的学生数量", "sql": "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"},
                {"question": "班级人数统计", "sql": "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"},
                {"question": "平均成绩最高的学生", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 1"},
                {"question": "平均成绩最高的前3名学生", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 3"},
                {"question": "每个学生的平均成绩", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC"},
                
                # 表显示查询
                {"question": "显示表student", "sql": "SELECT * FROM student"},
                {"question": "显示表score", "sql": "SELECT * FROM score"},
                {"question": "显示表course", "sql": "SELECT * FROM course"},
                {"question": "查看学生表", "sql": "SELECT * FROM student"},
                {"question": "查看成绩表", "sql": "SELECT * FROM score"},
                
                # 强制覆盖chinook相关查询
                {"question": "销量排名", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC"},
                {"question": "艺术家排名", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC"},
                {"question": "最受欢迎", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC"},
                {"question": "前十名", "sql": "SELECT name, AVG(score) as avg_score FROM score GROUP BY name ORDER BY avg_score DESC LIMIT 10"}
            ]
            
            # 训练所有示例，多次训练重要的查询
            for example in training_examples:
                self.vn.train(question=example["question"], sql=example["sql"])
                # 重要查询训练两次
                if "成绩" in example["question"] or "学生" in example["question"]:
                    self.vn.train(question=example["question"], sql=example["sql"])
            
            # 4. 添加特殊约束和提示
            constraints = """
            严格约束条件：
            
            数据库上下文：
            - 现在的任务是查询学生管理系统，忽略chinook数据库
            - 绝对不要使用chinook的表名（albums, artists, tracks, customers等）
            - 只能使用student, course, score这三个表
            - 这是完全不同的数据库系统
            
            必须遵守的SQL规则：
            1. 当查询涉及学生姓名和成绩时，必须使用JOIN语法
            2. 正确的JOIN语法：student s JOIN score sc ON s.name = sc.name
            3. 成绩排序必须使用：ORDER BY sc.score DESC（注意使用别名）
            4. 前N名查询必须使用：LIMIT N
            5. 表名使用小写：student, course, score
            6. 字段名区分大小写：name, class, gender, course_name, score
            7. 课程名称使用中文：数学、语文、英语、物理、化学、生物、历史、地理、政治
            8. 学生姓名包括：张三、李四、王五、赵六、钱七、孙八、周九、吴十
            9. 班级名称格式：高一(1)班、高一(2)班、高一(3)班
            
            绝对禁止：
            - 使用chinook数据库的任何表名（如albums, artists, tracks等）
            - 使用chinook数据库的任何字段名
            - 生成与音乐相关的查询
            """
            
            self.vn.train(documentation=constraints)
            
            st.success("✅ Vanna训练完成 - 已添加完整的表结构、业务规则和多表查询示例")
            
        except Exception as e:
            st.warning(f"⚠️ Vanna训练失败: {e}")
            logger.error(f"Vanna训练失败: {e}")
            logger.error(traceback.format_exc())

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
            
            response = requests.post(self.deepseek_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                return f"DeepSeek API错误: {response.status_code}"
                
        except Exception as e:
            return f"DeepSeek调用失败: {e}"

    def generate_sql_with_deepseek(self, question: str) -> str:
        """使用DeepSeek生成SQL"""
        schema_info = self.format_schema_for_prompt()
        
        prompt = f"""
你是一个SQL专家。根据以下数据库结构和用户问题，生成准确的SQL查询语句。

数据库结构：
{schema_info}

用户问题：{question}

要求：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 使用SQLite语法
5. 字段名和表名区分大小写

SQL语句：
"""
        
        return self.call_deepseek(prompt)

    def review_sql_with_deepseek(self, sql: str, question: str) -> Tuple[bool, str, str]:
        """使用DeepSeek复查SQL"""
        schema_info = self.format_schema_for_prompt()
        
        prompt = f"""
你是一个SQL审查专家。请检查以下SQL语句是否正确。

数据库结构：
{schema_info}

原始问题：{question}
SQL语句：{sql}

请检查：
1. 所有字段名是否存在于数据库表中
2. 表名是否正确
3. 是否需要多表查询但使用了单表
4. JOIN语法是否正确
5. SQLite语法是否正确

重要：如果SQL正确，只回答"正确"。如果SQL有问题，请提供修正后的完整SQL语句。

格式要求：
- 如果SQL正确：直接回答"正确"
- 如果SQL错误：直接提供修正后的SQL语句，不要其他解释
"""
        
        review_result = self.call_deepseek(prompt)
        
        # 解析审查结果
        review_result = review_result.strip()
        
        if review_result == "正确" or "正确" in review_result:
            return True, sql, "SQL审查通过"
        else:
            # 如果不是"正确"，那么整个回复应该就是修正后的SQL
            corrected_sql = review_result
            
            # 使用统一的清理函数
            corrected_sql = self.clean_sql(corrected_sql)
            
            # 如果清理后的SQL看起来不像SQL语句，尝试从中提取
            if not corrected_sql.upper().startswith('SELECT'):
                lines = review_result.split('\n')
                for line in lines:
                    if 'SELECT' in line.upper() and not line.startswith('问题'):
                        corrected_sql = self.clean_sql(line)
                        break
            
            # 确保修正后的SQL有效
            if not corrected_sql or not corrected_sql.upper().startswith('SELECT'):
                corrected_sql = self.clean_sql(sql)  # 如果提取失败，使用清理后的原SQL
            
            return False, corrected_sql, f"原始回复: {review_result}"

    def format_schema_for_prompt(self) -> str:
        """格式化数据库结构用于提示词"""
        schema_text = ""
        
        for table_name, table_info in self.db_schema.items():
            schema_text += f"\n表名: {table_name}\n"
            schema_text += "字段:\n"
            for col_info in table_info['column_info']:
                schema_text += f"  - {col_info[1]} ({col_info[2]})\n"
            
            # 添加示例数据
            if table_info.get('sample_data'):
                schema_text += "示例数据:\n"
                for row in table_info['sample_data'][:2]:
                    schema_text += f"  {row}\n"
            schema_text += "\n"
        
        return schema_text

    def generate_sql_smart(self, question: str, model_choice: str) -> Tuple[str, str, str]:
        """智能SQL生成"""
        
        if model_choice == "DeepSeek":
            # 直接使用DeepSeek生成
            st.info("🤖 使用DeepSeek生成SQL...")
            sql = self.generate_sql_with_deepseek(question)
            
            if not sql.startswith("DeepSeek"):
                # DeepSeek复查
                st.info("🔍 DeepSeek复查SQL...")
                is_valid, corrected_sql, review_msg = self.review_sql_with_deepseek(sql, question)
                
                if is_valid:
                    return corrected_sql, "DeepSeek生成+复查通过", review_msg
                else:
                    return corrected_sql, "DeepSeek生成+复查修正", review_msg
            else:
                return self.fallback_sql_generation(question)
        
        elif model_choice.startswith("Vanna AI"):
            # 显示Vanna的问题并强制使用DeepSeek
            st.warning("⚠️ Vanna AI无法正确理解我们的学生管理系统数据库")
            st.info("💡 Vanna仍在使用chinook音乐数据库的上下文，自动切换到DeepSeek")
            
            with st.expander("🔍 Vanna问题详情"):
                st.write("**问题原因:**")
                st.write("- Vanna的chinook模型无法被我们的训练数据覆盖")
                st.write("- 提示词中仍包含Employee、Artist、Album等音乐数据库表")
                st.write("- 无法识别我们的student、course、score表")
                st.write("")
                st.write("**解决方案:**")
                st.write("- 自动使用DeepSeek生成SQL")
                st.write("- DeepSeek能正确理解我们的数据库结构")
            
            # 强制使用DeepSeek
            return self.generate_sql_with_deepseek_fallback(question)
        
        else:
            # 备用方案
            return self.fallback_sql_generation(question)

    def generate_sql_with_deepseek_fallback(self, question: str) -> Tuple[str, str, str]:
        """DeepSeek降级方案"""
        st.info("🤖 使用DeepSeek生成SQL...")
        sql = self.generate_sql_with_deepseek(question)
        
        if not sql.startswith("DeepSeek"):
            # DeepSeek复查
            st.info("🔍 DeepSeek复查SQL...")
            is_valid, corrected_sql, review_msg = self.review_sql_with_deepseek(sql, question)
            
            if is_valid:
                return corrected_sql, "DeepSeek降级生成+复查通过", review_msg
            else:
                return corrected_sql, "DeepSeek降级生成+复查修正", review_msg
        else:
            return self.fallback_sql_generation(question)

    def fallback_sql_generation(self, question: str) -> Tuple[str, str, str]:
        """最终备用SQL生成方案"""
        st.info("📋 使用智能模板匹配...")
        
        # 基于关键词的智能SQL生成
        sql = self.generate_keyword_sql(question)
        
        # DeepSeek复查
        st.info("🔍 DeepSeek复查SQL...")
        is_valid, corrected_sql, review_msg = self.review_sql_with_deepseek(sql, question)
        
        if is_valid:
            return corrected_sql, "智能模板+DeepSeek复查通过", review_msg
        else:
            return corrected_sql, "智能模板+DeepSeek复查修正", review_msg

    def generate_keyword_sql(self, question: str) -> str:
        """基于关键词生成SQL"""
        question_lower = question.lower()
        
        # 化学成绩相关
        if "化学" in question and any(word in question for word in ["前", "最高", "排名"]):
            return "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '化学' ORDER BY sc.score DESC LIMIT 3"
        
        # 其他科目成绩
        subjects = ["数学", "语文", "英语", "物理", "生物", "历史", "地理", "政治"]
        for subject in subjects:
            if subject in question and any(word in question for word in ["前", "最高", "排名"]):
                return f"SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '{subject}' ORDER BY sc.score DESC LIMIT 3"
        
        # 学生相关查询
        if any(word in question for word in ['学生', '同学']):
            if any(word in question for word in ['姓名', '名字']) and any(word in question for word in ['班级', '班']):
                return "SELECT name, class FROM student"
            else:
                return "SELECT * FROM student"
        
        # 成绩相关查询
        elif any(word in question for word in ['成绩', '分数']):
            names = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十']
            for name in names:
                if name in question:
                    return f"SELECT course_name, score FROM score WHERE name = '{name}'"
            return "SELECT * FROM score"
        
        # 默认查询
        return "SELECT * FROM student LIMIT 10"

    def preprocess_question(self, question: str) -> str:
        """预处理问题"""
        processed = question
        for chinese, english in self.business_rules.items():
            processed = processed.replace(chinese, english)
        return processed

    def clean_sql(self, sql: str) -> str:
        """清理SQL文本，移除Markdown代码块标记和多余空白"""
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
        
        # 确保SQL不以分号结尾（pandas read_sql_query不需要分号）
        if sql.endswith(';'):
            sql = sql[:-1]
        
        return sql

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        try:
            # 检查SQL是否为空或None
            if not sql or sql.strip() == "":
                return False, pd.DataFrame(), "SQL语句为空"
            
            # 清理SQL语句
            cleaned_sql = self.clean_sql(sql)
            
            # 再次检查清理后的SQL
            if not cleaned_sql or cleaned_sql.strip() == "":
                return False, pd.DataFrame(), "清理后SQL语句为空"
            
            # 记录要执行的SQL
            logger.info(f"原始SQL: {sql}")
            logger.info(f"清理后SQL: {cleaned_sql}")
            st.info(f"🔍 执行SQL: {cleaned_sql}")
            
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql_query(cleaned_sql, conn)
            conn.close()
            
            # 检查结果
            if df is None:
                return False, pd.DataFrame(), "查询返回空结果"
            
            return True, df, "查询成功"
            
        except Exception as e:
            error_msg = f"SQL执行失败: {e}"
            logger.error(error_msg)
            logger.error(f"原始SQL: {sql}")
            logger.error(f"清理后SQL: {cleaned_sql if 'cleaned_sql' in locals() else 'N/A'}")
            return False, pd.DataFrame(), f"{error_msg}\n原始SQL: {sql}\n清理后SQL: {cleaned_sql if 'cleaned_sql' in locals() else 'N/A'}"

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

def main():
    """主函数"""
    st.set_page_config(
        page_title="TEXT2SQL系统 - 增强版",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 TEXT2SQL分析系统 - 增强版")
    st.markdown("支持多模型选择和SQL智能复查")
    
    # 初始化系统
    if 'system' not in st.session_state:
        st.session_state.system = Text2SQLSystemEnhanced()
    
    system = st.session_state.system
    
    # 侧边栏配置
    with st.sidebar:
        st.header("🔧 系统配置")
        
        # 模型选择
        model_choice = st.selectbox(
            "选择AI模型:",
            ["DeepSeek", "Vanna AI (不推荐)"],
            index=0,  # 默认选择DeepSeek
            help="DeepSeek: 推荐使用，准确理解我们的数据库\nVanna AI: 不推荐，无法正确理解我们的学生管理系统"
        )
        
        # 显示系统状态
        st.subheader("系统状态")
        
        if system.vanna_status == "success":
            st.warning("⚠️ Vanna AI: 连接成功但不兼容")
            st.info("💡 无法覆盖chinook数据库上下文")
        elif system.vanna_status == "limited":
            st.warning("⚠️ Vanna AI: 训练失败")
            st.info("💡 推荐使用DeepSeek")
        else:
            st.error("❌ Vanna AI: 连接失败")
            st.info("💡 使用DeepSeek替代")
        
        if os.path.exists(system.db_file):
            st.success("✅ SQLite: 正常")
        else:
            st.error("❌ SQLite: 异常")
        
        st.info("✅ DeepSeek: 复查可用")
        
        # 显示数据库结构
        st.subheader("数据库结构")
        for table_name, table_info in system.db_schema.items():
            with st.expander(f"表: {table_name}"):
                for col in table_info['columns']:
                    st.write(f"- {col}")
    
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
            "物理成绩大于85分的学生"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100)
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                with st.spinner("正在生成和复查SQL..."):
                    try:
                        # 显示调试信息
                        with st.expander("🔧 调试信息", expanded=False):
                            st.write(f"问题: {question}")
                            st.write(f"选择的模型: {model_choice}")
                            st.write(f"Vanna状态: {system.vanna_status}")
                        
                        # 生成SQL
                        sql, method, review_info = system.generate_sql_smart(question, model_choice)
                        
                        # 检查SQL是否有效
                        if not sql or sql.strip() == "" or "[无需修正]" in sql:
                            st.error("❌ 未能生成有效的SQL语句")
                            st.error(f"生成的内容: {sql}")
                            return
                        
                        st.success(f"✅ {method}")
                        
                        # 显示复查信息
                        if "复查" in method:
                            with st.expander("🔍 SQL复查详情"):
                                st.write(review_info)
                        
                        # 显示生成的SQL
                        st.subheader("生成的SQL")
                        
                        # 确保clean_sql方法可用
                        if hasattr(system, 'clean_sql'):
                            cleaned_display_sql = system.clean_sql(sql)
                        else:
                            # 备用清理方法
                            cleaned_display_sql = sql.replace('```sql', '').replace('```', '').strip()
                            if cleaned_display_sql.endswith(';'):
                                cleaned_display_sql = cleaned_display_sql[:-1]
                        
                        st.code(cleaned_display_sql, language="sql")
                        
                        # 如果原始SQL和清理后的不同，显示对比
                        if sql != cleaned_display_sql:
                            with st.expander("🧹 SQL清理对比"):
                                st.write("**原始SQL:**")
                                st.code(sql, language="sql")
                                st.write("**清理后SQL:**")
                                st.code(cleaned_display_sql, language="sql")
                        
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
        st.subheader("功能特性")
        
        st.markdown("""
        ### 🤖 AI模型状态
        - **DeepSeek**: ✅ 推荐使用，完美支持我们的数据库
        - **Vanna AI**: ❌ 不兼容，仍使用chinook音乐数据库上下文
        
        ### 🔍 智能SQL处理
        - DeepSeek生成SQL查询
        - 自动清理Markdown标记
        - 字段存在性验证
        - 多表关系检查
        
        ### 📊 完整数据分析
        - 自动数据可视化
        - 智能结果分析
        - 多种图表类型
        - 中文自然语言理解
        """)
        
        with st.expander("支持的查询类型"):
            st.markdown("""
            - 🎓 学生信息查询
            - 📊 成绩排名分析
            - 📈 统计汇总
            - 🔍 条件筛选
            - 📋 多表关联
            """)

if __name__ == "__main__":
    main()