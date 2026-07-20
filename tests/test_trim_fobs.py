import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from door_controller.key_management_application.trim_fobs import (
    RemoveOrphanedFobs,
    main
)


class TestRemoveOrphanedFobs(unittest.TestCase):

    def setUp(self):
        self.username = 'admin'
        self.password = 'password'
        self.db_config = 'postgresql://db'
        
        # Patch FobDatabaseManager constructor to avoid real db connections during setup
        with patch('door_controller.key_management_application.trim_fobs.FobDatabaseManager') as mock_db_mgr_class:
            self.mock_db_mgr = mock_db_mgr_class.return_value
            self.trimmer = RemoveOrphanedFobs(self.username, self.password, self.db_config)
            self.trimmer.db_mgr = self.mock_db_mgr

    def test_extract_cidr(self):
        self.assertEqual(self.trimmer.extract_cidr("http://69.21.119.147"), "69.21.119.147/32")
        self.assertEqual(self.trimmer.extract_cidr("https://192.168.1.10:8080"), "192.168.1.10/32")

    @patch('door_controller.key_management_application.trim_fobs.postgres')
    def test_get_all_fobs_from_controller(self, mock_postgres_class):
        mock_pg_db = mock_postgres_class.return_value
        mock_dm = MagicMock()
        mock_dm.sql = "INSERT INTO..."
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn
        self.mock_db_mgr.conn_str = self.db_config

        mock_cur.fetchall.return_value = [
            (21, 1001),
            (22, 1002)
        ]
        
        fobs = self.trimmer.get_all_fobs_from_controller('http://69.21.119.147', mock_dm)
        self.assertEqual(len(fobs), 2)
        self.assertEqual(fobs[0], ["21", "1001"])
        self.assertEqual(fobs[1], ["22", "1002"])

        mock_postgres_class.assert_called_once_with(self.db_config)
        mock_dm.get_keyfobs.assert_called_once()
        mock_pg_db.purge_fob_records.assert_any_call("'69.21.119.147/32'")
        mock_pg_db.write_db.assert_called_once_with(mock_dm.get_keyfobs.return_value, mock_dm.sql)

    @patch.object(RemoveOrphanedFobs, 'get_all_fobs_from_controller')
    @patch('door_controller.key_management_application.trim_fobs.DataManager')
    def test_remove_orphans(self, mock_dm_class, mock_get_all_fobs):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        self.mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        # DB only has fob 1001
        self.mock_db_mgr.list_fobs.return_value = [
            {'fob_id': 1001}
        ]

        # Controller has fob 1001 and 1002 (extra, to be deleted)
        mock_get_all_fobs.return_value = [
            ["21", "1001"],
            ["22", "1002"]
        ]

        mock_dm = mock_dm_class.return_value
        mock_dm.del_fob.return_value = 200

        res = self.trimmer.remove_orphans('http://69.21.119.147')
        
        self.assertTrue(res)
        mock_dm.del_fob.assert_called_once_with(1002)

    @patch.object(RemoveOrphanedFobs, 'run_controller_sync_loop')
    def test_start_scheduler_threads(self, mock_loop):
        urls = ['http://69.21.119.147', 'http://69.21.119.148']
        threads = self.trimmer.start_scheduler_threads(urls, recurrence_interval=300, limit_changes=5)
        
        self.assertEqual(len(threads), 2)
        for t in threads:
            self.assertTrue(t.daemon)
            self.assertIn(t.name, ["SyncThread-http://69.21.119.147", "SyncThread-http://69.21.119.148"])

    @patch('door_controller.key_management_application.trim_fobs.load_config')
    @patch('door_controller.key_management_application.trim_fobs.FobDatabaseManager')
    @patch.object(RemoveOrphanedFobs, 'remove_orphans')
    def test_main_run_once(self, mock_remove_orphans, mock_db_mgr_class, mock_load_config):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db',
                'username': 'admin',
                'password': 'password',
                'urls': ['http://69.21.119.147', 'http://69.21.119.148'],
                'recurrence': 1800
            }
        }
        
        main(argv=[])
        
        self.assertEqual(mock_remove_orphans.call_count, 2)
        mock_remove_orphans.assert_any_call('http://69.21.119.147', None)
        mock_remove_orphans.assert_any_call('http://69.21.119.148', None)

    @patch('door_controller.key_management_application.trim_fobs.datetime')
    @patch('door_controller.key_management_application.trim_fobs.time.sleep')
    @patch.object(RemoveOrphanedFobs, 'remove_orphans')
    def test_run_controller_sync_loop_skips_at_edge_times(self, mock_remove_orphans, mock_sleep, mock_datetime):
        # 1. Midnight check (hour=0, minute=0)
        mock_now = datetime(2026, 6, 17, 0, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            self.trimmer.run_controller_sync_loop('http://69.21.119.147', recurrence_interval=30)
        except KeyboardInterrupt:
            pass

        # Should skip initial and periodic runs
        mock_remove_orphans.assert_not_called()

        # 2. 11:59 PM check (hour=23, minute=59)
        mock_now = datetime(2026, 6, 17, 23, 59, 0)
        mock_datetime.now.return_value = mock_now
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            self.trimmer.run_controller_sync_loop('http://69.21.119.147', recurrence_interval=30)
        except KeyboardInterrupt:
            pass

        # Should skip initial and periodic runs
        mock_remove_orphans.assert_not_called()


if __name__ == '__main__':
    unittest.main()
