-- Enable the Python extension in PostgreSQL
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 1. Create the Python Trigger Function
CREATE OR REPLACE FUNCTION process_fob_changes_py()
RETURNS TRIGGER AS $$
    # You can import your existing Python modules here
    import sys
    
    # Point this to where BeSeenDoorController/door_controller/common_lib lives
    sys.path.append('/path/to/your/project/door_controller/common_lib')
    import data_manager

    # TD["event"] holds the trigger type ("INSERT" or "DELETE")
    if TD["event"] == "INSERT":
        # TD["new"] holds the newly inserted row as a dictionary
        fob_id = TD["new"]["fob_id"]
        
        # Call your existing Python function
        data_manager.add_fob(fob_id)
        plpy.info(f"Successfully ran add_fob for ID: {fob_id}")

    elif TD["event"] == "DELETE":
        # TD["old"] holds the deleted row as a dictionary
        fob_id = TD["old"]["fob_id"]
        
        # Call your existing Python function
        data_manager.del_fob(fob_id)
        plpy.info(f"Successfully ran del_fob for ID: {fob_id}")

    return "OK"
$$ LANGUAGE plpython3u;

-- 2. Attach the Trigger
CREATE TRIGGER fob_sync_py_trigger
AFTER INSERT OR DELETE ON fobs_table
FOR EACH ROW
EXECUTE FUNCTION process_fob_changes_py();