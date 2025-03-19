from door_controller import door_controller
import time

class fob_swipes(door_controller):
    def __init__(self, url, username, password, dbpath):
        super().__init__(url, username, password, dbpath)
        self.sql = "INSERT INTO system_swipes (record_id, fob_id, status, door, timestamp) values"

    def get_swipe_range(self, iterations, rec_id_start):
        # Add iterations, start val parameters
        next_index = rec_id_start
        # data = {'s2': 'Users'}
        swipes = []
        connect_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        print(self.session.headers)
        print(connect_data)
        try:
            response = self.connect(connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                print(x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                    print(url)
                    print(self.session.headers)
                    print(data)
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    print(url)
                    print(self.session.headers)
                    print(data)
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] =  self.url + '/ACT_ID_345'
                    print(url)
                    print(self.session.headers)
                    print(data)
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
                                print(next_index)
                                print(batch)
                                swipes = swipes + batch
                            else:
                                print ("No Records returned")
                                next_index =  swipes[len(swipes)-20][0]
                            time.sleep(self.timeout/3)
                    except:
                        pass
        return swipes

    def get_new_swipes(self, iterations):
        swipes = []
        connect_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        print(self.session.headers)
        print(connect_data)
        try:
            response = self.connect(connect_data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                print(x)
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s4':'Swipe'}
                    print(self.session.headers)
                    print(data)
                elif x == 2:
                    # Update passed data
                    data = {'PC': next_index,
                            'PE': 0,
                            'PN': 'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    print(self.session.headers)
                    print(data)
                else:
                    # Update passed data
                    data = {'PC':next_index,
                            'PE':0,
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    url = self.url + '/ACT_ID_345'
                    self.session.headers['Referer'] =  self.url + '/ACT_ID_21'
                    print(self.session.headers)
                    print(data)
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
                            print(next_index)
                            print(batch)
                            swipes = swipes + batch
                        else:
                            print ("No Records returned")
                            next_index =  swipes[len(swipes)-20][0]
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
            the_row = [row[0], row[1], splt_row[0].strip(), splt_row[1], row[4]]
            tpl_row.append(the_row)
        return tpl_row
