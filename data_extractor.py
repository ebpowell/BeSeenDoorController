from swipes import fob_swipes
from fobs import key_fobs
import time

if __name__=='__main__':
    username = "abc"
    password = "654321"
    url = "http://69.21.119.148"

    # obj_keyfobs = key_fobs(url, username, password, '/home/ebpowell/GIT_REPO/ww_door_controller/door_controller_data')
    # # lst_fobs = obj_keyfobs.get_keyfobs_range(10, 20)
    # lst_fobs = obj_keyfobs.get_keyfobs(5)
    # print (lst_fobs)
    # obj_keyfobs.write_db(lst_fobs)


    obj_swipe = fob_swipes(url, username, password, '/home/ebpowell/GIT_REPO/ww_door_controller/door_controller_data')
    # lst_swipes = obj_swipe.get_new_swipes(5)
    for x in range(0, 800):
        try:
            lst_swipes = obj_swipe.get_swipe_range(5, 24908-(x*20))
        except:
            raise
        time.sleep(5)
        obj_swipe.write_db(lst_swipes)