import unittest
from unittest.mock import MagicMock
from requests import Response
from door_controller.common_lib.door_controller import validate_and_parse_controller_html, ExternalSystemError
from door_controller.common_lib.fobs import key_fobs

class TestControllerHTMLValidation(unittest.TestCase):

    def create_mock_response(self, text, status_code=200, url="http://192.168.1.100/ACT_ID_21"):
        res = Response()
        res.status_code = status_code
        res._content = text.encode('utf-8')
        res.url = url
        return res

    def test_edited_success_tag(self):
        html = "<html><body>ID:490 user is edited successfully</body></html>"
        res = self.create_mock_response(html)
        parsed = validate_and_parse_controller_html(res, expected_marker="user is edited successfully")
        self.assertIn("user is edited successfully", parsed)

    def test_add_card_success_tag(self):
        html = "<html><head><title>Web Controller</title></head><body>CardNO:123456 Add Successfully Manual Input</body></html>"
        res = self.create_mock_response(html)
        parsed = validate_and_parse_controller_html(res, expected_marker="Add Successfully")
        self.assertIn("Add Successfully", parsed)

    def test_delete_user_success_tag(self):
        html = "<html><body>ID:457 user is deleted</body></html>"
        res = self.create_mock_response(html)
        parsed = validate_and_parse_controller_html(res, expected_marker="user is deleted")
        self.assertIn("user is deleted", parsed)

    def test_search_finished_success_tag(self):
        html = "<html><body>Found Users' Count: 1. Search Finished.<tr align=center><td>457</td><td>123456</td><td>Test User</td><td>Active</td></tr></body></html>"
        res = self.create_mock_response(html)
        parsed = validate_and_parse_controller_html(res, expected_marker="Search Finished")
        self.assertIn("Search Finished", parsed)

    def test_fallback_console_without_success_tag_raises_error(self):
        html = "<html><head><title>Web Controller</title></head><body>Manual Input AutoAddBySwiping Log In Required</body></html>"
        res = self.create_mock_response(html)
        with self.assertRaises(ExternalSystemError):
            validate_and_parse_controller_html(res, expected_marker="some_marker")

    def test_missing_expected_marker_raises_error(self):
        html = "<html><body>Generic HTML response without expected data</body></html>"
        res = self.create_mock_response(html)
        with self.assertRaises(ExternalSystemError):
            validate_and_parse_controller_html(res, expected_marker="MissingMarkerKey")

    def test_parse_user_id_found(self):
        kf = key_fobs("http://192.168.1.100", "admin", "admin")
        html = "<html><body>Found Users' Count: 1. Search Finished.<tr align=center><td>457</td><td>123456</td><td>Test User</td><td>Active</td></tr></body></html>"
        user_id = kf.parse_user_id(html)
        self.assertEqual(user_id, 457)

    def test_parse_user_id_zero_found_returns_none(self):
        kf = key_fobs("http://192.168.1.100", "admin", "admin")
        html = "<html><body>Found Users' Count: 0. Search Finished.</body></html>"
        user_id = kf.parse_user_id(html)
        self.assertIsNone(user_id)

    def test_get_permissions_record_none_record_id(self):
        kf = key_fobs("http://192.168.1.100", "admin", "admin")
        result = kf.get_permissions_record(None)
        self.assertIsNone(result)

    def test_parse_permissions_malformed_html_returns_none(self):
        kf = key_fobs("http://192.168.1.100", "admin", "admin")
        result = kf.parse_permissions("<html><body>Invalid HTML structure</body></html>")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
