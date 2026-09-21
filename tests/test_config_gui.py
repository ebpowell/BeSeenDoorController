import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
import json
import yaml

from door_controller.config_gui import app, get_config_file_path, save_config_to_disk


class TestConfigGUI(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.testing = True
        self.client = self.app.test_client()

    def test_index_route(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'DoorController_Driver_API', res.data)
        self.assertIn(b'Remote Configuration Manager', res.data)

    @patch('door_controller.config_gui.load_config')
    @patch('door_controller.config_gui.get_config_file_path')
    def test_get_config_api(self, mock_get_path, mock_load):
        mock_get_path.return_value = '/dummy/config.yaml'
        mock_load.return_value = {
            'app_name': 'Test App',
            'settings': {'log_level': 'INFO', 'urls': ['http://127.0.0.1']}
        }

        res = self.client.get('/api/config')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['file_path'], '/dummy/config.yaml')
        self.assertEqual(data['config']['app_name'], 'Test App')

    @patch('door_controller.config_gui.save_config_to_disk')
    def test_update_config_api_success(self, mock_save):
        mock_save.return_value = '/dummy/config.yaml'
        payload = {
            'app_name': 'New App Name',
            'settings': {'log_level': 'DEBUG', 'urls': ['http://192.168.1.50']}
        }

        res = self.client.post('/api/config', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        mock_save.assert_called_once_with(payload)

    def test_update_config_api_invalid_json(self):
        res = self.client.post('/api/config', data="not json", content_type='application/json')
        self.assertEqual(res.status_code, 400)

    @patch('requests.get')
    def test_test_controller_api_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        res = self.client.post('/api/test-controller', json={'url': 'http://192.168.1.100'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['status_code'], 200)

    @patch('requests.get')
    def test_test_controller_api_unreachable(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        res = self.client.post('/api/test-controller', json={'url': 'http://192.168.1.100'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('Connection refused', data['message'])

    def test_test_controller_api_missing_url(self):
        res = self.client.post('/api/test-controller', json={})
        self.assertEqual(res.status_code, 400)

    @patch('psycopg2.connect')
    def test_test_db_api_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        res = self.client.post('/api/test-db', json={'connect_string': 'postgresql://user:pass@localhost:5432/db'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        mock_conn.close.assert_called_once()

    def test_test_db_api_missing_string(self):
        res = self.client.post('/api/test-db', json={})
        self.assertEqual(res.status_code, 400)

    def test_save_config_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'config.yaml')
            with patch('door_controller.config_gui.get_config_file_path', return_value=test_file):
                data = {'app_name': 'Test Save', 'settings': {'log_level': 'INFO'}}
                saved_path = save_config_to_disk(data)
                self.assertEqual(saved_path, test_file)
                self.assertTrue(os.path.exists(test_file))
                with open(test_file, 'r') as f:
                    loaded = yaml.safe_load(f)
                    self.assertEqual(loaded['app_name'], 'Test Save')


if __name__ == '__main__':
    unittest.main()
