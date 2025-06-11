import time
import requests
from door_controller.common_lib.access_control_list import AccessControlList
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import log_info, load_config


def get_permissions(config, record, objdb, url):
    try:
        lst_perms = None
        while not lst_perms:
            try:
                obj_ACL = AccessControlList({config.get('settings', {}).get('username')},
                                            {config.get('settings', {}).get('password')}, url)
                lst_perms = obj_ACL.get_permissions_record(int(record[0]))
                del obj_ACL
            except requests.exceptions.Timeout as e:
                del obj_ACL
                raise e
            except requests.exceptions.ConnectionError as e:
                del obj_ACL
                raise e
        [objdb.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
    except:
        raise


def main():
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

    objdb = postgres(config.get('settings', {}).get('postgres_connect_string'))
    urls = config['settings']['urls']
    for url in urls:
        obj_ACL = AccessControlList({config.get('settings', {}).get('username')},
                                    {config.get('settings', {}).get('password')}, url)
        # Get the maximum number of users from the door controller
        max_record = obj_ACL.get_max_users()
        del obj_ACL
        # Get the record_start id from the database
        rec_id_start = objdb.get_max_fob_id(url)
        if not rec_id_start:
            rec_id_start = 1
        iterations = int((max_record - rec_id_start) / 20)
        for x in range(1, iterations):
            obj_ACL = AccessControlList({config.get('settings', {}).get('username')},
                                        {config.get('settings', {}).get('password')}, url)
            obj_ACL.get_users(rec_id_start, {config.get('settings', {}).get('batch_size')}, objdb)
            del obj_ACL
            # Wth users list in place, query users and controllers, pull ACL record
            # objdb.purge_acl_slop()
            # records = objdb.get_fob_records(url)
            # for record in records:
            #     try:
            #         get_permissions(config, record, objdb, url)
            #         time.sleep(15)
            #     except requests.exceptions.Timeout:
            #         log_info(F"""Record ID {record[0]} Skipped""")
            #     except:
            #         raise
            time.sleep(60)

if __name__ == '__main__':
    try:
        main()
    except:
        raise
