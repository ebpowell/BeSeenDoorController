import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app

class TestWebApp(unittest.TestCase):

    def setUp(self):
        # Configure the application for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_index_route(self, mock_get_db_mgr):
        # Mock database responses
        mock_db = MagicMock()
        mock_db.list_fobs.return_value = [
            {'fob_id': 1001, 'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe', 'created_at': None, 'updated_at': None}
        ]
        mock_db.list_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_replacement_logs.return_value = [
            {'replacement_id': 1, 'address': '101 Main St', 'replaced_fob_id': 999, 'new_fob_id': 1001, 'replaced_at': '2026-05-31'}
        ]
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'101 Main St', response.data)
        self.assertIn(b'John Doe', response.data)
        self.assertIn(b'1001', response.data)
        self.assertIn(b'#1', response.data)
        mock_db.list_fobs.assert_called_once()
        mock_db.list_properties.assert_called_once()
        mock_db.list_replacement_logs.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_success(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/add', data={
            'fob_id': '2001',
            'property_id': '10001',
            'replaced_fob_id': ''
        })
        # Should redirect back to index
        self.assertEqual(response.status_code, 302)
        mock_db.add_fob.assert_called_once_with(2001, 10001, None)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_with_replacement(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/add', data={
            'fob_id': '2001',
            'property_id': '10001',
            'replaced_fob_id': '1001'
        })
        # Should redirect back to index
        self.assertEqual(response.status_code, 302)
        mock_db.add_fob.assert_called_once_with(2001, 10001, 1001)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_invalid_id(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/add', data={
            'fob_id': 'invalid_id',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.add_fob.assert_not_called()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_update_property_owner_route(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_db.update_property_owner.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/property/update_owner', data={
            'property_id': '10001',
            'owner_name': 'John Connor'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_property_owner.assert_called_once_with(10001, 'John Connor')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_remove_fob_route(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_db.remove_fob.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/remove/1001')
        self.assertEqual(response.status_code, 302)
        mock_db.remove_fob.assert_called_once_with(1001)

if __name__ == '__main__':
    unittest.main()
