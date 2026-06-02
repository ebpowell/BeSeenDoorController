import os
from door_controller.common_lib.fobs import key_fobs

class DataManager(key_fobs):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)
        self.max_retries = 1

    def add_fob(self, fob_id, name):
        # obj_fob = key_fobs(self.url, self.username, self.password)
        self.max_retries = 1
        
        # Authenticate first
        login_data = {'username': self.username,
                      'pwd': self.password,
                      'logid': '20101222'}
        self.connect(login_data)

        data = {'s1':'AddCard'}
        url = self.url + '/ACT_ID_21'
        response = self.get_httpresponse(url, data)
        if response.status_code == 200:
            print("Response from server:")
            print(response.text)
            self.session.headers['Referer'] = self.url + '/ACT_ID_21'
            url = self.url+'/ACT_ID_312'
            # ACT_ID_312
            # Assuming UserID 99999, Username 'Test'
            str_fobid = str(fob_id)
            data = [('AD21', str_fobid),
                    ('AD22', name),
                    ('25', 'Add')]
            #Call response object
            print(data)
            response=self.get_httpresponse(url, data)
            # print("Response from server:")
            print(response.text)  # Print the HTML response from the server
            if "Login" in response.text or "session" in response.text:
                print("\nDEBUG: The response HTML mentions 'Login' or 'session'.")
                print("This strongly suggests you need to log in first. See step 2.")
            elif "Invalid" in response.text or "Error" in response.text:
                print(f"\nDEBUG: The response HTML contains an error message. Please read the HTML above.")
        return response


    def set_permissions(self, lst_permissions, record_id):
        # Support both record_id as integer or list/tuple of integer
        if isinstance(record_id, (list, tuple)):
            rec_id = record_id[0]
        else:
            rec_id = record_id
        
        rec_id = int(rec_id)
        
        # Authenticate first
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
        response = self.get_httpresponse(url, edit_data)
        if not response or response.status_code != 200:
            return response
            
        # Compile permission fields
        # Support dict format or list format
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

    def del_fob(self, data, record_id):
        obj_fob = key_fobs(self.url, self.username, self.password)
        response = obj_fob.navigate(data)
        if response.status_code==200:
            url = self.url +'/ACT_ID_324'
            the_number = record_id -1
            key = F"D{the_number}"
            data = {key:'Delete'}
            # Call response
            the_code = self.get_httpresponse(url, data)
            if the_code.status_code == 200:
                ok_key = F"X{the_number}"
                data= {ok_key:'OK'}
                #Call response
                the_code = self.get_httpresponse(url, data)
            return the_code.status_code