import sys
import os
import psycopg2

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/init_cloud_db.py <DATABASE_URL>")
        print("Example: python scripts/init_cloud_db.py postgres://user:password@host:port/dbname?sslmode=require")
        sys.exit(1)
        
    db_url = sys.argv[1]
    
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print("Successfully connected!")
        
        schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
        print(f"Reading schema.sql from {schema_path}...")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_content = f.read()
            
        print("Executing schema.sql on database...")
        cur.execute(sql_content)
        conn.commit()
        print("Database schema, views, and seed data successfully initialized!")
        
    except Exception as e:
        print(f"\nError initializing database: {str(e)}")
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
