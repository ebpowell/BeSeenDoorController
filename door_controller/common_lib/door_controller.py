import re
import requests
from requests.auth import HTTPBasicAuth


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

    def add_fob(self):
            ...

    def set_permissions(self):
             ...

    def del_fob(self):
        ...








