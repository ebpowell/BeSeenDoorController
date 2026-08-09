import unittest
from unittest.mock import MagicMock, patch
import requests
from requests.adapters import HTTPAdapter
from door_controller.common_lib.door_controller import door_controller

class TestDoorControllerRetries(unittest.TestCase):

    def test_session_has_retry_adapter(self):
        ctrl = door_controller("http://69.21.119.147", "user", "pass")
        adapter_http = ctrl.session.get_adapter("http://localhost")
        adapter_https = ctrl.session.get_adapter("https://localhost")
        
        self.assertIsInstance(adapter_http, HTTPAdapter)
        self.assertIsInstance(adapter_https, HTTPAdapter)
        self.assertIsNotNone(adapter_http.max_retries)
        self.assertEqual(adapter_http.max_retries.total, ctrl.max_retries)

    @patch('door_controller.common_lib.door_controller.requests.Session.post')
    def test_get_httpresponse_handles_request_exception(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("Connection timed out")
        ctrl = door_controller("http://69.21.119.147", "user", "pass")
        ctrl.timeout = 0.01

        with self.assertRaises(requests.exceptions.RequestException):
            ctrl.get_httpresponse("http://69.21.119.147/ACT_ID_1", {"data": "test"})
        
        self.assertEqual(mock_post.call_count, ctrl.max_retries)

    @patch('door_controller.common_lib.door_controller.requests.Session.post')
    def test_get_httpresponse_success_after_initial_retry(self, mock_post):
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_post.side_effect = [requests.exceptions.RequestException("Transient error"), mock_ok]

        ctrl = door_controller("http://69.21.119.147", "user", "pass")
        ctrl.timeout = 0.01

        response = ctrl.get_httpresponse("http://69.21.119.147/ACT_ID_1", {"data": "test"})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
