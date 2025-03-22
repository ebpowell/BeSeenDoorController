from door_controller import door_controller
import time

class key_fobs(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)
        self.sql = 'INSERT INTO system_fobs (record_id, fob_id) values'

    def parse_fobs_data(self, markup):
        tpl_row = []
        #Trim everything before the first data row in the table
        text_markup = markup[markup.find('<th>Operation</th></tr>'):]
        tag_len = len('<th>Operation</th></tr>')
        text_markup = text_markup[tag_len:text_markup.find('</table></p>')]
        tpl_murow = self.parse_tr_data(text_markup, r'<tr align=(.*?)</tr>', 4)
        [tpl_row.append([row[0], row[1]]) for row in tpl_murow]
        return  tpl_row

    def get_keyfobs(self, iterations):
        fobs = []
        # Add iterations, start val parameters
        data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        try:
            response = self.connect(data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s2':'Users'}
                elif x == 2:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    url = self.url + '/ACT_ID_325'
                    data = {'PC': f"000{(x*20)-19}",
                           'PE': f"000{(x*20)}",
                           'PN': 'Next'}
                else:
                    # Derive the PC value from the form element of the response text
                    # Update passed data
                    data = {'PC':f"000{(x*20)-19}",
                            'PE':f"000{(x*20)}",
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url+'/ACT_ID_325'
                    url = self.url + '/ACT_ID_325'
                try:
                    print(url)
                    print(x, data)
                    print(self.session.headers)
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                try:
                    if response.status_code ==200:
                        # Extract data from the returned page
                        batch = self.parse_fobs_data(response.text)
                        if batch:
                            fobs = fobs + batch
                        else:
                            print ("No Records returned")
                            # next_index =  swipes[len(swipes)-20][0]
                        time.sleep(self.timeout/3)
                except:
                    pass
            return fobs

    def get_keyfobs_range(self, iterations, start_rec):
        fobs = []
        print("Start:",start_rec)
        # Add iterations, start val parameters
        data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        try:
            response = self.connect(data)
        except:
            raise
        if response.status_code == 200:
            for x in range (1,iterations):
                if x == 1:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_1'
                    url = self.url + '/ACT_ID_21'
                    data = {'s2':'Users'}
                elif x == 2:
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url + '/ACT_ID_21'
                    url = self.url + '/ACT_ID_325'
                    data = {'PC': f"000{start_rec}",
                           'PE': f"000{(start_rec+20)}",
                           'PN': 'Next'}
                else:
                    # Derive the PC value from the form element of the response text
                    # Update passed data
                    data = {'PC':f"000{start_rec+((x*20)-19)}",
                            'PE':f"000{start_rec+(x*20)}",
                            'PN':'Next'}
                    # Update Request header to revise the referrer attribute
                    self.session.headers['Referer'] = self.url+'/ACT_ID_325'
                    url = self.url + '/ACT_ID_325'
                try:
                    print(url)
                    print(x, data)
                    print(self.session.headers)
                    response = self.get_httpresponse(url, data)
                except:
                    raise
                if x > 1:
                    try:
                        if response.status_code ==200:
                            # Extract data from the returned page
                            batch = self.parse_fobs_data(response.text)
                            if batch:
                                fobs = fobs + batch
                            else:
                                print ("No Records returned")
                                # next_index =  swipes[len(swipes)-20][0]
                            time.sleep(self.timeout/3)
                    except:
                        pass
            return fobs

    def get_fob_range(self, iterations, max_id):
        pass