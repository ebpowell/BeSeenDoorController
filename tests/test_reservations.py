import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app

class TestReservations(unittest.TestCase):

    def setUp(self):
        # Configure application for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_user', role='ManagementCo'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_reservations_route_renders(self, mock_get_db_mgr):
        self.set_logged_in()
        mock_db = MagicMock()
        mock_db.list_reservations.return_value = [
            {
                'reservation_id': 1,
                'property_id': 10001,
                'reservation_date': '2026-07-04',
                'from_time': '12:00:00',
                'to_time': '18:00:00',
                'payment_made': True,
                'deposit_on_file': False,
                'agreement_received': False,
                'address': '101 Main St',
                'owner_name': 'John Doe'
            }
        ]
        mock_db.list_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_db.list_reservation_blocks.return_value = [
            {'block_key': 'block1', 'block_name': 'Block 1: Morning', 'start_time': '08:00:00', 'end_time': '12:00:00', 'display_order': 1}
        ]
        mock_db.get_reservation_fee_config.return_value = {'single_block_fee': 15.0, 'multi_block_fee': 30.0}
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/reservations')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Clubhouse Reservations Registry', response.data)
        self.assertIn(b'101 Main St', response.data)
        self.assertIn(b'John Doe', response.data)
        mock_db.list_reservations.assert_called_once()
        mock_db.list_properties.assert_called_once()
        mock_db.list_reservation_blocks.assert_called_once()
        mock_db.get_reservation_fee_config.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_reservation_post_blocks(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations', data={
            'property_id': '10001',
            'reservation_date': '2026-07-04',
            'event_type': 'Private Event',
            'blocks': ['block1', 'block2'],
            'early_setup': 'on',
            'payment_made': 'on',
            'deposit_on_file': 'on',
            'agreement_received': 'on'
        })
        
        self.assertEqual(response.status_code, 302)
        mock_db.add_reservation.assert_called_once_with(
            property_id=10001,
            reservation_date='2026-07-04',
            from_time=None,
            to_time=None,
            blocks=['block1', 'block2'],
            early_setup=True,
            payment_made=True,
            deposit_on_file=True,
            agreement_received=True,
            event_type='Private Event',
            username='operator1'
        )

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_reservation_post_community_organization(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations', data={
            'property_id': '10001',
            'reservation_date': '2026-07-04',
            'event_type': 'Community Organization',
            'blocks': ['block1'],
            'payment_made': 'on'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        mock_db.add_reservation.assert_called_once_with(
            property_id=10001,
            reservation_date='2026-07-04',
            from_time=None,
            to_time=None,
            blocks=['block1'],
            early_setup=False,
            payment_made=True,
            deposit_on_file=False,
            agreement_received=False,
            event_type='Community Organization',
            username='operator1'
        )
        self.assertIn(b'Calculated Fee: $7.50', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_reservation_community_organization_early_setup_rejected(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_db.add_reservation.side_effect = ValueError("Early set-up is not allowed for Community Organization events.")
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations', data={
            'property_id': '10001',
            'reservation_date': '2026-07-04',
            'event_type': 'Community Organization',
            'blocks': ['block1'],
            'early_setup': 'on'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Early set-up is not allowed for Community Organization events.', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_add_reservation_early_setup_rejected_when_prior_reservation_exists(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_db.add_reservation.side_effect = ValueError("Early set-up is not allowed because another reservation exists in the previous 24 hours.")
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations', data={
            'property_id': '10001',
            'reservation_date': '2026-07-04',
            'blocks': ['block1'],
            'early_setup': 'on'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Early set-up is not allowed because another reservation exists in the previous 24 hours.', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_delete_reservation_post(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_db.delete_reservation.return_value = True
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/delete/1')
        self.assertEqual(response.status_code, 302)
        mock_db.delete_reservation.assert_called_once_with(1, username='operator1')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_toggle_payment_post(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/toggle_payment/1', data={
            'current_value': 'false'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_reservation_status.assert_called_once_with(1, 'payment_made', True, username='operator1')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_toggle_deposit_post(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/toggle_deposit/1', data={
            'current_value': 'true'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_reservation_status.assert_called_once_with(1, 'deposit_on_file', False, username='operator1')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_toggle_agreement_post(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/toggle_agreement/1', data={
            'current_value': 'false'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.update_reservation_status.assert_called_once_with(1, 'agreement_received', True, username='operator1')

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_api_search_properties(self, mock_get_db_mgr):
        self.set_logged_in()
        mock_db = MagicMock()
        mock_db.search_properties.return_value = [
            {'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}
        ]
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/api/properties/search?q=John')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [{'property_id': 10001, 'address': '101 Main St', 'owner_name': 'John Doe'}])
        mock_db.search_properties.assert_called_once_with('John')

if __name__ == '__main__':
    unittest.main()
