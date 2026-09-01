from logging import exception
import re
import time
import datetime
from urllib import response
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.utils import log_info, log_error


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

        log_info("Starting controller sync...")

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
                # print(f"Fetching page {page_iteration} -> {url}")
                # print(f"Payload: {data}")
                response = self.get_httpresponse(url, data)
            except Exception as e:
                log_info(f"Network error on page {page_iteration}: {e}")
                # Add to logger
                raise e

            if response.status_code == 200:
                try:
                    # First iteration, extract total number of key fobs from the page to determine when to sto
                    if page_iteration == 1:
                        total_fobs_match = re.search(r"Total Users:\s* (\d+)", response.text)
                        if total_fobs_match:
                            total_fobs = int(total_fobs_match.group(1))
                            log_info(f"Total key fobs to sync: {total_fobs}")
                        else:
                            log_info("Could not determine total number of key fobs. Proceeding with pagination until no more records are returned.")
                            total_fobs = None  # Unknown, will rely on termination condition
                    # Extract data from the returned page HTML
                    batch = self.parse_fobs_data(response.text) 
                    fobs.extend(batch)
                    start_idx += 20
                    batch_len = len(batch)      
                    if len(fobs) >= total_fobs if total_fobs is not None else False:
                        log_info("Reached the end of available records based on total count. Finalizing sync.")
                        log_info(f"Total fobs pulled: {len(fobs)}. Expected total: {total_fobs}.")
                        break
                    if not batch:
                        log_info("No more records returned. Ending pagination.")
                        log_info(f"Total fobs pulled: {len(fobs)}. Expected total: {total_fobs}.")
                        break
                    # print(f"Processed page {page_iteration}: {batch_len} records added. Next index target: {next_index}. Total fobs pulled so far: {len(fobs)}")              
                    log_info(f"Batch Size: {batch_len} | Next Index Target: {next_index} | Total Fobs Pulled: {len(fobs)}")
                    
                except Exception as e:
                    log_error(f"Error occurred while parsing page response: {e}")
                    # Optional: break or raise here if parsing failure shouldn't infinite-loop
                    break
                    
                time.sleep(self.timeout / 3)
                page_iteration += 1  # Increment to move into subsequent pages step
            else:
                log_error(f"Received non-200 status code ({response.status_code}). Stopping.")
                break

        return fobs


    def get_permissions_record(self, record_id):
        if record_id is None:
            return None
        try:
            record_num = int(record_id)
            data = {f"E{record_num - 1}": 'Edit'}
            self.session.headers['Referer'] = self.url + '/ACT_ID_21'
            url = self.url + '/ACT_ID_324'
            response = self.get_httpresponse(url, data)
            if not response or not getattr(response, 'text', None):
                return None
            return self.parse_permissions(response.text)
        except Exception as e:
            log_info(f"get_permissions_record: Exception retrieving record_id {record_id}: {e}")
            return None

    def parse_permissions(self, markup):
        if not markup or '</th></tr>' not in markup:
            return None
        try:
            head_idx = markup.find('</th></tr>')
            tail_idx = markup.find('</p></form></body><HEAD>')
            if head_idx == -1:
                return None
            sub_markup = markup[head_idx + 10:tail_idx - 8] if tail_idx != -1 else markup[head_idx + 10:]
            
            # Split into 5 columns
            tpl_murow = self.parse_tr_data(sub_markup, r'<tr align=(.*?)</tr>', 5)
            if not tpl_murow or len(tpl_murow[0]) < 4:
                return None
                
            lst_tags = tpl_murow[0][3].split('<br><br>')
            door_perms = [[tpl_murow[0][0], tpl_murow[0][1], self.parse_tag(perm)[0], self.parse_tag(perm)[1], self.url]
                          for perm in lst_tags if perm and perm.find('option') > 0]
            return door_perms
        except (IndexError, TypeError):
            log_info("parse_permissions: No permission record found for record_id (null result).")
            return None
        except Exception as e:
            log_error(f"parse_permissions error: {e}")
            return None

    def parse_tag(self, permission_tag):
        door = permission_tag[0:7]
        if permission_tag.find('selected') > 0:
            selected_tag = permission_tag[permission_tag.find('selected') + 9:]
            perm = selected_tag[:selected_tag.find('<')]
        elif permission_tag.find('Forbid') > 0:
            perm = 'Forbid'
        else:
            return
        return [door, perm]

    def get_record_id(self, fob_id):
        self.users_page()
        url = self.url + '/ACT_ID_323'
        try:
            self.session.headers['Referer'] = self.url + '/ACT_ID_21'
            data = {'US21': f"{fob_id}",
                    '22': '0',
                    '23': '',
                    '24': 'Search'}
            response = self.get_httpresponse(url, data, expected_marker='Search Finished')
            if not response or not getattr(response, 'text', None):
                return None
            return self.parse_user_id(response.text)
        except Exception as e:
            log_error(f"get_record_id error for fob_id {fob_id}: {e}")
            return None
        
    def parse_user_id(self, markup):
        if not markup:
            return None
        data_row_regex = r'<tr align=center>(.*?)</tr>'
        tpl_murow = self.parse_tr_data(markup, data_row_regex, tag_count=4)
        try:
            user_id = tpl_murow[0][0]
            try:
                return int(user_id)
            except:
                log_info(f"Failed to convert user_id to int: {user_id}")
                return None
        except IndexError:
            # Verify that the markup contains the information "Found Users' Count: 0. Search Finished"
            if "Found Users' Count: 0" in markup or "Search Finished" in markup:
                log_info(f"No users found on controller for given search.")
                return None
            else:
                log_error(markup)
            return None
        except Exception as e:
            log_error(e.args)
            return None