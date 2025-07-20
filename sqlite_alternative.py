#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 - SQLite版本 (无需MySQL)
"""

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from vanna.remote import VannaDefault
import json
import re
from typing import Dict, List, Tuple, Optional
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2SQLSystemSQLite:
    def __init__(self):
        """初始化TEXT2SQL系统 - SQLite版本"""
        self.vanna_api_key = "35d688e1655847838c9d0e318168d4f0"
        self.vanna_model = "chinook"
        self.deepseek_api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        
        # SQLite数据库文件
        self.db_file = "test_database.db"
        
        # 初始化Vanna
        self.vn = None
        self.initialize_vanna()
        
        # 初始化数据库
        self.initialize_database()
        
        # 业务规则和术语映射
        self.business_rules = {
            "学生": ["student", "学生信息", "学生名册"],
            "课程": ["course", "课程信息", "科目"],
            "成绩": ["score", "分数", "成绩表"],
            "姓名": ["name", "学生姓名"],
            "性别": ["gender", "男女"],
            "班级": ["class", "班级信息"],
            "课程名称": ["course_name", "科目名称"],
            "分数": ["score", "成绩", "得分"]
        }

    def initialize_vanna(self):
        """初始化Vanna连接"""
        try:
            self.vn = VannaDefault(model=self.vanna_model, api_key=self.vanna_api_key)
            logger.info("Vanna初始化成功")
        except Exception as e:
            logger.error(f"Vanna初始化失败: {e}")
            st.error(f"Vanna初始化失败: {e}")

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

    def get_table_schema(self) -> Dict:
        """获取数据库表结构"""
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
            
            conn.close()
            return schema
            
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            return {}

    def preprocess_question(self, question: str) -> str:
        """预处理用户问题，应用业务规则映射"""
        processed_question = question
        
        for chinese_term, english_terms in self.business_rules.items():
            if chinese_term in processed_question:
                processed_question = processed_question.replace(chinese_term, english_terms[0])
        
        return processed_question

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        try:
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql_query(sql, conn)
            conn.close()
            return True, df, "查询成功"
        except Exception as e:
            error_msg = f"SQL执行失败: {e}"
            logger.error(error_msg)
            return False, pd.DataFrame(), error_msg

    def generate_chart(self, df: pd.DataFrame, question: str) -> Optional[go.Figure]:
        """根据数据和问题自动生成图表"""
        if df.empty:
            return None
        
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        if len(numeric_columns) >= 1 and len(categorical_columns) >= 1:
            fig = px.bar(df, x=categorical_columns[0], y=numeric_columns[0],
                        title=f"{question} - 柱状图")
            return fig
        elif len(numeric_columns) >= 2:
            fig = px.scatter(df, x=numeric_columns[0], y=numeric_columns[1],
                           title=f"{question} - 散点图")
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
        
        analysis = []
        analysis.append(f"查询返回了 {len(df)} 条记录。")
        
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        for col in numeric_columns:
            mean_val = df[col].mean()
            max_val = df[col].max()
            min_val = df[col].min()
            analysis.append(f"{col}的平均值为 {mean_val:.2f}，最大值为 {max_val}，最小值为 {min_val}。")
        
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        for col in categorical_columns:
            unique_count = df[col].nunique()
            most_common = df[col].mode().iloc[0] if not df[col].mode().empty else "无"
            analysis.append(f"{col}有 {unique_count} 个不同的值，最常见的是 '{most_common}'。")
        
        return " ".join(analysis)

def main():
    """主函数 - Streamlit应用"""
    st.set_page_config(
        page_title="TEXT2SQL分析系统 (SQLite版)",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 TEXT2SQL分析系统 (SQLite版)")
    st.markdown("基于AI的自然语言转SQL查询分析平台 - 无需MySQL安装")
    
    # 初始化系统
    if 'system' not in st.session_state:
        st.session_state.system = Text2SQLSystemSQLite()
    
    system = st.session_state.system
    
    # 侧边栏配置
    with st.sidebar:
        st.header("系统配置")
        
        # 数据库状态
        if os.path.exists(system.db_file):
            st.success(f"✅ SQLite数据库已就绪: {system.db_file}")
        else:
            st.error("❌ 数据库文件不存在")
        
        # 显示表结构
        st.subheader("数据库表结构")
        schema = system.get_table_schema()
        for table_name, table_info in schema.items():
            with st.expander(f"表: {table_name}"):
                st.write("字段列表:")
                for col in table_info['columns']:
                    st.write(f"- {col}")
    
    # 主界面
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("自然语言查询")
        
        # 预设问题示例
        example_questions = [
            "查询所有学生的姓名和班级",
            "显示数学成绩大于90分的学生",
            "统计每个班级的学生人数",
            "查询张三的所有课程成绩",
            "显示平均成绩最高的前3名学生"
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = selected_example
        else:
            question = st.text_area("请输入您的问题:", height=100, 
                                  placeholder="例如：查询所有学生的平均成绩")
        
        if st.button("生成SQL查询", type="primary"):
            if question:
                with st.spinner("正在生成SQL..."):
                    try:
                        # 预处理问题
                        processed_question = system.preprocess_question(question)
                        st.info(f"处理后的问题: {processed_question}")
                        
                        # 生成SQL
                        if system.vn:
                            sql = system.vn.generate_sql(question=processed_question)
                            st.code(sql, language="sql")
                            
                            # 执行SQL
                            success, df, message = system.execute_sql(sql)
                            
                            if success:
                                st.success(message)
                                
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
                                st.error(message)
                        else:
                            st.error("Vanna AI未初始化")
                            
                    except Exception as e:
                        st.error(f"处理过程中出现错误: {e}")
            else:
                st.warning("请输入问题")
    
    with col2:
        st.subheader("系统信息")
        
        # 显示业务规则
        with st.expander("业务术语映射"):
            for chinese, english in system.business_rules.items():
                st.write(f"**{chinese}**: {', '.join(english)}")
        
        # 使用说明
        with st.expander("使用说明"):
            st.markdown("""
            ### SQLite版本优势
            - ✅ 无需安装MySQL
            - ✅ 数据库文件自动创建
            - ✅ 包含完整测试数据
            - ✅ 所有功能正常工作
            
            ### 使用步骤
            1. 在左侧输入自然语言问题
            2. 系统会自动生成SQL查询
            3. 执行查询并显示结果
            4. 自动生成数据可视化图表
            5. 提供数据分析结果
            """)

if __name__ == "__main__":
    main()