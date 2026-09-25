"""
Door Controller - Get Fob List Tool

Retrieves the key fob list stored on hardware controllers via the API client module
and synchronizes with PostgreSQL database records.
"""
# File: door_controller/cli_synch_tools/get_foblist_from_controller.py

import time
from door_controller.common_lib.utils import log_info, log_error, extract_cidr
from door_controller.cli_synch_tools.common import init_cli_tool

def sync_fobs_for_controller(api_client, db, url):
    cidr = extract_cidr(url)
    log_info(f"Purging old slop records for controller CIDR {cidr}")
    if db:
        db.purge_fob_records(f"'{cidr}'")

    cursor = None
    total_fobs = 0
    page = 0
    max_pages = 100  # Circuit breaker (up to 2,000–4,000 fobs)

    log_info(f"Starting page sync for controller: {url}")

    while page < max_pages:
        try:
            res = api_client.get_controller_fobs(controller_url=url, cursor=cursor)
        except Exception as e:
            log_error(f"Error fetching fob page at cursor {cursor} from {url}: {e}")
            break

        fobs = res.get('fobs', [])
        if not fobs:
            log_info(f"No further fobs returned by controller {url}.")
            break

        if db:
            slop_data = [
                (f['record_id'], f['fob_id'], cidr)
                for f in fobs
            ]
            db.insert_fobs_slop_records(slop_data)

        total_fobs += len(fobs)
        log_info(f"Page {page + 1}: Retrieved {len(fobs)} fobs (Total: {total_fobs})")

        if not res.get('has_more'):
            break

        cursor = res.get('next_cursor')
        page += 1

        # Pacing: embedded controller breathing room
        time.sleep(0.3)

    if db and total_fobs > 0:
        log_info(f"Promoting {total_fobs} staged fobs from slop to system_fobs for {url}")
        db.move_fob_records()

    log_info(f"Finished sync for {url}. Total processed: {total_fobs}")

def main():
    config, db, api_client = init_cli_tool("get_foblist_from_controller")
    log_info("Extracting FobID records via API Module")

    urls = config.get('settings', {}).get('urls', [])
    for url in urls:
        sync_fobs_for_controller(api_client, db, url)

if __name__ == "__main__":
    main()