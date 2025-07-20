#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地环境设置脚本
"""

import os
import sys
import subprocess
from config_local import LocalConfig

def install_dependencies():
    """安装依赖包"""
    print("安装依赖包...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("依赖包安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装异常: {e}")
        return False

def setup_directories():
    """设置目录结构"""
    print("创建目录结构...")
    
    try:
        LocalConfig.create_directories()
        print("目录结构创建完成")
        return True
    except Exception as e:
        print(f"目录创建失败: {e}")
        return False

def validate_configuration():
    """验证配置"""
    print("验证配置...")
    
    errors = LocalConfig.validate_config()
    
    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("配置验证通过")
        return True

def test_imports():
    """测试关键包导入"""
    print("测试关键包导入...")
    
    test_packages = [
        ("streamlit", "Streamlit"),
        ("vanna", "Vanna AI"),
        ("chromadb", "ChromaDB"),
        ("openai", "OpenAI"),
        ("pandas", "Pandas"),
        ("plotly", "Plotly")
    ]
    
    failed_imports = []
    
    for package, name in test_packages:
        try:
            __import__(package)
            print(f"  [OK] {name}")
        except ImportError:
            print(f"  [ERROR] {name}")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"以下包导入失败: {', '.join(failed_imports)}")
        return False
    else:
        print("所有关键包导入成功")
        return True

def create_sample_env_file():
    """创建示例环境变量文件"""
    env_content = """# TEXT2SQL本地部署环境变量配置
# 复制此文件为 .env 并修改相应的值

# DeepSeek API配置
DEEPSEEK_API_KEY=sk-0e6005b793aa4759bb022b91e9055f86

# ChromaDB配置
CHROMA_DB_PATH=./chroma_db

# SQLite数据库配置
SQLITE_DB_FILE=test_database.db

# 日志级别
LOG_LEVEL=INFO
"""
    
    try:
        with open(".env.example", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("创建示例环境变量文件: .env.example")
        return True
    except Exception as e:
        print(f"创建环境变量文件失败: {e}")
        return False

def main():
    """主函数"""
    print("TEXT2SQL本地部署环境设置")
    print("=" * 50)
    
    steps = [
        ("安装依赖包", install_dependencies),
        ("设置目录结构", setup_directories),
        ("验证配置", validate_configuration),
        ("测试包导入", test_imports),
        ("创建环境变量文件", create_sample_env_file)
    ]
    
    success_count = 0
    
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if step_func():
            success_count += 1
        else:
            print(f"{step_name}失败")
    
    print("\n" + "=" * 50)
    print(f"设置完成: {success_count}/{len(steps)} 步骤成功")
    
    if success_count == len(steps):
        print("环境设置完成！")
        print("\n下一步:")
        print("1. 检查并修改 config_local.py 中的配置")
        print("2. 运行: python run_local_system.py")
        print("3. 或直接运行: streamlit run text2sql_local_deepseek.py")
    else:
        print("部分步骤失败，请检查错误信息并重试")
        sys.exit(1)

if __name__ == "__main__":
    main()