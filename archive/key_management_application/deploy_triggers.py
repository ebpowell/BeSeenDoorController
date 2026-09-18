import os
import sys
import psycopg2
from door_controller.common_lib.utils import load_config, log_info, log_error

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

def deploy(conn_str, mode=0):
    """
    Reads all SQL scripts in the 'init' folder sequentially and deploys them to the database configured in config.yaml.
    """
    print("Database Trigger & Observability Deployment Tool")
    print("================================================")
    
  
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
    if mode == 0:
        print("Mode 0: Deploying all SQL files.")
    else:
        print("Mode 1: Skipping the first SQL file (for testing).")
        sql_file_paths = sql_file_paths[1:]  # Skip the first file - database exists

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
    import sys
    import argparse
    
    if argv is None:
        if any('unittest' in arg or 'pytest' in arg for arg in sys.argv) or (len(sys.argv) > 1 and sys.argv[1] == 'discover'):
            argv = []
        else:
            argv = sys.argv[1:]
            
    parser = argparse.ArgumentParser(description="Synchronize door controllers with database fobs and ACLs.")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as a daemon scheduling periodic updates.")
    parser.add_argument("-l", "--limit-changes", type=int, default=None, help="Limit the number of mutating changes applied per controller.")
    parser.add_argument("-c", "--config", type=str, default=None, help="Path to configuration file (optional).")

    args = parser.parse_args(argv)

    log_info("Starting global door controller synchronization routine.")
    if args.config:
        config = load_config(args.config)
    else:
        config = load_config()  
    if not config:
        log_error("Failed to load configuration.")
        return
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
        
    deploy(conn_str, mode=0)

if __name__ == "__main__":
    main()

