from logging import exception
import re
import time
import datetime
from urllib import response

from door_controller.common_lib.door_controller import door_controller


class key_fobs(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)
        self.sql = ('INSERT INTO dataload.fobs_slop (record_id, '
                    'fob_id, controller_ip, record_time) values')

    def parse_fobs_data(self, markup):
        tpl_row = []
        dt_now = datetime.datetime.now()
        now = "'{}'".format(dt_now.strftime("%Y-%m-%d %H:%M:%S"))
        cidr = self.url[7:]+'/32'
        cidr = "'{}'".format(cidr)
        #Trim everything before the first data row in the table
        text_markup = markup[markup.find('<th>Operation</th></tr>'):]
        tag_len = len('<th>Operation</th></tr>')
        text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
        tpl_murow = self.parse_tr_data(text_markup, r'<tr align=(.*?)</tr>', 4)
        [tpl_row.append([row[0], row[1],cidr, now]) for row in tpl_murow]
        return  tpl_row

    def get_keyfobs(self):
        batch_len = 20  # Number of records to fetch per page
        start_idx = 1  # Starting index for the first page
        fobs = []
        next_index = 20
        page_iteration = 1  # Track page step dynamically instead of using range()

        try:
            response = self.connect()
            # response = self.navigate()
        except Exception as e:
            raise e

        if response.status_code != 200:
            return None

        print("Starting controller sync...")

        while True:
            if page_iteration == 1:
                data = {'s2':'Users'}
                self.session.headers['Referer'] = f"{self.url}/ACT_ID_21"
                url = f"{self.url}/ACT_ID_21"
            else:
                data = {
                    'PC': start_idx,
                    'PE': start_idx+19,
                    'PN': 'Next'
                }
                self.session.headers['Referer'] = f"{self.url}/ACT_ID_325"
                url = f"{self.url}/ACT_ID_325"

            try:
                print(f"Fetching page {page_iteration} -> {url}")
                print(f"Payload: {data}")
                response = self.get_httpresponse(url, data)
            except Exception as e:
                print(f"Network error on page {page_iteration}: {e}")
                raise e

            if response.status_code == 200:
                try:
                    # First iteration, extract total number of key fobs from the page to determine when to sto
                    if page_iteration == 1:
                        total_fobs_match = re.search(r"Total Users:\s* (\d+)", response.text)
                        if total_fobs_match:
                            total_fobs = int(total_fobs_match.group(1))
                            print(f"Total key fobs to sync: {total_fobs}")
                        else:
                            print("Could not determine total number of key fobs. Proceeding with pagination until no more records are returned.")
                            total_fobs = None  # Unknown, will rely on termination condition
                    # Extract data from the returned page HTML
                    batch = self.parse_fobs_data(response.text) 
                    fobs.extend(batch)
                    start_idx += 20
                    batch_len = len(batch)      
                    if len(fobs) >= total_fobs if total_fobs is not None else False:
                        print("Reached the end of available records based on total count. Finalizing sync.")
                        print(f"Total fobs pulled: {len(fobs)}. Expected total: {total_fobs}.")
                        break
                    if len(fobs) == 0:
                        print("No more records returned. Ending pagination.")
                        print(f"Total fobs pulled: {len(fobs)}. Expected total: {total_fobs}.")
                        break
                    print(f"Processed page {page_iteration}: {batch_len} records added. Next index target: {next_index}. Total fobs pulled so far: {len(fobs)}")              
                    print(f"Batch Size: {batch_len} | Next Index Target: {next_index} | Total Fobs Pulled: {len(fobs)}")
                    
                except Exception as e:
                    print(f"Error occurred while parsing page response: {e}")
                    # Optional: break or raise here if parsing failure shouldn't infinite-loop
                    break
                    
                time.sleep(self.timeout / 3)
                page_iteration += 1  # Increment to move into subsequent pages step
            else:
                print(f"Received non-200 status code ({response.status_code}). Stopping.")
                break

        return fobs


    def get_permissions_record(self, record_id):
        data = {f"E{record_id - 1}": 'Edit'}
        self.session.headers['Referer'] = self.url + '/ACT_ID_21'
        url = self.url + '/ACT_ID_324'
        try:
            response = self.get_httpresponse(url, data)
            return self.parse_permissions(response.text)
        except:
            raise

    def parse_permissions(self, markup):
        markup = markup[markup.find('</th></tr>') + 10:markup.find('</p></form></body><HEAD>') - 8]
        # Split into 5 columns
        tpl_murow = self.parse_tr_data(markup, r'<tr align=(.*?)</tr>', 5)
        # Now chop-up row 4 (3) by <br><br>,
        try:
            lst_tags = tpl_murow[0][3].split('<br><br>')
            # Iterate through the list of subfields and determine if they contain "selected", if yes : Allow, else, Forbid
            door_perms = [[tpl_murow[0][0], tpl_murow[0][1], self.parse_tag(perm)[0], self.parse_tag(perm)[1], self.url]
                          for perm in lst_tags if perm.find('option') > 0]
            return door_perms
        except IndexError:
            print(markup)
            pass
        except Exception as e:
            raise e

    def parse_tag(self, permission_tag):

        door = permission_tag[0:7]
        # print(permission_tag, door)
        if permission_tag.find('selected') > 0:
            selected_tag = permission_tag[permission_tag.find('selected') + 9:]
            perm = selected_tag[:selected_tag.find('<')]
            # print(perm)
            # perm = selected_tag
        elif permission_tag.find('Forbid') > 0:
            perm = 'Forbid'
        else:
            return
        # print([door, perm])
        return [door, perm]

    def get_record_id(self, fob_id):
        self.navigate()
        url = self.url + '/ACT_ID_323'
        try:
            self.session.headers['Referer'] = self.url + '/ACT_ID_21'
            data = {'US21':f"{fob_id}",
                    '22': '0',
                    '23': '',
                    '24': 'Search'}
            response = self.get_httpresponse(url, data)
            return self.parse_user_id(response.text)
        except Exception as e:
            raise e
        
    def parse_user_id(self, markup):
        data_row_regex = r'<tr align=center>(.*?)</tr>'
        tpl_murow = self.parse_tr_data(markup, data_row_regex, tag_count=4)
        try:
            user_id = tpl_murow[0][0]
            try:
                return int(user_id)
            except:
                print(f"Failed to convert user_id to int: {user_id}")
                return None
        except IndexError:
            # Verify thet the markup contains the information "Found Users' Count: 0. Search Finished"
            if "Found Users' Count: 0. Search Finished" in markup:
                print("No users found for the given fob_id.")
                return None
            else:
                print(markup)
            pass
        except Exception as e:
            raise e