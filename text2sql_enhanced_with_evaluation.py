#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL增强版本 - 包含SQL评价和缓存系统
解决问题：
1. 单表查询优化 - 避免不必要的多表JOIN
2. 时间格式修复 - 正确解析时间条件
3. 业务规则应用 - 使用正确的产品规则
4. SQL评价系统 - 好的SQL进入知识库和缓存
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
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SQLEvaluation:
    """SQL评价结果"""
    sql: str
    question: str
    is_correct: bool
    score: float  # 0-100分
    issues: List[str]
    suggestions: List[str]
    execution_time: float
    result_count: int
    timestamp: str

class SQLEvaluationSystem:
    """SQL评价系统"""
    
    def __init__(self):
        self.evaluation_history = []
        self.good_sql_cache = {}  # 缓存好的SQL
        self.knowledge_base = {}  # 知识库
        
    def evaluate_sql(self, sql: str, question: str, execution_result=None, 
                    execution_time: float = 0) -> SQLEvaluation:
        """评价SQL质量"""
        issues = []
        suggestions = []
        score = 100.0
        
        # 1. 语法检查
        syntax_score, syntax_issues = self._check_syntax(sql)
        score *= syntax_score
        issues.extend(syntax_issues)
        
        # 2. 表结构检查
        structure_score, structure_issues = self._check_table_structure(sql)
        score *= structure_score
        issues.extend(structure_issues)
        
        # 3. 业务逻辑检查
        logic_score, logic_issues, logic_suggestions = self._check_business_logic(sql, question)
        score *= logic_score
        issues.extend(logic_issues)
        suggestions.extend(logic_suggestions)
        
        # 4. 性能检查
        performance_score, performance_issues = self._check_performance(sql)
        score *= performance_score
        issues.extend(performance_issues)
        
        # 5. 结果合理性检查
        if execution_result is not None:
            result_score, result_issues = self._check_result_reasonableness(
                execution_result, question)
            score *= result_score
            issues.extend(result_issues)
        
        is_correct = score >= 80.0 and len([i for i in issues if i.startswith("ERROR")]) == 0
        result_count = len(execution_result) if execution_result is not None else 0
        
        evaluation = SQLEvaluation(
            sql=sql,
            question=question,
            is_correct=is_correct,
            score=score,
            issues=issues,
            suggestions=suggestions,
            execution_time=execution_time,
            result_count=result_count,
            timestamp=datetime.now().isoformat()
        )
        
        # 记录评价历史
        self.evaluation_history.append(evaluation)
        
        # 如果是好的SQL，加入缓存和知识库
        if is_correct:
            self._add_to_cache(question, sql, score)
            self._add_to_knowledge_base(question, sql, evaluation)
        
        return evaluation
    
    def _check_syntax(self, sql: str) -> Tuple[float, List[str]]:
        """检查SQL语法"""
        issues = []
        score = 1.0
        
        # 基本语法检查
        if not sql.strip():
            issues.append("ERROR: SQL为空")
            return 0.0, issues
        
        # 检查关键字
        sql_upper = sql.upper()
        if not sql_upper.startswith('SELECT'):
            issues.append("ERROR: SQL必须以SELECT开头")
            score *= 0.5
        
        # 检查括号匹配
        if sql.count('(') != sql.count(')'):
            issues.append("ERROR: 括号不匹配")
            score *= 0.7
        
        # 检查引号匹配
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            issues.append("ERROR: 单引号不匹配")
            score *= 0.7
        
        return score, issues
    
    def _check_table_structure(self, sql: str) -> Tuple[float, List[str]]:
        """检查表结构合理性"""
        issues = []
        score = 1.0
        
        # 检查是否使用了不存在的表
        tables_in_sql = self._extract_tables_from_sql(sql)
        valid_tables = ["dtsupply_summary", "CONPD", "备货NY"]  # 从table_knowledge.json获取
        
        for table in tables_in_sql:
            if table not in valid_tables:
                issues.append(f"ERROR: 表 {table} 不存在")
                score *= 0.5
        
        # 检查字段名格式
        if re.search(r'\w+\.\w+', sql):
            # 有表别名，检查格式
            pass
        else:
            # 多表查询但没有表别名
            if len(tables_in_sql) > 1:
                issues.append("WARNING: 多表查询建议使用表别名")
                score *= 0.9
        
        return score, issues
    
    def _check_business_logic(self, sql: str, question: str) -> Tuple[float, List[str], List[str]]:
        """检查业务逻辑"""
        issues = []
        suggestions = []
        score = 1.0
        
        # 检查产品条件
        if "510S" in question or "510s" in question:
            if "天逸510S" not in sql:
                issues.append("ERROR: 510S产品应该使用'天逸510S'进行匹配")
                score *= 0.6
            if "[group] = 'ttl'" in sql:
                issues.append("ERROR: 不应该使用占位符'ttl'，应该使用实际的group模式匹配")
                score *= 0.5
        
        # 检查时间条件
        if re.search(r'\d+年', question):
            year_match = re.search(r'(\d{2})年', question)
            if year_match:
                expected_year = "20" + year_match.group(1)
                if expected_year not in sql:
                    issues.append(f"WARNING: 可能缺少年份条件 {expected_year}")
                    score *= 0.9
        
        if re.search(r'\d+月', question):
            month_match = re.search(r'(\d{1,2})月', question)
            if month_match:
                expected_month = month_match.group(1) + "月"
                if expected_month not in sql:
                    issues.append(f"WARNING: 可能缺少月份条件 '{expected_month}'")
                    score *= 0.9
                # 检查错误的时间格式
                wrong_format = "'" + "2025" + month_match.group(1) + "'"
                if wrong_format in sql:
                    issues.append(f"ERROR: 时间格式错误，应该是'{expected_month}'而不是{wrong_format}")
                    score *= 0.5
        
        # 检查单表vs多表
        tables_in_sql = self._extract_tables_from_sql(sql)
        if len(tables_in_sql) > 1:
            # 检查是否真的需要多表
            if self._can_use_single_table(question):
                issues.append("WARNING: 此查询可能可以使用单表完成，避免不必要的JOIN")
                suggestions.append("考虑使用单表查询提高性能")
                score *= 0.8
        
        return score, issues, suggestions
    
    def _check_performance(self, sql: str) -> Tuple[float, List[str]]:
        """检查性能"""
        issues = []
        score = 1.0
        
        # 检查是否有WHERE条件
        if "WHERE" not in sql.upper():
            issues.append("WARNING: 缺少WHERE条件，可能导致全表扫描")
            score *= 0.9
        
        # 检查JOIN条件
        join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
        on_count = len(re.findall(r'\bON\b', sql, re.IGNORECASE))
        
        if join_count > 0 and join_count != on_count:
            issues.append("ERROR: JOIN缺少对应的ON条件")
            score *= 0.6
        
        return score, issues
    
    def _check_result_reasonableness(self, result, question: str) -> Tuple[float, List[str]]:
        """检查结果合理性"""
        issues = []
        score = 1.0
        
        if result is None:
            issues.append("ERROR: 查询执行失败")
            return 0.0, issues
        
        if isinstance(result, pd.DataFrame):
            if len(result) == 0:
                issues.append("WARNING: 查询结果为空")
                score *= 0.8
            elif len(result) > 10000:
                issues.append("WARNING: 查询结果过多，可能需要添加限制条件")
                score *= 0.9
        
        return score, issues
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """从SQL中提取表名"""
        tables = []
        patterns = [
            r'FROM\s+\[?(\w+)\]?(?:\s+(?:AS\s+)?(\w+))?',
            r'JOIN\s+\[?(\w+)\]?(?:\s+(?:AS\s+)?(\w+))?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                table_name = match[0]
                tables.append(table_name)
        
        return list(set(tables))
    
    def _can_use_single_table(self, question: str) -> bool:
        """判断是否可以使用单表"""
        # 如果问题只涉及供应链数据且包含产品信息，通常可以用dtsupply_summary单表
        supply_keywords = ["全链库存", "SellOut", "SellIn", "周转", "DOI"]
        product_keywords = ["510S", "510s", "geek", "小新", "拯救者"]
        
        has_supply = any(keyword in question for keyword in supply_keywords)
        has_product = any(keyword in question for keyword in product_keywords)
        
        return has_supply and has_product
    
    def _add_to_cache(self, question: str, sql: str, score: float):
        """添加到缓存"""
        cache_key = hashlib.md5(question.encode()).hexdigest()
        self.good_sql_cache[cache_key] = {
            "question": question,
            "sql": sql,
            "score": score,
            "timestamp": datetime.now().isoformat(),
            "usage_count": 0
        }
    
    def _add_to_knowledge_base(self, question: str, sql: str, evaluation: SQLEvaluation):
        """添加到知识库"""
        kb_key = f"pattern_{len(self.knowledge_base)}"
        self.knowledge_base[kb_key] = {
            "question_pattern": self._extract_question_pattern(question),
            "sql_template": self._extract_sql_template(sql),
            "evaluation": evaluation,
            "examples": [{"question": question, "sql": sql}]
        }
    
    def _extract_question_pattern(self, question: str) -> str:
        """提取问题模式"""
        # 简化的模式提取
        pattern = question
        # 替换具体数值为占位符
        pattern = re.sub(r'\d+年', 'X年', pattern)
        pattern = re.sub(r'\d+月', 'X月', pattern)
        return pattern
    
    def _extract_sql_template(self, sql: str) -> str:
        """提取SQL模板"""
        # 简化的模板提取
        template = sql
        # 替换具体值为占位符
        template = re.sub(r"'\d+月'", "'X月'", template)
        template = re.sub(r"= \d{4}", "= YYYY", template)
        return template
    
    def get_cached_sql(self, question: str) -> Optional[str]:
        """获取缓存的SQL"""
        cache_key = hashlib.md5(question.encode()).hexdigest()
        if cache_key in self.good_sql_cache:
            cached = self.good_sql_cache[cache_key]
            cached["usage_count"] += 1
            return cached["sql"]
        return None
    
    def get_evaluation_stats(self) -> Dict:
        """获取评价统计"""
        if not self.evaluation_history:
            return {}
        
        total = len(self.evaluation_history)
        correct = len([e for e in self.evaluation_history if e.is_correct])
        avg_score = sum(e.score for e in self.evaluation_history) / total
        
        return {
            "total_evaluations": total,
            "correct_count": correct,
            "accuracy_rate": correct / total * 100,
            "average_score": avg_score,
            "cache_size": len(self.good_sql_cache),
            "knowledge_base_size": len(self.knowledge_base)
        }

class EnhancedSQLGenerator:
    """增强的SQL生成器"""
    
    def __init__(self):
        self.evaluation_system = SQLEvaluationSystem()
        self.load_knowledge()
    
    def load_knowledge(self):
        """加载知识库"""
        try:
            with open('business_rules.json', 'r', encoding='utf-8') as f:
                self.business_rules = json.load(f)
            with open('table_knowledge.json', 'r', encoding='utf-8') as f:
                self.table_knowledge = json.load(f)
            with open('product_knowledge.json', 'r', encoding='utf-8') as f:
                self.product_knowledge = json.load(f)
        except Exception as e:
            logger.error(f"加载知识库失败: {e}")
            self.business_rules = {}
            self.table_knowledge = {}
            self.product_knowledge = {}
    
    def generate_sql(self, question: str) -> Tuple[str, SQLEvaluation]:
        """生成SQL并评价"""
        # 1. 检查缓存
        cached_sql = self.evaluation_system.get_cached_sql(question)
        if cached_sql:
            evaluation = SQLEvaluation(
                sql=cached_sql,
                question=question,
                is_correct=True,
                score=100.0,
                issues=[],
                suggestions=["使用缓存的SQL"],
                execution_time=0,
                result_count=0,
                timestamp=datetime.now().isoformat()
            )
            return cached_sql, evaluation
        
        # 2. 生成新SQL
        start_time = time.time()
        sql = self._generate_optimized_sql(question)
        generation_time = time.time() - start_time
        
        # 3. 评价SQL
        evaluation = self.evaluation_system.evaluate_sql(
            sql, question, execution_time=generation_time)
        
        return sql, evaluation
    
    def _generate_optimized_sql(self, question: str) -> str:
        """生成优化的SQL"""
        # 1. 判断是否可以使用单表
        if self._should_use_single_table(question):
            return self._generate_single_table_sql(question)
        else:
            return self._generate_multi_table_sql(question)
    
    def _should_use_single_table(self, question: str) -> bool:
        """判断是否应该使用单表"""
        # 检查是否所有需要的字段都在dtsupply_summary表中
        supply_fields = ["全链库存", "SellOut", "SellIn", "周转", "DOI", "财年", "财月", "财周", 
                        "Roadmap Family", "Group", "Model"]
        
        # 提取问题中的目标字段
        target_fields = []
        for field in supply_fields:
            if field in question:
                target_fields.append(field)
        
        # 如果有目标字段且包含产品信息，使用单表
        product_keywords = ["510S", "510s", "geek", "小新", "拯救者"]
        has_product = any(keyword in question for keyword in product_keywords)
        
        return len(target_fields) > 0 and has_product
    
    def _generate_single_table_sql(self, question: str) -> str:
        """生成单表SQL"""
        # SELECT子句
        target_fields = self._extract_target_fields(question)
        if not target_fields:
            select_clause = "SELECT *"
        else:
            field_list = ", ".join(f"[{field}]" for field in target_fields)
            select_clause = f"SELECT {field_list}"
        
        # FROM子句
        from_clause = "FROM [dtsupply_summary]"
        
        # WHERE子句
        where_conditions = []
        
        # 产品条件 - 使用更新后的业务规则
        product_conditions = self._get_product_conditions(question)
        where_conditions.extend(product_conditions)
        
        # 时间条件 - 修复时间格式
        time_conditions = self._get_time_conditions(question)
        where_conditions.extend(time_conditions)
        
        # 组装SQL
        sql_parts = [select_clause, from_clause]
        if where_conditions:
            sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
        
        return " ".join(sql_parts)
    
    def _generate_multi_table_sql(self, question: str) -> str:
        """生成多表SQL（保留原有逻辑）"""
        # 这里可以保留原有的多表生成逻辑
        return "SELECT * FROM [dtsupply_summary] -- 多表逻辑待实现"
    
    def _extract_target_fields(self, question: str) -> List[str]:
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
        
        return fields
    
    def _get_product_conditions(self, question: str) -> List[str]:
        """获取产品条件 - 基于正确的产品层级理解"""
        conditions = []
        
        # 使用业务规则中的510S规则
        if "510S" in question or "510s" in question:
            if "510S" in self.business_rules:
                rule = self.business_rules["510S"]
                # 解析规则: "where [roadmap family] LIKE '%510S%' and [group]='ttl'"
                if "where " in rule.lower():
                    # 正确的产品层级理解：在roadmap family层级匹配，group使用ttl通配符
                    conditions.append("[Roadmap Family] LIKE '%510S%'")
                    conditions.append("[Group] = 'ttl'")
        
        return conditions
    
    def _get_time_conditions(self, question: str) -> List[str]:
        """获取时间条件 - 修复时间格式"""
        conditions = []
        
        # 解析年份 - 25年 -> 2025
        year_match = re.search(r'(\d{2})年', question)
        if year_match:
            year_str = year_match.group(1)
            year_value = int("20" + year_str)
            conditions.append(f"[财年] = {year_value}")
        
        # 解析月份 - 7月 -> "7月" (不是"20257")
        month_match = re.search(r'(\d{1,2})月', question)
        if month_match:
            month_str = month_match.group(1)
            conditions.append(f"[财月] = '{month_str}月'")
        
        # 特殊标识
        if "全链库存" in question:
            conditions.append("[财周] = 'ttl'")
        
        return conditions

# 主要接口函数
def generate_and_evaluate_sql(question: str) -> Tuple[str, SQLEvaluation, Dict]:
    """生成SQL并评价"""
    generator = EnhancedSQLGenerator()
    sql, evaluation = generator.generate_sql(question)
    stats = generator.evaluation_system.get_evaluation_stats()
    
    return sql, evaluation, stats

# 测试函数
def test_sql_generation():
    """测试SQL生成"""
    test_questions = [
        "510S 25年7月全链库存",
        "天逸510S 2025年7月的SellOut数据",
        "510s产品今年的周转情况"
    ]
    
    generator = EnhancedSQLGenerator()
    
    for question in test_questions:
        print(f"\n问题: {question}")
        sql, evaluation = generator.generate_sql(question)
        print(f"SQL: {sql}")
        print(f"评分: {evaluation.score:.1f}")
        print(f"是否正确: {evaluation.is_correct}")
        if evaluation.issues:
            print(f"问题: {evaluation.issues}")
        if evaluation.suggestions:
            print(f"建议: {evaluation.suggestions}")

if __name__ == "__main__":
    test_sql_generation()