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
        max_id = lst_swipes[rec_count-1][0]
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
                        time.sleep(5)
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
    str_connect = "host=192.168.50.110 dbname=wntworth_db user=wentworth_user password=ww_s3cret"
    # obj_db = cls_sqlite('/home/ebpowell/GIT_REPO/ww_door_controller/door_controller_data')
    obj_db = postgres(str_connect)
    # INitial the slop table
    obj_db.insert_swipe_start_record()
    for url in urls:
        obj_extract = ww_data_extractor(username, password, url, obj_db)
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
        # Add records from controller
        obj_extract.get_recent_fob_swipes()
    # TO DO: MOve records from slop table to the main table.
    obj_db.add_new_swipess()