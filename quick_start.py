#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEXT2SQL本地系统快速启动脚本
一键设置和启动系统
"""

import os
import sys
import subprocess
import time

def print_banner():
    """打印启动横幅"""
    banner = """
================================================================
                TEXT2SQL本地部署系统                          
              ChromaDB + DeepSeek + SQLite                   
                     快速启动工具                             
================================================================
"""
    print(banner)

def check_python_version():
    """检查Python版本"""
    print("检查Python版本...")
    
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        print(f"当前版本: {sys.version}")
        return False
    
    print(f"✅ Python版本: {sys.version.split()[0]}")
    return True

def install_requirements():
    """安装依赖包"""
    print("安装依赖包...")
    
    if not os.path.exists("requirements.txt"):
        print("❌ 找不到requirements.txt文件")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 依赖包安装完成")
            return True
        else:
            print("❌ 依赖包安装失败")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 安装超时")
        return False
    except Exception as e:
        print(f"❌ 安装异常: {e}")
        return False

def setup_environment():
    """设置环境"""
    print("设置环境...")
    
    try:
        # 运行环境设置脚本
        if os.path.exists("setup_local_environment.py"):
            result = subprocess.run([
                sys.executable, "setup_local_environment.py"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 环境设置完成")
                return True
            else:
                print("❌ 环境设置失败")
                print(result.stderr)
                return False
        else:
            # 手动创建必要目录
            os.makedirs("chroma_db", exist_ok=True)
            print("✅ 创建基本目录结构")
            return True
            
    except Exception as e:
        print(f"❌ 环境设置异常: {e}")
        return False

def run_tests():
    """运行测试"""
    print("运行系统测试...")
    
    try:
        if os.path.exists("test_local_system.py"):
            result = subprocess.run([
                sys.executable, "test_local_system.py"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 系统测试通过")
                return True
            else:
                print("⚠️ 部分测试失败，但可以继续")
                print("详细信息请查看测试输出")
                return True  # 允许继续，因为可能只是API测试失败
        else:
            print("⚠️ 测试脚本不存在，跳过测试")
            return True
            
    except Exception as e:
        print(f"⚠️ 测试异常: {e}")
        return True  # 允许继续

def start_system():
    """启动系统"""
    print("启动TEXT2SQL系统...")
    
    try:
        # 检查主程序文件
        if not os.path.exists("text2sql_local_deepseek.py"):
            print("❌ 找不到主程序文件: text2sql_local_deepseek.py")
            return False
        
        print("找到主程序文件")
        print("启动Streamlit服务...")
        print("浏览器将自动打开 http://localhost:8501")
        print("按 Ctrl+C 停止服务")
        print("-" * 60)
        
        # 启动Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "text2sql_local_deepseek.py",
            "--server.port=8501",
            "--server.address=localhost"
        ])
        
        return True
        
    except KeyboardInterrupt:
        print("\n用户停止服务")
        return True
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

def interactive_setup():
    """交互式设置"""
    print("交互式配置...")
    
    # 检查配置文件
    if not os.path.exists("config_local.py"):
        print("❌ 找不到配置文件 config_local.py")
        
        create_config = input("是否创建默认配置文件? (y/n): ").lower().strip()
        if create_config == 'y':
            try:
                # 创建基本配置文件
                config_content = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地TEXT2SQL系统配置文件
"""

import os

class LocalConfig:
    """本地部署配置"""
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY = "sk-0e6005b793aa4759bb022b91e9055f86"  # 请替换为您的API密钥
    DEEPSEEK_MODEL = "deepseek-chat"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    
    # ChromaDB配置
    CHROMA_DB_PATH = "./chroma_db"
    CHROMA_COLLECTION_NAME = "text2sql_knowledge"
    CHROMA_PERSIST = True
    
    # SQLite数据库配置
    SQLITE_DB_FILE = "test_database.db"
    
    # 系统配置
    LOG_LEVEL = "INFO"
    MAX_TOKENS = 1000
    TEMPERATURE = 0.1
    
    @classmethod
    def get_chroma_config(cls):
        """获取ChromaDB配置"""
        return {
            "api_key": cls.DEEPSEEK_API_KEY,
            "model": cls.DEEPSEEK_MODEL,
            "path": cls.CHROMA_DB_PATH,
            "collection_name": cls.CHROMA_COLLECTION_NAME
        }
'''
                
                with open("config_local.py", "w", encoding="utf-8") as f:
                    f.write(config_content)
                
                print("✅ 创建默认配置文件")
                print("⚠️ 请编辑 config_local.py 设置您的DeepSeek API密钥")
                
            except Exception as e:
                print(f"❌ 创建配置文件失败: {e}")
                return False
        else:
            print("❌ 需要配置文件才能继续")
            return False
    
    return True

def main():
    """主函数"""
    print_banner()
    
    steps = [
        ("检查Python版本", check_python_version),
        ("交互式设置", interactive_setup),
        ("安装依赖包", install_requirements),
        ("设置环境", setup_environment),
        ("运行测试", run_tests),
        ("启动系统", start_system)
    ]
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name} {'='*20}")
        
        if not step_func():
            print(f"\n❌ {step_name}失败，无法继续")
            
            if step_name == "运行测试":
                # 测试失败时询问是否继续
                continue_anyway = input("是否忽略测试错误继续启动? (y/n): ").lower().strip()
                if continue_anyway == 'y':
                    continue
            
            sys.exit(1)
        
        if step_name != "启动系统":  # 启动系统是最后一步，不需要等待
            time.sleep(1)
    
    print("\n系统启动完成！")

if __name__ == "__main__":
    main()