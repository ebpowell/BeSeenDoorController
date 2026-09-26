
# File: door_controller/common_lib/swipes.py
import time
import re
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.utils import log_info, log_error, log_warning

class fob_swipes(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)

    def parse_swipes_data(self, markup):
        tpl_row = []
        if not markup or '<th>DateTime</th></tr>' not in markup:
            return tpl_row

        try:
            start_tag = '<th>DateTime</th></tr>'
            start_idx = markup.find(start_tag) + len(start_tag)
            end_idx = markup.find('</table>', start_idx)
            text_markup = markup[start_idx:end_idx] if end_idx != -1 else markup[start_idx:]

            tpl_murow = self.parse_tr_data(text_markup, r'<tr class=(.*?)</tr>', 5)
            for row in tpl_murow:
                door_row = row[3]
                if 'IN[#' in door_row:
                    splt_row = door_row.split('IN[#')
                    door_name = splt_row[0].strip()
                    door_num = splt_row[1][0:1] if len(splt_row) > 1 else '0'
                else:
                    door_name = door_row.strip()
                    door_num = ''.join(c for c in door_row if c.isdigit()) or '0'

                tpl_row.append([row[0], row[1], door_name, door_num, row[4], self.url])
        except Exception as e:
            log_error(f"parse_swipes_data exception: {e}")

        return tpl_row

    def get_swipe_page(self, cursor=None):
        """
        Fetches a single page (up to 20 records) from the door controller board.
        If cursor is None or 0, opens the initial swipe view (/ACT_ID_21).
        If cursor is provided, fetches the next page using the cursor index (/ACT_ID_345).
        Returns: (records: list, next_cursor: int or None, has_more: bool)
        """
        self.verify_or_reauth()

        # Connect to the controller and navigate to the Swipe page.*****
        self.connect()
        # Navigate to the swipes page 
        url = f"{self.url}/ACT_ID_21"
        data = {'s4': 'Swipe'}
        response = self.get_httpresponse(url, data)
        if response is None or response.status_code != 200:
            log_warning(f"Failed to fetch initial swipe page from {url}: HTTP {getattr(response, 'status_code', None)}")
            return [], None, False  
        # *** TO DO: Parse records to get the maximum record_id for the first page. ***

        url = f"{self.url}/ACT_ID_345"
        data = {'PC': int(cursor) + 19, 'PE': 0, 'PN': 'Next'}

        response = self.get_httpresponse(url, data)
        if not response or response.status_code != 200:
            log_warning(f"Failed to fetch swipe page from {url}: HTTP {getattr(response, 'status_code', None)}")
            return [], None, False

        batch = self.parse_swipes_data(response.text)
        if not batch:
            return [], None, False

        # Calculate next_cursor defensively
        # Hardware uses the ID of the record to page backward
        try:
            if len(batch) > 1:
                next_cursor = int(batch[1][0]) + 19
            else:
                next_cursor = int(batch[0][0]) + 19
        except (ValueError, IndexError):
            next_cursor = None

        has_more = len(batch) >= 20 and next_cursor is not None
        return batch, next_cursor, has_more

    def get_maxid (self, response):
        """
        Retrieves the maximum record ID from the door controller board.
        Returns: max_record_id (int) or None if unable to retrieve.
        """
        self.verify_or_reauth()

        # Connect to the controller and navigate to the Swipe page.*****
        self.connect()
        # Navigate to the swipes page 
        url = f"{self.url}/ACT_ID_21"
        data = {'s4': 'Swipe'}
        response = self.get_httpresponse(url, data)
        if response is None or response.status_code != 200:
            log_warning(f"Failed to fetch initial swipe page from {url}: HTTP {getattr(response, 'status_code', None)}")
            return [], None, False  
        batch = self.parse_swipes_data(response.text)
        if not batch:
            return None
        try:
            max_record_id = max(int(row[0]) for row in batch)
            return max_record_id
        except (ValueError, IndexError):
            log_warning("Failed to determine max record ID from swipe data.")
            return None 




        
# # File: door_controller/common_lib/swipes.py

# def get_swipe_range(self, iterations, rec_id_start):
#     next_index = int(rec_id_start) + 20
#     swipes = []
    
#     # Pre-emptively verify session viability rather than unconditional force-connect
#     self.verify_or_reauth()

#     for x in range(1, iterations):
#         if x == 1:
#             url = self.url + '/ACT_ID_21'
#             data = {'s4': 'Swipe'}
#         else:
#             data = {'PC': next_index, 'PE': 0, 'PN': 'Next'}
#             url = self.url + '/ACT_ID_345'
            
#         try:
#             response = self.get_httpresponse(url, data)
#         except Exception as e:
#             log_error(f"Failed HTTP call on iteration {x}: {e}")
#             break

#         if not response or response.status_code != 200:
#             log_warning(f"Unexpected status code {getattr(response, 'status_code', None)} on iteration {x}")
#             break

#         if x > 1:
#             try:
#                 batch = self.parse_swipes_data(response.text)
#                 if batch:
#                     # FIX: Defensively retrieve next_index without assuming len(batch) > 1
#                     try:
#                         if len(batch) > 1:
#                             next_index = int(batch[1][0])
#                         else:
#                             next_index = int(batch[0][0])
#                     except (ValueError, IndexError):
#                         next_index += 20

#                     swipes = swipes + batch
#                     log_info(f"Swipes Count: {len(swipes)}")
#                 else:
#                     # FIX: Avoid IndexError when swipes has fewer than 20 items
#                     if len(swipes) >= 20:
#                         next_index = swipes[len(swipes) - 20][0]
#                     elif swipes:
#                         next_index = swipes[0][0]
#                     log_info(f"No Records returned, Next Index: {next_index}")
#                     break  # Stop paging if controller has no more data
#             except Exception as e:
#                 log_error(f"Error parsing swipe batch: {e}")
#                 break

#         # Slight pause between requests to prevent saturating the controller
#         time.sleep(0.3)

#     log_info(f"Records to add: {len(swipes)}")
#     return swipes