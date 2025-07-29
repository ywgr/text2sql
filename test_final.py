import json
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

# Create the query engine
engine = Text2SQLQueryEngine(
    table_knowledge, [], {}, {}, [], MockVanna(), MockDatabaseManager(), {}
)

# Test SQL with business terms
test_sql = "SELECT a.[全链库存], 未清PO数量, CONPD, 备货NY FROM [dtsupply_summary] a"

print("Testing validate_sql_fields function with actual data:")
print("=" * 60)
print("SQL:", test_sql)
print()

result = engine.validate_sql_fields(test_sql)
print("Valid fields:", result['valid_fields'])
print("Missing fields:", result['missing_fields'])
print("All valid:", result['all_valid'])

# Check if business terms are correctly handled
business_terms = ["未清PO数量", "CONPD", "备货NY"]
print()
print("Business terms check:")
for term in business_terms:
    if term in result['missing_fields']:
        print(f"ERROR: Business term '{term}' incorrectly flagged as missing")
    else:
        print(f"OK: Business term '{term}' correctly handled")

# Check if real database fields are correctly validated
print()
print("Database field validation:")
if "全链库存" in str(result['valid_fields']):
    print("OK: Database field '全链库存' correctly validated")
else:
    print("ERROR: Database field '全链库存' not correctly validated")