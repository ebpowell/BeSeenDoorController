"""
Door Controller - Get Fobs Tool

Extracts key fob list activity from door controllers via the API client module
and updates the PostgreSQL database.
"""

# File: door_controller/cli_synch_tools/get_fobs.py
import time
from door_controller.common_lib.utils import load_config, log_info, log_error, extract_cidr
from door_controller.common_lib.pg_database import postgres
from door_controller.cli_synch_tools.common import init_cli_tool

def sync_controller_fobs(api_client, db, url, db_max_id):
    cursor = None
    total_added = 0
    page_count = 0
    max_pages = 50
    cidr = extract_cidr(url)

    if db:
        db.purge_fob_records(f"'{cidr}'")

    log_info(f"Syncing fobs for {url} since record ID: {db_max_id}")
    try:
        res = api_client.get_max_fob_id(controller_url=url)
    except Exception as e:
        log_error(f"Failed to retrieve initial fob page from {url}: {e}")
        return

    cursor = res.get('max_record_id', db_max_id) if res and isinstance(res, dict) else db_max_id
    while page_count < max_pages:
        try:
            res = api_client.get_fobs(controller_url=url, start_record_id=cursor)
        except Exception as e:
            log_error(f"Failed to retrieve fob page at cursor {cursor} from {url}: {e}")
            break

        # Defensive guard against None or unexpected response types
        if not res or not isinstance(res, dict):
            log_error(f"Invalid or empty response received from API for {url}: {res}")
            break

        if res.get('status') == 'error':
            log_error(f"API returned error: {res.get('message', 'Unknown error')}")
            break

        fobs = res.get('fobs', [])
        if not fobs:
            log_info(f"No further records returned by controller {url}.")
            break

        # Format fobs for slop database table
        if fobs and db:
            slop_data = [
                (
                    f['record_id'] if isinstance(f, dict) else f[0],
                    f['fob_id'] if isinstance(f, dict) else f[1],
                    cidr
                )
                for f in fobs
            ]
            db.insert_fobs_slop_records(slop_data)
            total_added += len(fobs)

        if not res.get('has_more'):
            break

        cursor = res.get('next_cursor')
        page_count += 1
        time.sleep(0.3)

    if db and total_added > 0:
        log_info(f"Promoting {total_added} staged fobs from slop to system_fobs for {url}")
        db.move_fob_records()

    log_info(f"Sync complete for {url}. Total added: {total_added}")

def main():
    config, db, api_client = init_cli_tool("get_fobs")

    urls = config.get('settings', {}).get('urls', [])
    for url in urls:
        cidr = extract_cidr(url)
        query = f"SELECT COALESCE(max(record_id), 0) FROM dataload.fobs_slop WHERE controller_ip='{cidr}'"
        start_record_id = db.get_maxid(query) if db else 0
        sync_controller_fobs(api_client, db, url, start_record_id)

if __name__ == "__main__":
    main()
