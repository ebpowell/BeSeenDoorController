
from door_controller.pg_database import postgres
from door_controller.data_extractor import ww_data_extractor

if __name__=='__main__':
    '''
    Tool to periodically pull all of the swipes off of the door controllers at the Wentworth Clubhouse
    Designed to be run by the cron at whatever period is more appropriate (probably hourly)
    '''
    username = "abc"
    password = "654321"
    urls = ["http://69.21.119.147", "http://69.21.119.148"]
    str_connect = "host=192.168.50.150 dbname=wntworth_db user=wentworth_user password=ww_s3cret"
    obj_db = postgres(str_connect)
    # Intialize the slop table for the new records
    obj_db.insert_swipe_start_record()
    for url in urls:
        obj_extract = ww_data_extractor(username, password, url, obj_db)
        # Add records from controller
        obj_extract.get_recent_fob_swipes()
    # Copy records from slop table to the main table.
    obj_db.add_new_swipess()
