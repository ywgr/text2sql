#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL系统 V2.2 - 核心优化模块
主要优化：
1. 统一SQL生成和验证流程
2. 减少LLM调用次数
3. 智能缓存机制
4. 用户友好的错误处理
"""

import hashlib
import json
import re
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """SQL验证结果"""
    is_valid: bool
    corrected_sql: str
    issues: List[str]
    suggestions: List[str]
    performance_score: float = 0.0

@dataclass
class SQLGenerationContext:
    """SQL生成上下文"""
    question: str
    processed_question: str
    schema_info: str
    table_knowledge: Dict
    product_knowledge: Dict
    business_rules: Dict
    allowed_tables: set
    db_config: Dict

class SQLValidator:
    """统一SQL验证器"""
    
    def __init__(self, table_knowledge: Dict, business_rules: Dict):
        self.table_knowledge = table_knowledge
        self.business_rules = business_rules
        
    def validate_comprehensive(self, sql: str, context: SQLGenerationContext) -> ValidationResult:
        """一次性完成所有SQL验证"""
        issues = []
        suggestions = []
        corrected_sql = sql
        
        try:
            # 1. 基础语法检查
            syntax_issues = self._check_syntax(sql)
            issues.extend(syntax_issues)
            
            # 2. 表名白名单验证
            table_issues, corrected_sql = self._validate_tables(corrected_sql, context.allowed_tables)
            issues.extend(table_issues)
            
            # 3. 字段归属验证
            field_issues, corrected_sql = self._validate_fields(corrected_sql)
            issues.extend(field_issues)
            
            # 4. JOIN关系验证
            join_issues, corrected_sql = self._validate_joins(corrected_sql)
            issues.extend(join_issues)
            
            # 5. 业务逻辑验证
            business_issues = self._validate_business_logic(corrected_sql, context)
            issues.extend(business_issues)
            
            # 6. 性能评估
            performance_score = self._evaluate_performance(corrected_sql)
            
            is_valid = len([issue for issue in issues if issue.startswith("ERROR")]) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                corrected_sql=corrected_sql,
                issues=issues,
                suggestions=suggestions,
                performance_score=performance_score
            )
            
        except Exception as e:
            logger.error(f"SQL验证失败: {e}")
            return ValidationResult(
                is_valid=False,
                corrected_sql=sql,
                issues=[f"ERROR: 验证过程出错 - {str(e)}"],
                suggestions=["请检查SQL语法和表结构"]
            )
    
    def _check_syntax(self, sql: str) -> List[str]:
        """检查SQL基础语法"""
        issues = []
        
        # 检查基本SQL关键字
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            issues.append("ERROR: 缺少SELECT关键字")
        
        # 检查FROM子句
        if not re.search(r'\bFROM\b', sql, re.IGNORECASE):
            issues.append("ERROR: 缺少FROM子句")
        
        # 检查括号匹配
        if sql.count('(') != sql.count(')'):
            issues.append("ERROR: 括号不匹配")
        
        # 检查JOIN是否有对应的ON
        join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
        on_count = len(re.findall(r'\bON\b', sql, re.IGNORECASE))
        if join_count > on_count:
            issues.append("ERROR: JOIN缺少对应的ON条件")
        
        return issues
    
    def _validate_tables(self, sql: str, allowed_tables: set) -> Tuple[List[str], str]:
        """验证表名白名单"""
        issues = []
        corrected_sql = sql
        
        # 提取SQL中的表名
        table_patterns = [
            r'FROM\s+([^\s,()]+)',
            r'JOIN\s+([^\s,()]+)',
            r'UPDATE\s+([^\s,()]+)',
            r'INSERT\s+INTO\s+([^\s,()]+)'
        ]
        
        found_tables = set()
        for pattern in table_patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                table_name = match.split('.')[-1].strip('[]')
                found_tables.add(table_name)
        
        # 检查未授权的表
        invalid_tables = found_tables - allowed_tables
        if invalid_tables:
            issues.append(f"ERROR: 使用了未导入的表: {', '.join(invalid_tables)}")
            issues.append("SUGGESTION: 请在表结构管理中先导入这些表")
        
        return issues, corrected_sql
    
    def _validate_fields(self, sql: str) -> Tuple[List[str], str]:
        """验证字段归属"""
        issues = []
        corrected_sql = sql
        
        # 解析表别名
        alias_map = self._parse_table_aliases(sql)
        
        # 检查字段引用
        field_pattern = re.compile(r'(\w+)\.\[?(\w+)\]?')
        corrections = []
        
        for alias, field in field_pattern.findall(sql):
            if alias in alias_map:
                table = alias_map[alias]
                if table in self.table_knowledge:
                    columns = self.table_knowledge[table].get('columns', [])
                    if field not in columns:
                        # 寻找相似字段
                        from difflib import get_close_matches
                        candidates = get_close_matches(field, columns, n=1, cutoff=0.6)
                        if candidates:
                            corrections.append((f"{alias}.{field}", f"{alias}.[{candidates[0]}]"))
                            issues.append(f"WARNING: 字段 {field} 不存在，建议使用 {candidates[0]}")
                        else:
                            issues.append(f"ERROR: 表 {table} 中不存在字段 {field}")
        
        # 应用修正
        for old, new in corrections:
            corrected_sql = corrected_sql.replace(old, new)
        
        return issues, corrected_sql
    
    def _validate_joins(self, sql: str) -> Tuple[List[str], str]:
        """验证JOIN关系"""
        issues = []
        corrected_sql = sql
        
        # 提取JOIN条件
        join_pattern = re.compile(r'JOIN\s+([\w.\[\]]+)\s+(\w+)?\s*ON\s+([\w.\[\]]+)\s*=\s*([\w.\[\]]+)', re.IGNORECASE)
        matches = join_pattern.findall(sql)
        
        for match in matches:
            join_table, alias, left_field, right_field = match
            
            # 验证JOIN关系是否在知识库中
            if not self._is_valid_join_relationship(left_field, right_field):
                issues.append(f"WARNING: JOIN关系 {left_field} = {right_field} 未在知识库中定义")
                issues.append("SUGGESTION: 请在表关联管理中添加此关系")
        
        return issues, corrected_sql
    
    def _validate_business_logic(self, sql: str, context: SQLGenerationContext) -> List[str]:
        """验证业务逻辑"""
        issues = []
        
        # 检查是否正确应用了业务规则
        for business_term, db_term in context.business_rules.items():
            if business_term in context.question and db_term not in sql.lower():
                issues.append(f"INFO: 可能需要应用业务规则: {business_term} → {db_term}")
        
        return issues
    
    def _evaluate_performance(self, sql: str) -> float:
        """评估SQL性能"""
        score = 100.0
        
        # 检查是否使用了SELECT *
        if re.search(r'SELECT\s+\*', sql, re.IGNORECASE):
            score -= 10
        
        # 检查是否有WHERE条件
        if not re.search(r'\bWHERE\b', sql, re.IGNORECASE):
            score -= 5
        
        # 检查JOIN数量
        join_count = len(re.findall(r'\bJOIN\b', sql, re.IGNORECASE))
        if join_count > 3:
            score -= join_count * 2
        
        return max(0, score)
    
    def _parse_table_aliases(self, sql: str) -> Dict[str, str]:
        """解析表别名映射"""
        alias_map = {}
        
        # FROM子句别名
        from_pattern = re.compile(r'FROM\s+([\w.\[\]]+)\s+(\w+)', re.IGNORECASE)
        for match in from_pattern.finditer(sql):
            table_full, alias = match.groups()
            table_name = table_full.split('.')[-1].strip('[]')
            alias_map[alias] = table_name
        
        # JOIN子句别名
        join_pattern = re.compile(r'JOIN\s+([\w.\[\]]+)\s+(\w+)', re.IGNORECASE)
        for match in join_pattern.finditer(sql):
            table_full, alias = match.groups()
            table_name = table_full.split('.')[-1].strip('[]')
            alias_map[alias] = table_name
        
        return alias_map
    
    def _is_valid_join_relationship(self, left_field: str, right_field: str) -> bool:
        """检查JOIN关系是否有效"""
        # 简化版本，实际应该检查知识库中的关系定义
        for table_info in self.table_knowledge.values():
            relationships = table_info.get('relationships', [])
            for rel in relationships:
                if ((rel.get('field1') in left_field and rel.get('field2') in right_field) or
                    (rel.get('field1') in right_field and rel.get('field2') in left_field)):
                    return True
        return False

class EnhancedPromptBuilder:
    """增强的提示词构建器"""
    
    def __init__(self):
        self.comprehensive_template = """你是一个专业的SQL专家。请根据以下信息生成准确、安全、高效的SQL查询语句。

【数据库结构】
{schema_info}

【表结构知识库】
{table_knowledge}

【产品知识库】
{product_knowledge}

【业务规则映射】
{business_rules}

【用户问题】
{question}

【严格要求】
1. 只能使用以下已导入的表：{allowed_tables}
2. 所有字段必须真实存在且属于正确的表
3. 多表查询必须使用正确的JOIN和ON条件
4. JOIN关系必须基于知识库中定义的表关联
5. 自动为表分配简短别名（如a, b, c）
6. 所有字段和表名使用方括号包围
7. 应用业务规则进行术语转换
8. 优化查询性能，避免不必要的SELECT *

【输出要求】
- 只输出SQL语句，不要任何解释
- 确保SQL语法正确且可执行
- 如果无法生成合法SQL，输出：ERROR: [具体原因]

SQL语句："""
    
    def build_comprehensive_prompt(self, context: SQLGenerationContext) -> str:
        """构建综合提示词"""
        return self.comprehensive_template.format(
            schema_info=context.schema_info,
            table_knowledge=json.dumps(context.table_knowledge, ensure_ascii=False, indent=2),
            product_knowledge=json.dumps(context.product_knowledge, ensure_ascii=False, indent=2),
            business_rules=json.dumps(context.business_rules, ensure_ascii=False, indent=2),
            question=context.processed_question,
            allowed_tables=', '.join(context.allowed_tables)
        )

class SQLCache:
    """SQL缓存管理器"""
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.access_count = {}
    
    def get_cache_key(self, question: str, schema_hash: str, rules_hash: str) -> str:
        """生成缓存键"""
        content = f"{question}_{schema_hash}_{rules_hash}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[str]:
        """获取缓存的SQL"""
        if cache_key in self.cache:
            self.access_count[cache_key] = self.access_count.get(cache_key, 0) + 1
            return self.cache[cache_key]
        return None
    
    def set(self, cache_key: str, sql: str):
        """设置缓存"""
        if len(self.cache) >= self.max_size:
            # 删除最少使用的缓存
            least_used = min(self.access_count.items(), key=lambda x: x[1])[0]
            del self.cache[least_used]
            del self.access_count[least_used]
        
        self.cache[cache_key] = sql
        self.access_count[cache_key] = 1
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_count.clear()

class UserFriendlyErrorHandler:
    """用户友好的错误处理器"""
    
    def __init__(self):
        self.error_map = {
            "表不存在": "您提到的数据表还没有导入到系统中。请先在【表结构管理】中导入相关表。",
            "字段不存在": "字段名可能有误。系统已为您推荐了相似的字段名。",
            "JOIN关联错误": "表之间的关联关系需要先定义。请在【表结构管理】的关联管理中添加表关系。",
            "语法错误": "SQL语法有误。请检查查询条件和表达式。",
            "权限错误": "您没有权限访问某些表。请联系管理员或使用已授权的表。",
            "性能警告": "查询可能较慢。建议添加WHERE条件或优化查询逻辑。"
        }
    
    def format_issues(self, issues: List[str]) -> Dict[str, List[str]]:
        """格式化问题列表"""
        formatted = {
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "info": []
        }
        
        for issue in issues:
            if issue.startswith("ERROR"):
                formatted["errors"].append(self._make_user_friendly(issue))
            elif issue.startswith("WARNING"):
                formatted["warnings"].append(self._make_user_friendly(issue))
            elif issue.startswith("SUGGESTION"):
                formatted["suggestions"].append(self._make_user_friendly(issue))
            else:
                formatted["info"].append(self._make_user_friendly(issue))
        
        return formatted
    
    def _make_user_friendly(self, technical_message: str) -> str:
        """将技术信息转换为用户友好的消息"""
        # 移除技术前缀
        message = re.sub(r'^(ERROR|WARNING|SUGGESTION|INFO):\s*', '', technical_message)
        
        # 查找匹配的用户友好消息
        for key, friendly_msg in self.error_map.items():
            if key in message:
                return friendly_msg
        
        return message

# 性能监控装饰器
def monitor_performance(func):
    """性能监控装饰器"""
    def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        logger.info(f"{func.__name__} 执行时间: {end_time - start_time:.2f}秒")
        return result
    return wrapper