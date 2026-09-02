"""
BeSeenDoorController - REST API Module

Provides RESTful HTTP API endpoints for door controller operations:
- get_record_id for a fob_id
- add a fob
- delete a fob
- update fob permissions
- get swipes data for a specified time period
- get fob list from controller
- get fob permissions for a given time from controller
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
import re
from typing import Dict, Any, List

from door_controller.common_lib.utils import load_config, extract_cidr, parse_door_name
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.door_controller import ExternalSystemError

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_config():
    if hasattr(current_app, 'config') and 'DOOR_CONFIG' in current_app.config:
        return current_app.config['DOOR_CONFIG']
    config = load_config()
    return config or {}


def get_db_mgr():
    if hasattr(current_app, 'db_mgr') and current_app.db_mgr is not None:
        return current_app.db_mgr
    config = get_config()
    connect_string = config.get('settings', {}).get('postgres_connect_string', 'postgresql://wentworth_user:password@localhost:5432/wentworth_db')
    return FobDatabaseManager(connect_string)


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
@api_bp.route('/swipes', methods=['GET'])
def get_swipes_data():
    period_str = request.args.get('period', '24h')
    td = parse_period_to_timedelta(period_str)
    cutoff_time = datetime.now() - td

    db_mgr = get_db_mgr()
    swipes = []
    try:
        with db_mgr._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT record_id, fob_id, status, door, swipe_timestamp, door_controller_ip
                    FROM door_controller.t_keyswipes
                    WHERE swipe_timestamp >= %s
                    ORDER BY swipe_timestamp DESC
                """, (cutoff_time,))
                rows = cur.fetchall()
                for r in rows:
                    swipes.append({
                        'record_id': r[0],
                        'fob_id': r[1],
                        'status': r[2],
                        'door': r[3],
                        'swipe_timestamp': r[4].isoformat() if hasattr(r[4], 'isoformat') else str(r[4]),
                        'door_controller_ip': r[5]
                    })
        return jsonify({
            'status': 'success',
            'period': period_str,
            'since': cutoff_time.isoformat(),
            'count': len(swipes),
            'swipes': swipes
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 6. get fob list from controller
@api_bp.route('/controller/fobs', methods=['GET'])
def get_controller_fobs():
    controller_url = request.args.get('controller_url')
    dm = get_data_manager(controller_url)
    try:
        kf_list = dm.get_keyfobs()
        return jsonify({
            'status': 'success',
            'controller_url': dm.url,
            'count': len(kf_list) if kf_list else 0,
            'fobs': kf_list or []
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
