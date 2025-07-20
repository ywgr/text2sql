# TEXT2SQL本地部署系统

基于ChromaDB向量数据库和DeepSeek LLM的完全本地部署TEXT2SQL系统。

## 🏠 系统特点

- **完全本地部署**: 向量数据库和知识库都在本地存储
- **数据安全**: 除了LLM API调用外，所有数据处理都在本地
- **快速响应**: 本地向量检索，无网络延迟
- **可定制**: 完全控制知识库内容和训练数据

## 🔧 技术架构

```
用户自然语言问题
        ↓
ChromaDB本地向量检索 (相似问题/文档)
        ↓
构建包含上下文的提示词
        ↓
DeepSeek API生成SQL
        ↓
SQLite本地执行查询
        ↓
结果展示和可视化
```

### 核心组件

- **向量数据库**: ChromaDB (本地持久化存储)
- **LLM**: DeepSeek API
- **关系数据库**: SQLite (本地文件)
- **Web界面**: Streamlit
- **可视化**: Plotly

## 📦 安装和设置

### 1. 环境要求

- Python 3.8+
- 8GB+ 内存 (推荐)
- 2GB+ 磁盘空间

### 2. 快速安装

```bash
# 1. 克隆或下载项目文件
# 2. 安装依赖并设置环境
python setup_local_environment.py

# 3. 启动系统
python run_local_system.py
```

### 3. 手动安装

```bash
# 安装依赖
pip install -r requirements.txt

# 创建目录
mkdir chroma_db

# 启动系统
streamlit run text2sql_local_deepseek.py
```

## ⚙️ 配置说明

### 主要配置文件: `config_local.py`

```python
class LocalConfig:
    # DeepSeek API配置
    DEEPSEEK_API_KEY = "your_api_key_here"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    # ChromaDB配置
    CHROMA_DB_PATH = "./chroma_db"
    CHROMA_COLLECTION_NAME = "text2sql_knowledge"
    
    # SQLite数据库配置
    SQLITE_DB_FILE = "test_database.db"
```

### 环境变量配置

创建 `.env` 文件:

```bash
DEEPSEEK_API_KEY=sk-your-api-key-here
CHROMA_DB_PATH=./chroma_db
SQLITE_DB_FILE=test_database.db
```

## 🚀 使用方法

### 1. 启动系统

```bash
# 方法1: 使用启动脚本
python run_local_system.py

# 方法2: 直接启动Streamlit
streamlit run text2sql_local_deepseek.py
```

### 2. 访问界面

打开浏览器访问: http://localhost:8501

### 3. 使用示例

**支持的查询类型:**

- 基础查询: "查询所有学生"
- 条件查询: "数学成绩大于90分的学生"
- 排序查询: "化学成绩前3的学生"
- 统计查询: "每个班级的学生人数"
- 聚合查询: "平均成绩最高的学生"

## 📊 数据库结构

系统使用SQLite数据库，包含以下表:

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

## 🔍 工作原理

### 1. 知识库训练

系统启动时会自动训练本地知识库:

- **DDL语句**: 数据库表结构定义
- **业务文档**: 术语映射和业务规则
- **查询示例**: 问题-SQL对应关系

### 2. 查询处理流程

1. **用户输入**: 自然语言问题
2. **向量检索**: ChromaDB查找相似问题和相关文档
3. **上下文构建**: 组合检索结果构建提示词
4. **SQL生成**: DeepSeek API生成SQL查询
5. **查询执行**: SQLite执行SQL并返回结果
6. **结果展示**: 数据表格、图表和分析

### 3. 本地存储结构

```
项目目录/
├── text2sql_local_deepseek.py    # 主程序
├── config_local.py               # 配置文件
├── run_local_system.py          # 启动脚本
├── setup_local_environment.py   # 环境设置
├── test_database.db             # SQLite数据库
├── chroma_db/                   # ChromaDB本地存储
│   ├── chroma.sqlite3          # 向量索引
│   └── ...                     # 其他ChromaDB文件
└── requirements.txt            # 依赖包列表
```

## 🛠️ 自定义和扩展

### 1. 添加新的训练数据

```python
# 在 train_local_knowledge() 方法中添加
training_examples = [
    {"question": "你的问题", "sql": "对应的SQL"},
    # ... 更多示例
]
```

### 2. 修改数据库结构

1. 更新 `initialize_database()` 方法
2. 重新训练知识库
3. 添加相应的查询示例

### 3. 自定义业务规则

```python
self.business_rules = {
    "中文术语": "英文字段名",
    # ... 更多映射
}
```

## 🔧 故障排除

### 常见问题

1. **ChromaDB初始化失败**
   ```bash
   # 删除现有数据库重新初始化
   rm -rf chroma_db/
   python text2sql_local_deepseek.py
   ```

2. **DeepSeek API错误**
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 检查API配额

3. **依赖包问题**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

4. **SQLite数据库问题**
   ```bash
   # 删除数据库文件重新创建
   rm test_database.db
   python text2sql_local_deepseek.py
   ```

### 日志查看

系统使用Python logging模块，可以在控制台查看详细日志:

```python
# 在config_local.py中修改日志级别
LOG_LEVEL = "DEBUG"  # INFO, WARNING, ERROR
```

## 📈 性能优化

### 1. ChromaDB优化

- 定期清理无用的向量数据
- 调整向量维度和相似度阈值
- 使用SSD存储提高I/O性能

### 2. 查询优化

- 缓存常用查询结果
- 优化SQL查询语句
- 限制结果集大小

### 3. 内存优化

- 定期重启长时间运行的实例
- 监控内存使用情况
- 调整批处理大小

## 🔒 安全考虑

### 1. API密钥安全

- 使用环境变量存储API密钥
- 不要将密钥提交到版本控制
- 定期轮换API密钥

### 2. 数据安全

- 本地数据库文件权限控制
- 定期备份重要数据
- 网络访问限制

## 📝 更新日志

### v1.0.0
- 初始版本发布
- 支持ChromaDB本地部署
- 集成DeepSeek LLM
- 完整的Streamlit界面

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进系统。

## 📄 许可证

本项目仅供学习和研究使用。

## 📞 支持

如有问题，请查看故障排除部分或提交Issue。