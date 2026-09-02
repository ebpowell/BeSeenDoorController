import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from flask import Flask

from door_controller.key_management_application.api import api_bp, parse_period_to_timedelta


class TestDoorControllerRESTAPI(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test_secret'
        self.app.register_blueprint(api_bp)
        self.client = self.app.test_client()

    def test_parse_period_to_timedelta(self):
        self.assertEqual(parse_period_to_timedelta('1h').total_seconds(), 3600)
        self.assertEqual(parse_period_to_timedelta('24h').total_seconds(), 86400)
        self.assertEqual(parse_period_to_timedelta('7d').days, 7)
        self.assertEqual(parse_period_to_timedelta('2w').days, 14)
        self.assertEqual(parse_period_to_timedelta('1m').days, 30)
        self.assertEqual(parse_period_to_timedelta('invalid').total_seconds(), 86400)

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_get_fob_record_id_success(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_dm.get_record_id.return_value = 21
        mock_get_dm.return_value = mock_dm

        res = self.client.get('/api/fob/1001/record_id')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['fob_id'], 1001)
        self.assertEqual(data['record_id'], 21)

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_get_fob_record_id_not_found(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_dm.get_record_id.return_value = None
        mock_get_dm.return_value = mock_dm

        res = self.client.get('/api/fob/9999/record_id')
        self.assertEqual(res.status_code, 404)
        data = res.get_json()
        self.assertEqual(data['status'], 'error')

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_add_fob_success(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_dm.add_fob.return_value = ['success_code', 22]
        mock_get_dm.return_value = mock_dm

        res = self.client.post('/api/fob', json={'fob_id': 1002, 'owner_name': 'Jane Doe'})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['fob_id'], 1002)
        self.assertEqual(data['record_id'], 22)

    def test_add_fob_missing_id(self):
        res = self.client.post('/api/fob', json={'owner_name': 'Jane Doe'})
        self.assertEqual(res.status_code, 400)

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_delete_fob_success(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_get_dm.return_value = mock_dm

        res = self.client.delete('/api/fob/1001')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['fob_id'], 1001)
        self.assertTrue(data['deleted'])

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_update_fob_permissions_success(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_dm.set_permissions.return_value = MagicMock(status_code=200)
        mock_get_dm.return_value = mock_dm

        res = self.client.put('/api/fob/permissions', json={
            'record_id': 21,
            'permissions': [[1, True], [2, False]]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['record_id'], 21)

    @patch('door_controller.key_management_application.api.get_db_mgr')
    def test_get_swipes_data_success(self, mock_get_db):
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_db._get_connection.return_value.__enter__.return_value = mock_conn

        mock_cur.fetchall.return_value = [
            (100, 1001, 'Allowed', 'Door 01', datetime(2026, 9, 1, 12, 0, 0), '192.168.1.100')
        ]
        mock_get_db.return_value = mock_db

        res = self.client.get('/api/swipes?period=24h')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['swipes'][0]['fob_id'], 1001)

    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_get_controller_fobs_success(self, mock_get_dm):
        mock_dm = MagicMock()
        mock_dm.url = 'http://192.168.1.100'
        mock_dm.get_keyfobs.return_value = [
            ['21', '1001', 'Active', 'Permissions'],
            ['22', '1002', 'Active', 'Permissions']
        ]
        mock_get_dm.return_value = mock_dm

        res = self.client.get('/api/controller/fobs')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 2)

    @patch('door_controller.key_management_application.api.get_db_mgr')
    @patch('door_controller.key_management_application.api.get_data_manager')
    def test_get_controller_fob_permissions_success(self, mock_get_dm, mock_get_db):
        mock_dm = MagicMock()
        mock_dm.url = 'http://192.168.1.100'
        mock_dm.get_record_id.return_value = 21
        mock_dm.get_permissions_record.return_value = [["21", "1001", "Door 01", "Allow", "url"]]
        mock_get_dm.return_value = mock_dm

        mock_db = MagicMock()
        mock_db.get_expected_permissions.return_value = {1: True, 2: False}
        mock_get_db.return_value = mock_db

        res = self.client.get('/api/controller/fob/1001/permissions?timestamp=2026-09-01T12:00:00')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['fob_id'], 1001)
        self.assertEqual(data['record_id'], 21)
        self.assertEqual(data['expected_permissions'], {'1': True, '2': False})


if __name__ == '__main__':
    unittest.main()
