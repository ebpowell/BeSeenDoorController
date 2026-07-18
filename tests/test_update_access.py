import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, time as dt_time

from door_controller.key_management_application.update_access import (
    AccessSynchronizer,
    main
)


class TestAccessSynchronizer(unittest.TestCase):

    def setUp(self):
        self.username = 'admin'
        self.password = 'password'
        self.db_config = 'postgresql://db'
        
        # Patch FobDatabaseManager constructor to avoid real db connections during setup
        with patch('door_controller.key_management_application.update_access.FobDatabaseManager') as mock_db_mgr_class:
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

    def test_get_expected_permissions(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        mock_cur.fetchall.return_value = [
            (1, True),
            (2, False)
        ]
        perms = self.sync.get_expected_permissions(1001, '69.21.119.147/32')
        self.assertEqual(perms, {1: True, 2: False})

    def test_derive_run_schedule(self):
        ref_time = datetime(2026, 6, 16, 22, 30, 0)
        self.mock_db_mgr.get_runtimes_for_date.side_effect = [
            [dt_time(6, 0), dt_time(22, 0)],
            [dt_time(6, 0), dt_time(8, 0), dt_time(22, 0)]
        ]

        schedule = self.sync.derive_run_schedule('69.21.119.147/32', reference_time=ref_time)
        self.assertEqual(len(schedule), 3)
        self.assertEqual(schedule[0], datetime(2026, 6, 17, 6, 0, 0))
        self.assertEqual(schedule[1], datetime(2026, 6, 17, 8, 0, 0))
        self.assertEqual(schedule[2], datetime(2026, 6, 17, 22, 0, 0))

    @patch.object(AccessSynchronizer, 'get_expected_permissions')
    @patch('door_controller.key_management_application.update_access.DataManager')
    def test_synchronize_access(self, mock_dm_class, mock_get_expected_perms):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        # DB has fobs 1001 (exists on controller) and 1002 (missing, needs add)
        self.mock_db_mgr.list_fobs.return_value = [
            {'fob_id': 1001},
            {'fob_id': 1002}
        ]
        self.mock_db_mgr.get_owner_for_fobid.return_value = "Bob Owner"

        # Mock DataManager
        mock_dm = mock_dm_class.return_value
        # For fob 1001, get_record_id returns 21. For 1002, returns None (missing).
        mock_dm.get_record_id.side_effect = [21, None]
        
        # Mock add_fob return format [response, record_id]
        mock_add_resp = MagicMock()
        mock_add_resp.status_code = 200
        mock_dm.add_fob.return_value = [mock_add_resp, 22]

        # Permissions for 1001 (mismatch expected to sync)
        mock_dm.get_permissions_record.side_effect = [
            [["21", "1001", "Door 01", "Allow", "url"], ["21", "1001", "Door 02", "Allow", "url"]]
        ]

        # Expected permissions for 1001
        mock_get_expected_perms.return_value = {1: True, 2: False}

        res = self.sync.synchronize_access('http://69.21.119.147')
        
        self.assertTrue(res)
        
        # Verify get_record_id was called for both
        self.assertEqual(mock_dm.get_record_id.call_count, 2)
        mock_dm.get_record_id.assert_any_call(1001)
        mock_dm.get_record_id.assert_any_call(1002)

        # Verify addition of fob 1002 (owner "Bob Owner")
        mock_dm.add_fob.assert_called_once_with(1002, "Bob Owner")

        # Verify setting permissions for 1001 (door 2 forbidden)
        mock_dm.set_permissions.assert_called_once_with(
            [(1, True), (2, False)],
            21
        )

    @patch.object(AccessSynchronizer, 'run_controller_sync_loop')
    def test_start_scheduler_threads(self, mock_loop):
        urls = ['http://69.21.119.147', 'http://69.21.119.148']
        threads = self.sync.start_scheduler_threads(urls, limit_changes=5)
        
        self.assertEqual(len(threads), 2)
        for t in threads:
            self.assertTrue(t.daemon)
            self.assertIn(t.name, ["SyncThread-http://69.21.119.147", "SyncThread-http://69.21.119.148"])

    @patch('door_controller.key_management_application.update_access.load_config')
    @patch('door_controller.key_management_application.update_access.FobDatabaseManager')
    @patch.object(AccessSynchronizer, 'synchronize_access')
    def test_main_run_once(self, mock_sync_access, mock_db_mgr_class, mock_load_config):
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
        mock_sync_access.assert_any_call('http://69.21.119.147', None)
        mock_sync_access.assert_any_call('http://69.21.119.148', None)


if __name__ == '__main__':
    unittest.main()
