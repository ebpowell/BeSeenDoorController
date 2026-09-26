"""
Door Controller - Get Swipes Tool

Extracts card swipe activity from door controllers via the API client module
and updates the PostgreSQL database.
"""

# File: door_controller/cli_synch_tools/get_swipes.py
import time
from door_controller.common_lib.utils import load_config, log_info, log_error
from door_controller.common_lib.pg_database import postgres
from door_controller.cli_synch_tools.common import init_cli_tool

def sync_controller_swipes(api_client, db, url, db_max_id):
    cursor = None
    total_added = 0
    page_count = 0
    max_pages = 50

    log_info(f"Syncing swipes for {url} since record ID: {db_max_id}")
    try:
        res = api_client.get_max_swipe_id(controller_url=url)
    except Exception as e:
        log_error(f"Failed to retrieve initial swipe page from {url}: {e}")
        return
   
    cursor = res.get('max_record_id', db_max_id) if res and isinstance(res, dict) else db_max_id
    while page_count < max_pages:
        try:
            res = api_client.get_swipes(controller_url=url, start_record_id=cursor)
        except Exception as e:
            log_error(f"Failed to retrieve swipe page at cursor {cursor} from {url}: {e}")
            break

        # Defensive guard against None or unexpected response types
        if not res or not isinstance(res, dict):
            log_error(f"Invalid or empty response received from API for {url}: {res}")
            break

        if res.get('status') == 'error':
            log_error(f"API returned error: {res.get('message', 'Unknown error')}")
            break

        swipes = res.get('swipes', [])
        if not swipes:
            log_info(f"No further records returned by controller {url}.")
            break

        # Filter out records already seen
        new_swipes = [s for s in swipes if int(s['record_id']) > db_max_id]
        if new_swipes and db:
            formatted_data = [
                [
                    s['record_id'],
                    s['fob_id'],
                    s['status'],
                    s['door_num'],
                    s['swipe_timestamp'],
                    s.get('door_controller_ip', url)
                ]
                for s in new_swipes
            ]
            db.insert_swipe_record(formatted_data)
            db.add_new_swipes()
            total_added += len(new_swipes)

        #if len(new_swipes) < len(swipes) or not res.get('has_more'):
        if len(new_swipes) < len(swipes) or not res.get('has_more'):
            break

        cursor = res.get('next_cursor')
        page_count += 1
        time.sleep(0.3)

    log_info(f"Sync complete for {url}. Total added: {total_added}")

def main():
    config, db, api_client = init_cli_tool("get_swipes")
    
    urls = config.get('settings', {}).get('urls', [])
    for url in urls:
        query = f"SELECT COALESCE(max(record_id), 0) FROM dataload.t_keyswipes_slop WHERE door_controller_ip='{url}'"
        start_record_id = db.get_maxid(query) if db else 0
        sync_controller_swipes(api_client, db, url, start_record_id)

if __name__ == "__main__":
    main()