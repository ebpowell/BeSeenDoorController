import os
import sys
import psycopg2
from door_controller.common_lib.utils import load_config, log_info

def find_init_dir():
    """
    Helper to locate the 'init' directory across common path structures in host and container environments.
    """
    possible_paths = [
        "init",
        "/app/init",
        "../init",
        "SQL",
        "/app/SQL",
        "../SQL"
    ]
    for p in possible_paths:
        if os.path.isdir(p):
            return p

    # Try finding relative to this script file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))

    for folder_name in ["init", "SQL"]:
        p = os.path.join(project_root, folder_name)
        if os.path.isdir(p):
            return p

    return None

def find_sql_file(filename):
    """
    Helper to locate a specific SQL file within the init/SQL directory.
    """
    init_dir = find_init_dir()
    if init_dir:
        p = os.path.join(init_dir, filename)
        if os.path.exists(p):
            return p
    return None

def get_sql_files(init_dir):
    """
    Returns a sorted list of full file paths for all .sql files in the given directory.
    """
    if not init_dir or not os.path.isdir(init_dir):
        return []
    sql_files = [f for f in os.listdir(init_dir) if f.endswith(".sql")]
    sql_files.sort()
    return [os.path.join(init_dir, f) for f in sql_files]

def deploy():
    """
    Reads all SQL scripts in the 'init' folder sequentially and deploys them to the database configured in config.yaml.
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
        
    # 2. Locate SQL script files in the init directory
    init_dir = find_init_dir()
    if not init_dir:
        print("Error: Could not locate 'init' directory.", file=sys.stderr)
        sys.exit(1)
        
    sql_file_paths = get_sql_files(init_dir)
    if not sql_file_paths:
        print(f"Error: No SQL files found in directory '{init_dir}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Found SQL directory: {init_dir}")
    print(f"Found {len(sql_file_paths)} SQL file(s) to execute sequentially:")
    for path in sql_file_paths:
        print(f"  - {os.path.basename(path)}")

    # 3. Read scripts
    sql_contents = []
    try:
        for path in sql_file_paths:
            with open(path, 'r', encoding='utf-8') as f:
                sql_contents.append((path, f.read()))
    except Exception as e:
        print(f"Error reading SQL files: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 4. Connect to DB and deploy within a single transaction
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = False
        with conn.cursor() as cur:
            for path, sql_content in sql_contents:
                filename = os.path.basename(path)
                print(f"Applying {filename} from: {path} ...")
                cur.execute(sql_content)
        
            conn.commit()
            print("All SQL scripts deployed successfully!")

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

