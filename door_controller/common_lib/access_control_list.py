import requests

from database import cls_sqlite
from pg_database import postgres
from fobs import key_fobs
import time


class AccessControlList(key_fobs):
     # Assumes we are at a page of
    def __init__(self, username, password, url):
        super().__init__(url, username, password)
        self.max_retries = 20


    def get_permissions_record(self, record_id):
        # Use get self.get_keyfobs_rangw to pull the recordset
        # Using the record_ids in the returned by self.get_keyfobs_range, generate the
        # Varibales to extract the door permissions

        # E0=Edit (where the number is record_id - 1
        # Ref = ACT_ID_21
        # URL = http://69.21.119.148/ACT_ID_324

        data = {F"""E{record_id-1}""":'Edit'}
        # Update Request header to revise the referrer attribute
        self.session.headers['Referer'] = self.url + '/ACT_ID_21'
        url = self.url + '/ACT_ID_324'
        try:
             response = self.get_httpresponse(url, data)
             return self.parse_permissions(response.text)
        except:
            raise


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
            door_perms = [[tpl_murow[0][0], tpl_murow[0][1], self.parse_tag(perm)[0], self.parse_tag(perm)[1], self.url]
                          for perm in lst_tags if perm.find('option') >0]
            return door_perms
        except IndexError:
            print(markup)
            pass
        except Exception as e:
            raise e

    def parse_tag(self, permission_tag):

        door = permission_tag[0:7]
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

    def add_fob(self):
        ...

    def set_permissions(self):
         ...

    def del_fob(self):
        ...


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

