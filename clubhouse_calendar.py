import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import sqlite3

class calendar:
    def __init__(self, url,
                 username, password):
        self.auth = HTTPBasicAuth(username, password)
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': url,
            'Connection': 'keep-alive',
            'Referer': url + '/ACT_ID_1',
            'Upgrade-Insecure-Requests': '1',
            'Priority': 'u=0, i'
        }

    def connect(self):
        response = requests.post(self.url+'\ACT_ID_1', headers=self.headers, data=data, auth=self.auth)
        # Check for successful response
        if response.status_code == 200:
            print("Connected")
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)