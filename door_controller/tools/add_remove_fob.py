import sys
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version

def main(mode, url, fob_id):
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

    # objdb = postgres(config.get('settings', {}).get('postgres_connect_string'))
    # for url in config.get('urls'):
        objcontroller = door_controller(url, config.get('username'), config.get('password'))
        if mode == 1:
            objcontroller.add_fob(fob_id)
        else:
            objcontroller.del_fob(fob_id)

if __name__ == 'main':
    mode  = 1
    fob_id = 123456
    url = ''
    main(mode, url, fob_id)