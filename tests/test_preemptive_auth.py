import unittest
from unittest.mock import MagicMock, patch
import time

from door_controller.common_lib.door_controller import door_controller, ExternalSystemError
from door_controller.common_lib.fobs import key_fobs


class TestPreemptiveAuthentication(unittest.TestCase):

    def setUp(self):
        self.url = 'http://192.168.1.100'
        self.username = 'admin'
        self.password = 'password'
        self.dc = door_controller(self.url, self.username, self.password, session_timeout_secs=180)

    def test_is_session_viable_fresh(self):
        self.dc._logged_in = True
        self.dc.last_login_time = time.time()
        self.assertTrue(self.dc.is_session_viable())

    def test_is_session_viable_expired(self):
        self.dc._logged_in = True
        self.dc.last_login_time = time.time() - 200  # 200s > 180s timeout
        self.assertFalse(self.dc.is_session_viable())

    def test_is_session_viable_unauthenticated(self):
        self.dc._logged_in = False
        self.dc.last_login_time = 0.0
        self.assertFalse(self.dc.is_session_viable())

    @patch.object(door_controller, 'connect')
    def test_verify_or_reauth_active(self, mock_connect):
        self.dc._logged_in = True
        self.dc.last_login_time = time.time()
        res = self.dc.verify_or_reauth()
        self.assertTrue(res)
        mock_connect.assert_not_called()

    @patch.object(door_controller, 'connect')
    def test_verify_or_reauth_expired_reconnects(self, mock_connect):
        self.dc._logged_in = True
        self.dc.last_login_time = time.time() - 200
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_connect.return_value = mock_resp

        res = self.dc.verify_or_reauth()
        self.assertTrue(res)
        mock_connect.assert_called_once()

    @patch.object(door_controller, 'connect')
    def test_verify_or_reauth_fails_raises_exception(self, mock_connect):
        self.dc._logged_in = True
        self.dc.last_login_time = time.time() - 200
        mock_connect.return_value = None

        with self.assertRaises(ExternalSystemError):
            self.dc.verify_or_reauth()

    @patch.object(key_fobs, 'get_httpresponse')
    @patch.object(key_fobs, 'verify_or_reauth')
    @patch.object(key_fobs, 'connect')
    def test_fobs_preemptive_auth_check(self, mock_connect, mock_verify, mock_get_http):
        kf = key_fobs(self.url, self.username, self.password)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Total Users: 0 <th>Operation</th></tr></table></p>"
        mock_connect.return_value = mock_resp
        mock_get_http.return_value = mock_resp

        kf.get_keyfobs()
        mock_verify.assert_called_once()


if __name__ == '__main__':
    unittest.main()
