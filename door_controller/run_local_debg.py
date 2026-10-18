
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
from door_controller.cli_synch_tools.get_fobs import sync_controller_fobs
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
        try:
            # In-process call directly hits Flask @api_bp.route('/controller/get_max_swipe_id') via /api/controller/get_max_swipe_id
            response = self.client.get('/api/controller/get_max_swipe_id', query_string=params)
            
            if response.status_code == 200:
                return response.get_json()
            
            logging.error(f"GET /api/controller/get_max_swipe_id failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'swipes': []}
        except Exception as e:
            logging.error(f"Exception during GET /api/controller/get_max_swipe_id: {e}")
            return {'status': 'error', 'swipes': []}

    def get_fobs(self, controller_url=None, start_record_id=0, cursor=None):
        cur = cursor if cursor is not None else start_record_id
        params = {
            'controller_url': controller_url,
            'start_record_id': cur
        }
        response = self.client.get('/api/controller/fobs', query_string=params)
        if response.status_code == 200:
            return response.get_json()
        logging.error(f"GET /api/controller/fobs failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
        return {'status': 'error', 'fobs': []}

    def get_max_fob_id(self, controller_url=None):
        params = {
            'controller_url': controller_url
        }
        try:
            response = self.client.get('/api/controller/get_max_fob_id', query_string=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"GET /api/controller/get_max_fob_id failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'fobs': []}
        except Exception as e:
            logging.error(f"Exception during GET /api/controller/get_max_fob_id: {e}")
            return {'status': 'error', 'fobs': []}

    def get_fob_record_id(self, controller_url=None, fob_id=None):
        params = {
            'controller_url': controller_url,
            'fob_id': fob_id
        }
        try:
            response = self.client.get(f'/api/fob/record_id', query_string=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"GET /api/controller/get_fob_record_id failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'record_id': None}
        except Exception as e:
            logging.error(f"Exception during GET /api/controller/get_fob_record_id: {e}")
            return {'status': 'error', 'record_id': None}
        
    def set_fob_permissions(self, controller_url=None, record_id=None, permissions=None):
        params = {
            'controller_url': controller_url,
            'record_id': record_id,
            'permissions': permissions
        }
        try:
            response = self.client.put(f'/api/fob/permissions', json=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"PUT /api/controller/set_fob_permissions failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'message': 'Failed to set permissions'}
        except Exception as e:
            logging.error(f"Exception during PUT /api/fob/permissions: {e}")
            return {'status': 'error', 'message': str(e)}
        
    def add_fob(self, controller_url=None, fob_id=None, name=None):
        params = {
            'controller_url': controller_url,
            'fob_id': fob_id,
            'name': name
        }
        try:
            response = self.client.post(f'/api/fob/add', json=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"POST /api/controller/add_fob failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'message': 'Failed to add fob'}
        except Exception as e:
            logging.error(f"Exception during POST /api/controller/add_fob: {e}")
            return {'status': 'error', 'message': str(e)}

    def delete_fob(self, controller_url=None, fob_id=None):
        params = {
            'controller_url': controller_url,
            'fob_id': fob_id
        }
        try:
            response = self.client.delete(f'/api/fob/delete', json=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"DELETE /api/fob/delete failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'message': 'Failed to delete fob'}
        except Exception as e:
            logging.error(f"Exception during DELETE /api/fob/delete: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_fob_permissions(self, controller_url=None, fob_id=None, timestamp=None):
        params = {
            'controller_url': controller_url,
            'fob_id': fob_id,
            'timestamp': timestamp
        }
        try:
            response = self.client.get(f'/api/controller/fob/permissions', query_string=params)
            if response.status_code == 200:
                return response.get_json()
            logging.error(f"GET /api/controller/fob/permissions failed [{response.status_code}]: {response.data.decode('utf-8', errors='ignore')}")
            return {'status': 'error', 'permissions': []}
        except Exception as e:
            logging.error(f"Exception during GET /api/controller/fob/permissions: {e}")
            return {'status': 'error', 'permissions': []}

if __name__ == '__main__':
    config = load_config()
    db_conn = config.get('settings', {}).get('postgres_connect_string')
    db = postgres(db_conn) if db_conn else None

    debug_api = LocalDebugApiClient(app)
    urls = config.get('settings', {}).get('controller_urls', [])

    for url in urls:
        print(f"\n[*] Testing sync for: {url}")
        # sync_controller_swipes(debug_api, db, url, db_max_id=20052)
        # sync_controller_fobs(debug_api, db, url, db_max_id=20052)
        
        # Add a record

        add_result = debug_api.add_fob(controller_url=url, fob_id=123456, name="Test Fob")
        print(f"add_fob_result: {add_result}")

        result = debug_api.get_fob_record_id(controller_url=url, fob_id=123456)
        print(f"get_fob_record_id_result: {result}")

        # Set permissions for the newly added fob
        if add_result.get('status') == 'success':
            set_perm_result = debug_api.set_fob_permissions(controller_url=url, record_id=result['record_id'], permissions=[[1,1], [2, 1]])
            print(f"set_fob_permissions_result: {set_perm_result}") 

            get_perm_result = debug_api.get_fob_permissions(controller_url=url, fob_id=123456, timestamp="2024-01-01T00:00:00Z")
            print(f"get_fob_permissions_result: {get_perm_result}")

        #Delete the fob after testing
        delete_result = debug_api.delete_fob(controller_url=url, fob_id=123456)
        print(f"delete_fob_result: {delete_result}")    
