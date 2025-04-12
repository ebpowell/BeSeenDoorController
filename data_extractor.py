import time

from database import cls_sqlite
from fobs import key_fobs
from pg_database import postgres
from swipes import fob_swipes


class ww_data_extractor:
    def __init__(self, the_uname, the_pass, the_url, the_db):
        self.username = the_uname
        self.password = the_pass
        self.url =the_url
        self.obj_db = the_db
        self.iterations =  5

    def get_historical_fob_swipes(self):
        obj_db.purge_db('system_swipes')
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
        query = F"""SELECT max(record_id) FROM system_swipes where door_controller=('{self.url}')"""
        max_id = self.obj_db.get_maxid(query)
        obj_swipe = fob_swipes(self.url, self.username, self.password)
        lst_swipes = obj_swipe.get_new_swipes(5)
        self.obj_db.write_new(lst_swipes, obj_swipe.sql, max_id)
        print("get_new_swipes Complete")
        # Query the database to get the last recordid
        # Compare max_id tp the last valeu of lst_swipes
        # If so, continue pulling records
        target_id = max_id
        max_id = lst_swipes[20][0]
        if target_id < int(max_id):
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

                self.obj_db.write_new(lst_swipes, obj_swipe.sql, target_id)
                time.sleep(5)
                # ASK THE DATABASE WHERE TO RESTART
                max_id = lst_swipes[20][0]
                if max_id <= target_id:
                    break

    def get_system_fob_list(self):
        obj_db.purge_db('system_fobs')
        obj_keyfobs = key_fobs(self.url, username, password)
        lst_fobs = obj_keyfobs.get_keyfobs(5)
        self.obj_db.write_db(lst_fobs, obj_keyfobs.sql)
        print("get_new_swipes Complete")
        # Query the database to get the last recordid
        query = "SELECT max(record_id) FROM system_fobs"
         # where door_controller={self.url})"""
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
                        time.sleep(10)
            except:
                raise
            self.obj_db.write_db(lst_fobs, obj_keyfobs.sql)
            time.sleep(5)
            # ASK THE DATABASE WHERE TO RESTART
            max_id = self.obj_db.get_maxid(query)
            if max_id == 1:
                break


    # def get_authorizations(self)




if __name__=='__main__':
    username = "abc"
    password = "654321"
    urls = ["http://69.21.119.147", "http://69.21.119.148"]
    str_connect = ''
    obj_db = cls_sqlite('/home/ebpowell/GIT_REPO/ww_door_controller/door_controller_data')

    obj_extract = ww_data_extractor(username, password, urls[0], obj_db)
    # *******Download the list of swipes
    # for url in urls:
    #     obj_extract.get_historical_fob_swipes()

    #***** Get the most recent swipes
    # for url in urls:
    #     obj_swipe = fob_swipes(url, username, password)
    #     obj_swipe.get_new_swipes(5)

    # *** Get the list of keyfob id from the door controllers
    # obj_extract.get_system_fob_list()

    # *** Generate the access control status list

    #*** Push updated access control list


    #**** Get daily pull
    obj_extract.get_recent_fob_swipes()