import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, time as dt_time

from door_controller.key_management_application.update_access_v2 import (
    AccessSynchronizer,
    main
)


class TestAccessSynchronizerV2(unittest.TestCase):

    def setUp(self):
        self.username = 'admin'
        self.password = 'password'
        self.db_config = 'postgresql://db'
        
        with patch('door_controller.key_management_application.update_access_v2.FobDatabaseManager') as mock_db_mgr_class:
            self.mock_db_mgr = mock_db_mgr_class.return_value
            self.sync = AccessSynchronizer(self.username, self.password, self.db_config)
            self.sync.db_mgr = self.mock_db_mgr

    def test_extract_cidr(self):
        self.assertEqual(self.sync.extract_cidr("http://69.21.119.147"), "69.21.119.147/32")
        self.assertEqual(self.sync.extract_cidr("https://192.168.1.10:8080"), "192.168.1.10/32")

    def test_parse_door_name(self):
        self.assertEqual(self.sync.parse_door_name("Door 01"), 1)
        self.assertEqual(self.sync.parse_door_name("Door 12"), 12)
        self.assertEqual(self.sync.parse_door_name("Door A"), None)
        self.assertEqual(self.sync.parse_door_name(""), None)
        self.assertEqual(self.sync.parse_door_name(None), None)

    @patch.object(AccessSynchronizer, 'get_expected_permissions')
    @patch('door_controller.key_management_application.update_access_v2.DataManager')
    def test_synchronize_access_thread_safe(self, mock_dm_class, mock_get_expected_perms):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        self.mock_db_mgr.list_fobs.return_value = [
            {'fob_id': 1001},
            {'fob_id': 1002}
        ]
        self.mock_db_mgr.get_owner_for_fobid.return_value = "Bob Owner"

        mock_dm = mock_dm_class.return_value
        mock_dm.get_record_id.side_effect = [21, None]
        
        mock_add_resp = MagicMock()
        mock_add_resp.status_code = 200
        mock_dm.add_fob.return_value = [mock_add_resp, 22]

        mock_dm.get_permissions_record.side_effect = [
            [["21", "1001", "Door 01", "Allow", "url"], ["21", "1001", "Door 02", "Allow", "url"]],
            [["22", "1002", "Door 01", "Allow", "url"], ["22", "1002", "Door 02", "Allow", "url"]]
        ]

        mock_get_expected_perms.side_effect = [
            {1: True, 2: False},
            {1: True, 2: True}
        ]

        res = self.sync.synchronize_access('http://69.21.119.147')
        
        self.assertTrue(res)
        self.assertEqual(mock_dm.get_record_id.call_count, 2)
        mock_dm.get_record_id.assert_any_call(1001)
        mock_dm.get_record_id.assert_any_call(1002)
        mock_dm.add_fob.assert_called_once_with(1002, "Bob Owner")
        self.assertEqual(mock_dm.set_permissions.call_count, 2)

    @patch.object(AccessSynchronizer, 'run_controller_sync_loop')
    def test_start_scheduler_threads_creates_isolated_threads(self, mock_loop):
        urls = ['http://69.21.119.147', 'http://69.21.119.148']
        threads = self.sync.start_scheduler_threads(urls, limit_changes=5)
        
        self.assertEqual(len(threads), 2)
        for t in threads:
            self.assertTrue(t.daemon)
            self.assertTrue(t.name.startswith("SyncThread-"))

    @patch.object(AccessSynchronizer, 'run_controller_sync_loop')
    def test_start_thread_safe_scheduler_function(self, mock_loop):
        from door_controller.key_management_application.update_access_v2 import start_thread_safe_scheduler
        urls = ['http://69.21.119.147', 'http://69.21.119.148']
        threads = start_thread_safe_scheduler(urls, {'settings': {'postgres_connect_string': 'postgresql://db'}}, 'admin', 'password', limit_changes=5)
        
        self.assertEqual(len(threads), 2)
        for t in threads:
            self.assertTrue(t.daemon)
            self.assertTrue(t.name.startswith("Sync-"))

    @patch('door_controller.key_management_application.update_access_v2.time.sleep')
    @patch('door_controller.key_management_application.update_access_v2.collect_metrics_stats')
    @patch('door_controller.key_management_application.update_access_v2.load_config')
    @patch('door_controller.key_management_application.update_access_v2.FobDatabaseManager')
    @patch.object(AccessSynchronizer, 'synchronize_access')
    def test_main_run_once_threads(self, mock_sync_access, mock_db_mgr_class, mock_load_config, mock_collect_metrics, mock_sleep):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db',
                'username': 'admin',
                'password': 'password',
                'urls': ['http://69.21.119.147', 'http://69.21.119.148']
            }
        }
        
        main(argv=[])
        
        self.assertEqual(mock_sync_access.call_count, 2)
        mock_sync_access.assert_any_call('http://69.21.119.147', limit_changes=None, num_batches=None, max_batch_size=10, throttle_delay=0.15)
        mock_sync_access.assert_any_call('http://69.21.119.148', limit_changes=None, num_batches=None, max_batch_size=10, throttle_delay=0.15)


if __name__ == '__main__':
    unittest.main()
