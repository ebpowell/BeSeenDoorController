import os
from functools import wraps
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.utils import log_info, log_error, load_config
from door_controller.common_lib.door_controller import door_controller
from door_controller.key_management_application.db_manager import FobDatabaseManager

config = load_config()
controller_ip = config.get('settings', {}).get('urls', [])[0].split('//')[1]  # Extract the IP address from the URL
url = config.get('settings', {}).get('urls', [])[0]
username = config.get('settings', {}).get('username')
password = config.get('settings', {}).get('password')
fb = FobDatabaseManager(conn_str=config.get('settings', {}).get('postgres_connect_string'))
lst_doors = fb.get_door_details(controller_ip)
dc = door_controller(username=username, password=password, url=url)
# Get the door record from the database
for door in lst_doors:
    try:
        response = dc.unlock_door(door_desc=door['door_desc'], door_no=door['door_no'], controller_ip=door['controller_ip'])
        if response:
            log_info('Unlocked')
        else:
            log_info('Unlock Fail')        
    except Exception as e:
        raise e

