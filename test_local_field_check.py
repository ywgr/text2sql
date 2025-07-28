import json
from text2sql_2_5_query import Text2SQLQueryEngine

if __name__ == "__main__":
    # 读取table_knowledge.json
    with open("table_knowledge.json", "r", encoding="utf-8") as f:
        table_knowledge = json.load(f)
    
    # 初始化引擎，只传table_knowledge，其它参数用None或空dict
    engine = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=None,
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
    AND s.[财周] = 'ttl'
'''
    
    # 输出本地字段校验结果
    print(engine.local_field_check(sql)) 