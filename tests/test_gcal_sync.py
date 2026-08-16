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

    def test_config_file_loading(self):
        with patch('door_controller.common_lib.gcal_sync.load_config') as mock_load_cfg:
            mock_load_cfg.return_value = {
                'gcal': {
                    'service_account_file': 'custom_service_account.json',
                    'calendar_id': 'custom_cal_id@gmail.com',
                    'timezone': 'America/Chicago'
                }
            }
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.calendar_id, 'custom_cal_id@gmail.com')
            self.assertEqual(syncer.timezone, 'America/Chicago')

    def test_is_eligible_for_sync(self):
        # Private Event missing payment/deposit/agreement -> ineligible
        incomplete_private = {
            'reservation_id': 1,
            'event_type': 'Private Event',
            'property_id': 1001,
            'payment_made': True,
            'deposit_on_file': False,
            'agreement_received': True
        }
        self.assertFalse(self.syncer.is_eligible_for_sync(incomplete_private))

        # Private Event with all 3 flags True -> eligible
        complete_private = {
            'reservation_id': 2,
            'event_type': 'Private Event',
            'property_id': 1001,
            'payment_made': True,
            'deposit_on_file': True,
            'agreement_received': True
        }
        self.assertTrue(self.syncer.is_eligible_for_sync(complete_private))

        # Community / HOA Event without property or flags -> eligible
        community_event = {
            'reservation_id': 3,
            'event_type': 'Community Event',
            'property_id': None,
            'payment_made': False,
            'deposit_on_file': False,
            'agreement_received': False
        }
        self.assertTrue(self.syncer.is_eligible_for_sync(community_event))

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
            'reschedule_required': False,
            'payment_made': True,
            'deposit_on_file': True,
            'agreement_received': True
        }

        payload = self.syncer.format_event_payload(res)

        self.assertEqual(payload['summary'], 'Clubhouse Reservation - 101 Main St')
        self.assertEqual(payload['start']['dateTime'], '2026-08-20T08:00:00')
        self.assertEqual(payload['end']['dateTime'], '2026-08-20T12:00:00')
        self.assertEqual(payload['start']['timeZone'], 'America/New_York')
        self.assertEqual(payload['extendedProperties']['private']['reservation_id'], '42')
        self.assertIn('John Doe', payload['description'])

    def test_format_event_payload_community_event_no_property(self):
        res = {
            'reservation_id': 77,
            'property_id': None,
            'event_type': 'Community Event',
            'event_name': 'Summer Pool Party',
            'event_description': 'Annual neighborhood summer gathering',
            'reservation_date': '2026-07-04',
            'from_time': '12:00:00',
            'to_time': '18:00:00'
        }

        payload = self.syncer.format_event_payload(res)

        self.assertEqual(payload['summary'], 'Community Event: Summer Pool Party')
        self.assertEqual(payload['start']['dateTime'], '2026-07-04T12:00:00')
        self.assertEqual(payload['end']['dateTime'], '2026-07-04T18:00:00')
        self.assertIn('Summer Pool Party', payload['description'])
        self.assertIn('Community Clubhouse', payload['description'])
        self.assertEqual(payload['extendedProperties']['private']['reservation_id'], '77')

    def test_sync_single_reservation_ineligible_skipped(self):
        res = {
            'reservation_id': 5,
            'property_id': 10001,
            'address': '101 Main St',
            'owner_name': 'Charlie',
            'event_type': 'Private Event',
            'reservation_date': '2026-08-25',
            'from_time': '10:00:00',
            'to_time': '14:00:00',
            'payment_made': False,
            'deposit_on_file': True,
            'agreement_received': True
        }
        res_out = self.syncer.sync_single_reservation(res, dry_run=True)
        self.assertEqual(res_out['action'], 'skipped_ineligible')
        self.assertEqual(res_out['reservation_id'], '5')

    def test_sync_single_reservation_eligible_dry_run(self):
        res = {
            'reservation_id': 5,
            'property_id': 10001,
            'address': '101 Main St',
            'owner_name': 'Charlie',
            'event_type': 'Private Event',
            'reservation_date': '2026-08-25',
            'from_time': '10:00:00',
            'to_time': '14:00:00',
            'payment_made': True,
            'deposit_on_file': True,
            'agreement_received': True
        }
        res_out = self.syncer.sync_single_reservation(res, dry_run=True)
        self.assertEqual(res_out['action'], 'dry_run')
        self.assertEqual(res_out['reservation_id'], '5')

    def test_delete_single_reservation_dry_run(self):
        res_out = self.syncer.delete_single_reservation(5, dry_run=True)
        self.assertEqual(res_out['action'], 'dry_run_deleted')
        self.assertEqual(res_out['reservation_id'], '5')

    def test_process_trigger_event(self):
        new_row = {
            'reservation_id': 10,
            'property_id': 10001,
            'address': '101 Main St',
            'owner_name': 'Dave',
            'event_type': 'Private Event',
            'reservation_date': '2026-08-30',
            'from_time': '09:00:00',
            'to_time': '11:00:00',
            'payment_made': True,
            'deposit_on_file': True,
            'agreement_received': True
        }
        old_row = {'reservation_id': 10}

        # Test INSERT
        insert_res = self.syncer.process_trigger_event("INSERT", new_row=new_row, dry_run=True)
        self.assertEqual(insert_res['action'], 'dry_run')
        self.assertEqual(insert_res['reservation_id'], '10')

        # Test UPDATE
        update_res = self.syncer.process_trigger_event("UPDATE", new_row=new_row, old_row=old_row, dry_run=True)
        self.assertEqual(update_res['action'], 'dry_run')

        # Test DELETE
        delete_res = self.syncer.process_trigger_event("DELETE", old_row=old_row, dry_run=True)
        self.assertEqual(delete_res['action'], 'dry_run_deleted')
        self.assertEqual(delete_res['reservation_id'], '10')

if __name__ == '__main__':
    unittest.main()
