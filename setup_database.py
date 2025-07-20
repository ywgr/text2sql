#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库初始化脚本 - 创建TEST数据库和测试数据
"""

import mysql.connector
from mysql.connector import Error
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseSetup:
    def __init__(self, host='localhost', user='root', password='password'):
        """初始化数据库连接参数"""
        self.host = host
        self.user = user
        self.password = password
        self.connection = None

    def connect_mysql(self):
        """连接到MySQL服务器（不指定数据库）"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                logger.info("MySQL服务器连接成功")
                return True
        except Error as e:
            logger.error(f"MySQL连接失败: {e}")
            return False

    def create_database(self):
        """创建TEST数据库"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 创建数据库
            cursor.execute("CREATE DATABASE IF NOT EXISTS TEST CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info("数据库TEST创建成功")
            
            # 使用数据库
            cursor.execute("USE TEST")
            
            cursor.close()
            return True
            
        except Error as e:
            logger.error(f"创建数据库失败: {e}")
            return False

    def create_tables(self):
        """创建数据表"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 创建学生表
            student_table = """
            CREATE TABLE IF NOT EXISTS student (
                student_id INT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                gender VARCHAR(10) NOT NULL,
                class VARCHAR(20) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            cursor.execute(student_table)
            logger.info("学生表创建成功")
            
            # 创建课程表
            course_table = """
            CREATE TABLE IF NOT EXISTS course (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                course_name VARCHAR(50) NOT NULL,
                FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            cursor.execute(course_table)
            logger.info("课程表创建成功")
            
            # 创建成绩表
            score_table = """
            CREATE TABLE IF NOT EXISTS score (
                id INT AUTO_INCREMENT PRIMARY KEY,
                course_name VARCHAR(50) NOT NULL,
                score DECIMAL(5,2) NOT NULL,
                name VARCHAR(50) NOT NULL,
                INDEX idx_name (name),
                INDEX idx_course (course_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            cursor.execute(score_table)
            logger.info("成绩表创建成功")
            
            cursor.close()
            return True
            
        except Error as e:
            logger.error(f"创建表失败: {e}")
            return False

    def insert_test_data(self):
        """插入测试数据"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 清空现有数据
            cursor.execute("DELETE FROM score")
            cursor.execute("DELETE FROM course")
            cursor.execute("DELETE FROM student")
            
            # 插入学生数据
            student_data = [
                (1001, '张三', '男', '高一(1)班'),
                (1002, '李四', '男', '高一(1)班'),
                (1003, '王五', '男', '高一(2)班'),
                (1004, '赵六', '女', '高一(2)班'),
                (1005, '钱七', '女', '高一(3)班'),
                (1006, '孙八', '男', '高一(3)班'),
                (1007, '周九', '女', '高一(1)班'),
                (1008, '吴十', '男', '高一(2)班')
            ]
            
            cursor.executemany(
                "INSERT INTO student (student_id, name, gender, class) VALUES (%s, %s, %s, %s)",
                student_data
            )
            logger.info(f"插入{len(student_data)}条学生数据")
            
            # 插入课程数据
            course_data = [
                (1001, '语文'), (1001, '数学'), (1001, '英语'),
                (1002, '语文'), (1002, '物理'), (1002, '化学'),
                (1003, '数学'), (1003, '物理'), (1003, '生物'),
                (1004, '语文'), (1004, '英语'), (1004, '历史'),
                (1005, '数学'), (1005, '地理'), (1005, '政治'),
                (1006, '语文'), (1006, '数学'), (1006, '英语'), (1006, '物理'),
                (1007, '语文'), (1007, '数学'), (1007, '化学'),
                (1008, '数学'), (1008, '物理'), (1008, '生物')
            ]
            
            cursor.executemany(
                "INSERT INTO course (student_id, course_name) VALUES (%s, %s)",
                course_data
            )
            logger.info(f"插入{len(course_data)}条课程数据")
            
            # 插入成绩数据
            score_data = [
                ('语文', 85.5, '张三'), ('数学', 92.0, '张三'), ('英语', 78.5, '张三'),
                ('语文', 76.0, '李四'), ('物理', 88.5, '李四'), ('化学', 90.0, '李四'),
                ('数学', 95.5, '王五'), ('物理', 82.0, '王五'), ('生物', 79.5, '王五'),
                ('语文', 88.0, '赵六'), ('英语', 92.5, '赵六'), ('历史', 85.0, '赵六'),
                ('数学', 90.0, '钱七'), ('地理', 87.5, '钱七'), ('政治', 93.0, '钱七'),
                ('语文', 82.0, '孙八'), ('数学', 88.0, '孙八'), ('英语', 85.0, '孙八'), ('物理', 91.0, '孙八'),
                ('语文', 89.0, '周九'), ('数学', 94.0, '周九'), ('化学', 87.0, '周九'),
                ('数学', 86.0, '吴十'), ('物理', 89.0, '吴十'), ('生物', 83.0, '吴十')
            ]
            
            cursor.executemany(
                "INSERT INTO score (course_name, score, name) VALUES (%s, %s, %s)",
                score_data
            )
            logger.info(f"插入{len(score_data)}条成绩数据")
            
            # 提交事务
            self.connection.commit()
            cursor.close()
            return True
            
        except Error as e:
            logger.error(f"插入数据失败: {e}")
            self.connection.rollback()
            return False

    def verify_data(self):
        """验证数据插入是否成功"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 检查各表数据量
            tables = ['student', 'course', 'score']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"表 {table} 有 {count} 条记录")
            
            # 显示一些示例数据
            cursor.execute("""
                SELECT s.name, s.class, sc.course_name, sc.score 
                FROM student s 
                JOIN score sc ON s.name = sc.name 
                LIMIT 5
            """)
            
            results = cursor.fetchall()
            logger.info("示例数据:")
            for row in results:
                logger.info(f"  {row[0]} ({row[1]}) - {row[2]}: {row[3]}分")
            
            cursor.close()
            return True
            
        except Error as e:
            logger.error(f"验证数据失败: {e}")
            return False

    def close_connection(self):
        """关闭数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("数据库连接已关闭")

def main():
    """主函数"""
    print("=== TEXT2SQL数据库初始化脚本 ===")
    print("请确保MySQL服务已启动")
    
    # 获取数据库连接信息
    host = input("MySQL主机地址 (默认: localhost): ").strip() or "localhost"
    user = input("MySQL用户名 (默认: root): ").strip() or "root"
    password = input("MySQL密码: ").strip()
    
    if not password:
        print("警告: 密码为空，请确保MySQL允许空密码连接")
    
    # 初始化数据库
    db_setup = DatabaseSetup(host=host, user=user, password=password)
    
    try:
        # 连接MySQL
        if not db_setup.connect_mysql():
            print("❌ MySQL连接失败，请检查连接参数")
            return
        
        print("✅ MySQL连接成功")
        
        # 创建数据库
        if not db_setup.create_database():
            print("❌ 数据库创建失败")
            return
        
        print("✅ 数据库TEST创建成功")
        
        # 创建表
        if not db_setup.create_tables():
            print("❌ 数据表创建失败")
            return
        
        print("✅ 数据表创建成功")
        
        # 插入测试数据
        if not db_setup.insert_test_data():
            print("❌ 测试数据插入失败")
            return
        
        print("✅ 测试数据插入成功")
        
        # 验证数据
        if not db_setup.verify_data():
            print("❌ 数据验证失败")
            return
        
        print("✅ 数据验证成功")
        print("\n🎉 数据库初始化完成！")
        print("现在可以运行 text2sql_system.py 来启动TEXT2SQL系统")
        
    except Exception as e:
        print(f"❌ 初始化过程中出现错误: {e}")
    
    finally:
        db_setup.close_connection()

if __name__ == "__main__":
    main()