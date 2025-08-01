#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的关系校验功能
验证系统能正确识别手工添加的关系，特别是备货NY和ConDT_Open_PO的关系
"""

import json
import os
from text2sql_2_5_query import Text2SQLQueryEngine, VannaWrapper, DatabaseManager

def load_json(path):
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件 {path} 不存在")
        return {}
    except Exception as e:
        print(f"加载 {path} 失败: {e}")
        return {}

def test_relationship_validation_fix():
    """测试修复后的关系校验功能"""
    print("=== 测试修复后的关系校验功能 ===")
    
    # 1. 加载知识库
    print("\n1. 加载知识库...")
    table_knowledge = load_json('table_knowledge.json')
    relationships = load_json('table_relationships.json')
    business_rules = load_json('business_rules.json')
    product_knowledge = load_json('product_knowledge.json')
    historical_qa = load_json('historical_qa.json')
    
    # 2. 初始化系统
    print("\n2. 初始化系统...")
    vanna = VannaWrapper()
    db_manager = DatabaseManager()
    
    system = Text2SQLQueryEngine(
        table_knowledge=table_knowledge,
        relationships=relationships,
        business_rules=business_rules,
        product_knowledge=product_knowledge,
        historical_qa=historical_qa,
        vanna=vanna,
        db_manager=db_manager,
        prompt_templates={}
    )
    
    # 3. 检查备货NY表的关系定义
    print("\n3. 检查备货NY表的关系定义...")
    if "备货NY" in table_knowledge:
        beihuo_relationships = table_knowledge["备货NY"].get("relationships", [])
        print(f"备货NY表的关系定义:")
        for rel in beihuo_relationships:
            print(f"  - {rel}")
        
        # 查找CONPD.PN <-> 备货NY.MTM的关系
        found_relationship = False
        for rel in beihuo_relationships:
            if "CONPD.PN <-> 备货NY.MTM" in rel.get("description", ""):
                found_relationship = True
                print(f"✅ 找到关系: {rel['description']}")
                break
        
        if not found_relationship:
            print("❌ 未找到CONPD.PN <-> 备货NY.MTM的关系")
    else:
        print("❌ 备货NY表不在知识库中")
    
    # 4. 检查ConDT_Open_PO表的关系定义
    print("\n4. 检查ConDT_Open_PO表的关系定义...")
    if "ConDT_Open_PO" in table_knowledge:
        condt_relationships = table_knowledge["ConDT_Open_PO"].get("relationships", [])
        print(f"ConDT_Open_PO表的关系定义:")
        for rel in condt_relationships:
            print(f"  - {rel}")
    else:
        print("❌ ConDT_Open_PO表不在知识库中")
    
    # 5. 测试有问题的SQL
    print("\n5. 测试有问题的SQL...")
    problematic_sql = """
    SELECT 
        s.[全链库存],
        b.[本月备货],
        p.[未清PO数量]
    FROM 
        [FF_IDSS_Dev_FF].[dbo].[dtsupply_summary] s
    JOIN 
        [FF_IDSS_Dev_FF].[dbo].[CONPD] c ON s.[Roadmap Family] = c.[Roadmap Family]
    JOIN 
        [FF_IDSS_Dev_FF].[dbo].[备货NY] b ON c.[PN] = b.[MTM]
    JOIN 
        [FF_IDSS_Data_CON_BAK].[dbo].[ConDT_Open_PO] p ON c.[PN] = p.[PN]
    WHERE 
        s.[Roadmap Family] LIKE '%510S%' 
        AND s.[Group] = 'ttl'
        AND s.[自然年] = 2025
        AND s.[财月] = '7月'
        AND s.[财周] = 'ttl'
    """
    
    print(f"测试SQL:\n{problematic_sql}")
    
    # 6. 进行本地校验
    print("\n6. 进行本地校验...")
    local_check_result = system.enhanced_local_field_check(problematic_sql)
    print(f"本地校验结果:\n{local_check_result}")
    
    # 7. 分析关系校验结果
    print("\n7. 分析关系校验结果...")
    if "关系校验" in local_check_result:
        if "未在关系库中定义" in local_check_result:
            print("❌ 仍然存在关系校验误报")
        elif "匹配" in local_check_result:
            print("✅ 关系校验正确识别了关系")
        else:
            print("⚠️ 关系校验结果不明确")
    else:
        print("✅ 没有关系校验问题")
    
    # 8. 测试另一个SQL（包含备货NY和ConDT_Open_PO的JOIN）
    print("\n8. 测试另一个SQL（包含备货NY和ConDT_Open_PO的JOIN）...")
    test_sql2 = """
    SELECT 
        b.[本月备货],
        p.[Qty]
    FROM 
        [FF_IDSS_Dev_FF].[dbo].[备货NY] b
    JOIN 
        [FF_IDSS_Data_CON_BAK].[dbo].[ConDT_Open_PO] p ON b.[MTM] = p.[PN]
    WHERE 
        b.[MTM] = '90V2001KCP'
    """
    
    print(f"测试SQL2:\n{test_sql2}")
    
    local_check_result2 = system.enhanced_local_field_check(test_sql2)
    print(f"本地校验结果2:\n{local_check_result2}")
    
    # 9. 总结
    print("\n9. 总结...")
    print("✅ 修复内容:")
    print("   - 从table_knowledge中收集所有关系定义")
    print("   - 支持手工添加的关系格式")
    print("   - 改进表名和字段名的标准化处理")
    
    print("\n✅ 预期效果:")
    print("   - 正确识别CONPD.PN <-> 备货NY.MTM关系")
    print("   - 不再误报'备货ny--condt_open_po 字段[MTM]--[PN] 未在关系库中定义'")
    print("   - 支持手工添加的关系格式")

if __name__ == "__main__":
    test_relationship_validation_fix() 