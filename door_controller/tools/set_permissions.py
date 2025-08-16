import sys
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version

def main(url, fob_id, permissions):
    """Main function for 'update_controller'."""
    log_info(f"--- Starting update_controller (v{__version__}) at {get_current_timestamp()} ---")

    # Accessing command-line arguments for config path
    args = sys.argv[1:]
    if args:
        log_info(f"Received arguments: {args}")

    # Using common utility to load config
    config = load_config(args[0])  # Uses default or APP_CONFIG_DIR env var
    if config:
        log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
        log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    else:
        log_info("No config loaded.")

    log_info("Extracting Access List from Door Controller")
    data = {'username': config.get('username'),
            'pwd': config.get('password'),
            'logid': '20101222'}

    objdb = postgres(config.get('settings', {}).get('postgres_connect_string'))
    # for url in config.get('urls'):
    record_id = objdb.get_record_id(url, fob_id)
    objcontroller = door_controller(url, config.get('username'), config.get('password'))
    objcontroller.set_permissions(data, record_id, permissions)


if __name__ == 'main':
    # Permissions is a tuple of 1 or more permissions tuples of the form [Door #, FobID]:
    url = ''
    fob_id =  9999999
    permissions = [{1:'Allow'},{2:'Deny'}]
    main(url, fob_id, permissions)