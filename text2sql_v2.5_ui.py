import streamlit as st
import pandas as pd
import os
import json
from text2sql_2_5_query import Text2SQLQueryEngine, DatabaseManager, VannaWrapper
import re
import time
import plotly.express as px
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')
# 这里粘贴/导入V2.4的各show_xxx_page_v23函数
# ...（请将show_database_management_page_v23、show_table_management_page_v23等函数粘贴到此处）

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(data, path):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def show_sql_query_page_v25(system):
    st.header("智能SQL查询 V2.5 (2.5_query内核)")
    
    # 网络状态检查
    def check_network_status():
        try:
            import requests
            response = requests.get("https://api.deepseek.com", timeout=5)
            return True, "网络连接正常"
        except Exception as e:
            return False, f"网络连接异常: {str(e)}"
    
    # 显示网络状态
    network_ok, network_msg = check_network_status()
    if network_ok:
        st.success("🌐 " + network_msg)
    else:
        st.warning("⚠️ " + network_msg)
        st.info("💡 如果遇到API调用失败，请检查网络连接或稍后重试")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("自然语言查询")
        example_questions = [
            "510S本月全链库存 本月备货 MTM 未清PO",
            "geek25年7月全链库存",
            "geek25年7月全链库存，本月备货，MTM,未清PO",
        ]
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        if selected_example != "自定义问题":
            question = st.text_area("请输入您的问题:", value=selected_example, height=100)
        else:
            question = st.text_area("请输入您的问题:", height=100)
        # 新增：数据库名选择
        database_options = ["FF_IDSS_Dev_FF", "FF_IDSS_Prod", "Another_DB"]
        selected_database = st.selectbox("选择数据库", database_options, index=0)
        db_config = {
            "type": "mssql",
            "config": {
                "server": "10.97.34.39",
                "database": selected_database,
                "username": "AI_User",
                "password": "D!O$LYHSVNSL",
                "driver": "ODBC Driver 18 for SQL Server",
                "encrypt": "no",
                "trust_server_certificate": "yes"
            }
        }
        if st.button("生成SQL查询 (2.5_query内核)", type="primary"):
            if question:
                # 合并SQL生成和执行过程
                with st.spinner("正在处理查询..."):
                    # 尝试从问题中识别目标表
                    target_table = None
                    for table_name in system.table_knowledge.keys():
                        if table_name.lower() in question.lower():
                            target_table = table_name
                            break
                    
                    prompt = system.generate_prompt(question, target_table)
                    
                    # 增加错误处理
                    try:
                        sql, analysis = system.generate_sql(prompt)
                        
                        # 应用产品层级映射（处理跨表维度不匹配）
                        if sql and not sql.startswith("API调用失败") and not sql.startswith("网络连接"):
                            sql = system.apply_product_hierarchy_mapping(question, sql, db_config)
                            
                    except Exception as e:
                        st.error(f"SQL生成过程中发生错误: {str(e)}")
                        st.info("💡 建议：请检查网络连接，或稍后重试")
                        return
                    
                    if sql and not sql.startswith("API调用失败") and not sql.startswith("网络连接"):
                        st.success("SQL生成成功")
                        st.code(sql, language="sql")
                        
                        # SQL校验
                        with st.spinner("正在校验SQL..."):
                            try:
                                validated_sql, validation_analysis = system.llm_validate_sql(sql, prompt)
                            except Exception as e:
                                st.warning(f"SQL校验过程中发生错误: {str(e)}")
                                validated_sql, validation_analysis = sql, "校验失败"
                            
                            if validated_sql and not validated_sql.startswith("API调用失败"):
                                # 检查校验后的SQL是否与原始SQL不同
                                if validated_sql.strip() != sql.strip():
                                    st.warning("SQL已校验并修正")
                                    st.code(validated_sql, language="sql")
                                    sql = validated_sql  # 使用修正后的SQL
                                else:
                                    st.success("SQL校验通过，无需修正")
                            else:
                                st.warning("SQL校验失败，使用原始SQL")
                        
                        # 本地校验
                        try:
                            local_check_result = system.enhanced_local_field_check(sql)
                        except Exception as e:
                            st.warning(f"本地校验过程中发生错误: {str(e)}")
                            local_check_result = "本地校验失败"
                            
                        if "发现问题" in local_check_result:
                            st.warning("本地校验发现问题")
                            st.text_area("本地校验结果:", local_check_result, height=100, disabled=True)
                            
                            # 新增：LLM自动修正本地校验发现的问题
                            st.info("正在使用LLM修正本地校验发现的问题...")
                            with st.spinner("LLM正在修正SQL..."):
                                try:
                                    fixed_sql, fix_analysis = system.llm_fix_sql(sql, local_check_result, question)
                                except Exception as e:
                                    st.warning(f"LLM修正过程中发生错误: {str(e)}")
                                    fixed_sql, fix_analysis = sql, "修正失败"
                                
                                if fixed_sql != sql:
                                    st.success("✅ SQL已自动修正")
                                    st.code(fixed_sql, language="sql")
                                    
                                    # 显示修正分析
                                    with st.expander("查看修正分析", expanded=False):
                                        st.text_area("修正分析:", fix_analysis, height=150, disabled=True)
                                    
                                    # 使用修正后的SQL
                                    sql = fixed_sql
                                else:
                                    st.warning("⚠️ LLM未能修正SQL")
                        
                        # 显示详细LLM过程（合并SQL生成和校验分析）
                        with st.expander("显示详细LLM过程", expanded=False):
                            st.text_area("提示词:", prompt, height=200, disabled=True)
                            st.text_area("LLM 分析:", analysis, height=200, disabled=True)
                            if validation_analysis and not validation_analysis.startswith("API调用失败"):
                                st.text_area("校验分析:", validation_analysis, height=150, disabled=True)
                        
                        # 字段验证 - 已删除误报的无效字段检测功能
                        
                        # 执行SQL
                        with st.spinner("正在执行SQL..."):
                            try:
                                success, df, exec_message = system.execute_sql(sql, db_config)
                            except Exception as e:
                                st.error(f"SQL执行过程中发生错误: {str(e)}")
                                return
                            
                            if success:
                                st.success("SQL执行成功")
                                
                                # 显示查询结果
                                st.subheader("查询结果")
                                st.dataframe(df, use_container_width=True)
                                
                                # 可视化
                                if not df.empty:
                                    st.subheader("数据可视化")
                                    
                                    # 智能识别字段类型
                                    categorical_cols = []
                                    numeric_cols = []
                                    doi_cols = []
                                    doi_columns = []  # 添加这个变量以确保兼容性
                                    
                                    for col in df.columns:
                                        if df[col].dtype == 'object' or col in ['Roadmap Family', 'MTM', '产品', '型号', 'Group']:
                                            categorical_cols.append(col)
                                        elif df[col].dtype != 'object':
                                            if 'DOI' in col or '周转天' in col:
                                                doi_cols.append(col)
                                                doi_columns.append(col)  # 同时填充两个变量
                                            else:
                                                numeric_cols.append(col)
                                    
                                    # 智能选择X轴（优先选择分类字段）
                                    if categorical_cols:
                                        x_axis_col = categorical_cols[0]  # 优先使用第一个分类字段
                                    else:
                                        # 如果没有分类字段，尝试从问题中提取指标作为X轴
                                        import re
                                        indicators = re.findall(r'全链库存|周转|预测|备货|PO', question)
                                        if indicators and len(df.columns) > 1:
                                            x_axis_col = df.columns[1]  # 使用第二列作为X轴
                                        else:
                                            x_axis_col = df.columns[0]
                                    
                                    # 数值字段（Y轴候选）
                                    value_columns_no_doi = [col for col in numeric_cols if col not in doi_cols]
                                    
                                    # 用户多选库存类指标（柱状图）
                                    selected_bars = st.multiselect(
                                        "请选择库存类指标（柱状图，可多选）",
                                        value_columns_no_doi,
                                        default=value_columns_no_doi[:1] if value_columns_no_doi else []
                                    )
                                    
                                    # 用户单选DOI类指标（折线图）
                                    selected_line = st.selectbox("请选择DOI类指标（折线图，单选）", doi_cols) if doi_cols else None
                                    
                                    # 生成图表标题
                                    def generate_chart_title(question, df):
                                        import re
                                        # 提取定语（如510S、GEEK等）
                                        qualifier_match = re.search(r'([A-Z0-9]+[A-Z]|[一-龯]+)', question)
                                        qualifier = qualifier_match.group(1) if qualifier_match else ""
                                        
                                        # 提取时间信息
                                        time_match = re.search(r'(\d{4}年\d{1,2}月|\d{4}年|\d{1,2}月)', question)
                                        time_info = time_match.group(1) if time_match else ""
                                        
                                        # 如果没有时间信息，尝试从SQL中提取
                                        if not time_info:
                                            # 检查是否有"本月"、"7月"等时间信息
                                            month_match = re.search(r'(本月|7月|8月|9月|10月|11月|12月)', question)
                                            if month_match:
                                                time_info = "2025年" + month_match.group(1)
                                            else:
                                                time_info = "2025年7月"  # 默认时间
                                        
                                        if qualifier and time_info:
                                            return f"{time_info} {qualifier}"
                                        elif qualifier:
                                            return f"{qualifier} 数据对比"
                                        elif time_info:
                                            return f"{time_info} 数据对比"
                                        else:
                                            return f"{question} - 查询结果"
                                    
                                    chart_title = generate_chart_title(question, df)
                                    
                                    import plotly.graph_objects as go
                                    if selected_bars and selected_line:
                                        fig = go.Figure()
                                        # 柱状图
                                        for bar in selected_bars:
                                            fig.add_trace(go.Bar(
                                                x=df[x_axis_col],
                                                y=df[bar],
                                                name=bar,
                                                yaxis='y1'
                                            ))
                                        # 折线图
                                        fig.add_trace(go.Scatter(
                                            x=df[x_axis_col],
                                            y=df[selected_line],
                                            name=selected_line,
                                            yaxis='y2',
                                            mode='lines+markers',
                                            line=dict(width=3, color='red')
                                        ))
                                        fig.update_layout(
                                            title=chart_title,
                                            xaxis=dict(title=x_axis_col),
                                            yaxis=dict(title='数值指标', side='left'),
                                            yaxis2=dict(title='DOI/周转天数', overlaying='y', side='right'),
                                            legend=dict(x=0.01, y=0.99)
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                                    elif selected_bars:
                                        fig = go.Figure()
                                        for bar in selected_bars:
                                            fig.add_trace(go.Bar(
                                                x=df[x_axis_col],
                                                y=df[bar],
                                                name=bar
                                            ))
                                        fig.update_layout(title=chart_title, xaxis=dict(title=x_axis_col), yaxis=dict(title='数值'))
                                        st.plotly_chart(fig, use_container_width=True)
                                    else:
                                        st.info("请至少选择一个库存类指标。")
                                
                                # 下载功能
                                csv = df.to_csv(index=False)
                                st.download_button("下载CSV", csv, "query_results.csv", "text/csv")
                                
                                # 智能分析并存储到session state
                                if not df.empty:
                                    analysis_result = system.analyze_query_result(df, sql, question)
                                    st.session_state.last_analysis = analysis_result
                                
                                # 评价区
                                st.subheader("SQL评价")
                                col1_eval, col2_eval = st.columns(2)
                                with col1_eval:
                                    if st.button("👍 正确", key="correct_btn"):
                                        system.record_historical_qa(question, sql)
                                        st.success("已存入历史知识库，后续将参考提升准确率")
                                        # 强制刷新页面以显示更新
                                        st.rerun()
                                with col2_eval:
                                    if st.button("👎 错误", key="wrong_btn"):
                                        st.info("感谢反馈，已忽略本次SQL")
                            else:
                                # 过滤掉误报的字段验证错误信息
                                if "SQL字段验证失败" in exec_message and "以下字段不存在于表结构中" in exec_message:
                                    st.error("查询失败: 数据库连接或SQL执行错误")
                                elif "用户 'FF_User' 登录失败" in exec_message:
                                    st.error("查询失败: 数据库用户登录失败，请检查用户名和密码")
                                    st.info("💡 提示：请联系数据库管理员确认正确的登录凭据")
                                elif "SSL 提供程序" in exec_message and "证书链" in exec_message:
                                    st.error("查询失败: 数据库SSL证书验证失败")
                                    st.info("💡 提示：请检查数据库服务器的SSL证书配置")
                                elif "未发现数据源名称" in exec_message:
                                    st.error("查询失败: ODBC驱动未正确安装")
                                    st.info("💡 提示：请安装 Microsoft ODBC Driver for SQL Server")
                                else:
                                    st.error(f"查询失败: {exec_message}")
                    elif sql:
                        st.error(f"SQL生成失败: {sql}")
                        return
                    else:
                        st.error("SQL生成失败")
            else:
                st.warning("请输入问题")
    with col2:
        st.subheader("历史问答对")
        # 显示历史问答对统计
        qa_count = len(system.historical_qa)
        st.metric("历史问答对数量", qa_count)
        
        # 历史问答对查看功能
        if system.historical_qa:
            st.subheader("最近的历史问答对")
            
            # 添加删除功能
            col_qa_header1, col_qa_header2 = st.columns([3, 1])
            with col_qa_header1:
                st.write(f"共 {len(system.historical_qa)} 条记录")
            with col_qa_header2:
                if st.button("🗑️ 清空所有", key="clear_all_qa"):
                    if st.session_state.get("confirm_clear_qa", False):
                        system.historical_qa = []
                        if save_json(system.historical_qa, 'historical_qa.json'):
                            st.success("✅ 已清空所有历史问答对")
                            st.rerun()
                    else:
                        st.session_state["confirm_clear_qa"] = True
                        st.warning("⚠️ 再次点击确认清空")
            
            # 显示历史问答对，支持删除单个
            for i, qa in enumerate(system.historical_qa[-10:]):  # 显示最近10条
                col_qa1, col_qa2 = st.columns([4, 1])
                with col_qa1:
                    with st.expander(f"Q{i+1}: {qa['question'][:50]}...", expanded=False):
                        st.write(f"**问题:** {qa['question']}")
                        st.code(qa['sql'], language="sql")
                        st.caption(f"时间: {qa.get('timestamp', '未知')}")
                with col_qa2:
                    if st.button(f"删除", key=f"delete_qa_{i}"):
                        if st.session_state.get(f"confirm_delete_qa_{i}", False):
                            # 删除指定索引的记录
                            actual_index = len(system.historical_qa) - 10 + i
                            if 0 <= actual_index < len(system.historical_qa):
                                del system.historical_qa[actual_index]
                                if save_json(system.historical_qa, 'historical_qa.json'):
                                    st.success("✅ 已删除该记录")
                                    st.rerun()
                        else:
                            st.session_state[f"confirm_delete_qa_{i}"] = True
                            st.warning("⚠️ 再次点击确认删除")
        else:
            st.info("暂无历史问答对")
        
        # 新增：Vanna训练功能
        st.subheader("Vanna训练")
        if st.button("训练Vanna (使用历史问答对)", type="secondary"):
            with st.spinner("正在训练Vanna..."):
                success = system.train_vanna_with_enterprise_knowledge()
                if success:
                    st.success("✅ Vanna训练完成！历史问答对已加入训练")
                else:
                    st.error("❌ Vanna训练失败，请检查配置")
        
        # 显示训练状态
        if hasattr(system, 'vanna') and system.vanna:
            st.info("💡 Vanna已初始化，可以进行训练")
        else:
            st.warning("⚠️ Vanna未初始化，无法进行训练")
        
        # 智能分析区域
        st.subheader("智能分析")
        if 'last_analysis' in st.session_state and st.session_state.last_analysis:
            st.markdown(st.session_state.last_analysis)
        else:
            st.info("请在左侧输入问题并点击按钮进行查询，分析结果将显示在这里。")

# 移除重复的main函数，保留更完整的版本


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
            "510S本月全链库存 本月备货 MTM 未清PO",
            "geek25年7月全链库存",
            "geek25年7月全链库存，本月备货，MTM,未清PO",
        ]
        
        selected_example = st.selectbox("选择示例问题:", ["自定义问题"] + example_questions)
        
        if selected_example != "自定义问题":
            question = st.text_area("请输入您的问题:", value=selected_example, height=100)
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
        
        # V2.3 终极优化：强制单表查询开关
        force_single_table = st.checkbox("优先单表查询", value=True, help="当问题所需字段可能存在于单个表时，强制使用单表查询，避免不必要的JOIN。")
        
        # V2.3增强：显示性能指标
        col_gen, col_perf = st.columns([3, 1])
        
        with col_gen:
            if st.button("生成SQL查询 (V2.3增强)", type="primary"):
                if question:
                    with st.spinner("正在使用V2.3增强引擎生成SQL..."):
                        # 获取选中的数据库配置
                        db_config = active_dbs[selected_db]
                        
                        # 使用V2.3增强版SQL生成 (传入新参数)
                        start_time = time.time()
                        sql, message = system.generate_sql_enhanced(question, db_config, force_single_table)
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
    
            # V2.3增强：SQL评价功能
            st.subheader("评价本次查询:")
            col_feedback1, col_feedback2, col_feedback3 = st.columns([1, 1, 3])

            with col_feedback1:
                if st.button("👍 正确"):
                    if st.session_state.get('current_question_v23') and st.session_state.get('current_sql_v23'):
                        system.record_historical_qa(st.session_state.current_question_v23, st.session_state.current_sql_v23)
                        st.success("感谢评价！已将此优质问答存入历史知识库。")
                        st.balloons()
                    else:
                        st.warning("没有可评价的查询。")
            
            with col_feedback2:
                if st.button("👎 错误"):
                    if st.session_state.get('current_cache_key_v23'):
                        system.sql_cache.remove(st.session_state.current_cache_key_v23)
                        st.success("感谢评价！已从缓存中移除此错误SQL，避免再次使用。")
                        # 清空当前显示的错误结果
                        st.session_state.current_sql_v23 = ""
                        st.session_state.query_results_v23 = None
                        if 'current_cache_key_v23' in st.session_state:
                           del st.session_state['current_cache_key_v23']
                        st.rerun()
                    else:
                        st.warning("没有可评价的缓存查询。")

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

    # 新增：企业知识库一键训练Vanna
    st.markdown("---")
    st.subheader("企业知识库一键训练Vanna")
    if hasattr(system, 'vn') and system.vn:
        # 可编辑的qa_examples
        if 'qa_examples' not in st.session_state:
            st.session_state.qa_examples = [
                {"question": f"查询{table_name}所有数据", "sql": f"SELECT * FROM [{table_name}]"}
                for table_name in system.table_knowledge.keys()
            ]
        # 显示和编辑每对问题-SQL
        remove_indices = []
        for i, qa in enumerate(st.session_state.qa_examples):
            st.markdown(f"**问题-SQL对 {i+1}**")
            q = st.text_area(f"问题 {i+1}", value=qa["question"], key=f"q_{i}")
            s = st.text_area(f"SQL {i+1}", value=qa["sql"], key=f"s_{i}")
            st.session_state.qa_examples[i]["question"] = q
            st.session_state.qa_examples[i]["sql"] = s
            if st.button(f"删除第{i+1}对", key=f"del_{i}"):
                remove_indices.append(i)
        # 删除选中的
        for idx in sorted(remove_indices, reverse=True):
            st.session_state.qa_examples.pop(idx)
        if st.button("新增问题-SQL对"):
            st.session_state.qa_examples.append({"question": "", "sql": ""})
        if st.button("确认并训练Vanna", type="primary"):
            qa_examples = [qa for qa in st.session_state.qa_examples if qa["question"].strip() and qa["sql"].strip()]
            system.train_vanna_with_enterprise_knowledge(qa_examples)
    else:
        st.info("请先初始化本地Vanna，再进行知识库训练。")

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
        
        # V2.3 增强：仅在选择数据库后加载表
        tables = []
        if selected_db:
            with st.spinner("正在获取表列表..."):
                start_time = time.time()
                tables = system.db_manager.get_tables(db_config["type"], db_config["config"])
                load_time = time.time() - start_time
        
        if tables:
            st.info(f"共找到 {len(tables)} 个表 (耗时: {load_time:.2f}s)")
            
            # 表筛选功能
            st.subheader("表筛选")
            search_term = st.text_input("搜索表名:", placeholder="输入表名关键词")
            filtered_tables = [t for t in tables if search_term.lower() in t.lower()] if search_term else tables
            
            # 显示筛选结果
            if search_term:
                st.info(f"筛选结果: {len(filtered_tables)} 个表")
            
            # 添加滚动条容器
            st.subheader("数据库表列表")
            with st.container():
                # 限制初始显示的表数量
                display_limit = 10
                show_more = st.button("显示更多表", key="show_more_tables")
                
                if show_more or len(filtered_tables) <= display_limit:
                    tables_to_show = filtered_tables
                else:
                    tables_to_show = filtered_tables[:display_limit]
                
                # 创建可滚动的表列表
                table_container = st.container()
                with table_container:
                    for i, table in enumerate(tables_to_show):
                        with st.expander(f"📋 {table}", expanded=False):
                            # 表结构信息
                            schema = system.db_manager.get_table_schema(db_config["type"], db_config["config"], table)
                            if schema:
                                st.write(f"**字段数**: {len(schema['columns'])}")
                                st.write(f"**字段列表**: {', '.join(schema['columns'][:5])}{'...' if len(schema['columns']) > 5 else ''}")
                                
                                # 导入状态检查
                                if table in system.table_knowledge:
                                    st.success("✅ 已在知识库")
                                    if st.button(f"更新结构", key=f"update_db_{table}"):
                                        system.table_knowledge[table]["columns"] = schema["columns"]
                                        system.table_knowledge[table]["column_info"] = schema["column_info"]
                                        system.table_knowledge[table]["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                        system.save_table_knowledge()
                                        st.success(f"表 {table} 结构已更新")
                                        st.rerun()
                                else:
                                    st.warning("❌ 未导入知识库")
                                    if st.button(f"导入到知识库", key=f"import_db_{table}"):
                                        system.table_knowledge[table] = {
                                            "columns": schema["columns"],
                                            "column_info": schema["column_info"],
                                            "comment": f"从{db_config['name']}自动导入",
                                            "relationships": [],
                                            "business_fields": {},
                                            "import_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                            "database": db_config["config"].get("database") or db_config["config"].get("db") or "",
                                            "schema": "dbo",
                                        }
                                        system.save_table_knowledge()
                                        st.success(f"表 {table} 已导入知识库")
                                        st.rerun()
                            else:
                                st.error("❌ 无法获取表结构")
                
                # 显示更多按钮
                if len(filtered_tables) > display_limit and not show_more:
                    st.info(f"显示 {len(tables_to_show)} / {len(filtered_tables)} 个表")
            
            # 批量操作
            st.subheader("批量操作")
            col_batch1, col_batch2, col_batch3 = st.columns(3)
            
            with col_batch1:
                if st.button("导入所有表到知识库"):
                    imported_count = 0
                    with st.spinner("正在批量导入表结构..."):
                        for table in filtered_tables:
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
                                        "import_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "database": db_config["config"].get("database") or db_config["config"].get("db") or "",
                                        "schema": "dbo",
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
            
            # 显示表详情（默认全部收起）
            # 限制显示数量，提高效率
            display_count = 10
            total_tables = len(filtered_tables)
            
            if total_tables > display_count:
                st.info(f"显示前 {display_count} 个表（共 {total_tables} 个表）")
                # 添加滚动查看更多功能
                if st.button("显示更多表"):
                    display_count = min(display_count + 10, total_tables)
                    st.rerun()
            
            for i, table in enumerate(filtered_tables[:display_count]):
                with st.expander(f"📊 {table}", expanded=False):
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
                                if st.button(f"导入知识库", key=f"import_kb_{table}"):
                                    system.table_knowledge[table] = {
                                        "columns": schema["columns"],
                                        "column_info": schema["column_info"],
                                        "comment": "",
                                        "relationships": [],
                                        "business_fields": {},
                                        "import_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "database": db_config["config"].get("database") or db_config["config"].get("db") or "",
                                        "schema": "dbo",
                                    }
                                    system.save_table_knowledge()
                                    st.success(f"表 {table} 已导入知识库")
                                    st.rerun()
                            else:
                                st.success("✅ 已在知识库")
                                if st.button(f"更新结构", key=f"update_kb_{table}"):
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
            # 添加调试信息
            st.info(f"知识库中共有 {len(system.table_knowledge)} 个表")
            
            # 显示所有表名（调试用）
            table_names = list(system.table_knowledge.keys())
            st.write(f"**表列表**: {', '.join(table_names)}")
            
            # 按表名排序显示
            sorted_tables = sorted(system.table_knowledge.items(), key=lambda x: x[0])
            
            for table_name, table_info in sorted_tables:
                with st.expander(f"🧠 {table_name} (知识库)", expanded=False):
                    col_kb1, col_kb2 = st.columns([2, 1])
                    
                    with col_kb1:
                        # V2.3增强：数据库和Schema可编辑
                        current_db = table_info.get("database", "")
                        new_db = st.text_input("所属数据库:", value=current_db, key=f"db_{table_name}")
                        
                        current_schema = table_info.get("schema", "dbo")
                        new_schema = st.text_input("所属Schema:", value=current_schema, key=f"schema_{table_name}")

                        # 表备注编辑
                        current_comment = table_info.get("comment", "")
                        new_comment = st.text_area(
                            "表备注:", 
                            value=current_comment, 
                            key=f"comment_{table_name}",
                            height=100
                        )
                        
                        if st.button(f"保存元数据", key=f"save_meta_{table_name}"):
                            system.table_knowledge[table_name]["database"] = new_db
                            system.table_knowledge[table_name]["schema"] = new_schema
                            system.table_knowledge[table_name]["comment"] = new_comment
                            system.save_table_knowledge()
                            st.success("元数据已保存")
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
            
            # 删除关联关系（改进布局：删除按钮和关系信息在同一行）
            st.write("**删除关联关系:**")
            for idx, rel in enumerate(all_relationships):
                # 使用列布局，将删除按钮和关系信息放在同一行
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 2, 1, 1, 1, 3, 1])
                
                with col1:
                    st.write(f"**{rel['表1']}**")
                with col2:
                    st.write(f"→ {rel['字段1']}")
                with col3:
                    st.write(f"**{rel['表2']}**")
                with col4:
                    st.write(f"→ {rel['字段2']}")
                with col5:
                    st.write(f"({rel['类型']})")
                with col6:
                    st.write(f"{rel['置信度']:.1f}")
                with col7:
                    st.write(f"*{rel['描述']}*")
                with col8:
                    if st.button(f"删除", key=f"del_rel_{rel['key']}", type="secondary"):
                        # 删除该关联关系（从所有涉及表中删除）
                        for t in [rel["表1"], rel["表2"]]:
                            if t in system.table_knowledge:
                                system.table_knowledge[t]["relationships"] = [
                                    r for r in system.table_knowledge[t]["relationships"]
                                    if not (
                                        r.get("table1") == rel["表1"] and
                                        r.get("table2") == rel["表2"] and
                                        r.get("field1") == rel["字段1"] and
                                        r.get("field2") == rel["字段2"]
                                    )
                                ]
                        
                        system.save_table_knowledge()
                        st.success(f"已删除关联关系: {rel['表1']}.{rel['字段1']} ↔ {rel['表2']}.{rel['字段2']}")
                        st.rerun()
                
                # 添加分隔线
                st.divider()
            # 删除全部
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
            # 表选择放在表单外，保证字段下拉实时联动
            manual_table1 = st.selectbox("表1", table_names, key="manual_table1_out")
            manual_table2 = st.selectbox("表2", table_names, key="manual_table2_out")
            field1_options = system.table_knowledge[manual_table1]["columns"] if manual_table1 in system.table_knowledge else []
            field2_options = system.table_knowledge[manual_table2]["columns"] if manual_table2 in system.table_knowledge else []
            with st.form("add_manual_relationship"):
                manual_field1 = st.selectbox("字段1", field1_options, key=f"manual_field1_{manual_table1}")
                manual_field2 = st.selectbox("字段2", field2_options, key=f"manual_field2_{manual_table2}")
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
            
            # product_tables = [t for t in tables if any(keyword in t.lower() for keyword in ['group', 'product', 'item', 'goods'])]
            product_tables = tables  # 放开限制，允许选择所有表
            
            if product_tables:
                st.write(f"**找到 {len(product_tables)} 个可选的产品表:**")
                
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
                                        
                                        # 只保留供应链核心字段，其他作为自定义字段
                                        product_data = {
                                            "pn": str(row.iloc[0]) if len(row) > 0 else "",
                                            "group": str(row.iloc[1]) if len(row) > 1 else "",
                                            "roadmap_family": str(row.iloc[2]) if len(row) > 2 else "",
                                            "model": str(row.iloc[3]) if len(row) > 3 else "",
                                            "import_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                            "source_table": selected_table,
                                            "source_database": db_config["name"],
                                            "source": "import"
                                        }
                                        
                                        # 将其他字段作为自定义字段
                                        for i, (col_name, value) in enumerate(row.items()):
                                            if i > 3 and pd.notna(value):  # 跳过前4个核心字段
                                                product_data[f"field_{col_name}"] = str(value)
                                        
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
        
        # 手动添加产品信息 - 只保留供应链核心字段
        st.subheader("手动添加产品信息")
        st.info("只保留供应链核心字段：PN、Group、Roadmap Family、Model")
        
        with st.form("add_product"):
            col_prod1, col_prod2 = st.columns(2)
            
            with col_prod1:
                product_id = st.text_input("产品ID:")
                pn = st.text_input("PN:")
                group = st.text_input("Group:")
            
            with col_prod2:
                roadmap_family = st.text_input("Roadmap Family:")
                model = st.text_input("Model:")
            
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
                if product_id and pn:
                    if "products" not in system.product_knowledge:
                        system.product_knowledge["products"] = {}
                    
                    product_data = {
                        "pn": pn,
                        "group": group,
                        "roadmap_family": roadmap_family,
                        "model": model,
                        "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "manual"
                    }
                    
                    # 添加自定义字段
                    product_data.update(custom_fields)
                    
                    system.product_knowledge["products"][product_id] = product_data
                    
                    if system.save_product_knowledge():
                        st.success(f"已添加产品: {pn}")
                        st.session_state.custom_field_count = 0
                        st.rerun()
                    else:
                        st.error("保存失败")
                else:
                    st.warning("请填写产品ID和PN")
        
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
                    if product.get("group"):
                        all_categories.add(product["group"])
                
                filter_category = st.selectbox("筛选分类:", ["全部"] + list(all_categories))
            
            # 过滤产品
            filtered_products = {}
            for product_id, product_info in system.product_knowledge["products"].items():
                # 搜索过滤
                if search_term:
                    if (search_term.lower() not in product_id.lower() and 
                        search_term.lower() not in product_info.get('pn', '').lower()):
                        continue
                
                # 分类过滤
                if filter_category != "全部":
                    if product_info.get('group') != filter_category:
                        continue
                
                filtered_products[product_id] = product_info
            
            st.write(f"**显示 {len(filtered_products)} / {len(system.product_knowledge['products'])} 个产品**")
            
            # 批量操作
            if filtered_products:
                col_batch1, col_batch2, col_batch3, col_batch4 = st.columns(4)
                
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
                    if st.button("批量更新Model"):
                        new_model = st.text_input("新Model:", key="batch_model")
                        if st.button("确认更新"):
                            for product_id in filtered_products:
                                system.product_knowledge["products"][product_id]["model"] = new_model
                                system.product_knowledge["products"][product_id]["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            
                            system.save_product_knowledge()
                            st.success(f"已更新 {len(filtered_products)} 个产品Model")
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
                
                with col_batch4:
                    if st.button("清理非核心字段"):
                        cleaned_count = 0
                        for product_id in filtered_products:
                            product_info = system.product_knowledge["products"][product_id]
                            # 只保留供应链核心字段
                            cleaned_product = {
                                "pn": product_info.get("pn", ""),
                                "group": product_info.get("group", ""),
                                "roadmap_family": product_info.get("roadmap_family", ""),
                                "model": product_info.get("model", ""),
                                "create_time": product_info.get("create_time", ""),
                                "import_time": product_info.get("import_time", ""),
                                "update_time": product_info.get("update_time", ""),
                                "source": product_info.get("source", ""),
                                "source_table": product_info.get("source_table", ""),
                                "source_database": product_info.get("source_database", "")
                            }
                            # 保留自定义字段（以field_开头的字段）
                            for key, value in product_info.items():
                                if key.startswith("field_"):
                                    cleaned_product[key] = value
                            
                            system.product_knowledge["products"][product_id] = cleaned_product
                            cleaned_count += 1
                        
                        system.save_product_knowledge()
                        st.success(f"已清理 {cleaned_count} 个产品的非核心字段")
                        st.rerun()
            
            # 显示产品列表
            for product_id, product_info in filtered_products.items():
                with st.expander(f"🏷️ {product_info.get('pn', product_id)} (ID: {product_id})"):
                    col_info, col_action = st.columns([3, 1])
                    
                    with col_info:
                        # 基础信息
                        st.write(f"**PN**: {product_info.get('pn', '')}")
                        st.write(f"**Group**: {product_info.get('group', '')}")
                        st.write(f"**Roadmap Family**: {product_info.get('roadmap_family', '')}")
                        st.write(f"**Model**: {product_info.get('model', '')}")
                        
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
                                       if k not in ['pn', 'group', 'roadmap_family', 'model', 
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
                            new_pn = st.text_input("PN:", value=product_info.get('pn', ''))
                            new_group = st.text_input("Group:", value=product_info.get('group', ''))
                            new_roadmap_family = st.text_input("Roadmap Family:", value=product_info.get('roadmap_family', ''))
                            new_model = st.text_input("Model:", value=product_info.get('model', ''))
                            
                            col_save, col_cancel = st.columns(2)
                            
                            with col_save:
                                if st.form_submit_button("保存修改"):
                                    system.product_knowledge["products"][product_id].update({
                                        'pn': new_pn,
                                        'group': new_group,
                                        'roadmap_family': new_roadmap_family,
                                        'model': new_model,
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
                business_term = st.text_input("业务术语:", placeholder="例如: 消台")
            with col_term2:
                db_term = st.text_input("数据库术语:", placeholder="例如: model")
            with col_term3:
                term_type = st.selectbox("类型:", ["实体", "字段", "条件", "时间"])
            
            # 添加表限制选择
            available_tables = list(system.table_knowledge.keys()) if system.table_knowledge else []
            table_restriction = st.selectbox(
                "表限制:", 
                ["全部表"] + available_tables,
                help="选择特定表时，此映射只对该表生效；选择全部表时，对所有表生效"
            )
            
            # 添加条件类型和条件值
            col_condition1, col_condition2 = st.columns(2)
            with col_condition1:
                condition_type = st.selectbox("条件类型:", ["等于", "包含", "正则"], help="指定字段的匹配条件")
            with col_condition2:
                condition_value = st.text_input("条件值:", placeholder="例如: ttl", help="字段需要匹配的值")
            
            term_description = st.text_input("描述:", placeholder="术语映射的说明")
            
            if st.form_submit_button("添加映射"):
                if business_term and db_term:
                    # 生成规则键（包含表信息）
                    if table_restriction != "全部表":
                        rule_key = f"{table_restriction}_{business_term}"
                    else:
                        rule_key = business_term
                    
                    # 检查是否已存在
                    if rule_key in system.business_rules:
                        st.warning(f"术语 '{business_term}' 在表 '{table_restriction}' 中已存在，将覆盖原有映射")
                    
                    # 保存业务规则
                    system.business_rules[rule_key] = {
                        "business_term": business_term,
                        "db_field": db_term,
                        "condition_type": condition_type,
                        "condition_value": condition_value,
                        "table": table_restriction if table_restriction != "全部表" else None,
                        "type": term_type,
                        "description": term_description,
                        "create_time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if system.save_business_rules():
                        st.success(f"已添加映射: {business_term} → {db_term} (表: {table_restriction})")
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
                    # 读取文件内容
                    file_content = uploaded_file.read().decode('utf-8')
                    new_rules = json.loads(file_content)
                    
                    # 检查JSON格式并转换为正确的格式
                    if isinstance(new_rules, list):
                        # 如果是数组格式，转换为对象格式
                        st.warning("检测到数组格式的JSON，正在转换为对象格式...")
                        converted_rules = {}
                        for i, rule in enumerate(new_rules):
                            if isinstance(rule, dict):
                                # 如果有business_term字段，使用它作为键
                                if 'business_term' in rule:
                                    key = rule['business_term']
                                    if rule.get('table'):
                                        key = f"{rule['table']}_{rule['business_term']}"
                                else:
                                    # 否则使用索引作为键
                                    key = f"rule_{i}"
                                converted_rules[key] = rule
                            else:
                                st.error(f"数组中的第{i+1}个元素不是有效的规则对象")
                                continue
                        new_rules = converted_rules
                        st.success(f"已转换 {len(converted_rules)} 条规则")
                    
                    elif isinstance(new_rules, dict):
                        # 已经是对象格式，直接使用
                        pass
                    else:
                        st.error("JSON文件格式不正确，请确保是对象或数组格式")
                        return
                    
                    if st.button("预览导入规则"):
                        st.write("**将导入的规则:**")
                        if new_rules:
                            preview_data = []
                            for key, rule in new_rules.items():
                                if isinstance(rule, dict):
                                    business_term = rule.get('business_term', key)
                                    db_field = rule.get('db_field', '')
                                    table = rule.get('table', '全部表')
                                    preview_data.append({
                                        "业务术语": business_term,
                                        "数据库字段": db_field,
                                        "表": table,
                                        "条件类型": rule.get('condition_type', '等于'),
                                        "条件值": rule.get('condition_value', '')
                                    })
                            
                            if preview_data:
                                preview_df = pd.DataFrame(preview_data)
                                st.dataframe(preview_df, use_container_width=True)
                            else:
                                st.warning("没有找到有效的规则数据")
                        else:
                            st.warning("没有规则数据")
                    
                    if st.button("确认导入规则"):
                        imported_count = 0
                        skipped_count = 0
                        
                        for key, rule in new_rules.items():
                            if isinstance(rule, dict):
                                # 检查是否是新的业务规则格式
                                if 'business_term' in rule and 'db_field' in rule:
                                    # 新格式：直接使用
                                    system.business_rules[key] = rule
                                    imported_count += 1
                                elif isinstance(rule, str):
                                    # 旧格式：简单映射
                                    business_term = key
                                    db_term = rule
                                    system.business_rules[business_term] = db_term
                                    imported_count += 1
                                else:
                                    skipped_count += 1
                                    st.warning(f"跳过无效规则: {key}")
                            else:
                                skipped_count += 1
                                st.warning(f"跳过无效规则: {key}")
                        
                        if imported_count > 0:
                            if system.save_business_rules():
                                st.success(f"已导入 {imported_count} 条新规则")
                                if skipped_count > 0:
                                    st.info(f"跳过 {skipped_count} 条无效规则")
                                st.rerun()
                            else:
                                st.error("导入失败")
                        else:
                            st.warning("没有导入任何规则")
                            
                except json.JSONDecodeError as e:
                    st.error(f"JSON格式错误: {e}")
                    st.info("请确保上传的是有效的JSON文件")
                except Exception as e:
                    st.error(f"文件处理错误: {e}")
                    st.info("请检查文件格式是否正确")
        
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
            all_tables = set()
            for meta in system.business_rules_meta.values():
                if meta.get("type"):
                    all_types.add(meta["type"])
                if meta.get("table_restriction"):
                    all_tables.add(meta["table_restriction"])
            
            filter_type = st.selectbox("筛选类型:", ["全部"] + list(all_types))
            filter_table = st.selectbox("筛选表限制:", ["全部"] + list(all_tables))
        
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
            
            # 表限制过滤
            if filter_table != "全部":
                meta = system.business_rules_meta.get(term, {})
                if meta.get("table_restriction") != filter_table:
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
                st.write(f"📂 {category} ({len(category_rules)}条)")
                for term, rule_info in category_rules.items():
                    # 处理新的业务规则格式（字典）
                    if isinstance(rule_info, dict):
                        business_term = rule_info.get('business_term', term)
                        db_field = rule_info.get('db_field', '')
                        condition_type = rule_info.get('condition_type', '等于')
                        condition_value = rule_info.get('condition_value', '')
                        table_restriction = rule_info.get('table', '')
                        rule_type = rule_info.get('type', '实体')
                        description = rule_info.get('description', '')
                    else:
                        # 处理旧的业务规则格式（字符串）
                        business_term = term
                        db_field = rule_info
                        condition_type = '等于'
                        condition_value = ''
                        table_restriction = ''
                        rule_type = '实体'
                        description = ''
                    
                    # 创建编辑表单 - 使用容器而不是expander
                    with st.container():
                        st.write(f"**编辑规则: {business_term}**")
                        col_edit1, col_edit2 = st.columns(2)
                        
                        with col_edit1:
                            new_business_term = st.text_input("业务术语:", value=business_term, key=f"edit_term_{category}_{term}")
                            new_db_field = st.text_input("数据库字段:", value=db_field, key=f"edit_field_{category}_{term}")
                            new_condition_type = st.selectbox("条件类型:", ["等于", "包含", "正则"], index=["等于", "包含", "正则"].index(condition_type), key=f"edit_condition_type_{category}_{term}")
                            new_condition_value = st.text_input("条件值:", value=condition_value, key=f"edit_condition_value_{category}_{term}")
                        
                        with col_edit2:
                            available_tables = list(system.table_knowledge.keys()) if system.table_knowledge else []
                            table_options = ["全部表"] + available_tables
                            current_table_index = 0 if not table_restriction else (table_options.index(table_restriction) if table_restriction in table_options else 0)
                            new_table_restriction = st.selectbox("表限制:", table_options, index=current_table_index, key=f"edit_table_{category}_{term}")
                            new_rule_type = st.selectbox("规则类型:", ["实体", "字段", "条件", "时间"], index=["实体", "字段", "条件", "时间"].index(rule_type), key=f"edit_type_{category}_{term}")
                            new_description = st.text_input("描述:", value=description, key=f"edit_desc_{category}_{term}")
                        
                        col_btn1, col_btn2, col_btn3 = st.columns(3)
                        
                        with col_btn1:
                            if st.button("保存更改", key=f"save_{category}_{term}"):
                                # 创建新的规则对象
                                new_rule = {
                                    "business_term": new_business_term,
                                    "db_field": new_db_field,
                                    "condition_type": new_condition_type,
                                    "condition_value": new_condition_value,
                                    "table": new_table_restriction if new_table_restriction != "全部表" else None,
                                    "type": new_rule_type,
                                    "description": new_description,
                                    "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                }
                                
                                # 如果术语改变了，需要更新键
                                if new_business_term != business_term:
                                    del system.business_rules[term]
                                    new_key = f"{new_table_restriction}_{new_business_term}" if new_table_restriction != "全部表" else new_business_term
                                else:
                                    new_key = term
                                
                                system.business_rules[new_key] = new_rule
                                
                                # 更新元数据
                                if new_key in system.business_rules_meta:
                                    system.business_rules_meta[new_key].update({
                                        "type": new_rule_type,
                                        "table_restriction": new_table_restriction if new_table_restriction != "全部表" else None,
                                        "description": new_description,
                                        "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                    })
                                
                                if system.save_business_rules():
                                    st.success("✅ 规则已更新")
                                    st.rerun()
                                else:
                                    st.error("❌ 保存失败")
                        
                        with col_btn2:
                            if st.button("删除规则", key=f"delete_{category}_{term}"):
                                if st.session_state.get(f"confirm_delete_{term}", False):
                                    del system.business_rules[term]
                                    if term in system.business_rules_meta:
                                        del system.business_rules_meta[term]
                                    if system.save_business_rules():
                                        st.success("✅ 规则已删除")
                                        st.rerun()
                                    else:
                                        st.error("❌ 删除失败")
                                else:
                                    st.session_state[f"confirm_delete_{term}"] = True
                                    st.warning("⚠️ 再次点击确认删除")
                        
                        with col_btn3:
                            if st.button("复制规则", key=f"copy_{category}_{term}"):
                                # 创建副本
                                copy_key = f"{term}_copy"
                                system.business_rules[copy_key] = rule_info.copy() if isinstance(rule_info, dict) else rule_info
                                if system.save_business_rules():
                                    st.success("✅ 规则已复制")
                                    st.rerun()
                                else:
                                    st.error("❌ 复制失败")
                        
                        # 显示规则预览
                        col_preview1, col_preview2, col_preview3 = st.columns([3, 2, 1])
                        
                        with col_preview1:
                            if isinstance(rule_info, dict):
                                preview_text = f"{rule_info.get('business_term', '')} → {rule_info.get('db_field', '')}"
                                if rule_info.get('condition_value'):
                                    preview_text += f" ({rule_info.get('condition_value', '')})"
                            else:
                                preview_text = f"{term} → {rule_info}"
                            st.text(preview_text)
                        
                        with col_preview2:
                            if isinstance(rule_info, dict):
                                table_info = rule_info.get('table', '全部表')
                                type_info = rule_info.get('type', '实体')
                                st.caption(f"表: {table_info} | 类型: {type_info}")
                            else:
                                st.caption("旧格式规则")
                        
                        with col_preview3:
                            st.caption(f"ID: {term[:10]}...")
                        
                        # 显示元数据
                        meta = system.business_rules_meta.get(term, {})
                        if meta:
                            meta_info = []
                            if meta.get("type"):
                                meta_info.append(f"类型: {meta['type']}")
                            if meta.get("table_restriction"):
                                meta_info.append(f"表限制: {meta['table_restriction']}")
                            elif meta.get("table_restriction") is None:
                                meta_info.append("表限制: 全部表")
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
                for term, rule_info in other_rules.items():
                    # 处理新的业务规则格式（字典）
                    if isinstance(rule_info, dict):
                        business_term = rule_info.get('business_term', term)
                        db_field = rule_info.get('db_field', '')
                        condition_type = rule_info.get('condition_type', '等于')
                        condition_value = rule_info.get('condition_value', '')
                        table_restriction = rule_info.get('table', '')
                        rule_type = rule_info.get('type', '实体')
                        description = rule_info.get('description', '')
                    else:
                        # 处理旧的业务规则格式（字符串）
                        business_term = term
                        db_field = rule_info
                        condition_type = '等于'
                        condition_value = ''
                        table_restriction = ''
                        rule_type = '实体'
                        description = ''
                    
                    # 创建编辑表单
                    with st.container():
                        st.write(f"**编辑规则: {business_term}**")
                        col_edit1, col_edit2 = st.columns(2)

                        with col_edit1:
                            new_business_term = st.text_input("业务术语:", value=business_term, key=f"other_edit_term_{term}")
                            new_db_field = st.text_input("数据库字段:", value=db_field, key=f"other_edit_field_{term}")
                            new_condition_type = st.selectbox("条件类型:", ["等于", "包含", "正则"], index=["等于", "包含", "正则"].index(condition_type), key=f"other_edit_condition_type_{term}")
                            new_condition_value = st.text_input("条件值:", value=condition_value, key=f"other_edit_condition_value_{term}")
                        with col_edit2:
                            available_tables = list(system.table_knowledge.keys()) if system.table_knowledge else []
                            table_options = ["全部表"] + available_tables
                            current_table_index = 0 if not table_restriction else (table_options.index(table_restriction) if table_restriction in table_options else 0)
                            new_table_restriction = st.selectbox("表限制:", table_options, index=current_table_index, key=f"other_edit_table_{term}")
                            new_rule_type = st.selectbox("规则类型:", ["实体", "字段", "条件", "时间"], index=["实体", "字段", "条件", "时间"].index(rule_type), key=f"other_edit_type_{term}")
                            new_description = st.text_input("描述:", value=description, key=f"other_edit_desc_{term}")

                        col_btn1, col_btn2, col_btn3 = st.columns(3)

                        with col_btn1:
                            if st.button("保存更改", key=f"other_save_{term}"):
                                # 创建新的规则对象
                                new_rule = {
                                    "business_term": new_business_term,
                                    "db_field": new_db_field,
                                    "condition_type": new_condition_type,
                                    "condition_value": new_condition_value,
                                    "table": new_table_restriction if new_table_restriction != "全部表" else None,
                                    "type": new_rule_type,
                                    "description": new_description,
                                    "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                }

                                # 如果术语改变了，需要更新键
                                if new_business_term != business_term:
                                    del system.business_rules[term]
                                    new_key = f"{new_table_restriction}_{new_business_term}" if new_table_restriction != "全部表" else new_business_term
                                else:
                                    new_key = term

                                system.business_rules[new_key] = new_rule

                                # 更新元数据
                                if new_key in system.business_rules_meta:
                                    system.business_rules_meta[new_key].update({
                                        "type": new_rule_type,
                                        "table_restriction": new_table_restriction if new_table_restriction != "全部表" else None,
                                        "description": new_description,
                                        "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
                                    })

                                if system.save_business_rules():
                                    st.success("✅ 规则已更新")
                                    st.rerun()
                                else:
                                    st.error("❌ 保存失败")

                        with col_btn2:
                            if st.button("删除规则", key=f"other_delete_{term}"):
                                if st.session_state.get(f"other_confirm_delete_{term}", False):
                                    del system.business_rules[term]
                                    if term in system.business_rules_meta:
                                        del system.business_rules_meta[term]
                                    if system.save_business_rules():
                                        st.success("✅ 规则已删除")
                                        st.rerun()
                                    else:
                                        st.error("❌ 删除失败")
                                else:
                                    st.session_state[f"other_confirm_delete_{term}"] = True
                                    st.warning("⚠️ 再次点击确认删除")

                        with col_btn3:
                            if st.button("复制规则", key=f"other_copy_{term}"):
                                # 创建副本
                                copy_key = f"{term}_copy"
                                system.business_rules[copy_key] = rule_info.copy() if isinstance(rule_info, dict) else rule_info
                                if system.save_business_rules():
                                    st.success("✅ 规则已复制")
                                    st.rerun()
                                else:
                                    st.error("❌ 复制失败")
                        
                        # 显示规则预览
                        col_preview1, col_preview2, col_preview3 = st.columns([3, 2, 1])
                        
                        with col_preview1:
                            if isinstance(rule_info, dict):
                                preview_text = f"{rule_info.get('business_term', '')} → {rule_info.get('db_field', '')}"
                                if rule_info.get('condition_value'):
                                    preview_text += f" ({rule_info.get('condition_value', '')})"
                            else:
                                preview_text = f"{term} → {rule_info}"
                            st.text(preview_text)
                        
                        with col_preview2:
                            if isinstance(rule_info, dict):
                                table_info = rule_info.get('table', '全部表')
                                type_info = rule_info.get('type', '实体')
                                st.caption(f"表: {table_info} | 类型: {type_info}")
                            else:
                                st.caption("旧格式规则")
                        
                        with col_preview3:
                            st.caption(f"ID: {term[:10]}...")
    
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

        # 条件规则管理区 (已禁用)
        st.subheader("条件规则管理")
        st.info("⚠️ 条件规则管理功能已禁用")
        st.write("如需启用此功能，请联系管理员")
        
        # 注释掉自动创建逻辑，避免自动创建conditional_rules
        # if "conditional_rules" not in system.business_rules:
        #     system.business_rules["conditional_rules"] = []
        # conditional_rules = system.business_rules["conditional_rules"]
        
        # 展示现有规则（如果存在）
        if "conditional_rules" in system.business_rules and system.business_rules["conditional_rules"]:
            conditional_rules = system.business_rules["conditional_rules"]
            st.write("**现有条件规则（只读）:**")
            for idx, rule in enumerate(conditional_rules):
                with st.expander(f"规则{idx+1}: {rule.get('description', '')}"):
                    st.write(f"**触发类型**: {rule.get('trigger_type', '')}")
                    st.write(f"**触发值**: {rule.get('trigger_value', '')}")
                    st.write(f"**动作**: {rule.get('action', '')}")
                    st.write(f"**追加条件**: {rule.get('condition', '')}")
                    st.write(f"**描述**: {rule.get('description', '')}")
                    
                    # 只提供删除功能
                    if st.button("删除规则", key=f"del_cond_{idx}"):
                        conditional_rules.pop(idx)
                        system.save_business_rules()
                        st.success("已删除条件规则")
                        st.rerun()
        else:
            st.info("暂无条件规则")
        
        # 禁用添加新条件规则功能
        st.subheader("添加新条件规则")
        st.warning("❌ 添加功能已禁用")
        st.write("如需添加条件规则，请联系管理员启用此功能")

        # 业务规则管理
        st.subheader("业务规则管理")
        
        # 支持表特定的业务规则
        st.write("**表特定业务规则**")
        st.write("同一业务术语在不同表中可能有不同的映射规则")
        
        # 选择表
        available_tables = list(system.table_knowledge.keys()) if system.table_knowledge else []
        if available_tables:
            selected_table = st.selectbox("选择表:", available_tables, key="business_rule_table")
            
            # 显示该表的业务规则
            table_business_rules = system.table_knowledge[selected_table].get("business_rules", {})
            
            st.write(f"**{selected_table} 表的业务规则:**")
            
            # 添加新业务规则
            with st.form(f"add_business_rule_{selected_table}"):
                col1, col2 = st.columns(2)
                with col1:
                    business_term = st.text_input("业务术语:", key=f"business_term_{selected_table}")
                    db_field = st.text_input("数据库字段:", key=f"db_field_{selected_table}")
                with col2:
                    condition_type = st.selectbox("条件类型:", ["等于", "包含", "正则"], key=f"condition_type_{selected_table}")
                    condition_value = st.text_input("条件值:", key=f"condition_value_{selected_table}")
                
                if st.form_submit_button("添加业务规则"):
                    if business_term and db_field:
                        rule_key = f"{selected_table}_{business_term}"
                        system.business_rules[rule_key] = {
                            "table": selected_table,
                            "business_term": business_term,
                            "db_field": db_field,
                            "condition_type": condition_type,
                            "condition_value": condition_value,
                            "description": f"{selected_table}表中{business_term}映射到{db_field}"
                        }
                        system.save_business_rules()
                        st.success(f"已添加业务规则: {business_term} → {db_field}")
                        st.rerun()
            
            # 显示现有业务规则
            if table_business_rules:
                st.write("**现有业务规则:**")
                for rule_key, rule_info in table_business_rules.items():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{rule_info['business_term']}** → {rule_info['db_field']}")
                        st.write(f"条件: {rule_info['condition_type']} = '{rule_info['condition_value']}'")
                    with col2:
                        if st.button(f"编辑", key=f"edit_rule_{rule_key}"):
                            st.session_state[f"editing_rule_{rule_key}"] = True
                    with col3:
                        if st.button(f"删除", key=f"del_rule_{rule_key}"):
                            del table_business_rules[rule_key]
                            system.save_business_rules()
                            st.success(f"已删除业务规则: {rule_info['business_term']}")
                            st.rerun()
                    
                    # 编辑模式
                    if st.session_state.get(f"editing_rule_{rule_key}", False):
                        with st.form(f"edit_rule_{rule_key}"):
                            new_db_field = st.text_input("数据库字段:", value=rule_info['db_field'], key=f"edit_db_field_{rule_key}")
                            new_condition_type = st.selectbox("条件类型:", ["等于", "包含", "正则"], index=["等于", "包含", "正则"].index(rule_info['condition_type']), key=f"edit_condition_type_{rule_key}")
                            new_condition_value = st.text_input("条件值:", value=rule_info['condition_value'], key=f"edit_condition_value_{rule_key}")
                            
                            if st.form_submit_button("保存"):
                                rule_info['db_field'] = new_db_field
                                rule_info['condition_type'] = new_condition_type
                                rule_info['condition_value'] = new_condition_value
                                system.save_business_rules()
                                st.session_state[f"editing_rule_{rule_key}"] = False
                                st.success("业务规则已更新")
                                st.rerun()
                        
                        if st.button("取消编辑", key=f"cancel_edit_{rule_key}"):
                            st.session_state[f"editing_rule_{rule_key}"] = False
                            st.rerun()
                    
                    st.divider()
        else:
            st.warning("请先导入表结构到知识库")

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

def show_product_hierarchy_page_v25(system):
    """产品层级管理页面 V2.5 - 处理复杂的产品层级关系和跨表维度映射"""
    st.header("产品层级管理 V2.5")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("产品层级维度映射")
        
        # 加载产品层级配置
        try:
            with open("product_hierarchy.json", 'r', encoding='utf-8') as f:
                product_hierarchy = json.load(f)
        except:
            product_hierarchy = {"product_hierarchy": {}}
        
        # 维度映射管理
        st.write("**产品维度层级:**")
        dimension_mapping = product_hierarchy.get("product_hierarchy", {}).get("dimension_mapping", {})
        
        for dim_name, dim_info in dimension_mapping.items():
            with st.expander(f"📊 {dim_name} (Level {dim_info.get('level', 0)})"):
                col_dim1, col_dim2 = st.columns(2)
                
                with col_dim1:
                    st.write(f"**描述**: {dim_info.get('description', '')}")
                    st.write(f"**父级**: {dim_info.get('parent', '无')}")
                    st.write(f"**子级**: {', '.join(dim_info.get('children', []))}")
                
                with col_dim2:
                    examples = dim_info.get('examples', [])
                    if examples:
                        st.write("**示例**:")
                        for example in examples:
                            st.write(f"- {example}")
                
                # 编辑功能
                if st.button(f"编辑{dim_name}", key=f"edit_dim_{dim_name}"):
                    st.session_state[f"editing_dim_{dim_name}"] = True
                    st.rerun()
        
        # 跨表映射管理
        st.subheader("跨表维度映射")
        cross_table_mapping = product_hierarchy.get("product_hierarchy", {}).get("cross_table_mapping", {})
        
        for table_name, table_info in cross_table_mapping.items():
            with st.expander(f"📋 {table_name}"):
                st.write(f"**可用维度**: {', '.join(table_info.get('available_dimensions', []))}")
                st.write(f"**默认聚合**: {table_info.get('default_aggregation', '')}")
                st.write(f"**描述**: {table_info.get('description', '')}")
        
        # 聚合规则管理
        st.subheader("聚合规则管理")
        aggregation_rules = product_hierarchy.get("product_hierarchy", {}).get("aggregation_rules", {})
        
        for rule_name, rule_info in aggregation_rules.items():
            with st.expander(f"⚙️ {rule_name}"):
                st.write(f"**条件**: {rule_info.get('condition', '')}")
                st.write(f"**动作**: {rule_info.get('action', '')}")
                st.write(f"**SQL模板**: {rule_info.get('sql_template', '')}")
                st.write(f"**说明**: {rule_info.get('explanation', '')}")
        
        # 添加新的维度映射
        st.subheader("添加维度映射")
        with st.form("add_dimension_mapping"):
            col_add1, col_add2 = st.columns(2)
            
            with col_add1:
                dim_name = st.text_input("维度名称:", placeholder="如: roadmap family")
                dim_level = st.number_input("层级:", min_value=1, max_value=10, value=1)
                dim_description = st.text_input("描述:", placeholder="维度说明")
            
            with col_add2:
                dim_parent = st.text_input("父级维度:", placeholder="如: box")
                dim_children = st.text_input("子级维度:", placeholder="用逗号分隔，如: model,box")
                dim_examples = st.text_input("示例值:", placeholder="用逗号分隔，如: 510S,520S,ttl")
            
            if st.form_submit_button("添加维度映射"):
                if dim_name:
                    new_dim = {
                        "level": dim_level,
                        "description": dim_description,
                        "parent": dim_parent if dim_parent else None,
                        "children": [c.strip() for c in dim_children.split(',') if c.strip()],
                        "examples": [e.strip() for e in dim_examples.split(',') if e.strip()]
                    }
                    
                    if "product_hierarchy" not in product_hierarchy:
                        product_hierarchy["product_hierarchy"] = {}
                    if "dimension_mapping" not in product_hierarchy["product_hierarchy"]:
                        product_hierarchy["product_hierarchy"]["dimension_mapping"] = {}
                    
                    product_hierarchy["product_hierarchy"]["dimension_mapping"][dim_name] = new_dim
                    
                    # 保存配置
                    with open("product_hierarchy.json", 'w', encoding='utf-8') as f:
                        json.dump(product_hierarchy, f, ensure_ascii=False, indent=2)
                    
                    st.success(f"已添加维度映射: {dim_name}")
                    st.rerun()
        
        # 智能SQL生成测试
        st.subheader("智能SQL生成测试")
        
        test_question = st.text_input("测试问题:", placeholder="如: 510S 25年7月全链库存，营销目标")
        
        if st.button("生成智能SQL"):
            if test_question:
                # 分析问题中的维度
                detected_dimensions = []
                for dim_name in dimension_mapping.keys():
                    if dim_name.lower() in test_question.lower():
                        detected_dimensions.append(dim_name)
                
                st.write("**检测到的维度:**")
                for dim in detected_dimensions:
                    st.write(f"- {dim}")
                
                # 生成跨表SQL
                if "roadmap family" in detected_dimensions and "营销目标" in test_question:
                    st.write("**跨表查询SQL:**")
                    st.code("""
-- 查询dtsupply_summary表的roadmap family维度
SELECT [roadmap family], SUM(全链库存) as 库存总量
FROM dtsupply_summary 
WHERE [roadmap family] LIKE '%510S%' 
  AND 自然年 = 2025 AND 财月 = '7月' AND 财周 = 'ttl'

-- 查询con_target表的Product Line维度（需要维度映射）
SELECT [Product Line], SUM(营销目标) as 目标总量
FROM con_target 
WHERE [Product Line] = 'IdeaCentre'  -- 将roadmap family映射到Product Line
  AND 自然年 = 2025 AND 财月 = '7月'
                    """, language="sql")
                    
                    st.info("💡 **维度映射说明**: 因为con_target表只有Product Line维度，所以将roadmap family的510S映射到Product Line的IdeaCentre")
                
                elif "Product Line" in detected_dimensions and "全链库存" in test_question:
                    st.write("**跨表查询SQL:**")
                    st.code("""
-- 查询dtsupply_summary表（需要维度映射）
SELECT [roadmap family], SUM(全链库存) as 库存总量
FROM dtsupply_summary 
WHERE [roadmap family] = 'ttl'  -- 将Product Line映射到roadmap family的ttl汇总
  AND 自然年 = 2025 AND 财月 = '7月' AND 财周 = 'ttl'

-- 查询con_target表的Product Line维度
SELECT [Product Line], SUM(营销目标) as 目标总量
FROM con_target 
WHERE [Product Line] = 'IdeaCentre'
  AND 自然年 = 2025 AND 财月 = '7月'
                    """, language="sql")
                    
                    st.info("💡 **维度映射说明**: 因为dtsupply_summary表支持roadmap family维度，所以将Product Line映射到roadmap family的ttl汇总")
    
    with col2:
        st.subheader("V2.5产品层级管理增强")
        st.markdown("""
        ### 🚀 新增功能
        - **维度层级管理**: 定义产品各层级关系
        - **跨表映射**: 处理不同表的维度差异
        - **智能聚合**: 自动处理维度不匹配问题
        - **业务层级**: 支持WW→PRC→CON层级
        
        ### 📊 维度层级
        - **Product Line**: 产品线级别
        - **IdeaCentre**: IdeaCentre系列
        - **model**: 具体型号
        - **box**: 包装级别
        - **roadmap family**: 路线图系列
        
        ### 🛠️ 映射规则
        - **con_target表**: 只有Product Line维度
        - **dtsupply_summary表**: 支持多层级维度
        - **自动映射**: 根据查询需求自动转换
        
        ### ⚡ 智能处理
        - **维度检测**: 自动识别查询中的维度
        - **跨表查询**: 处理不同表的维度差异
        - **聚合规则**: 自动应用合适的聚合方式
        """)
        
        # 统计信息
        st.subheader("统计信息")
        
        total_dimensions = len(dimension_mapping)
        total_tables = len(cross_table_mapping)
        total_rules = len(aggregation_rules)
        
        st.metric("维度数量", total_dimensions)
        st.metric("表映射", total_tables)
        st.metric("聚合规则", total_rules)
        
        # 导出功能
        if st.button("导出产品层级配置"):
            st.download_button(
                label="下载JSON文件",
                data=json.dumps(product_hierarchy, ensure_ascii=False, indent=2),
                file_name=f"product_hierarchy_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        # 重置功能
        if st.button("重置为默认配置"):
            if st.session_state.get("confirm_reset_hierarchy", False):
                # 重新创建默认配置
                default_hierarchy = {
                    "product_hierarchy": {
                        "dimension_mapping": {
                            "Product Line": {
                                "level": 1,
                                "description": "产品线级别",
                                "examples": ["IdeaCentre", "IdeaPAD"],
                                "parent": None,
                                "children": ["IdeaCentre", "IdeaPAD"]
                            }
                        },
                        "cross_table_mapping": {
                            "dtsupply_summary": {
                                "available_dimensions": ["roadmap family", "box", "model"],
                                "default_aggregation": "ttl",
                                "description": "供应汇总表"
                            },
                            "con_target": {
                                "available_dimensions": ["Product Line"],
                                "default_aggregation": "IdeaCentre",
                                "description": "营销目标表"
                            }
                        }
                    }
                }
                
                with open("product_hierarchy.json", 'w', encoding='utf-8') as f:
                    json.dump(default_hierarchy, f, ensure_ascii=False, indent=2)
                
                st.success("已重置为默认配置")
                st.session_state["confirm_reset_hierarchy"] = False
                st.rerun()
            else:
                st.session_state["confirm_reset_hierarchy"] = True
                st.warning("再次点击确认重置")

# 为Text2SQLQueryEngine添加缺失的方法
def add_missing_methods_to_system(system):
    """为系统添加缺失的方法"""
    
    def apply_product_hierarchy_mapping(question: str, sql: str, db_config: dict) -> str:
        """应用产品层级映射，处理跨表维度不匹配问题"""
        try:
            # 加载产品层级配置
            with open("product_hierarchy.json", 'r', encoding='utf-8') as f:
                product_hierarchy = json.load(f)
        except:
            return sql  # 如果配置文件不存在，直接返回原SQL
        
        cross_table_mapping = product_hierarchy.get("product_hierarchy", {}).get("cross_table_mapping", {})
        aggregation_rules = product_hierarchy.get("product_hierarchy", {}).get("aggregation_rules", {})
        
        # 检测问题中的维度
        detected_dimensions = []
        for table_name, table_info in cross_table_mapping.items():
            for dim in table_info.get("available_dimensions", []):
                if dim.lower() in question.lower():
                    detected_dimensions.append(dim)
        
        # 应用聚合规则
        for rule_name, rule_info in aggregation_rules.items():
            condition = rule_info.get("condition", "")
            if condition.lower() in question.lower():
                action = rule_info.get("action", "")
                sql_template = rule_info.get("sql_template", "")
                
                # 根据规则修改SQL
                if "con_target" in sql and "roadmap family" in detected_dimensions:
                    # 将roadmap family映射到Product Line
                    sql = sql.replace("[roadmap family]", "[Product Line]")
                    sql = sql.replace("LIKE '%510S%'", "= 'IdeaCentre'")
                    st.info(f"💡 应用维度映射: {action}")
                
                elif "dtsupply_summary" in sql and "Product Line" in detected_dimensions:
                    # 将Product Line映射到roadmap family
                    sql = sql.replace("[Product Line]", "[roadmap family]")
                    sql = sql.replace("= 'IdeaCentre'", "= 'ttl'")
                    st.info(f"💡 应用维度映射: {action}")
        
        return sql
    
    # 添加缺失的方法到系统
    system.apply_product_hierarchy_mapping = apply_product_hierarchy_mapping
    
    # 添加其他可能缺失的属性
    if not hasattr(system, 'business_rules_meta'):
        system.business_rules_meta = {}
    if not hasattr(system, 'template_metadata'):
        system.template_metadata = {}
    if not hasattr(system, 'sql_cache'):
        system.sql_cache = None
    if not hasattr(system, 'vn'):
        system.vn = None
    if not hasattr(system, 'databases'):
        system.databases = {}
    
    return system

# 在main函数中添加产品层级管理页面
def main():
    """主函数 - 添加产品层级管理页面"""
    st.set_page_config(
        page_title="TEXT2SQL 分析系统 V2.5",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 初始化系统
    # 加载配置
    table_knowledge = load_json("table_knowledge.json")
    relationships = load_json("table_relationships.json")
    business_rules = load_json("business_rules.json")
    product_knowledge = load_json("product_knowledge.json")
    historical_qa = load_json("historical_qa.json")
    prompt_templates = load_json("prompt_templates.json")
    
    # 初始化组件
    db_manager = DatabaseManager()
    vanna = VannaWrapper()
    
    # 初始化系统
    system = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=relationships,
        business_rules=business_rules,
        product_knowledge=product_knowledge,
        historical_qa=historical_qa,
        vanna=vanna,
        db_manager=db_manager,
        prompt_templates=prompt_templates
    )
    
    # 添加缺失的方法
    system = add_missing_methods_to_system(system)
    
    # 侧边栏导航
    st.sidebar.title("📊 TEXT2SQL 分析系统")
    st.sidebar.markdown("**版本**: V2.5")
    
    # 页面选择
    page = st.sidebar.selectbox(
        "选择功能页面:",
        [
            "SQL查询生成",
            "数据库管理", 
            "表结构管理",
            "产品知识库",
            "业务规则管理",
            "产品层级管理",  # 新增
            "提示词管理",
            "系统监控"
        ]
    )
    
    # 页面路由
    if page == "SQL查询生成":
        show_sql_query_page_v25(system)
    elif page == "数据库管理":
        show_database_management_page_v23(system)
    elif page == "表结构管理":
        show_table_management_page_v23(system)
    elif page == "产品知识库":
        show_product_knowledge_page_v23(system)
    elif page == "业务规则管理":
        show_business_rules_page_v23(system)
    elif page == "产品层级管理":  # 新增
        show_product_hierarchy_page_v25(system)
    elif page == "提示词管理":
        show_prompt_templates_page_v23(system)
    elif page == "系统监控":
        show_system_monitoring_page_v23(system)

if __name__ == "__main__":
    main()