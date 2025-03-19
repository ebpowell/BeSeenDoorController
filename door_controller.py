from bs4 import BeautifulSoup
import re
import requests
from requests import ReadTimeout
from requests.auth import HTTPBasicAuth
import sqlite3
import time

class door_controller:
    def __init__(self, url, username, password, dbpath):
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
        self.db_path = dbpath


    def get_httpresponse(self, url, data):
        # print(url)
        # print(data)
        # print(self.session.headers)
        try:
            response = requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout=5)
        except ReadTimeout:
            print ('Read Timeout, get_httpresponse')
            return
        # Check for successful response
        if response.status_code == 200:
            # print(response.text)
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)
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
        response = requests.post(url, headers=self.session.headers, data=data, auth=self.auth)
        # Check for successful response
        if response.status_code == 200:
            print("Connected")
            return response
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)

    def write_db(self, query, data):
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        [cur.execute(f"{query}{token})") for token in data]
        db.commit()
        # Close the database
        db.close()

    def purge_db(self, table):
        db = sqlite3.connect(self.db_path)
        # Add records tp SQLite database
        cur = db.cursor()
        cur.execute(f"delete from {table}")
        db.commit()

class key_fobs(door_controller):
    def __init__(self, url, username, password, dbpath):
        super().__init__(url, username, password, dbpath)
        self.sql = f"INSERT INTO system_fobs (record_id, fob_id) values("

    def parse_fobs_data(self, markup):
        tpl_row = []
        #Trim everything before the first data row in the table
        text_markup = markup[markup.find('<th>Operation</th></tr>'):]
        tag_len = len('<th>Operation</th></tr>')
        text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
        tpl_murow = self.parse_tr_data(text_markup, r'<tr align=(.*?)</tr>', 4)
        [tpl_row.append([row[0], row[1]]) for row in tpl_murow]
        return  tpl_row

    def get_keyfobs(self):
        data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        response = self.connect(data)
        if response.status_code == 200:
            for x in range (1,18):
                print(x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s2':'Users'}
                elif x == 2:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    url = self.url + '/ACT_ID_325'
                    ata = {'PC': f"0001",
                           'PE': f"00020",
                           'PN': 'Next'}
                else:
                    # Derive the PC value from the form element of the response text
                    # Update passed data
                    data = {'PC':f"000{(x*20)-19}",
                            'PE':f"000{(x*20)}",
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url+'/ACT_ID_325'
                    url = self.url + '/ACT_ID_325'
                response = self.get_httpresponse(url, data)
                try:
                    if response.status_code ==200:
                        # Extract data from the returned page
                        batch = self.parse_fobs_data(response.text)
                        if batch:
                            fobs = fobs + batch
                        else:
                            print ("No Records returned")
                            # next_index =  swipes[len(swipes)-20][0]
                        time.sleep(5)
                except:
                    pass


class fob_swipes(door_controller):
    def __init__(self, url, username, password, dbpath):
        super().__init__(url, username, password, dbpath)
        self.sql = f"INSERT INTO system_swipes (record_id, fob_id, status, door, timestamp) values("

    def get_swipes(self):
        # data = {'s2': 'Users'}
        swipes = []
        connect_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        print(self.session.headers)
        print(connect_data)
        response = self.connect(connect_data)
        if response.status_code == 200:
            for x in range (1,18):
                print(x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                    print(self.session.headers)
                    print(data)
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    print(self.session.headers)
                    print(data)
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] =  self.url + '/ACT_ID_21'
                    print(self.session.headers)
                    print(data)
                response = self.get_httpresponse(url, data)
                try:
                    if response.status_code ==200:
                        # Extract data from the returned page
                        batch = self.parse_swipes_data(response.text)
                        if batch:
                            next_index = int(batch[1][0])
                            print(next_index)
                            print(batch)
                            swipes = swipes + batch
                        else:
                            print ("No Records returned")
                            next_index =  swipes[len(swipes)-20][0]
                        time.sleep(5)
                except:
                    pass

        print(swipes)
                    # if swipes:
                    #     self.write_db('s',swipes, x)

    def parse_swipes_data(self, markup):
        tpl_row = []
        #Trim everything before the first data row in the table
        text_markup = markup[markup.find('<th>DateTime</th></tr>'):]
        tag_len = len('<th>DateTime</th></tr>')
        text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
        # if text_markup.find('Forbid') !=0:
        #     print(text_markup)
        # Extract the table data
        tpl_murow = self.parse_tr_data(text_markup, r'<tr class=(.*?)</tr>', 5)
        # Parse the list of rows for the data we want
        for row in tpl_murow:
            door_row = row[3]
            splt_row = door_row.split('IN[#')
            # print(splt_row)
            splt_row[1] = splt_row[1][0:1]
            the_row = [row[0], row[1], splt_row[0].strip(), splt_row[1], row[4]]
            # print(the_row)
            tpl_row.append(the_row)
        return tpl_row


if __name__=='__main__':
    username = "abc"
    password = "654321"
    url = "http://69.21.119.148"

    obj_keyfobs = key_fobs(url, username, password, '/home/ebpowell/Documents/Wentworth HOA/Key_Fobs/key_fobs.db')
    obj_keyfobs.get_keyfobs()
    # obj_swipe = fob_swipes(url, username, password, '/home/ebpowell/Documents/Wentworth HOA/Key_Fobs/key_fobs.db')
    # obj_swipe.get_swipes()