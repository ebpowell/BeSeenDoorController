import re
import requests
from requests.auth import HTTPBasicAuth
import time

class door_controller:
    def __init__(self, url, username, password):
        self.auth = HTTPBasicAuth(username, password)
        self.url = url
        self.username = username
        self.password = password
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': url,
            'Connection': 'keep-alive',
            'Referer': url+'/ACT_ID_1',
            'Upgrade-Insecure-Requests': '1',
            'Priority': 'u=0, i'
        }
        self.session = requests.session()
        self.session.headers.update(headers)
        self.sql = ''
        self.timeout = 15
        self.max_retries = 20


    def get_httpresponse(self, url, data):
        for x in range (0, self.max_retries):
            try:
                response = requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout=self.timeout)
                # Check for successful response
                if response.status_code == 200:
                    print("door_controller.get_httpresponse: Connected")
                    return response
                else:
                    print(f"door_controller.get_httpresponse: Request failed with status code: {response.status_code}")
                    print(response.text)
                    return
            except Exception as e:
                pass
        return

    def is_convertible_to_int(self, token):
      """
      Checks if a given token can be converted to an integer.

      Args:
        token: The token to be checked.

      Returns:
        True if the token can be converted to an integer, False otherwise.
      """
      try:
        int(token)
        return True
      except ValueError:
        return False

    def parse_tr_data(self, text, the_regex, tag_count):
        """
        Parses the given text and extracts data from <tr class=Y> tags into a list of tuples.

        Args:
            text: The input text containing <tr> tags.

        Returns:
            A list of tuples, where each tuple represents the data from a <tr class=Y> tag.
        """
        results = []
        tr_tags = re.findall(the_regex, text, re.DOTALL)
        # tr_tags = re.findall(r'<tr class=(.*?)</tr>', text, re.DOTALL)
        for tr_tag_content in tr_tags:
            td_tags = re.findall(r'<td>(.*?)</td>', tr_tag_content)
            if len(td_tags) == tag_count:  # Ensure we have the correct number of columns
                results.append(tuple(td_tags))
        # print(results)
        return results

    def connect(self, data):
        url = self.url+'/ACT_ID_1'
        for x in range(0, self.max_retries):
            try:
                response = requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout=self.timeout)
                # Check for successful response
                if response.status_code == 200:
                    print("door_controller.connect: Connected")
                    return response
                else:
                    print(f"door_controller.connect: Connection Request failed with status code: {response.status_code}")
                    print(response.text)
                    return
            except:
                pass
        print('Connection Failed')
        return

    # def add_fob(self, fob_id, name):
    #     obj_fob = key_fobs(self.url, self.username, self.password)
    #     data = {'s1':'AddCard'}
    #     response = obj_fob.navigate(data)
    #     if response.status_code == 200:
    #         url = self.url+'\ACT_ID_312'
    #         # ACT_ID_312
    #         # Assuming UserID 99999, Username 'Test'
    #         data = {25:'Add', 'AD21':fob_id, 'AD22':name}
    #         #Call response object
    #         response=self.get_httpresponse(url, data)
    #         return response.status_code
    #
    #
    # def set_permissions(self, data, record_id, dct_permissions):
    #     url = self.url + '\ACT_ID_324'
    #     # TO DO: Map Door / Controller combos to numeric values on Edit page
    #     dct_doors = {1:24, 2:25, 3:26, 4:27}
    #     dct_perms = {'Allow':1, 'Forbid':0}
    #     obj_fob = key_fobs(self.username, self.password, self.url)
    #     response = obj_fob.navigate(data)
    #     # Look up the Fob_ID
    #     if response.status_code == 200:
    #         for x in range(0, 20):
    #             try:
    #                 lst_perms = obj_fob.get_permissions_record(record_id[0])
    #                 # Insert into database
    #                 if lst_perms:
    #                     edit_record = f"E{record_id[0] - 1}"
    #                     save_record = f"S{record_id[0]-1}"
    #                     data = {edit_record:'Edit'}
    #                     #Call response object
    #                     response = self.get_httpresponse(url, data)
    #                     if response==200:
    #                         data = {24:"0",
    #                                 25:"0",
    #                                 26:"1",
    #                                 27:"1",
    #                                 "USXo":"",
    #                                 save_record:'Save'}
    #                         response=self.get_httpresponse(url, data)
    #                         return response
    #
    #             except Exception as e:
    #                 raise e
    #
    # def del_fob(self, data, record_id, permissions):
    #     obj_fob = key_fobs(self.username, self.password, self.url)
    #     response = obj_fob.navigate(data)
    #     if response.status_code==200:
    #         url = self.url +'\ACT_ID_324'
    #         the_number = record_id -1
    #         key = F"D{the_number}"
    #         data = {key:'Delete'}
    #         # Call response
    #         the_code = self.get_httpresponse(url, data)
    #         if the_code.status_code == 200:
    #             ok_key = F"X{the_number}"
    #             data= {ok_key:'OK'}
    #             #Call response
    #             the_code = self.get_httpresponse(url, data)
    #             return the_code.status_code

    def users_page(self):

        self.session.headers['Referer'] = self.url + '/ACT_ID_1'
        url = self.url + '/ACT_ID_21'
        data ={'s2':'Users'}
        for x in range(0, self.max_retries):
            try:
                response =  requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout = self.timeout )
                return response
            except:
                time.sleep(self.timeout/3)
                pass

    def navigate(self, data):
        # obj_ACL = AccessControlList(self.username, self.password, self.url)
        try:
            response = self.connect(data)
            if response.status_code == 200:
                try:
                    response = self.users_page()
                    return response
                except Exception as e:
                    raise e
        except Exception as e:
            raise e





