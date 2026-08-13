import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from door_controller.common_lib.utils import log_info

logger = logging.getLogger(__name__)

class GoogleCalendarSync:
    """
    Integrates PostgreSQL clubhouse_reservations table with Google Calendar via Service Account authentication.
    Follows system-centric pattern outlined in gemini_description.
    """
    def __init__(
        self,
        service_account_file: Optional[str] = None,
        calendar_id: Optional[str] = None,
        timezone: str = "America/New_York",
        db_manager: Any = None
    ):
        self.service_account_file = service_account_file or os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"
        )
        self.calendar_id = calendar_id or os.environ.get("CALENDAR_ID", "primary")
        self.timezone = timezone
        self.db_manager = db_manager
        self.calendar_service = None

        if GOOGLE_API_AVAILABLE and os.path.exists(self.service_account_file):
            try:
                scopes = ['https://www.googleapis.com/auth/calendar']
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_file, scopes=scopes
                )
                self.calendar_service = build('calendar', 'v3', credentials=creds)
                log_info(f"GoogleCalendarSync: Initialized Google Calendar service with {self.service_account_file}")
            except Exception as e:
                log_info(f"GoogleCalendarSync Warning: Could not initialize Google Calendar service: {e}")

    def format_event_payload(self, res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats a database reservation dictionary into a Google Calendar API event body.
        """
        res_id = res.get('reservation_id')
        event_type = res.get('event_type', 'Private Event')
        address = res.get('address', f"Property {res.get('property_id')}")
        owner_name = res.get('owner_name', '')
        event_name = res.get('event_name', '')
        event_desc = res.get('event_description', '')
        res_date = res.get('reservation_date')
        from_time = res.get('from_time', '08:00:00')
        to_time = res.get('to_time', '23:00:00')
        fee = res.get('fee', 0.0)
        early_setup = res.get('early_setup', False)
        reschedule_required = res.get('reschedule_required', False)

        # Parse date and times
        if isinstance(res_date, str):
            res_date_str = res_date
        elif hasattr(res_date, 'strftime'):
            res_date_str = res_date.strftime('%Y-%m-%d')
        else:
            res_date_str = str(res_date)

        from_time_str = from_time.strftime('%H:%M:%S') if hasattr(from_time, 'strftime') else str(from_time or '08:00:00')
        to_time_str = to_time.strftime('%H:%M:%S') if hasattr(to_time, 'strftime') else str(to_time or '23:00:00')

        if len(from_time_str) == 5:
            from_time_str += ":00"
        if len(to_time_str) == 5:
            to_time_str += ":00"

        start_iso = f"{res_date_str}T{from_time_str}"
        end_iso = f"{res_date_str}T{to_time_str}"

        if event_type == 'HOA Event':
            summary = f"HOA Event: {event_name or 'Board Meeting'}"
            description = (
                f"Official Board of Directors HOA Event\n"
                f"Event Name: {event_name or 'N/A'}\n"
                f"Details: {event_desc or 'None'}\n"
                f"Date: {res_date_str}\n"
                f"Time: {from_time_str} - {to_time_str}\n"
                f"Reservation ID: #{res_id}"
            )
        else:
            summary = f"Clubhouse Reservation - {address}"
            description = (
                f"Clubhouse Reservation for {address}\n"
                f"Property Owner: {owner_name or 'N/A'}\n"
                f"Event Type: {event_type}\n"
                f"Fee: ${float(fee or 0):.2f}\n"
                f"Early Setup: {'Yes' if early_setup else 'No'}\n"
                f"Status: {'⚠️ Reschedule Required (HOA Conflict)' if reschedule_required else 'Active'}\n"
                f"Reservation ID: #{res_id}"
            )

        event_payload = {
            'summary': summary,
            'description': description,
            'location': 'Community Clubhouse',
            'start': {
                'dateTime': start_iso,
                'timeZone': self.timezone,
            },
            'end': {
                'dateTime': end_iso,
                'timeZone': self.timezone,
            },
            'extendedProperties': {
                'private': {
                    'reservation_id': str(res_id),
                    'event_type': str(event_type),
                    'reschedule_required': str(reschedule_required)
                }
            }
        }
        return event_payload

    def sync_reservations(self, dry_run: bool = False) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        Syncs all reservations from PostgreSQL database to Google Calendar.
        Returns tuple of (created_count, updated_count, synced_events_list).
        """
        if not self.db_manager:
            from door_controller.key_management_application.db_manager import FobDatabaseManager
            self.db_manager = FobDatabaseManager()

        reservations = self.db_manager.list_reservations()
        created_count = 0
        updated_count = 0
        results = []

        # Build existing Google Calendar events map by reservation_id if service is available
        existing_gcal_events = {}
        if self.calendar_service and not dry_run:
            try:
                events_result = self.calendar_service.events().list(
                    calendarId=self.calendar_id,
                    maxResults=2500
                ).execute()
                items = events_result.get('items', [])
                for item in items:
                    ext_props = item.get('extendedProperties', {}).get('private', {})
                    res_id_prop = ext_props.get('reservation_id')
                    if res_id_prop:
                        existing_gcal_events[str(res_id_prop)] = item
            except Exception as e:
                log_info(f"GoogleCalendarSync Warning: Could not list existing GCal events: {e}")

        for res in reservations:
            res_id_str = str(res.get('reservation_id'))
            payload = self.format_event_payload(res)

            if dry_run or not self.calendar_service:
                log_info(f"[DRY-RUN] Would sync Reservation #{res_id_str} ({payload['summary']}) to Google Calendar")
                results.append({'reservation_id': res_id_str, 'action': 'dry_run', 'payload': payload})
                created_count += 1
                continue

            try:
                if res_id_str in existing_gcal_events:
                    gcal_event = existing_gcal_events[res_id_str]
                    gcal_id = gcal_event['id']
                    updated_event = self.calendar_service.events().update(
                        calendarId=self.calendar_id,
                        eventId=gcal_id,
                        body=payload
                    ).execute()
                    log_info(f"GoogleCalendarSync: Updated GCal Event {gcal_id} for Reservation #{res_id_str}")
                    updated_count += 1
                    results.append({'reservation_id': res_id_str, 'action': 'updated', 'gcal_id': gcal_id, 'link': updated_event.get('htmlLink')})
                else:
                    created_event = self.calendar_service.events().insert(
                        calendarId=self.calendar_id,
                        body=payload
                    ).execute()
                    gcal_id = created_event.get('id')
                    log_info(f"GoogleCalendarSync: Created GCal Event {gcal_id} for Reservation #{res_id_str}")
                    created_count += 1
                    results.append({'reservation_id': res_id_str, 'action': 'created', 'gcal_id': gcal_id, 'link': created_event.get('htmlLink')})
            except Exception as e:
                log_info(f"GoogleCalendarSync Error syncing Reservation #{res_id_str}: {e}")
                results.append({'reservation_id': res_id_str, 'action': 'error', 'error': str(e)})

        return created_count, updated_count, results
