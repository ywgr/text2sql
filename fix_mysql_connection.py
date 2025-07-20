import mysql.connector
from mysql.connector import Error
import getpass

def test_mysql_with_password():
    print("=== MySQL Connection Troubleshooter ===")
    print("Error 1045 means access denied - we need the correct password")
    print()
    
    host = input("Host (default: localhost): ").strip() or "localhost"
    user = input("User (default: root): ").strip() or "root"
    
    # Try different password scenarios
    print("\nTrying different password options:")
    
    # Option 1: Try with password
    print("1. Enter your MySQL root password:")
    password = getpass.getpass("Password (hidden): ")
    
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        
        if connection.is_connected():
            print("✅ SUCCESS: Connected with password!")
            
            # Save connection info for later use
            print(f"\n📝 Your working connection settings:")
            print(f"Host: {host}")
            print(f"User: {user}")
            print(f"Password: [HIDDEN - length {len(password)}]")
            
            # Test database operations
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"MySQL Version: {version[0]}")
            
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            print(f"Found {len(databases)} databases")
            
            connection.close()
            
            # Update the main system file with correct password
            update_system_config(password)
            return True
            
    except Error as e:
        print(f"❌ Still failed with password: {e}")
        
        # Option 2: Try common default passwords
        print("\n2. Trying common default passwords...")
        common_passwords = ["", "root", "password", "123456", "admin"]
        
        for pwd in common_passwords:
            try:
                connection = mysql.connector.connect(
                    host=host,
                    user=user,
                    password=pwd
                )
                if connection.is_connected():
                    print(f"✅ SUCCESS: Connected with password '{pwd}'!")
                    connection.close()
                    update_system_config(pwd)
                    return True
            except:
                continue
        
        print("❌ None of the common passwords worked")
        
    # Option 3: Instructions for resetting password
    print("\n3. 🔧 MySQL Password Reset Instructions:")
    print("If you forgot your MySQL password, you can reset it:")
    print()
    print("Method 1 - Using MySQL Workbench:")
    print("- Open MySQL Workbench")
    print("- Go to Server > Users and Privileges")
    print("- Select root user and reset password")
    print()
    print("Method 2 - Command line (Windows):")
    print("1. Stop MySQL service: net stop mysql")
    print("2. Start MySQL without password: mysqld --skip-grant-tables")
    print("3. Connect: mysql -u root")
    print("4. Reset password: ALTER USER 'root'@'localhost' IDENTIFIED BY 'newpassword';")
    print("5. Restart MySQL service normally")
    print()
    print("Method 3 - Reinstall MySQL with known password")
    
    return False

def update_system_config(password):
    """Update the main system file with correct password"""
    try:
        with open('text2sql_system.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the password in the config
        old_line = "'password': ''  # 请根据实际情况修改"
        new_line = f"'password': '{password}'  # Auto-updated by fix script"
        
        if old_line in content:
            content = content.replace(old_line, new_line)
            
            with open('text2sql_system.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Updated text2sql_system.py with correct password")
        else:
            print("⚠️  Could not auto-update password in text2sql_system.py")
            print(f"Please manually change the password to: {password}")
            
    except Exception as e:
        print(f"⚠️  Could not update config file: {e}")
        print(f"Please manually set password to: {password}")

if __name__ == "__main__":
    if test_mysql_with_password():
        print("\n🎉 MySQL connection fixed!")
        print("Now you can run: python setup_db_simple.py")
    else:
        print("\n❌ Could not establish MySQL connection")
        print("Please check your MySQL installation and password")