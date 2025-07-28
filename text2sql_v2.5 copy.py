
import json
import pandas as pd
import requests
import plotly.express as px

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
    def generate_sql(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
        response = self.vanna.generate_sql(prompt) if self.vanna else self.call_deepseek_api(prompt)
        sql, analysis = self._extract_sql_and_analysis(response)
        return sql, analysis
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
                    if any(keyword in line_stripped.upper() for keyword in ['FROM', 'WHERE', 'JOIN', 'GROUP', 'ORDER', 'HAVING', 'UNION']):
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

# ========== 主流程可运行示例 ========== 
if __name__ == "__main__":
    # 1. 加载知识库
    def load_json(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 路径修正示例：
    # with open('text2sql/table_knowledge.json', ...) -> with open('table_knowledge.json', ...)
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    try:
        historical_qa = load_json('historical_qa.json')
    except:
        historical_qa = []
    # 加载提示词模板
    try:
        prompt_templates = load_json('prompt_templates.json')
    except:
        prompt_templates = {}
    # 2. 初始化依赖
    db_manager = DatabaseManager()
    vanna = VannaWrapper()  # 不再需要传api_key
    # 3. 构造db_config和输入问题
    db_config = {
        "type": "mssql",
        "config": {
            "server": "10.97.34.39",
            "database": "FF_IDSS_Dev_FF",
            "username": "FF_User",
            "password": "Grape!0808",
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": "no",
            "trust_server_certificate": "yes"
        }
    }
  

    question = "GEEK产品2025年7月的全链库存、MTM和未清PO信息"
    # 4. 主流程
    engine = Text2SQLQueryEngine(
        table_knowledge, relationships, business_rules,
        product_knowledge, historical_qa, vanna, db_manager, prompt_templates
    )
    prompt = engine.generate_prompt(question)
    print("\n==== LLM Prompt ====")
    print(prompt)
    sql, analysis = engine.generate_sql(prompt)
    print("\n==== LLM SQL ====")
    print(sql)
    print("\n==== LLM 分析 ====")
    print(analysis)
    sql2, analysis2 = engine.llm_validate_sql(sql, prompt)
    print("\n==== LLM 校验后SQL ====")
    print(sql2)
    print("\n==== LLM 校验分析 ====")
    print(analysis2)
    success, df, msg = engine.execute_sql(sql2, db_config)
    print("\n==== SQL执行 ====")
    print(msg)
    if success:
        print(df.head())
        fig = engine.visualize_result(df)
        if fig:
            fig.show()
    engine.record_historical_qa(question, sql2) 