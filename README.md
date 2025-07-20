# TEXT2SQL分析系统

基于AI的自然语言转SQL查询分析平台，使用Vanna AI、DeepSeek和Streamlit构建。

## 功能特性

- 🔍 **自然语言查询**: 支持中文自然语言转SQL查询
- 🤖 **AI驱动**: 集成Vanna AI和DeepSeek大模型
- 📊 **数据可视化**: 自动生成图表和数据分析
- ✅ **SQL验证**: 自动验证SQL语法和字段正确性
- 🔄 **多表查询**: 支持复杂的多表关联查询
- 📈 **智能分析**: 提供数据洞察和统计分析

## 系统架构

```
前端界面：Streamlit Web应用
AI引擎：Vanna AI + DeepSeek API
数据库：MySQL (学生/课程/成绩管理系统)
可视化：Plotly图表库
```

## 快速开始

### 1. 环境准备

确保已安装Python 3.8+和MySQL服务器。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 数据库初始化

运行数据库设置脚本：

```bash
python setup_database.py
```

按提示输入MySQL连接信息，脚本将自动创建TEST数据库和测试数据。

### 4. 启动系统

```bash
python run_system.py
```

或直接使用Streamlit：

```bash
streamlit run text2sql_system.py
```

### 5. 配置API密钥

在系统中配置以下API密钥：
- Vanna API Key: `35d688e1655847838c9d0e318168d4f0`
- DeepSeek API Key: `sk-0e6005b793aa4759bb022b91e9055f86`

## 数据库结构

系统使用以下三张表：

### student (学生表)
- student_id: 学生ID (主键)
- name: 姓名
- gender: 性别
- class: 班级

### course (课程表)
- id: 课程记录ID (主键)
- student_id: 学生ID (外键)
- course_name: 课程名称

### score (成绩表)
- id: 成绩记录ID (主键)
- course_name: 课程名称
- score: 分数
- name: 学生姓名

## 使用示例

### 示例查询

1. **基础查询**
   - "查询所有学生的姓名和班级"
   - "显示张三的所有课程成绩"

2. **统计分析**
   - "统计每个班级的学生人数"
   - "显示数学成绩大于90分的学生"

3. **排序查询**
   - "显示平均成绩最高的前3名学生"
   - "按成绩降序显示所有语文成绩"

### 业务术语映射

系统支持中文术语自动映射：
- 学生 → student
- 课程 → course
- 成绩 → score
- 姓名 → name
- 班级 → class

## 系统特性

### SQL验证
- 语法检查
- 字段存在性验证
- 表关系验证
- 多表查询支持

### 数据可视化
- 自动图表生成
- 柱状图、散点图、饼图
- 交互式图表展示

### 智能分析
- 统计摘要
- 数据洞察
- 趋势分析

## 配置说明

### 数据库配置

在 `text2sql_system.py` 中修改数据库连接参数：

```python
self.db_config = {
    'host': 'localhost',
    'database': 'TEST',
    'user': 'root',
    'password': 'your_password'  # 修改为实际密码
}
```

### API配置

```python
self.vanna_api_key = "35d688e1655847838c9d0e318168d4f0"
self.deepseek_api_key = "sk-0e6005b793aa4759bb022b91e9055f86"
```

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MySQL服务是否启动
   - 验证用户名和密码
   - 确认数据库TEST是否存在

2. **Vanna API错误**
   - 检查API密钥是否正确
   - 确认网络连接正常

3. **依赖包问题**
   - 运行 `pip install -r requirements.txt`
   - 检查Python版本兼容性

### 日志查看

系统使用Python logging模块记录详细日志，可以查看控制台输出获取调试信息。

## 开发说明

### 项目结构

```
├── text2sql_system.py      # 主系统文件
├── setup_database.py       # 数据库初始化脚本
├── run_system.py          # 系统启动器
├── requirements.txt       # 依赖包列表
├── README.md             # 说明文档
├── TEST.sql              # 原始SQL脚本
├── vanna1.py             # Vanna测试脚本
└── import vanna as vn.py # API密钥获取脚本
```

### 扩展开发

1. **添加新的业务规则**: 修改 `business_rules` 字典
2. **支持新的数据库**: 修改数据库连接和SQL方言
3. **增加图表类型**: 扩展 `generate_chart` 方法
4. **优化SQL验证**: 改进 `validate_sql` 逻辑

## 许可证

本项目仅供学习和研究使用。

## 联系方式

如有问题或建议，请联系开发团队。