
import unittest
from unittest.mock import MagicMock, patch
from door_controller.common_lib.data_manager import DataManager

class TestDataManager(unittest.TestCase):

    def setUp(self):
        self.url = 'http://example.com'
        self.username = 'user'
        self.password = 'pass'
        self.dm = DataManager(self.url, self.username, self.password)

    @patch('door_controller.common_lib.door_controller.requests.session')
    def test_add_fob_ordering_and_auth(self, mock_session):
        # Setup mock session and response
        mock_sess_instance = MagicMock()
        mock_session.return_value = mock_sess_instance
        
        # We need to test the logic inside add_fob which calls self.connect() then self.get_httpresponse()
        # Mock get_httpresponse to return success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html>Success</html>'
        
        # We need to patch get_httpresponse directly on the instance or class strictly speaking, 
        # but since we want to verify the arguments passed to requests.post inside get_httpresponse,
        # we should patch requests.post.

        with patch('door_controller.common_lib.door_controller.requests.post') as mock_post:
            mock_post.return_value = mock_response
            
            fob_id = 12345
            name = 'TestUser'
            
            self.dm.add_fob(fob_id, name)
            
            # Verify calls
            # Expected calls:
            # 1. connect() -> POST to ACT_ID_1 (Login)
            # 2. POST to ACT_ID_21 (s1=AddCard)
            # 3. POST to ACT_ID_312 (Data with specific order)
            
            self.assertTrue(mock_post.call_count >= 3)
            
            # Check the login call
            login_call = mock_post.call_args_list[0]
            login_url = login_call[0][0]
            self.assertIn('ACT_ID_1', login_url)
            
            # Check the final add fob call
            # The last call should be the one adding the fob data
            add_call = mock_post.call_args_list[-1]
            args, kwargs = add_call
            url = args[0]
            data = kwargs['data'] # This is what we want to check order on
            
            self.assertIn('ACT_ID_312', url)
            
            # Verify data is a list of tuples and has correct order
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 3)
            self.assertEqual(data[0], ('AD21', '12345'))
            self.assertEqual(data[1], ('AD22', 'TestUser'))
            self.assertEqual(data[2], ('25', 'Add'))

if __name__ == '__main__':
    unittest.main()
