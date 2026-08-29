import unittest
from unittest.mock import MagicMock, patch
from door_controller.key_management_application.ledger_manager import (
    Posting,
    Transaction,
    LedgerEngine
)
from door_controller.key_management_application.web_app.app import app

class TestLedgerFeature(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()

    def set_logged_in(self, username='test_user', role='ManagementCo'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    def test_posting_creation(self):
        p = Posting("Assets:Checking", 150.00)
        self.assertEqual(p.account_name, "Assets:Checking")
        self.assertEqual(p.amount, 150.00)
        self.assertEqual(p.commodity, "USD")

    def test_balanced_transaction(self):
        postings = [
            Posting("Assets:Checking", 150.00),
            Posting("Income:ClubhouseRentalFees", -150.00)
        ]
        tx = Transaction(payee="Clubhouse Rental Fee - Smith", postings=postings, date="2026-08-29")
        self.assertEqual(tx.payee, "Clubhouse Rental Fee - Smith")
        self.assertEqual(len(tx.postings), 2)

    def test_unbalanced_transaction_raises_error(self):
        postings = [
            Posting("Assets:Checking", 150.00),
            Posting("Income:ClubhouseRentalFees", -100.00)
        ]
        with self.assertRaises(ValueError):
            Transaction(payee="Unbalanced Entry", postings=postings)

    def test_transaction_fewer_than_two_postings_raises_error(self):
        with self.assertRaises(ValueError):
            Transaction(payee="Single Entry", postings=[Posting("Assets:Checking", 100.00)])

    def test_ledger_engine_balances_and_summary(self):
        engine = LedgerEngine()
        
        # Transaction 1: Deposit $150 into Escrow from Checking
        tx1 = Transaction(
            payee="Security Deposit Escrow - Smith",
            postings=[
                Posting("Liabilities:Escrow:ClubhouseSecurityDeposits", -150.00),
                Posting("Assets:Checking", 150.00)
            ]
        )
        engine.add_transaction(tx1)

        # Transaction 2: Deposit $500 Rental Income into Checking
        tx2 = Transaction(
            payee="Rental Fee Income",
            postings=[
                Posting("Assets:Checking", 500.00),
                Posting("Income:ClubhouseRentalFees", -500.00)
            ]
        )
        engine.add_transaction(tx2)

        # Transaction 3: Maintenance Expense $100 paid from Checking
        tx3 = Transaction(
            payee="Plumbing Maintenance",
            postings=[
                Posting("Expenses:Maintenance", 100.00),
                Posting("Assets:Checking", -100.00)
            ]
        )
        engine.add_transaction(tx3)

        summary = engine.get_financial_summary()
        self.assertEqual(summary["checking_balance"], 550.00)
        self.assertEqual(summary["escrow_balance"], 150.00)
        self.assertEqual(summary["total_income"], 500.00)
        self.assertEqual(summary["total_expenses"], 100.00)

        journal = engine.export_ledger_journal()
        self.assertIn("Security Deposit Escrow - Smith", journal)
        self.assertIn("Assets:Checking", journal)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_ledger_view_get(self, mock_get_db_mgr):
        self.set_logged_in()
        mock_db = MagicMock()
        mock_db.list_ledger_transactions.return_value = [
            {
                'tx_id': 1,
                'date': '2026-08-29',
                'payee': 'Initial Escrow Deposit',
                'notes': 'Check #1001',
                'postings': [
                    {'account_name': 'Assets:Checking', 'amount': 150.0, 'commodity': 'USD'},
                    {'account_name': 'Liabilities:Escrow:ClubhouseSecurityDeposits', 'amount': -150.0, 'commodity': 'USD'}
                ]
            }
        ]
        mock_db.get_ledger_financial_summary.return_value = {
            'checking_balance': 150.0,
            'investment_balance': 0.0,
            'escrow_balance': 150.0,
            'total_income': 0.0,
            'total_expenses': 0.0,
            'net_assets': 0.0
        }
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/ledger')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Financial Ledger', response.data)
        self.assertIn(b'Initial Escrow Deposit', response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_ledger_view_post_success(self, mock_get_db_mgr):
        self.set_logged_in()
        mock_db = MagicMock()
        mock_db.add_ledger_transaction.return_value = 42
        mock_get_db_mgr.return_value = mock_db

        response = self.client.post('/ledger', data={
            'tx_date': '2026-08-29',
            'payee': 'Security Deposit Deposit',
            'dr_account': 'Assets:Checking',
            'cr_account': 'Liabilities:Escrow:ClubhouseSecurityDeposits',
            'dr_amount': '150.00',
            'notes': 'Check #5541'
        })
        self.assertEqual(response.status_code, 302)
        mock_db.add_ledger_transaction.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_api_ledger_summary_route(self, mock_get_db_mgr):
        self.set_logged_in()
        mock_db = MagicMock()
        mock_db.get_ledger_financial_summary.return_value = {
            'checking_balance': 1000.0,
            'investment_balance': 5000.0,
            'escrow_balance': 150.0,
            'total_income': 2000.0,
            'total_expenses': 500.0,
            'net_assets': 5850.0
        }
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/api/ledger/summary')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data['checking_balance'], 1000.0)
        self.assertEqual(data['escrow_balance'], 150.0)

if __name__ == '__main__':
    unittest.main()
