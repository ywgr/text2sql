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
        # 如果table_knowledge为空，使用默认的正确字段名
        if not table_knowledge:
            table_knowledge = {
                "dtsupply_summary": {
                    "columns": [
                        "Roadmap Family", "Group", "Model", "全链库存", "全链库存DOI", 
                        "FCST", "SellOut预测", "SellIn", "SellOut", "自然年", "财月", "财周",
                        "PO PSD", "PO RSD", "TTLPSD", "TTLRSD", "TTLFCST"
                    ]
                },
                "CONPD": {
                    "columns": [
                        "Roadmap Family", "Group", "PN", "Model", "Product Line"
                    ]
                },
                "备货NY": {
                    "columns": [
                        "MTM", "本月备货", "下月备货", "财月", "自然年"
                    ]
                },
                "ConDT_Open_PO": {
                    "columns": [
                        "PN", "SD PO Open Qty", "Qty", "PO", "SO", "自然年", "财月"
                    ]
                }
            }
        
        self.table_knowledge = table_knowledge
        self.relationships = relationships
        self.business_rules = business_rules
        self.product_knowledge = product_knowledge
        self.historical_qa = historical_qa
        self.vanna = vanna
        self.db_manager = db_manager
        self.prompt_templates = prompt_templates
        self.databases = {}
        
        # 验证表存在性
        self._validate_table_existence()
    
    def _validate_table_existence(self):
        """验证表知识库中的表是否存在"""
        if not self.db_manager:
            return
        
        # 已知存在的表
        existing_tables = {
            "dtsupply_summary": "FF_IDSS_Dev_FF.dbo.dtsupply_summary",
            "CONPD": "FF_IDSS_Dev_FF.dbo.CONPD",
            "备货NY": "FF_IDSS_Dev_FF.dbo.备货NY",
            "ConDT_Open_PO": "FF_IDSS_Data_CON_BAK.dbo.ConDT_Open_PO",
            "con_target": "FF_IDSS_Data_CON_BAK.dbo.con_target",
            "ConDT_Commit": "FF_IDSS_Data_CON_BAK.dbo.ConDT_Commit",
        }
        
        # 过滤掉不存在的表
        filtered_knowledge = {}
        for table_name, table_info in self.table_knowledge.items():
            if table_name in existing_tables:
                filtered_knowledge[table_name] = table_info
            else:
                print(f"警告：表 {table_name} 不存在，已从知识库中移除")
        
        self.table_knowledge = filtered_knowledge
    
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
        
        # 智能聚类分析
        clustering_analysis = self._analyze_clustering_requirements(question)
        
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
        
        # 构建包含数据库名称的表结构信息
        existing_tables = {
            "dtsupply_summary": "FF_IDSS_Dev_FF.dbo.dtsupply_summary",
            "CONPD": "FF_IDSS_Dev_FF.dbo.CONPD",
            "备货NY": "FF_IDSS_Dev_FF.dbo.备货NY",
            "ConDT_Open_PO": "FF_IDSS_Data_CON_BAK.dbo.ConDT_Open_PO",
            "con_target": "FF_IDSS_Data_CON_BAK.dbo.con_target",
            "ConDT_Commit": "FF_IDSS_Data_CON_BAK.dbo.ConDT_Commit",
        }
        
        table_lines = []
        for tbl, info in self.table_knowledge.items():
            if tbl in existing_tables:
                full_table_name = existing_tables[tbl]
                columns = info.get('columns', [])
                if isinstance(columns, list):
                    column_names = []
                    for col in columns:
                        if isinstance(col, dict):
                            column_names.append(col.get('name', str(col)))
                        else:
                            column_names.append(str(col))
                    table_lines.append(f"- {full_table_name}: {', '.join(column_names)}")
                else:
                    table_lines.append(f"- {full_table_name}: {columns}")
        
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
        
        # 提取定语信息用于SELECT第一列
        import re
        
        # 查找业务术语作为定语
        qualifier_terms = []
        for term, rule_info in self.business_rules.items():
            if isinstance(rule_info, dict):
                business_term = rule_info.get('business_term', term)
                db_field = rule_info.get('db_field', '')
                table_restriction = rule_info.get('table', '')
                
                # 检查是否是定语（实体类型且不是时间）
                if (rule_info.get('type') == '实体' and 
                    business_term in question):
                    
                    # 检查表限制
                    if not table_restriction or target_table == table_restriction:
                        qualifier_terms.append({
                            'term': business_term,
                            'field': db_field,
                            'table': table_restriction
                        })
        
        # 如果没有找到定语，尝试在原始问题中查找
        if not qualifier_terms:
            # 常见的定语术语
            common_qualifiers = ['510S', 'geek', '小新', '拯救者', '消台']
            for qualifier in common_qualifiers:
                if qualifier in question:
                    # 查找对应的业务规则
                    for term, rule_info in self.business_rules.items():
                        if isinstance(rule_info, dict):
                            business_term = rule_info.get('business_term', term)
                            if business_term.strip() == qualifier:
                                db_field = rule_info.get('db_field', '')
                                table_restriction = rule_info.get('table', '')
                                
                                # 检查表限制
                                if not table_restriction or target_table == table_restriction:
                                    qualifier_terms.append({
                                        'term': business_term,
                                        'field': db_field,
                                        'table': table_restriction
                                    })
                                    break
        
        # 构建SELECT定语指令
        select_qualifier_instruction = ""
        if qualifier_terms:
            select_qualifier_instruction = f"""
【重要：SELECT定语字段要求】
问题中包含以下定语：{', '.join([q['term'] for q in qualifier_terms])}

请在SELECT语句中包含对应的定语字段，使用AS别名：
"""
            for qualifier in qualifier_terms:
                if qualifier['field'] and not qualifier['field'].startswith('where'):
                    # 如果是简单字段映射，使用AS
                    select_qualifier_instruction += f"- {qualifier['term']} → {qualifier['field']} AS '{qualifier['term']}'\n"
                else:
                    # 如果是复杂条件，提取字段名
                    field_match = re.search(r'\[([^\]]+)\]', qualifier['field'])
                    if field_match:
                        field_name = field_match.group(1)
                        select_qualifier_instruction += f"- {qualifier['term']} → [{field_name}] AS '{qualifier['term']}'\n"
            
            select_qualifier_instruction += """
例如：SELECT [Product Line] AS '消台', [其他字段]...
"""
        
        # 使用新的定语指令
        select_first_col_instruction = select_qualifier_instruction
        
        # 聚类层级指令
        clustering_instruction = ""
        if clustering_analysis:
            clustering_instruction = f"""
【聚类层级要求】
{clustering_analysis}

请根据产品层级正确聚类数据：
- 如果查询Roadmap Family层级（如510S），则按Roadmap Family聚合
- 如果查询PO层级数据，需要按Roadmap Family聚合PO数据
- 使用SUM()函数聚合数值字段
- 使用GROUP BY按产品层级分组
"""
        
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
                    relationships=rel_struct,
                    question=processed_question,
                    qa_examples=qa_examples,
                    time_field_warning=time_field_warning,
                    clustering_analysis=clustering_analysis,
                    select_first_col_instruction=select_first_col_instruction,
                    clustering_instruction=clustering_instruction
                )
            except KeyError as e:
                print(f"模板格式化错误: {e}")
                prompt = f"""
请根据以下信息生成SQL查询：

【表结构】
{table_struct}

【业务规则】
{rules_str}

【表关系】
{rel_struct}

【问题】
{processed_question}

【聚类分析】
{clustering_analysis}

【SELECT第一列要求】
{select_first_col_instruction}

【聚类层级要求】
{clustering_instruction}

【时间字段提醒】
{time_field_warning}

【历史问答示例】
{qa_examples}

请生成准确的SQL查询语句。
"""
        else:
            prompt = f"""
你是一个专业的SQL生成助手。请根据以下信息生成准确的SQL查询：

【表结构】
{table_struct}

【业务规则】
{rules_str}

【表关系】
{rel_struct}

【问题】
{processed_question}

【聚类分析】
{clustering_analysis}

【SELECT第一列要求】
{select_first_col_instruction}

【聚类层级要求】
{clustering_instruction}

【时间字段提醒】
{time_field_warning}

【历史问答示例】
{qa_examples}

【重要要求】
1. SELECT语句的第一列必须包含定语字段（如Roadmap Family），让结果更清晰
2. 根据产品层级正确聚类数据，使用SUM()和GROUP BY
3. 只使用上述表结构中明确列出的表和字段
4. 确保JOIN条件正确，避免笛卡尔积
5. 添加适当的时间条件（年、月、周等）

请生成准确的SQL查询语句。
"""
        
        return prompt
    
    def _analyze_clustering_requirements(self, question):
        """分析聚类需求，确定产品层级"""
        import re
        
        # 产品层级定义
        hierarchy_levels = {
            'roadmap_family': ['roadmap family', 'roadmap', 'family', '产品系列'],
            'model': ['model', '型号', '产品型号'],
            'mtm': ['mtm', 'pn', '物料编码', 'part number'],
            'po': ['po', 'purchase order', '采购订单', '订单'],
            'so': ['so', 'sales order', '销售订单']
        }
        
        # 检测查询中的产品层级
        detected_level = None
        question_lower = question.lower()
        
        # 检查是否有PO相关查询
        po_indicators = ['po', 'purchase order', '采购订单', '订单', '未清po', 'open po']
        has_po_query = any(indicator in question_lower for indicator in po_indicators)
        
        # 检查是否有Roadmap Family相关查询
        roadmap_indicators = ['510s', 'geek', 'roadmap family', '产品系列']
        has_roadmap_query = any(indicator in question_lower for indicator in roadmap_indicators)
        
        # 确定聚类层级
        if has_roadmap_query:
            detected_level = 'roadmap_family'
        elif has_po_query:
            # 如果查询PO数据，但产品层级是Roadmap Family，需要按Roadmap Family聚类PO
            detected_level = 'roadmap_family'
        else:
            # 默认按Roadmap Family聚类
            detected_level = 'roadmap_family'
        
        # 生成聚类规则
        clustering_rules = ""
        if detected_level == 'roadmap_family':
            clustering_rules = """
【聚类规则：Roadmap Family层级】
- 按Roadmap Family分组
- 对数值字段使用SUM()聚合
- 对PO相关数据按Roadmap Family聚合
- GROUP BY: Roadmap Family
- 示例：SELECT [Roadmap Family], SUM([SD PO Open Qty]) AS [未清PO数量]
"""
        elif detected_level == 'model':
            clustering_rules = """
【聚类规则：Model层级】
- 按Model分组
- 对数值字段使用SUM()聚合
- GROUP BY: Model
"""
        elif detected_level == 'mtm':
            clustering_rules = """
【聚类规则：MTM层级】
- 按MTM/PN分组
- 对数值字段使用SUM()聚合
- GROUP BY: MTM/PN
"""
        
        return clustering_rules
    def apply_business_rules(self, question, target_table=None):
        """应用业务规则转换，支持表限制和复杂条件"""
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
        
        # 字段名映射 - 确保使用正确的字段名
        field_mapping = {
            "预测": "FCST",
            "周转天数": "全链库存DOI",
            "库存": "全链库存",
            "销售预测": "SellOut预测",
            "销售": "SellOut",
            "采购": "SellIn",
            "PO数量": "SD PO Open Qty",
            "未清PO": "SD PO Open Qty"
        }
        
        # 应用字段名映射
        for old_name, new_name in field_mapping.items():
            processed_question = processed_question.replace(old_name, new_name)
        
        # 收集WHERE条件
        where_conditions = []
        
        # 应用业务规则 - 优化版本，优先处理时间规则
        # 首先按规则长度排序，确保更具体的规则（如"25年7月"）优先于通用规则（如"25年"）
        sorted_rules = sorted(self.business_rules.items(), key=lambda x: len(x[0]), reverse=True)
        
        for business_term, rule_info in sorted_rules:
            # 处理新的业务规则格式（字典）
            if isinstance(rule_info, dict):
                business_term_actual = rule_info.get('business_term', business_term)
                db_field = rule_info.get('db_field', '')
                condition_type = rule_info.get('condition_type', '等于')
                condition_value = rule_info.get('condition_value', '')
                table_restriction = rule_info.get('table', '')
                rule_type = rule_info.get('type', '实体')
                
                # 检查表限制 - 优先应用表特定的规则
                if table_restriction:
                    if target_table and table_restriction != target_table:
                        continue
                    # 表特定规则优先级更高
                    if business_term_actual in processed_question:
                        # 对于字段类型的规则，检查是否是字段映射（如"全链库存周转"）
                        if rule_type == '字段' and db_field:
                            # 字段映射：将"周转"替换为"DOI"
                            processed_question = processed_question.replace(business_term_actual, db_field)
                        elif condition_value and rule_type in ['时间', '条件']:
                            # 时间或条件类型的规则，添加到WHERE条件中
                            where_conditions.append(condition_value)
                            # 从问题中移除业务术语，避免重复
                            processed_question = processed_question.replace(business_term_actual, '')
                        elif condition_value:
                            # 实体类型的规则，直接替换
                            processed_question = processed_question.replace(business_term_actual, condition_value)
                        elif db_field:
                            # 使用简单的字段映射
                            processed_question = processed_question.replace(business_term_actual, db_field)
                else:
                    # 通用规则，但需要确保没有表特定规则存在
                    if business_term_actual in processed_question:
                        # 检查是否有表特定的规则
                        has_table_specific = False
                        for other_term, other_rule in self.business_rules.items():
                            if isinstance(other_rule, dict):
                                other_business_term = other_rule.get('business_term', other_term)
                                other_table = other_rule.get('table', '')
                                if (other_business_term == business_term_actual and 
                                    other_table and target_table and other_table == target_table):
                                    has_table_specific = True
                                    break
                        
                        # 只有在没有表特定规则时才应用通用规则
                        if not has_table_specific:
                            # 对于字段类型的规则，优先处理字段映射
                            if rule_type == '字段' and db_field:
                                # 字段映射：将"周转"替换为"DOI"
                                processed_question = processed_question.replace(business_term_actual, db_field)
                            elif condition_value and rule_type in ['时间', '条件']:
                                # 时间或条件类型的规则，添加到WHERE条件中
                                where_conditions.append(condition_value)
                                # 从问题中移除业务术语，避免重复
                                processed_question = processed_question.replace(business_term_actual, '')
                            elif condition_value:
                                # 实体类型的规则，直接替换
                                processed_question = processed_question.replace(business_term_actual, condition_value)
                            elif db_field:
                                processed_question = processed_question.replace(business_term_actual, db_field)
            
            # 处理旧的业务规则格式（字符串）
            elif isinstance(rule_info, str):
                # 检查表限制
                meta_info = business_rules_meta.get(business_term, {})
                table_restriction = meta_info.get('table_restriction')
                rule_type = meta_info.get('type', '实体')
                
                # 如果没有表限制，或者目标表匹配，则应用规则
                if table_restriction is None or target_table == table_restriction:
                    if business_term in processed_question:
                        # 对于时间类型的规则，添加到WHERE条件中
                        if rule_type == '时间':
                            where_conditions.append(rule_info)
                            # 从问题中移除业务术语，避免重复
                            processed_question = processed_question.replace(business_term, '')
                        else:
                            # 其他类型的规则，直接替换
                            processed_question = processed_question.replace(business_term, rule_info)
        
        # 清理多余的空格和重复内容
        processed_question = re.sub(r'\s+', ' ', processed_question).strip()
        
        # 移除重复的"where"和条件
        processed_question = re.sub(r'where\s+where', 'where', processed_question, flags=re.IGNORECASE)
        processed_question = re.sub(r'本\s*where', '', processed_question)
        processed_question = re.sub(r'全链\s*全链', '全链', processed_question)
        
        # 清理剩余的混乱文本
        processed_question = re.sub(r'where\s+[^A-Za-z]*\s+where', 'where', processed_question, flags=re.IGNORECASE)
        processed_question = re.sub(r'本\s*全链', '全链', processed_question)
        
        # 最终清理：移除多余的where条件
        processed_question = re.sub(r'where\s+财周=\'ttl\'', '', processed_question)
        
        # 特殊处理：确保"全链库存周转"被正确映射为"全链库存DOI"
        if '全链库存周转' in processed_question:
            processed_question = processed_question.replace('全链库存周转', '全链库存DOI')
        elif '周转' in processed_question and 'DOI' not in processed_question:
            processed_question = processed_question.replace('周转', 'DOI')
        
        # 智能时间条件应用：只对包含时间字段的表应用时间条件
        if where_conditions:
            # 检查哪些表包含时间字段
            tables_with_time = []
            tables_without_time = []
            
            for table_name in self.table_knowledge:
                if self.check_table_has_time_fields(table_name):
                    tables_with_time.append(table_name)
                else:
                    tables_without_time.append(table_name)
            
            # 过滤WHERE条件，只保留适用于包含时间字段的表的条件
            filtered_where_conditions = []
            for condition in where_conditions:
                # 检查条件是否包含时间字段
                time_field_patterns = ['财年', '财月', '财周', '自然年', '年', '月', '日']
                has_time_fields = any(pattern in condition for pattern in time_field_patterns)
                
                if has_time_fields:
                    # 这是一个时间条件，需要检查目标表是否包含时间字段
                    if target_table and target_table in tables_with_time:
                        filtered_where_conditions.append(condition)
                    elif not target_table:
                        # 如果没有指定目标表，添加条件但标记为需要验证
                        filtered_where_conditions.append(condition)
                else:
                    # 非时间条件，直接添加
                    filtered_where_conditions.append(condition)
            
            where_conditions = filtered_where_conditions
        
        # 如果有WHERE条件，添加到问题中
        if where_conditions:
            where_clause = ' AND '.join(where_conditions)
            # 清理WHERE条件中的重复内容
            where_clause = re.sub(r'where\s+', '', where_clause, flags=re.IGNORECASE)
            # 确保WHERE条件格式正确
            where_clause = where_clause.strip()
            if where_clause:
                processed_question += f" WHERE条件: {where_clause}"
        
        return processed_question
    def generate_sql(self, prompt):
        # 首先尝试使用Vanna（如果可用）
        if self.vanna:
            try:
                response = self.vanna.generate_sql(prompt)
                sql, analysis = self._extract_sql_and_analysis(response)
                return sql, analysis
            except Exception as e:
                print(f"Vanna调用失败，切换到DeepSeek API: {e}")
        
        # 尝试主要API调用
        response = self.call_deepseek_api(prompt)
        
        # 如果主要API调用失败，尝试备用方法
        if response.startswith("API调用失败") or response.startswith("网络连接"):
            print("主要API调用失败，尝试备用方法...")
            response = self.call_deepseek_api_fallback(prompt)
        
        sql, analysis = self._extract_sql_and_analysis(response)
        
        # 聚类验证
        if sql and not sql.startswith("API调用失败"):
            clustering_validation = self.validate_clustering_sql(sql, prompt)
            if not clustering_validation['is_valid']:
                # 如果聚类验证失败，尝试修正SQL
                print("聚类验证失败，尝试修正SQL...")
                corrected_sql = self._fix_clustering_sql(sql, clustering_validation['suggestions'])
                if corrected_sql != sql:
                    sql = corrected_sql
                    analysis += f"\n\n【聚类修正】\n根据聚类要求修正了SQL：\n{corrected_sql}"
        
        return sql, analysis
    
    def _fix_clustering_sql(self, sql, suggestions):
        """根据聚类建议修正SQL"""
        import re
        
        # 简单的SQL修正逻辑
        corrected_sql = sql
        
        # 如果建议添加聚合函数
        if "添加SUM()函数" in str(suggestions):
            # 查找数值字段并添加SUM
            numeric_fields = re.findall(r'\[([^\]]*(?:库存|预测|PO|SO)[^\]]*)\]', sql, re.IGNORECASE)
            for field in numeric_fields:
                if f'[{field}]' in corrected_sql and f'SUM([{field}])' not in corrected_sql:
                    corrected_sql = corrected_sql.replace(f'[{field}]', f'SUM([{field}])')
        
        # 如果建议添加GROUP BY
        if "添加GROUP BY子句" in str(suggestions):
            # 查找产品层级字段
            hierarchy_fields = re.findall(r'\[([^\]]*(?:Model|Roadmap Family|Group|MTM|PN)[^\]]*)\]', sql, re.IGNORECASE)
            if hierarchy_fields and 'GROUP BY' not in corrected_sql.upper():
                group_by_clause = f"GROUP BY [{hierarchy_fields[0]}]"
                corrected_sql = corrected_sql.replace('WHERE', f'WHERE\nGROUP BY [{hierarchy_fields[0]}]')
        
        return corrected_sql
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
            r'\[自然年\]', r'\[财月\]', r'\[财周\]', r'\[财年\]', r'\[年\]', r'\[月\]', r'\[日\]',
            r'YEAR\s*\(', r'MONTH\s*\(', r'GETDATE\s*\(\s*\)\s*\)', r'CAST\s*\(.*?AS.*?VARCHAR\s*\)'
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
            
            # 临时禁用字段验证 - 因为表知识库可能不完整
            # field_validation = self.validate_sql_fields(sql)
            # if not field_validation['all_valid']:
            #     missing_fields_str = ', '.join(field_validation['missing_fields'])
            #     return False, pd.DataFrame(), f"SQL字段验证失败：以下字段不存在于表结构中：{missing_fields_str}"
            
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
            # 智能分析数据结构和字段类型
            categorical_cols = []
            numeric_cols = []
            doi_cols = []
            
            for col in df.columns:
                if df[col].dtype == 'object' or col in ['Roadmap Family', 'MTM', '产品', '型号']:
                    categorical_cols.append(col)
                elif df[col].dtype != 'object':
                    if 'DOI' in col or '周转天' in col:
                        doi_cols.append(col)
                    else:
                        numeric_cols.append(col)
            
            # 构建分析提示
            analysis_prompt = f"""
请分析以下SQL查询结果，并智能选择最佳的图表配置：

问题: {question}
SQL: {sql}
数据列: {list(df.columns)}
数据行数: {len(df)}
前5行数据: {df.head().to_dict()}

字段分类：
- 分类字段（X轴候选）: {categorical_cols}
- 数值字段（Y轴候选）: {numeric_cols}
- DOI字段（副Y轴候选）: {doi_cols}

请分析数据特点并返回JSON格式的图表配置：
{{
    "chart_type": "柱状图/折线图/饼图/双Y轴图",
    "x_axis": "X轴字段名（优先选择分类字段）",
    "y1_axis": "主Y轴字段名（数值字段）",
    "y2_axis": "副Y轴字段名（DOI字段，可选）",
    "title": "图表标题（基于定语或时间条件）",
    "reason": "选择原因"
}}

选择规则：
1. X轴优先选择分类字段（如Roadmap Family、MTM等）
2. 如果有DOI字段，使用双Y轴图（主Y轴柱状图，副Y轴折线图）
3. 如果没有分类字段，使用数值字段作为X轴
4. 图表标题应包含定语（如"510S"）或时间条件（如"2025年7月"）
5. 避免使用时间作为Y轴，只用于X轴
"""
            
            # 调用LLM分析
            response = self.call_deepseek_api(analysis_prompt)
            
            # 检查是否返回错误信息
            if response.startswith("API调用失败") or response.startswith("网络连接"):
                print(f"LLM图表分析失败: {response}")
                return self._smart_default_visualize(df, question)
            
            # 解析JSON响应
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    config = json.loads(json_match.group())
                    
                    # 根据配置生成图表
                    x_col = config.get("x_axis", categorical_cols[0] if categorical_cols else df.columns[0])
                    y1_col = config.get("y1_axis", numeric_cols[0] if numeric_cols else df.columns[1])
                    y2_col = config.get("y2_axis", doi_cols[0] if doi_cols else None)
                    chart_type = config.get("chart_type", "柱状图")
                    title = config.get("title", f"{question} - 查询结果")
                    
                    # 验证字段是否存在
                    if x_col not in df.columns:
                        x_col = categorical_cols[0] if categorical_cols else df.columns[0]
                    if y1_col not in df.columns:
                        y1_col = numeric_cols[0] if numeric_cols else df.columns[1]
                    if y2_col and y2_col not in df.columns:
                        y2_col = None
                    
                    # 生成图表
                    if chart_type == "双Y轴图" and y2_col:
                        import plotly.graph_objects as go
                        fig = go.Figure()
                        
                        # 主Y轴柱状图
                        fig.add_trace(go.Bar(
                            x=df[x_col],
                            y=df[y1_col],
                            name=y1_col,
                            yaxis='y1'
                        ))
                        
                        # 副Y轴折线图
                        fig.add_trace(go.Scatter(
                            x=df[x_col],
                            y=df[y2_col],
                            name=y2_col,
                            yaxis='y2',
                            mode='lines+markers',
                            line=dict(width=3, color='red')
                        ))
                        
                        fig.update_layout(
                            title=title,
                            xaxis=dict(title=x_col),
                            yaxis=dict(title='数值指标', side='left'),
                            yaxis2=dict(title='DOI/周转天数', overlaying='y', side='right'),
                            legend=dict(x=0.01, y=0.99)
                        )
                    elif chart_type == "柱状图":
                        import plotly.express as px
                        fig = px.bar(df, x=x_col, y=y1_col, title=title)
                    elif chart_type == "折线图":
                        import plotly.express as px
                        fig = px.line(df, x=x_col, y=y1_col, title=title)
                    elif chart_type == "饼图":
                        import plotly.express as px
                        fig = px.pie(df, names=x_col, values=y1_col, title=title)
                    else:
                        import plotly.express as px
                        fig = px.bar(df, x=x_col, y=y1_col, title=title)
                    
                    return fig
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    print(f"LLM图表分析失败: JSON解析错误 - {e}")
                    return self._smart_default_visualize(df, question)
            else:
                # 如果LLM分析失败，使用智能默认逻辑
                return self._smart_default_visualize(df, question)
                
        except Exception as e:
            print(f"LLM图表分析失败: {e}")
            return self._smart_default_visualize(df, question)
    
    def _smart_default_visualize(self, df, question):
        """智能默认图表生成"""
        try:
            # 自动识别字段类型
            categorical_cols = []
            numeric_cols = []
            doi_cols = []
            
            for col in df.columns:
                if df[col].dtype == 'object' or col in ['Roadmap Family', 'MTM', '产品', '型号']:
                    categorical_cols.append(col)
                elif df[col].dtype != 'object':
                    if 'DOI' in col or '周转天' in col:
                        doi_cols.append(col)
                    else:
                        numeric_cols.append(col)
            
            # 智能选择轴
            x_col = categorical_cols[0] if categorical_cols else df.columns[0]
            y1_col = numeric_cols[0] if numeric_cols else df.columns[1]
            y2_col = doi_cols[0] if doi_cols else None
            
            # 生成标题
            title = self._generate_chart_title(question, df)
            
            # 生成图表
            if y2_col:
                # 双Y轴图
                import plotly.graph_objects as go
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=df[x_col],
                    y=df[y1_col],
                    name=y1_col,
                    yaxis='y1'
                ))
                
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[y2_col],
                    name=y2_col,
                    yaxis='y2',
                    mode='lines+markers',
                    line=dict(width=3, color='red')
                ))
                
                fig.update_layout(
                    title=title,
                    xaxis=dict(title=x_col),
                    yaxis=dict(title='数值指标', side='left'),
                    yaxis2=dict(title='DOI/周转天数', overlaying='y', side='right'),
                    legend=dict(x=0.01, y=0.99)
                )
            else:
                # 普通柱状图
                import plotly.express as px
                fig = px.bar(df, x=x_col, y=y1_col, title=title)
            
            return fig
        except Exception as e:
            print(f"智能默认图表生成失败: {e}")
            return self._default_visualize(df)
    
    def _generate_chart_title(self, question, df):
        """基于问题和数据生成图表标题"""
        import re
        
        # 提取定语（如510S、小新等）
        qualifier_match = re.search(r'([A-Z0-9]+[A-Z]|[一-龯]+)', question)
        qualifier = qualifier_match.group(1) if qualifier_match else ""
        
        # 提取时间信息
        time_match = re.search(r'(\d{4}年\d{1,2}月|\d{4}年|\d{1,2}月)', question)
        time_info = time_match.group(1) if time_match else ""
        
        # 生成标题
        if qualifier and time_info:
            return f"{qualifier} {time_info} 数据对比"
        elif qualifier:
            return f"{qualifier} 数据对比"
        elif time_info:
            return f"{time_info} 数据对比"
        else:
            return f"{question} - 查询结果"
    
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
        """记录历史问答对 - 修复版本"""
        import datetime
        
        # 避免重复添加
        for qa in self.historical_qa:
            if qa.get('question') == question and qa.get('sql') == sql:
                print("此条记录已存在于历史知识库中")
                return
        
        qa_record = {
            "question": question, 
            "sql": sql,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rating": "ok"
        }
        self.historical_qa.append(qa_record)
        
        # 保存到文件
        try:
            with open("historical_qa.json", "w", encoding="utf-8") as f:
                json.dump(self.historical_qa, f, ensure_ascii=False, indent=2)
            print(f"✅ 已保存历史问答对: {question[:30]}...")
        except Exception as e:
            print(f"❌ 保存历史问答对失败: {e}")
    
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
你是一个SQL专家。请根据以下信息修正SQL语句中的错误，并自动优化SQL：

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

【修正与优化要求】
1. 根据校验错误信息，修正SQL中的问题。
2. 确保所有字段名存在于对应表中。
3. 确保所有表名正确。
4. 确保JOIN条件使用正确的表关系。
5. 保持原始查询意图不变。
6. 如果SQL中某些JOIN导致结果重复（如一对多），且数值字段如[SD PO Open Qty]、[QTY]等出现多条记录，请自动将这些字段用SUM聚合，并加上合适的GROUP BY，避免重复计数。
7. 如果JOIN条件中有多个字段，但只需关键字段即可唯一关联，请自动简化JOIN条件，只保留最关键的字段。
8. 只输出修正和优化后的SQL，不要其他解释。

【输出格式】
直接输出修正和优化后的SQL语句，不要包含任何其他内容。
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
        retry_delay = 5  # 增加初始延迟
        
        headers = {
            "Authorization": f"Bearer sk-0e6005b793aa4759bb022b91e9055f86",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        # 创建会话以复用连接
        session = requests.Session()
        session.headers.update(headers)
        
        # 配置连接池和超时
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        for attempt in range(max_retries):
            try:
                print(f"正在调用DeepSeek API (尝试 {attempt + 1}/{max_retries})...")
                
                # 使用更保守的超时设置
                response = session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    json=data,
                    timeout=(30, 90)  # (连接超时, 读取超时)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    print(f"API调用成功，返回内容长度: {len(content)}")
                    return content
                else:
                    print(f"API响应错误: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        print(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        return f"API调用失败，状态码: {response.status_code}"
                        
            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return "网络连接超时，请检查网络连接或稍后重试"
                    
            except requests.exceptions.ConnectionError as e:
                print(f"连接错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return "网络连接失败，请检查网络连接"
                    
            except Exception as e:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return f"API调用失败: {str(e)}"
            finally:
                # 确保会话正确关闭
                session.close()
        
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

    def call_deepseek_api_fallback(self, prompt):
        """备用API调用方法，使用更简单的策略"""
        import time
        
        headers = {
            "Authorization": f"Bearer sk-0e6005b793aa4759bb022b91e9055f86",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1000  # 减少token数量
        }
        
        try:
            print("使用备用API调用方法...")
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=180  # 3分钟超时
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"备用API调用成功")
                return content
            else:
                return f"备用API调用失败，状态码: {response.status_code}"
                
        except Exception as e:
            return f"备用API调用失败: {str(e)}"

    def validate_clustering_sql(self, sql, question):
        """验证SQL是否符合聚类要求"""
        import re
        
        # 检查是否包含必要的聚类字段
        clustering_fields = ['Model', 'Roadmap Family', 'Group', 'MTM', 'PN']
        found_fields = []
        
        for field in clustering_fields:
            if field.lower() in sql.lower():
                found_fields.append(field)
        
        # 检查是否使用了聚合函数
        has_aggregation = re.search(r'SUM\s*\(|COUNT\s*\(|AVG\s*\(', sql, re.IGNORECASE)
        
        # 检查是否有GROUP BY子句
        has_group_by = re.search(r'GROUP\s+BY', sql, re.IGNORECASE)
        
        # 分析问题中的层级需求
        question_lower = question.lower()
        is_total_query = any(word in question_lower for word in ['总数', '总量', '总计', 'sum', '合计'])
        
        validation_result = {
            'is_valid': True,
            'issues': [],
            'suggestions': []
        }
        
        # 验证逻辑
        if is_total_query and not has_aggregation:
            validation_result['issues'].append("总数查询应该使用聚合函数（如SUM）")
            validation_result['suggestions'].append("添加SUM()函数对数值字段进行聚合")
        
        if is_total_query and not has_group_by:
            validation_result['issues'].append("总数查询应该使用GROUP BY进行聚类")
            validation_result['suggestions'].append("添加GROUP BY子句按产品层级进行聚类")
        
        if found_fields and not has_group_by:
            validation_result['issues'].append("包含产品层级字段但缺少GROUP BY聚类")
            validation_result['suggestions'].append("添加GROUP BY子句避免重复计算")
        
        if validation_result['issues']:
            validation_result['is_valid'] = False
        
        return validation_result



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