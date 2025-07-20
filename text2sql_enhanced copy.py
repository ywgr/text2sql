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
        self.vanna_model = "chinook"
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
        """初始化Vanna连接"""
        try:
            from vanna.remote import VannaDefault
            self.vn = VannaDefault(model=self.vanna_model, api_key=self.vanna_api_key)
            return "success"
        except Exception as e:
            logger.error(f"Vanna初始化失败: {e}")
            return "failed"

    def call_deepseek(self, prompt: str) -> str:
        """调用DeepSeek API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.deepseek_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-coder",
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

如果SQL有问题，请提供修正后的SQL。

请按以下格式回答：
状态：[正确/错误]
问题：[如果有错误，描述问题]
修正SQL：[如果需要修正，提供正确的SQL]
"""
        
        review_result = self.call_deepseek(prompt)
        
        # 解析审查结果
        if "状态：正确" in review_result or "状态: 正确" in review_result:
            return True, sql, "SQL审查通过"
        else:
            # 提取修正后的SQL
            lines = review_result.split('\n')
            corrected_sql = sql  # 默认使用原SQL
            
            for line in lines:
                if line.startswith('修正SQL：') or line.startswith('修正SQL:'):
                    corrected_sql = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                    # 清理SQL语句
                    corrected_sql = corrected_sql.replace('```sql', '').replace('```', '').strip()
                    if corrected_sql.endswith(';'):
                        corrected_sql = corrected_sql[:-1]
                    break
                elif 'SELECT' in line.upper() and not line.startswith('问题'):
                    # 如果找到包含SELECT的行，可能是修正的SQL
                    corrected_sql = line.strip()
                    corrected_sql = corrected_sql.replace('```sql', '').replace('```', '').strip()
                    if corrected_sql.endswith(';'):
                        corrected_sql = corrected_sql[:-1]
                    break
            
            return False, corrected_sql, review_result

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
        
        elif model_choice == "Vanna AI" and self.vanna_status == "success":
            # 使用Vanna生成
            st.info("🤖 使用Vanna AI生成SQL...")
            try:
                processed_question = self.preprocess_question(question)
                sql = self.vn.generate_sql(question=processed_question)
                
                # 显示Vanna生成的原始SQL
                st.info(f"📝 Vanna原始SQL: {sql}")
                
                if sql and not sql.startswith("The provided context"):
                    # DeepSeek复查
                    st.info("🔍 DeepSeek复查SQL...")
                    is_valid, corrected_sql, review_msg = self.review_sql_with_deepseek(sql, question)
                    
                    if is_valid:
                        return corrected_sql, "Vanna AI生成+DeepSeek复查通过", f"原始SQL: {sql}\n复查结果: {review_msg}"
                    else:
                        return corrected_sql, "Vanna AI生成+DeepSeek复查修正", f"原始SQL: {sql}\n复查结果: {review_msg}"
                else:
                    return self.fallback_sql_generation(question)
            except Exception as e:
                st.warning(f"Vanna AI生成失败: {e}")
                return self.fallback_sql_generation(question)
        
        else:
            # 备用方案
            return self.fallback_sql_generation(question)

    def fallback_sql_generation(self, question: str) -> Tuple[str, str, str]:
        """备用SQL生成方案"""
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

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        try:
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql_query(sql, conn)
            conn.close()
            return True, df, "查询成功"
        except Exception as e:
            return False, pd.DataFrame(), f"SQL执行失败: {e}"

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
            ["DeepSeek", "Vanna AI"],
            help="DeepSeek: 更准确的SQL生成\nVanna AI: 专业的Text2SQL模型"
        )
        
        # 显示系统状态
        st.subheader("系统状态")
        
        if system.vanna_status == "success":
            st.success("✅ Vanna AI: 正常")
        else:
            st.error("❌ Vanna AI: 异常")
        
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
                        # 生成SQL
                        sql, method, review_info = system.generate_sql_smart(question, model_choice)
                        
                        st.success(f"✅ {method}")
                        
                        # 显示复查信息
                        if "复查" in method:
                            with st.expander("🔍 SQL复查详情"):
                                st.write(review_info)
                        
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
        st.subheader("功能特性")
        
        st.markdown("""
        ### 🤖 多模型支持
        - **DeepSeek**: 强大的中文理解
        - **Vanna AI**: 专业Text2SQL
        
        ### 🔍 智能复查
        - 字段存在性检查
        - 多表关系验证
        - SQL语法校正
        
        ### 📊 完整分析
        - 自动数据可视化
        - 智能结果分析
        - 多种图表类型
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