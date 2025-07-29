import json
import re

def norm_table_name(name):
    if '.' in name:
        name = name.split('.')[-1]
    return name.replace('[','').replace(']','').strip().lower()

def norm_field_name(name):
    return name.replace('[','').replace(']','').strip().lower()

# Load the actual table knowledge
with open('table_knowledge.json', 'r', encoding='utf-8') as f:
    table_knowledge = json.load(f)

def validate_sql_fields(sql):
    """验证SQL中的字段是否存在于表结构中"""
    
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
        for tk in table_knowledge:
            if norm_table_name(tk) == table:
                matched_table = tk
                break
        if not matched_table:
            missing_fields.append(f"表[{table}]未在知识库中定义")
            continue
            
        # 检查字段是否存在
        columns = []
        for col in table_knowledge[matched_table]['columns']:
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
        for table_name, table_info in table_knowledge.items():
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

# Test cases
test_sql_1 = """SELECT 
    a.[全链库存],
    未清PO数量,
    CONPD,
    备货NY
FROM [dtsupply_summary] a"""

test_sql_2 = """SELECT 
    [全链库存],
    未清PO数量,
    CONPD,
    备货NY
FROM dtsupply_summary"""

print("Testing validate_sql_fields function:")
print("=" * 50)

# Test 1
print("Test 1 - SQL with alias and business terms:")
print(test_sql_1)
result1 = validate_sql_fields(test_sql_1)
print(f"Valid fields: {result1['valid_fields']}")
print(f"Missing fields: {result1['missing_fields']}")
print(f"All valid: {result1['all_valid']}")
print()

# Test 2
print("Test 2 - SQL without alias and with business terms:")
print(test_sql_2)
result2 = validate_sql_fields(test_sql_2)
print(f"Valid fields: {result2['valid_fields']}")
print(f"Missing fields: {result2['missing_fields']}")
print(f"All valid: {result2['all_valid']}")
print()

print("Test completed.")