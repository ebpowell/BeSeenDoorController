import unittest
from unittest.mock import MagicMock, patch
from flask import Flask

from door_controller.api import api_bp, parse_period_to_timedelta


class TestDoorControllerRESTAPI(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test_secret'
        self.app.register_blueprint(api_bp)
        self.client = self.app.test_client()

    @patch('door_controller.api.DataManager')
    def test_get_data_manager_uses_controller_urls_config(self, mock_data_manager):
        from door_controller.api import get_data_manager

        self.app.config['DOOR_CONFIG'] = {
            'settings': {
                'controller_urls': ['https://controller.example:60001'],
                'username': 'user',
                'password': 'pass',
                'recovery_delay': 5,
            }
        }
        with self.app.app_context():
            get_data_manager()

        self.assertEqual(mock_data_manager.call_args.args[0], 'https://controller.example:60001')

    def test_parse_period_to_timedelta(self):
        self.assertEqual(parse_period_to_timedelta('1h').total_seconds(), 3600)
        self.assertEqual(parse_period_to_timedelta('24h').total_seconds(), 86400)
        self.assertEqual(parse_period_to_timedelta('7d').days, 7)
        self.assertEqual(parse_period_to_timedelta('2w').days, 14)
        self.assertEqual(parse_period_to_timedelta('1m').days, 30)
        self.assertEqual(parse_period_to_timedelta('invalid').total_seconds(), 86400)

    @patch('door_controller.api.FobSwipes')
    @patch('door_controller.api.get_db_mgr')
    def test_get_swipes_data_success(self, mock_get_db, mock_fob_swipes):
        mock_swipe_inst = MagicMock()
        mock_swipe_inst.get_swipe_page.return_value = (
            [{'record_id': 100, 'fob_id': 1001, 'status': 'Allowed', 'door_num': 'Door 01', 'swipe_timestamp': '2026-09-01T12:00:00', 'door_controller_ip': '192.168.1.100'}],
            None,
            False
        )
        mock_fob_swipes.return_value = mock_swipe_inst

        mock_get_db.return_value = MagicMock()

        res = self.client.get('/api/swipes?period=24h')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['swipes'][0]['fob_id'], 1001)

    @patch('door_controller.api.get_data_manager')
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


if __name__ == '__main__':
    unittest.main()
