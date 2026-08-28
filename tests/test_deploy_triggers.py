import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys

from door_controller.key_management_application.deploy_triggers import deploy, get_sql_files, find_init_dir

class TestDeployTriggers(unittest.TestCase):

    @patch('door_controller.key_management_application.deploy_triggers.os.path.isdir')
    @patch('door_controller.key_management_application.deploy_triggers.os.listdir')
    def test_get_sql_files_sorting(self, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = [
            "03_fob_sync_trigger.sql",
            "01_init_db.sql",
            "README.md",
            "02_f_get_runtimes.sql"
        ]
        files = get_sql_files("init")
        self.assertEqual(files, [
            "init/01_init_db.sql",
            "init/02_f_get_runtimes.sql",
            "init/03_fob_sync_trigger.sql"
        ])

    @patch('door_controller.key_management_application.deploy_triggers.load_config')
    @patch('door_controller.key_management_application.deploy_triggers.psycopg2.connect')
    @patch('door_controller.key_management_application.deploy_triggers.find_init_dir')
    @patch('door_controller.key_management_application.deploy_triggers.get_sql_files')
    @patch('builtins.open', new_callable=mock_open, read_data="CREATE TRIGGER test;")
    def test_deploy_success(self, mock_file, mock_get_sql_files, mock_find_init_dir, mock_connect, mock_load_config):
        # Configure mocks
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://wentworth_user:ww_s3cret@localhost/wntworth_db'
            }
        }
        mock_find_init_dir.return_value = "init"
        mock_get_sql_files.return_value = [
            "init/01_init_db.sql",
            "init/02_f_get_runtimes.sql",
            "init/03_fob_sync_trigger.sql",
            "init/04_observability.sql",
            "init/05_f_get_permissions.sql",
            "init/06_gcal_sync_trigger.sql",
            "init/07_v_export_runtimes.sql",
            "init/08_f_get_group_for_runtime.sql"
        ]
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        deploy()
        
        # Assert database commands were executed sequentially for all 8 files
        mock_connect.assert_called_once_with('postgresql://wentworth_user:ww_s3cret@localhost/wntworth_db')
        self.assertEqual(mock_cur.execute.call_count, 8)
        mock_cur.execute.assert_any_call("CREATE TRIGGER test;")
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('door_controller.key_management_application.deploy_triggers.load_config')
    def test_deploy_missing_conn_str(self, mock_load_config):
        mock_load_config.return_value = {
            'settings': {}
        }
        
        with self.assertRaises(SystemExit) as cm:
            deploy()
        self.assertEqual(cm.exception.code, 1)

    @patch('door_controller.key_management_application.deploy_triggers.load_config')
    @patch('door_controller.key_management_application.deploy_triggers.find_init_dir')
    def test_deploy_missing_sql_file(self, mock_find_init_dir, mock_load_config):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db'
            }
        }
        mock_find_init_dir.return_value = None
        
        with self.assertRaises(SystemExit) as cm:
            deploy()
        self.assertEqual(cm.exception.code, 1)

    @patch('door_controller.key_management_application.deploy_triggers.load_config')
    @patch('door_controller.key_management_application.deploy_triggers.psycopg2.connect')
    @patch('door_controller.key_management_application.deploy_triggers.find_init_dir')
    @patch('door_controller.key_management_application.deploy_triggers.get_sql_files')
    @patch('builtins.open', new_callable=mock_open, read_data="CREATE TRIGGER test;")
    def test_deploy_db_error(self, mock_file, mock_get_sql_files, mock_find_init_dir, mock_connect, mock_load_config):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db'
            }
        }
        mock_find_init_dir.return_value = "init"
        mock_get_sql_files.return_value = ["init/01_init_db.sql"]
        
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.execute.side_effect = Exception("Syntax error")
        
        with self.assertRaises(SystemExit) as cm:
            deploy()
        self.assertEqual(cm.exception.code, 1)
        mock_conn.commit.assert_not_called()
        mock_conn.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()

