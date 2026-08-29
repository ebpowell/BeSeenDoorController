import os
import io
import shutil
import unittest
from unittest.mock import MagicMock, patch
from pypdf import PdfWriter
from door_controller.key_management_application.web_app.app import app
from DocumentProcessing import verify_signed_agreement

class TestAgreementUpload(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.secret_key = 'test_secret_key'
        self.client = app.test_client()
        self.upload_dir = os.path.join(os.getcwd(), 'uploads', 'agreements')

    def set_logged_in(self, username='test_user', role='ManagementCo'):
        with self.client.session_transaction() as sess:
            sess['username'] = username
            sess['role'] = role

    def create_dummy_pdf(self, content_text="Sample Document"):
        """Utility to generate an in-memory PDF file."""
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return buf

    def test_verify_signed_agreement_nonexistent_file(self):
        is_valid, msg, details = verify_signed_agreement("non_existent_file.pdf")
        self.assertFalse(is_valid)
        self.assertIn("File does not exist", msg)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    @patch('DocumentProcessing.verify_signed_agreement')
    def test_upload_agreement_success(self, mock_verify, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db
        mock_verify.return_value = (True, "Signature detected", {"signature_detected": True})

        pdf_buf = self.create_dummy_pdf("Signed PDF Content")
        data = {
            'agreement_file': (pdf_buf, 'signed_agreement.pdf')
        }

        response = self.client.post('/reservations/upload_agreement/1', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Signed PDF agreement successfully uploaded, scanned, and stored!", response.data)
        
        mock_db.update_reservation_status.assert_called_once_with(1, 'agreement_received', True, username='operator1')
        mock_verify.assert_called_once()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    @patch('DocumentProcessing.verify_signed_agreement')
    def test_upload_agreement_scan_failed(self, mock_verify, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_get_db_mgr.return_value = mock_db
        mock_verify.return_value = (False, "No signature detected", {})

        pdf_buf = self.create_dummy_pdf("Unsigned PDF Content")
        data = {
            'agreement_file': (pdf_buf, 'unsigned_agreement.pdf')
        }

        response = self.client.post('/reservations/upload_agreement/1', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Agreement verification failed: No signature detected", response.data)
        mock_db.update_reservation_status.assert_not_called()

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_upload_agreement_invalid_file_type(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        data = {
            'agreement_file': (io.BytesIO(b"Hello World"), 'document.txt')
        }

        response = self.client.post('/reservations/upload_agreement/1', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid file type. Only PDF documents (.pdf) are allowed.", response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_upload_agreement_no_file(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        response = self.client.post('/reservations/upload_agreement/1', data={}, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No file provided for upload.", response.data)

    @patch('door_controller.key_management_application.web_app.app.get_db_mgr')
    def test_view_agreement_non_existent(self, mock_get_db_mgr):
        self.set_logged_in(username='operator1')
        mock_db = MagicMock()
        mock_db.list_reservations.return_value = []
        mock_db.list_properties.return_value = []
        mock_db.list_reservation_blocks.return_value = []
        mock_db.get_reservation_fee_config.return_value = {}
        mock_get_db_mgr.return_value = mock_db

        response = self.client.get('/reservations/view_agreement/999999', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No stored agreement file found for this reservation.", response.data)

if __name__ == '__main__':
    unittest.main()
