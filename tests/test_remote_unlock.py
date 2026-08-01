import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app
from door_controller.key_management_application.db_manager import FobDatabaseManager

class TestRemoteDoorUnlock(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_user', role='ManagementCo'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    @patch('door_controller.key_management_application.db_manager.psycopg2.connect')
    def test_get_door_details_db(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        mock_cur.fetchall.return_value = [
            {'door_id': 1, 'door_no': 1, 'door_desc': 'Pool Gate', 'controller_ip': '69.21.119.147'},
            {'door_id': 2, 'door_no': 2, 'door_desc': 'Clubhouse Front', 'controller_ip': '69.21.119.147'}
        ]

        db_mgr = FobDatabaseManager(conn_str="postgres://user:pass@localhost/db")
        doors = db_mgr.get_door_details()

        self.assertEqual(len(doors), 2)
        self.assertEqual(doors[0]['door_desc'], 'Pool Gate')
        self.assertEqual(doors[1]['door_desc'], 'Clubhouse Front')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_doors_route_accessible_by_managementco(self, mock_get_db_mgr):
        self.set_logged_in(username='user1', role='ManagementCo')
        mock_db = MagicMock()
        mock_db.get_door_details.return_value = [
            {'door_id': 1, 'door_no': 1, 'door_desc': 'Pool Gate', 'controller_ip': '69.21.119.147'}
        ]
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/doors')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Remote Door Control Panel', response.data)
        self.assertIn(b'Pool Gate', response.data)
        mock_db.get_door_details.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_doors_route_accessible_by_sysadmin(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.get_door_details.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/doors')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Remote Door Control Panel', response.data)

    @patch('door_controller.common_lib.utils.load_config')
    @patch('door_controller.common_lib.data_manager.DataManager')
    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_unlock_door_route_success(self, mock_get_db_mgr, mock_data_mgr_class, mock_load_config):
        self.set_logged_in(username='user1', role='Secretary')
        
        mock_db = MagicMock()
        mock_db.get_door_details.return_value = [
            {'door_id': 1, 'door_no': 1, 'door_desc': 'Pool Gate', 'controller_ip': '69.21.119.147'}
        ]
        mock_get_db_mgr.return_value = mock_db

        mock_load_config.return_value = {
            'settings': {'username': 'test_ctrl_user', 'password': 'test_ctrl_pass'}
        }

        mock_data_mgr_inst = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_data_mgr_inst.unlock_door.return_value = mock_response
        mock_data_mgr_class.return_value = mock_data_mgr_inst

        response = self.client.post('/doors/unlock/1')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/doors'))

        mock_data_mgr_inst.unlock_door.assert_called_once_with('Pool Gate', 1, '69.21.119.147')

if __name__ == '__main__':
    unittest.main()
