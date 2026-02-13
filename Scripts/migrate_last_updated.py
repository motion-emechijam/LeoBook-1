import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "Data" / "Store"

FILES_TO_MIGRATE = [
    "schedules.csv",
    "teams.csv",
    "region_league.csv",
    "predictions.csv",
    "standings.csv"
]

def migrate_file(filename: str):
    file_path = DATA_DIR / filename
    if not file_path.exists():
        print(f"[SKIP] {filename} does not exist.")
        return

    print(f"[PROCESSING] {filename}...")
    
    # Read all rows
    rows = []
    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print(f"  [WARN] Empty header.")
            return
        rows = list(reader)

    # Check if 'last_updated' exists
    if 'last_updated' in fieldnames:
        print(f"  [OK] 'last_updated' already exists. Checking for empty values...")
        # Optional: Backfill empty values
        updated = False
        now_str = datetime.utcnow().isoformat()
        for row in rows:
            if not row.get('last_updated'):
                row['last_updated'] = now_str
                updated = True
        
        if updated:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  [UPDATED] Backfilled missing timestamps.")
        return

    # Add 'last_updated'
    new_fieldnames = fieldnames + ['last_updated']
    now_str = datetime.utcnow().isoformat()

    for row in rows:
        row['last_updated'] = now_str

    # Write back
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  [SUCCESS] Added 'last_updated' column to {len(rows)} rows.")

if __name__ == "__main__":
    print(f"Migrating CSVs in {DATA_DIR}...")
    for filename in FILES_TO_MIGRATE:
        migrate_file(filename)
    print("Migration complete.")
