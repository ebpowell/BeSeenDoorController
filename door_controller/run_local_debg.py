# File: door_controller/run_locall_debg.py (or run_local_debug.py)
# File: door_controller/run_locall_debg.py
# File: door_controller/run_locall_debg.pycursor=cursor, 
import sys
import logging
from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from door_controller.api import api_bp
from door_controller.cli_synch_tools.get_swipes import sync_controller_swipes
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.utils import load_config

# Initialize local in-process test app
app = Flask("local_debug")
# Register api_bp: if api_bp already has url_prefix='/api', do not add it again
if not api_bp.url_prefix:
    app.register_blueprint(api_bp, url_prefix='/api')
else:
    app.register_blueprint(api_bp)

app.config['TESTING'] = True

class LocalDebugApiClient:
    def __init__(self, flask_app):
        self.client = flask_app.test_client()

    def get_swipes(self, controller_url=None, start_record_id=0):
        params = {
            'controller_url': controller_url,
            'start_record_id': start_record_id
        }
        # In-process call directly hits Flask @api_bp.route('/swipes') via /api/swipes
        response = self.client.get('/api/controller/swipes', query_string=params)
        
        if response.status_code == 200:
            return response.get_json()
        
        logging.error(f"GET /api/controller/swipes failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
        return {'status': 'error', 'swipes': []}

    def get_max_swipe_id(self, controller_url=None):
        params = {
            'controller_url': controller_url
        }
        response = self.client.get('/api/controller/get_max_swipe_id', query_string=params)
        
        if response.status_code == 200:
            return response.get_json()
        
        logging.error(f"GET /api/controller/get_max_swipe_id failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
        return {'status': 'error', 'swipes': []}

if __name__ == '__main__':
    config = load_config()
    db_conn = config.get('settings', {}).get('postgres_connect_string')
    db = postgres(db_conn) if db_conn else None

    debug_api = LocalDebugApiClient(app)
    urls = config.get('settings', {}).get('urls', [])

    for url in urls:
        print(f"\n[*] Testing sync for: {url}")
        sync_controller_swipes(debug_api, db, url, db_max_id=20052)