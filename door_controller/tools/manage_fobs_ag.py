import sys
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config, render_output
from door_controller import __version__ # Access package version

def main(mode, fob_id, user_name):
    """Main function for 'update_controller'."""
    log_info(f"--- Starting update_controller (v{__version__}) at {get_current_timestamp()} ---")

    # Accessing command-line arguments for config path
    args = sys.argv[1:]
    if args:
        log_info(f"Received arguments: {args}")
        mode = args[0]
        fob_id = args[1]
        user_name = args[2] 
    else:
        log_info("No arguments received.")
        # raise
        pass

    # Using common utility to load config
    config = load_config()  # Uses default or APP_CONFIG_DIR env var
    if config:
        log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
        log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    else:
        log_info("No config loaded.")

    log_info("Extracting Access List from Door Controller")
    # data = {'username': config.get('username'),
    #         'pwd': config.get('password'),
    #         'logid': '20101222'}

    # objdb = postgres(config.get('settings', {}).get('postgres_connect_string'))
    urls = config['settings']['urls']
    for url in urls:
        objDataManager = DataManager(url, config.get('username'), config.get('password'))
        try:
            if mode == 1:
                response = objDataManager.add_fob(fob_id, user_name)
            else:
                response = objDataManager.del_fob(fob_id)
            decoded_text = ""
            try:
                decoded_text = response.content.decode('utf-8')
                print("\n------- SERVER RESPONSE (decoded as UTF-8) -------")
                decoded_text = decoded_text.replace('\0', '')
                print(decoded_text)
                # render_output(decoded_text)
                # print("-------------------------------------------------")

            except UnicodeDecodeError:
                # If utf-16 fails, just print the raw bytes so we can see them
                print("\nUTF-8 decoding failed. Printing raw response content:")
                print(response.content)
                print("-------------------------------------------------")
                print("\nDEBUG: Raw content printed above. Please check it for clues.")
                # Exit or return here, as further checks will fail
                exit()
        except Exception as e:
            raise e

if __name__ == '__main__':
    mode  = 1
    #fob_id = '0002725269'
    fob_id = '0001234567'
    user_name = 'Eddie'
    # url = ''
    try:
        main(mode,  fob_id, user_name)
    except Exception as e:
        raise e