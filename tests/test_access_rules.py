import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app
from door_controller.key_management_application.db_manager import FobDatabaseManager

class TestAccessRules(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_admin', role='SysAdmin'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    @patch('door_controller.key_management_application.db_manager.psycopg2.connect')
    def test_list_access_rules_db(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchall.return_value = [
            {
                'perm_id': 1,
                'group_id': 1,
                'group_name': 'Residents',
                'door_id': 2,
                'door_desc': 'Pool Gate',
                'start_date': '2026-05-01',
                'end_date': '2026-09-30',
                'start_month': 5,
                'start_day': 1,
                'end_month': 9,
                'end_day': 30,
                'start_time': '08:00:00',
                'end_time': '20:00:00',
                'allow': True
            }
        ]

        db_mgr = FobDatabaseManager(conn_str="postgres://user:pass@localhost/db")
        rules = db_mgr.list_access_rules()

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['group_name'], 'Residents')
        self.assertEqual(rules[0]['door_desc'], 'Pool Gate')
        self.assertEqual(rules[0]['start_month'], 5)
        self.assertEqual(rules[0]['start_day'], 1)
        self.assertEqual(rules[0]['end_month'], 9)
        self.assertEqual(rules[0]['end_day'], 30)

    @patch('door_controller.key_management_application.db_manager.psycopg2.connect')
    def test_add_access_rule_db(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchone.side_effect = [
            ('Residents',),   # Group check
            ('Pool Gate',),   # Door check
            (101,)            # Insert RETURNING perm_id
        ]

        db_mgr = FobDatabaseManager(conn_str="postgres://user:pass@localhost/db")
        perm_id = db_mgr.add_access_rule(
            group_id=1,
            door_id=2,
            start_month=5,
            start_day=1,
            end_month=9,
            end_day=30,
            start_time='08:00:00',
            end_time='20:00:00',
            allow=True,
            username='admin'
        )

        self.assertEqual(perm_id, 101)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_access_rules_route_get(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.list_access_rules.return_value = [
            {
                'perm_id': 1,
                'group_name': 'Residents',
                'door_desc': 'Pool Gate',
                'start_month': 5,
                'start_day': 1,
                'end_month': 9,
                'end_day': 30,
                'start_time': '08:00:00',
                'end_time': '20:00:00',
                'allow': True
            }
        ]
        mock_db.get_door_details.return_value = [{'door_id': 2, 'door_no': 1, 'door_desc': 'Pool Gate'}]
        mock_db.list_groups.return_value = [{'group_id': 1, 'name': 'Residents'}]
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/access_rules')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Visualizing Access Rules', response.data)
        self.assertIn(b'Residents', response.data)
        self.assertIn(b'Pool Gate', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_access_rules_route_post_success(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.add_access_rule.return_value = 50
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/access_rules', data={
            'group_id': '1',
            'door_id': '2',
            'start_month': '5',
            'start_day': '1',
            'end_month': '9',
            'end_day': '30',
            'unlock_time': '08:00:00',
            'lock_time': '20:00:00',
            'allow': 'true'
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/access_rules'))
        mock_db.add_access_rule.assert_called_once_with(
            group_id=1,
            door_id=2,
            start_month='5',
            start_day='1',
            end_month='9',
            end_day='30',
            start_time='08:00:00',
            end_time='20:00:00',
            allow=True,
            username='admin'
        )

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_delete_access_rule_route(self, mock_get_db_mgr):
        self.set_logged_in(username='admin', role='SysAdmin')
        mock_db = MagicMock()
        mock_db.delete_access_rule.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/access_rules/delete/50')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/access_rules'))
        mock_db.delete_access_rule.assert_called_once_with(50, username='admin')

if __name__ == '__main__':
    unittest.main()
