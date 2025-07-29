import json
import pandas as pd
import requests
import plotly.express as px
import os

# ====== MOCK/占位实现 ======
class DatabaseManager:
    def get_mssql_connection_string(self, config):
        base = f"mssql+pyodbc://{config['username']}:{config['password']}@{config['server']}/{config['database']}?driver={config['driver'].replace(' ', '+')}"
        extras = [f"{k}={v}" for k, v in config.items() if k not in ["server", "database", "username", "password", "driver"]]
        if extras:
            base += "&" + "&".join(extras)
        return base

    def test_connection(self, db_type, config):
        try:
            if db_type == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["file_path"])
                conn.close()
                return True, "SQLite连接成功"
            elif db_type == "mssql":
                from sqlalchemy import create_engine, text
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True, "MSSQL连接成功"
            else:
                return False, "不支持的数据库类型"
        except Exception as e:
            return False, f"连接失败: {e}"

    def get_tables(self, db_type, config):
        try:
            if db_type == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["file_path"])
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                return tables
            elif db_type == "mssql":
                from sqlalchemy import create_engine, text
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"))
                    tables = [row[0] for row in result.fetchall()]
                return tables
            else:
                return []
        except Exception as e:
            print(f"获取表列表失败: {e}")
            return []

    def get_table_schema(self, db_type, config, table_name):
        try:
            if db_type == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["file_path"])
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]
                conn.close()
                return {"columns": columns, "column_info": []}
            elif db_type == "mssql":
                from sqlalchemy import create_engine, text
                conn_str = self.get_mssql_connection_string(config)
                engine = create_engine(conn_str)
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table_name}'"))
                    columns = [row[0] for row in result.fetchall()]
                return {"columns": columns, "column_info": []}
            else:
                return {"columns": [], "column_info": []}
        except Exception as e:
            print(f"获取表结构失败: {e}")
            return {"columns": [], "column_info": []}

class VannaWrapper:
    def __init__(self, api_key=None):
        self.api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
        self.training_data = []  # 存储训练数据
    
    def train(self, ddl=None, documentation=None, question=None, sql=None):
        """训练Vanna模型"""
        training_item = {}
        if ddl:
            training_item['ddl'] = ddl
        if documentation:
            training_item['documentation'] = documentation
        if question and sql:
            training_item['question'] = question
            training_item['sql'] = sql
        
        if training_item:
            self.training_data.append(training_item)
            print(f"训练数据已添加: {training_item}")
    
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
        # 兼容V2.4 UI
        self.databases = {}
        self.sql_cache = type('SqlCache', (), {'cache': {}, 'access_count': {}})()
    def check_table_has_time_fields(self, table_name):
        """检查表是否包含时间字段（年、月、日等）"""
        if table_name not in self.table_knowledge:
            return False
        
        time_field_patterns = [
            '年', '月', '日', '周', '财年', '财月', '财周', '自然年', '自然月',
            'year', 'month', 'day', 'week', 'fiscal_year', 'fiscal_month', 'fiscal_week'
        ]
        
        columns = self.table_knowledge[table_name].get('columns', [])
        for col in columns:
            if isinstance(col, dict):
                field_name = col.get('name', '').lower()
            elif isinstance(col, str):
                field_name = col.lower()
            else:
                continue
                
            # 检查字段名是否包含时间模式
            for pattern in time_field_patterns:
                if pattern in field_name:
                    return True
        
        return False
    
    def get_tables_without_time_fields(self):
        """获取不包含时间字段的表列表"""
        tables_without_time = []
        for table_name in self.table_knowledge:
            if not self.check_table_has_time_fields(table_name):
                tables_without_time.append(table_name)
        return tables_without_time
    
    def generate_prompt(self, question, target_table=None):
        processed_question = self.apply_business_rules(question, target_table)
        
        # 检查表的时间字段情况
        tables_without_time = self.get_tables_without_time_fields()
        time_field_warning = ""
        if tables_without_time:
            time_field_warning = f"""
【重要提醒：无时间字段的表】
以下表不包含时间字段（年、月、日等），生成SQL时不应添加时间条件：
{', '.join(tables_without_time)}

注意：如果查询涉及这些表，请勿添加时间相关的WHERE条件。
"""
        
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
        if self.prompt_templates and 'sql_generation' in self.prompt_templates:
            template = self.prompt_templates['sql_generation']
            table_knowledge_str = json.dumps(self.table_knowledge, ensure_ascii=False, indent=2)
            template = template.replace('{table_knowledge.json}', table_knowledge_str)
            template = template.replace('{产品名}', '产品名')
            template = template.replace('{产品}', '产品')
            template = template.replace('{}', '')
            try:
                prompt = template.format(
                    schema_info=table_struct,
                    business_rules=rules_str,
                    question=processed_question
                )
            except KeyError as e:
                prompt = template
                prompt = prompt.replace('{schema_info}', table_struct)
                prompt = prompt.replace('{business_rules}', rules_str)
                prompt = prompt.replace('{question}', processed_question)
        else:
            prompt = f"""
【最高规则】
1. 你只能使用下方"表结构知识库"中列出的表和字段，禁止出现其它表和字段。
2. 所有JOIN只能使用下方"表关系定义"中明确列出的关系，禁止自创或猜测JOIN。
3. 生成SQL后，必须逐条校验所有表和JOIN，发现不合规必须剔除或修正，并在分析中详细说明。
4. 如有任何不合规，输出"严重错误：出现未授权表/字段/关系"，并给出修正建议。
5. 特别注意：如果查询的表不包含时间字段，则不应添加时间相关的WHERE条件。

{time_field_warning}

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
3. 特别注意检查是否在不包含时间字段的表中添加了时间条件。
"""
        return prompt
    def apply_business_rules(self, question, target_table=None):
        """应用业务规则转换，支持表限制"""
        import re
        
        # 加载业务规则元数据
        business_rules_meta = {}
        try:
            if os.path.exists("business_rules_meta.json"):
                with open("business_rules_meta.json", 'r', encoding='utf-8') as f:
                    business_rules_meta = json.load(f)
        except:
            pass
        
        processed_question = question
        
        # 应用业务规则
        for business_term, db_term in self.business_rules.items():
            # 确保db_term是字符串类型
            if not isinstance(db_term, str):
                continue
                
            # 检查表限制
            meta_info = business_rules_meta.get(business_term, {})
            table_restriction = meta_info.get('table_restriction')
            
            # 如果没有表限制，或者目标表匹配，则应用规则
            if table_restriction is None or target_table == table_restriction:
                processed_question = processed_question.replace(business_term, db_term)
        
        return processed_question
    def generate_sql(self, prompt):
        response = self.vanna.generate_sql(prompt) if self.vanna else self.call_deepseek_api(prompt)
        sql, analysis = self._extract_sql_and_analysis(response)
        return sql, analysis
    def get_related_table_info(self, sql):
        import re
        table_info = self.table_knowledge
        table_pattern = r'FROM\s+([\w\[\]\.]+)'
        join_pattern = r'JOIN\s+([\w\[\]\.]+)'
        tables = re.findall(table_pattern, sql, re.IGNORECASE) + re.findall(join_pattern, sql, re.IGNORECASE)
        related = {}
        for table in tables:
            table_clean = table.split('.')[-1].replace('[', '').replace(']', '')
            if table_clean in table_info:
                related[table_clean] = table_info[table_clean]
        return related

    def llm_validate_sql(self, sql, prompt):
        """使用LLM校验SQL，只进行校验不修改"""
        try:
            # 检查SQL中涉及的表是否包含时间字段
            tables_in_sql = self.extract_tables_from_sql(sql)
            time_field_validation = self.validate_time_conditions(sql, tables_in_sql)
            
            # 构建校验提示词
            validation_prompt = f"""
你是一个SQL专家。请对以下SQL进行校验分析，但不要修改SQL。

【原始SQL】
{sql}

【表结构知识库】
{json.dumps(self.table_knowledge, ensure_ascii=False, indent=2)}

【表关系定义】
{json.dumps(self.relationships, ensure_ascii=False, indent=2)}

【时间字段检查结果】
{time_field_validation}

【校验要求】
1. 检查SQL语法是否正确
2. 检查所有表名和字段名是否存在于知识库中
3. 检查JOIN条件是否使用了正确的表关系
4. 检查时间条件是否与表结构匹配
5. 如果表不包含时间字段，则不应有该表的时间条件
6. 只进行校验分析，不要修改SQL

【输出格式】
请输出详细的校验分析，包括：
- 语法检查结果
- 字段存在性检查
- 表关系检查
- 时间条件合理性检查
- 总体评价
"""
            
            # 调用LLM进行校验
            response = self.call_deepseek_api(validation_prompt)
            
            if response and not response.startswith("API调用失败"):
                return sql, response
            else:
                return sql, f"SQL校验失败：{response}"
                
        except Exception as e:
            return sql, f"SQL校验过程中出现错误：{str(e)}"
    
    def extract_tables_from_sql(self, sql):
        """从SQL中提取表名"""
        import re
        tables = []
        
        # 提取FROM和JOIN中的表名
        from_pattern = r'FROM\s+([\w\[\]\.]+)'
        join_pattern = r'JOIN\s+([\w\[\]\.]+)'
        
        for pattern in [from_pattern, join_pattern]:
            for match in re.findall(pattern, sql, re.IGNORECASE):
                # 提取表名（去掉数据库名和schema）
                table_name = match.split('.')[-1].replace('[', '').replace(']', '')
                tables.append(table_name)
        
        return list(set(tables))  # 去重
    
    def validate_time_conditions(self, sql, tables_in_sql):
        """验证SQL中的时间条件是否与表结构匹配"""
        import re
        
        # 检查SQL中的时间条件
        time_conditions = []
        time_patterns = [
            r'\[自然年\]', r'\[财年\]', r'\[财月\]', r'\[财周\]', r'\[年\]', r'\[月\]', r'\[日\]',
            r'YEAR\s*\(', r'MONTH\s*\(', r'GETDATE\s*\(', r'CAST\s*\(.*?AS.*?VARCHAR\s*\)'
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                time_conditions.append(pattern)
        
        if not time_conditions:
            return "SQL中未发现时间条件，无需检查。"
        
        # 检查每个表是否包含时间字段
        validation_results = []
        for table in tables_in_sql:
            has_time_fields = self.check_table_has_time_fields(table)
            if not has_time_fields and time_conditions:
                validation_results.append(f"⚠️ 警告：表[{table}]不包含时间字段，但SQL中包含时间条件")
            elif has_time_fields:
                validation_results.append(f"✅ 表[{table}]包含时间字段，时间条件合理")
            else:
                validation_results.append(f"✅ 表[{table}]不包含时间字段，且SQL中无时间条件")
        
        if validation_results:
            return "\n".join(validation_results)
        else:
            return "时间条件检查通过。"
    
    def enhanced_local_field_check(self, sql):
        """增强版本地字段校验，支持表别名和关系校验"""
        import re
        
        def norm_table_name(name):
            if '.' in name:
                name = name.split('.')[-1]
            return name.replace('[','').replace(']','').strip().lower()
        
        def norm_field_name(name):
            return name.replace('[','').replace(']','').strip().lower()
        
        # 1. 解析表别名映射
        alias2table = {}
        from_pattern = r'FROM\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
        join_pattern = r'JOIN\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
        for pat in [from_pattern, join_pattern]:
            for m in re.findall(pat, sql, re.IGNORECASE):
                table, alias = m
                alias2table[alias] = norm_table_name(table)
        
        # 2. 字段校验 - 检查所有字段引用
        field_results = []
        
        # 检查SELECT子句中的字段
        select_pattern = r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]'
        for alias, field in re.findall(select_pattern, sql):
            table = alias2table.get(alias)
            if not table:
                field_results.append(f"别名[{alias}]未找到对应表")
                continue
                
            matched_table = None
            for tk in self.table_knowledge:
                if norm_table_name(tk) == table:
                    matched_table = tk
                    break
            if not matched_table:
                field_results.append(f"表[{table}]未在知识库中定义")
                continue
                
            # 处理columns字段
            columns = []
            for col in self.table_knowledge[matched_table]['columns']:
                if isinstance(col, dict) and 'name' in col:
                    columns.append(norm_field_name(col['name']))
                elif isinstance(col, str):
                    columns.append(norm_field_name(col))
                    
            if norm_field_name(field) in columns:
                field_results.append(f"表[{matched_table}] 字段[{field}] (别名:{alias}) : 存在")
            else:
                field_results.append(f"表[{matched_table}] 字段[{field}] (别名:{alias}) : 不存在")
        
        # 检查WHERE子句中的字段
        where_pattern = r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)'
        where_match = re.search(where_pattern, sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1)
            # 提取WHERE中的字段引用
            where_field_pattern = r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]'
            for alias, field in re.findall(where_field_pattern, where_clause):
                table = alias2table.get(alias)
                if not table:
                    field_results.append(f"WHERE中别名[{alias}]未找到对应表")
                    continue
                    
                matched_table = None
                for tk in self.table_knowledge:
                    if norm_table_name(tk) == table:
                        matched_table = tk
                        break
                if not matched_table:
                    field_results.append(f"WHERE中表[{table}]未在知识库中定义")
                    continue
                    
                # 处理columns字段
                columns = []
                for col in self.table_knowledge[matched_table]['columns']:
                    if isinstance(col, dict) and 'name' in col:
                        columns.append(norm_field_name(col['name']))
                    elif isinstance(col, str):
                        columns.append(norm_field_name(col))
                        
                if norm_field_name(field) in columns:
                    field_results.append(f"WHERE中表[{matched_table}] 字段[{field}] (别名:{alias}) : 存在")
                else:
                    field_results.append(f"WHERE中表[{matched_table}] 字段[{field}] (别名:{alias}) : 不存在")
        
        # 检查没有表别名的字段引用 - 改进逻辑
        # 对于没有表别名的字段，我们需要更谨慎地判断
        simple_field_pattern = r'\[([^\]]+)\]'
        simple_fields = re.findall(simple_field_pattern, sql)
        
        # 过滤掉已经在带别名字段中处理过的字段
        aliased_fields = set()
        for alias, field in re.findall(select_pattern, sql):
            aliased_fields.add(field)
        for alias, field in re.findall(r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]', where_clause if where_match else ''):
            aliased_fields.add(field)
        
        simple_fields = [field for field in simple_fields if field not in aliased_fields]
        
        for field in simple_fields:
            # 跳过明显的表名、数据库名等
            if any(skip in field.lower() for skip in ['ff_idss', 'dbo', 'dtsupply', 'condt', 'commit', 'summary']):
                continue
            if '.' in field:
                continue
                
            # 检查是否在任何表中存在
            field_exists = False
            for table_name, table_info in self.table_knowledge.items():
                columns = []
                for col in table_info.get('columns', []):
                    if isinstance(col, dict) and 'name' in col:
                        columns.append(norm_field_name(col['name']))
                    elif isinstance(col, str):
                        columns.append(norm_field_name(col))
                
                if norm_field_name(field) in columns:
                    field_exists = True
                    field_results.append(f"表[{table_name}] 字段[{field}] (无别名) : 存在")
                    break
            
            # 如果字段在任何表中都不存在，但可能是业务术语，也不报错
            business_terms = ["未清PO数量", "本月备货", "全链库存", "自然年", "财月", "财周", "财年", "Model"]
            if field in business_terms:
                field_results.append(f"业务术语[{field}] : 跳过验证")
                continue
            
            if not field_exists:
                field_results.append(f"字段[{field}] (无别名) : 未在任何表中找到")
        
        # 3. 关系校验
        relationship_results = []
        if hasattr(self, 'relationships') and self.relationships:
            # 解析关系数据
            rel_list = []
            if isinstance(self.relationships, dict) and 'relationships' in self.relationships:
                for rel in self.relationships['relationships']:
                    desc = rel.get('description', '')
                    # 支持 =、<->、==、等于
                    m = re.match(r'([\w]+)\.([\w\s]+)\s*(=|<->|==|等于)\s*([\w]+)\.([\w\s]+)', desc)
                    if m:
                        t1, f1, _, t2, f2 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
                        rel_list.append({
                            'table1': norm_table_name(t1),
                            'field1': norm_field_name(f1),
                            'table2': norm_table_name(t2),
                            'field2': norm_field_name(f2)
                        })
                    else:
                        # 兜底用字段
                        rel_list.append({
                            'table1': norm_table_name(rel.get('table1','')),
                            'field1': norm_field_name(rel.get('field1','')),
                            'table2': norm_table_name(rel.get('table2','')),
                            'field2': norm_field_name(rel.get('field2',''))
                        })
            elif isinstance(self.relationships, list):
                # 直接是关系列表
                for rel in self.relationships:
                    desc = rel.get('description', '')
                    m = re.match(r'([\w]+)\.([\w\s]+)\s*(=|<->|==|等于)\s*([\w]+)\.([\w\s]+)', desc)
                    if m:
                        t1, f1, _, t2, f2 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
                        rel_list.append({
                            'table1': norm_table_name(t1),
                            'field1': norm_field_name(f1),
                            'table2': norm_table_name(t2),
                            'field2': norm_field_name(f2)
                        })
                    else:
                        rel_list.append({
                            'table1': norm_table_name(rel.get('table1','')),
                            'field1': norm_field_name(rel.get('field1','')),
                            'table2': norm_table_name(rel.get('table2','')),
                            'field2': norm_field_name(rel.get('field2',''))
                        })
            
            # 执行关系校验
            join_on_pattern = r'JOIN\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)\s+ON\s+([^\n]+)'
            for join_table, join_alias, on_clause in re.findall(join_on_pattern, sql, re.IGNORECASE):
                on_pairs = re.findall(r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]\s*=\s*([a-zA-Z0-9_]+)\.\[([^\]]+)\]', on_clause)
                for left_alias, left_field, right_alias, right_field in on_pairs:
                    left_table = alias2table.get(left_alias)
                    right_table = alias2table.get(right_alias)
                    if not left_table or not right_table:
                        relationship_results.append(f"关系校验: 别名[{left_alias}]或[{right_alias}]未找到对应表")
                        continue
                        
                    found = False
                    for rel in rel_list:
                        if (
                            (rel['table1'] == left_table and rel['table2'] == right_table and 
                             rel['field1'] == norm_field_name(left_field) and rel['field2'] == norm_field_name(right_field)) or
                            (rel['table2'] == left_table and rel['table1'] == right_table and 
                             rel['field2'] == norm_field_name(left_field) and rel['field1'] == norm_field_name(right_field))
                        ):
                            relationship_results.append(f"关系校验: {left_table}--{right_table} 字段[{left_field}]--[{right_field}] 匹配")
                            found = True
                            break
                    if not found:
                        relationship_results.append(f"关系校验: {left_table}--{right_table} 字段[{left_field}]--[{right_field}] 未在关系库中定义")
        
        # 4. 组合结果
        result_parts = []
        if field_results:
            result_parts.append("字段校验结果:\n" + "\n".join(field_results))
        if relationship_results:
            result_parts.append("关系校验结果:\n" + "\n".join(relationship_results))
        
        if not result_parts:
            return "本地校验：所有字段和关系均存在，校验通过。"
        
        # 返回详细的错误信息，便于LLM修正
        detailed_errors = []
        for result in result_parts:
            if "不存在" in result or "未找到" in result or "未在关系库中定义" in result:
                detailed_errors.append(result)
        
        if detailed_errors:
            return "本地校验发现问题：\n" + "\n\n".join(detailed_errors)
        else:
            return "本地校验：\n" + "\n\n".join(result_parts)

    def local_field_check(self, sql):
        import re
        # 1. 提取SQL中用到的表名
        table_pattern = r'FROM\s+([\w\[\]\.]+)|JOIN\s+([\w\[\]\.]+)'
        tables = re.findall(table_pattern, sql, re.IGNORECASE)
        table_names = set()
        for t1, t2 in tables:
            if t1: table_names.add(t1)
            if t2: table_names.add(t2)
        # 2. 标准化表名
        def norm(s): return s.replace('[','').replace(']','').strip().lower()
        table_names = {norm(t) for t in table_names}
        # 3. 提取SQL中用到的字段
        field_pattern = r'\[([^\]]+)\]'
        fields = re.findall(field_pattern, sql)
        fields = [f.strip().lower() for f in fields]
        # 4. 遍历表，查找字段
        result = []
        for t in table_names:
            # 找到table_knowledge中最接近的表
            matched_table = None
            for tk in self.table_knowledge:
                if norm(tk) == t:
                    matched_table = tk
                    break
            if not matched_table:
                result.append(f"本地校验：表 {t} 不存在于表结构知识库")
                continue
            table_fields = [f.strip().lower() for f in self.table_knowledge[matched_table]]
            for f in fields:
                if f not in table_fields:
                    result.append(f"表 {matched_table} 不存在字段 [{f}]")
        if not result:
            return "本地校验：所有字段均存在，校验通过。"
        return "本地校验：\n" + "; ".join(result)
    
    def _extract_sql_and_analysis(self, response):
        import re
        if "VALID" in response.upper():
            return "", response
        sql_match = re.search(r"```sql[\s\S]*?([\s\S]+?)```", response, re.IGNORECASE)
        if sql_match:
            sql = sql_match.group(1).strip()
            analysis = response.replace(sql_match.group(0), '').strip()
        else:
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
    
    def _extract_time_conditions(self, sql):
        """提取SQL中的时间相关条件"""
        import re
        time_conditions = []
        
        # 匹配时间相关字段的条件
        time_patterns = [
            r'AND\s+\[自然年\]\s*=\s*[^AND\s]+',
            r'AND\s+\[财月\]\s*=\s*[^AND\s]+',
            r'AND\s+\[财周\]\s*=\s*[^AND\s]+',
            r'AND\s+\[财年\]\s*=\s*[^AND\s]+',
            r'AND\s+\[自然年\]\s*=\s*YEAR\s*\(\s*GETDATE\s*\(\s*\)\s*\)',
            r'AND\s+\[财月\]\s*=\s*CAST\s*\(\s*MONTH\s*\(\s*GETDATE\s*\(\s*\)\s*\)\s*AS\s+VARCHAR\s*\)\s*\+\s*\'月\'',
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            time_conditions.extend(matches)
        
        return time_conditions
    
    def _restore_time_conditions(self, sql, time_conditions):
        import re
        if not time_conditions:
            return sql

        # 检查是否有被拆分的片段
        if any(bad in sql for bad in ["= YE", "= C", "= YEA", "= CA"]):
            # 先移除校验后SQL中所有被拆分的时间条件片段
            sql = re.sub(r"AND\s+\[自然年\]\s*=\s*YE", "", sql)
            sql = re.sub(r"AND\s+\[财月\]\s*=\s*C", "", sql)
            sql = re.sub(r"AND\s+\[自然年\]\s*=\s*YEA", "", sql)
            sql = re.sub(r"AND\s+\[财月\]\s*=\s*CA", "", sql)
            # 找到WHERE子句
            where_match = re.search(r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1).strip()
                # 移除所有原有的时间条件
                where_clause = re.sub(r"AND\s+\[自然年\].*?(?=AND|$)", "", where_clause)
                where_clause = re.sub(r"AND\s+\[财月\].*?(?=AND|$)", "", where_clause)
                where_clause = re.sub(r"AND\s+\[财周\].*?(?=AND|$)", "", where_clause)
                # 重新拼接
                new_where = where_clause + " " + " ".join(time_conditions)
                sql = sql.replace(where_match.group(1), new_where)
            return sql

        # 原有逻辑
        # 找到WHERE子句的位置
        where_match = re.search(r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            # 在WHERE子句末尾添加时间条件
            restored_sql = sql.replace(where_clause, where_clause + ' ' + ' '.join(time_conditions))
            return restored_sql
        else:
            # 如果没有WHERE子句，添加一个
            from_match = re.search(r'FROM\s+.*?(?=\s*WHERE|\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
            if from_match:
                from_clause_end = from_match.end()
                restored_sql = sql[:from_clause_end] + ' WHERE ' + ' '.join(time_conditions) + sql[from_clause_end:]
                return restored_sql
        return sql
    
    def validate_sql_fields(self, sql):
        """验证SQL中的字段是否存在于表结构中"""
        import re
        
        def norm_table_name(name):
            if '.' in name:
                name = name.split('.')[-1]
            return name.replace('[','').replace(']','').strip().lower()
        
        def norm_field_name(name):
            return name.replace('[','').replace(']','').strip().lower()
        
        # 1. 解析表别名映射
        alias2table = {}
        from_pattern = r'FROM\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
        join_pattern = r'JOIN\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
        for pat in [from_pattern, join_pattern]:
            for m in re.findall(pat, sql, re.IGNORECASE):
                table, alias = m
                alias2table[alias] = norm_table_name(table)
        
        # 2. 提取所有带表别名的字段引用
        field_pattern = r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]'
        field_refs = re.findall(field_pattern, sql)
        
        missing_fields = []
        valid_fields = []
        
        for alias, field in field_refs:
            table = alias2table.get(alias)
            if not table:
                missing_fields.append(f"别名[{alias}]未找到对应表")
                continue
                
            # 查找对应的表
            matched_table = None
            for tk in self.table_knowledge:
                if norm_table_name(tk) == table:
                    matched_table = tk
                    break
            if not matched_table:
                missing_fields.append(f"表[{table}]未在知识库中定义")
                continue
                
            # 检查字段是否存在
            columns = []
            for col in self.table_knowledge[matched_table]['columns']:
                if isinstance(col, dict) and 'name' in col:
                    columns.append(norm_field_name(col['name']))
                elif isinstance(col, str):
                    columns.append(norm_field_name(col))
                    
            if norm_field_name(field) in columns:
                valid_fields.append(f"{alias}.{field}")
            else:
                missing_fields.append(f"表[{matched_table}] 字段[{field}] (别名:{alias})")
        
        # 3. 检查没有表别名的字段引用 - 改进逻辑
        # 对于没有表别名的字段，我们需要更智能地判断它们属于哪个表
        simple_field_pattern = r'\[([^\]]+)\]'
        simple_fields = re.findall(simple_field_pattern, sql)
        
        # 过滤掉已经在带别名字段中处理过的字段
        aliased_fields = {field for _, field in field_refs}
        simple_fields = [field for field in simple_fields if field not in aliased_fields]
        
        for field in simple_fields:
            # 跳过明显的表名、数据库名等
            if any(skip in field.lower() for skip in ['ff_idss', 'dbo', 'dtsupply', 'condt', 'commit', 'summary']):
                continue
            if '.' in field:
                continue
                
            # 改进：根据SQL上下文判断字段可能属于哪个表
            # 1. 检查是否在SELECT子句中（可能是聚合函数或计算字段）
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)
                if f'[{field}]' in select_clause:
                    # 如果字段在SELECT子句中且没有表别名，可能是计算字段或聚合函数
                    # 这种情况下我们不应该报错
                    valid_fields.append(field)
                    continue
            
            # 2. 检查是否在WHERE子句中
            where_match = re.search(r'WHERE\s+(.*?)(?=\s*ORDER\s+BY|\s*GROUP\s+BY|\s*HAVING|\s*$)', sql, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                if f'[{field}]' in where_clause:
                    # 如果字段在WHERE子句中且没有表别名，需要检查它是否存在于主表中
                    # 提取主表名
                    from_match = re.search(r'FROM\s+([\w\[\]\.]+)', sql, re.IGNORECASE)
                    if from_match:
                        main_table = norm_table_name(from_match.group(1))
                        # 检查字段是否在主表中存在
                        field_exists = False
                        for table_name, table_info in self.table_knowledge.items():
                            if norm_table_name(table_name) == main_table:
                                columns = []
                                for col in table_info.get('columns', []):
                                    if isinstance(col, dict) and 'name' in col:
                                        columns.append(norm_field_name(col['name']))
                                    elif isinstance(col, str):
                                        columns.append(norm_field_name(col))
                                
                                if norm_field_name(field) in columns:
                                    field_exists = True
                                    valid_fields.append(field)
                                    break
                        
                        if not field_exists:
                            missing_fields.append(f"主表[{main_table}] 字段[{field}]")
                            continue
                    else:
                        # 如果找不到主表，按业务术语处理
                        business_terms = ["未清PO数量", "本月备货", "全链库存", "自然年", "财月", "财周", "财年"]
                        if field in business_terms:
                            valid_fields.append(field)
                            continue
                        else:
                            missing_fields.append(field)
                            continue
            
            # 3. 检查是否在任何表中存在（作为兜底检查）
            field_exists = False
            for table_name, table_info in self.table_knowledge.items():
                columns = []
                for col in table_info.get('columns', []):
                    if isinstance(col, dict) and 'name' in col:
                        columns.append(norm_field_name(col['name']))
                    elif isinstance(col, str):
                        columns.append(norm_field_name(col))
                
                if norm_field_name(field) in columns:
                    field_exists = True
                    valid_fields.append(field)
                    break
            
            # 4. 如果字段在任何表中都不存在，但可能是业务术语，也不报错
            # 比如"未清PO数量"这样的业务术语
            business_terms = ["未清PO数量", "本月备货", "全链库存", "自然年", "财月", "财周", "财年"]
            if field in business_terms:
                valid_fields.append(field)
                continue
            
            if not field_exists:
                missing_fields.append(field)
        
        return {
            'valid_fields': valid_fields,
            'missing_fields': missing_fields,
            'all_valid': len(missing_fields) == 0
        }
    
    def execute_sql(self, sql, db_config):
        try:
            db_type = db_config["type"]
            config = db_config["config"]
            print(f"正在连接数据库: {config['server']}/{config['database']}")
            print(f"执行的SQL长度: {len(sql) if sql else 0}")
            print(f"执行的SQL: {repr(sql)}")
            
            if not sql or not sql.strip():
                return False, pd.DataFrame(), "SQL语句为空"
            
            # 预校验字段
            field_validation = self.validate_sql_fields(sql)
            if not field_validation['all_valid']:
                missing_fields_str = ', '.join(field_validation['missing_fields'])
                return False, pd.DataFrame(), f"SQL字段验证失败：以下字段不存在于表结构中：{missing_fields_str}"
            
            if db_type == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["file_path"])
                df = pd.read_sql_query(sql, conn)
                conn.close()
                return True, df, "查询执行成功"
            elif db_type == "mssql":
                from sqlalchemy import create_engine, text
                conn_str = self.db_manager.get_mssql_connection_string(config)
                print(f"连接字符串: {conn_str}")
                engine = create_engine(conn_str)
                df = pd.read_sql_query(text(sql), engine)
                return True, df, "查询执行成功"
            else:
                return False, pd.DataFrame(), f"不支持的数据库类型: {db_type}"
        except Exception as e:
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
            return False, pd.DataFrame(), f"SQL执行失败: {str(e)}"
    def visualize_result(self, df, sql, question):
        """使用LLM分析SQL结果并智能生成图表"""
        if df.empty or len(df.columns) < 2:
            return None
            
        try:
            # 构建分析提示
            analysis_prompt = f"""
请分析以下SQL查询结果，并决定最佳的图表类型和轴设置：

问题: {question}
SQL: {sql}
数据列: {list(df.columns)}
数据行数: {len(df)}
前5行数据: {df.head().to_dict()}

请分析数据特点并返回JSON格式的图表配置：
{{
    "chart_type": "柱状图/折线图/饼图/散点图",
    "x_axis": "X轴字段名",
    "y_axis": "Y轴字段名", 
    "title": "图表标题",
    "reason": "选择原因"
}}

注意：
1. 如果包含时间字段，优先作为X轴
2. 如果有多个数值字段，选择最重要的作为Y轴
3. 如果有多个维度，考虑合并显示
4. 避免使用时间作为Y轴，只用于X轴
"""
            
            # 调用LLM分析
            response = self.call_deepseek_api(analysis_prompt)
            
            # 检查是否返回错误信息
            if response.startswith("API调用失败") or response.startswith("网络连接"):
                print(f"LLM图表分析失败: {response}")
                return self._default_visualize(df)
            
            # 解析JSON响应
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    config = json.loads(json_match.group())
                    
                    # 根据配置生成图表
                    x_col = config.get("x_axis", df.columns[0])
                    y_col = config.get("y_axis", df.columns[1])
                    chart_type = config.get("chart_type", "柱状图")
                    title = config.get("title", f"{question} - 查询结果")
                    
                    # 验证字段是否存在
                    if x_col not in df.columns or y_col not in df.columns:
                        print(f"LLM图表分析失败: 字段不存在 - x_col: {x_col}, y_col: {y_col}")
                        return self._default_visualize(df)
                    
                    if chart_type == "柱状图":
                        fig = px.bar(df, x=x_col, y=y_col, title=title)
                    elif chart_type == "折线图":
                        fig = px.line(df, x=x_col, y=y_col, title=title)
                    elif chart_type == "饼图":
                        fig = px.pie(df, names=x_col, values=y_col, title=title)
                    elif chart_type == "散点图":
                        fig = px.scatter(df, x=x_col, y=y_col, title=title)
                    else:
                        fig = px.bar(df, x=x_col, y=y_col, title=title)
                    
                    return fig
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    print(f"LLM图表分析失败: JSON解析错误 - {e}")
                    return self._default_visualize(df)
            else:
                # 如果LLM分析失败，使用默认逻辑
                return self._default_visualize(df)
                
        except Exception as e:
            print(f"LLM图表分析失败: {e}")
            return self._default_visualize(df)
    
    def analyze_query_result(self, df, sql, question):
        """LLM自动分析查询结果"""
        try:
            if df.empty:
                return "查询结果为空，无法进行分析。"
            
            # 构建分析提示词
            analysis_prompt = f"""
请分析以下查询结果，并提供专业的业务洞察：

【用户问题】
{question}

【执行的SQL】
{sql}

【查询结果统计】
- 数据行数: {len(df)}
- 数据列数: {len(df.columns)}
- 列名: {list(df.columns)}

【数据摘要】
{df.describe().to_string() if not df.empty else '无数据'}

【前5行数据】
{df.head().to_string() if not df.empty else '无数据'}

请从以下角度进行分析：
1. 数据概览：数据规模、主要特征
2. 业务洞察：关键发现、趋势分析
3. 数据质量：异常值、缺失值情况
4. 建议：基于数据的业务建议

请用中文回答，格式要清晰易读。
"""
            
            # 调用LLM进行分析
            response = self.call_deepseek_api(analysis_prompt)
            
            # 检查是否返回错误信息
            if response.startswith("API调用失败") or response.startswith("网络连接"):
                return f"LLM分析暂时不可用: {response}。请稍后重试。"
            
            # 提取分析结果
            if "```" in response:
                # 如果返回的是代码块格式，提取内容
                import re
                match = re.search(r'```(?:markdown)?\n(.*?)\n```', response, re.DOTALL)
                if match:
                    return match.group(1)
                else:
                    return response
            else:
                return response
                
        except Exception as e:
            return f"分析过程中出现错误: {str(e)}"
    
    def _default_visualize(self, df):
        """默认图表生成逻辑"""
        if len(df.columns) >= 2 and len(df) > 1:
            # 检查是否有时间列
            time_columns = [col for col in df.columns if any(time_word in col.lower() for time_word in ['时间', '日期', 'date', 'time', '年', '月', '日'])]
            
            if time_columns:
                # 有时间列，作为X轴
                x_col = time_columns[0]
                y_col = [col for col in df.columns if col != x_col][0]
            else:
                # 没有时间列，使用前两列
                x_col = df.columns[0]
                y_col = df.columns[1]
            
            fig = px.bar(df, x=x_col, y=y_col, title=f"{x_col} vs {y_col}")
            return fig
        return None
    def record_historical_qa(self, question, sql):
        import datetime
        qa_record = {
            "question": question, 
            "sql": sql,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.historical_qa.append(qa_record)
        # 保存到文件
        try:
            with open("historical_qa.json", "w", encoding="utf-8") as f:
                json.dump(self.historical_qa, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史问答对失败: {e}")
    
    def train_vanna_with_enterprise_knowledge(self, qa_examples: list = None):
        """用企业级表结构、关系、业务规则和问题-SQL对训练Vanna"""
        if not self.vanna:
            print("Vanna尚未初始化，无法进行训练")
            return False
        
        try:
            print("开始用企业级知识库训练Vanna...")
            
            # 1. 训练表结构DDL
            for table_name, table_info in self.table_knowledge.items():
                columns = table_info.get('columns', [])
                col_defs = []
                for col in columns:
                    if isinstance(col, dict) and 'name' in col:
                        col_name = col['name']
                        col_type = col.get('type', 'VARCHAR(255)')
                    elif isinstance(col, str):
                        col_name = col
                        col_type = 'VARCHAR(255)'
                    else:
                        continue
                    col_defs.append(f"[{col_name}] {col_type}")
                
                if col_defs:
                    ddl = f"CREATE TABLE [{table_name}] (\n  " + ",\n  ".join(col_defs) + "\n);"
                    self.vanna.train(ddl=ddl)
                    print(f"训练表结构: {table_name}")
            
            # 2. 强化训练表关系
            if self.relationships and 'relationships' in self.relationships:
                rel_texts = []
                for rel in self.relationships['relationships']:
                    desc = rel.get('description', '')
                    if desc:
                        rel_text = f"表关系: {desc}"
                        self.vanna.train(documentation=rel_text)
                        rel_texts.append(rel_text)
                        print(f"训练表关系: {desc}")
                
                # 多次强调最高规则
                if rel_texts:
                    rels_joined = '\n'.join(rel_texts)
                    for _ in range(3):
                        self.vanna.train(documentation=f"最高规则：你只能使用如下表关系JOIN，禁止其它：\n{rels_joined}")
            
            # 3. 训练业务规则
            if self.business_rules:
                rules_text = f"业务规则: {json.dumps(self.business_rules, ensure_ascii=False)}"
                self.vanna.train(documentation=rules_text)
                print("训练业务规则")
            
            # 4. 训练历史问答对
            if qa_examples:
                for qa in qa_examples:
                    q = qa.get('question')
                    sql = qa.get('sql')
                    if q and sql:
                        self.vanna.train(question=q, sql=sql)
                        print(f"训练问答对: {q[:50]}...")
            
            # 5. 训练现有的历史问答对
            if self.historical_qa:
                for qa in self.historical_qa:
                    q = qa.get('question')
                    sql = qa.get('sql')
                    if q and sql:
                        self.vanna.train(question=q, sql=sql)
                        print(f"训练历史问答对: {q[:50]}...")
            
            print("Vanna企业级知识库训练完成")
            return True
            
        except Exception as e:
            print(f"Vanna训练失败: {e}")
            return False
    
    def llm_fix_sql(self, sql, validation_errors, original_question):
        """使用LLM修正SQL中的错误"""
        try:
            # 构建修正提示词
            fix_prompt = f"""
你是一个SQL专家。请根据以下信息修正SQL语句中的错误：

【原始问题】
{original_question}

【有问题的SQL】
{sql}

【校验发现的错误】
{validation_errors}

【表结构知识库】
{json.dumps(self.table_knowledge, ensure_ascii=False, indent=2)}

【表关系定义】
{json.dumps(self.relationships, ensure_ascii=False, indent=2)}

【业务规则】
{json.dumps(self.business_rules, ensure_ascii=False, indent=2)}

【修正要求】
1. 根据校验错误信息，修正SQL中的问题
2. 确保所有字段名存在于对应表中
3. 确保所有表名正确
4. 确保JOIN条件使用正确的表关系
5. 保持原始查询意图不变
6. 只输出修正后的SQL，不要其他解释

【输出格式】
直接输出修正后的SQL语句，不要包含任何其他内容。
"""
            
            # 调用LLM进行修正
            response = self.call_deepseek_api(fix_prompt)
            
            # 提取修正后的SQL
            if response and not response.startswith("API调用失败"):
                # 尝试从响应中提取SQL
                import re
                sql_match = re.search(r'```sql\s*\n(.*?)\n```', response, re.DOTALL | re.IGNORECASE)
                if sql_match:
                    fixed_sql = sql_match.group(1).strip()
                else:
                    # 如果没有代码块，尝试直接提取
                    lines = response.strip().split('\n')
                    fixed_sql = lines[0].strip()
                    if fixed_sql.startswith('SELECT'):
                        pass  # 看起来是SQL
                    else:
                        # 查找以SELECT开头的行
                        for line in lines:
                            if line.strip().upper().startswith('SELECT'):
                                fixed_sql = line.strip()
                                break
                
                return fixed_sql, f"LLM修正结果：\n{response}"
            else:
                return sql, f"LLM修正失败：{response}"
                
        except Exception as e:
            return sql, f"LLM修正过程中出现错误：{str(e)}"
    
    def call_deepseek_api(self, prompt):
        """调用DeepSeek API，带重试机制"""
        import time
        max_retries = 3
        retry_delay = 2
        
        headers = {
            "Authorization": f"Bearer sk-0e6005b793aa4759bb022b91e9055f86",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60  # 增加超时时间
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    print(f"API响应错误: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        return f"API调用失败，状态码: {response.status_code}"
                        
            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return "网络连接超时，请检查网络连接或稍后重试"
                    
            except requests.exceptions.ConnectionError:
                print(f"连接错误 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return "网络连接失败，请检查网络连接"
                    
            except Exception as e:
                print(f"API调用失败: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return f"API调用失败: {str(e)}"
        
        return "所有重试都失败了，请检查网络连接和API配置"
    def save_database_configs(self):
        # 保存数据库配置到文件
        try:
            with open("database_configs.json", "w", encoding="utf-8") as f:
                json.dump(self.databases, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存数据库配置失败: {e}")
            return False

    def load_database_configs(self):
        # 从文件加载数据库配置
        try:
            if os.path.exists("database_configs.json"):
                with open("database_configs.json", "r", encoding="utf-8") as f:
                    self.databases = json.load(f)
                return True
            return False
        except Exception as e:
            print(f"加载数据库配置失败: {e}")
            return False

    def save_business_rules(self):
        # 兼容V2.4 UI，保存到 business_rules.json
        try:
            with open("business_rules.json", "w", encoding="utf-8") as f:
                json.dump(self.business_rules, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False

    def save_prompt_templates(self):
        # 兼容V2.4 UI，保存到 prompt_templates.json
        try:
            with open("prompt_templates.json", "w", encoding="utf-8") as f:
                json.dump(self.prompt_templates, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False

    def save_product_knowledge(self):
        # 兼容V2.4 UI，保存到 product_knowledge.json
        try:
            with open("product_knowledge.json", "w", encoding="utf-8") as f:
                json.dump(self.product_knowledge, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False

    def save_table_knowledge(self):
        # 兼容V2.4 UI，保存到 table_knowledge.json
        try:
            with open("table_knowledge.json", "w", encoding="utf-8") as f:
                json.dump(self.table_knowledge, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存表结构知识库失败: {e}")
            return False

    def load_table_knowledge(self):
        # 兼容V2.4 UI，从 table_knowledge.json 加载
        try:
            if os.path.exists("table_knowledge.json"):
                with open("table_knowledge.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载表结构知识库失败: {e}")
        return {}

if __name__ == "__main__":
    def load_json(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    try:
        historical_qa = load_json('historical_qa.json')
    except:
        historical_qa = []
    try:
        prompt_templates = load_json('prompt_templates.json')
    except:
        prompt_templates = {}
    db_manager = DatabaseManager()
    vanna = VannaWrapper()
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
    question = "510S 25年7月的全链库存、本月备货，MTM和未清PO信息"
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
        fig = engine.visualize_result(df, sql2, question)
        if fig:
            fig.show()
    engine.record_historical_qa(question, sql2)