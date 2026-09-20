import unittest
from unittest.mock import patch, MagicMock
from door_controller.common_lib.api_client import ApiClient
from door_controller.cli_synch_tools.common import init_cli_tool


class TestApiClient(unittest.TestCase):

    def setUp(self):
        self.client = ApiClient(api_url='http://127.0.0.1:5000')

    @patch('requests.get')
    def test_get_fob_record_id_api_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'success', 'record_id': 42}
        mock_get.return_value = mock_resp

        record_id = self.client.get_fob_record_id(1001)
        self.assertEqual(record_id, 42)

    @patch('door_controller.common_lib.api_client.ApiClient._get_data_manager')
    @patch('requests.get')
    def test_get_fob_record_id_fallback(self, mock_get, mock_get_dm):
        mock_get.side_effect = Exception("API down")
        mock_dm = MagicMock()
        mock_dm.get_record_id.return_value = 99
        mock_get_dm.return_value = mock_dm

        record_id = self.client.get_fob_record_id(1001)
        self.assertEqual(record_id, 99)

    @patch('requests.post')
    def test_add_fob_api_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {'status': 'success', 'fob_id': 1002, 'record_id': 10}
        mock_post.return_value = mock_resp

        res = self.client.add_fob(1002, 'John Doe')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['record_id'], 10)

    @patch('requests.delete')
    def test_delete_fob_api_success(self, mock_del):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'success', 'fob_id': 1001, 'deleted': True}
        mock_del.return_value = mock_resp

        res = self.client.delete_fob(1001)
        self.assertTrue(res['deleted'])

    @patch('requests.put')
    def test_update_fob_permissions_api_success(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'success', 'record_id': 10}
        mock_put.return_value = mock_resp

        res = self.client.update_fob_permissions(10, [[1, True]])
        self.assertEqual(res['status'], 'success')

    @patch('requests.get')
    def test_get_controller_fobs_api_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'success', 'fobs': [['10', '1001']]}
        mock_get.return_value = mock_resp

        fobs = self.client.get_controller_fobs()
        self.assertEqual(len(fobs), 1)

    @patch('door_controller.cli_synch_tools.common.load_config')
    def test_init_cli_tool(self, mock_load):
        mock_load.return_value = {
            'app_name': 'Test CLI',
            'settings': {'log_level': 'INFO', 'postgres_connect_string': ''}
        }
        config, db, client = init_cli_tool('test_tool')
        self.assertEqual(config['app_name'], 'Test CLI')
        self.assertIsNotNone(client)


if __name__ == '__main__':
    unittest.main()
