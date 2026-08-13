import unittest
from unittest.mock import MagicMock, patch
import datetime

from door_controller.common_lib.gcal_sync import GoogleCalendarSync

class TestGoogleCalendarSync(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.syncer = GoogleCalendarSync(
            service_account_file="nonexistent_service_account.json",
            calendar_id="test_calendar_id@gmail.com",
            timezone="America/New_York",
            db_manager=self.mock_db
        )

    def test_format_event_payload_private_event(self):
        res = {
            'reservation_id': 42,
            'property_id': 10001,
            'address': '101 Main St',
            'owner_name': 'John Doe',
            'event_type': 'Private Event',
            'reservation_date': datetime.date(2026, 8, 20),
            'from_time': datetime.time(8, 0),
            'to_time': datetime.time(12, 0),
            'fee': 15.0,
            'early_setup': False,
            'reschedule_required': False
        }

        payload = self.syncer.format_event_payload(res)

        self.assertEqual(payload['summary'], 'Clubhouse Reservation - 101 Main St')
        self.assertEqual(payload['start']['dateTime'], '2026-08-20T08:00:00')
        self.assertEqual(payload['end']['dateTime'], '2026-08-20T12:00:00')
        self.assertEqual(payload['start']['timeZone'], 'America/New_York')
        self.assertEqual(payload['extendedProperties']['private']['reservation_id'], '42')
        self.assertIn('John Doe', payload['description'])

    def test_format_event_payload_hoa_event(self):
        res = {
            'reservation_id': 99,
            'property_id': 10001,
            'address': 'HOA Board',
            'event_type': 'HOA Event',
            'event_name': 'Annual Budget Meeting',
            'event_description': 'Discussion of 2027 fiscal budget',
            'reservation_date': '2026-09-15',
            'from_time': '08:00:00',
            'to_time': '23:00:00',
            'fee': 0.0,
            'early_setup': False,
            'reschedule_required': False
        }

        payload = self.syncer.format_event_payload(res)

        self.assertEqual(payload['summary'], 'HOA Event: Annual Budget Meeting')
        self.assertEqual(payload['start']['dateTime'], '2026-09-15T08:00:00')
        self.assertEqual(payload['end']['dateTime'], '2026-09-15T23:00:00')
        self.assertIn('Annual Budget Meeting', payload['description'])
        self.assertEqual(payload['extendedProperties']['private']['reservation_id'], '99')

    def test_sync_reservations_dry_run(self):
        self.mock_db.list_reservations.return_value = [
            {
                'reservation_id': 1,
                'property_id': 10001,
                'address': '101 Main St',
                'owner_name': 'Alice Smith',
                'event_type': 'Private Event',
                'reservation_date': '2026-08-25',
                'from_time': '08:00:00',
                'to_time': '12:00:00',
                'fee': 15.0,
                'early_setup': False,
                'reschedule_required': False
            }
        ]

        created, updated, results = self.syncer.sync_reservations(dry_run=True)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['action'], 'dry_run')
        self.assertEqual(results[0]['reservation_id'], '1')

if __name__ == '__main__':
    unittest.main()
