import unittest
from unittest.mock import MagicMock, patch
import sys
import os

from door_controller.key_management_application.collect_metrics import main

class TestCollectMetrics(unittest.TestCase):

    @patch('door_controller.key_management_application.collect_metrics.load_config')
    @patch('door_controller.key_management_application.collect_metrics.psycopg2.connect')
    @patch('door_controller.key_management_application.collect_metrics.DataManager')
    @patch('door_controller.key_management_application.collect_metrics.random.sample')
    def test_collect_metrics_success(self, mock_sample, mock_dm_class, mock_connect, mock_load_config):
        # 1. Configure configuration mocks
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://wentworth_user:ww_s3cret@localhost/wntworth_db',
                'username': 'admin',
                'password': 'password123',
                'urls': ['http://69.21.119.147']
            }
        }

        # 2. Configure Database connection/cursor mocks
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        # Mock database calls for controllers, fobs, and views
        # get_active_controllers, get_active_fobs, missing view, unassigned view
        mock_cur.fetchall.side_effect = [
            [( '69.21.119.147', )], # active controllers
            [(1001,), (1002,)],       # active fobs
            [( '69.21.119.147', 1)], # missing assigned view count
            [( '69.21.119.147', 2)], # unassigned count
            [(1, 1)] # expected permissions query: door_no=1, allow=1
        ]

        # 3. Configure DataManager and random sampling mocks
        mock_dm = MagicMock()
        mock_dm_class.return_value = mock_dm
        mock_dm.navigate.return_value = MagicMock(status_code=200)
        
        # Auditing sample fobs
        mock_dm.get_record_id.return_value = 21 # record ID on controller
        mock_dm.get_permissions_record.return_value = [
            [21, 1001, 'Door 01', 'Allow', 'http://69.21.119.147'],
            [21, 1001, 'Door 02', 'Forbid', 'http://69.21.119.147']
        ]

        # Audit sample will select 1001
        mock_sample.return_value = [1001]

        # Run main function
        # Mock sys.argv to supply parameters
        with patch.object(sys, 'argv', ['collect_metrics', '--sample-size', '1']):
            main()

        # 4. Verify Database Interaction and Metrics Writing
        mock_connect.assert_called_once_with('postgresql://wentworth_user:ww_s3cret@localhost/wntworth_db')
        
        # Verify that ensure_metrics_table_exists table was created
        mock_cur.execute.assert_any_call("""
        CREATE TABLE IF NOT EXISTS door_controller.controller_metrics (
            metric_id SERIAL PRIMARY KEY,
            metric_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            controller_ip CIDR,
            metric_name VARCHAR(100) NOT NULL,
            metric_value NUMERIC NOT NULL,
            metadata JSONB
        );
    """)

        # Verify views counts were fetched
        mock_cur.execute.assert_any_call("""
            SELECT controller_ip, count(*) 
            FROM door_controller.vext_system_missing_assigned_fobs 
            GROUP BY controller_ip;
        """)
        mock_cur.execute.assert_any_call("""
            SELECT controller_ip, count(*) 
            FROM door_controller.vext_system_unassigned_fobs 
            GROUP BY controller_ip;
        """)

        # Verify metrics were recorded
        # DB-only metrics
        mock_cur.execute.assert_any_call("""
        INSERT INTO door_controller.controller_metrics (controller_ip, metric_name, metric_value, metadata)
        VALUES (%s, %s, %s, %s);
    """, ('69.21.119.147', 'missing_assigned_fobs_count', 1, None))
        mock_cur.execute.assert_any_call("""
        INSERT INTO door_controller.controller_metrics (controller_ip, metric_name, metric_value, metadata)
        VALUES (%s, %s, %s, %s);
    """, ('69.21.119.147', 'unassigned_fobs_count', 2, None))

        # Controller audit metrics (integrity score etc)
        # Expected: audited_fobs_count = 1, mismatched = 0, integrity_score = 1.0
        mock_cur.execute.assert_any_call("""
        INSERT INTO door_controller.controller_metrics (controller_ip, metric_name, metric_value, metadata)
        VALUES (%s, %s, %s, %s);
    """, ('69.21.119.147', 'controller_online', 1, None))

        # Check transactions committed and connection closed
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called_once()

    @patch('door_controller.key_management_application.collect_metrics.load_config')
    @patch('door_controller.key_management_application.collect_metrics.psycopg2.connect')
    def test_collect_metrics_missing_config(self, mock_connect, mock_load_config):
        mock_load_config.return_value = {
            'settings': {}
        }
        
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['collect_metrics']):
                main()
        self.assertEqual(cm.exception.code, 1)
        mock_connect.assert_not_called()

    @patch('door_controller.key_management_application.collect_metrics.load_config')
    @patch('door_controller.key_management_application.collect_metrics.psycopg2.connect')
    def test_collect_metrics_db_connection_error(self, mock_connect, mock_load_config):
        mock_load_config.return_value = {
            'settings': {
                'postgres_connect_string': 'postgresql://db'
            }
        }
        mock_connect.side_effect = Exception("Connection refused")
        
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['collect_metrics']):
                main()
        self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()
