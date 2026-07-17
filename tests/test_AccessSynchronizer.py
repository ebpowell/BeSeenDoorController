# Test add, del and update permissions against real Door Controller

from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.pg_database import postgres
from door_controller.key_management_application.update_access import AccessSynchronizer


# Get the database connection parameters from the config file
from door_controller.common_lib.utils import load_config



if __name__ == '__main__':
    config = load_config()
    controller_ip = config.get('settings', {}).get('urls', [])[0].split('//')[1]  # Extract the IP address from the URL
    url = config.get('settings', {}).get('urls', [])[0]
    username = config.get('settings', {}).get('username')
    password = config.get('settings', {}).get('password')

    # Now, extract a single record from the database to use in the test
    # pg_db = postgres(config.get('settings', {}).get('postgres_connect_string'))
    connect_string = config.get('settings', {}).get('postgres_connect_string')
    # Fetch a single record to delete from the physical controller. This assumes that there is at least one unassigned fob in the database.
    dm = DataManager(url, username, password)
    #Test deletion by pulling foblist and looking for deleted fob
    success = 0
    objAC = AccessSynchronizer(username, password, connect_string)
    objAC.synchronize_access(url)

