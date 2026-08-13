import time

from door_controller.common_lib.door_controller import door_controller


class fob_swipes(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)
        self.sql = "INSERT INTO door_controller.t_keyswipes (record_id, fob_id, status, door, swipe_timestamp, door_controller_ip) values"

    def get_swipe_range(self, iterations, rec_id_start):
        # Add iterations, start val parameters
        next_index = int(rec_id_start)+20
        swipes = []
        try:
            response = self.connect()
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                print('get_swipes_range X value:', x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    headers ={'Referer': self.url + '/ACT_ID_1'}
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    headers ={'Referer': self.url + '/ACT_ID_21'}
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    headers={'Referer':  self.url + '/ACT_ID_21'}
                try:
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                if x > 1:
                    try:
                        if response.status_code ==200:
                            # Extract data from the returned page
                            batch = self.parse_swipes_data(response.text)
                            if batch:
                                next_index = int(batch[1][0])
                                swipes = swipes + batch
                                print('Pass:',x, 'Parse Records Success', 'Batch Record Count:',
                                        len(batch),'Next Index:', next_index)
                                print('Swipes Count:', len(swipes))
                        else:
                            next_index =  swipes[len(swipes)-20][0]
                            print("No Records returned", 'Next Index:', next_index)
                            time.sleep(5)
                    except:
                        pass
        print('Records to add:',len(swipes))
        return swipes

    def get_new_swipes(self, iterations):
        next_index = 0
        swipes = []
        try:
            response = self.connect()
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    headers={'Referer': self.url + '/ACT_ID_1'}
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    headers={'Referer': self.url + '/ACT_ID_21'}
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    headers={'Referer': self.url + '/ACT_ID_21'}
                try:
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                try:
                    if response.status_code ==200:
                        # Extract data from the returned page
                        batch = self.parse_swipes_data(response.text)
                        if batch:
                            next_index = int(batch[1][0])
                            swipes = swipes + batch
                            print('Parse Records Success', 'Next Index:', next_index)
                        else:
                            next_index =  swipes[len(swipes)-20][0]
                            print("No Records returned", 'Next Index:', next_index)
                        time.sleep(5)
                except:
                    pass
        return swipes

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
