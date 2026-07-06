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
# import time

    def get_keyfobs(self):
        batch_len = 20  # Number of records to fetch per page
        fobs = []
        next_index = 20
        page_iteration = 1  # Track page step dynamically instead of using range()

        try:
            response = self.connect()
        except Exception as e:
            raise e

        if response.status_code != 200:
            return None

        print("Starting controller sync...")

        while True:
            # Determine URL, data payload, and headers dynamically based on current page step
            if page_iteration == 1:
                self.session.headers['Referer'] = f"{self.url}/ACT_ID_1"
                url = f"{self.url}/ACT_ID_21"
                data = {'s2': 'Users'}
            else:
                # Dynamically calculate and string-pad indices to keep format uniform (e.g., '0001', '0021')
                start_idx = str(next_index - batch_len).zfill(4)
                end_idx = str(next_index).zfill(4)
                
                data = {
                    'PC': start_idx,
                    'PE': end_idx,
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
                    # First iteration, extract total number of key fobs from the page to determine when to stop
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
                    # TERMINATION CONDITION: once the returns no new records (id the last record id does not change), we can stop the loop
                    if not batch:

                        print("No more records returned from controller. Finalizing sync.")
                        break
                    
                    fobs.extend(batch)
                    
                    # Calculate the next pagination markers based on the last processed ID
                    last_record_id = int(batch[-1][0])
                    next_index = last_record_id + 1
                    batch_len = len(batch)      
                    if len(fobs) >= total_fobs if total_fobs is not None else False:
                        print("Reached the end of available records based on total count. Finalizing sync.")
                        break
                    print(f"Processed page {page_iteration}: {batch_len} records added. Next index target: {next_index}. Total fobs pulled so far: {len(fobs)}")              
                    print(f"Next Index Target: {next_index} | Total Fobs Pulled: {len(fobs)}")
                    
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



    # def get_keyfobs(self):
    #     fobs = []
    #     next_index = 20
    #     try:
    #         response = self.connect()
    #     except exception as e:
    #         raise e
    #     if response.status_code == 200:
    #         for x in range (1,self.max_retries):
    #             if x == 1:
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url + '/ACT_ID_1'
    #                 url = self.url + '/ACT_ID_21'
    #                 data = {'s2':'Users'}
    #             elif x == 2:
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url + '/ACT_ID_21'
    #                 url = self.url + '/ACT_ID_325'
    #                 data = {'PC': f"000{next_index-19}",
    #                        'PE': f"000{next_index}",
    #                        'PN': 'Next'}
    #             else:
    #                 # Derive the PC value from the form element of the response text
    #                 # Update passed data
    #                 data = {'PC': f"000{next_index - 19}",
    #                  'PE': f"000{next_index}",
    #                  'PN': 'Next'}
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url+'/ACT_ID_325'
    #                 url = self.url + '/ACT_ID_325'
    #             try:
    #                 print(url)
    #                 print(x, data)
    #                 # print(self.session.headers)
    #                 response = self.get_httpresponse(url, data)
    #             except:
    #                 raise
    #             try:
    #                 if response.status_code ==200:
    #                     # Extract data from the returned page
    #                     batch = self.parse_fobs_data(response.text)
    #                     if batch:
    #                         fobs = fobs + batch
    #                         # Calculate the next index based on the last record in the batch
    #                         next_index = int(batch[-1][0]) + 1
    #                         # next_index = int(batch[19][0])
    #                         print('Next Index:', next_index, 'Records Added:', len(fobs), 'Total Count:', len(batch))
    #                     else:
    #                         print ("No Records returned")
    #                         # next_index =  swipes[len(swipes)-20][0]
    #                     time.sleep(self.timeout/3)
    #             except exception as e:
    #                 print(f"Error occurred while processing response: {e}")
    #                 pass
    #         return fobs
    #     return None

    # def get_keyfobs_range(self, iterations, start_rec):
    #     fobs = []
    #     next_index = start_rec
    #     print("Start:",start_rec)
    #     # Add iterations, start val parameters
    #     data = {'username': self.username,
    #     'pwd': self.password,
    #     'logid': '20101222'}
    #     try:
    #         response = self.connect(data)
    #     except:
    #         raise
    #     if response.status_code == 200:
    #         for x in range (1,iterations):
    #             if x == 1:
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url + '/ACT_ID_1'
    #                 url = self.url + '/ACT_ID_21'
    #                 data = {'s2':'Users'}
    #             elif x == 2:
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url + '/ACT_ID_21'
    #                 url = self.url + '/ACT_ID_325'
    #                 data = {'PC': f"000{next_index-19}",
    #                        'PE': f"000{(next_index)}",
    #                        'PN': 'Next'}
    #             else:
    #                 # Derive the PC value from the form element of the response text
    #                 # Update passed data
    #                 data = {'PC':f"000{next_index-19}",
    #                         'PE':f"000{next_index}",
    #                         'PN':'Next'}
    #                 # Update Request header to revise the referrer attribute
    #                 self.session.headers['Referer'] = self.url+'/ACT_ID_325'
    #                 url = self.url + '/ACT_ID_325'
    #             try:
    #                 response = self.get_httpresponse(url, data)
    #             except:
    #                 raise
    #             if x > 1:
    #                 try:
    #                     if response.status_code ==200:
    #                         # Extract data from the returned page
    #                         batch = self.parse_fobs_data(response.text)
    #                         if batch:
    #                             fobs = fobs + batch
    #                             next_index = int(batch[19][0])
    #                             print ('Next Index:',next_index, 'Records Added:',len(fobs), 'Total Count:',len(batch))
    #                         else:
    #                             print ("No Records returned")
    #                             # next_index =  swipes[len(swipes)-20][0]
    #                         time.sleep(self.timeout/2)
    #                 except:
    #                     pass
    #             else:
    #                 print("Skipping first iteration, no data returned")
    #         return fobs
    #     return None

    def get_fob_range(self, iterations, max_id):
        pass

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
        print(permission_tag, door)
        if permission_tag.find('selected') > 0:
            selected_tag = permission_tag[permission_tag.find('selected') + 9:]
            perm = selected_tag[:selected_tag.find('<')]
            # print(perm)
            # perm = selected_tag
        elif permission_tag.find('Forbid') > 0:
            perm = 'Forbid'
        else:
            return
        print([door, perm])
        return [door, perm]

    def get_user_id(self, fob_id):
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