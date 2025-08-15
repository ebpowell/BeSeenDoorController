
import time
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.swipes import fob_swipes


class ww_data_extractor:
    def __init__(self, the_uname, the_pass, the_url, the_db):
        self.username = the_uname
        self.password = the_pass
        self.url =the_url
        self.obj_db = the_db
        self.iterations =  5

    def get_historical_fob_swipes(self):
        self.obj_db.purge_db('system_swipes')
        obj_swipe = fob_swipes(self.url, self.username, self.password)
        lst_swipes = obj_swipe.get_new_swipes(5)
        self.obj_db.write_db(lst_swipes, obj_swipe.sql)
        print("get_new_swipes Complete")
        # Query the database to get the last recordid
        query = F""""SELECT min(record_id) FROM system_swipes where door_controller=('{self.url}'"""
        max_id = self.obj_db.get_maxid(query)
        print("Starting ID:", max_id)
        for x in range(0, 21):
            try:
                for y in range(0, 5):
                    try:
                        print("get_swipe_range Connect Attempt:", y, 'Pass:', x, 'Starting Record ID', max_id)
                        lst_swipes = obj_swipe.get_swipe_range(self.iterations, max_id)
                        break
                    except:
                        pass
                        time.sleep(10)
            except:
                raise
            self.obj_db.write_db(lst_swipes, obj_swipe.sql)
            time.sleep(5)
            # ASK THE DATABASE WHERE TO RESTART
            max_id = self.obj_db.get_maxid(query)
            if max_id == 1:
                break

    def get_recent_fob_swipes(self):
        # Function to pull only Fob swipes added tp system since last poll to keep external
        # database current
        # Trick is that database is behind the controller BUT the controller returns records from newest to oldest. That
        # means we are work backward until we intesect the existing result-set in the database.
        # When the Fob Supplied list returns a starting value that is older than the starting value in the database,
        # the process needs to termiinate, thus the db_max_id should be static for this function.
        query = F"""SELECT max(record_id) FROM dataload.t_keyswipes_slop where door_controller_ip=('{self.url}')"""
        # Store the maximum record value in db at start of the process to refer to later
        db_max_id = self.obj_db.get_maxid(query)
        obj_swipe = fob_swipes(self.url, self.username, self.password)
        lst_swipes = obj_swipe.get_new_swipes(5)
        # new Swipes starts at newest swipe and works backwards
        self.obj_db.insert_swipe_record(lst_swipes, db_max_id)
        print("get_new_swipes Complete")
        rec_count = len(lst_swipes)
        if rec_count > 0:
            max_id = lst_swipes[rec_count-1][0]
        else:
            return
        # if target_id < int(db_max_id):
        if db_max_id < int(max_id):
            print("Starting ID:", max_id)
            for x in range(0, 21):
                # try:
                for y in range(0, 5):
                    try:
                        print("get_swipe_range Connect Attempt:", y, 'Pass:', x, 'Starting Record ID', max_id)
                        lst_swipes = obj_swipe.get_swipe_range(self.iterations, max_id)
                        break
                    except Exception as e:
                        print(e)
                        # raise e
                        pass
                        time.sleep(5)

                self.obj_db.insert_swipe_record(lst_swipes, db_max_id)
                time.sleep(5)
                # Pull next batch of records where the previous batch ended
                rec_count = len(lst_swipes)
                if rec_count > 0:
                    print('Records Returned: ',rec_count)
                    max_id = lst_swipes[rec_count-1][0]
                print('Max_id:', max_id)
                # db_max_id = self.obj_db.get_maxid(query)
                if int(max_id) <= db_max_id:
                    break

    def get_system_fob_list(self):
        cidr = self.url[7:] + '/32'
        cidr = "'{}'".format(cidr)
        self.obj_db.purge_fob_records(cidr)
        obj_keyfobs = key_fobs(self.url, self.username, self.password)
        lst_fobs = obj_keyfobs.get_keyfobs(5)
        self.obj_db.write_db(lst_fobs, obj_keyfobs.sql)
        # Query the database to get the last recordid
        query = (f"SELECT max(record_id) FROM dataload.fobs_slop "
                 f"where controller_ip={cidr}")
        max_id = self.obj_db.get_maxid(query)-20
        print("Starting ID:", max_id)
        for x in range(0, 20):
            try:
                for y in range(0, 5):
                    try:
                        print("get_swipe_range Connect Attempt:", y, 'Pass:', x, 'Starting Record ID', max_id)
                        lst_fobs = obj_keyfobs.get_keyfobs_range(self.iterations, max_id)
                        break
                    except:
                        pass
                        time.sleep(5)
            except:
                raise
            self.obj_db.write_db(lst_fobs, obj_keyfobs.sql)
            time.sleep(5)
            # ASK THE DATABASE WHERE TO RESTART
            max_id = self.obj_db.get_maxid(query)
            if max_id == 1:
                break


    def get_permissions_record(self, record_id):
        '''
        Function to extract and return the permissions for a FobID from the Door Controller

        :param record_id:
        :return:
        '''
        data = {'username': self.username,
                'pwd': self.password,
                'logid': '20101222'}
        # E0=Edit (where the number is record_id - 1
        # Ref = ACT_ID_21
        # URL = http://69.21.119.148/ACT_ID_324
        obj_keyfobs = key_fobs(self.url, self.username, self.password)
        response = obj_keyfobs.connect(data)
        if response.status_code==200:
            response= obj_keyfobs.users_page()
            if response.status_code==200:
                data = {F"""E{record_id - 1}""": 'Edit'}
                # Update Request header to revise the referrer attribute
                obj_keyfobs.session.headers['Referer'] = self.url + '/ACT_ID_21'
                url = self.url + '/ACT_ID_324'
                try:
                    response = obj_keyfobs.get_httpresponse(url, data)
                    return obj_keyfobs.parse_permissions(response.text)
                except:
                    raise