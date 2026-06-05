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

    def set_logged_in(self, username='test_user', role='ManagementCo'):
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
        mock_db.authenticate_user.return_value = {'username': 'admin', 'role': 'SysAdmin'}
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'admin')
            self.assertEqual(sess.get('role'), 'SysAdmin')
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
    def test_index_redirects_to_fobs(self, mock_get_db_mgr):
        self.set_logged_in()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/fobs'))

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_fobs_route_sysadmin(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.list_fobs.return_value = [
            {'fob_id': 1001, 'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe', 'created_at': None, 'updated_at': None}
        ]
        mock_db.list_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_replacement_logs.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/fobs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'101 Main St', response.data)
        self.assertIn(b'Assign Key Fob', response.data)
        mock_db.list_fobs.assert_called_once_with(group_id=None)
        mock_db.list_properties.assert_called_once_with(group_id=None)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_fobs_route_restricted_managementco(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='ManagementCo')
        mock_db = MagicMock()
        mock_db.get_group_id_by_name.return_value = 1
        mock_db.list_fobs.return_value = []
        mock_db.list_properties.return_value = []
        mock_db.list_replacement_logs.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/fobs')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'Group Access Control', response.data)
        mock_db.get_group_id_by_name.assert_called_once_with('ManagementCo')
        mock_db.list_fobs.assert_called_once_with(group_id=1)
        mock_db.list_properties.assert_called_once_with(group_id=1)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_ownership_route_authorized_secretary(self, mock_get_db_mgr):
        self.set_logged_in(username='secretary1', role='Secretary')
        mock_db = MagicMock()
        mock_db.list_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/ownership')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Update Property Owner', response.data)
        self.assertIn(b'101 Main St', response.data)
        mock_db.list_properties.assert_called_once_with(group_id=None)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_ownership_route_unauthorized_managementco(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='ManagementCo')
        response = self.client.get('/ownership')
        self.assertEqual(response.status_code, 302)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_groups_route_sysadmin(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.list_group_properties.return_value = [
            {'group_id': 1, 'group_name': 'operators', 'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_groups.return_value = [
            {'group_id': 1, 'name': 'operators'}
        ]
        mock_db.list_properties.return_value = []
        mock_db.list_audit_logs.return_value = []
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/groups')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Group Access Control', response.data)
        self.assertIn(b'Active Group Mappings', response.data)
        mock_db.list_group_properties.assert_called_once()
        mock_db.list_groups.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_groups_route_managementco_unauthorized(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='ManagementCo')
        response = self.client.get('/groups')
        self.assertEqual(response.status_code, 302)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_assign_group_access_success(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/group/assign', data={
            'group_id': '1',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.assign_property_to_group.assert_called_once_with(1, 10001, username='admin')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_assign_group_access_unauthorized(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1', role='ManagementCo')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/group/assign', data={
            'group_id': '1',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.assign_property_to_group.assert_not_called()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_unassign_group_access_success(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/group/unassign', data={
            'group_id': '1',
            'property_id': '10001'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.unassign_property_from_group.assert_called_once_with(1, 10001, username='admin')

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
    def test_update_property_owner_route_success(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user', role='Secretary')
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
    def test_update_property_owner_route_unauthorized(self, mock_get_db_mgr):
        self.set_logged_in(username='test_user', role='ManagementCo')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/property/update_owner', data={
            'property_id': '10001',
            'owner_name': 'John Connor'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_property_owner.assert_not_called()

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
