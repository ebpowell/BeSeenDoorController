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
    def __init__(self, username, password, url, run_time):
        super().__init__(url, username, password)
        self.max_retries = 5
        self.run_time = run_time


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
        connect_data = {'username': self.username,
                        'pwd': self.password,
                        'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        try:
            response = self.get_httpresponse(url, connect_data)
        except:
            raise
        if response.status_code == 200:
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
        return None

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
            door_perms = [[tpl_murow[0][0], tpl_murow[0][1], self.parse_tag(perm)[0], self.parse_tag(perm)[1], self.url[-3:], self.run_time]
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


    def get_users(self, rec_id_start, batch_size, objdb):
        headers = {}
        # Add iterations, start val parameters
        if rec_id_start:
            last_index = int(rec_id_start) - 20
            # last_index = 20
        else:
            last_index = 1
            rec_id_start = 1
        next_index = last_index + 20
        batch_size = tuple(batch_size)
        iterations = int(batch_size[0] / 20) + 1
        connect_data = {'username': self.username,
                     'pwd': self.password,
                     'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        try:
            response = self.get_httpresponse(url, connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range(1, iterations +1):
                 print('get_users X value:', x)
                 if x == 1:
                     url = self.url + '/ACT_ID_21'
                     data = {'s2': 'Users'}
                 else:
                     # Update passed data
                     data = {'PC': last_index,
                             'PE': next_index,
                             'PN': 'Next'}
                     url = self.url + '/ACT_ID_325'
                     print(F"""Rec_id_start:{rec_id_start}, Batch_Size:{batch_size},Data: {data}""")
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
                 # DO not load records 1-20 a bunch of times
                 if (rec_id_start > 1 and x > 1) or rec_id_start <= 1:
                     try:
                         if response.status_code == 200:
                             # Extract data from the returned page
                             batch = self.parse_users_data(response.text)
                             # Write to users table in the database
                             if batch:
                                 [objdb.insert_controller_fobs_slop([record[0], record[1],
                                                                     self.url[7:], self.run_time])
                                  for record in batch]
                                 next_index = objdb.get_max_fob_id(self.url)
                                 last_index = next_index-20
                                 # next_index = int(batch[len(batch)-1][0])
                                 # last_index = next_index-20
                                 print(F"""last_index: {last_index},  Next_Index:{next_index}""")
                                 time.sleep(10)
                                 # if last_index >= rec_id_start:
                                 #     break
                             else:
                                 break
                         else:
                             print(response.status_code)
                     except:
                         # pass
                        raise
        # print('Records to add:', len(users))
        return

    def get_users_count(self):
        connect_data = {'username': self.username,
                        'pwd': self.password,
                        'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        text = ''
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
        except ValueError:
            print (text)
            self.get_users_count()
        except Exception as e:
            raise e
        return None

    def get_max_record_id(self):
        connect_data = {'username': self.username,
                        'pwd': self.password,
                        'logid': '20101222'}
        url = self.url + '/ACT_ID_1'
        text = ''
        try:
            response = self.get_httpresponse(url, connect_data)
            if response.status_code == 200:
                try: #Navigate to Users
                    url = self.url + '/ACT_ID_21'
                    data = {'s2': 'Users'}
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                if response.status_code == 200:
                    try: #Navigate to Last page Users
                        url = self.url + '/ACT_ID_325'
                        data = {'PC': '00001',
                                'PE': ['00020', 'Last']}
                        response = self.get_httpresponse(url, data)
                    except:
                        raise
                    if response.status_code == 200:
                        # Get the last User record id
                        text = response.text[response.text.find('</body>')-162:response.text.find('</body>')-150]
                        text = text[:text.find("</td>")]
                        text = text[text.find('<td>') + 4:].strip()
                        while not self.is_convertible_to_int(text):
                            text = text[:-1]
                        print(F"""Final Record_id:{text}""")
                        return int(text)
        except ValueError:
            print(text)
            self.get_max_record_id()
        except Exception as e:
            raise e
        return None

# if __name__ == '__main__':
#     username = "abc"
#     password = "654321"
#     urls = ["http://69.21.119.147", "http://69.21.119.148"]
#     data = {'username': username,
#             'pwd': password,
#             'logid': '20101222'}
#     #record_id = 55
#     objdb = cls_sqlite('/door_controller_data')
#     record_ids = objdb.get_fob_records()
#     for record_id in record_ids:
#         print('Record ID:', record_id)
#         for url in urls:
#             obj_ACL = AccessControlList(username, password, url)
#             response = obj_ACL.navigate(data)
#             if response.status_code == 200:
#                 for x in range(0, 20):
#                     try:
#                         lst_perms = obj_ACL.get_permissions_record(record_id[0])
#                         # Insert into database
#                         if lst_perms:
#                             [objdb.insert_access_list_record(perm_rec) for perm_rec in lst_perms]
#                             # time.sleep(1)
#                             break
#                         else: # Record not returned, need to try to pull again
#                             print('Iteration: ', x, '...Reconnecting')
#                             time.sleep(1)
#                             response = obj_ACL.navigate(data)
#                     except:
#                         raise
#             del obj_ACL

