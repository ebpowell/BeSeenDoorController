# Test add, del and update permissions against real Door Controller

from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.pg_database import postgres


# Get the database connection parameters from the config file
from door_controller.common_lib.utils import load_config
config = load_config()
controller_ip = config.get('settings', {}).get('urls', [])[0].split('//')[1]  # Extract the IP address from the URL
url = config.get('settings', {}).get('urls', [])[0]
username = config.get('settings', {}).get('username')
password = config.get('settings', {}).get('password')

# Now, extract a single record from the database to use in the test
pg_db = postgres(config.get('settings', {}).get('postgres_connect_string'))
# Fetch a single record to delete from the physical controller. This assumes that there is at least one unassigned fob in the database.
dm = DataManager(url, username, password)
#Test deletion by pulling foblist and looking for deleted fob
success = 0

records = pg_db.get_val("SELECT distinct fob_id " \
    "FROM key_fobs.v_system_fobids_to_remove where controller_ip = concat(%s, '/32')::cidr " \
    "LIMIT 5", (controller_ip,))
for record in records:
    try:
        print (record[0])
        response = dm.del_fob(record[0])
        if response:
            print(f"Attempted to delete fob with ID {record}. Response: {response}")
        else:
            print(f"Failed to delete fob with ID {record}. No FobID not present on controller.")
    except Exception as e:
        raise e
        # print(f"Error occurred while deleting fob: {e}")


fob_list = dm.get_keyfobs()
for record in records:
    if fob_list:
        if int(record[0]) not in fob_list:
            print(f"Fob {record} successfully deleted.")
            success += 1
        else:
            print(f"Fob {record} still present in fob list.")  

if success > 0:
    print(f"Fob deletion test passed. {success} successful deletions]")
    print("Test completed successfully.")
else:  
    print("Fob deletion test failed. No successful deletions.")
    print("Test completed with failures.")

