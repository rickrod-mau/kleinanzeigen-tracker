import sys
import os
import psycopg2

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url and len(sys.argv) >= 2:
        db_url = sys.argv[1]
        
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set and no argument was provided.")
        print("Usage: python scripts/apply_keyword_update.py [DATABASE_URL]")
        sys.exit(1)
        
    print("Connecting to database to apply keyword updates...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print("Connected successfully!")
        
        script_path = os.path.join(os.path.dirname(__file__), "update_keywords.sql")
        print(f"Reading update_keywords.sql from {script_path}...")
        with open(script_path, "r", encoding="utf-8") as f:
            sql_content = f.read()
            
        print("Executing update_keywords.sql on database...")
        cur.execute(sql_content)
        conn.commit()
        print("Keywords successfully updated in the database!")
        
    except Exception as e:
        print(f"\nError updating keywords: {str(e)}")
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
