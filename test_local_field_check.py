import json
import re
from text2sql_2_5_query import Text2SQLQueryEngine

def norm_table_name(name):
    # 只保留表名部分，去除数据库、dbo、[]、大小写
    if '.' in name:
        name = name.split('.')[-1]
    return name.replace('[','').replace(']','').strip().lower()

def norm_field_name(name):
    return name.replace('[','').replace(']','').strip().lower()

if __name__ == "__main__":
    # 读取table_knowledge.json
    with open("table_knowledge.json", "r", encoding="utf-8") as f:
        table_knowledge = json.load(f)
    # 读取table_relationships.json
    with open("table_relationships.json", "r", encoding="utf-8") as f:
        table_relationships = json.load(f)
    # 解析relationships为可比对结构
    rel_list = []
    if isinstance(table_relationships, dict) and 'relationships' in table_relationships:
        for rel in table_relationships['relationships']:
            # 优先用description解析
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
    else:
        rel_list = []
    # 初始化引擎
    engine = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=rel_list,
        business_rules=None,
        product_knowledge=None,
        historical_qa=None,
        vanna=None,
        db_manager=None
    )
    # 输入SQL
    sql = '''SELECT 
    s.[全链库存],
    b.[本月备货],
    p.[SD PO Open Qty] AS [未清PO数量]
FROM 
    [FF_IDSS_Dev_FF].[dbo].[dtsupply_summary] s
JOIN 
    [FF_IDSS_Dev_FF].[dbo].[CONPD] c ON s.[Roadmap Family] = c.[Roadmap Family] AND s.[Group] = c.[Group] AND s.[Model] = c.[Model]
JOIN 
    [FF_IDSS_Dev_FF].[dbo].[备货NY] b ON c.[PN] = b.[MTM]
JOIN 
    [FF_IDSS_Data_CON_BAK].[dbo].[ConDT_Open_PO] p ON c.[PN] = p.[PN]
WHERE 
    s.[Roadmap Family] LIKE '%510S%' 
    AND s.[Group] = 'ttl'
    AND s.[自然年] = YEAR(GETDATE()) 
    AND s.[财月] = CAST(MONTH(GETDATE()) AS VARCHAR) + '月' 
    AND s.[财周] = 'ttl' '''
    # 1. 解析表别名
    alias2table = {}
    from_pattern = r'FROM\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
    join_pattern = r'JOIN\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)'
    for pat in [from_pattern, join_pattern]:
        for m in re.findall(pat, sql, re.IGNORECASE):
            table, alias = m
            alias2table[alias] = norm_table_name(table)
    # 2. 字段校验
    print("字段校验结果:")
    select_pattern = r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]'
    for alias, field in re.findall(select_pattern, sql):
        table = alias2table.get(alias)
        if not table:
            print(f"  别名[{alias}]未找到对应表")
            continue
        matched_table = None
        for tk in table_knowledge:
            if norm_table_name(tk) == table:
                matched_table = tk
                break
        if not matched_table:
            print(f"  表[{table}]未在知识库中定义")
            continue
        # 兼容columns为字符串或字典
        columns = []
        for col in table_knowledge[matched_table]['columns']:
            if isinstance(col, dict) and 'name' in col:
                columns.append(norm_field_name(col['name']))
            elif isinstance(col, str):
                columns.append(norm_field_name(col))
        if norm_field_name(field) in columns:
            print(f"  表[{matched_table}] 字段[{field}] (别名:{alias}) : 存在")
        else:
            print(f"  表[{matched_table}] 字段[{field}] (别名:{alias}) : 不存在")
    # 3. 关系校验
    print("\n关系校验结果:")
    join_on_pattern = r'JOIN\s+([\w\[\]\.]+)\s+([a-zA-Z0-9_]+)\s+ON\s+([^\n]+)'
    for join_table, join_alias, on_clause in re.findall(join_on_pattern, sql, re.IGNORECASE):
        # 解析ON条件，支持多个AND
        on_pairs = re.findall(r'([a-zA-Z0-9_]+)\.\[([^\]]+)\]\s*=\s*([a-zA-Z0-9_]+)\.\[([^\]]+)\]', on_clause)
        for left_alias, left_field, right_alias, right_field in on_pairs:
            left_table = alias2table.get(left_alias)
            right_table = alias2table.get(right_alias)
            if not left_table or not right_table:
                print(f"  关系校验: 别名[{left_alias}]或[{right_alias}]未找到对应表")
                continue
            # 遍历rel_list查找匹配
            found = False
            for rel in rel_list:
                # 支持正反向
                if (
                    (rel['table1'] == left_table and rel['table2'] == right_table and rel['field1'] == norm_field_name(left_field) and rel['field2'] == norm_field_name(right_field)) or
                    (rel['table2'] == left_table and rel['table1'] == right_table and rel['field2'] == norm_field_name(left_field) and rel['field1'] == norm_field_name(right_field))
                ):
                    print(f"  关系校验: {left_table}--{right_table} 字段[{left_field}]--[{right_field}] 匹配")
                    found = True
                    break
            if not found:
                print(f"  关系校验: {left_table}--{right_table} 字段[{left_field}]--[{right_field}] 未在关系库中定义") 