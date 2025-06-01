import sys
import time
from door_controller.common_lib.access_control_list import AccessControlList
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version


def main():
    # username = "abc"
    # password = "654321"
    # urls = ["http://69.21.119.147", "http://69.21.119.148"]

    # strconnect = "host=192.168.50.150 dbname=wntworth_db user=wentworth_user password=ww_s3cret"
    # record_id = 55
    # objdb = cls_sqlite('/door_controller_data')

    """Main function for 'get_acl_from_controller'."""
    # log_info(f"--- Starting get_acl_from_comtroller (v{__version__}) at {get_current_timestamp()} ---")
    #
    # # Accessing command-line arguments for config path
    # args = sys.argv[1:]
    # if args:
    #     log_info(f"Received arguments: {args}")

    # Using common utility to load config
    config = load_config() # Uses default or APP_CONFIG_DIR env var
    # config = load_config(args[0])  # Uses default or APP_CONFIG_DIR env var
    if config:
        log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
        log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    else:
        log_info("No config loaded.")

    log_info("Extracting Access List from Door Controller")
    data = {'username': {config.get('settings', {}).get('username')},
            'pwd': {config.get('settings', {}).get('password')},
            'logid': '20101222'}

    objdb = postgres(str_connect={config.get('settings', {}).get('postgres_connect_string')})
    record_ids = objdb.get_fob_records()
    for record_id in record_ids:
        print('Record ID:', record_id)
        # ** Implement list comprehension logic ***** TO DO
        urls = config['settings']['urls']
        for url in urls:
            obj_ACL = AccessControlList({config.get('settings', {}).config.get('username')}, {config.get('settings', {}).get('password')}, url)
            response = obj_ACL.navigate(data)
            if response.status_code == 200:
                for x in range(0, 20):
                    try:
                        lst_perms = obj_ACL.get_permissions_record(record_id[0])
                        # Insert into database
                        if lst_perms:
                            [objdb.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
                            # time.sleep(1)
                            break
                        else:  # Record not returned, need to try to pull again
                            print('Iteration: ', x, '...Reconnecting')
                            time.sleep(1)
                            response = obj_ACL.navigate(data)
                    except:
                        raise
            del obj_ACL

if __name__ == '__main__':
    main()