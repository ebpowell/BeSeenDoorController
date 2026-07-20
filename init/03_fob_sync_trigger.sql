-- Enable the Python extension in PostgreSQL
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 1. Create the Python Trigger Function
CREATE OR REPLACE FUNCTION key_fobs.process_fob_changes_py()
RETURNS TRIGGER AS $$
    import sys
    import os

    # Resolve project path dynamically (supporting both containerized '/app' and local dev)
    project_path = '/app'
    if not os.path.exists(project_path):
        project_path = '/home/ebpowell/GIT_REPO/BeSeenDoorController'

    if os.path.exists(project_path) and project_path not in sys.path:
        sys.path.append(project_path)

    # Set configuration directory environment variable
    os.environ['APP_CONFIG_DIR'] = os.path.join(project_path, 'config')

    from door_controller.common_lib.utils import load_config
    from door_controller.common_lib.data_manager import DataManager

    # Load project configuration
    config = load_config()
    settings = config.get('settings', {})
    username = settings.get('username')
    password = settings.get('password')
    urls = settings.get('urls', [])

    if not urls:
        plpy.warning("No controller URLs found in config.yaml for fob sync.")
        return "OK"

    event = TD["event"]

    if event == "INSERT":
        fob_id = TD["new"]["fob_id"]
        
        # Get owner name from DB for log and UI presentation
        plan = plpy.prepare("""
            SELECT concat(o.first_name, ' ', o.last_name) owner_name
            FROM key_fobs.keyfobs f
            JOIN key_fobs.properties p ON f.property_id = p.property_id
            LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
            WHERE f.fob_id = $1;
        """, ["integer"])
        res = plpy.execute(plan, [fob_id])
        if res and res[0]["owner_name"]:
            owner_name = res[0]["owner_name"]
        else:
            owner_name = f"Fob {fob_id}"

        # Propagate insert to all configured door controllers
        for url in urls:
            try:
                dm = DataManager(url, username, password)
                add_res = dm.add_fob(fob_id, owner_name)
                
                # Verify add was successful before closing the transaction block
                if not add_res or not add_res[1]:
                    status_code = add_res[0].status_code if add_res and add_res[0] else 'No Response'
                    raise Exception(f"Controller returned status {status_code} and empty record ID.")
                
                plpy.info(f"Successfully added Fob {fob_id} to controller {url} as record ID {add_res[1]}")
            except Exception as e:
                # plpy.error aborts and rolls back the current PostgreSQL transaction
                plpy.error(f"Fob synchronization failed for INSERT of Fob {fob_id} on controller {url}. Error: {e}")

    elif event == "DELETE":
        fob_id = TD["old"]["fob_id"]

        # Propagate delete to all configured door controllers
        for url in urls:
            try:
                dm = DataManager(url, username, password)
                status = dm.del_fob(fob_id)
                
                # Verify delete was successful (expected status 200) before closing the transaction block
                if status != 200:
                    raise Exception(f"Controller returned status code {status} (expected 200).")
                
                plpy.info(f"Successfully deleted Fob {fob_id} from controller {url}")
            except Exception as e:
                # plpy.error aborts and rolls back the current PostgreSQL transaction
                plpy.error(f"Fob synchronization failed for DELETE of Fob {fob_id} on controller {url}. Error: {e}")

    return "OK"
$$ LANGUAGE plpython3u;

-- 2. Attach the Trigger to key_fobs.keyfobs table
DROP TRIGGER IF EXISTS fob_sync_py_trigger ON key_fobs.keyfobs;

CREATE TRIGGER fob_sync_py_trigger
AFTER INSERT OR DELETE ON key_fobs.keyfobs
FOR EACH ROW
EXECUTE FUNCTION key_fobs.process_fob_changes_py();
