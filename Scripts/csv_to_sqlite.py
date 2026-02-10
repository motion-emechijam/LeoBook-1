"""
Convert predictions.csv to SQLite database for efficient querying.
This solves the timeout issues with the 6.8 MB CSV file.
"""

import sqlite3
import csv
import os
from pathlib import Path

def csv_to_sqlite(csv_path, db_path):
    """Convert predictions CSV to SQLite database."""
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Reading CSV from: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        headers = next(reader)
        
        print(f"Headers: {headers}")
        
        # Create table with dynamic columns
        column_defs = ', '.join([f'"{h}" TEXT' for h in headers])
        create_table_sql = f'CREATE TABLE predictions ({column_defs})'
        cursor.execute(create_table_sql)
        
        # Create indexes for common queries
        cursor.execute('CREATE INDEX idx_fixture_id ON predictions(fixture_id)')
        cursor.execute('CREATE INDEX idx_date ON predictions(date)' if 'date' in headers else 'SELECT 1')
        cursor.execute('CREATE INDEX idx_league ON predictions(league)' if 'league' in headers else 'SELECT 1')
        
        # Insert data in batches for performance
        placeholders = ', '.join(['?' for _ in headers])
        insert_sql = f'INSERT INTO predictions VALUES ({placeholders})'
        
        batch = []
        batch_size = 1000
        total_rows = 0
        
        for row in reader:
            if len(row) == len(headers):
                batch.append(row)
                total_rows += 1
                
                if len(batch) >= batch_size:
                    cursor.executemany(insert_sql, batch)
                    batch = []
                    if total_rows % 10000 == 0:
                        print(f"Inserted {total_rows} rows...")
        
        # Insert remaining rows
        if batch:
            cursor.executemany(insert_sql, batch)
        
        conn.commit()
        print(f"\nSuccessfully created SQLite database with {total_rows} rows")
        print(f"Database size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB")
    
    conn.close()

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    csv_file = base_dir / "Data" / "Store" / "predictions.csv"
    db_file = base_dir / "Data" / "Store" / "predictions.db"
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        exit(1)
    
    print("Converting predictions.csv to SQLite database...")
    csv_to_sqlite(str(csv_file), str(db_file))
    print(f"\nDatabase ready at: {db_file}")
