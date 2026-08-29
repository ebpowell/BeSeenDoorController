import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.web_app.app import app
from PaymentProcessing import (
    extract_owner_last_name,
    generate_reservation_item_name,
    calculate_order_amount_cents,
    create_swipe_payment_intent
)

class TestSwipePaymentProcessor(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_user', role='ManagementCo'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    def test_extract_owner_last_name(self):
        self.assertEqual(extract_owner_last_name('John Smith'), 'Smith')
        self.assertEqual(extract_owner_last_name('Jane Van Dyke'), 'Dyke')
        self.assertEqual(extract_owner_last_name('Doe'), 'Doe')
        self.assertEqual(extract_owner_last_name(''), 'Resident')
        self.assertEqual(extract_owner_last_name(None), 'Resident')

    def test_generate_reservation_item_name(self):
        self.assertEqual(generate_reservation_item_name('John Smith'), 'Clubhouse Reservation - Smith')
        self.assertEqual(generate_reservation_item_name('Alice Cooper'), 'Clubhouse Reservation - Cooper')
        self.assertEqual(generate_reservation_item_name(''), 'Clubhouse Reservation - Resident')

    def test_calculate_order_amount_cents(self):
        self.assertEqual(calculate_order_amount_cents(15.00), 1500)
        self.assertEqual(calculate_order_amount_cents(45.50), 4550)
        self.assertEqual(calculate_order_amount_cents('30'), 3000)

    def test_create_swipe_payment_intent(self):
        res = create_swipe_payment_intent(45.00, 'John Smith', reservation_id=123)
        self.assertTrue(res['success'])
        self.assertEqual(res['item_name'], 'Clubhouse Reservation - Smith')
        self.assertEqual(res['amount_cents'], 4500)
        self.assertEqual(res['owner_last_name'], 'Smith')
        self.assertIn('clientSecret', res)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_create_payment_intent_route(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_db.list_reservations.return_value = [
            {'reservation_id': 5, 'owner_name': 'John Doe', 'fee': 30.0}
        ]
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/create_payment_intent', json={
            'reservation_id': 5,
            'amount': 30.00,
            'owner_name': 'John Doe'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data['success'])
        self.assertEqual(data['item_name'], 'Clubhouse Reservation - Doe')
        self.assertEqual(data['amount_cents'], 3000)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_confirm_payment_route_success(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/reservations/confirm_payment', json={
            'reservation_id': 5,
            'payment_intent_id': 'pi_swipe_mock_res_5_3000'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data['success'])
        self.assertEqual(data['reservation_id'], 5)
        self.assertTrue(data['payment_made'])

        mock_db.update_reservation_status.assert_called_once_with(5, 'payment_made', True, username='operator1')

    def test_confirm_payment_route_missing_reservation_id(self):
        self.set_logged_in(username='operator1')
        response = self.client.post('/reservations/confirm_payment', json={})
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
