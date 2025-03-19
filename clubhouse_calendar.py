import re
import requests
from requests.auth import HTTPBasicAuth
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import sqlite3

class hoa_page:
    def __init__(self,
                 username, password):
        self.auth = HTTPBasicAuth(username, password)
        # self.url = url
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

    def connect(self, data):
        response = requests.post(self.url, headers=self.headers, data=data, auth=self.auth)
        # Check for successful response
        if response.status_code == 200:
            print("Connected")
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)


class calendar(hoa_page):
    def __init__(self, url, username, password):
        super().__init__(username, password)
        # Overload self.url
        self.url = url+'/p/Calendar'

class minutes(hoa_page):
    def __init__(self, url, username, password):
        super().__init__(username, password)
        # Overload self.url
        self.url = url+'/p/Minutes'

if __name__ == '__main__':
    username = 'ebpowell'
    password = 'Geo!ogy1'
    url = 'https://www.wentworthhoa.com'
    # the_minutes = minutes(url, username, password)
    # resp = the_minutes.connect('')
    # print (resp.text)
    the_calendar = calendar(url, username, password)
    resp = the_calendar.connect('')
    print (resp.text)
    resp.html.render()



