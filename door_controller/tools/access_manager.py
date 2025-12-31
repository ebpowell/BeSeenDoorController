import sys
import datetime
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.utils import log_info, get_current_timestamp, load_config, render_output
from door_controller import __version__ # Access package version
from door_controller.common_lib.pg_database import postgres



class ManageFobs:
    def __init__(self):
        self.config = load_config()
        if self.config:
            log_info(f"Loaded config app_name: {self.config.get('app_name', 'N/A')}")
            log_info(f"Configured log_level: {self.config.get('settings', {}).get('log_level', 'N/A')}")
        else:
            log_info("No config loaded.")
        self.urls = self.config['settings']['urls']
        self.username = self.config['settings']['username']
        self.password = self.config['settings']['password']
        self.db = postgres(self.config['settings']['postgres_connect_string'])

    def _add_remove_fob(self, mode, fob_id, user_name):
        log_info("Adding/Removing Fob from Door Controller")
        urls = self.config['settings']['urls']
        for url in urls:
            objDataManager = DataManager(url, self.username, self.password)
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

    def add_fob(self, fob_id, user_name):
        log_info(f"Adding Fob {fob_id}")
        try:
            self._add_remove_fob(1, fob_id, user_name)
        except Exception as e:
            raise e


    def remove_fob(self, fob_id, user_name):
        log_info(f"Removing Fob {fob_id}")
        try:
            self._add_remove_fob(0, fob_id, user_name = None)
        except Exception as e:
            raise e
    
    def _get_db_permissions(self):
        log_info(f"Getting permissions from database")
        try:
            ...
        except Exception as e:
            raise e
        
    def _get_record_id_from_controller(self, target_fob_id):
        """
        Fetches fobs from controller and finds the record_id for the given fob_id.
        Returns record_id as string (or tuple if expected by set_permissions), or None.
        """
        data_manager = DataManager(self.url, self.username, self.password)
        log_info(f"Looking up Record ID for Fob {target_fob_id}...")
        # Fetch first few pages (iteration=5 means 4 pages? check code)
        # get_keyfobs returns a list of lists: [record_id, fob_id, cidr, time]
        fobs = data_manager.get_keyfobs(target_fob_id)
        if fobs:
            for fob in fobs:
                # fob[0] is record_id, fob[1] is fob_id
                if str(fob[1]) == str(target_fob_id):
                    log_info(f"Found Fob {target_fob_id} at Record ID {fob[0]}")
                    return int(fob[0])
        return None

    def _set_fob_permissions(self, fob_id, permissions):
        log_info(f"Setting permissions")
        # try:
        record_id = self._get_record_id_from_controller(fob_id)
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
        # except Exception as e:
        #     raise e
        # return permissions

    def set_permissions(self):
        log_info(f"Setting Controller permissions")
        try:
            for record in self._get_db_permissions():
                fob_id = record['fob_id']
                permissions = record['permissions']
                self._set_fob_permissions(fob_id, permissions)
        except Exception as e:
            raise e

    def sync_permissions():
        # Connect to your Postgres DB
        # conn = psycopg2.connect("dbname=locks user=admin")
        # cur = conn.cursor()

        while True:
            # 1. Identify permissions that SHOULD be active but AREN'T
            cur.execute("""
                SELECT fob_id, lock_id FROM access_rules 
                WHERE NOW() BETWEEN start_time AND end_time 
                AND current_state = FALSE
            """)
            to_activate = cur.fetchall()
            for fob, lock in to_activate:
                if send_to_microcontroller(fob, lock, "ALLOW"):
                    cur.execute("UPDATE access_rules SET current_state = TRUE WHERE fob_id = %s", (fob,))

            # 2. Identify permissions that HAVE EXPIRED but are still active on MCU
            cur.execute("""
                SELECT fob_id, lock_id FROM access_rules 
                WHERE (NOW() < start_time OR NOW() > end_time)
                AND current_state = TRUE
            """)
            to_deactivate = cur.fetchall()
            for fob, lock in to_deactivate:
                if send_to_microcontroller(fob, lock, "DENY"):
                    cur.execute("UPDATE access_rules SET current_state = FALSE WHERE fob_id = %s", (fob,))

            conn.commit()
            time.sleep(60) # Run check every minute