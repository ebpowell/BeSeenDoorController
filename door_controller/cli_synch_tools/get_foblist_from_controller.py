
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__ # Access package version

def main():

    """Main function for 'get_recent_swipes'."""
    log_info(f"--- Starting get_system_fob_list (v{__version__}) at {get_current_timestamp()} ---")

    # # Accessing command-line arguments for config path
    # args = sys.argv[1:]
    # if args:
    #     log_info(f"Received arguments: {args}")

    # Using common utility to load config
    config = load_config()  # Uses default or APP_CONFIG_DIR env var
    if config:
        log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
        log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    else:
        log_info("No config loaded.")
        raise

    log_info("Extracting FobID records from Door Controller")

    obj_db = postgres(config.get('settings', {}).get('postgres_connect_string'))
    # Intialize the slop table for the new records
    obj_db.insert_swipe_start_record()
    urls = config['settings']['urls']
    for url in urls:
        obj_extract = ww_data_extractor({config.get('settings', {}).get('username')},
                                        {config.get('settings', {}).get('password')}, url, obj_db)
        # Add records from controller
        obj_extract.get_system_fob_list()
        # Move the records from the slop table to the door controller table
        obj_db.move_fob_records()

if __name__=='__main__':
    ''' 
    Tool to pull all of the FobIDs from the Door controller to check alignment with 
    official dataset
    '''

    main()