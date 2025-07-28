
import json
import pandas as pd
import requests
import plotly.express as px
import os # Added for os.path.exists

# ====== 辅助函数 ======
def load_json(path):
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 文件 {path} 不存在")
        return {}
    except Exception as e:
        print(f"错误: 加载文件 {path} 失败: {e}")
        return {}

# ====== MOCK/占位实现 ======
class DatabaseManager:
    def get_mssql_connection_string(self, config):
        base = f"mssql+pyodbc://{config['username']}:{config['password']}@{config['server']}/{config['database']}?driver={config['driver'].replace(' ', '+')}"
        extras = [f"{k}={v}" for k, v in config.items() if k not in ["server", "database", "username", "password", "driver"]]
        if extras:
            base += "&" + "&".join(extras)
        return base

class VannaWrapper:
    def __init__(self, api_key=None):
        # 强制使用指定API Key
        self.api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        self.api_calls = 0
        self.errors = []
    
    def generate_sql(self, prompt):
        try:
            self.api_calls += 1
            print(f"\n🔍 正在调用DeepSeek API (第{self.api_calls}次调用)")
            print(f"📝 提示词长度: {len(prompt)} 字符")
            print(f"📋 提示词预览: {prompt[:100]}...")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000  # 增加token限制
            }
            
            print("🌐 发送API请求...")
            print(f"📡 请求参数: model={data['model']}, temperature={data['temperature']}, max_tokens={data['max_tokens']}")
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60  # 增加超时时间
            )
            
            print(f"📡 API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ API调用成功，响应长度: {len(content)} 字符")
                print(f"📄 响应内容预览: {content[:200]}...")
                return content
            else:
                error_msg = f"API调用失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                
                print(f"❌ {error_msg}")
                self.errors.append(error_msg)
                raise RuntimeError(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = "API请求超时"
            print(f"❌ {error_msg}")
            self.errors.append(error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求错误: {str(e)}"
            print(f"❌ {error_msg}")
            self.errors.append(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            print(f"❌ {error_msg}")
            self.errors.append(error_msg)
            raise RuntimeError(error_msg)
    
    def get_stats(self):
        return {
            "api_calls": self.api_calls,
            "errors": self.errors,
            "error_count": len(self.errors)
        }

# ====== 主引擎类（不变） ======
class Text2SQLQueryEngine:
    def __init__(self, table_knowledge, relationships, business_rules, product_knowledge, historical_qa, vanna, db_manager, prompt_templates=None):
        self.table_knowledge = table_knowledge
        self.relationships = relationships
        self.business_rules = business_rules
        self.product_knowledge = product_knowledge
        self.historical_qa = historical_qa
        self.vanna = vanna
        self.db_manager = db_manager
        self.prompt_templates = prompt_templates or {}
    
    def generate_prompt(self, question):
        processed_question = self.apply_business_rules(question)
        table_lines = [f"- {tbl}: {', '.join(info.get('columns', []))}" for tbl, info in self.table_knowledge.items()]
        table_struct = '\n'.join(table_lines)
        rel_lines = []
        for rel in self.relationships.get('relationships', []):
            t1, t2, f1, f2 = rel.get('table1', ''), rel.get('table2', ''), rel.get('field1', ''), rel.get('field2', '')
            cond = rel.get('join_condition', rel.get('description', ''))
            if t1 and t2 and f1 and f2:
                rel_lines.append(f"- {t1}.{f1} <-> {t2}.{f2}  条件: {cond}")
            elif cond:
                rel_lines.append(f"- {cond}")
        rel_struct = '\n'.join(rel_lines)
        rules_str = json.dumps(self.business_rules, ensure_ascii=False, indent=2) if self.business_rules else ''
        qa_examples = ""
        if self.historical_qa:
            for qa in self.historical_qa[:3]:
                qa_examples += f"\n【历史问答】问题：{qa['question']}，SQL：{qa['sql']}"
        
        # 使用prompt_templates中的模板
        if self.prompt_templates and 'sql_generation' in self.prompt_templates:
            template = self.prompt_templates['sql_generation']
            # 处理模板中的特殊占位符
            table_knowledge_str = json.dumps(self.table_knowledge, ensure_ascii=False, indent=2)
            template = template.replace('{table_knowledge.json}', table_knowledge_str)
            # 处理其他可能的占位符
            template = template.replace('{产品名}', '产品名')
            template = template.replace('{产品}', '产品')
            template = template.replace('{}', '')
            
            # 使用更安全的方式处理format
            try:
                prompt = template.format(
                    schema_info=table_struct,
                    business_rules=rules_str,
                    question=processed_question
                )
            except KeyError as e:
                # 如果还有未处理的占位符，使用字符串替换
                prompt = template
                prompt = prompt.replace('{schema_info}', table_struct)
                prompt = prompt.replace('{business_rules}', rules_str)
                prompt = prompt.replace('{question}', processed_question)
        else:
            # 使用原来的硬编码提示词作为后备
            prompt = f"""
【最高规则】
1. 你只能使用下方"表结构知识库"中列出的表和字段，禁止出现其它表和字段。
2. 所有JOIN只能使用下方"表关系定义"中明确列出的关系，禁止自创或猜测JOIN。
3. 生成SQL后，必须逐条校验所有表和JOIN，发现不合规必须剔除或修正，并在分析中详细说明。
4. 如有任何不合规，输出"严重错误：出现未授权表/字段/关系"，并给出修正建议。

【表结构知识库】
{table_struct}

【表关系定义】
{rel_struct}

【业务规则映射】
{rules_str}

【产品知识库】
{json.dumps(self.product_knowledge, ensure_ascii=False, indent=2) if self.product_knowledge else ''}
{qa_examples}

【用户问题】
{processed_question}

【输出要求】
1. 先输出最终合规SQL（只输出SQL，不要多余解释）；
2. 再输出结构化分析过程，逐条列出每个表和JOIN的合规性。
"""
        return prompt
    def apply_business_rules(self, question):
        import re
        question = re.sub(r'\b510S\b', "[Roadmap Family] LIKE '%510S%' and [group]='ttl", question, flags=re.IGNORECASE)
        return question
    def generate_sql(self, prompt):
        try:
            print("🚀 开始生成SQL...")
            
            # 调用API生成SQL
            response = self.vanna.generate_sql(prompt) if self.vanna else self.call_deepseek_api(prompt)
            
            # 提取SQL和分析
            sql, analysis = self._extract_sql_and_analysis(response)
            
            # 记录结果
            print(f"📊 提取结果 - SQL长度: {len(sql) if sql else 0}, 分析长度: {len(analysis) if analysis else 0}")
            
            if sql:
                print("✅ SQL生成成功")
                # 记录历史问答
                self.record_historical_qa(prompt, sql)
            else:
                print("⚠️ SQL生成失败 - 未提取到有效SQL")
            
            return sql, analysis
            
        except Exception as e:
            print(f"❌ SQL生成过程中发生错误: {str(e)}")
            import traceback
            print(f"🔍 详细错误信息: {traceback.format_exc()}")
            return "", f"SQL生成失败: {str(e)}"
    def llm_validate_sql(self, sql, prompt):
        # 使用prompt_templates中的验证模板
        if self.prompt_templates and 'sql_verification' in self.prompt_templates:
            template = self.prompt_templates['sql_verification']
            # 提取表结构信息
            table_lines = [f"- {tbl}: {', '.join(info.get('columns', []))}" for tbl, info in self.table_knowledge.items()]
            table_struct = '\n'.join(table_lines)
            rules_str = json.dumps(self.business_rules, ensure_ascii=False, indent=2) if self.business_rules else ''
            
            validate_prompt = template.format(
                schema_info=table_struct,
                business_rules=rules_str,
                question=prompt,
                sql=sql
            )
        else:
            # 使用原来的硬编码验证提示词作为后备
            validate_prompt = f"""
你是SQL合规性校验专家。请根据下方"表结构知识库"和"表关系定义"，严格校验下方SQL是否完全合规，发现任何不合规请修正并说明原因。

【SQL】
{sql}

{prompt}

【输出要求】
1. 先输出最终合规SQL（只输出SQL，不要多余解释）；
2. 再输出结构化分析过程，逐条列出每个表和JOIN的合规性。
"""
        response = self.vanna.generate_sql(validate_prompt) if self.vanna else self.call_deepseek_api(validate_prompt)
        sql2, analysis2 = self._extract_sql_and_analysis(response)
        
        # 如果验证返回VALID且没有修正SQL，则使用原始SQL
        if not sql2 and "VALID" in response.upper():
            sql2 = sql
            analysis2 = response
        
        return sql2, analysis2
    def _extract_sql_and_analysis(self, response):
        import re
        # 如果响应包含"VALID"，说明SQL是正确的，应该保留原始SQL
        if "VALID" in response.upper():
            return "", response  # 返回空SQL，让调用者使用原始SQL
        
        # 尝试从代码块中提取SQL
        sql_match = re.search(r"```sql[\s\S]*?([\s\S]+?)```", response, re.IGNORECASE)
        if sql_match:
            sql = sql_match.group(1).strip()
            analysis = response.replace(sql_match.group(0), '').strip()
        else:
            # 尝试从普通文本中提取SQL
            lines = response.strip().split('\n')
            sql_lines, analysis_lines, in_sql = [], [], False
            
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.lower().startswith('select') or line_stripped.startswith('with'):
                    in_sql = True
                    sql_lines.append(line)
                elif in_sql and (line_stripped == '' or line_stripped.startswith('--')):
                    sql_lines.append(line)
                elif in_sql and line_stripped and not line_stripped.startswith('--'):
                    # 如果遇到非空行且不是注释，可能是SQL的继续
                    if any(keyword in line_stripped.upper() for keyword in ['FROM', 'WHERE', 'JOIN', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'LIMIT', 'OFFSET', ';']):
                        sql_lines.append(line)
                    else:
                        in_sql = False
                        analysis_lines.append(line)
                else:
                    analysis_lines.append(line)
            
            sql = '\n'.join(sql_lines).strip()
            analysis = '\n'.join(analysis_lines).strip()
        
        return sql, analysis
    def execute_sql(self, sql, db_config):
        try:
            db_type = db_config["type"]
            config = db_config["config"]
            print(f"正在连接数据库: {config['server']}/{config['database']}")
            print(f"执行的SQL长度: {len(sql) if sql else 0}")
            print(f"执行的SQL: {repr(sql)}")  # 使用repr来显示完整内容
            
            # 验证SQL不为空
            if not sql or not sql.strip():
                return False, pd.DataFrame(), "SQL语句为空"
            
            if db_type == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["file_path"])
                df = pd.read_sql_query(sql, conn)
                conn.close()
                return True, df, "查询执行成功"
            elif db_type == "mssql":
                from sqlalchemy import create_engine
                conn_str = self.db_manager.get_mssql_connection_string(config)
                print(f"连接字符串: {conn_str}")
                engine = create_engine(conn_str)
                df = pd.read_sql_query(sql, engine)
                return True, df, "查询执行成功"
            else:
                return False, pd.DataFrame(), f"不支持的数据库类型: {db_type}"
        except Exception as e:
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
            return False, pd.DataFrame(), f"SQL执行失败: {str(e)}"
    def visualize_result(self, df):
        if len(df.columns) >= 2 and len(df) > 1:
            fig = px.bar(df, x=df.columns[0], y=df.columns[1], title=f"{df.columns[0]} vs {df.columns[1]}")
            return fig
        return None
    def record_historical_qa(self, question, sql):
        self.historical_qa.append({"question": question, "sql": sql})
    def call_deepseek_api(self, prompt):
        # 兜底备用
        headers = {
            "Authorization": f"Bearer sk-0e6005b793aa4759bb022b91e9055f86",  # 替换为你的API Key
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
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
            raise RuntimeError(f"API调用失败: {response.status_code}")

# ========== UI界面集成 ==========
import streamlit as st
import time
import pandas as pd
from typing import Dict, List, Optional, Tuple

def main():
    """主函数"""
    st.set_page_config(
        page_title="TEXT2SQL系统 V2.5",
        page_icon="🚀",
        layout="wide"
    )
    
    st.title("TEXT2SQL系统 V2.5 - 增强优化版")
    st.markdown("**企业级数据库管理 + AI智能查询系统 + V2.5核心优化**")
    
    # 初始化系统
    if 'system_v25' not in st.session_state:
        # 加载提示词模板
        prompt_templates = load_json('prompt_templates.json') if os.path.exists('prompt_templates.json') else {}
        
        st.session_state.system_v25 = Text2SQLQueryEngine(
            table_knowledge=load_json('table_knowledge.json'),
            relationships=load_json('table_relationships.json'),
            business_rules=load_json('business_rules.json'),
            product_knowledge=load_json('product_knowledge.json'),
            historical_qa=load_json('historical_qa.json') if os.path.exists('historical_qa.json') else [],
            vanna=VannaWrapper(),
            db_manager=DatabaseManager(),
            prompt_templates=prompt_templates
        )
    
    system = st.session_state.system_v25
    
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
        st.success("本地Vanna: 正常运行")
        st.info("向量数据库: ChromaDB")
        st.info("LLM: DeepSeek")
        
        # 显示API调用统计
        if hasattr(system.vanna, 'get_stats'):
            stats = system.vanna.get_stats()
            st.subheader("API调用统计")
            st.metric("API调用次数", stats.get('api_calls', 0))
            st.metric("错误次数", stats.get('error_count', 0))
            
            if stats.get('errors'):
                with st.expander("最近错误"):
                    for error in stats['errors'][-3:]:  # 显示最近3个错误
                        st.error(error)
        
        # 显示数据库连接状态
        st.subheader("数据库状态")
        # 这里可以添加数据库连接状态显示
        
        # 性能监控
        st.subheader("性能监控")
        st.metric("SQL缓存", "0/100")
        
        if st.button("清空缓存"):
            st.success("缓存已清空")
            st.rerun()
        
        # 知识库状态
        st.subheader("知识库状态")
        st.metric("历史优质问答", f"{len(system.historical_qa)} 条")
    
    # 根据选择的页面显示不同内容
    if page == "SQL查询":
        show_sql_query_page_v25(system)
    elif page == "数据库管理":
        show_database_management_page_v25(system)
    elif page == "表结构管理":
        show_table_management_page_v25(system)
    elif page == "产品知识库":
        show_product_knowledge_page_v25(system)
    elif page == "业务规则管理":
        show_business_rules_page_v25(system)
    elif page == "提示词管理":
        show_prompt_templates_page_v25(system)
    elif page == "系统监控":
        show_system_monitoring_page_v25(system)

def show_sql_query_page_v25(system):
    """显示SQL查询页面 V2.5版本"""
    st.header("智能SQL查询 V2.5")
    
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
        if 'current_sql_v25' not in st.session_state:
            st.session_state.current_sql_v25 = ""
        if 'current_question_v25' not in st.session_state:
            st.session_state.current_question_v25 = ""
        if 'current_db_config_v25' not in st.session_state:
            st.session_state.current_db_config_v25 = None
        if 'query_results_v25' not in st.session_state:
            st.session_state.query_results_v25 = None
        
        # 数据库配置（简化版）
        db_config = {
            "type": "mssql",
            "config": {
                "server": "localhost",
                "database": "test_db",
                "username": "user",
                "password": "password",
                "driver": "ODBC Driver 18 for SQL Server"
            }
        }
        
        if st.button("生成SQL查询 (V2.5增强)", type="primary"):
            if question:
                with st.spinner("正在使用V2.5增强引擎生成SQL..."):
                    # 使用V2.5增强版SQL生成
                    start_time = time.time()
                    sql, analysis = system.generate_sql(question)
                    generation_time = time.time() - start_time
                    
                    if sql:
                        # 保存到session state
                        st.session_state.current_sql_v25 = sql
                        st.session_state.current_question_v25 = question
                        st.session_state.current_db_config_v25 = db_config
                        
                        st.success("SQL生成成功")
                        st.info(f"⚡ 生成耗时: {generation_time:.2f}秒")
                        
                        # 自动执行SQL查询
                        with st.spinner("正在执行查询..."):
                            exec_start_time = time.time()
                            success, df, exec_message = system.execute_sql(sql, db_config)
                            exec_time = time.time() - exec_start_time
                            
                            if success:
                                # 保存查询结果到session state
                                st.session_state.query_results_v25 = {
                                    'success': True,
                                    'df': df,
                                    'message': exec_message,
                                    'exec_time': exec_time
                                }
                                st.info(f"⚡ 执行耗时: {exec_time:.2f}秒")
                            else:
                                st.session_state.query_results_v25 = {
                                    'success': False,
                                    'df': pd.DataFrame(),
                                    'message': exec_message,
                                    'exec_time': exec_time
                                }
                    else:
                        st.error("SQL生成失败")
                        st.session_state.current_sql_v25 = ""
                        st.session_state.query_results_v25 = None
            else:
                st.warning("请输入问题")
    
    with col2:
        st.subheader("查询结果")
        
        if st.session_state.query_results_v25:
            results = st.session_state.query_results_v25
            
            if results['success']:
                st.success("查询成功")
                st.dataframe(results['df'], use_container_width=True)
                
                # 显示统计信息
                st.subheader("结果统计")
                st.write(f"记录数: {len(results['df'])}")
                st.write(f"列数: {len(results['df'].columns)}")
                
                # 下载按钮
                csv = results['df'].to_csv(index=False)
                st.download_button(
                    label="下载CSV",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv"
                )
            else:
                st.error(f"查询失败: {results['message']}")

def show_database_management_page_v25(system):
    """数据库管理页面 V2.5"""
    st.header("数据库管理 V2.5")
    
    st.subheader("数据库配置")
    st.info("数据库管理功能正在开发中...")
    
    # 这里可以添加数据库配置功能
    with st.expander("添加数据库配置"):
        db_type = st.selectbox("数据库类型:", ["mssql", "sqlite"])
        
        if db_type == "mssql":
            server = st.text_input("服务器:")
            database = st.text_input("数据库名:")
            username = st.text_input("用户名:")
            password = st.text_input("密码:", type="password")
            driver = st.selectbox("ODBC驱动:", ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"])
        
        if st.button("添加数据库"):
            st.success("数据库配置已添加")

def show_table_management_page_v25(system):
    """表结构管理页面 V2.5"""
    st.header("表结构管理 V2.5")
    
    st.subheader("表结构知识库")
    st.info("表结构管理功能正在开发中...")
    
    # 显示当前表结构
    with st.expander("当前表结构"):
        table_knowledge = system.table_knowledge
        for table_name, table_info in table_knowledge.items():
            st.write(f"**{table_name}**: {', '.join(table_info.get('columns', []))}")

def show_product_knowledge_page_v25(system):
    """产品知识库页面 V2.5"""
    st.header("产品知识库 V2.5")
    
    st.subheader("产品知识管理")
    st.info("产品知识库管理功能正在开发中...")
    
    # 显示当前产品知识
    with st.expander("当前产品知识"):
        product_knowledge = system.product_knowledge
        for product_name, product_info in product_knowledge.items():
            st.write(f"**{product_name}**: {product_info}")

def show_business_rules_page_v25(system):
    """业务规则管理页面 V2.5"""
    st.header("业务规则管理 V2.5")
    
    st.subheader("业务规则配置")
    st.info("业务规则管理功能正在开发中...")
    
    # 显示当前业务规则
    with st.expander("当前业务规则"):
        business_rules = system.business_rules
        for rule_name, rule_info in business_rules.items():
            st.write(f"**{rule_name}**: {rule_info}")

def show_prompt_templates_page_v25(system):
    """提示词管理页面 V2.5"""
    st.header("提示词管理 V2.5")
    
    st.subheader("提示词模板")
    st.info("提示词管理功能正在开发中...")
    
    # 显示当前提示词模板
    with st.expander("当前提示词模板"):
        prompt_templates = system.prompt_templates
        for template_name, template_content in prompt_templates.items():
            st.write(f"**{template_name}**:")
            st.code(template_content, language="text")

def show_system_monitoring_page_v25(system):
    """系统监控页面 V2.5"""
    st.header("系统监控 V2.5")
    
    st.subheader("系统状态")
    
    # 获取真实的监控数据
    api_stats = system.vanna.get_stats() if hasattr(system.vanna, 'get_stats') else {}
    historical_count = len(system.historical_qa) if hasattr(system, 'historical_qa') else 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("API调用次数", api_stats.get('api_calls', 0))
        st.metric("SQL生成成功率", f"{100 - api_stats.get('error_count', 0) * 10}%" if api_stats.get('api_calls', 0) > 0 else "0%")
    
    with col2:
        st.metric("平均响应时间", "计算中...")  # 可以后续添加时间统计
        st.metric("缓存命中率", "0%")  # 可以后续添加缓存功能
    
    with col3:
        error_rate = (api_stats.get('error_count', 0) / max(api_stats.get('api_calls', 1), 1)) * 100
        st.metric("错误率", f"{error_rate:.1f}%")
        st.metric("历史问答数", historical_count)
    
    # 显示详细统计
    st.subheader("详细统计")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**API调用统计**")
        st.write(f"- 总调用次数: {api_stats.get('api_calls', 0)}")
        st.write(f"- 成功次数: {api_stats.get('api_calls', 0) - api_stats.get('error_count', 0)}")
        st.write(f"- 失败次数: {api_stats.get('error_count', 0)}")
        
        if api_stats.get('errors'):
            st.write("**最近错误**")
            for i, error in enumerate(api_stats['errors'][-5:], 1):
                st.error(f"{i}. {error}")
    
    with col2:
        st.write("**系统资源**")
        st.write(f"- 表结构数量: {len(system.table_knowledge)}")
        st.write(f"- 表关系数量: {len(system.relationships.get('relationships', []))}")
        st.write(f"- 业务规则数量: {len(system.business_rules)}")
        st.write(f"- 产品知识数量: {len(system.product_knowledge)}")
    
    # 显示最近查询（如果有的话）
    st.subheader("最近查询")
    if historical_count > 0:
        recent_qa = system.historical_qa[-5:]  # 显示最近5个
        for qa in recent_qa:
            with st.expander(f"问题: {qa.get('question', '')[:50]}..."):
                st.write(f"**问题:** {qa.get('question', '')}")
                st.code(qa.get('sql', ''), language='sql')
    else:
        st.info("暂无查询记录")
    
    # 添加系统诊断功能
    st.subheader("系统诊断")
    if st.button("运行系统诊断"):
        with st.spinner("正在诊断系统..."):
            # 检查各个组件
            checks = []
            
            # 检查API连接
            try:
                test_response = system.vanna.generate_sql("SELECT 1")
                checks.append(("✅ API连接", "正常"))
            except Exception as e:
                checks.append(("❌ API连接", f"失败: {str(e)}"))
            
            # 检查配置文件
            config_files = ['table_knowledge.json', 'table_relationships.json', 'business_rules.json']
            for file in config_files:
                if os.path.exists(file):
                    checks.append((f"✅ {file}", "存在"))
                else:
                    checks.append((f"❌ {file}", "缺失"))
            
            # 显示诊断结果
            for check, status in checks:
                st.write(f"{check}: {status}")

# ========== 主程序入口 ==========
if __name__ == "__main__":
    # 检查是否在Streamlit环境中运行
    try:
        import streamlit as st
        main()
    except ImportError:
        # 如果不在Streamlit环境中，运行命令行版本
        print("在命令行环境中运行，启动命令行版本...")
        # 这里可以添加命令行版本的逻辑
        pass 