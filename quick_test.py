import mysql.connector
from mysql.connector import Error

def test_with_password_123():
    print("Testing MySQL connection with password '123'...")
    
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='123'
        )
        
        if connection.is_connected():
            print("✅ SUCCESS: Connected to MySQL!")
            
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"MySQL Version: {version[0]}")
            
            # Check for TEST database
            cursor.execute("SHOW DATABASES LIKE 'TEST'")
            test_db = cursor.fetchone()
            
            if test_db:
                print("✅ TEST database already exists")
            else:
                print("ℹ️  TEST database not found - will create it")
            
            cursor.close()
            connection.close()
            
            # Update the system config file
            update_config()
            
            return True
            
    except Error as e:
        print(f"❌ Connection failed: {e}")
        return False

def update_config():
    """Update text2sql_system.py with correct password"""
    try:
        with open('text2sql_system.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace password
        old_line = "'password': ''  # 请根据实际情况修改"
        new_line = "'password': '123'  # Updated with correct password"
        
        if old_line in content:
            content = content.replace(old_line, new_line)
            
            with open('text2sql_system.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Updated text2sql_system.py with password '123'")
        else:
            print("⚠️  Config file already updated or format changed")
            
    except Exception as e:
        print(f"⚠️  Could not update config: {e}")

if __name__ == "__main__":
    if test_with_password_123():
        print("\n🎉 MySQL connection successful!")
        print("Next steps:")
        print("1. Run: python setup_db_simple.py")
        print("2. Then: python run_system.py")
    else:
        print("\n❌ Please check if MySQL is running and password is correct")