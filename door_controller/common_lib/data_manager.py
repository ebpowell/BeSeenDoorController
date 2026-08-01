import os
from time import sleep
from door_controller.common_lib.fobs import key_fobs

class DataManager(key_fobs):
    def __init__(self, url, username, password, retries=3, retry_sleep=None):
        super().__init__(url, username, password)
        self.max_retries = retries
        if retry_sleep is None:
            try:
                from door_controller.common_lib.utils import load_config
                config = load_config()
                self.retry_sleep = config.get('settings', {}).get('retry_sleep_seconds', 1)
            except Exception:
                self.retry_sleep = 1
        else:
            self.retry_sleep = retry_sleep

    def add_fob(self, fob_id, name):
        response = self.navigate()
        if response and response.status_code == 200:
            url = self.url + '/ACT_ID_21'
            data = {'s1': 'AddCard'}
            self.session.headers['Referer'] = self.url + '/ACT_ID_1'
            response = self.get_httpresponse(url, data)
            if response and response.status_code == 200:
                url_add = self.url + '/ACT_ID_312'
                str_fobid = str(fob_id)
                # AD21=123456&AD22=Test&25=Add
                add_data = [('AD21', str_fobid),
                            ('AD22', name),
                            ('25', 'Add')]
                self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                for i in range(self.max_retries):
                    the_code = self.get_httpresponse(url_add, add_data)
                    if the_code:
                        if the_code.status_code == 200:
                            # Print warnings for developer debugging
                            if "Login" in the_code.text or "session" in the_code.text:
                                print("\nDEBUG: The response HTML mentions 'Login' or 'session'.\n")
                                rec_id = None
                            elif "Invalid" in the_code.text or "Error" in the_code.text:
                                print(f"\nDEBUG: The response HTML contains an error message.\n")
                                rec_id = None
                            else:
                                print(f"\nDEBUG: The response HTML does not contain any obvious error messages.\n")
                                rec_id = self.get_record_id(fob_id)
                        return [the_code, rec_id]
                    else:
                        sleep(self.retry_sleep)
                        if i < self.max_retries - 1:
                            print(f"Retrying add_fob... Attempt {i + 2} of {self.max_retries}")
                        else:
                            print("Max retries reached. Failed to add fob.")
                return None
        return None

    def set_permissions(self, lst_permissions, record_id):
        # Support both record_id as integer or list/tuple of integer
        if isinstance(record_id, (list, tuple)):
            rec_id = record_id[0]
        else:
            rec_id = record_id
        
        rec_id = int(rec_id)
        self.navigate()
        
        url = self.url + '/ACT_ID_324'
        edit_key = f"E{rec_id - 1}"
        edit_data = {edit_key: 'Edit'}
        
        self.session.headers['Referer'] = self.url + '/ACT_ID_21'
        # USX106=0&24=1&25=1&26=1&27=1&S106=Save
        for i in range(self.max_retries):
            response = self.get_httpresponse(url, edit_data)
            if not response:
                sleep(self.retry_sleep)
                if i < self.max_retries - 1:
                    print(f"Retrying set_permissions... Attempt {i + 2} of {self.max_retries}")
                else:
                    print("Max retries reached. Failed to set permissions.")
            else:
                if response.status_code == 200:
                    if isinstance(lst_permissions, dict):
                        perms_iterable = lst_permissions.items()
                    else:
                        perms_iterable = lst_permissions
                        
                    dct_doors = {1: '24', 2: '25', 3: '26', 4: '27'}
                    # 1. Initialize all 4 doors to a default '0' (disabled/disallowed)
                    current_door_vals = {field: '0' for field in dct_doors.values()}
                    
                    # 2. Update with the explicitly provided permissions
                    for door_no, allow in perms_iterable:
                        door_field = dct_doors.get(int(door_no))
                        if door_field:
                            val = '1' if (allow is True or str(allow) in ('1', 'True', 'Allow', 'allow')) else '0'
                            current_door_vals[door_field] = val
                            
                    # 3. Build the save_data array strictly ordered by door field IDs
                    save_data = [(field, current_door_vals[field]) for field in ('24', '25', '26', '27')]
                    
                    # 4. Prepend the US Key
                    save_data.insert(0,[f"USX{rec_id - 1}",''])
                    #5. Appned the Save
                    save_key = f"S{rec_id - 1}"
                    save_data.append((save_key, 'Save'))
                    self.session.headers['Referer'] = self.url + '/ACT_ID_324'
                    response = self.get_httpresponse(url, save_data)
                return response
        return None

    def del_fob(self, fob_id):
        response = self.navigate()
        if response and response.status_code == 200:
            try:
                url = self.url + '/ACT_ID_324'
                record_id = self.get_record_id(fob_id)
                if record_id is None:
                    print(f"Could not find record ID for fob ID {fob_id}.") 
                    return 200
                the_number = record_id - 1
                key = f"D{the_number}"
                del_data = {key: 'Delete'}
                
                for i in range(self.max_retries):
                    the_code = self.get_httpresponse(url, del_data)
                    if the_code: # Check for valid response from server
                        if the_code.status_code == 200:
                            ok_key = f"X{the_number}"
                            ok_data = {ok_key: 'OK'}
                            the_code = self.get_httpresponse(url, ok_data)
                        return the_code.status_code
                    else: # Null response from server
                        sleep(self.retry_sleep)
                        if i < self.max_retries - 1:
                            print(f"Retrying del_fob... Attempt {i + 2} of {self.max_retries}")
                        else:
                            print("Max retries reached. Failed to delete fob.")
            except Exception as e:
                print(f"Error occurred while deleting fob with ID {fob_id}.")
                raise e
            return None
        return None

