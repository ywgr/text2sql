import mysql.connector
from mysql.connector import Error
import subprocess
import sys

def check_mysql_service():
    """检查MySQL服务是否运行"""
    print("=== Checking MySQL Service ===")
    try:
        # Windows服务检查
        result = subprocess.run(['sc', 'query', 'mysql'], 
                              capture_output=True, text=True, shell=True)
        if 'RUNNING' in result.stdout:
            print("✅ MySQL service is running")
            return True
        else:
            print("❌ MySQL service is not running")
            print("Try: net start mysql")
            return False
    except:
        print("⚠️  Could not check service status")
        return None

def try_common_passwords():
    """尝试常见的MySQL密码"""
    print("\n=== Trying Common Passwords ===")
    
    passwords = [
        "",           # 空密码
        "root",       # root
        "password",   # password  
        "123456",     # 123456
        "admin",      # admin
        "mysql",      # mysql
        "123",        # 您提到的123
        "1234",       # 1234
        "12345",      # 12345
    ]
    
    host = "localhost"
    user = "root"
    
    for pwd in passwords:
        try:
            print(f"Trying password: {'(empty)' if pwd == '' else pwd}")
            connection = mysql.connector.connect(
                host=host,
                user=user,
                password=pwd,
                connect_timeout=5
            )
            
            if connection.is_connected():
                print(f"✅ SUCCESS! Password is: {'(empty)' if pwd == '' else pwd}")
                
                # 测试基本操作
                cursor = connection.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()
                print(f"MySQL Version: {version[0]}")
                
                cursor.execute("SHOW DATABASES")
                databases = cursor.fetchall()
                print(f"Available databases: {len(databases)}")
                
                connection.close()
                return pwd
                
        except Error as e:
            if "Access denied" not in str(e):
                print(f"  Error (not password): {e}")
            continue
        except Exception as e:
            print(f"  Connection error: {e}")
            continue
    
    print("❌ None of the common passwords worked")
    return None

def check_mysql_installation():
    """检查MySQL安装"""
    print("\n=== Checking MySQL Installation ===")
    
    try:
        # 检查mysql命令是否可用
        result = subprocess.run(['mysql', '--version'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✅ MySQL client found: {result.stdout.strip()}")
            return True
        else:
            print("❌ MySQL client not found in PATH")
            return False
    except:
        print("❌ MySQL client not accessible")
        return False

def suggest_solutions():
    """提供解决方案建议"""
    print("\n=== Suggested Solutions ===")
    print()
    print("1. 🔧 Reset MySQL Root Password:")
    print("   - Stop MySQL: net stop mysql")
    print("   - Start without password: mysqld --skip-grant-tables")
    print("   - Connect: mysql -u root")
    print("   - Reset: ALTER USER 'root'@'localhost' IDENTIFIED BY 'newpassword';")
    print("   - Restart: net start mysql")
    print()
    print("2. 🔄 Reinstall MySQL:")
    print("   - Download from: https://dev.mysql.com/downloads/mysql/")
    print("   - During installation, set a known password")
    print()
    print("3. 🐳 Use Docker MySQL:")
    print("   - docker run -d -p 3306:3306 -e MYSQL_ROOT_PASSWORD=123 mysql:8.0")
    print()
    print("4. 📱 Use MySQL Workbench:")
    print("   - GUI tool to manage MySQL connections and passwords")
    print()
    print("5. 🔍 Check MySQL Configuration:")
    print("   - Look for my.cnf or my.ini file")
    print("   - Check authentication settings")

def main():
    print("🔍 MySQL Connection Diagnosis Tool")
    print("=" * 50)
    
    # 检查服务
    service_running = check_mysql_service()
    
    # 检查安装
    mysql_installed = check_mysql_installation()
    
    if not mysql_installed:
        print("\n❌ MySQL doesn't seem to be properly installed")
        suggest_solutions()
        return
    
    if service_running is False:
        print("\n❌ MySQL service is not running")
        print("Try starting it with: net start mysql")
        return
    
    # 尝试密码
    working_password = try_common_passwords()
    
    if working_password is not None:
        print(f"\n🎉 Found working password: {'(empty)' if working_password == '' else working_password}")
        
        # 更新配置文件
        try:
            with open('text2sql_system.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            old_line = "'password': '123'  # Updated with correct password"
            new_line = f"'password': '{working_password}'  # Auto-detected password"
            
            content = content.replace(old_line, new_line)
            
            with open('text2sql_system.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Updated system configuration")
            print("\nNext steps:")
            print("1. python setup_db_simple.py")
            print("2. python run_system.py")
            
        except Exception as e:
            print(f"⚠️  Could not update config: {e}")
            print(f"Please manually set password to: {working_password}")
    else:
        suggest_solutions()

if __name__ == "__main__":
    main()