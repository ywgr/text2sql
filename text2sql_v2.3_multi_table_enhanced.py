#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 V2.3 多表查询增强版本
基于AI咨询建议的多表查询优化实现
主要改进：
1. 强化数据结构知识库的「关系显性化」
2. 优化专用术语映射的「场景化绑定」
3. 细化业务规则的「关联逻辑模板」
4. 重构提示词：引导模型「分步推理」
5. 添加「自动校验机制」修复生成的SQL
"""

import streamlit as st
import pandas as pd
import json
import re
import time
import hashlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TableRelationship:
    """表关系结构化描述"""
    table1: str
    field1: str
    table2: str
    field2: str
    relation_type: str  # "一对一", "一对多", "多对多"
    business_meaning: str
    confidence: float = 1.0
    is_mandatory: bool = True  # 是否为必须关联

@dataclass
class FieldBinding:
    """字段从属关系的唯一化绑定"""
    field_name: str
    table_name: str
    business_term: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    related_tables: List[str] = None

@dataclass
class QueryScenario:
    """查询场景模板"""
    scenario_name: str
    involved_tables: List[str]
    relation_chain: List[TableRelationship]
    common_fields: List[str]
    business_logic: str
    sql_template: str

class EnhancedRelationshipManager:
    """增强的关系管理器"""
    
    def __init__(self):
        self.table_relationships: List[TableRelationship] = []
        self.field_bindings: Dict[str, List[FieldBinding]] = {}
        self.query_scenarios: List[QueryScenario] = []
        self.forbidden_relations: List[Tuple[str, str, str]] = []  # (table1, table2, reason)
        
    def add_relationship(self, relationship: TableRelationship):
        """添加表关系"""
        # 检查是否已存在相同关系
        existing = self.find_relationship(relationship.table1, relationship.table2)
        if existing:
            # 更新现有关系
            existing.confidence = max(existing.confidence, relationship.confidence)
            existing.business_meaning = relationship.business_meaning
        else:
            self.table_relationships.append(relationship)
    
    def find_relationship(self, table1: str, table2: str) -> Optional[TableRelationship]:
        """查找表关系"""
        for rel in self.table_relationships:
            if ((rel.table1 == table1 and rel.table2 == table2) or 
                (rel.table1 == table2 and rel.table2 == table1)):
                return rel
        return None
    
    def get_relation_chain(self, start_table: str, end_table: str) -> List[TableRelationship]:
        """获取表关联链路"""
        # 使用BFS查找最短关联路径
        from collections import deque
        
        if start_table == end_table:
            return []
        
        queue = deque([(start_table, [])])
        visited = {start_table}
        
        while queue:
            current_table, path = queue.popleft()
            
            # 查找与当前表相关的所有关系
            for rel in self.table_relationships:
                next_table = None
                if rel.table1 == current_table:
                    next_table = rel.table2
                elif rel.table2 == current_table:
                    next_table = rel.table1
                
                if next_table and next_table not in visited:
                    new_path = path + [rel]
                    
                    if next_table == end_table:
                        return new_path
                    
                    visited.add(next_table)
                    queue.append((next_table, new_path))
        
        return []  # 未找到关联路径
    
    def add_field_binding(self, binding: FieldBinding):
        """添加字段绑定"""
        if binding.table_name not in self.field_bindings:
            self.field_bindings[binding.table_name] = []
        
        # 检查是否已存在
        existing = next((b for b in self.field_bindings[binding.table_name] 
                        if b.field_name == binding.field_name), None)
        if existing:
            existing.business_term = binding.business_term
            existing.data_type = binding.data_type
        else:
            self.field_bindings[binding.table_name].append(binding)
    
    def get_field_table(self, field_name: str) -> List[Tuple[str, FieldBinding]]:
        """获取字段所属的表"""
        results = []
        for table_name, bindings in self.field_bindings.items():
            for binding in bindings:
                if binding.field_name.lower() == field_name.lower():
                    results.append((table_name, binding))
        return results
    
    def add_forbidden_relation(self, table1: str, table2: str, reason: str):
        """添加禁止关联的表对"""
        self.forbidden_relations.append((table1, table2, reason))
    
    def is_forbidden_relation(self, table1: str, table2: str) -> Tuple[bool, str]:
        """检查是否为禁止关联"""
        for t1, t2, reason in self.forbidden_relations:
            if ((t1 == table1 and t2 == table2) or (t1 == table2 and t2 == table1)):
                return True, reason
        return False, ""

class ScenarioBasedTermMapper:
    """场景化术语映射器"""
    
    def __init__(self):
        self.scenario_mappings: Dict[str, Dict[str, str]] = {}
        self.ambiguous_terms: Dict[str, List[Dict]] = {}
    
    def add_scenario_mapping(self, scenario: str, term: str, table_combination: List[str], 
                           core_field: str, join_conditions: List[str]):
        """添加场景化术语映射"""
        if scenario not in self.scenario_mappings:
            self.scenario_mappings[scenario] = {}
        
        self.scenario_mappings[scenario][term] = {
            "tables": table_combination,
            "core_field": core_field,
            "join_conditions": join_conditions,
            "description": f"在{scenario}场景下，{term}涉及表：{', '.join(table_combination)}"
        }
    
    def add_ambiguous_term(self, term: str, scenarios: List[Dict]):
        """添加歧义术语的场景区分"""
        self.ambiguous_terms[term] = scenarios
    
    def resolve_term_in_context(self, term: str, question_context: str) -> Dict:
        """根据上下文解析术语"""
        # 检查是否为歧义术语
        if term in self.ambiguous_terms:
            for scenario in self.ambiguous_terms[term]:
                if any(keyword in question_context for keyword in scenario.get("keywords", [])):
                    return scenario
        
        # 检查场景映射
        for scenario, mappings in self.scenario_mappings.items():
            if term in mappings and any(keyword in question_context 
                                      for keyword in scenario.split("_")):
                return mappings[term]
        
        return {}

class StructuredPromptBuilder:
    """结构化提示词构建器"""
    
    def __init__(self, relation_manager: EnhancedRelationshipManager, 
                 term_mapper: ScenarioBasedTermMapper):
        self.relation_manager = relation_manager
        self.term_mapper = term_mapper
        
    def build_multi_table_prompt(self, question: str, table_knowledge: Dict, 
                                business_rules: Dict, schema_info: str) -> str:
        """构建多表查询专用提示词"""
        
        # 1. 构建带关系的表结构元数据
        enhanced_metadata = self._build_enhanced_metadata(table_knowledge)
        
        # 2. 构建关联逻辑模板
        relation_templates = self._build_relation_templates()
        
        # 3. 构建分步推理指令
        reasoning_steps = self._build_reasoning_steps()
        
        # 4. 构建反面示例约束
        negative_constraints = self._build_negative_constraints()
        
        # 5. 构建自我校验指令
        validation_instructions = self._build_validation_instructions()
        
        prompt = f"""你是一个专业的SQL专家，专门处理复杂的多表查询。请严格按照以下流程处理用户问题。

{reasoning_steps}

{enhanced_metadata}

{relation_templates}

{negative_constraints}

【术语映射和业务规则】
{json.dumps(business_rules, ensure_ascii=False, indent=2)}

【用户问题】
{question}

{validation_instructions}

【输出要求】
1. 必须输出完整的推理过程（步骤1-4）
2. 生成的SQL必须遵循格式约束
3. 完成自我校验并输出校验结果
4. 最终输出一个可执行的SQL语句

开始分析："""

        return prompt
    
    def _build_enhanced_metadata(self, table_knowledge: Dict) -> str:
        """构建增强的元数据"""
        metadata = "【表结构及关系】\n"
        
        for table_name, table_info in table_knowledge.items():
            metadata += f"\n{table_name}表：\n"
            
            # 字段信息
            columns = table_info.get('columns', [])
            metadata += f"  字段：{', '.join(columns)}\n"
            
            # 主键和外键信息
            primary_keys = []
            foreign_keys = []
            
            for binding in self.relation_manager.field_bindings.get(table_name, []):
                if binding.is_primary_key:
                    primary_keys.append(binding.field_name)
                if binding.is_foreign_key:
                    foreign_keys.append(f"{binding.field_name}(关联{binding.related_tables})")
            
            if primary_keys:
                metadata += f"  主键：{', '.join(primary_keys)}\n"
            if foreign_keys:
                metadata += f"  外键：{', '.join(foreign_keys)}\n"
            
            # 关联关系
            relations = [rel for rel in self.relation_manager.table_relationships 
                        if rel.table1 == table_name or rel.table2 == table_name]
            
            if relations:
                metadata += "  关联关系：\n"
                for rel in relations:
                    other_table = rel.table2 if rel.table1 == table_name else rel.table1
                    metadata += f"    - 与{other_table}：{rel.field1} = {rel.field2} ({rel.relation_type})\n"
                    metadata += f"      业务含义：{rel.business_meaning}\n"
            
            # 业务备注
            comment = table_info.get('comment', '')
            if comment:
                metadata += f"  业务说明：{comment}\n"
        
        # 禁止关联的表对
        if self.relation_manager.forbidden_relations:
            metadata += "\n【禁止直接关联的表对】\n"
            for table1, table2, reason in self.relation_manager.forbidden_relations:
                metadata += f"- {table1} 与 {table2}：{reason}\n"
        
        return metadata
    
    def _build_relation_templates(self) -> str:
        """构建关联逻辑模板"""
        templates = "\n【常见关联模板】\n"
        
        for scenario in self.relation_manager.query_scenarios:
            templates += f"\n场景：{scenario.scenario_name}\n"
            templates += f"涉及表：{' → '.join(scenario.involved_tables)}\n"
            templates += f"关联链：\n"
            
            for rel in scenario.relation_chain:
                templates += f"  {rel.table1}.{rel.field1} = {rel.table2}.{rel.field2}\n"
            
            templates += f"业务逻辑：{scenario.business_logic}\n"
            templates += f"SQL模板：{scenario.sql_template}\n"
        
        return templates
    
    def _build_reasoning_steps(self) -> str:
        """构建分步推理指令"""
        return """【必须严格按以下4步执行，每步都要输出结果】

步骤1：实体识别
- 从问题中提取所有业务实体（如"客户""订单""商品"）
- 将每个实体对应到数据库中的具体表名
- 说明选择该表的理由

步骤2：关联关系确认
- 对每对相关表，写出具体的关联字段（如"客户表.客户ID = 订单表.客户ID"）
- 说明关联类型（一对一/一对多/多对多）
- 说明关联的业务逻辑

步骤3：字段归属绑定
- 将问题中的所有属性绑定到具体表的字段
- 格式："属性名 → 表名.字段名"
- 如有字段名重复，说明选择该表的理由

步骤4：表关系校验
- 列出所有涉及的表
- 检查表之间是否有完整的关联路径
- 排除无关表并说明理由"""
    
    def _build_negative_constraints(self) -> str:
        """构建反面示例约束"""
        return """
【严格禁止的错误】
1. 字段归属错误：禁止将字段写到错误的表前缀（如订单金额写成customer.amount）
2. 关联条件缺失：多表查询必须有明确的JOIN条件，禁止用WHERE隐式关联
3. 冗余表关联：只关联问题明确涉及的表，不要添加无关表
4. 聚合遗漏GROUP BY：使用聚合函数时必须正确分组
5. 跨表直接关联：禁止跳过中间表直接关联（如客户表直接关联商品表）
6. 字段名歧义：所有字段必须带表别名，避免同名字段混淆"""
    
    def _build_validation_instructions(self) -> str:
        """构建自我校验指令"""
        return """
【生成SQL后必须执行自我校验】
1. 表检查：SQL中的所有表是否都在步骤1识别的实体中？
2. 字段检查：每个字段是否属于其前缀表？是否在表结构中存在？
3. 关联检查：多表查询是否有完整的JOIN条件？关联字段是否正确？
4. 业务检查：是否符合业务逻辑？是否有逻辑矛盾？
5. 格式检查：是否使用了表别名？是否遵循了SQL格式约束？

【SQL格式约束】
- 所有表必须使用别名（如customer AS c）
- 所有字段必须带表别名（如c.name）
- 多表关联必须用显式JOIN，禁用逗号连接
- 聚合函数必须有别名
- 日期条件必须使用明确格式"""

class MultiTableSQLValidator:
    """多表SQL验证器"""
    
    def __init__(self, relation_manager: EnhancedRelationshipManager):
        self.relation_manager = relation_manager
    
    def validate_multi_table_sql(self, sql: str, question: str, 
                                table_knowledge: Dict) -> Tuple[bool, List[str], str]:
        """验证多表SQL"""
        issues = []
        corrected_sql = sql
        
        try:
            # 1. 提取SQL中的表和字段
            tables_in_sql = self._extract_tables_from_sql(sql)
            fields_in_sql = self._extract_fields_from_sql(sql)
            
            # 2. 验证表的合理性
            table_issues = self._validate_tables_relevance(tables_in_sql, question)
            issues.extend(table_issues)
            
            # 3. 验证字段归属
            field_issues, corrected_sql = self._validate_field_ownership(
                fields_in_sql, tables_in_sql, table_knowledge, corrected_sql)
            issues.extend(field_issues)
            
            # 4. 验证JOIN关系
            join_issues, corrected_sql = self._validate_join_relationships(
                corrected_sql, tables_in_sql)
            issues.extend(join_issues)
            
            # 5. 验证关联路径完整性
            path_issues = self._validate_relation_paths(tables_in_sql)
            issues.extend(path_issues)
            
            # 6. 验证业务逻辑
            logic_issues = self._validate_business_logic(corrected_sql, question)
            issues.extend(logic_issues)
            
            is_valid = len([issue for issue in issues if issue.startswith("ERROR")]) == 0
            
            return is_valid, issues, corrected_sql
            
        except Exception as e:
            logger.error(f"多表SQL验证失败: {e}")
            return False, [f"ERROR: 验证过程出错 - {str(e)}"], sql
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """从SQL中提取表名"""
        tables = []
        
        # 匹配FROM和JOIN后的表名
        patterns = [
            r'FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?',
            r'JOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                table_name = match[0]
                tables.append(table_name)
        
        return list(set(tables))
    
    def _extract_fields_from_sql(self, sql: str) -> List[Tuple[str, str]]:
        """从SQL中提取字段名和表别名"""
        fields = []
        
        # 匹配 表别名.字段名 的模式
        field_pattern = re.compile(r'(\w+)\.(\w+)')
        matches = field_pattern.findall(sql)
        
        for table_alias, field_name in matches:
            fields.append((table_alias, field_name))
        
        return fields
    
    def _validate_tables_relevance(self, tables_in_sql: List[str], question: str) -> List[str]:
        """验证表的相关性"""
        issues = []
        
        # 简单的关键词匹配来判断表是否相关
        question_lower = question.lower()
        
        for table in tables_in_sql:
            table_lower = table.lower()
            
            # 检查表名是否在问题中出现或有相关词汇
            if (table_lower not in question_lower and 
                not any(keyword in question_lower for keyword in [
                    table_lower[:3], "订单", "客户", "商品", "用户", "产品"
                ])):
                issues.append(f"WARNING: 表 {table} 可能与问题不相关")
        
        return issues
    
    def _validate_field_ownership(self, fields_in_sql: List[Tuple[str, str]], 
                                 tables_in_sql: List[str], table_knowledge: Dict,
                                 sql: str) -> Tuple[List[str], str]:
        """验证字段归属"""
        issues = []
        corrected_sql = sql
        corrections = []
        
        # 构建表别名映射
        alias_map = self._parse_table_aliases(sql)
        
        for table_alias, field_name in fields_in_sql:
            if table_alias in alias_map:
                actual_table = alias_map[table_alias]
                
                if actual_table in table_knowledge:
                    columns = table_knowledge[actual_table].get('columns', [])
                    
                    if field_name not in columns:
                        # 查找相似字段
                        from difflib import get_close_matches
                        candidates = get_close_matches(field_name, columns, n=1, cutoff=0.6)
                        
                        if candidates:
                            corrections.append((f"{table_alias}.{field_name}", 
                                              f"{table_alias}.{candidates[0]}"))
                            issues.append(f"WARNING: 字段 {field_name} 不存在于表 {actual_table}，建议使用 {candidates[0]}")
                        else:
                            issues.append(f"ERROR: 表 {actual_table} 中不存在字段 {field_name}")
        
        # 应用修正
        for old, new in corrections:
            corrected_sql = corrected_sql.replace(old, new)
        
        return issues, corrected_sql
    
    def _validate_join_relationships(self, sql: str, tables_in_sql: List[str]) -> Tuple[List[str], str]:
        """验证JOIN关系"""
        issues = []
        corrected_sql = sql
        
        if len(tables_in_sql) > 1:
            # 检查是否有JOIN条件
            join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
            on_count = len(re.findall(r'\bON\b', sql, re.IGNORECASE))
            
            if join_count > on_count:
                issues.append("ERROR: JOIN缺少对应的ON条件")
            
            # 验证JOIN条件是否使用了正确的关联字段
            join_conditions = re.findall(r'ON\s+(\w+\.\w+)\s*=\s*(\w+\.\w+)', sql, re.IGNORECASE)
            
            for left_field, right_field in join_conditions:
                # 检查关联字段是否在关系管理器中定义
                left_parts = left_field.split('.')
                right_parts = right_field.split('.')
                
                if len(left_parts) == 2 and len(right_parts) == 2:
                    # 这里可以添加更复杂的关联验证逻辑
                    pass
        
        return issues, corrected_sql
    
    def _validate_relation_paths(self, tables_in_sql: List[str]) -> List[str]:
        """验证关联路径完整性"""
        issues = []
        
        if len(tables_in_sql) > 2:
            # 检查是否所有表都有关联路径
            for i, table1 in enumerate(tables_in_sql):
                for table2 in tables_in_sql[i+1:]:
                    relation_chain = self.relation_manager.get_relation_chain(table1, table2)
                    
                    if not relation_chain:
                        # 检查是否为禁止关联
                        is_forbidden, reason = self.relation_manager.is_forbidden_relation(table1, table2)
                        
                        if is_forbidden:
                            issues.append(f"ERROR: {table1} 与 {table2} 禁止直接关联：{reason}")
                        else:
                            issues.append(f"WARNING: {table1} 与 {table2} 之间没有定义关联路径")
        
        return issues
    
    def _validate_business_logic(self, sql: str, question: str) -> List[str]:
        """验证业务逻辑"""
        issues = []
        
        # 检查一些常见的业务逻辑错误
        if "SUM(" in sql.upper() and "GROUP BY" not in sql.upper():
            issues.append("WARNING: 使用聚合函数但缺少GROUP BY子句")
        
        if "COUNT(" in sql.upper() and "DISTINCT" not in sql.upper():
            issues.append("INFO: 考虑是否需要使用COUNT(DISTINCT ...)避免重复计数")
        
        return issues
    
    def _parse_table_aliases(self, sql: str) -> Dict[str, str]:
        """解析表别名映射"""
        alias_map = {}
        
        # 匹配 表名 AS 别名 或 表名 别名
        patterns = [
            r'FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?',
            r'JOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                table_name = match[0]
                alias = match[1] if match[1] else table_name
                alias_map[alias] = table_name
        
        return alias_map

# 导出主要类供其他模块使用
__all__ = [
    'EnhancedRelationshipManager',
    'ScenarioBasedTermMapper', 
    'StructuredPromptBuilder',
    'MultiTableSQLValidator',
    'TableRelationship',
    'FieldBinding',
    'QueryScenario'
]