"""
Door Controller - Get Fob List Tool

Retrieves the key fob list stored on hardware controllers via the API client module
and synchronizes with PostgreSQL database records.
"""
# File: door_controller/cli_synch_tools/get_foblist_from_controller.py

from door_controller.cli_synch_tools.get_fobs import sync_controller_fobs, main

def sync_fobs_for_controller(api_client, db, url):
    sync_controller_fobs(api_client, db, url, 0)

if __name__ == "__main__":
    main()