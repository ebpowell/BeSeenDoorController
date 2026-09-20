"""
Door Controller - Get Fob List Tool

Retrieves the key fob list stored on hardware controllers via the API client module
and synchronizes with PostgreSQL database records.
"""

from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info


def main():
    config, db, api_client = init_cli_tool("get_foblist_from_controller")
    log_info("Extracting FobID records via API Module")

    if db:
        db.insert_swipe_start_record()
        urls = config.get('settings', {}).get('urls', [])
        for url in urls:
            fobs = api_client.get_controller_fobs(url)
            log_info(f"Retrieved {len(fobs)} fobs from {url} via API Client.")
        db.move_fob_records()


if __name__ == '__main__':
    main()