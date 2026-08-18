import os
import unittest
from unittest.mock import patch, MagicMock

from door_controller.common_lib.gcal_sync import GoogleCalendarSync

class TestGCalSyncModeConfig(unittest.TestCase):

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {}, clear=False)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_sync_mode_application(self):
        with patch('door_controller.common_lib.gcal_sync.load_config', return_value={'gcal': {'sync_mode': 'application'}}):
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.sync_mode, 'application')
            self.assertTrue(syncer.is_application_sync_enabled())
            self.assertFalse(syncer.is_database_sync_enabled())

            # DB trigger should be skipped
            res = syncer.process_trigger_event(event_type='INSERT', new_row={'reservation_id': 1})
            self.assertEqual(res.get('action'), 'skipped_disabled')

    def test_sync_mode_database(self):
        with patch('door_controller.common_lib.gcal_sync.load_config', return_value={'gcal': {'sync_mode': 'database'}}):
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.sync_mode, 'database')
            self.assertFalse(syncer.is_application_sync_enabled())
            self.assertTrue(syncer.is_database_sync_enabled())

    def test_sync_mode_both(self):
        with patch('door_controller.common_lib.gcal_sync.load_config', return_value={'gcal': {'sync_mode': 'both'}}):
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.sync_mode, 'both')
            self.assertTrue(syncer.is_application_sync_enabled())
            self.assertTrue(syncer.is_database_sync_enabled())

    def test_sync_mode_disabled(self):
        with patch('door_controller.common_lib.gcal_sync.load_config', return_value={'gcal': {'sync_mode': 'disabled'}}):
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.sync_mode, 'disabled')
            self.assertFalse(syncer.is_application_sync_enabled())
            self.assertFalse(syncer.is_database_sync_enabled())

            res = syncer.process_trigger_event(event_type='INSERT', new_row={'reservation_id': 1})
            self.assertEqual(res.get('action'), 'skipped_disabled')

    def test_sync_mode_environment_variable_override(self):
        os.environ['GCAL_SYNC_MODE'] = 'database'
        with patch('door_controller.common_lib.gcal_sync.load_config', return_value={'gcal': {'sync_mode': 'application'}}):
            syncer = GoogleCalendarSync()
            self.assertEqual(syncer.sync_mode, 'database')
            self.assertFalse(syncer.is_application_sync_enabled())
            self.assertTrue(syncer.is_database_sync_enabled())

if __name__ == '__main__':
    unittest.main()
