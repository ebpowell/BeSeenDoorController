
import time
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version

def main():

    """Main function for 'get_acl_from_controller'."""
    log_info(f"--- Starting get_acl_from_comtroller (v{__version__}) at {get_current_timestamp()} ---")
    #
    # # Accessing command-line arguments for config path
    # args = sys.argv[1:]
    # if args:
    #     log_info(f"Received arguments: {args}")

    # Using common utility to load config
    config = load_config() # Uses default or APP_CONFIG_DIR env var
    if config:
        log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
        log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    else:
        log_info("No config loaded.")

    log_info("Extracting Access List from Door Controller")
    data = {'username': {config.get('settings', {}).get('username')},
            'pwd': {config.get('settings', {}).get('password')},
            'logid': '20101222'}

    obj_db = postgres(config.get('settings', {}).get('postgres_connect_string'))
    obj_db.purge_acl_records()
    record_ids = obj_db.get_fob_records()
    urls = config['settings']['urls']
    for record_id in record_ids:
        print('Record ID:', record_id)
        # ** Implement list comprehension logic ***** TO DO
        for url in urls:
            obj_extract = ww_data_extractor({config.get('settings', {}).get('username')},
                                            {config.get('settings', {}).get('password')}, url, obj_db)
            for x in range(0, 5):
                lst_perms = obj_extract.get_permissions_record(record_id[0])
                # Insert into database
                if lst_perms:
                    [obj_db.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
                    # time.sleep(1)
                    break
                else:  # Record not returned, need to try to pull again
                    print('Iteration: ', x, '...Reconnecting')
                    time.sleep(1)
            # response = objcontrol.navigate(data)
            # if response.status_code == 200:
            #     for x in range(0, 20):
            #         try:
            #             lst_perms = obj_extract.get_permissions_record(record_id[0])
            #             # Insert into database
            #             if lst_perms:
            #                 [obj_db.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
            #                 # time.sleep(1)
            #                 break
            #             else:  # Record not returned, need to try to pull again
            #                 print('Iteration: ', x, '...Reconnecting')
            #                 time.sleep(1)
            #                 response = objcontrol.navigate(data)
            #         except:
            #             raise
            del obj_extract
        obj_db.move_acl_records()

if __name__ == '__main__':
    main()
