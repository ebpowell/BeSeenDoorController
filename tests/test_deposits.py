import unittest
from unittest.mock import patch, MagicMock

from door_controller.key_management_application.db_manager import FobDatabaseManager

class TestClubhouseDeposits(unittest.TestCase):

    def _setup_mock_db(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Make context managers return mock_conn and mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_cursor.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        return mock_conn, mock_cursor

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager._get_connection')
    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager._create_reservation_tables')
    def test_add_clubhouse_deposit(self, mock_create_tables, mock_get_conn):
        mock_conn, mock_cursor = self._setup_mock_db(mock_get_conn)
        mock_cursor.fetchone.return_value = (101,)

        db_mgr = FobDatabaseManager()
        dep_id = db_mgr.add_clubhouse_deposit(
            property_id=181,
            amount=150.00,
            deposit_status='On File',
            check_or_ref_no='Check #1042',
            notes='Clean deposit received'
        )

        self.assertEqual(dep_id, 101)
        self.assertTrue(mock_cursor.execute.called)

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager._get_connection')
    def test_list_clubhouse_deposits(self, mock_get_conn):
        mock_conn, mock_cursor = self._setup_mock_db(mock_get_conn)
        mock_cursor.fetchall.return_value = [
            {'deposit_id': 1, 'property_id': 181, 'address': '429 Gwinhurst Rd', 'amount': 150.0, 'deposit_status': 'On File'}
        ]

        db_mgr = FobDatabaseManager()
        deposits = db_mgr.list_clubhouse_deposits()

        self.assertEqual(len(deposits), 1)
        self.assertEqual(deposits[0]['deposit_status'], 'On File')
        self.assertEqual(deposits[0]['address'], '429 Gwinhurst Rd')

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager._get_connection')
    def test_update_clubhouse_deposit(self, mock_get_conn):
        mock_conn, mock_cursor = self._setup_mock_db(mock_get_conn)
        mock_cursor.fetchone.return_value = {'property_id': 181, 'reservation_id': 5}

        db_mgr = FobDatabaseManager()
        db_mgr.update_clubhouse_deposit(
            deposit_id=1,
            deposit_status='Refunded',
            refund_date='2026-08-18',
            notes='Inspection passed, full refund issued'
        )

        self.assertTrue(mock_cursor.execute.called)

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager._get_connection')
    def test_delete_clubhouse_deposit(self, mock_get_conn):
        mock_conn, mock_cursor = self._setup_mock_db(mock_get_conn)

        db_mgr = FobDatabaseManager()
        db_mgr.delete_clubhouse_deposit(deposit_id=1)

        self.assertTrue(mock_cursor.execute.called)

if __name__ == '__main__':
    unittest.main()
