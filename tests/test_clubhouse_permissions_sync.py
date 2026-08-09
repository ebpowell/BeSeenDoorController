import unittest
from unittest.mock import MagicMock, patch
import datetime

from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.key_management_application.update_access import AccessSynchronizer


class DummyCursor:
    def __init__(self, query_results):
        self.query_results = query_results
        self.executed_queries = []
        self.current_result = []

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))
        self.current_result = []
        for keyword, data in self.query_results:
            if keyword in query:
                self.current_result = data
                break

    def fetchall(self):
        return self.current_result

    def fetchone(self):
        return self.current_result[0] if self.current_result else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class DummyConnection:
    def __init__(self, query_results):
        self.query_results = query_results
        self.cursor_obj = DummyCursor(query_results)
        self.committed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestClubhousePermissionsSync(unittest.TestCase):

    @patch.object(FobDatabaseManager, '__init__', lambda self, conn_str=None: None)
    def test_sync_clubhouse_reservation_permissions_grant(self):
        db_mgr = FobDatabaseManager()
        
        now = datetime.datetime(2026, 8, 3, 14, 0, 0)
        res_date = datetime.date(2026, 8, 3)
        from_time = datetime.time(12, 0, 0)
        to_time = datetime.time(18, 0, 0)
        
        dummy_conn = DummyConnection([
            ("clubhouse_reservations", [(10001, res_date, from_time, to_time)]),
            ("property_group_permissions WHERE group_id = 8", [])
        ])
        
        with patch.object(db_mgr, '_get_connection', return_value=dummy_conn):
            with patch.object(db_mgr, 'log_audit_action'):
                res = db_mgr.sync_clubhouse_reservation_permissions(now=now)
                
        self.assertEqual(res['granted'], [10001])
        self.assertEqual(res['revoked'], [])
        self.assertEqual(res['active'], [10001])
        self.assertTrue(dummy_conn.committed)

    @patch.object(FobDatabaseManager, '__init__', lambda self, conn_str=None: None)
    def test_sync_clubhouse_reservation_permissions_revoke_when_expired(self):
        db_mgr = FobDatabaseManager()
        
        now = datetime.datetime(2026, 8, 3, 19, 0, 0)  # After 18:00
        res_date = datetime.date(2026, 8, 3)
        from_time = datetime.time(12, 0, 0)
        to_time = datetime.time(18, 0, 0)
        
        dummy_conn = DummyConnection([
            ("clubhouse_reservations", [(10001, res_date, from_time, to_time)]),
            ("property_group_permissions WHERE group_id = 8", [(10001,)])
        ])
        
        with patch.object(db_mgr, '_get_connection', return_value=dummy_conn):
            with patch.object(db_mgr, 'log_audit_action'):
                res = db_mgr.sync_clubhouse_reservation_permissions(now=now)
                
        self.assertEqual(res['granted'], [])
        self.assertEqual(res['revoked'], [10001])
        self.assertEqual(res['active'], [])
        self.assertTrue(dummy_conn.committed)

    @patch.object(FobDatabaseManager, '__init__', lambda self, conn_str=None: None)
    def test_get_runtimes_for_date_includes_reservation_times(self):
        db_mgr = FobDatabaseManager()
        
        target_date = datetime.date(2026, 8, 3)
        from_time = datetime.time(14, 0, 0)
        to_time = datetime.time(17, 0, 0)
        
        dummy_conn = DummyConnection([
            ("f_get_runtimes", [(datetime.time(8, 0, 0),)]),
            ("clubhouse_reservations", [(from_time, to_time)])
        ])
        
        with patch.object(db_mgr, '_get_connection', return_value=dummy_conn):
            runtimes = db_mgr.get_runtimes_for_date(target_date)
            
        self.assertIn(datetime.time(8, 0, 0), runtimes)
        self.assertIn(from_time, runtimes)
        self.assertIn(to_time, runtimes)
        self.assertEqual(runtimes, sorted(runtimes))

    @patch('door_controller.key_management_application.update_access.DataManager')
    @patch('door_controller.key_management_application.update_access.extract_cidr')
    def test_synchronize_access_calls_clubhouse_sync(self, mock_extract_cidr, mock_data_manager_cls):
        mock_db_mgr = MagicMock()
        mock_db_mgr.conn_str = "postgresql://localhost/db"
        mock_db_mgr.list_fobs.return_value = []
        mock_extract_cidr.return_value = "69.21.119.147/32"
        
        synchronizer = AccessSynchronizer("admin", "pass", mock_db_mgr)
        synchronizer.synchronize_access("http://69.21.119.147")
        
        mock_db_mgr.sync_clubhouse_reservation_permissions.assert_called_once()


if __name__ == "__main__":
    unittest.main()
