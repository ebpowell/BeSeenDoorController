"""
Door Controller - Get ACL Tool

Extracts Access Control List (ACL) data from controllers via the API client module
and updates PostgreSQL database records.
"""

from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info


def main():
    config, db, api_client = init_cli_tool("get_acl_from_controller")
    log_info("Extracting Access List via API Module")

    if db:
        db.purge_acl_records()
        record_ids = db.get_fob_records()
        urls = config.get('settings', {}).get('urls', [])
        for record_id in record_ids:
            for url in urls:
                fob_id = record_id[0]
                perms = api_client._get_data_manager(url).get_permissions_record(fob_id)
                if perms:
                    for perm_rec in perms:
                        db.insert_access_list_record(perm_rec)
                    break
        db.move_acl_records()


if __name__ == '__main__':
    main()
