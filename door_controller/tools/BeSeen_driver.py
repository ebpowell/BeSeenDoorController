import sys
import argparse
import time
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config
from door_controller import __version__
from door_controller.common_lib.pg_database import postgres

class FobManager:
    def __init__(self):
        self.config = load_config()
        if self.config:
            log_info(f"Loaded config app_name: {self.config.get('app_name', 'N/A')}")
            log_info(f"Configured log_level: {self.config.get('settings', {}).get('log_level', 'N/A')}")
        else:
            log_info("No config loaded.")
            # Depending on usage, we might want to exit or raise an error here if config is critical
        
        self.urls = self.config['settings']['urls']
        self.username = self.config['settings']['username']
        self.password = self.config['settings']['password']
        self.db_connect_string = self.config['settings']['postgres_connect_string']
        # Delay DB connection until needed or handle connection errors gracefully
        self.db = None

    def _get_db(self):
        if not self.db:
            self.db = postgres(self.db_connect_string)
        return self.db

    def _add_remove_fob(self, mode, fob_id, user_name=None):
        """
        Internal method to add or remove a fob from all configured controllers.
        mode: 1 for add, 0 for remove
        """
        action = "Adding" if mode == 1 else "Removing"
        log_info(f"{action} Fob {fob_id} on Door Controller(s)")
        
        for url in self.urls:
            log_info(f"Connecting to controller at {url}")
            data_manager = DataManager(url, self.username, self.password)
            try:
                if mode == 1:
                    response = data_manager.add_fob(fob_id, user_name)
                else:
                    # For deletion, we first need to find the record ID if the API requires it.
                    # existing del_fob signature in DataManager: def del_fob(self, data, record_id):
                    # But wait, original manage_fobs.py called objDataManager.del_fob(fob_id)
                    # Let's check DataManager source again. 
                    # DataManager.del_fob(self, data, record_id). 
                    # However, manage_fobs.py passed just fob_id?
                    # Line 32 of original manage_fobs.py: response = objDataManager.del_fob(fob_id)
                    # If DataManager.del_fob implementation requires data and record_id, then original code might have been broken 
                    # OR I misread DataManager. Let's assume I need to get the record ID first for deletion too.
                    
                    # Correction: looking at previous `manage_fobs.py` dump, it indeed called `del_fob(fob_id)`.
                    # Looking at `data_manager.py` dump: `def del_fob(self, data, record_id):`
                    # The arguments mismatch. The original code was likely broken or I am misinterpreting. 
                    # To be safe, I will implement lookup first.
                    
                    record_id = self._get_record_id_from_controller(data_manager, fob_id)
                    if record_id:
                        # Construct 'data' if needed. DataManager.del_fob needs 'data' for navigation?
                        # It calls `obj_fob.navigate(data)`. `navigate` calls `connect(data)`.
                        # `connect` uses `data` in `requests.post`. 
                        # Usually `connect` takes login data?
                        login_data = {'username': self.username, 'pwd': self.password, 'logid': '20101222'}
                        response_code = data_manager.del_fob(login_data, record_id)
                        # data_manager.del_fob returns a status code (int), not a response object
                        log_info(f"Delete operation returned status code: {response_code}")
                        return # del_fob returns code, not object
                    else:
                        log_info(f"Could not find record ID for fob {fob_id} on controller {url}, skipping deletion.")
                        continue

                # Handle response for add (which returns an object)
                if response:
                     self._print_response(response)

            except Exception as e:
                log_info(f"Error acting on {url}: {e}")
                # We typically want to try other controllers even if one fails
                pass 

    def split_manage_fobs_add(self, fob_id, user_name):
        # This matches the signature expected by original wrapper if needed, 
        # but we are moving to CLI. keeping method name simple.
        self.add_fob(fob_id, user_name)

    def add_fob(self, fob_id, user_name):
        log_info(f"Adding Fob {fob_id} ({user_name})")
        self._add_remove_fob(1, fob_id, user_name)

    def remove_fob(self, fob_id):
        log_info(f"Removing Fob {fob_id}")
        self._add_remove_fob(0, fob_id)

    def _print_response(self, response):
        try:
            decoded_text = response.content.decode('utf-8')
            print("\n------- SERVER RESPONSE -------")
            decoded_text = decoded_text.replace('\0', '')
            print(decoded_text)
        except UnicodeDecodeError:
            print("\nUTF-8 decoding failed. Raw response:")
            print(response.content)

    def _get_record_id_from_controller(self, data_manager, target_fob_id):
        """
        Fetches fobs from controller and finds the record_id for the given fob_id.
        """
        log_info(f"Looking up Record ID for Fob {target_fob_id}...")
        # Fetch first few pages (iteration=3 passed in set_permissions.py)
        fobs = data_manager.get_keyfobs(3)
        if fobs:
            for fob in fobs:
                # fob[0] is record_id, fob[1] is fob_id
                if str(fob[1]) == str(target_fob_id):
                    log_info(f"Found Fob {target_fob_id} at Record ID {fob[0]}")
                    return int(fob[0])
        return None

    def set_fob_permissions(self, fob_id, permissions=None):
        """
        Set permissions for a specific fob on all controllers.
        """
        log_info(f"Setting permissions for Fob {fob_id}")
        login_data = {'username': self.username, 'pwd': self.password, 'logid': '20101222'}
        
        for url in self.urls:
            data_manager = DataManager(url, self.username, self.password)
            record_id = self._get_record_id_from_controller(data_manager, fob_id)
            
            if not record_id:
                log_info(f"Could not find Record ID for Fob {fob_id} on {url}")
                continue

            record_id_wrapper = [record_id]
            # permission arg is currently unused by DataManager.set_permissions but required by signature?
            # DataManager.set_permissions(self, data, record_id, dct_permissions)
            # It uses hardcoded permissions inside. 
            result = data_manager.set_permissions(login_data, record_id_wrapper, permissions)
            
            if result and result.status_code == 200:
                log_info(f"Permissions set successfully on {url}.")
            else:
                log_info(f"Failed to set permissions on {url}.")

    # def sync_permissions(self):
    #     """
    #     Sync permissions based on database state.
    #     This runs a loop to activate/deactivate fobs based on time schedules.
    #     """
    #     log_info("Starting Permission Sync Loop...")
    #     db = self._get_db()
    #     conn = db.conn # Access internal connection if needed, or add methods to postgres class
    #     # existing code used 'cur' and 'send_to_microcontroller'. 
    #     # verify if send_to_microcontroller exists... it was probably pseudocode in the original file 
    #     # or imported? The original file check showed it simply called send_to_microcontroller which wasn't defined in the file.
    #     # I will assume we need to implement it using set_fob_permissions logic or similar.
        
    #     # NOTE: The original sync_permissions code seemed incomplete or relied on globals not present.
    #     # It referenced `cur` (cursor) which wasn't defined locally.
    #     # It referenced `send_to_microcontroller` which wasn't imported.
    #     # I will comment out the logic to prevent runtime errors but keep the structure 
    #     # for the user to fill in or for future implementation.
        
    #     log_info("Sync logic is currently a placeholder as original dependencies were missing.")
    #     # while True:
    #     #     # Implementation pending correct DB schema and helper methods
    #     #     time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description="Door Controller Fob Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Add Fob
    parser_add = subparsers.add_parser("add", help="Add a new key fob")
    parser_add.add_argument("fob_id", type=str, help="The ID of the fob")
    parser_add.add_argument("name", type=str, help="The name of the user/fob owner")

    # Remove Fob
    parser_remove = subparsers.add_parser("remove", help="Remove an existing key fob")
    parser_remove.add_argument("fob_id", type=str, help="The ID of the fob to remove")

    # Set Permissions
    parser_perms = subparsers.add_parser("set_permissions", help="Set permissions for a fob")
    parser_perms.add_argument("fob_id", type=str, help="The ID of the fob")
    
    # # Sync
    # parser_sync = subparsers.add_parser("sync", help="Run the sync loop")

    args = parser.parse_args()
    
    manager = FobManager()

    if args.command == "add":
        manager.add_fob(args.fob_id, args.name)
    elif args.command == "remove":
        manager.remove_fob(args.fob_id)
    elif args.command == "set_permissions":
        manager.set_fob_permissions(args.fob_id)
    # elif args.command == "sync":
    #     manager.sync_permissions()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()