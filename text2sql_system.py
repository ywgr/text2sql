#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL分析系统 - 基于Vanna AI和DeepSeek的自然语言转SQL查询系统
"""

import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
import plotly.express as px
import plotly.graph_objects as go
from vanna.remote import VannaDefault
import json
import re
from typing import Dict, List, Tuple, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Text2SQLSystem:
    def __init__(self):
        """初始化TEXT2SQL系统"""
        self.vanna_api_key = "35d688e1655847838c9d0e318168d4f0"
        self.vanna_model = "chinook"
        self.deepseek_api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        
        # 数据库配置
        self.db_config = {
            'host': 'localhost',
            'database': 'TEST',
            'user': 'root',
            'password': '123'  # Updated with correct password
        }
        
        # 初始化Vanna
        self.vn = None
        self.connection = None
        self.initialize_vanna()
        
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
        
        # 表关系定义
        self.table_relationships = {
            "student": {
                "primary_key": "student_id",
                "foreign_keys": [],
                "related_tables": ["course"]
            },
            "course": {
                "primary_key": "id",
                "foreign_keys": [{"column": "student_id", "references": "student.student_id"}],
                "related_tables": ["student"]
            },
            "score": {
                "primary_key": "id",
                "foreign_keys": [],
                "related_tables": ["student", "course"]
            }
        }

    def initialize_vanna(self):
        """初始化Vanna连接"""
        try:
            self.vn = VannaDefault(model=self.vanna_model, api_key=self.vanna_api_key)
            logger.info("Vanna初始化成功")
        except Exception as e:
            logger.error(f"Vanna初始化失败: {e}")
            st.error(f"Vanna初始化失败: {e}")

    def connect_database(self):
        """连接数据库"""
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            if self.connection.is_connected():
                logger.info("数据库连接成功")
                return True
        except Error as e:
            logger.error(f"数据库连接失败: {e}")
            st.error(f"数据库连接失败: {e}")
            return False

    def get_table_schema(self) -> Dict:
        """获取数据库表结构"""
        if not self.connection:
            if not self.connect_database():
                return {}
        
        schema = {}
        try:
            cursor = self.connection.cursor()
            
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            
            for table in tables:
                # 获取表结构
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                schema[table] = {
                    'columns': [col[0] for col in columns],
                    'column_info': columns
                }
            
            cursor.close()
            return schema
            
        except Error as e:
            logger.error(f"获取表结构失败: {e}")
            return {}

    def preprocess_question(self, question: str) -> str:
        """预处理用户问题，应用业务规则映射"""
        processed_question = question
        
        for chinese_term, english_terms in self.business_rules.items():
            if chinese_term in processed_question:
                # 使用第一个英文术语替换
                processed_question = processed_question.replace(chinese_term, english_terms[0])
        
        return processed_question

    def validate_sql(self, sql: str, schema: Dict) -> Tuple[bool, List[str]]:
        """验证SQL语句的正确性"""
        errors = []
        
        # 检查SQL基本语法
        if not sql.strip():
            errors.append("SQL语句为空")
            return False, errors
        
        # 检查是否包含SELECT语句
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            errors.append("SQL语句必须包含SELECT")
        
        # 提取表名和字段名
        table_pattern = r'\bFROM\s+(\w+)'
        field_pattern = r'SELECT\s+(.*?)\s+FROM'
        
        tables_in_sql = re.findall(table_pattern, sql, re.IGNORECASE)
        fields_match = re.search(field_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if fields_match:
            fields_str = fields_match.group(1)
            # 简单的字段提取（可以进一步优化）
            fields = [f.strip() for f in fields_str.split(',') if f.strip() != '*']
        else:
            fields = []
        
        # 验证表名
        for table in tables_in_sql:
            if table not in schema:
                errors.append(f"表 '{table}' 不存在于数据库中")
        
        # 验证字段名
        for field in fields:
            # 移除别名和函数
            clean_field = re.sub(r'\s+AS\s+\w+', '', field, flags=re.IGNORECASE)
            clean_field = re.sub(r'\w+\((.*?)\)', r'\1', clean_field)
            clean_field = clean_field.strip()
            
            if '.' in clean_field:
                table_name, column_name = clean_field.split('.', 1)
                if table_name in schema and column_name not in schema[table_name]['columns']:
                    errors.append(f"字段 '{column_name}' 不存在于表 '{table_name}' 中")
            else:
                # 检查字段是否存在于任何表中
                field_exists = False
                for table_name, table_info in schema.items():
                    if clean_field in table_info['columns']:
                        field_exists = True
                        break
                if not field_exists and clean_field != '*':
                    errors.append(f"字段 '{clean_field}' 不存在于任何表中")
        
        return len(errors) == 0, errors

    def execute_sql(self, sql: str) -> Tuple[bool, pd.DataFrame, str]:
        """执行SQL查询"""
        if not self.connection:
            if not self.connect_database():
                return False, pd.DataFrame(), "数据库连接失败"
        
        try:
            df = pd.read_sql(sql, self.connection)
            return True, df, "查询成功"
        except Exception as e:
            error_msg = f"SQL执行失败: {e}"
            logger.error(error_msg)
            return False, pd.DataFrame(), error_msg

    def generate_chart(self, df: pd.DataFrame, question: str) -> Optional[go.Figure]:
        """根据数据和问题自动生成图表"""
        if df.empty:
            return None
        
        # 根据数据类型和问题内容选择合适的图表类型
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        if len(numeric_columns) >= 1 and len(categorical_columns) >= 1:
            # 柱状图
            fig = px.bar(df, x=categorical_columns[0], y=numeric_columns[0],
                        title=f"{question} - 柱状图")
            return fig
        elif len(numeric_columns) >= 2:
            # 散点图
            fig = px.scatter(df, x=numeric_columns[0], y=numeric_columns[1],
                           title=f"{question} - 散点图")
            return fig
        elif len(categorical_columns) >= 1:
            # 饼图（如果有数值列）
            if len(numeric_columns) >= 1:
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
        
        # 数值列统计
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        for col in numeric_columns:
            mean_val = df[col].mean()
            max_val = df[col].max()
            min_val = df[col].min()
            analysis.append(f"{col}的平均值为 {mean_val:.2f}，最大值为 {max_val}，最小值为 {min_val}。")
        
        # 分类列统计
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        for col in categorical_columns:
            unique_count = df[col].nunique()
            most_common = df[col].mode().iloc[0] if not df[col].mode().empty else "无"
            analysis.append(f"{col}有 {unique_count} 个不同的值，最常见的是 '{most_common}'。")
        
        return " ".join(analysis)

def main():
    """主函数 - Streamlit应用"""
    st.set_page_config(
        page_title="TEXT2SQL分析系统",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 TEXT2SQL分析系统")
    st.markdown("基于AI的自然语言转SQL查询分析平台")
    
    # 初始化系统
    if 'system' not in st.session_state:
        st.session_state.system = Text2SQLSystem()
    
    system = st.session_state.system
    
    # 侧边栏配置
    with st.sidebar:
        st.header("系统配置")
        
        # 数据库连接状态
        if st.button("测试数据库连接"):
            if system.connect_database():
                st.success("数据库连接成功！")
            else:
                st.error("数据库连接失败！")
        
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
            question = st.text_area("请输入您的问题:", height=100, placeholder="例如：查询所有学生的平均成绩")
        
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
                            
                            # 验证SQL
                            schema = system.get_table_schema()
                            is_valid, errors = system.validate_sql(sql, schema)
                            
                            if is_valid:
                                st.success("SQL语法验证通过！")
                                
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
                                st.error("SQL验证失败:")
                                for error in errors:
                                    st.error(f"- {error}")
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
        
        # 显示表关系
        with st.expander("表关系"):
            for table, relations in system.table_relationships.items():
                st.write(f"**{table}**:")
                st.write(f"- 主键: {relations['primary_key']}")
                if relations['foreign_keys']:
                    for fk in relations['foreign_keys']:
                        st.write(f"- 外键: {fk['column']} -> {fk['references']}")
        
        # 使用说明
        with st.expander("使用说明"):
            st.markdown("""
            1. 在左侧输入自然语言问题
            2. 系统会自动生成SQL查询
            3. 验证SQL语法和字段正确性
            4. 执行查询并显示结果
            5. 自动生成数据可视化图表
            6. 提供数据分析结果
            """)

if __name__ == "__main__":
    main()