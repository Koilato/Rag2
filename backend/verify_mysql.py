import sys
import os

# Add the parent directory to the Python path to allow importing MySqlSource
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MySqlSource import connect_to_mysql, close_connection

def verify_mysql_connection():
    print("Attempting to connect to MySQL...")
    connection = connect_to_mysql()
    if connection:
        print("Successfully connected to MySQL.")
        try:
            with connection.cursor() as cursor:
                # Try to list tables as a simple verification
                cursor.execute("SHOW TABLES;")
                tables = cursor.fetchall()
                print("Tables in the database:")
                for table in tables:
                    print(f"- {table}")
        except Exception as e:
            print(f"Error executing query: {e}")
        finally:
            close_connection(connection)
    else:
        print("Failed to connect to MySQL.")

if __name__ == "__main__":
    verify_mysql_connection()
