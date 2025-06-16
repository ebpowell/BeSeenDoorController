import sys
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
                                            {config.get('settings', {}).get('password')}, url, run_time)
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

def get_acl_list(url, config, objdb, mode = 'All'):
    try:
        # Wth users list in place, query users and controllers, pull ACL record
        records = objdb.get_fob_records(url)
        for record in records:
            try:
                get_permissions(config, record, objdb, url)
                time.sleep(10)
            except requests.exceptions.Timeout:
                log_info(F"""Record ID {record[0]} Skipped""")
            except:
                raise
    except Exception as e:
        raise e

def get_users_list(url, config, objdb, mode='All'):
    try:
        obj_ACL = AccessControlList({config.get('settings', {}).get('username')},
                                    {config.get('settings', {}).get('password')}, url, run_time)
        # Get the maximum number of users from the door controller
        record_count = obj_ACL.get_users_count()
        print(F"""Maximum Users: {record_count}""")
        max_record_id = obj_ACL.get_max_record_id()
        del obj_ACL
        # Get the record_start id from the database
        rec_id_start = objdb.get_max_fob_id(url)
        print(F"""Record_id_start:{rec_id_start}, Max Record ID:{max_record_id}, Record Count: {record_count}""")
        x = 0
        while rec_id_start < max_record_id:
            x += 1
            obj_ACL = AccessControlList({config.get('settings', {}).get('username')},
                                        {config.get('settings', {}).get('password')}, url, run_time)
            obj_ACL.get_users(rec_id_start, {config.get('settings', {}).get('batch_size')}, objdb)
            del obj_ACL
            rec_id_start = objdb.get_max_fob_id(url)
            print(F"""Main Rec_ID_Start:{rec_id_start}, Iteration:{x}""")
            time.sleep(5)
    except Exception as e:
        raise e


def main(mode='All'):
    # Get a timestamp for all records
    run_timne = datetime.datetime.now()
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
    if mode == 'All':
        objdb.purge_controller_fobs_slop()
        objdb.purge_acl_slop()
    urls = config['settings']['urls']
    for url in urls:
        try:
            get_users_list(url, config, objdb, mode, run_time)
            time.sleep(10)
            # get_acl_list(url, config, objdb, mode, run_time)
        except Exception as e:
            raise e


if __name__ == '__main__':
    # mode = sys.argv[0]
    mode = 'Add'
    try:
        main(mode)
    except:
        raise
