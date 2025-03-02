import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import sqlite3

class keyfobs:
    def __init__(self, url, username, password):
        self.auth = HTTPBasicAuth(username, password)
        self.url = url
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
            'Origin': url,
            'Connection': 'keep-alive',
            'Referer': url+'/ACT_ID_1',
            'Upgrade-Insecure-Requests': '1',
            'Priority': 'u=0, i'
        }
        self.session = requests.session()
        self.session.headers.update(headers)


    def get_httpresponse(self, url, data):
        print(url)
        print(data)
        print(self.headers)
        response = requests.post(url, headers=self.headers, data=data, auth=self.auth)
        # response = requests.post(url, headers=self.headers, data=data)
        # Check for successful response
        if response.status_code == 200:
            print(response.text)
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)

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

    def get_fobids(self, token):
        str_length = len(token)
        subtoken = token
        while len(subtoken) >= 8:
            subtoken = subtoken[1:]
            print(subtoken)
            if self.is_convertible_to_int(subtoken)==True:
                return int(subtoken)

    def connect(self, data):
        url = self.url+'/ACT_ID_1'
        response = requests.post(url, headers=self.headers, data=data, auth=self.auth)
        # Check for successful response
        if response.status_code == 200:
            print("Connected")
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)

    def get_keyfobs(self):
        data = {'s2': 'Users'}
        response = self.connect(data)
        if response.status_code == 200:
            for x in range (0,17):
                print(x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_325'
                else:
                    # Update passed data
                    data = {'PC':f"000{(x*20)-19}",
                            'PE':f"000{x*20}",
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    self.headers['Referer'] = self.url+'/ACT_ID_21'
                    url = self.url + '/ACT_ID_325'
                response = self.get_httpresponse(url, data)
                if response.status_code ==200:
                    soup1 = BeautifulSoup(response.content, features='html.parser')
                    tokens = soup1.text.split(' ')
                    # List comprehension to find generate the foblist for the page
                    fobs = [self.get_fobids(token) for token in tokens if self.get_fobids(token)]
                    # Write list to sqlite database
                    if fobs:
                        self.write_db(fobs, x)

    def write_db(self, fobs, x):
        db = sqlite3.connect('/home/ebpowell/Documents/Wentworth HOA/Key_Fobs/key_fobs.db')
        # Add records tp SQLite database
        cur = db.cursor()
        # Purge table on the first batch of records.
        if x == 1:
            cur.execute('delete from system_fobs')
            db.commit()
        [cur.execute(f"INSERT INTO system_fobs (fob_id) values({token})") for token in fobs]
        db.commit()
        # Close the database
        db.close()

if __name__=='__main__':
    username = "abc"
    password = "654321"
    url = "http://69.21.119.148"
    obj_keyfobs = keyfobs(url, username, password)
    obj_keyfobs.get_keyfobs()
