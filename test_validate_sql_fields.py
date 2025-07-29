import json
import os
import sys

# Add the current directory to the path so we can import text2sql_2_5_query
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from text2sql_2_5_query import Text2SQLQueryEngine, DatabaseManager, VannaWrapper

# Load the actual table knowledge from the JSON file
def load_table_knowledge():
    with open('table_knowledge.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Create mock objects for testing
class MockVanna:
    def __init__(self):
        pass

class MockDatabaseManager:
    def __init__(self):
        pass

# Load the actual table knowledge
table_knowledge = load_table_knowledge()

# Sample relationships for testing
relationships = []

# Sample business rules for testing
business_rules = {}

# Sample product knowledge for testing
product_knowledge = {}

# Sample historical QA for testing
historical_qa = []

# Sample prompt templates for testing
prompt_templates = {}

# Create the query engine
engine = Text2SQLQueryEngine(
    table_knowledge, relationships, business_rules,
    product_knowledge, historical_qa, MockVanna(), MockDatabaseManager(), prompt_templates
)

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
result1 = engine.validate_sql_fields(test_sql_1)
print(f"Valid fields: {result1['valid_fields']}")
print(f"Missing fields: {result1['missing_fields']}")
print(f"All valid: {result1['all_valid']}")
print()

# Test 2
print("Test 2 - SQL without alias and with business terms:")
print(test_sql_2)
result2 = engine.validate_sql_fields(test_sql_2)
print(f"Valid fields: {result2['valid_fields']}")
print(f"Missing fields: {result2['missing_fields']}")
print(f"All valid: {result2['all_valid']}")
print()

print("Test completed.")