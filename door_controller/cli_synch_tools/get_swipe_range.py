"""
Door Controller - Get Swipe Range Tool

Pulls door swipes within a specified range via the API client module.
"""

from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info


def main(start_id=None, url=None):
    config, db, api_client = init_cli_tool("get_swipe_range")
    log_info(f"Extracting Swipe Range starting from ID {start_id} via API Module")

    swipes = api_client.get_swipes(period='30d')
    log_info(f"Retrieved {len(swipes)} swipes via API Client.")

    if db and swipes:
        db.add_new_swipess()


if __name__ == '__main__':
    main(37586)
