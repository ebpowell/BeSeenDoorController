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
        # Authenticate first
        login_data = {'username': self.username,
                      'pwd': self.password,
                      'logid': '20101222'}
        self.connect(login_data)

        data = {'s1': 'AddCard'}
        url = self.url + '/ACT_ID_21'
        for i in range(self.max_retries):
            response = self.get_httpresponse(url, data)
            if not response:
                sleep(self.retry_sleep)
                if i < self.max_retries - 1:
                    print(f"Retrying add_fob... Attempt {i + 2} of {self.max_retries}")
                else:
                    print("Max retries reached. Failed to add fob.")
            else:
                if response.status_code == 200:
                    print("Connected to server successfully. Proceeding to add fob.")
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    url = self.url + '/ACT_ID_312'
                    str_fobid = str(fob_id)
                    data = [('AD21', str_fobid),
                            ('AD22', name),
                            ('25', 'Add')]
                    response = self.get_httpresponse(url, data)
                    
                    if response:
                        # Print warnings for developer debugging
                        if "Login" in response.text or "session" in response.text:
                            print("\nDEBUG: The response HTML mentions 'Login' or 'session'.\n")
                        elif "Invalid" in response.text or "Error" in response.text:
                            print(f"\nDEBUG: The response HTML contains an error message.\n")
                            
                return response
        return None

    def set_permissions(self, lst_permissions, record_id):
        # Support both record_id as integer or list/tuple of integer
        if isinstance(record_id, (list, tuple)):
            rec_id = record_id[0]
        else:
            rec_id = record_id
        
        rec_id = int(rec_id)
        
        login_data = {
            'username': self.username,
            'pwd': self.password,
            'logid': '20101222'
        }
        self.connect(login_data)
        self.users_page()
        
        url = self.url + '/ACT_ID_324'
        edit_key = f"E{rec_id - 1}"
        edit_data = {edit_key: 'Edit'}
        
        self.session.headers['Referer'] = self.url + '/ACT_ID_21'
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
                    save_data = []
                    for door_no, allow in perms_iterable:
                        door_field = dct_doors.get(int(door_no))
                        if door_field:
                            val = '1' if (allow is True or str(allow) in ('1', 'True', 'Allow', 'allow')) else '0'
                            save_data.append((door_field, val))
                            
                    save_key = f"S{rec_id - 1}"
                    save_data.append(('USXo', ''))
                    save_data.append((save_key, 'Save'))
                    
                    self.session.headers['Referer'] = self.url + '/ACT_ID_324'
                    response = self.get_httpresponse(url, save_data)
                return response
        return None

    def del_fob(self, data, record_id):
        # Authenticate first
        self.connect(data)
        self.users_page()

        url = self.url + '/ACT_ID_324'
        the_number = record_id - 1
        key = f"D{the_number}"
        del_data = {key: 'Delete'}
        
        self.session.headers['Referer'] = self.url + '/ACT_ID_21'
        for i in range(self.max_retries):
            response = self.get_httpresponse(url, del_data)
            if not response:
                sleep(self.retry_sleep)
                if i < self.max_retries - 1:
                    print(f"Retrying del_fob... Attempt {i + 2} of {self.max_retries}")
                else:
                    print("Max retries reached. Failed to delete fob.")
            else:
                if response.status_code == 200:
                    self.session.headers['Referer'] = self.url + '/ACT_ID_324'
                    ok_key = f"X{the_number}"
                    ok_data = {ok_key: 'OK'}
                    response = self.get_httpresponse(url, ok_data)
                    
                return response.status_code if response else None
        return None
