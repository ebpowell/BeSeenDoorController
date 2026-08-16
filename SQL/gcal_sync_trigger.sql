-- Enable the Python extension in PostgreSQL
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 1. Create the PL/Python Trigger Function for Google Calendar Sync
CREATE OR REPLACE FUNCTION key_fobs.process_gcal_sync_py()
RETURNS TRIGGER AS $$
    import sys
    import os

    # Resolve project path dynamically (supporting container '/app' and local dev)
    project_path = '/app'
    if not os.path.exists(project_path):
        project_path = '/home/ebpowell/GIT_REPO/BeSeenDoorController'

    if os.path.exists(project_path) and project_path not in sys.path:
        sys.path.append(project_path)

    os.environ['APP_CONFIG_DIR'] = os.path.join(project_path, 'config')

    from door_controller.common_lib.gcal_sync import GoogleCalendarSync

    event = TD["event"]
    old_row = dict(TD["old"]) if TD["old"] is not None else None
    new_row = dict(TD["new"]) if TD["new"] is not None else None

    # Handle owner name and property address lookup for property_id if present; fallback gracefully for community events
    if new_row:
        prop_id = new_row.get("property_id")
        if prop_id:
            try:
                plan = plpy.prepare("""
                    SELECT concat(o.first_name, ' ', o.last_name) AS owner_name, p.address
                    FROM key_fobs.properties p
                    LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                    WHERE p.property_id = $1;
                """, ["integer"])
                res = plpy.execute(plan, [prop_id])
                if res:
                    if not new_row.get("owner_name") and res[0].get("owner_name"):
                        new_row["owner_name"] = res[0]["owner_name"]
                    if not new_row.get("address") and res[0].get("address"):
                        new_row["address"] = res[0]["address"]
            except Exception as e:
                plpy.warning(f"GoogleCalendarSync trigger notice: Could not fetch owner details for property_id {prop_id}: {e}")
        else:
            if not new_row.get("address"):
                new_row["address"] = "Community Clubhouse"
            if "owner_name" not in new_row:
                new_row["owner_name"] = ""

    try:
        syncer = GoogleCalendarSync()
        res = syncer.process_trigger_event(event_type=event, old_row=old_row, new_row=new_row)
        plpy.info(f"GoogleCalendarSync: Processed trigger event '{event}' for reservation. Action result: {res.get('action')}")
    except Exception as e:
        plpy.warning(f"GoogleCalendarSync: Warning executing trigger on {event}: {e}")

    return "OK"
$$ LANGUAGE plpython3u;

-- 2. Attach the Trigger to key_fobs.clubhouse_reservations table
DROP TRIGGER IF EXISTS gcal_sync_py_trigger ON key_fobs.clubhouse_reservations;

CREATE TRIGGER gcal_sync_py_trigger
AFTER INSERT OR UPDATE OR DELETE ON key_fobs.clubhouse_reservations
FOR EACH ROW
EXECUTE FUNCTION key_fobs.process_gcal_sync_py();
