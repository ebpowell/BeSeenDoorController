"""
BeSeen Door Controller - Key Fob Management CLI Tool

Provides CLI commands to add, remove, and manage key fob permissions
by communicating through the BeSeen API client module.
"""

import argparse
from door_controller.cli_synch_tools.common import init_cli_tool
from door_controller.common_lib.utils import log_info


class FobManager:
    def __init__(self, api_client=None):
        self.config, self.db, self.api_client = init_cli_tool("BeSeen_driver")
        if api_client:
            self.api_client = api_client

    def add_fob(self, fob_id, owner_name):
        log_info(f"Adding Fob {fob_id} ({owner_name}) via API Client...")
        result = self.api_client.add_fob(fob_id, owner_name)
        log_info(f"API Result: {result}")
        return result

    def remove_fob(self, fob_id):
        log_info(f"Removing Fob {fob_id} via API Client...")
        result = self.api_client.delete_fob(fob_id)
        log_info(f"API Result: {result}")
        return result

    def set_fob_permissions(self, fob_id, permissions=None):
        log_info(f"Setting permissions for Fob {fob_id} via API Client...")
        record_id = self.api_client.get_fob_record_id(fob_id)
        if not record_id:
            log_info(f"Could not find hardware record ID for fob {fob_id}.")
            return None

        target_perms = permissions or [[1, True], [2, True]]
        result = self.api_client.update_fob_permissions(record_id, target_perms)
        log_info(f"API Result: {result}")
        return result


def main():
    parser = argparse.ArgumentParser(description="Door Controller Key Fob Management Driver")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    parser_add = subparsers.add_parser("add", help="Add a new key fob")
    parser_add.add_argument("fob_id", type=int, help="The ID of the fob")
    parser_add.add_argument("name", type=str, help="The name of the fob owner")

    parser_remove = subparsers.add_parser("remove", help="Remove an existing key fob")
    parser_remove.add_argument("fob_id", type=int, help="The ID of the fob to remove")

    parser_perms = subparsers.add_parser("set_permissions", help="Set permissions for a fob")
    parser_perms.add_argument("fob_id", type=int, help="The ID of the fob")

    args = parser.parse_args()
    manager = FobManager()

    if args.command == "add":
        manager.add_fob(args.fob_id, args.name)
    elif args.command == "remove":
        manager.remove_fob(args.fob_id)
    elif args.command == "set_permissions":
        manager.set_fob_permissions(args.fob_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()