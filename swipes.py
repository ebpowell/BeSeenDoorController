import time

from door_controller import door_controller


class fob_swipes(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)
        self.sql = "INSERT INTO system_swipes (record_id, fob_id, status, door, timestamp, door_controller) values"

    def get_swipe_range(self, iterations, rec_id_start):
        # Add iterations, start val parameters
        next_index = rec_id_start+20
        # data = {'s2': 'Users'}
        swipes = []
        connect_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        # print(rec_id_start)
        # print(self.session.headers)
        # print(connect_data)
        try:
            response = self.connect(connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                print('get_swipes_range X value:', x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] =  self.url + '/ACT_ID_345'
                for y in range (1, 5):
                    try:
                        print('Connect Attempt:', y)
                        response = self.get_httpresponse(url, data)
                        print("Success")
                        # print(url)
                        # print(self.session.headers)
                        # print(x, data)
                        break
                    except:
                        # after two tries, move to the next batch of records
                        time.sleep(self.timeout)
                        pass
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
                                # next_index =  swipes[len(swipes)-20][0]
                                print(response.text)
                                print("No Records returned", 'Next Index:', next_index)
                                # This connection is f&cked....write the records and try again
                                break
                            time.sleep(self.timeout/3)
                        else:
                            print(response.status_code)
                    except:
                        pass
        print('Records to add:',len(swipes))
        return swipes

    def get_new_swipes(self, iterations):
        next_index = 0
        swipes = []
        connect_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        # print(self.session.headers)
        # print(connect_data)
        try:
            response = self.connect(connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] =  self.url + '/ACT_ID_21'
                try:
                    # print(url)
                    # print(self.session.headers)
                    # print(x, data)
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
