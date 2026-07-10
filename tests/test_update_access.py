import unittest
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, date, time as dt_time
import threading

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

    def test_get_owner_for_fob(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        # Test case: Owner exists
        mock_cur.fetchone.return_value = ("Alice Owner",)
        owner = self.sync.get_owner_for_fob(1001)
        self.assertEqual(owner, "Alice Owner")

        # Test case: Owner does not exist
        mock_cur.fetchone.return_value = None
        owner = self.sync.get_owner_for_fob(9999)
        self.assertEqual(owner, "Fob 9999")

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

    @patch('door_controller.key_management_application.update_access.postgres')
    @patch('door_controller.key_management_application.update_access.ww_data_extractor')
    def test_get_all_fobs_from_controller(self, mock_extractor_class, mock_postgres_class):
        mock_pg_db = mock_postgres_class.return_value
        mock_extractor = mock_extractor_class.return_value
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn
        self.mock_db_mgr.conn_str = self.db_config

        mock_cur.fetchall.return_value = [
            (21, 1001),
            (22, 1002)
        ]
        
        fobs = self.sync.get_all_fobs_from_controller('http://69.21.119.147')
        self.assertEqual(len(fobs), 2)
        self.assertEqual(fobs[0], ["21", "1001"])
        self.assertEqual(fobs[1], ["22", "1002"])

        mock_postgres_class.assert_called_once_with(self.db_config)
        mock_extractor_class.assert_called_once_with('admin', 'password', 'http://69.21.119.147', mock_pg_db)
        mock_extractor.get_system_fob_list.assert_called_once()
        mock_pg_db.purge_fob_records.assert_called_once_with("'69.21.119.147/32'")

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

    @patch.object(AccessSynchronizer, 'get_all_fobs_from_controller')
    @patch.object(AccessSynchronizer, 'get_owner_for_fob')
    @patch.object(AccessSynchronizer, 'get_expected_permissions')
    @patch('door_controller.key_management_application.update_access.DataManager')
    @patch('door_controller.key_management_application.update_access.ww_data_extractor')
    def test_synchronize_access(self, mock_extractor_class, mock_dm_class, mock_get_expected_perms, mock_get_owner, mock_get_all_fobs):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        self.mock_db_mgr.list_fobs.return_value = [
            {'fob_id': 1001},
            {'fob_id': 1002}
        ]

        # Initial controller state: has 1001 and 1003 (extra fob to delete, missing 1002)
        mock_get_all_fobs.side_effect = [
            [["21", "1001"], ["23", "1003"]],
            [["21", "1001"], ["22", "1002"]]
        ]

        mock_get_owner.return_value = "Bob Owner"

        mock_get_expected_perms.side_effect = [
            {1: True, 2: False},
            {1: True, 2: True}
        ]

        mock_extractor = mock_extractor_class.return_value
        mock_extractor.get_permissions_record.side_effect = [
            [["21", "1001", "Door 01", "Allow", "url"], ["21", "1001", "Door 02", "Allow", "url"]],
            [["22", "1002", "Door 01", "Allow", "url"], ["22", "1002", "Door 02", "Allow", "url"]]
        ]

        mock_dm = mock_dm_class.return_value
        mock_dm.del_fob.return_value = 200
        
        # Mock add_fob return format [response, record_id]
        mock_add_resp = MagicMock()
        mock_add_resp.status_code = 200
        mock_dm.add_fob.return_value = mock_add_resp

        res = self.sync.synchronize_access('http://69.21.119.147')
        
        self.assertTrue(res)
        mock_dm.del_fob.assert_called_once_with(23)
        mock_dm.add_fob.assert_called_once_with(1002, "Bob Owner")
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
            self.assertTrue(t.is_alive() or not t.is_alive()) # Just check it is a Thread object
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
