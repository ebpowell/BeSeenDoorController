
import time
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.utils import log_info, log_error

class fob_swipes(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)

    def get_swipe_range(self, iterations, rec_id_start):
        next_index = int(rec_id_start)+20
        swipes = []
        try:
            response = self.connect()
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                if x == 1:
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                else:
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    url = self.url + '/ACT_ID_345'
                try:
                    response = self.get_httpresponse(url, data)
                except Exception as e:
                    log_error(e)            
                    raise e
                if x > 1:
                    try:
                        if response.status_code ==200:
                            # Extract data from the returned page
                            batch = self.parse_swipes_data(response.text)
                            if batch:
                                next_index = int(batch[1][0])
                                swipes = swipes + batch
                                log_info(f"Swipes Count: {len(swipes)}")
                        else:
                            next_index =  swipes[len(swipes)-20][0]
                            log_info(f"No Records returned, Next Index: {next_index}")
                            time.sleep(5)

                    except Exception as e:
                        log_error(e)
                        raise e

        log_info(f"Records to add: {len(swipes)}")
        return swipes

    # def get_new_swipes(self, iterations):
    #     next_index = 0
    #     swipes = []
    #     try:
    #         response = self.connect()
    #     except:
    #         raise
    #     if response.status_code == 200:
    #         for x in range (1,iterations):
    #             if x == 1:
    #                 # Update Request header to revise the referrer attribute
    #                 headers={'Referer': self.url + '/ACT_ID_1'}
    #                 url = self.url + '/ACT_ID_21'
    #                 data = {'s4':'Swipe'}
    #             elif x == 2:
    #                 # Update passed data
    #                 data = {'PC': next_index,
    #                         'PE': 0,
    #                         'PN': 'Next'}
    #                 # Update Request header to revise the referrer attribute
    #                 url = self.url + '/ACT_ID_345'
    #                 headers={'Referer': self.url + '/ACT_ID_21'}
    #             else:
    #                 # Update passed data
    #                 data = {'PC':next_index,
    #                         'PE':0,
    #                         'PN':'Next'}
    #                 # Update Request header to revise the referrer attribute
    #                 url = self.url + '/ACT_ID_345'
    #                 headers={'Referer': self.url + '/ACT_ID_21'}
    #             try:
    #                 response = self.get_httpresponse(url, data)
    #             except:
    #                 raise
    #             try:
    #                 if response.status_code ==200:
    #                     # Extract data from the returned page
    #                     batch = self.parse_swipes_data(response.text)
    #                     if batch:
    #                         next_index = int(batch[1][0])
    #                         swipes = swipes + batch
    #                         print('Parse Records Success', 'Next Index:', next_index)
    #                     else:
    #                         next_index =  swipes[len(swipes)-20][0]
    #                         print("No Records returned", 'Next Index:', next_index)
    #                     time.sleep(5)
    #             except:
    #                 pass
    #     return swipes

    def parse_swipes_data(self, markup):
        tpl_row = []
        #Trim everything before the first data row in the table
        text_markup = markup[markup.find('<th>DateTime</th></tr>'):]
        tag_len = len('<th>DateTime</th></tr>')
        text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
        tpl_murow = self.parse_tr_data(text_markup, r'<tr class=(.*?)</tr>', 5)
        # Parse the list of rows for the data we want
        for row in tpl_murow:
            door_row = row[3]
            splt_row = door_row.split('IN[#')
            splt_row[1] = splt_row[1][0:1]
            the_row = [row[0], row[1], splt_row[0].strip(), splt_row[1], row[4], self.url]
            tpl_row.append(the_row)
        return tpl_row
