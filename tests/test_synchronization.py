import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.synchronization import (
    parse_door_name,
    get_owner_for_fob,
    get_expected_permissions,
    get_all_fobs_from_controller,
    synchronize_controller,
    main
)


class TestSynchronization(unittest.TestCase):

    def test_parse_door_name(self):
        self.assertEqual(parse_door_name("Door 01"), 1)
        self.assertEqual(parse_door_name("Door 12"), 12)
        self.assertEqual(parse_door_name("Door A"), None)
        self.assertEqual(parse_door_name(""), None)
        self.assertEqual(parse_door_name(None), None)

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager')
    def test_get_owner_for_fob(self, mock_db_mgr_class):
        mock_db_mgr = mock_db_mgr_class.return_value
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        # Test case: Owner exists
        mock_cur.fetchone.return_value = ("Alice Owner",)
        owner = get_owner_for_fob(mock_db_mgr, 1001)
        self.assertEqual(owner, "Alice Owner")

        # Test case: Owner does not exist
        mock_cur.fetchone.return_value = None
        owner = get_owner_for_fob(mock_db_mgr, 9999)
        self.assertEqual(owner, "Fob 9999")

    @patch('door_controller.key_management_application.db_manager.FobDatabaseManager')
    def test_get_expected_permissions(self, mock_db_mgr_class):
        mock_db_mgr = mock_db_mgr_class.return_value
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        mock_cur.fetchall.return_value = [
            (1, True),
            (2, False)
        ]
        perms = get_expected_permissions(mock_db_mgr, 1001, '69.21.119.147/32')
        self.assertEqual(perms, {1: True, 2: False})

    @patch('door_controller.key_management_application.synchronization.key_fobs')
    def test_get_all_fobs_from_controller(self, mock_key_fobs_class):
        mock_kf = mock_key_fobs_class.return_value
        mock_kf.connect.return_value.status_code = 200
        
        # Mock pages
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.text = "page 1 html"
        
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.text = "page 2 html"

        mock_kf.get_httpresponse.side_effect = [mock_response_1, mock_response_2]
        
        # parse_fobs_data mock returns:
        # page 1: [["21", "1001"], ["22", "1002"]]
        # page 2: [["23", "1003"]]
        mock_kf.parse_fobs_data.side_effect = [
            [["21", "1001"], ["22", "1002"]],
            [["23", "1003"]]
        ]
        
        fobs = get_all_fobs_from_controller('http://69.21.119.147', 'admin', 'password')
        self.assertEqual(len(fobs), 3)
        self.assertEqual(fobs[0][1], "1001")
        self.assertEqual(fobs[2][1], "1003")

    @patch('door_controller.key_management_application.synchronization.get_all_fobs_from_controller')
    @patch('door_controller.key_management_application.synchronization.get_owner_for_fob')
    @patch('door_controller.key_management_application.synchronization.get_expected_permissions')
    @patch('door_controller.key_management_application.synchronization.DataManager')
    @patch('door_controller.key_management_application.synchronization.ww_data_extractor')
    def test_synchronize_controller(self, mock_extractor_class, mock_dm_class, mock_get_expected_perms, mock_get_owner, mock_get_all_fobs):
        # 1. Setup DB manager mock
        mock_db_mgr = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_db_mgr._get_connection.return_value.__enter__.return_value = mock_conn

        # DB has fobs 1001 and 1002
        mock_db_mgr.list_fobs.return_value = [
            {'fob_id': 1001},
            {'fob_id': 1002}
        ]

        # 2. Setup get_all_fobs_from_controller mock
        # Initial controller state: has 1001 and 1003 (extra fob to delete, missing 1002)
        mock_get_all_fobs.side_effect = [
            [["21", "1001"], ["23", "1003"]], # first call
            [["21", "1001"], ["22", "1002"]]  # second call (after updates)
        ]

        mock_get_owner.return_value = "Bob Owner"

        # Expected permissions mock
        # Fob 1001 has Door 1 allowed, Door 2 forbidden
        # Fob 1002 has Door 1 allowed, Door 2 allowed
        mock_get_expected_perms.side_effect = [
            {1: True, 2: False}, # for 1001
            {1: True, 2: True}   # for 1002
        ]

        # 3. Setup extractor and DataManager mocks
        mock_extractor = mock_extractor_class.return_value
        # For fob 1001: door 1 allowed, door 2 allowed (mismatch on door 2)
        # For fob 1002: door 1 allowed, door 2 allowed (match)
        mock_extractor.get_permissions_record.side_effect = [
            [["21", "1001", "Door 01", "Allow", "url"], ["21", "1001", "Door 02", "Allow", "url"]], # 1001
            [["22", "1002", "Door 01", "Allow", "url"], ["22", "1002", "Door 02", "Allow", "url"]]  # 1002
        ]

        mock_dm = mock_dm_class.return_value

        # Run synchronization
        res = synchronize_controller('http://69.21.119.147', 'admin', 'password', mock_db_mgr)
        
        self.assertTrue(res)

        # Verify deletion of fob 1003 (record id 23)
        mock_dm.del_fob.assert_called_once_with(
            {'username': 'admin', 'pwd': 'password', 'logid': '20101222'},
            23
        )

        # Verify addition of fob 1002 (owner "Bob Owner")
        mock_dm.add_fob.assert_called_once_with(1002, "Bob Owner")

        # Verify setting permissions for 1001 (door 2 forbidden)
        # target_perms: [(1, True), (2, False)]
        mock_dm.set_permissions.assert_called_once_with(
            [(1, True), (2, False)],
            21
        )

    @patch('door_controller.key_management_application.synchronization.load_config')
    @patch('door_controller.key_management_application.synchronization.FobDatabaseManager')
    @patch('door_controller.key_management_application.synchronization.synchronize_controller')
    def test_main(self, mock_sync_controller, mock_db_mgr_class, mock_load_config):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db',
                'username': 'admin',
                'password': 'password',
                'urls': ['http://69.21.119.147', 'http://69.21.119.148']
            }
        }

        main()

        self.assertEqual(mock_sync_controller.call_count, 2)
        mock_sync_controller.assert_any_call(
            'http://69.21.119.147', 'admin', 'password', mock_db_mgr_class.return_value
        )
        mock_sync_controller.assert_any_call(
            'http://69.21.119.148', 'admin', 'password', mock_db_mgr_class.return_value
        )


if __name__ == '__main__':
    unittest.main()
