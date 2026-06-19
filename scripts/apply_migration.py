import sys
import os
import psycopg2

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/apply_migration.py <MIGRATION_FILE> <DATABASE_URL>")
        sys.exit(1)
        
    migration_file = sys.argv[1]
    db_url = sys.argv[2]
    
    print(f"Connecting to database to apply migration from '{migration_file}'...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print("Connected successfully!")
        
        print(f"Reading SQL content...")
        with open(migration_file, "r", encoding="utf-8") as f:
            sql_content = f.read()
            
        print("Executing SQL script...")
        cur.execute(sql_content)
        conn.commit()
        print("Migration successfully applied!")
        
    except Exception as e:
        print(f"\nError running migration: {str(e)}")
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
