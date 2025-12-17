
import unittest
from unittest.mock import MagicMock, patch
from door_controller.common_lib.fobs import key_fobs

class TestKeyFobs(unittest.TestCase):

    def setUp(self):
        self.url = 'http://example.com'
        self.username = 'user'
        self.password = 'pass'
        self.kf = key_fobs(self.url, self.username, self.password)

    def test_get_permissions_record_exists(self):
        # Verify the method exists (was missing before)
        self.assertTrue(hasattr(self.kf, 'get_permissions_record'))

    @patch('door_controller.common_lib.door_controller.requests.post')
    def test_get_permissions_record_logic(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mock HTML response that parse_permissions expects
        # Based on fobs.py parse_permissions logic: 
        # markup[markup.find('</th></tr>') + 10:markup.find('</p></form></body><HEAD>') - 8]
        # And splits by <br><br>
        # And looks for 'option' and 'selected' or 'Forbid'
        # This is complex to mock perfectly without seeing real HTML, but we check if it makes the request.
        
        mock_response.text = "<html>Dummy Response ensuring no crash</html>" 
        mock_post.return_value = mock_response

        # We anticipate parse_permissions might fail or return empty on dummy text.
        # But we want to ensure the REQUEST is correct.
        
        try:
            self.kf.get_permissions_record(123)
        except Exception:
            # We expect an exception from parse logic likely, or not.
            pass
            
        # Verify call to ACT_ID_324 and E122 (123 - 1)
        # Expected data: {'E122': 'Edit'}
        
        found = False
        for call in mock_post.call_args_list:
            args, kwargs = call
            if 'ACT_ID_324' in args[0]:
                found = True
                self.assertEqual(kwargs['data'], {'E122': 'Edit'})
        
        self.assertTrue(found, "Did not find call to ACT_ID_324")

if __name__ == '__main__':
    unittest.main()
