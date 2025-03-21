from swipes import fob_swipes
from fobs import key_fobs
import sqlite3
import time
from database import cls_sqlite

if __name__=='__main__':
    username = "abc"
    password = "654321"
    urls = ["http://69.21.119.147", "http://69.21.119.148"]
    obj_db = cls_sqlite('/home/ebpowell/GIT_REPO/ww_door_controller/door_controller_data')
    iterations = 5

    # obj_keyfobs = key_fobs(url, username, password, db_path)
    # # lst_fobs = obj_keyfobs.get_keyfobs_range(10, 20)
    # lst_fobs = obj_keyfobs.get_keyfobs(5)
    # print (lst_fobs)
    # obj_keyfobs.write_db(lst_fobs)


    # obj_db.purge_db('system_swipes')
    # for url in urls:
    obj_swipe = fob_swipes(urls[1], username, password)
    lst_swipes = obj_swipe.get_new_swipes(5)
    obj_db.write_db(lst_swipes, obj_swipe.sql)
    print("get_new_swipes Complete")
    # Query the database to get the last recordid
    query = "SELECT min(record_id) FROM system_swipes where door_controller='http://69.21.119.148'"
    max_id = obj_db.get_maxid(query)
    print("Starting ID:", max_id)
    for x in range(0, 800):
        int_add_cnt = 0
        try:
            for y in range(0, 5):
                try:
                    print ("get_swipe_range Connect Attempt:", y, 'Pass:',x, 'Starting Record ID', max_id)
                    lst_swipes = obj_swipe.get_swipe_range(iterations, max_id)
                    break
                except:
                    pass
                    time.sleep(10)
        except:
                raise
        obj_db.write_db(lst_swipes, obj_swipe.sql)
        time.sleep(5)
        # ASK THE DATABASE WHERE TO RESTART
        max_id = obj_db.get_maxid(query)
        if max_id == 1:
            break