"""
BeSeenDoorController - REST API Module

Provides RESTful HTTP API endpoints for door controller operations:
- get_record_id for a fob_id
- add a fob
- delete a fob
- update fob permissions
- get swipes data for a specified time period
- get fob list from controller
"""

import traceback

from flask import Blueprint, request, jsonify, current_app, Flask
from datetime import datetime, timedelta
import re
import threading
from collections import defaultdict
from typing import Dict, Any, List
from door_controller.common_lib.utils import load_config, extract_cidr, parse_door_name, log_info, log_error    
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.data_extractor import ww_data_extractor as DataExtractor
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.door_controller import ExternalSystemError
from door_controller.common_lib.swipes import fob_swipes as FobSwipes

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Global mutex per controller URL to prevent overlapping scrapes
controller_locks = defaultdict(threading.Lock)

def get_config():
    if hasattr(current_app, 'config') and 'DOOR_CONFIG' in current_app.config:
        return current_app.config['DOOR_CONFIG']
    config = load_config()
    return config or {}


def get_db_mgr():
    if hasattr(current_app, 'db_mgr') and current_app.db_mgr is not None:
        return current_app.db_mgr
    config = get_config()
    connect_string = config.get('settings', {}).get('postgres_connect_string', 'postgresql://wentworth_user:password@localhost:5432/wntworth_db')
    try:
        from door_controller.common_lib.pg_database import FobDatabaseManager
        return FobDatabaseManager(connect_string)
    except Exception as e:
        raise RuntimeError(f"Database manager initialization failed: {e}")


def get_data_extractor(controller_url=None):
    config = get_config()
    settings = config.get('settings', {})
    username = settings.get('username', 'admin')
    password = settings.get('password', 'admin')    
    iterations = settings.get('iterations', 10)
    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'
    try:
        data_extractor = DataExtractor(username,
                                    password,
                                    controller_url,
                                    iterations)
        return data_extractor
    except Exception as e:
        log_error(f"\n[CRITICAL ERROR] Failed to instantiate DataExtractor: {e}", flush=True) 
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc()}, 500
        # raise RuntimeError(f"DataExtractor initialization failed for controller {controller_url}: {e}")               
    # return DataExtractor(config.get('settings', {}).get('username'),
    #                     config.get('settings', {}).get('password'), 
    #                     controller_url, 
    #                     iterations=config.get('settings', {}).get('iterations', {}))    

def get_fob_swipes(username, password,controller_url=None):
    config = get_config()
    settings = config.get('settings', {})
    # username = settings.get('username', 'admin')
    # password = settings.get('password', 'admin')    
    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'
    try:
        obj_swipes = FobSwipes(controller_url,
                               username,
                               password)
        return obj_swipes
    except Exception as e:
        log_error(f"\n[CRITICAL ERROR] Failed to instantiate DataExtractor: {e}", flush=True) 
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc()}, 500
        # raise RuntimeError(f"DataExtractor initialization failed for controller {controller_url}: {e}")               
    # return DataExtractor(config.get('settings', {}).get('username'),
    #                     config.get('settings', {}).get('password'), 
    #                     controller_url, 
    #                     iterations=config.get('settings', {}).get('iterations', {}))    

def get_data_manager(controller_url=None):
    config = get_config()
    settings = config.get('settings', {})
    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'
    username = settings.get('username', 'admin')
    password = settings.get('password', 'admin')
    retry_sleep = settings.get('recovery_delay', 5)
    return DataManager(controller_url, username, password, retry_sleep)


def parse_period_to_timedelta(period_str: str) -> timedelta:
    if not period_str:
        return timedelta(hours=24)
    period_str = period_str.strip().lower()
    match = re.match(r'^(\d+)\s*([hdwm])$', period_str)
    if not match:
        return timedelta(hours=24)
    val, unit = int(match.group(1)), match.group(2)
    if unit == 'h':
        return timedelta(hours=val)
    elif unit == 'd':
        return timedelta(days=val)
    elif unit == 'w':
        return timedelta(weeks=val)
    elif unit == 'm':
        return timedelta(days=val * 30)
    return timedelta(hours=24)


# 1. get_record_id for a fob_id
@api_bp.route('/fob/<int:fob_id>/record_id', methods=['GET'])
def get_fob_record_id(fob_id):
    controller_url = request.args.get('controller_url')
    dm = get_data_manager(controller_url)
    try:
        record_id = dm.get_record_id(fob_id)
        if record_id is None:
            return jsonify({'status': 'error', 'message': f'Record ID not found for fob_id {fob_id}'}), 404
        return jsonify({'status': 'success', 'fob_id': fob_id, 'record_id': record_id}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 2. add a fob
@api_bp.route('/fob', methods=['POST'])
def add_fob():
    data = request.get_json() or {}
    fob_id = data.get('fob_id')
    owner_name = data.get('owner_name', f'Fob {fob_id}')
    controller_url = data.get('controller_url')

    if not fob_id:
        return jsonify({'status': 'error', 'message': 'fob_id is required'}), 400

    dm = get_data_manager(controller_url)
    try:
        result = dm.add_fob(fob_id, owner_name)
        record_id = result[1] if result and len(result) > 1 else None
        return jsonify({
            'status': 'success',
            'fob_id': fob_id,
            'owner_name': owner_name,
            'record_id': record_id
        }), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 3. delete a fob
@api_bp.route('/fob/<int:fob_id>', methods=['DELETE'])
def delete_fob(fob_id):
    controller_url = request.args.get('controller_url')
    dm = get_data_manager(controller_url)
    try:
        dm.del_fob(fob_id)
        return jsonify({'status': 'success', 'fob_id': fob_id, 'deleted': True}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 4. update fob permissions
@api_bp.route('/fob/permissions', methods=['PUT'])
def update_fob_permissions():
    data = request.get_json() or {}
    record_id = data.get('record_id')
    raw_perms = data.get('permissions')
    controller_url = data.get('controller_url')

    if record_id is None or raw_perms is None:
        return jsonify({'status': 'error', 'message': 'record_id and permissions are required'}), 400

    target_perms = []
    if isinstance(raw_perms, dict):
        for k, v in raw_perms.items():
            target_perms.append((int(k), bool(v)))
    elif isinstance(raw_perms, list):
        for item in raw_perms:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                target_perms.append((int(item[0]), bool(item[1])))

    dm = get_data_manager(controller_url)
    try:
        resp = dm.set_permissions(target_perms, record_id)
        return jsonify({'status': 'success', 'record_id': record_id, 'permissions': target_perms}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 5. get swipes data for the last <time period>
@api_bp.route('controller/swipes', methods=['GET'])
def get_swipes_data():
    config = load_config()
    settings = config.get('settings', {}) if isinstance(config, dict) else {}
    username = settings.get('username', 'admin')
    password = settings.get('password', 'admin')
    iterations = int(request.args.get('iterations', settings.get('iterations', 10)))
    start_rec = int(request.args.get('start_record_id', 0))
    controller_url = request.args.get('controller_url')

    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'

    try:
        obj_swipe = FobSwipes(controller_url, username, password)
        # Using the single-page method or range method
        if hasattr(obj_swipe, 'get_swipe_page'):
            batch, next_cursor, has_more = obj_swipe.get_swipe_page(cursor=start_rec)
            swipes = batch
        else:
            swipes = obj_swipe.get_swipe_range(iterations, start_rec)

        formatted_swipes = []
        for s in swipes:
            if isinstance(s, dict):
                formatted_swipes.append(s)
            elif len(s) >= 6:
                formatted_swipes.append({
                    'record_id': s[0],
                    'fob_id': s[1],
                    'door': s[2],
                    'door_num': s[3],
                    'swipe_timestamp': s[4],
                    'door_controller_ip': s[5]
                })

        return jsonify({
            'status': 'success',
            'controller_url': controller_url,
            'count': len(formatted_swipes),
            'swipes': formatted_swipes,
            'has_more': False
        }), 200

    except Exception as e:
        log_error(f"Error in /api/swipes on {controller_url}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'controller_url': controller_url,
            'message': str(e),
            'swipes': []
        }), 502


@api_bp.route('controller/fobs', methods=['GET'])
def get_controller_fobs():
    controller_url = request.args.get('controller_url')
    cursor = request.args.get('cursor', type=int)

    config = get_config()
    settings = config.get('settings', {})
    username = settings.get('username', 'admin')
    password = settings.get('password', 'admin')

    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'

    try:
        from door_controller.common_lib.key_fobs import key_fobs
        kf = key_fobs(controller_url, username, password)
        batch, next_cursor, has_more = kf.get_fob_page(cursor=cursor)

        formatted_fobs = []
        for row in batch:
            formatted_fobs.append({
                'record_id': row[0],
                'fob_id': row[1],
                'status': row[2],
                'owner_name': row[3],
                'controller_url': row[4]
            })

        return jsonify({
            'status': 'success',
            'controller_url': controller_url,
            'count': len(formatted_fobs),
            'next_cursor': next_cursor,
            'has_more': has_more,
            'fobs': formatted_fobs
        }), 200

    except Exception as e:
        log_error(f"API /api/controller/fobs error on {controller_url}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'controller_url': controller_url,
            'message': str(e)
        }), 502

# 7. get fob permissions for a given time from controller
@api_bp.route('/controller/fob/<int:fob_id>/permissions', methods=['GET'])
def get_controller_fob_permissions(fob_id):
    controller_url = request.args.get('controller_url')
    target_time_str = request.args.get('timestamp')
    dm = get_data_manager(controller_url)
    db_mgr = get_db_mgr()
    cidr = extract_cidr(dm.url)

    target_time = None
    if target_time_str:
        try:
            target_time = datetime.fromisoformat(target_time_str)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid timestamp ISO format'}), 400

    try:
        record_id = dm.get_record_id(fob_id)
        live_perms = None
        if record_id:
            live_perms = dm.get_permissions_record(record_id)

        expected_perms = db_mgr.get_expected_permissions(fob_id, cidr)

        return jsonify({
            'status': 'success',
            'fob_id': fob_id,
            'record_id': record_id,
            'target_time': target_time.isoformat() if target_time else None,
            'expected_permissions': expected_perms,
            'live_permissions': live_perms
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 8. Get the maximum swipe recpord ID from the controller
api_bp.route('controller/get_max_swipe_id', methods=['GET'])
def get_max_swipe_id():
    config = load_config()
    settings = config.get('settings', {}) if isinstance(config, dict) else {}
    username = settings.get('username', 'admin')
    password = settings.get('password', 'admin')
    controller_url = request.args.get('controller_url')

    if not controller_url:
        urls = settings.get('urls', [])
        controller_url = urls[0] if urls else 'http://192.168.1.100'

    try:
        obj_swipe = FobSwipes(controller_url, username, password)
        # Using the single-page method or range method
        if hasattr(obj_swipe, 'get_swipe_page'):
            batch, next_cursor, has_more = obj_swipe.get_swipe_page(cursor=0)
            swipes = batch
        else:
            return jsonify({
                'status': 'error',
                'controller_url': controller_url,
                'message': 'Controller does not support get_swipe_page method'
            }), 501
        
        formatted_fobs = []
        for row in batch:
            formatted_fobs.append({
                'record_id': row[0],
                'fob_id': row[1],
                'status': row[2],
                'owner_name': row[3],
                'controller_url': row[4]
            })
        max_record_id = formatted_fobs[0]['record_id'] if formatted_fobs else None
        return jsonify({
            'status': 'success',
            'controller_url': controller_url,
            'max_record_id': max_record_id
        }), 200     
    except Exception as e:
        log_error(f"API /api/controller/get_max_swipe_id error on {controller_url}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'controller_url': controller_url,
            'message': str(e)
        }), 502


# Module-level application factory / instance for Flask CLI and debugpy
def create_app():
    application = Flask(__name__)
    application.register_blueprint(api_bp)
    return application

app = create_app()

def main():
    import argparse
    from flask import Flask
    from door_controller.common_lib.utils import get_ssl_config, get_ssl_context, configure_app_security, log_info

    parser = argparse.ArgumentParser(description="BeSeen Door Controller REST API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to run REST API (default: 5000)")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL/HTTPS")
    parser.add_argument("--cert", type=str, help="Path to SSL certificate file")
    parser.add_argument("--key", type=str, help="Path to SSL private key file")
    args = parser.parse_args()

    app = Flask(__name__)
    app.register_blueprint(api_bp)

    ssl_cfg = get_ssl_config(args)
    configure_app_security(app, ssl_enabled=ssl_cfg.get('enabled', False))
    ssl_context = get_ssl_context(ssl_cfg)

    log_info(f"Starting BeSeen Door Controller REST API on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, ssl_context=ssl_context, debug=False, threaded=True)


if __name__ == '__main__':
    main()

