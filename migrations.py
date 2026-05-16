"""
Database Migration Script
Adds missing columns to existing tables
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Use the same MySQL configuration as app.py
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "Aroako123."
DATABASE_NAME = "bookstore_db"


def make_url(database=None):
    return URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=database,
    )


def run_migrations():
    db_engine = create_engine(make_url(DATABASE_NAME))
    
    with db_engine.connect() as conn:
        # Check if orders table has status column
        result = conn.execute(text("SHOW COLUMNS FROM orders LIKE 'status'"))
        status_column_exists = result.fetchone()
        
        if not status_column_exists:
            print("Adding 'status' column to orders table...")
            conn.execute(text("ALTER TABLE orders ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'Pending'"))
            conn.commit()
            print("Successfully added 'status' column to orders table.")
        else:
            print("The 'status' column already exists in orders table.")
        
        # Verify the column was added
        result = conn.execute(text("SHOW COLUMNS FROM orders"))
        columns = [row[0] for row in result.fetchall()]
        print(f"\nCurrent columns in orders table: {columns}")


if __name__ == "__main__":
    print("Running database migrations...")
    run_migrations()
    print("\nMigration complete!")
