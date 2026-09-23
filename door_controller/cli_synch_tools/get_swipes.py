"""
Door Controller - Get Swipes Tool

Extracts card swipe activity from door controllers via the API client module
and updates the PostgreSQL database.
"""

import sys
from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info, load_config
from door_controller.common_lib.pg_database import postgres


# def load_config():
#     """
#     Load configuration settings from the default config file.
#     Returns:
#         dict: Configuration settings.
#     """
#     try:
#         config = load_config()
#         return config
#     except Exception as e:
#         log_info(f"Error loading configuration: {e}")
#         return {}

def main():
    config = load_config()
    db = postgres(config.get('settings', {}).get('postgres_connect_string')) if config.get('settings', {}).get('postgres_connect_string') else None
    api_client = init_cli_tool("get_swipes")
    log_info("Extracting Recent Swipes via API Module")

    is_all_mode = len(sys.argv) > 1 and sys.argv[1] == 'All'
    # Ge the start swipe record ID from the database to fetch swipes since that record
    urls = config.get('settings', {}).get('urls')
    for url in urls:

        query = F"""SELECT COALESCE(max(record_id), 0) FROM dataload.t_keyswipes_slop where door_controller_ip=('{url}')"""

        start_record_id = db.get_maxid(query) if db else 0
        log_info(f"Fetching swipes since record ID: {start_record_id}")
        swipes = api_client.get_swipes(controller_url=url, start_record_id=start_record_id)
        log_info(f"Retrieved {len(swipes)} swipe entries via API Client.")
        #obj_db.insert_swipe_record(lst_swipes)
        if db and swipes:
            db.insert_swipe_start_record()
            formatted_data = []
            for s in swipes:
                formatted_data.append([
                    s.get('record_id'),
                    s.get('fob_id'),
                    s.get('status'),
                    s.get('door'),
                    s.get('swipe_timestamp'),
                    s.get('door_controller_ip')
                ])
            db.insert_swipe_record(formatted_data)
            db.add_new_swipess()


if __name__ == '__main__':
    main()
