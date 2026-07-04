import re
import requests
from bs4 import BeautifulSoup
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
        self.timeout = 10
        self.max_retries = 6
        self.login_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}


    def get_httpresponse(self, url, data):
        for x in range (0, self.max_retries):
            try:
                response = self.session.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout=self.timeout)
                # Check for successful response
                if response.status_code == 200:
                    return response
                else:
                    print(f"door_controller.get_httpresponse: Request failed with status code: {response.status_code}")
                    print(response.text)
                    return
            except Exception as e:
                #raise e
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

    def connect(self):
        url = self.url+'/ACT_ID_1'
        for x in range(0, self.max_retries):
            try:
                # TO DO: Use self.get_httpresponse instead of direct requests.post to maintain session and headers
                response = self.get_httpresponse(url, data = self.login_data)
                # response = self.session.post(url, headers=self.session.headers, data=self.login_data, auth=self.auth, timeout=self.timeout)
                # Check for successful response
                if response.status_code == 200:
                    # print("door_controller.connect: Connected")
                    return response
                else:
                    print(f"door_controller.connect: Connection Request failed with status code: {response.status_code}")
                    print(response.text)
                    return
            except Exception as e:
                # raise e
                pass
        print('Connection Failed')
        return

    def users_page(self):
        response = self.connect()
        if response and response.status_code == 200:
            self.session.headers['Referer'] = self.url + '/ACT_ID_1'
            url = self.url + '/ACT_ID_21'
            data ={'s2':'Users'}
            for x in range(0, self.max_retries):
                try:
                    response = self.get_httpresponse(url, data=data)
                    #response =  requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout = self.timeout )
                    return response
                except:
                    time.sleep(self.timeout/3)
                    pass

    def navigate(self):
        # obj_ACL = AccessControlList(self.username, self.password, self.url)
        try:
            response = self.connect()
            if response.status_code == 200:
                try:
                    response = self.users_page()
                    return response
                except Exception as e:
                    raise e
        except Exception as e:
            raise e