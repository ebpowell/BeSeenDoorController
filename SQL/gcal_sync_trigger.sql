-- Enable the Python extension in PostgreSQL
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 1. Create the PL/Python Trigger Function for Google Calendar Sync
CREATE OR REPLACE FUNCTION key_fobs.process_gcal_sync_py()
RETURNS TRIGGER AS $$
    import sys
    import os

    # Resolve project path dynamically (supporting container '/app', host git repo, and site-packages)
    candidate_paths = [
        '/app',
        '/home/ebpowell/GIT_REPO/BeSeenDoorController',
        os.getcwd()
    ]

    project_path = None
    for p in candidate_paths:
        if p and os.path.exists(os.path.join(p, 'door_controller', 'common_lib', 'gcal_sync.py')):
            project_path = p
            break

    if not project_path:
        # Fallback to /app if present
        if os.path.exists('/app'):
            project_path = '/app'
        elif os.path.exists('/home/ebpowell/GIT_REPO/BeSeenDoorController'):
            project_path = '/home/ebpowell/GIT_REPO/BeSeenDoorController'

    if project_path:
        if project_path in sys.path:
            sys.path.remove(project_path)
        sys.path.insert(0, project_path)
        os.environ['APP_CONFIG_DIR'] = os.path.join(project_path, 'config')

    try:
        from door_controller.common_lib.gcal_sync import GoogleCalendarSync
    except ModuleNotFoundError as e:
        plpy.warning(f"GoogleCalendarSync trigger notice: Could not import GoogleCalendarSync module: {e}")
        return "OK"

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
        action = res.get('action')
        if action in ('created', 'updated', 'deleted'):
            plpy.info(f"GoogleCalendarSync: Successfully synced trigger event '{event}' to Google Calendar. Action: {action}, GCal Event ID: {res.get('gcal_id')}")
        elif action == 'skipped_ineligible':
            plpy.info(f"GoogleCalendarSync Notice: Skipped GCal sync for '{event}'. Reason: {res.get('reason')}")
        else:
            plpy.warning(f"GoogleCalendarSync Warning: GCal sync result for '{event}': {res}")
    except Exception as e:
        plpy.warning(f"GoogleCalendarSync Error: Warning executing trigger on {event}: {e}")

    return "OK"
$$ LANGUAGE plpython3u;

-- 2. Attach the Trigger to key_fobs.clubhouse_reservations table
DROP TRIGGER IF EXISTS gcal_sync_py_trigger ON key_fobs.clubhouse_reservations;

CREATE TRIGGER gcal_sync_py_trigger
AFTER INSERT OR UPDATE OR DELETE ON key_fobs.clubhouse_reservations
FOR EACH ROW
EXECUTE FUNCTION key_fobs.process_gcal_sync_py();
