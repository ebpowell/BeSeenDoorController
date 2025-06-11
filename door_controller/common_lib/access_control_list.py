from logging import exception
import datetime
import requests
import time

from door_controller.common_lib.database import cls_sqlite
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.fobs import key_fobs


class AccessControlList(key_fobs):
     # Assumes we are at a page of
    def __init__(self, username, password, url):
        super().__init__(url, username, password)
        self.max_retries = 5


    def get_permissions_record(self, record_id):
        # Use get self.get_keyfobs_rangw to pull the recordset
        # Using the record_ids in the returned by self.get_keyfobs_range, generate the
        # Varibales to extract the door permissions

        # E0=Edit (where the number is record_id - 1
        # Ref = ACT_ID_21
        # URL = http://69.21.119.148/ACT_ID_324

        #Connect to the controller to make sure we are past the login page
        users = []
        # connect_data = {'username': self.username,
        #                 'pwd': self.password,
        #                 'logid': '20101222'}
        # try:
        #     response = self.connect(connect_data)
        # except:
        #     raise

        # pull the edit record
        data = {F"""E{record_id-1}""":'Edit'}
        print('get_permission_record:',data)
        # Update Request header to revise the referrer attribute
        headers={'Referer': self.url + '/ACT_ID_21'}
        url = self.url + '/ACT_ID_324'
        try:
            response = self.get_httpresponse(url, data,  headers=headers, timeout=(15,30), retries = 6)
            print(response.status_code)
            return self.parse_permissions(response.text)
        except requests.exceptions.Timeout: #Detect pause on the controller.
            print("get_permissions_record: The request timed out. Door Controller took too long to respond.")
            print(data, url)
            raise requests.exceptions.Timeout
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            raise e


    def parse_permissions(self, markup):
        # access permissions are on attribute names Door controller 1: 24, 25, 26, and 27,
        # access permissions are on attribute names Door controller 2:  26, and 27,
        # Values 0 : Forbid, 1 : Allow
        # Chop the inital noise off of the record
        # markup = markup[markup.find('<th>Operation</th></tr>'):markup.find('</p></form></body><HEAD>')]
        markup = markup[markup.find('</th></tr>')+10:markup.find('</p></form></body><HEAD>')-8]
        # Split into 5 columns
        tpl_murow = self.parse_tr_data(markup, r'<tr align=(.*?)</tr>', 5)
        # Now chop-up row 4 (3) by <br><br>,
        try:
            lst_tags = tpl_murow[0][3].split('<br><br>')
            # Iterate through the list of subfields and determine if they contain "selected", if yes : Allow, else, Forbid
            door_perms = [[tpl_murow[0][0], tpl_murow[0][1], self.parse_tag(perm)[0], self.parse_tag(perm)[1], self.url[-3:]]
                          for perm in lst_tags if perm.find('option') >0]
            return door_perms
        except IndexError:
            print(markup)
            pass
        except Exception as e:
            raise e

    def parse_tag(self, permission_tag):

        door = permission_tag[1:3]
        print (permission_tag, door)
        if permission_tag.find('selected') > 0:
            selected_tag = permission_tag[permission_tag.find('selected')+9:]
            perm = selected_tag[:selected_tag.find('<')]
            # print(perm)
            # perm = selected_tag
        elif permission_tag.find('Forbid') > 0:
            perm = 'Forbid'
        else:
            return
        print([door, perm])
        return [door, perm]

    def navigate(self, data):
        # obj_ACL = AccessControlList(self.username, self.password, self.url)
        url = self.url + '/ACT_ID_21'
        data ={'s2':'Users'}
        try:
            response = self.get_httpresponse(url, data, headers= {'Referer': self.url + '/ACT_ID_1'})
            return response
        except Exception as e:
            raise e
        # except Exception as e:
        #     raise e
        return None

    def parse_users_data(self, response):
        tpl_row = []
        #Trim everything before the first data row in the table
        try:
            text_markup = response[response.find('<th>Operation</th></tr>'):]
            tag_len = len('<th>Operation</th></tr>')
            text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
            tpl_murow = self.parse_tr_data(text_markup, r'<tr align=(.*?)</tr>', 4)
            [tpl_row.append([row[0], row[1]]) for row in tpl_murow]
        except Exception as e:
            print(e)
            raise e
        return  tpl_row

    def tokenize(self, response):
        content = response['content']
        ...

    # DEPRECATED
    def get_acl(self, connect_string):
        headers = {}
        # Add iterations, start val parameters
        last_index = int(rec_id_start)
        # next_index = int(rec_id_start) + 19
        next_index = last_index
        # data = {'s2': 'Users'}
        users = []
        connect_data = {'username': self.username,
                     'pwd': self.password,
                     'logid': '20101222'}
        # print(rec_id_start)
        # print(self.session.headers)
        # print(connect_data)
        url = self.url + '/ACT_ID_1'
        try:
            # response = self.connect(connect_data)
            response = self.get_httpresponse(url, connect_data)
        except:
            raise
        if response.status_code == 200:
            # Pool database for record_ids
            objdb = postgres(connect_string)
            records = objdb.get_fob_records()
            for record in range(records):
                 print('get_users_range X value:', x)
                 if x == 1:
                     # Update Request header to revise the referrer attribute
                     # self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                     url = self.url + '/ACT_ID_21'
                     data = {'s2': 'Users'}
                 # elif x == 2:
                 #     # Update passed data
                 #     data = {'PC': last_index,
                 #             'PE': next_index,
                 #             'PN': 'Next'}
                 #     # Update Request header to revise the referrer attribute
                 #     url = self.url + '/ACT_ID_325'
                     # self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                 else:
                     # Update passed data
                     data = {'PC': last_index,
                             'PE': next_index,
                             'PN': 'Next'}
                     # Update Request header to revise the referrer attribute
                     url = self.url + '/ACT_ID_325'
                     # self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                 for y in range(1, iterations):
                     try:
                         print('Connect Attempt:', y)
                         headers = {'Referer': self.url + '/ACT_ID_21'}
                         response = self.get_httpresponse(url, data, headers=headers)
                         print("Success")
                         # print(url)
                         # print(self.session.headers)
                         # print(x, data)
                         break
                     except:
                         # after two tries, move to the next batch of records
                         time.sleep(self.timeout)
                         pass
                 # if x > 1:
                 try:
                     if response.status_code == 200:
                         # Extract data from the returned page
                         batch = self.parse_users_data(response.text)
                         if batch:
                             last_index = next_index
                             next_index = int(batch[len(batch)-1][0])
                             users = users + batch
                             print('Pass:', x, 'Parse Records Success', 'Batch Record Count:',
                                   len(batch), 'Next Index:', next_index)
                             print('users Count:', len(users))
                         else:
                             # next_index =  users[len(users)-20][0]
                             print(response.text)
                             print("No Records returned", 'Next Index:', next_index)
                             # This connection is f&cked....write the records and try again
                             break
                         time.sleep(self.timeout / 3)
                     else:
                         print(response.status_code)
                 except:
                     # pass
                    raise
        print('Records to add:', len(users))
        return users# DEPRECATRE

    def get_users(self, rec_id_start, batch_size, objdb):
        headers = {}
        # Add iterations, start val parameters
        last_index = int(rec_id_start)
        next_index = last_index
        users = []
        batch_size = tuple(batch_size)
        iterations = int(batch_size[0] / 20)
        connect_data = {'username': self.username,
                     'pwd': self.password,
                     'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        try:
            response = self.get_httpresponse(url, connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range(1, iterations):
                 print('get_users_range X value:', x)
                 if x == 1:
                     url = self.url + '/ACT_ID_21'
                     data = {'s2': 'Users'}
                 else:
                     # Update passed data
                     data = {'PC': last_index,
                             'PE': next_index,
                             'PN': 'Next'}
                     url = self.url + '/ACT_ID_325'
                 try:
                     print('Connect Attempt:')
                     headers = {'Referer': self.url + '/ACT_ID_21'}
                     response = self.get_httpresponse(url, data, headers=headers)
                     print("Success")
                     # break
                 except:
                    # after two tries, move to the next batch of records
                    time.sleep(self.timeout)
                    pass
                 try:
                     if response.status_code == 200:
                         # Extract data from the returned page
                         batch = self.parse_users_data(response.text)
                         # Write to users table in the database
                         if batch:
                             [objdb.insert_controller_fobs_slop([record[0], record[1],
                                                                 self.url[7:], str(datetime.datetime.now())])
                              for record in batch]
                             last_index = next_index
                             next_index = int(batch[len(batch)-1][0])
                             time.sleep(10)
                         else:
                             break
                     else:
                         print(response.status_code)
                 except:
                     # pass
                    raise
        print('Records to add:', len(users))
        return

    def get_max_users(self):
        connect_data = {'username': self.username,
                        'pwd': self.password,
                        'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        try:
            response = self.get_httpresponse(url, connect_data)
            if response.status_code == 200:
                try:
                    url = self.url + '/ACT_ID_21'
                    data = {'s2': 'Users'}
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                if response.status_code == 200:
                    text = response.text[response.text.find('Total Users:'):]
                    text = text[:text.find("<")]
                    # int(text[text.find(':')+1:].strip())
                    return int(text[text.find(':')+1:].strip())
        except:
            raise

        return None


if __name__ == '__main__':
    username = "abc"
    password = "654321"
    urls = ["http://69.21.119.147", "http://69.21.119.148"]
    data = {'username': username,
            'pwd': password,
            'logid': '20101222'}
    #record_id = 55
    objdb = cls_sqlite('/door_controller_data')
    record_ids = objdb.get_fob_records()
    for record_id in record_ids:
        print('Record ID:', record_id)
        for url in urls:
            obj_ACL = AccessControlList(username, password, url)
            response = obj_ACL.navigate(data)
            if response.status_code == 200:
                for x in range(0, 20):
                    try:
                        lst_perms = obj_ACL.get_permissions_record(record_id[0])
                        # Insert into database
                        if lst_perms:
                            [objdb.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
                            # time.sleep(1)
                            break
                        else: # Record not returned, need to try to pull again
                            print('Iteration: ', x, '...Reconnecting')
                            time.sleep(1)
                            response = obj_ACL.navigate(data)
                    except:
                        raise
            del obj_ACL

