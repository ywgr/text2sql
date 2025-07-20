-- 创建TEST数据库
CREATE DATABASE IF NOT EXISTS TEST;

-- 使用TEST数据库
USE TEST;

-- 创建学生名册表
CREATE TABLE IF NOT EXISTS student (
    student_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    class VARCHAR(20) NOT NULL
);

-- 创建课程表
CREATE TABLE IF NOT EXISTS course (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_name VARCHAR(50) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);

-- 创建成绩表
CREATE TABLE IF NOT EXISTS score (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_name VARCHAR(50) NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    name VARCHAR(50) NOT NULL
);

-- 向学生名册表插入数据
INSERT INTO student (student_id, name, gender, class) VALUES
(1001, '张三', '男', '高一(1)班'),
(1002, '李四', '男', '高一(1)班'),
(1003, '王五', '男', '高一(2)班'),
(1004, '赵六', '女', '高一(2)班'),
(1005, '钱七', '女', '高一(3)班');

-- 向课程表插入数据
INSERT INTO course (student_id, course_name) VALUES
(1001, '语文'),
(1001, '数学'),
(1001, '英语'),
(1002, '语文'),
(1002, '物理'),
(1002, '化学'),
(1003, '数学'),
(1003, '物理'),
(1003, '生物'),
(1004, '语文'),
(1004, '英语'),
(1004, '历史'),
(1005, '数学'),
(1005, '地理'),
(1005, '政治');

-- 向成绩表插入数据
INSERT INTO score (course_name, score, name) VALUES
('语文', 85.5, '张三'),
('数学', 92.0, '张三'),
('英语', 78.5, '张三'),
('语文', 76.0, '李四'),
('物理', 88.5, '李四'),
('化学', 90.0, '李四'),
('数学', 95.5, '王五'),
('物理', 82.0, '王五'),
('生物', 79.5, '王五'),
('语文', 88.0, '赵六'),
('英语', 92.5, '赵六'),
('历史', 85.0, '赵六'),
('数学', 90.0, '钱七'),
('地理', 87.5, '钱七'),
('政治', 93.0, '钱七');
