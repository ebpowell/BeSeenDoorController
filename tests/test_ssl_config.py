import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

from door_controller.key_management_application.web_app.app import (
    app,
    get_ssl_config,
    get_ssl_context,
    configure_app_security
)

class TestSSLConfig(unittest.TestCase):

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {}, clear=False)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_get_ssl_config_defaults(self):
        # Ensure env vars are clean
        for var in ['SSL_ENABLED', 'SSL_CERT', 'SSL_KEY', 'SSL_CERT_PATH', 'SSL_KEY_PATH']:
            os.environ.pop(var, None)

        with patch('door_controller.key_management_application.web_app.app.load_config', return_value={}):
            cfg = get_ssl_config()
            self.assertFalse(cfg['enabled'])
            self.assertIsNone(cfg['cert'])
            self.assertIsNone(cfg['key'])

    def test_get_ssl_config_env_vars(self):
        os.environ['SSL_ENABLED'] = 'true'
        os.environ['SSL_CERT'] = '/path/to/cert.pem'
        os.environ['SSL_KEY'] = '/path/to/key.pem'

        cfg = get_ssl_config()
        self.assertTrue(cfg['enabled'])
        self.assertEqual(cfg['cert'], '/path/to/cert.pem')
        self.assertEqual(cfg['key'], '/path/to/key.pem')

    def test_get_ssl_config_cli_args(self):
        mock_args = MagicMock()
        mock_args.ssl = True
        mock_args.cert = '/cli/cert.pem'
        mock_args.key = '/cli/key.pem'

        cfg = get_ssl_config(cli_args=mock_args)
        self.assertTrue(cfg['enabled'])
        self.assertEqual(cfg['cert'], '/cli/cert.pem')
        self.assertEqual(cfg['key'], '/cli/key.pem')

    def test_get_ssl_context_disabled(self):
        cfg = {'enabled': False, 'cert': None, 'key': None}
        self.assertIsNone(get_ssl_context(cfg))

    def test_get_ssl_context_adhoc(self):
        cfg = {'enabled': True, 'cert': None, 'key': None}
        self.assertEqual(get_ssl_context(cfg), 'adhoc')

    def test_get_ssl_context_valid_files(self):
        with tempfile.NamedTemporaryFile() as cert_f, tempfile.NamedTemporaryFile() as key_f:
            cfg = {'enabled': True, 'cert': cert_f.name, 'key': key_f.name}
            ctx = get_ssl_context(cfg)
            self.assertEqual(ctx, (cert_f.name, key_f.name))

    def test_get_ssl_context_missing_files_fallback(self):
        cfg = {'enabled': True, 'cert': '/nonexistent/cert.pem', 'key': '/nonexistent/key.pem'}
        ctx = get_ssl_context(cfg)
        self.assertEqual(ctx, 'adhoc')

    def test_configure_app_security(self):
        test_app = Flask('test_app')
        configure_app_security(test_app, ssl_enabled=True)

        self.assertTrue(test_app.config['SSL_ENABLED'])
        self.assertTrue(test_app.config['SESSION_COOKIE_SECURE'])
        self.assertTrue(test_app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(test_app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

        configure_app_security(test_app, ssl_enabled=False)
        self.assertFalse(test_app.config['SSL_ENABLED'])
        self.assertFalse(test_app.config['SESSION_COOKIE_SECURE'])

    def test_enforce_ssl_redirect_headers(self):
        app.config['TESTING'] = True
        app.config['SSL_ENABLED'] = True

        client = app.test_client()
        # Request with HTTP header
        res = client.get('/login', headers={'X-Forwarded-Proto': 'http'})
        self.assertEqual(res.status_code, 301)
        self.assertTrue(res.location.startswith('https://'))

if __name__ == '__main__':
    unittest.main()
