#!/usr/bin/env python3
"""
Google Calendar Integration Tool for BeSeen Door Controller.
Pushes clubhouse reservations from PostgreSQL database table (key_fobs.clubhouse_reservations)
to Google Calendar via a Google Service Account.

Based on system-centric design guidance in gemini_description.
"""

import os
import sys
import json
import argparse
import logging
from door_controller.common_lib.gcal_sync import GoogleCalendarSync, GOOGLE_API_AVAILABLE
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.utils import load_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    config = load_config() or {}
    gcal_cfg = config.get("gcal", {})
    settings_cfg = config.get("settings", {})

    default_sa_file = (
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        or gcal_cfg.get("service_account_file")
        or settings_cfg.get("gcal_service_account_file")
        or "service_account.json"
    )
    default_calendar_id = (
        os.environ.get("CALENDAR_ID")
        or gcal_cfg.get("calendar_id")
        or settings_cfg.get("gcal_calendar_id")
        or "primary"
    )
    default_timezone = (
        os.environ.get("GCAL_TIMEZONE")
        or gcal_cfg.get("timezone")
        or settings_cfg.get("gcal_timezone")
        or "America/New_York"
    )

    parser = argparse.ArgumentParser(
        description="BeSeen Door Controller - Google Calendar Integration Tool"
    )
    parser.add_argument(
        "--service-account-file",
        default=default_sa_file,
        help=f"Path to Google Service Account JSON key file (default from config: {default_sa_file})"
    )
    parser.add_argument(
        "--calendar-id",
        default=default_calendar_id,
        help=f"Target Google Calendar ID (default from config: {default_calendar_id})"
    )
    parser.add_argument(
        "--timezone",
        default=default_timezone,
        help=f"Timezone string for calendar events (default from config: {default_timezone})"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview formatted Google Calendar payloads without calling Google Calendar API"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output sync results as JSON"
    )

    args = parser.parse_args()

    print("=====================================================")
    print(" BeSeen Door Controller - Google Calendar Sync Tool")
    print("=====================================================")
    print(f"Service Account File: {args.service_account_file}")
    print(f"Calendar ID:          {args.calendar_id}")
    print(f"Timezone:             {args.timezone}")
    print(f"Dry-Run Mode:         {'ENABLED' if args.dry_run else 'DISABLED'}")
    print("-----------------------------------------------------")

    if not GOOGLE_API_AVAILABLE:
        print("⚠️ Warning: google-auth and google-api-python-client packages are not installed.")
        print("To enable live API push, run: pip install google-auth google-api-python-client\n")

    if not os.path.exists(args.service_account_file) and not args.dry_run:
        print(f"⚠️ Notice: Service Account file '{args.service_account_file}' not found.")
        print("Running in preview / dry-run mode...\n")
        args.dry_run = True

    try:
        db_mgr = FobDatabaseManager()
        syncer = GoogleCalendarSync(
            service_account_file=args.service_account_file,
            calendar_id=args.calendar_id,
            timezone=args.timezone,
            db_manager=db_mgr
        )

        created, updated, results = syncer.sync_reservations(dry_run=args.dry_run)

        if args.json:
            print(json.dumps({'created': created, 'updated': updated, 'results': results}, indent=2))
        else:
            print("\nSync Summary:")
            print(f"  • Created: {created}")
            print(f"  • Updated: {updated}")
            print(f"  • Total Processed: {len(results)}")
            print("=====================================================\n")

            for item in results:
                action = item.get('action')
                res_id = item.get('reservation_id')
                if action == 'dry_run':
                    p = item.get('payload', {})
                    print(f"[DRY-RUN] Res #{res_id}: Summary='{p.get('summary')}' | Start={p.get('start', {}).get('dateTime')}")
                elif action in ('created', 'updated'):
                    print(f"[{action.upper()}] Res #{res_id}: GCal ID={item.get('gcal_id')}")
                elif action == 'error':
                    print(f"[ERROR] Res #{res_id}: {item.get('error')}")

    except Exception as e:
        print(f"❌ Error executing Google Calendar sync: {e}")
        if "connection to server" in str(e).lower() or "connection timed out" in str(e).lower():
            print("\n💡 Hint: PostgreSQL database host is unreachable. Ensure the database server is running or set the DB_HOST environment variable.")
        sys.exit(1)

if __name__ == '__main__':
    main()
