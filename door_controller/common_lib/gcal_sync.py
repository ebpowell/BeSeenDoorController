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

from door_controller.common_lib.utils import log_info, load_config

logger = logging.getLogger(__name__)

class GoogleCalendarSync:
    """
    Integrates PostgreSQL clubhouse_reservations table with Google Calendar via Service Account authentication.
    Follows system-centric pattern outlined in gemini_description. Reads configuration from common config file (config.yaml).
    """
    def __init__(
        self,
        service_account_file: Optional[str] = None,
        calendar_id: Optional[str] = None,
        timezone: Optional[str] = None,
        db_manager: Any = None
    ):
        config = load_config() or {}
        gcal_cfg = config.get("gcal", {})
        settings_cfg = config.get("settings", {})

        # Service Account File resolution
        sa_file = (
            service_account_file
            or os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
            or gcal_cfg.get("service_account_file")
            or settings_cfg.get("gcal_service_account_file")
            or "service_account.json"
        )
        if not os.path.exists(sa_file):
            candidate_dirs = [
                os.getenv("APP_CONFIG_DIR"),
                "./config",
                "/app/config",
                "/etc/door_controller",
                os.path.expanduser("~/.config/door_controller"),
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ]
            for c_dir in candidate_dirs:
                if c_dir:
                    cand_path = os.path.join(c_dir, os.path.basename(sa_file))
                    if os.path.exists(cand_path):
                        sa_file = cand_path
                        break
                    cand_sub_path = os.path.join(c_dir, sa_file)
                    if os.path.exists(cand_sub_path):
                        sa_file = cand_sub_path
                        break

        self.service_account_file = sa_file

        # Calendar ID resolution
        self.calendar_id = (
            calendar_id
            or os.environ.get("CALENDAR_ID")
            or gcal_cfg.get("calendar_id")
            or settings_cfg.get("gcal_calendar_id")
            or "primary"
        )

        # Timezone resolution
        self.timezone = (
            timezone
            or os.environ.get("GCAL_TIMEZONE")
            or gcal_cfg.get("timezone")
            or settings_cfg.get("gcal_timezone")
            or "America/New_York"
        )

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

    def is_eligible_for_sync(self, res: Dict[str, Any]) -> bool:
        """
        Determines if a reservation is eligible to be synced to Google Calendar.
        - Community events / HOA events (or events without property_id that are not explicitly Private Events)
          do not require payment, deposit, or agreement flags.
        - Private events MUST have payment_made, deposit_on_file, and agreement_received (or agreement_recieved) all set to True.
        """
        event_type = str(res.get('event_type') or 'Private Event')
        property_id = res.get('property_id')

        is_community_or_hoa = (
            event_type in ('HOA Event', 'Community Event')
            or (property_id is None and event_type != 'Private Event')
        )

        if is_community_or_hoa:
            return True

        # For Private Events, verify payment_made, deposit_on_file, and agreement_received are all True
        payment_made = bool(res.get('payment_made'))
        deposit_on_file = bool(res.get('deposit_on_file'))
        agreement_received = bool(res.get('agreement_received') or res.get('agreement_recieved'))

        return payment_made and deposit_on_file and agreement_received

    def format_event_payload(self, res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats a database reservation dictionary into a Google Calendar API event body.
        Handles community/HOA events that do not have property address or owner associated.
        """
        res_id = res.get('reservation_id')
        event_type = res.get('event_type', 'Private Event')
        property_id = res.get('property_id')

        # Address resolution
        if res.get('address'):
            address = res.get('address')
        elif property_id:
            address = f"Property {property_id}"
        else:
            address = "Community Clubhouse"

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

        if event_type in ('HOA Event', 'Community Event'):
            default_name = 'Board Meeting' if event_type == 'HOA Event' else 'Community Event'
            summary = f"{event_type}: {event_name or default_name}"
            description = (
                f"Official {event_type}\n"
                f"Event Name: {event_name or 'N/A'}\n"
                f"Details: {event_desc or 'None'}\n"
                f"Location: {address}\n"
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

    def _fetch_existing_gcal_events(self) -> Dict[str, Any]:
        """Helper to list existing events keyed by reservation_id."""
        existing_gcal_events = {}
        if self.calendar_service:
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
        return existing_gcal_events

    def sync_single_reservation(
        self,
        res: Dict[str, Any],
        existing_gcal_events: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Syncs a single reservation to Google Calendar (Insert or Update).
        Private Events require payment_made, deposit_on_file, and agreement_received to be True.
        """
        res_id_str = str(res.get('reservation_id'))

        if not self.is_eligible_for_sync(res):
            log_info(f"GoogleCalendarSync Notice: Reservation #{res_id_str} ({res.get('event_type', 'Private Event')}) does not meet GCal sync criteria (requires payment_made, deposit_on_file, and agreement_received).")
            if existing_gcal_events is None and self.calendar_service and not dry_run:
                existing_gcal_events = self._fetch_existing_gcal_events()

            if existing_gcal_events and res_id_str in existing_gcal_events:
                log_info(f"GoogleCalendarSync Notice: Removing existing GCal Event for Reservation #{res_id_str} because it no longer meets criteria.")
                return self.delete_single_reservation(res_id_str, existing_gcal_events=existing_gcal_events, dry_run=dry_run)

            return {'reservation_id': res_id_str, 'action': 'skipped_ineligible', 'reason': 'Missing required payment, deposit, or agreement'}

        payload = self.format_event_payload(res)

        if dry_run or not self.calendar_service:
            log_info(f"[DRY-RUN] Would sync Reservation #{res_id_str} ({payload['summary']}) to Google Calendar")
            return {'reservation_id': res_id_str, 'action': 'dry_run', 'payload': payload}

        if existing_gcal_events is None:
            existing_gcal_events = self._fetch_existing_gcal_events()

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
                return {'reservation_id': res_id_str, 'action': 'updated', 'gcal_id': gcal_id, 'link': updated_event.get('htmlLink')}
            else:
                created_event = self.calendar_service.events().insert(
                    calendarId=self.calendar_id,
                    body=payload
                ).execute()
                gcal_id = created_event.get('id')
                log_info(f"GoogleCalendarSync: Created GCal Event {gcal_id} for Reservation #{res_id_str}")
                return {'reservation_id': res_id_str, 'action': 'created', 'gcal_id': gcal_id, 'link': created_event.get('htmlLink')}
        except Exception as e:
            log_info(f"GoogleCalendarSync Error syncing Reservation #{res_id_str}: {e}")
            return {'reservation_id': res_id_str, 'action': 'error', 'error': str(e)}

    def delete_single_reservation(
        self,
        reservation_id: Any,
        existing_gcal_events: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Deletes a single reservation from Google Calendar by reservation_id.
        """
        res_id_str = str(reservation_id)
        if dry_run or not self.calendar_service:
            log_info(f"[DRY-RUN] Would delete GCal Event for Reservation #{res_id_str}")
            return {'reservation_id': res_id_str, 'action': 'dry_run_deleted'}

        if existing_gcal_events is None:
            existing_gcal_events = self._fetch_existing_gcal_events()

        if res_id_str in existing_gcal_events:
            gcal_event = existing_gcal_events[res_id_str]
            gcal_id = gcal_event['id']
            try:
                self.calendar_service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=gcal_id
                ).execute()
                log_info(f"GoogleCalendarSync: Deleted GCal Event {gcal_id} for Reservation #{res_id_str}")
                return {'reservation_id': res_id_str, 'action': 'deleted', 'gcal_id': gcal_id}
            except Exception as e:
                log_info(f"GoogleCalendarSync Error deleting Reservation #{res_id_str}: {e}")
                return {'reservation_id': res_id_str, 'action': 'error', 'error': str(e)}
        else:
            log_info(f"GoogleCalendarSync Notice: No existing GCal Event found for Reservation #{res_id_str} to delete")
            return {'reservation_id': res_id_str, 'action': 'not_found'}

    def process_trigger_event(
        self,
        event_type: str,
        old_row: Optional[Dict[str, Any]] = None,
        new_row: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Processes a PostgreSQL trigger event (INSERT, UPDATE, DELETE).
        """
        event_upper = (event_type or "").upper()
        if event_upper in ("INSERT", "UPDATE"):
            if not new_row:
                raise ValueError(f"new_row must be provided for {event_upper} trigger event.")
            return self.sync_single_reservation(new_row, dry_run=dry_run)
        elif event_upper == "DELETE":
            res_id = (old_row or {}).get('reservation_id')
            if res_id is None:
                raise ValueError("old_row containing reservation_id must be provided for DELETE trigger event.")
            return self.delete_single_reservation(res_id, dry_run=dry_run)
        else:
            raise ValueError(f"Unknown trigger event type: {event_type}")

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

        existing_gcal_events = self._fetch_existing_gcal_events() if (self.calendar_service and not dry_run) else {}

        for res in reservations:
            res_result = self.sync_single_reservation(res, existing_gcal_events=existing_gcal_events, dry_run=dry_run)
            results.append(res_result)
            action = res_result.get('action')
            if action in ('created', 'dry_run'):
                created_count += 1
            elif action == 'updated':
                updated_count += 1

        return created_count, updated_count, results
