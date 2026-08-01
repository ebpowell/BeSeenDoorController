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
                
                # Fetch current permissions from Postgres and set them on the controller
                controller_ip = url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
                perm_plan = plpy.prepare("""
                    SELECT door_no, allow 
                    FROM key_fobs.f_get_permissions($1, $2::cidr, NOW()::time, CURRENT_DATE);
                """, ["integer", "text"])
                perm_res = plpy.execute(perm_plan, [fob_id, f"{controller_ip}/32"])
                permissions = [(r["door_no"], r["allow"]) for r in perm_res]

                set_res = dm.set_permissions(permissions, add_res[1])
                if not set_res or set_res.status_code != 200:
                    status_code = set_res.status_code if set_res else 'No Response'
                    raise Exception(f"Failed to set permissions on controller. Returned status {status_code}.")

                plpy.info(f"Successfully added Fob {fob_id} with permissions {permissions} to controller {url} as record ID {add_res[1]}")
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

    elif event == "UPDATE":
        old_fob_id = TD["old"]["fob_id"]
        new_fob_id = TD["new"]["fob_id"]

        if old_fob_id != new_fob_id:
            # Get owner name from DB for log and UI presentation
            plan = plpy.prepare("""
                SELECT concat(o.first_name, ' ', o.last_name) owner_name
                FROM key_fobs.keyfobs f
                JOIN key_fobs.properties p ON f.property_id = p.property_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE f.fob_id = $1;
            """, ["integer"])
            res = plpy.execute(plan, [new_fob_id])
            if res and res[0]["owner_name"]:
                owner_name = res[0]["owner_name"]
            else:
                owner_name = f"Fob {new_fob_id}"

            # Propagate update (add new, delete old) to all configured door controllers
            for url in urls:
                try:
                    dm = DataManager(url, username, password)
                    
                    # 1. Add the new fob
                    add_res = dm.add_fob(new_fob_id, owner_name)
                    if not add_res or not add_res[1]:
                        status_code = add_res[0].status_code if add_res and add_res[0] else 'No Response'
                        raise Exception(f"Failed to add new fob {new_fob_id}. Controller returned status {status_code} and empty record ID.")
                    
                    # 2. Fetch current permissions from Postgres and set them for the new fob on the controller
                    controller_ip = url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
                    perm_plan = plpy.prepare("""
                        SELECT door_no, allow 
                        FROM key_fobs.f_get_permissions($1, $2::cidr, NOW()::time, CURRENT_DATE);
                    """, ["integer", "text"])
                    perm_res = plpy.execute(perm_plan, [new_fob_id, f"{controller_ip}/32"])
                    permissions = [(r["door_no"], r["allow"]) for r in perm_res]

                    set_res = dm.set_permissions(permissions, add_res[1])
                    if not set_res or set_res.status_code != 200:
                        status_code = set_res.status_code if set_res else 'No Response'
                        raise Exception(f"Failed to set permissions for new fob {new_fob_id}. Returned status {status_code}.")

                    # 3. Delete the old fob
                    status = dm.del_fob(old_fob_id)
                    if status != 200:
                        raise Exception(f"Failed to delete old fob {old_fob_id}. Controller returned status code {status} (expected 200).")

                    plpy.info(f"Successfully updated Fob {old_fob_id} -> {new_fob_id} with permissions {permissions} on controller {url}")
                except Exception as e:
                    # plpy.error aborts and rolls back the current PostgreSQL transaction
                    plpy.error(f"Fob synchronization failed for UPDATE of Fob {old_fob_id} -> {new_fob_id} on controller {url}. Error: {e}")

    return "OK"
$$ LANGUAGE plpython3u;

-- 2. Attach the Trigger to key_fobs.keyfobs table
DROP TRIGGER IF EXISTS fob_sync_py_trigger ON key_fobs.keyfobs;

CREATE TRIGGER fob_sync_py_trigger
AFTER INSERT OR UPDATE OR DELETE ON key_fobs.keyfobs
FOR EACH ROW
EXECUTE FUNCTION key_fobs.process_fob_changes_py();
