
import sys
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.utils import load_config

def main():
    config = load_config()
    if not config:
        print("No config loaded")
        sys.exit(1)
    
    urls = config['settings']['urls']
    username = config['settings']['username']
    password = config['settings']['password']

    for url in urls:
        print(f"Connecting to {url}...")
        obj_keyfobs = key_fobs(url, username, password)
        # get_keyfobs takes iterations. Using 1 to get the first batch
        try:
            fobs = obj_keyfobs.get_keyfobs(2) 
            if fobs:
                print(f"Found {len(fobs)} fobs:")
                for fob in fobs:
                     # fob structure seems to be [record_id, fob_id, cidr, time] based on fobs.py parse_fobs_data
                     print(fob)
            else:
                print("No fobs found.")
        except Exception as e:
            print(f"Error fetching fobs: {e}")

if __name__ == '__main__':
    main()
