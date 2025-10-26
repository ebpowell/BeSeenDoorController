import os
from door_controller.common_lib.fobs import key_fobs

class DataManager(key_fobs):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)

    def add_fob(self, fob_id, name):
        # obj_fob = key_fobs(self.url, self.username, self.password)
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
            data = {'25':'Add',
                    'AD21':str(fob_id),
                    'AD22':name}
            #Call response object
            response=self.get_httpresponse(url, data)
            # print("Response from server:")
            print(response.text)  # Print the HTML response from the server
            if "Login" in response.text or "session" in response.text:
                print("\nDEBUG: The response HTML mentions 'Login' or 'session'.")
                print("This strongly suggests you need to log in first. See step 2.")
            elif "Invalid" in response.text or "Error" in response.text:
                print(f"\nDEBUG: The response HTML contains an error message. Please read the HTML above.")
        return response


    def set_permissions(self, data, record_id, dct_permissions):
        url = self.url + '/ACT_ID_324'
        # TO DO: Map Door / Controller combos to numeric values on Edit page
        dct_doors = {1:24, 2:25, 3:26, 4:27}
        dct_perms = {'Allow':1, 'Forbid':0}
        obj_fob = key_fobs(self.username, self.password, self.url)
        response = obj_fob.navigate(data)
        # Look up the Fob_ID
        if response.status_code == 200:
            for x in range(0, 20):
                try:
                    lst_perms = obj_fob.get_permissions_record(record_id[0])
                    # Insert into database
                    if lst_perms:
                        edit_record = f"E{record_id[0] - 1}"
                        save_record = f"S{record_id[0]-1}"
                        data = {edit_record:'Edit'}
                        #Call response object
                        response = self.get_httpresponse(url, data)
                        if response==200:
                            data = {24:"0",
                                    25:"0",
                                    26:"1",
                                    27:"1",
                                    "USXo":"",
                                    save_record:'Save'}
                            response=self.get_httpresponse(url, data)
                            return response

                except Exception as e:
                    raise e

    def del_fob(self, data, record_id):
        obj_fob = key_fobs(self.username, self.password, self.url)
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