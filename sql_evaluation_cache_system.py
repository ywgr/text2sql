#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SQL评价和缓存系统
功能：
1. 评价SQL质量（语法、业务逻辑、性能）
2. 好的SQL自动进入缓存和知识库
3. 坏的SQL不进入缓存，提供改进建议
4. 支持用户手动评价和反馈
"""

import json
import hashlib
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class SQLEvaluationResult:
    """SQL评价结果"""
    sql: str
    question: str
    score: float  # 0-100
    is_correct: bool
    issues: List[str]
    suggestions: List[str]
    should_cache: bool
    evaluation_time: str
    user_feedback: Optional[str] = None

class SQLEvaluationCache:
    """SQL评价和缓存系统"""
    
    def __init__(self, cache_file="sql_cache.db"):
        self.cache_file = cache_file
        self.init_database()
        
        # 评价规则权重
        self.evaluation_weights = {
            "syntax": 0.3,      # 语法正确性
            "business": 0.4,    # 业务逻辑正确性  
            "performance": 0.2, # 性能优化
            "structure": 0.1    # 表结构合理性
        }
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        # 创建SQL缓存表
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
        
        # 创建评价历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                sql TEXT,
                score REAL,
                is_correct BOOLEAN,
                issues TEXT,
                suggestions TEXT,
                evaluation_time TEXT,
                user_feedback TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def evaluate_sql(self, sql: str, question: str, user_feedback: str = None) -> SQLEvaluationResult:
        """评价SQL"""
        # 1. 语法检查
        syntax_score, syntax_issues = self._check_syntax(sql)
        
        # 2. 业务逻辑检查
        business_score, business_issues, business_suggestions = self._check_business_logic(sql, question)
        
        # 3. 性能检查
        performance_score, performance_issues = self._check_performance(sql)
        
        # 4. 表结构检查
        structure_score, structure_issues = self._check_table_structure(sql)
        
        # 计算总分
        total_score = (
            syntax_score * self.evaluation_weights["syntax"] +
            business_score * self.evaluation_weights["business"] +
            performance_score * self.evaluation_weights["performance"] +
            structure_score * self.evaluation_weights["structure"]
        ) * 100
        
        # 汇总问题和建议
        all_issues = syntax_issues + business_issues + performance_issues + structure_issues
        all_suggestions = business_suggestions
        
        # 判断是否正确
        is_correct = (total_score >= 80 and 
                     not any(issue.startswith("ERROR") for issue in all_issues))
        
        # 是否应该缓存
        should_cache = is_correct or user_feedback == "correct"
        
        result = SQLEvaluationResult(
            sql=sql,
            question=question,
            score=total_score,
            is_correct=is_correct,
            issues=all_issues,
            suggestions=all_suggestions,
            should_cache=should_cache,
            evaluation_time=datetime.now().isoformat(),
            user_feedback=user_feedback
        )
        
        # 保存评价历史
        self._save_evaluation_history(result)
        
        # 如果应该缓存，则加入缓存
        if should_cache:
            self._add_to_cache(result)
        
        return result
    
    def _check_syntax(self, sql: str) -> Tuple[float, List[str]]:
        """检查语法"""
        issues = []
        score = 1.0
        
        if not sql.strip():
            return 0.0, ["ERROR: SQL为空"]
        
        sql_upper = sql.upper()
        
        # 基本语法检查
        if not sql_upper.startswith('SELECT'):
            issues.append("ERROR: SQL必须以SELECT开头")
            score *= 0.5
        
        # 括号匹配
        if sql.count('(') != sql.count(')'):
            issues.append("ERROR: 括号不匹配")
            score *= 0.7
        
        # 引号匹配
        if sql.count("'") % 2 != 0:
            issues.append("ERROR: 单引号不匹配")
            score *= 0.7
        
        return score, issues
    
    def _check_business_logic(self, sql: str, question: str) -> Tuple[float, List[str], List[str]]:
        """检查业务逻辑"""
        issues = []
        suggestions = []
        score = 1.0
        
        # 检查510S产品规则 - 基于正确的产品层级理解
        if "510S" in question or "510s" in question:
            # 正确的模式：[roadmap family] LIKE '%510S%' and [group]='ttl'
            has_correct_roadmap = "[roadmap family] LIKE '%510S%'" in sql or "[Roadmap Family] LIKE '%510S%'" in sql
            has_correct_group = "[group]='ttl'" in sql or "[Group] = 'ttl'" in sql
            
            if not has_correct_roadmap:
                issues.append("WARNING: 510S应该使用 [Roadmap Family] LIKE '%510S%' 进行匹配")
                suggestions.append("在roadmap family层级进行模糊匹配")
                score *= 0.9
            
            if not has_correct_group:
                issues.append("WARNING: 应该使用 [Group] = 'ttl' 作为通配符")
                suggestions.append("'ttl'是正确的通配符，表示该产品系列下所有group")
                score *= 0.9
        
        # 检查时间格式
        import re
        month_match = re.search(r'(\d{1,2})月', question)
        if month_match:
            month_num = month_match.group(1)
            wrong_format = f"'2025{month_num}'"
            correct_format = f"'{month_num}月'"
            
            if wrong_format in sql:
                issues.append(f"ERROR: 时间格式错误，应该是{correct_format}而不是{wrong_format}")
                suggestions.append(f"修正时间格式为 [财月] = {correct_format}")
                score *= 0.6
        
        # 检查单表vs多表
        if "JOIN" in sql.upper() and self._can_use_single_table(question):
            issues.append("WARNING: 可以使用单表查询，避免不必要的JOIN")
            suggestions.append("考虑使用dtsupply_summary单表查询提高性能")
            score *= 0.8
        
        return score, issues, suggestions
    
    def _check_performance(self, sql: str) -> Tuple[float, List[str]]:
        """检查性能"""
        issues = []
        score = 1.0
        
        # 检查WHERE条件
        if "WHERE" not in sql.upper():
            issues.append("WARNING: 缺少WHERE条件，可能导致全表扫描")
            score *= 0.9
        
        # 检查JOIN条件
        import re
        join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
        on_count = len(re.findall(r'\bON\b', sql, re.IGNORECASE))
        
        if join_count > 0 and join_count != on_count:
            issues.append("ERROR: JOIN缺少对应的ON条件")
            score *= 0.6
        
        return score, issues
    
    def _check_table_structure(self, sql: str) -> Tuple[float, List[str]]:
        """检查表结构"""
        issues = []
        score = 1.0
        
        # 检查表名
        valid_tables = ["dtsupply_summary", "CONPD", "备货NY"]
        tables_in_sql = self._extract_tables_from_sql(sql)
        
        for table in tables_in_sql:
            if table not in valid_tables:
                issues.append(f"ERROR: 表 {table} 不存在")
                score *= 0.5
        
        return score, issues
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """提取SQL中的表名"""
        import re
        tables = []
        patterns = [
            r'FROM\s+\[?(\w+)\]?',
            r'JOIN\s+\[?(\w+)\]?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        
        return list(set(tables))
    
    def _can_use_single_table(self, question: str) -> bool:
        """判断是否可以使用单表"""
        supply_keywords = ["全链库存", "SellOut", "SellIn", "周转", "DOI"]
        product_keywords = ["510S", "510s", "geek", "小新", "拯救者"]
        
        has_supply = any(keyword in question for keyword in supply_keywords)
        has_product = any(keyword in question for keyword in product_keywords)
        
        return has_supply and has_product
    
    def _save_evaluation_history(self, result: SQLEvaluationResult):
        """保存评价历史"""
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO evaluation_history 
            (question, sql, score, is_correct, issues, suggestions, evaluation_time, user_feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.question,
            result.sql,
            result.score,
            result.is_correct,
            json.dumps(result.issues, ensure_ascii=False),
            json.dumps(result.suggestions, ensure_ascii=False),
            result.evaluation_time,
            result.user_feedback
        ))
        
        conn.commit()
        conn.close()
    
    def _add_to_cache(self, result: SQLEvaluationResult):
        """添加到缓存"""
        question_hash = hashlib.md5(result.question.encode()).hexdigest()
        
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sql_cache 
            (question_hash, question, sql, score, is_correct, issues, suggestions, created_time, user_feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            question_hash,
            result.question,
            result.sql,
            result.score,
            result.is_correct,
            json.dumps(result.issues, ensure_ascii=False),
            json.dumps(result.suggestions, ensure_ascii=False),
            result.evaluation_time,
            result.user_feedback
        ))
        
        conn.commit()
        conn.close()
    
    def get_cached_sql(self, question: str) -> Optional[Dict]:
        """获取缓存的SQL"""
        question_hash = hashlib.md5(question.encode()).hexdigest()
        
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sql, score, usage_count FROM sql_cache 
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
            return {
                "sql": result[0],
                "score": result[1],
                "usage_count": result[2] + 1
            }
        
        conn.close()
        return None
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        # 评价历史统计
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
            "correct_rate": (correct_count / total_evaluations * 100) if total_evaluations > 0 else 0,
            "cache_size": cache_size or 0,
            "total_cache_usage": total_cache_usage
        }

# 使用示例
def demo_evaluation_system():
    """演示评价系统"""
    evaluator = SQLEvaluationCache()
    
    # 测试错误的SQL
    error_sql = """SELECT [d].[全链库存] FROM [dtsupply_summary] AS [d] 
    JOIN [CONPD] AS [c] ON [d].[Roadmap Family] = [c].[Roadmap Family] 
    WHERE [c].[Group] = 'ttl' AND [d].[财月] = '20257'"""
    
    question = "510S 25年7月全链库存"
    
    print("=== SQL评价系统演示 ===")
    print(f"问题: {question}")
    print(f"SQL: {error_sql}")
    
    # 评价SQL
    result = evaluator.evaluate_sql(error_sql, question)
    
    print(f"\n评价结果:")
    print(f"评分: {result.score:.1f}")
    print(f"是否正确: {result.is_correct}")
    print(f"是否缓存: {result.should_cache}")
    
    if result.issues:
        print(f"\n发现的问题:")
        for issue in result.issues:
            print(f"  - {issue}")
    
    if result.suggestions:
        print(f"\n改进建议:")
        for suggestion in result.suggestions:
            print(f"  - {suggestion}")
    
    # 测试正确的SQL
    correct_sql = """SELECT [全链库存] FROM [dtsupply_summary] 
    WHERE [Roadmap Family] LIKE '%天逸510S%' 
    AND [Group] LIKE '%天逸510S_%' 
    AND [财年] = 2025 
    AND [财月] = '7月' 
    AND [财周] = 'ttl'"""
    
    print(f"\n=== 测试正确的SQL ===")
    print(f"SQL: {correct_sql}")
    
    result2 = evaluator.evaluate_sql(correct_sql, question, user_feedback="correct")
    print(f"评分: {result2.score:.1f}")
    print(f"是否正确: {result2.is_correct}")
    print(f"是否缓存: {result2.should_cache}")
    
    # 测试缓存
    cached = evaluator.get_cached_sql(question)
    if cached:
        print(f"\n缓存命中: {cached['sql'][:50]}...")
        print(f"使用次数: {cached['usage_count']}")
    
    # 统计信息
    stats = evaluator.get_statistics()
    print(f"\n统计信息: {stats}")

if __name__ == "__main__":
    demo_evaluation_system()