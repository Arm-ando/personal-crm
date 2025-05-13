import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables from .env
def get_db_connection():
    load_dotenv()
    # Fetch variables
    USER = os.getenv("user")
    PASSWORD = os.getenv("password")
    HOST = os.getenv("host")
    PORT = os.getenv("port")
    DBNAME = os.getenv("dbname")

    try:
        # Establish the connection
        connection = psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        )
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

# Connect to the database
try:
    connection = get_db_connection()
    if connection:
        print("Connection successful!")
        
        # Create a cursor to execute SQL queries
        cursor = connection.cursor()
        
        # Example query
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("Current Time:", result)

        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("Connection closed.")
    else:
        print("Failed to establish a connection.")

except Exception as e:
    print(f"Failed to connect: {e}")