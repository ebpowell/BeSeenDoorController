import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app

class TestWebApp(unittest.TestCase):

    def setUp(self):
        # Configure the application for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_user', role='operator'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    def test_unauthenticated_redirect(self):
        # Accessing root without login should redirect to /login
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login'))

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_login_renders(self, mock_get_db_mgr):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Access Panel', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_login_success(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_db.authenticate_user.return_value = {'username': 'admin', 'role': 'admin'}
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'admin')
            self.assertEqual(sess.get('role'), 'admin')
        mock_db.authenticate_user.assert_called_once_with('admin', 'admin123')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_login_failure(self, mock_get_db_mgr):
        mock_db = MagicMock()
        mock_db.authenticate_user.return_value = None
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'wrong_password'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password.', response.data)
        with self.client.session_transaction() as sess:
            self.assertNotIn('username', sess)

    def test_logout(self):
        self.set_logged_in()
        response = self.client.post('/logout')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn('username', sess)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_index_route_admin(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='admin')
        mock_db = MagicMock()
        mock_db.list_fobs.return_value = [
            {'fob_id': 1001, 'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe', 'created_at': None, 'updated_at': None}
        ]
        mock_db.list_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_replacement_logs.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_db.list_role_properties.return_value = [
            {'role': 'operator', 'property_id': 10001, 'address': '101 Main St'}
        ]
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'101 Main St', response.data)
        self.assertIn(b'Role Access Control', response.data)
        mock_db.list_fobs.assert_called_once_with(role='admin')
        mock_db.list_properties.assert_called_once_with(role='admin')
        mock_db.list_role_properties.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_index_route_restricted_operator(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='operator')
        mock_db = MagicMock()
        mock_db.list_fobs.return_value = []
        mock_db.list_properties.return_value = []
        mock_db.list_replacement_logs.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'Role Access Control', response.data)
        mock_db.list_fobs.assert_called_once_with(role='operator')
        mock_db.list_properties.assert_called_once_with(role='operator')
        mock_db.list_role_properties.assert_not_called()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_assign_role_access_success(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='admin')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/role/assign', data={
            'role': 'operator',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.assign_property_to_role.assert_called_once_with('operator', 10001, username='admin')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_assign_role_access_unauthorized(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='operator')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/role/assign', data={
            'role': 'operator',
            'property_id': '10001'
        })
        # Should redirect back to index due to failure to meet admin requirement
        self.assertEqual(response.status_code, 302)
        mock_db.assign_property_to_role.assert_not_called()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_unassign_role_access_success(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='admin')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/role/unassign', data={
            'role': 'operator',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.unassign_property_from_role.assert_called_once_with('operator', 10001, username='admin')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_success(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/add', data={
            'fob_id': '2001',
            'property_id': '10001',
            'replaced_fob_id': ''
        })
        # Should redirect back to index
        self.assertEqual(response.status_code, 302)
        mock_db.add_fob.assert_called_once_with(2001, 10001, None, username='test_user')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_with_replacement(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/add', data={
            'fob_id': '2001',
            'property_id': '10001',
            'replaced_fob_id': '1001'
        })
        # Should redirect back to index
        self.assertEqual(response.status_code, 302)
        mock_db.add_fob.assert_called_once_with(2001, 10001, 1001, username='test_user')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_fob_route_invalid_id(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user')
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
        self.set_logged_in(username='test_user')
        mock_db = MagicMock()
        mock_db.update_property_owner.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/property/update_owner', data={
            'property_id': '10001',
            'owner_name': 'John Connor'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_property_owner.assert_called_once_with(10001, 'John Connor', username='test_user')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_remove_fob_route(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user')
        mock_db = MagicMock()
        mock_db.remove_fob.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/fob/remove/1001')
        self.assertEqual(response.status_code, 302)
        mock_db.remove_fob.assert_called_once_with(1001, username='test_user')

if __name__ == '__main__':
    unittest.main()
