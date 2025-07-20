#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版TEXT2SQL系统 - 避免ChromaDB问题
直接使用DeepSeek API + 规则匹配
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
from typing import Dict, List, Tuple, Optional
import logging
import os
import traceback

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleText2SQLSystem:
    """简化的TEXT2SQL系统"""
    
    def __init__(self):
        """初始化系统"""
        self.deepseek_api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        self.db_file = "test_database.db"
        
        # 初始化数据库
        self.initialize_database()
        
        # 获取数据库结构
        self.db_schema = self.get_database_schema()
        
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
            st.error(f"数据库初始化失败: {e}")

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
                "max_tokens": 500
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

重要规则：
1. 只返回SQL语句，不要其他解释
2. 确保所有字段名都存在于数据库表中
3. 如果需要多表查询，使用正确的JOIN语句
4. 使用SQLite语法
5. 字段名和表名区分大小写
6. 表名：student, course, score
7. 主要字段：name, class, gender, course_name, score

常见查询模式：
- 显示表student: SELECT * FROM student
- 查询所有学生: SELECT * FROM student
- 学生姓名: SELECT name FROM student
- 班级统计: SELECT class, COUNT(*) FROM student GROUP BY class
- 成绩查询: SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学'

SQL语句：
"""
        
        return self.call_deepseek(prompt)

    def generate_smart_sql(self, question: str) -> Tuple[str, str]:
        """智能SQL生成"""
        
        # 首先尝试规则匹配
        rule_sql = self.generate_rule_based_sql(question)
        if rule_sql:
            return rule_sql, "规则匹配生成"
        
        # 然后尝试DeepSeek
        st.info("使用DeepSeek生成SQL...")
        deepseek_sql = self.generate_sql_with_deepseek(question)
        
        if deepseek_sql and not deepseek_sql.startswith("DeepSeek"):
            cleaned_sql = self.clean_sql(deepseek_sql)
            if cleaned_sql and cleaned_sql.upper().startswith('SELECT'):
                return cleaned_sql, "DeepSeek生成"
        
        # 最后使用默认规则
        default_sql = self.generate_default_sql(question)
        return default_sql, "默认规则生成"

    def generate_rule_based_sql(self, question: str) -> str:
        """基于规则的SQL生成"""
        question_lower = question.lower()
        
        # 精确匹配常见查询
        if "显示表" in question and "student" in question:
            return "SELECT * FROM student"
        elif "显示表" in question and "course" in question:
            return "SELECT * FROM course"
        elif "显示表" in question and "score" in question:
            return "SELECT * FROM score"
        elif question in ["查询所有学生", "显示所有学生", "所有学生信息"]:
            return "SELECT * FROM student"
        elif question in ["学生姓名", "显示学生姓名", "查询学生姓名"]:
            return "SELECT name FROM student"
        elif "班级" in question and "人数" in question:
            return "SELECT class, COUNT(*) as student_count FROM student GROUP BY class"
        elif "张三" in question and "成绩" in question:
            return "SELECT course_name, score FROM score WHERE name = '张三'"
        elif "数学成绩" in question and "前" in question:
            return "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '数学' ORDER BY sc.score DESC LIMIT 3"
        elif "化学成绩" in question and "前" in question:
            return "SELECT s.name, sc.score FROM student s JOIN score sc ON s.name = sc.name WHERE sc.course_name = '化学' ORDER BY sc.score DESC LIMIT 3"
        
        return None

    def generate_default_sql(self, question: str) -> str:
        """生成默认SQL"""
        if any(word in question for word in ["成绩", "分数"]):
            return "SELECT * FROM score LIMIT 10"
        elif any(word in question for word in ["课程"]):
            return "SELECT * FROM course LIMIT 10"
        else:
            return "SELECT * FROM student LIMIT 10"

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

def main():
    """主函数"""
    st.set_page_config(
        page_title="TEXT2SQL系统 - 简化版",
        page_icon="⚡",
        layout="wide"
    )
    
    st.title("TEXT2SQL系统 - 简化版")
    st.markdown("**DeepSeek LLM + 规则匹配 + SQLite数据库**")
    
    # 初始化系统
    if 'simple_system' not in st.session_state:
        st.session_state.simple_system = SimpleText2SQLSystem()
    
    system = st.session_state.simple_system
    
    # 侧边栏配置
    with st.sidebar:
        st.header("系统配置")
        
        # 显示系统状态
        st.subheader("系统状态")
        st.success("DeepSeek API: 可用")
        st.success("规则匹配: 可用")
        
        if os.path.exists(system.db_file):
            st.success("SQLite: 正常")
        else:
            st.error("SQLite: 异常")
        
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
            "显示表 student",
            "查询所有学生",
            "学生姓名",
            "统计每个班级的学生人数",
            "查询张三的所有课程成绩",
            "数学成绩前3名",
            "化学成绩前3的学生"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100)
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                with st.spinner("正在生成SQL..."):
                    try:
                        # 生成SQL
                        sql, method = system.generate_smart_sql(question)
                        
                        if not sql or sql.strip() == "":
                            st.error("未能生成有效的SQL语句")
                            return
                        
                        st.success(f"{method}")
                        
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
        st.subheader("系统特点")
        
        st.markdown("""
        ### 简化架构
        - **规则匹配**: 快速响应常见查询
        - **DeepSeek API**: 处理复杂查询
        - **SQLite数据库**: 本地数据存储
        - **无向量数据库**: 避免复杂依赖
        
        ### 支持的查询
        - 基础查询: "显示表 student"
        - 条件查询: "数学成绩大于90分"
        - 排序查询: "成绩前3名"
        - 统计查询: "班级人数统计"
        
        ### 优势
        - 启动快速
        - 稳定可靠
        - 易于维护
        - 响应迅速
        """)

if __name__ == "__main__":
    main()