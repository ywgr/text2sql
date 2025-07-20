#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL V2.3 多表查询UI补丁
用于修复SQL查询页面的多表查询增强按钮
"""

def add_multi_table_button_to_sql_page():
    """为SQL查询页面添加多表查询增强按钮的代码片段"""
    
    multi_table_button_code = '''
        with col_multi:
            # V2.3新增：多表查询增强按钮
            multi_table_available = hasattr(system, 'structured_prompt_builder') and system.structured_prompt_builder is not None
            
            if multi_table_available:
                if st.button("多表增强查询", type="secondary", help="使用AI建议优化的多表查询增强功能"):
                    if question:
                        with st.spinner("正在使用多表增强引擎生成SQL..."):
                            # 获取选中的数据库配置
                            db_config = active_dbs[selected_db]
                            
                            # 使用多表增强版SQL生成
                            start_time = time.time()
                            sql, message = system.generate_sql_multi_table_enhanced(question, db_config)
                            generation_time = time.time() - start_time
                            
                            if sql:
                                # 保存到session state
                                st.session_state.current_sql_v23 = sql
                                st.session_state.current_question_v23 = question
                                st.session_state.current_db_config_v23 = db_config
                                
                                st.success("🔗 多表增强SQL生成成功")
                                st.info(f"⚡ 生成耗时: {generation_time:.2f}秒")
                                
                                # 显示详细信息
                                with st.expander("查看详细分析过程"):
                                    st.text(message)
                                
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
                                st.error("多表增强SQL生成失败")
                                st.error(message)
                                st.session_state.current_sql_v23 = ""
                                st.session_state.query_results_v23 = None
                    else:
                        st.warning("请输入问题")
            else:
                st.info("多表增强功能未启用")
                st.caption("需要导入V2.3多表增强模块")
    '''
    
    return multi_table_button_code

def get_enhanced_sql_query_page_layout():
    """获取增强的SQL查询页面布局代码"""
    
    layout_code = '''
        # V2.3增强：显示性能指标和多表查询选项
        col_gen, col_multi, col_perf = st.columns([2, 1, 1])
        
        with col_gen:
            if st.button("生成SQL查询 (V2.3增强)", type="primary"):
                # 标准SQL生成逻辑...
                pass
        
        with col_multi:
            # 多表查询增强按钮
            multi_table_available = hasattr(system, 'structured_prompt_builder') and system.structured_prompt_builder is not None
            
            if multi_table_available:
                if st.button("🔗 多表增强", type="secondary", help="使用分步推理的多表查询增强功能"):
                    # 多表增强逻辑...
                    pass
            else:
                st.info("💡 多表增强")
                st.caption("需要V2.3增强模块")
        
        with col_perf:
            # 性能指标显示
            if st.session_state.query_results_v23:
                exec_time = st.session_state.query_results_v23.get('exec_time', 0)
                st.metric("执行时间", f"{exec_time:.2f}s")
            
            cache_hits = len(system.sql_cache.cache)
            st.metric("缓存命中", cache_hits)
    '''
    
    return layout_code

def create_multi_table_examples():
    """创建多表查询示例"""
    
    examples = {
        "教育系统多表查询": [
            "查询每个学生的所有课程成绩",
            "统计各班级学生的平均成绩",
            "查询数学成绩大于90分的学生姓名和班级",
            "统计每个教师教授的课程数量",
            "查询选修了'数学'课程的所有学生信息"
        ],
        "电商系统多表查询": [
            "查询每个客户的订单总金额",
            "统计各商品的销售数量",
            "查询购买了特定商品的客户信息",
            "统计每个月的销售额",
            "查询库存不足的商品及其供应商"
        ],
        "人事系统多表查询": [
            "查询每个部门的员工数量和平均薪资",
            "统计各职位的薪资范围",
            "查询入职时间超过5年的员工信息",
            "统计每个部门的绩效分布",
            "查询薪资最高的前10名员工"
        ]
    }
    
    return examples

def get_multi_table_help_text():
    """获取多表查询帮助文本"""
    
    help_text = """
    ### 🔗 多表查询增强功能说明
    
    **V2.3多表增强特性：**
    - **分步推理**: AI按步骤分析表关系和字段归属
    - **关系验证**: 自动验证表间关联的正确性
    - **智能修正**: 发现错误时自动修正SQL
    - **性能评估**: 提供SQL质量评分和优化建议
    
    **适用场景：**
    - 涉及2个或以上表的查询
    - 包含JOIN操作的复杂查询
    - 需要聚合统计的跨表查询
    - 业务逻辑复杂的关联查询
    
    **使用建议：**
    1. 确保相关表已导入知识库
    2. 配置好表间关联关系
    3. 使用明确的业务术语描述需求
    4. 查看分析过程了解AI推理逻辑
    """
    
    return help_text

if __name__ == "__main__":
    print("TEXT2SQL V2.3 多表查询UI补丁")
    print("使用方法：")
    print("1. 导入此模块")
    print("2. 调用相应函数获取代码片段")
    print("3. 集成到主系统中")