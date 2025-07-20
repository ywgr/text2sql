import mysql.connector
from mysql.connector import Error

def test_mysql_connection():
    print("Testing MySQL connection...")
    
    host = input("Host (default: localhost): ").strip() or "localhost"
    user = input("User (default: root): ").strip() or "root" 
    password = input("Password: ").strip()
    
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        
        if connection.is_connected():
            print("SUCCESS: MySQL connection established!")
            
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            
            print("Available databases:")
            for db in databases:
                print(f"  - {db[0]}")
            
            # Check if TEST database exists
            cursor.execute("SHOW DATABASES LIKE 'TEST'")
            test_db = cursor.fetchone()
            
            if test_db:
                print("TEST database found!")
                cursor.execute("USE TEST")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print("Tables in TEST database:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("TEST database not found. Run setup_db_simple.py first.")
                
        else:
            print("FAILED: Could not connect to MySQL")
            
    except Error as e:
        print(f"ERROR: {e}")
        
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("Connection closed.")

if __name__ == "__main__":
    test_mysql_connection()