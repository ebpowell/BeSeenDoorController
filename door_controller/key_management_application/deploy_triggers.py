import os
import sys
import psycopg2
from door_controller.common_lib.utils import load_config, log_info

def deploy():
    """
    Reads the trigger SQL script and deploys it to the database configured in config.yaml.
    """
    print("Database Trigger Deployment Tool")
    print("================================")
    
    # 1. Load config
    try:
        config = load_config()
        conn_str = config.get('settings', {}).get('postgres_connect_string')
        if not conn_str:
            print("Error: 'postgres_connect_string' not found in config/config.yaml.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 2. Locate SQL trigger file
    # Try multiple common relative/absolute locations
    possible_paths = [
        "init/03_fob_sync_trigger.sql",
        "SQL/fob_sync_trigger.sql",
        "/app/init/03_fob_sync_trigger.sql",
        "../init/03_fob_sync_trigger.sql"
    ]
    
    sql_path = None
    for p in possible_paths:
        if os.path.exists(p):
            sql_path = p
            break
            
    if not sql_path:
        # Try finding relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        p = os.path.join(project_root, "init", "03_fob_sync_trigger.sql")
        if os.path.exists(p):
            sql_path = p
            
    if not sql_path:
        print("Error: Could not locate 03_fob_sync_trigger.sql file.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Reading trigger SQL script from: {sql_path}")
    try:
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
    except Exception as e:
        print(f"Error reading SQL file: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 3. Connect to DB and deploy
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = False
        with conn.cursor() as cur:
            print("Applying triggers and functions...")
            cur.execute(sql_script)
            conn.commit()
            print("Triggers and PL/Python functions deployed successfully!")
    except Exception as e:
        print(f"\nFailed to deploy triggers: {e}", file=sys.stderr)
        print("Rollback performed.", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def main():
    deploy()

if __name__ == "__main__":
    main()
