#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用产品匹配器
支持所有产品：510S、geek、小新、拯救者等
基于产品层级：MODEL -> [ROADMAP FAMILY] -> [GROUP]
"""

import json
import re
from typing import List, Dict, Optional

class UniversalProductMatcher:
    """通用产品匹配器"""
    
    def __init__(self):
        self.load_product_knowledge()
        self.init_product_patterns()
    
    def load_product_knowledge(self):
        """加载产品知识库"""
        try:
            with open('product_knowledge.json', 'r', encoding='utf-8') as f:
                self.product_knowledge = json.load(f)
        except:
            try:
                with open('product_knowledge.json', 'r', encoding='gbk') as f:
                    self.product_knowledge = json.load(f)
            except:
                self.product_knowledge = {"products": {}}
    
    def init_product_patterns(self):
        """初始化产品模式"""
        # 从产品知识库中提取所有产品系列
        roadmap_families = set()
        for pn, product in self.product_knowledge.get('products', {}).items():
            if 'Roadmap Family' in product and product['Roadmap Family'] != 'ttl':
                roadmap_families.add(product['Roadmap Family'])
        
        # 建立产品关键词到roadmap family的映射
        self.product_patterns = {
            # 基于实际数据的映射
            "510S": {"pattern": "510S", "families": []},
            "510s": {"pattern": "510S", "families": []},
            "geek": {"pattern": "Geek", "families": []},
            "GeekPro": {"pattern": "Geek", "families": []},
            "小新": {"pattern": "小新", "families": []},
            "拯救者": {"pattern": "拯救者", "families": []},
            "AIO": {"pattern": "AIO", "families": []},
            "BOX": {"pattern": "BOX", "families": []},
        }
        
        # 填充实际的families
        for family in roadmap_families:
            for keyword, config in self.product_patterns.items():
                if config["pattern"] in family:
                    config["families"].append(family)
        
        # 清理空的模式
        self.product_patterns = {k: v for k, v in self.product_patterns.items() if v["families"]}
    
    def detect_product_in_question(self, question: str) -> Optional[Dict]:
        """从问题中检测产品"""
        question_lower = question.lower()
        
        # 按优先级检测产品关键词
        for keyword, config in self.product_patterns.items():
            if keyword.lower() in question_lower:
                return {
                    "keyword": keyword,
                    "pattern": config["pattern"],
                    "families": config["families"]
                }
        
        return None
    
    def generate_product_conditions(self, question: str) -> List[str]:
        """生成产品条件 - 通用逻辑"""
        conditions = []
        
        product_info = self.detect_product_in_question(question)
        if product_info:
            # 使用通用的产品层级逻辑
            pattern = product_info["pattern"]
            conditions.append(f"[Roadmap Family] LIKE '%{pattern}%'")
            conditions.append("[Group] = 'ttl'")
        
        return conditions
    
    def get_all_supported_products(self) -> Dict:
        """获取所有支持的产品"""
        return {k: v["families"] for k, v in self.product_patterns.items()}

class EnhancedSQLGenerator:
    """增强的SQL生成器 - 集成通用产品匹配"""
    
    def __init__(self):
        self.product_matcher = UniversalProductMatcher()
        self.load_knowledge()
        
        # 单表字段映射
        self.single_table_fields = [
            "全链库存", "财年", "财月", "财周", "Roadmap Family", "Group", "Model",
            "SellOut", "SellIn", "所有欠单", "成品总量", "BTC 库存总量", "联想DC库存"
        ]
    
    def load_knowledge(self):
        """加载知识库"""
        try:
            with open('business_rules.json', 'r', encoding='utf-8') as f:
                self.business_rules = json.load(f)
        except:
            self.business_rules = {}
    
    def should_use_single_table(self, question: str) -> bool:
        """判断是否应该使用单表查询"""
        # 提取目标字段
        target_fields = self.extract_target_fields(question)
        
        # 检查是否所有字段都在单表中
        fields_in_single_table = all(field in self.single_table_fields for field in target_fields)
        
        # 检查是否包含产品信息
        has_product = self.product_matcher.detect_product_in_question(question) is not None
        
        return fields_in_single_table and has_product
    
    def extract_target_fields(self, question: str) -> List[str]:
        """提取目标字段"""
        fields = []
        field_mapping = {
            "全链库存": "全链库存",
            "周转": "全链库存DOI",
            "DOI": "全链库存DOI",
            "SellOut": "SellOut", 
            "SellIn": "SellIn",
            "欠单": "所有欠单"
        }
        
        for keyword, field in field_mapping.items():
            if keyword in question:
                fields.append(field)
        
        return fields if fields else ["全链库存"]
    
    def generate_time_conditions(self, question: str) -> List[str]:
        """生成时间条件"""
        conditions = []
        
        # 年份：25年 -> 2025
        year_match = re.search(r'(\d{2})年', question)
        if year_match:
            year_value = int("20" + year_match.group(1))
            conditions.append(f"[财年] = {year_value}")
        
        # 月份：7月 -> "7月"
        month_match = re.search(r'(\d{1,2})月', question)
        if month_match:
            month_str = month_match.group(1) + "月"
            conditions.append(f"[财月] = '{month_str}'")
        
        # 特殊标识
        if "全链库存" in question:
            conditions.append("[财周] = 'ttl'")
        
        return conditions
    
    def generate_sql(self, question: str) -> str:
        """生成SQL - 主入口"""
        if self.should_use_single_table(question):
            return self.generate_single_table_sql(question)
        else:
            return self.generate_multi_table_sql(question)
    
    def generate_single_table_sql(self, question: str) -> str:
        """生成单表SQL"""
        # SELECT子句
        target_fields = self.extract_target_fields(question)
        field_list = ", ".join(f"[{field}]" for field in target_fields)
        select_clause = f"SELECT {field_list}"
        
        # FROM子句
        from_clause = "FROM [dtsupply_summary]"
        
        # WHERE条件
        where_conditions = []
        
        # 产品条件 - 使用通用匹配器
        product_conditions = self.product_matcher.generate_product_conditions(question)
        where_conditions.extend(product_conditions)
        
        # 时间条件
        time_conditions = self.generate_time_conditions(question)
        where_conditions.extend(time_conditions)
        
        # 组装SQL
        sql_parts = [select_clause, from_clause]
        if where_conditions:
            sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
        
        return " ".join(sql_parts)
    
    def generate_multi_table_sql(self, question: str) -> str:
        """生成多表SQL"""
        # 如果检测到产品但不在单表字段中，仍然尝试单表
        product_info = self.product_matcher.detect_product_in_question(question)
        if product_info:
            return self.generate_single_table_sql(question)
        
        return "SELECT * FROM [dtsupply_summary] WHERE 1=1"

# 测试函数
def test_universal_matcher():
    """测试通用匹配器"""
    generator = EnhancedSQLGenerator()
    
    test_questions = [
        "510S 25年7月全链库存",
        "geek产品今年的SellOut数据", 
        "小新系列2025年周转情况",
        "拯救者全链库存",
        "GeekPro产品库存"
    ]
    
    print("=== 通用产品匹配测试 ===")
    
    # 显示支持的产品
    supported_products = generator.product_matcher.get_all_supported_products()
    print("支持的产品:")
    for keyword, families in supported_products.items():
        print(f"  {keyword}: {families[:2]}...")  # 只显示前2个
    
    print(f"\n=== SQL生成测试 ===")
    for question in test_questions:
        print(f"\n问题: {question}")
        
        # 检测产品
        product_info = generator.product_matcher.detect_product_in_question(question)
        if product_info:
            print(f"检测到产品: {product_info['keyword']} -> {product_info['pattern']}")
        
        # 生成SQL
        sql = generator.generate_sql(question)
        print(f"SQL: {sql}")
        
        # 检查是否使用单表
        is_single_table = generator.should_use_single_table(question)
        print(f"使用单表: {is_single_table}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_universal_matcher()