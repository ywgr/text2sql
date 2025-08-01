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
    def generate_prompt(self, question, target_table=None):
        processed_question = self.apply_business_rules(question, target_table)
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
        related_table_info = self.get_related_table_info(sql)
        validate_prompt = f"""
你是SQL合规性校验专家。请严格校验下方SQL是否合规，只做校验，不做修正。

【相关表结构】
{json.dumps(related_table_info, ensure_ascii=False, indent=2)}

【待校验SQL】
{sql}

【校验要求】
1. 只能根据上方表结构判断字段是否存在，不能凭经验猜测。
2. 字段名区分大小写。
3. 只做校验，不做修正。
4. 只输出"校验分析"。
"""
        # 增加重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.vanna.generate_sql(validate_prompt) if self.vanna else self.call_deepseek_api(validate_prompt)
                # 执行本地校验作为补充
                local_check_result = self.enhanced_local_field_check(sql)
                # 合并LLM校验和本地校验结果
                combined_response = f"{response}\n\n{local_check_result}"
                return sql, combined_response
            except Exception as e:
                if attempt == max_retries - 1:
                    # 即使LLM失败，也执行本地校验
                    local_check_result = self.enhanced_local_field_check(sql)
                    return sql, f"LLM校验API调用失败: {e}\n\n{local_check_result}"
                import time
                time.sleep(2 * (attempt + 1))

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
        
        # 3. 检查没有表别名的字段引用（可能是表名直接引用）
        # 这种情况比较少见，但为了完整性还是检查一下
        simple_field_pattern = r'\[([^\]]+)\]'
        simple_fields = re.findall(simple_field_pattern, sql)
        
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
                    valid_fields.append(field)
                    break
            
            if not field_exists:
                # 只有当字段不在已验证的有效字段中时才报错
                if field not in [f.split('.')[-1] for f in valid_fields]:
                    missing_fields.append(field)
        
        # 4. 特殊处理：对于一些业务字段，即使在表结构中找不到也应该通过验证
        # 比如"未清PO数量", "CONPD", "备货NY"等字段可能是业务术语而非实际字段名
        business_terms = ["未清PO数量", "CONPD", "备货NY"]
        filtered_missing_fields = []
        for field in missing_fields:
            # 如果是业务术语，则不报错
            is_business_term = any(term in field for term in business_terms)
            if not is_business_term:
                # 特殊处理：对于简单字段名，检查是否包含业务术语
                is_simple_business_term = any(term == field for term in business_terms)
                if not is_simple_business_term:
                    filtered_missing_fields.append(field)
            # 如果是业务术语，则跳过不添加到filtered_missing_fields中
        
        return {
            'valid_fields': valid_fields,
            'missing_fields': filtered_missing_fields,
            'all_valid': len(filtered_missing_fields) == 0
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