#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL集成系统 - 包含所有修正
主要功能：
1. 正确的产品层级理解：MODEL -> [ROADMAP FAMILY] -> [GROUP]
2. 单表查询优化，避免不必要的JOIN
3. 正确的时间格式解析
4. SQL评价和缓存系统
5. 用户反馈机制
"""

import streamlit as st
import pandas as pd
import json
import re
import time
import hashlib
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SQLResult:
    """SQL生成结果"""
    sql: str
    question: str
    score: float
    is_correct: bool
    issues: List[str]
    suggestions: List[str]
    from_cache: bool
    generation_time: float

class IntegratedText2SQLSystem:
    """集成的Text2SQL系统"""
    
    def __init__(self, cache_db="sql_cache.db"):
        self.cache_db = cache_db
        self.init_cache_database()
        self.load_knowledge_base()
        
        # 产品层级理解
        self.product_hierarchy = {
            "510S": {
                "roadmap_family_pattern": "%510S%",
                "group_wildcard": "ttl",
                "description": "510S产品系列，包含所有天逸510S相关产品"
            }
        }
        
        # 单表字段映射
        self.single_table_fields = {
            "dtsupply_summary": [
                "全链库存", "财年", "财月", "财周", "Roadmap Family", "Group", "Model",
                "SellOut", "SellIn", "所有欠单", "成品总量", "BTC 库存总量", "联想DC库存"
            ]
        }
    
    def init_cache_database(self):
        """初始化缓存数据库"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sql_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_hash TEXT UNIQUE,
                question TEXT,
                sql TEXT,
                score REAL,
                is_correct BOOLEAN,
                issues TEXT,
                suggestions TEXT,
                created_time TEXT,
                usage_count INTEGER DEFAULT 0,
                user_feedback TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                sql TEXT,
                score REAL,
                is_correct BOOLEAN,
                issues TEXT,
                evaluation_time TEXT,
                user_feedback TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_knowledge_base(self):
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
    
    def generate_sql(self, question: str, user_feedback: str = None) -> SQLResult:
        """生成SQL的主入口"""
        start_time = time.time()
        
        # 1. 检查缓存
        cached_result = self._get_from_cache(question)
        if cached_result and not user_feedback:
            generation_time = time.time() - start_time
            return SQLResult(
                sql=cached_result["sql"],
                question=question,
                score=cached_result["score"],
                is_correct=True,
                issues=[],
                suggestions=["使用缓存的SQL"],
                from_cache=True,
                generation_time=generation_time
            )
        
        # 2. 生成新SQL
        sql = self._generate_optimized_sql(question)
        generation_time = time.time() - start_time
        
        # 3. 评价SQL
        evaluation = self._evaluate_sql(sql, question, user_feedback)
        
        # 4. 如果评价通过，加入缓存
        if evaluation["should_cache"]:
            self._add_to_cache(question, sql, evaluation)
        
        # 5. 保存评价历史
        self._save_evaluation_history(question, sql, evaluation, user_feedback)
        
        return SQLResult(
            sql=sql,
            question=question,
            score=evaluation["score"],
            is_correct=evaluation["is_correct"],
            issues=evaluation["issues"],
            suggestions=evaluation["suggestions"],
            from_cache=False,
            generation_time=generation_time
        )
    
    def _generate_optimized_sql(self, question: str) -> str:
        """生成优化的SQL"""
        # 1. 判断是否使用单表
        if self._should_use_single_table(question):
            return self._generate_single_table_sql(question)
        else:
            # 多表逻辑（保留现有逻辑或调用其他生成器）
            return self._generate_multi_table_sql(question)
    
    def _should_use_single_table(self, question: str) -> bool:
        """判断是否应该使用单表查询"""
        # 提取问题中的目标字段
        target_fields = self._extract_target_fields(question)
        
        # 检查是否所有字段都在单表中
        supply_fields = self.single_table_fields["dtsupply_summary"]
        fields_in_single_table = all(field in supply_fields for field in target_fields)
        
        # 检查是否包含产品信息
        has_product = any(product in question for product in self.product_hierarchy.keys())
        
        return fields_in_single_table and has_product
    
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
        
        # WHERE条件
        where_conditions = []
        
        # 产品条件 - 使用正确的层级理解
        product_conditions = self._get_product_conditions(question)
        where_conditions.extend(product_conditions)
        
        # 时间条件 - 修复格式
        time_conditions = self._get_time_conditions(question)
        where_conditions.extend(time_conditions)
        
        # 组装SQL
        sql_parts = [select_clause, from_clause]
        if where_conditions:
            sql_parts.append(f"WHERE {' AND '.join(where_conditions)}")
        
        return " ".join(sql_parts)
    
    def _generate_multi_table_sql(self, question: str) -> str:
        """生成多表SQL（保留现有逻辑）"""
        # 这里可以调用现有的多表生成逻辑
        return "SELECT * FROM [dtsupply_summary] -- 多表逻辑待完善"
    
    def _extract_target_fields(self, question: str) -> List[str]:
        """从问题中提取目标字段"""
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
        
        return fields if fields else ["全链库存"]  # 默认返回全链库存
    
    def _get_product_conditions(self, question: str) -> List[str]:
        """获取产品条件 - 基于正确的产品层级"""
        conditions = []
        
        for product_key, product_config in self.product_hierarchy.items():
            if product_key in question:
                # 使用正确的产品层级理解
                roadmap_pattern = product_config["roadmap_family_pattern"]
                group_wildcard = product_config["group_wildcard"]
                
                conditions.append(f"[Roadmap Family] LIKE '{roadmap_pattern}'")
                conditions.append(f"[Group] = '{group_wildcard}'")
                break
        
        return conditions
    
    def _get_time_conditions(self, question: str) -> List[str]:
        """获取时间条件 - 修复格式问题"""
        conditions = []
        
        # 年份：25年 -> 2025
        year_match = re.search(r'(\d{2})年', question)
        if year_match:
            year_value = int("20" + year_match.group(1))
            conditions.append(f"[财年] = {year_value}")
        
        # 月份：7月 -> "7月" (不是"20257")
        month_match = re.search(r'(\d{1,2})月', question)
        if month_match:
            month_str = month_match.group(1) + "月"
            conditions.append(f"[财月] = '{month_str}'")
        
        # 特殊标识
        if "全链库存" in question:
            conditions.append("[财周] = 'ttl'")
        
        return conditions
    
    def _evaluate_sql(self, sql: str, question: str, user_feedback: str = None) -> Dict:
        """评价SQL质量"""
        issues = []
        suggestions = []
        score = 100.0
        
        # 1. 检查时间格式
        month_match = re.search(r'(\d{1,2})月', question)
        if month_match:
            month_num = month_match.group(1)
            wrong_format = f"'2025{month_num}'"
            correct_format = f"'{month_num}月'"
            
            if wrong_format in sql:
                issues.append(f"ERROR: 时间格式错误，应该是{correct_format}而不是{wrong_format}")
                score -= 30
        
        # 2. 检查单表vs多表
        if "JOIN" in sql.upper() and self._should_use_single_table(question):
            issues.append("WARNING: 可以使用单表查询，避免不必要的JOIN")
            suggestions.append("建议使用dtsupply_summary单表查询提高性能")
            score -= 20
        
        # 3. 检查产品条件（基于正确理解）
        if "510S" in question:
            has_correct_roadmap = "[Roadmap Family] LIKE '%510S%'" in sql
            has_correct_group = "[Group] = 'ttl'" in sql
            
            if not has_correct_roadmap:
                issues.append("WARNING: 510S应该使用 [Roadmap Family] LIKE '%510S%'")
                score -= 10
            
            if not has_correct_group:
                issues.append("WARNING: 应该使用 [Group] = 'ttl' 作为通配符")
                score -= 10
        
        # 4. 语法检查
        if not sql.strip():
            issues.append("ERROR: SQL为空")
            score = 0
        
        # 5. 用户反馈优先
        if user_feedback == "correct":
            score = max(score, 85)  # 用户确认正确，至少85分
        elif user_feedback == "incorrect":
            score = min(score, 70)  # 用户确认错误，最多70分
        
        is_correct = score >= 80 and not any(issue.startswith("ERROR") for issue in issues)
        should_cache = is_correct or user_feedback == "correct"
        
        return {
            "score": score,
            "is_correct": is_correct,
            "issues": issues,
            "suggestions": suggestions,
            "should_cache": should_cache
        }
    
    def _get_from_cache(self, question: str) -> Optional[Dict]:
        """从缓存获取SQL"""
        question_hash = hashlib.md5(question.encode()).hexdigest()
        
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sql, score FROM sql_cache 
            WHERE question_hash = ? AND is_correct = 1
        ''', (question_hash,))
        
        result = cursor.fetchone()
        
        if result:
            # 更新使用次数
            cursor.execute('''
                UPDATE sql_cache SET usage_count = usage_count + 1 
                WHERE question_hash = ?
            ''', (question_hash,))
            conn.commit()
            
            conn.close()
            return {"sql": result[0], "score": result[1]}
        
        conn.close()
        return None
    
    def _add_to_cache(self, question: str, sql: str, evaluation: Dict):
        """添加到缓存"""
        question_hash = hashlib.md5(question.encode()).hexdigest()
        
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sql_cache 
            (question_hash, question, sql, score, is_correct, issues, suggestions, created_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            question_hash,
            question,
            sql,
            evaluation["score"],
            evaluation["is_correct"],
            json.dumps(evaluation["issues"], ensure_ascii=False),
            json.dumps(evaluation["suggestions"], ensure_ascii=False),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def _save_evaluation_history(self, question: str, sql: str, evaluation: Dict, user_feedback: str):
        """保存评价历史"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO evaluation_history 
            (question, sql, score, is_correct, issues, evaluation_time, user_feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            question,
            sql,
            evaluation["score"],
            evaluation["is_correct"],
            json.dumps(evaluation["issues"], ensure_ascii=False),
            datetime.now().isoformat(),
            user_feedback
        ))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """获取系统统计"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        # 评价统计
        cursor.execute('SELECT COUNT(*), AVG(score) FROM evaluation_history')
        total_evaluations, avg_score = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM evaluation_history WHERE is_correct = 1')
        correct_count = cursor.fetchone()[0]
        
        # 缓存统计
        cursor.execute('SELECT COUNT(*) FROM sql_cache')
        cache_size = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(usage_count) FROM sql_cache')
        total_cache_usage = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_evaluations": total_evaluations or 0,
            "average_score": avg_score or 0,
            "accuracy_rate": (correct_count / total_evaluations * 100) if total_evaluations > 0 else 0,
            "cache_size": cache_size or 0,
            "cache_hit_rate": total_cache_usage,
            "product_hierarchy": self.product_hierarchy
        }

# Streamlit界面
def create_streamlit_interface():
    """创建Streamlit界面"""
    st.title("Text2SQL集成系统")
    st.write("支持产品层级理解、单表优化、SQL评价和缓存")
    
    # 初始化系统
    if 'text2sql_system' not in st.session_state:
        st.session_state.text2sql_system = IntegratedText2SQLSystem()
    
    system = st.session_state.text2sql_system
    
    # 主界面
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("SQL生成")
        question = st.text_input("请输入您的问题:", placeholder="例如：510S 25年7月全链库存")
        
        if st.button("生成SQL"):
            if question:
                result = system.generate_sql(question)
                
                st.code(result.sql, language="sql")
                
                # 显示评价结果
                col_score, col_cache = st.columns(2)
                with col_score:
                    color = "green" if result.is_correct else "red"
                    st.markdown(f"**评分**: <span style='color:{color}'>{result.score:.1f}</span>", unsafe_allow_html=True)
                
                with col_cache:
                    cache_text = "缓存命中" if result.from_cache else "新生成"
                    st.write(f"**来源**: {cache_text}")
                
                # 显示问题和建议
                if result.issues:
                    st.subheader("发现的问题:")
                    for issue in result.issues:
                        st.write(f"- {issue}")
                
                if result.suggestions:
                    st.subheader("改进建议:")
                    for suggestion in result.suggestions:
                        st.write(f"- {suggestion}")
                
                # 用户反馈
                st.subheader("用户反馈")
                feedback_col1, feedback_col2 = st.columns(2)
                
                with feedback_col1:
                    if st.button("✅ 正确"):
                        result_with_feedback = system.generate_sql(question, "correct")
                        st.success("已标记为正确并加入缓存")
                        st.rerun()
                
                with feedback_col2:
                    if st.button("❌ 错误"):
                        result_with_feedback = system.generate_sql(question, "incorrect")
                        st.error("已标记为错误，不会缓存")
                        st.rerun()
    
    with col2:
        st.subheader("系统统计")
        stats = system.get_statistics()
        
        st.metric("总评价次数", stats["total_evaluations"])
        st.metric("平均评分", f"{stats['average_score']:.1f}")
        st.metric("准确率", f"{stats['accuracy_rate']:.1f}%")
        st.metric("缓存大小", stats["cache_size"])
        st.metric("缓存使用次数", stats["cache_hit_rate"])
        
        # 产品层级说明
        st.subheader("产品层级理解")
        st.write("MODEL → [ROADMAP FAMILY] → [GROUP]")
        for product, config in stats["product_hierarchy"].items():
            st.write(f"**{product}**: {config['description']}")

# 测试函数
def test_integrated_system():
    """测试集成系统"""
    system = IntegratedText2SQLSystem()
    
    test_questions = [
        "510S 25年7月全链库存",
        "510S产品今年的SellOut数据",
        "天逸510S 2025年的周转情况"
    ]
    
    print("=== 集成系统测试 ===")
    
    for question in test_questions:
        print(f"\n问题: {question}")
        
        result = system.generate_sql(question)
        
        print(f"SQL: {result.sql}")
        print(f"评分: {result.score:.1f}")
        print(f"是否正确: {result.is_correct}")
        print(f"来源: {'缓存' if result.from_cache else '新生成'}")
        
        if result.issues:
            print("问题:")
            for issue in result.issues:
                print(f"  - {issue}")
        
        if result.suggestions:
            print("建议:")
            for suggestion in result.suggestions:
                print(f"  - {suggestion}")
        
        print("-" * 50)
    
    # 显示统计
    stats = system.get_statistics()
    print(f"\n=== 系统统计 ===")
    print(f"总评价次数: {stats['total_evaluations']}")
    print(f"平均评分: {stats['average_score']:.1f}")
    print(f"准确率: {stats['accuracy_rate']:.1f}%")
    print(f"缓存大小: {stats['cache_size']}")

if __name__ == "__main__":
    # 命令行测试
    test_integrated_system()
    
    # 或者运行Streamlit界面
    # streamlit run text2sql_integrated_system.py