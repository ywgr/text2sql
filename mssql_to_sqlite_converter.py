#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MS SQL to SQLite 数据库转换工具
功能：
1. 连接MS SQL数据库
2. 选择要转换的表
3. 将数据转换到SQLite数据库
4. 保持表名和数据结构一致
"""

import streamlit as st
import pandas as pd
import sqlite3
import pyodbc
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
import os
import traceback
from typing import Dict, List, Tuple, Optional
import time
from datetime import datetime

class DatabaseConverter:
    """数据库转换器"""
    
    def __init__(self):
        self.mssql_engine = None
        self.sqlite_engine = None
        self.mssql_connection = None
        self.sqlite_connection = None
        
    def connect_mssql(self, config: Dict) -> Tuple[bool, str]:
        """连接MS SQL数据库"""
        try:
            # 构建连接字符串
            connection_string = (
                f"mssql+pyodbc://{config['username']}:{config['password']}"
                f"@{config['server']}/{config['database']}"
                f"?driver={config['driver'].replace(' ', '+')}"
                f"&encrypt={config['encrypt']}"
                f"&TrustServerCertificate={config['trust_server_certificate']}"
            )
            
            # 创建引擎
            self.mssql_engine = create_engine(connection_string)
            
            # 测试连接
            with self.mssql_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            return True, "MS SQL数据库连接成功！"
            
        except Exception as e:
            return False, f"MS SQL连接失败: {str(e)}"
    
    def connect_sqlite(self, db_path: str) -> Tuple[bool, str]:
        """连接SQLite数据库"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
            
            # 创建SQLite连接
            self.sqlite_engine = create_engine(f"sqlite:///{db_path}")
            
            # 测试连接
            with self.sqlite_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            return True, f"SQLite数据库连接成功！文件: {db_path}"
            
        except Exception as e:
            return False, f"SQLite连接失败: {str(e)}"
    
    def get_mssql_tables(self) -> List[str]:
        """获取MS SQL数据库中的所有表"""
        try:
            if not self.mssql_engine:
                return []
            
            inspector = inspect(self.mssql_engine)
            tables = inspector.get_table_names()
            return sorted(tables)
            
        except Exception as e:
            st.error(f"获取表列表失败: {str(e)}")
            return []
    
    def get_table_info(self, table_name: str) -> Dict:
        """获取表的详细信息"""
        try:
            if not self.mssql_engine:
                return {}
            
            inspector = inspect(self.mssql_engine)
            
            # 获取列信息
            columns = inspector.get_columns(table_name)
            
            # 获取主键
            primary_keys = inspector.get_pk_constraint(table_name)
            
            # 获取索引
            indexes = inspector.get_indexes(table_name)
            
            # 获取行数
            with self.mssql_engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM [{table_name}]"))
                row_count = result.scalar()
            
            return {
                'columns': columns,
                'primary_keys': primary_keys,
                'indexes': indexes,
                'row_count': row_count
            }
            
        except Exception as e:
            st.error(f"获取表信息失败: {str(e)}")
            return {}
    
    def convert_table(self, table_name: str, chunk_size: int = 1000) -> Tuple[bool, str, Dict]:
        """转换单个表"""
        try:
            if not self.mssql_engine or not self.sqlite_engine:
                return False, "数据库连接未建立", {}
            
            start_time = time.time()
            
            # 获取表结构信息
            table_info = self.get_table_info(table_name)
            total_rows = table_info.get('row_count', 0)
            
            if total_rows == 0:
                return True, f"表 {table_name} 为空，跳过转换", {'rows_converted': 0, 'time_taken': 0}
            
            # 分批读取和写入数据
            converted_rows = 0
            
            # 创建进度条
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 分批处理数据
            for chunk_start in range(0, total_rows, chunk_size):
                # 读取数据块
                query = f"""
                SELECT * FROM [{table_name}]
                ORDER BY (SELECT NULL)
                OFFSET {chunk_start} ROWS
                FETCH NEXT {chunk_size} ROWS ONLY
                """
                
                df_chunk = pd.read_sql(query, self.mssql_engine)
                
                if df_chunk.empty:
                    break
                
                # 写入SQLite
                df_chunk.to_sql(
                    table_name, 
                    self.sqlite_engine, 
                    if_exists='append' if chunk_start > 0 else 'replace',
                    index=False,
                    method='multi'
                )
                
                converted_rows += len(df_chunk)
                
                # 更新进度
                progress = min(converted_rows / total_rows, 1.0)
                progress_bar.progress(progress)
                status_text.text(f"正在转换 {table_name}: {converted_rows}/{total_rows} 行")
            
            end_time = time.time()
            time_taken = end_time - start_time
            
            # 清理进度显示
            progress_bar.empty()
            status_text.empty()
            
            return True, f"表 {table_name} 转换成功", {
                'rows_converted': converted_rows,
                'time_taken': time_taken
            }
            
        except Exception as e:
            return False, f"转换表 {table_name} 失败: {str(e)}", {}
    
    def convert_multiple_tables(self, table_names: List[str], chunk_size: int = 1000) -> Dict:
        """转换多个表"""
        results = {
            'success': [],
            'failed': [],
            'total_rows': 0,
            'total_time': 0
        }
        
        total_tables = len(table_names)
        
        # 创建总体进度条
        overall_progress = st.progress(0)
        overall_status = st.empty()
        
        for i, table_name in enumerate(table_names):
            overall_status.text(f"正在处理表 {i+1}/{total_tables}: {table_name}")
            
            success, message, stats = self.convert_table(table_name, chunk_size)
            
            if success:
                results['success'].append({
                    'table': table_name,
                    'message': message,
                    'rows': stats.get('rows_converted', 0),
                    'time': stats.get('time_taken', 0)
                })
                results['total_rows'] += stats.get('rows_converted', 0)
                results['total_time'] += stats.get('time_taken', 0)
            else:
                results['failed'].append({
                    'table': table_name,
                    'error': message
                })
            
            # 更新总体进度
            overall_progress.progress((i + 1) / total_tables)
        
        # 清理进度显示
        overall_progress.empty()
        overall_status.empty()
        
        return results

def main():
    """主函数"""
    st.set_page_config(
        page_title="MS SQL to SQLite 转换器",
        page_icon="🔄",
        layout="wide"
    )
    
    st.title("🔄 MS SQL to SQLite 数据库转换器")
    st.markdown("---")
    
    # 初始化转换器
    if 'converter' not in st.session_state:
        st.session_state.converter = DatabaseConverter()
    
    converter = st.session_state.converter
    
    # 侧边栏配置
    with st.sidebar:
        st.header("🛠️ 数据库配置")
        
        # MS SQL配置
        st.subheader("MS SQL 数据库")
        
        # 默认配置
        default_mssql_config = {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF", 
            "username": "FF_User",
            "password": "Grape!0808",
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
        
        mssql_config = {}
        mssql_config['server'] = st.text_input("服务器", value=default_mssql_config['server'])
        mssql_config['database'] = st.text_input("数据库", value=default_mssql_config['database'])
        mssql_config['username'] = st.text_input("用户名", value=default_mssql_config['username'])
        mssql_config['password'] = st.text_input("密码", type="password", value=default_mssql_config['password'])
        mssql_config['driver'] = st.selectbox("驱动", [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "SQL Server"
        ], index=0)
        mssql_config['encrypt'] = st.selectbox("加密", ["no", "yes"], index=0)
        mssql_config['trust_server_certificate'] = st.selectbox("信任服务器证书", ["yes", "no"], index=0)
        
        # 测试MS SQL连接
        if st.button("🔗 测试 MS SQL 连接", type="primary"):
            with st.spinner("正在连接MS SQL..."):
                success, message = converter.connect_mssql(mssql_config)
                if success:
                    st.success(message)
                    st.session_state.mssql_connected = True
                else:
                    st.error(message)
                    st.session_state.mssql_connected = False
        
        st.markdown("---")
        
        # SQLite配置
        st.subheader("SQLite 数据库")
        sqlite_path = st.text_input("SQLite文件路径", value="FF_IDSS_Dev_FF.db")
        
        if st.button("🔗 连接 SQLite"):
            success, message = converter.connect_sqlite(sqlite_path)
            if success:
                st.success(message)
                st.session_state.sqlite_connected = True
            else:
                st.error(message)
                st.session_state.sqlite_connected = False
    
    # 主界面
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📋 数据库状态")
        
        # 连接状态
        mssql_status = "🟢 已连接" if getattr(st.session_state, 'mssql_connected', False) else "🔴 未连接"
        sqlite_status = "🟢 已连接" if getattr(st.session_state, 'sqlite_connected', False) else "🔴 未连接"
        
        st.write(f"**MS SQL:** {mssql_status}")
        st.write(f"**SQLite:** {sqlite_status}")
        
        # 获取表列表
        if getattr(st.session_state, 'mssql_connected', False):
            if st.button("🔄 刷新表列表"):
                st.session_state.tables = converter.get_mssql_tables()
            
            if 'tables' in st.session_state and st.session_state.tables:
                st.subheader("📊 可用表列表")
                
                # 显示表信息
                for table in st.session_state.tables:
                    with st.expander(f"📋 {table}"):
                        table_info = converter.get_table_info(table)
                        if table_info:
                            st.write(f"**行数:** {table_info.get('row_count', 'N/A')}")
                            st.write(f"**列数:** {len(table_info.get('columns', []))}")
                            
                            # 显示列信息
                            if table_info.get('columns'):
                                cols_df = pd.DataFrame([
                                    {
                                        '列名': col['name'],
                                        '类型': str(col['type']),
                                        '可空': col.get('nullable', True)
                                    }
                                    for col in table_info['columns']
                                ])
                                st.dataframe(cols_df, use_container_width=True)
    
    with col2:
        st.header("🔄 数据转换")
        
        if (getattr(st.session_state, 'mssql_connected', False) and 
            getattr(st.session_state, 'sqlite_connected', False) and
            'tables' in st.session_state):
            
            # 表选择
            st.subheader("选择要转换的表")
            
            # 全选/全不选
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("✅ 全选"):
                    st.session_state.selected_tables = st.session_state.tables.copy()
            with col_b:
                if st.button("❌ 全不选"):
                    st.session_state.selected_tables = []
            
            # 表选择器
            selected_tables = st.multiselect(
                "选择表:",
                options=st.session_state.tables,
                default=getattr(st.session_state, 'selected_tables', []),
                key='table_selector'
            )
            
            # 转换设置
            st.subheader("转换设置")
            chunk_size = st.slider("批处理大小", min_value=100, max_value=10000, value=1000, step=100)
            
            # 开始转换
            if selected_tables:
                st.write(f"已选择 {len(selected_tables)} 个表进行转换")
                
                if st.button("🚀 开始转换", type="primary"):
                    st.markdown("---")
                    st.subheader("转换进度")
                    
                    start_time = time.time()
                    
                    # 执行转换
                    results = converter.convert_multiple_tables(selected_tables, chunk_size)
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    # 显示结果
                    st.markdown("---")
                    st.subheader("📊 转换结果")
                    
                    # 成功统计
                    col_success, col_failed, col_rows, col_time = st.columns(4)
                    
                    with col_success:
                        st.metric("成功", len(results['success']))
                    
                    with col_failed:
                        st.metric("失败", len(results['failed']))
                    
                    with col_rows:
                        st.metric("总行数", f"{results['total_rows']:,}")
                    
                    with col_time:
                        st.metric("总时间", f"{total_time:.2f}s")
                    
                    # 详细结果
                    if results['success']:
                        st.success("✅ 转换成功的表:")
                        success_df = pd.DataFrame(results['success'])
                        st.dataframe(success_df, use_container_width=True)
                    
                    if results['failed']:
                        st.error("❌ 转换失败的表:")
                        failed_df = pd.DataFrame(results['failed'])
                        st.dataframe(failed_df, use_container_width=True)
            else:
                st.warning("请选择要转换的表")
        else:
            st.warning("请先连接两个数据库并获取表列表")

if __name__ == "__main__":
    main()