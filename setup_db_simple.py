import mysql.connector
from mysql.connector import Error

def setup_database():
    print("=== Database Setup ===")
    
    # Get connection info
    host = input("MySQL host (default: localhost): ").strip() or "localhost"
    user = input("MySQL user (default: root): ").strip() or "root"
    password = input("MySQL password: ").strip()
    
    try:
        # Connect to MySQL
        print("Connecting to MySQL...")
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        
        if connection.is_connected():
            print("Connected successfully!")
            cursor = connection.cursor()
            
            # Create database
            print("Creating database TEST...")
            cursor.execute("CREATE DATABASE IF NOT EXISTS TEST")
            cursor.execute("USE TEST")
            
            # Create tables
            print("Creating tables...")
            
            # Student table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student (
                    student_id INT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL,
                    gender VARCHAR(10) NOT NULL,
                    class VARCHAR(20) NOT NULL
                )
            """)
            
            # Course table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS course (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    course_name VARCHAR(50) NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES student(student_id)
                )
            """)
            
            # Score table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS score (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    course_name VARCHAR(50) NOT NULL,
                    score DECIMAL(5,2) NOT NULL,
                    name VARCHAR(50) NOT NULL
                )
            """)
            
            # Insert test data
            print("Inserting test data...")
            
            # Clear existing data
            cursor.execute("DELETE FROM score")
            cursor.execute("DELETE FROM course") 
            cursor.execute("DELETE FROM student")
            
            # Student data
            students = [
                (1001, 'Zhang San', 'Male', 'Class 1-1'),
                (1002, 'Li Si', 'Male', 'Class 1-1'),
                (1003, 'Wang Wu', 'Male', 'Class 1-2'),
                (1004, 'Zhao Liu', 'Female', 'Class 1-2'),
                (1005, 'Qian Qi', 'Female', 'Class 1-3')
            ]
            
            cursor.executemany(
                "INSERT INTO student (student_id, name, gender, class) VALUES (%s, %s, %s, %s)",
                students
            )
            
            # Course data
            courses = [
                (1001, 'Chinese'), (1001, 'Math'), (1001, 'English'),
                (1002, 'Chinese'), (1002, 'Physics'), (1002, 'Chemistry'),
                (1003, 'Math'), (1003, 'Physics'), (1003, 'Biology'),
                (1004, 'Chinese'), (1004, 'English'), (1004, 'History'),
                (1005, 'Math'), (1005, 'Geography'), (1005, 'Politics')
            ]
            
            cursor.executemany(
                "INSERT INTO course (student_id, course_name) VALUES (%s, %s)",
                courses
            )
            
            # Score data
            scores = [
                ('Chinese', 85.5, 'Zhang San'), ('Math', 92.0, 'Zhang San'), ('English', 78.5, 'Zhang San'),
                ('Chinese', 76.0, 'Li Si'), ('Physics', 88.5, 'Li Si'), ('Chemistry', 90.0, 'Li Si'),
                ('Math', 95.5, 'Wang Wu'), ('Physics', 82.0, 'Wang Wu'), ('Biology', 79.5, 'Wang Wu'),
                ('Chinese', 88.0, 'Zhao Liu'), ('English', 92.5, 'Zhao Liu'), ('History', 85.0, 'Zhao Liu'),
                ('Math', 90.0, 'Qian Qi'), ('Geography', 87.5, 'Qian Qi'), ('Politics', 93.0, 'Qian Qi')
            ]
            
            cursor.executemany(
                "INSERT INTO score (course_name, score, name) VALUES (%s, %s, %s)",
                scores
            )
            
            connection.commit()
            
            # Verify data
            print("Verifying data...")
            cursor.execute("SELECT COUNT(*) FROM student")
            student_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM course") 
            course_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM score")
            score_count = cursor.fetchone()[0]
            
            print(f"Students: {student_count}")
            print(f"Courses: {course_count}")
            print(f"Scores: {score_count}")
            
            print("Database setup completed successfully!")
            
    except Error as e:
        print(f"Error: {e}")
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("Connection closed.")

if __name__ == "__main__":
    setup_database()