import os
import sys
import psycopg2
from door_controller.common_lib.utils import load_config, log_info

def find_sql_file(filename):
    """
    Helper to locate a SQL file across common path structures in host and container environments.
    """
    possible_paths = [
        os.path.join("init", filename),
        os.path.join("SQL", filename),
        os.path.join("/app/init", filename),
        os.path.join("../init", filename)
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
            
    # Try finding relative to this script file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    p = os.path.join(project_root, "init", filename)
    if os.path.exists(p):
        return p
        
    p = os.path.join(project_root, "SQL", filename)
    if os.path.exists(p):
        return p
        
    return None

def deploy():
    """
    Reads the trigger and observability SQL scripts and deploys them to the database configured in config.yaml.
    """
    print("Database Trigger & Observability Deployment Tool")
    print("================================================")
    
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
        
    # 2. Locate SQL script files
    trigger_path = find_sql_file("03_fob_sync_trigger.sql") or find_sql_file("fob_sync_trigger.sql")
    observability_path = find_sql_file("04_observability.sql") or find_sql_file("observability.sql")
    
    if not trigger_path:
        print("Error: Could not locate 03_fob_sync_trigger.sql or fob_sync_trigger.sql script.", file=sys.stderr)
        sys.exit(1)
        
    if not observability_path:
        print("Error: Could not locate 04_observability.sql or observability.sql script.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Found trigger script: {trigger_path}")
    print(f"Found observability script: {observability_path}")
    
    # Read scripts
    try:
        with open(trigger_path, 'r', encoding='utf-8') as f:
            trigger_sql = f.read()
        with open(observability_path, 'r', encoding='utf-8') as f:
            observability_sql = f.read()
    except Exception as e:
        print(f"Error reading SQL files: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 3. Connect to DB and deploy within a single transaction
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = False
        with conn.cursor() as cur:
            print(f"Applying trigger and PL/Python functions from: {trigger_path} ...")
            cur.execute(trigger_sql)
            
            print(f"Applying metrics schema and views from: {observability_path} ...")
            cur.execute(observability_sql)
            
            conn.commit()
            print("Triggers, PL/Python functions, and observability views deployed successfully!")
    except Exception as e:
        print(f"\nFailed to deploy database schemas: {e}", file=sys.stderr)
        print("Rollback performed.", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def main():
    deploy()

if __name__ == "__main__":
    main()
