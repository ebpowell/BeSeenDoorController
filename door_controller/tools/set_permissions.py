import sys
from door_controller.common_lib.manage_fobs import DataManager
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__

def get_record_id_from_controller(data_manager, target_fob_id):
    """
    Fetches fobs from controller and finds the record_id for the given fob_id.
    Returns record_id as string (or tuple if expected by set_permissions), or None.
    """
    log_info(f"Looking up Record ID for Fob {target_fob_id}...")
    # Fetch first few pages (iteration=5 means 4 pages? check code)
    # get_keyfobs returns a list of lists: [record_id, fob_id, cidr, time]
    fobs = data_manager.get_keyfobs(3) 
    if fobs:
        for fob in fobs:
            # fob[0] is record_id, fob[1] is fob_id
            if str(fob[1]) == str(target_fob_id):
                log_info(f"Found Fob {target_fob_id} at Record ID {fob[0]}")
                return int(fob[0])
    return None

def main(url, fob_id, permissions):
    log_info(f"--- Starting set_permissions (v{__version__}) ---")
    
    # Load Config (simplified)
    config = load_config()
    if not config:
        log_info("No config loaded.")
        return

    username = config['settings']['username']
    password = config['settings']['password']
    
    if not url:
        urls = config['settings']['urls']
        url = urls[0] # Default to first

    # Initialize DataManager
    data_manager = DataManager(url, username, password)
    
    # Login (Authenticate) - Implicitly handled by set_permissions logic? 
    # Wait, set_permissions calls obj_fob.navigate(data) -> connect(data).
    # But add_fob failed because it didn't authenticate. 
    # set_permissions implementation creates NEW key_fobs instance:
    # obj_fob = key_fobs(self.username, self.password, self.url)
    # response = obj_fob.navigate(data)
    # navigate calls connect. So it SHOULD be fine if data contains credentials.
    
    login_data = {'username': username, 'pwd': password, 'logid': '20101222'}
    
    # Find Record ID
    record_id = get_record_id_from_controller(data_manager, fob_id)
    if not record_id:
        log_info(f"Could not find Record ID for Fob {fob_id}")
        sys.exit(1)

    # set_permissions expects record_id as a tuple/list? 
    # Code: lst_perms = obj_fob.get_permissions_record(record_id[0])
    # So yes, it expects a list/tuple where [0] is the ID.
    record_id_wrapper = [record_id]

    # Call set_permissions
    # Note: connect(data) is called inside via navigate(data), but we need to pass login_data as 'data' arg?
    # verify signature: def set_permissions(self, data, record_id, dct_permissions):
    result = data_manager.set_permissions(login_data, record_id_wrapper, permissions)
    
    if result and result.status_code == 200:
        log_info("Permissions set successfully.")
    else:
        log_info("Failed to set permissions.")

if __name__ == '__main__':
    # Test values
    # url = '' 
    fob_id = 2725269 # The ID we know exists from previous step
    permissions = [] # Not really used in the current hardcoded set_permissions implementation, but required arg
    main(None, fob_id, permissions)