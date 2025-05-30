import sys
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version

def main():
    # username = "abc"
    # password = "654321"
    # urls = ["http://69.21.119.147", "http://69.21.119.148"]
    # str_connect = "host=192.168.50.150 dbname=wntworth_db user=wentworth_user password=ww_s3cret"

    """Main function for 'get_recent_swipes'."""
    log_info(f"--- Starting get_recent_swipes (v{__version__}) at {get_current_timestamp()} ---")

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

    obj_db = postgres(config.get('postgres_connect_string'))
    # Intialize the slop table for the new records
    obj_db.insert_swipe_start_record()
    for url in config.get('urls'):
        obj_extract = ww_data_extractor(config.get('username'), config.get('password'), url, obj_db)
        # Add records from controller
        obj_extract.get_recent_fob_swipes()
    # Copy records from slop table to the main table.
    obj_db.add_new_swipess()

if __name__=='__main__':
    '''
    Tool to periodically pull all of the swipes off of the door controllers at the Wentworth Clubhouse
    Designed to be run by the cron at whatever period is more appropriate (probably hourly)
    '''
    main()
