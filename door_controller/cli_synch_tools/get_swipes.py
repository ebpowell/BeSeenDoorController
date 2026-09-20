"""
Door Controller - Get Swipes Tool

Extracts card swipe activity from door controllers via the API client module
and updates the PostgreSQL database.
"""

import sys
from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info


def main():
    config, db, api_client = init_cli_tool("get_swipes")
    log_info("Extracting Recent Swipes via API Module")

    is_all_mode = len(sys.argv) > 1 and sys.argv[1] == 'All'
    period = '30d' if is_all_mode else '24h'

    swipes = api_client.get_swipes(period=period)
    log_info(f"Retrieved {len(swipes)} swipe entries via API Client.")

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
