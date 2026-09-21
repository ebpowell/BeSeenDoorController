"""
BeSeenDoorController - API Client Module

Provides a unified client interface (ApiClient) for communicating with the
BeSeen Door Controller REST API server (beseen-api).
If the remote REST API HTTP service is unreachable, automatically falls back to direct DataManager execution.
"""

import os
import requests
from HOA_OS_Application.archive.door_controller.common_lib.utils import load_config, log_info, log_error
from door_controller.common_lib.data_manager import DataManager


class ApiClient:
    def __init__(self, api_url=None):
        config = load_config()
        settings = config.get('settings', {}) if isinstance(config, dict) else {}
        env_url = os.getenv('BESEEN_API_URL') or os.getenv('API_URL')

        if api_url:
            self.api_url = api_url.rstrip('/')
        elif env_url:
            self.api_url = env_url.rstrip('/')
        else:
            self.api_url = 'http://beseen-api:5000'

        self.urls = settings.get('urls', ['http://192.168.1.100'])
        self.username = settings.get('username', 'admin')
        self.password = settings.get('password', 'admin')
        self.recovery_delay = settings.get('recovery_delay', 5)

    def _get_data_manager(self, controller_url=None):
        url = controller_url or (self.urls[0] if self.urls else 'http://192.168.1.100')
        return DataManager(url, self.username, self.password, self.recovery_delay)

    def get_fob_record_id(self, fob_id, controller_url=None, data_manager=None):
        """Fetches the hardware record ID for a given key fob ID."""
        try:
            params = {'controller_url': controller_url} if controller_url else None
            resp = requests.get(f"{self.api_url}/api/fob/{fob_id}/record_id", params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    return data.get('record_id')
        except Exception as e:
            log_info(f"ApiClient.get_fob_record_id fallback to DataManager: {e}")

        dm = data_manager or self._get_data_manager(controller_url)
        return dm.get_record_id(fob_id)

    def add_fob(self, fob_id, owner_name=None, controller_url=None, data_manager=None):
        """Adds a new key fob via REST API or direct fallback."""
        payload = {
            'fob_id': fob_id,
            'owner_name': owner_name or f"Fob {fob_id}",
            'controller_url': controller_url
        }
        try:
            resp = requests.post(f"{self.api_url}/api/fob", json=payload, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception as e:
            log_info(f"ApiClient.add_fob fallback to DataManager: {e}")

        dm = data_manager or self._get_data_manager(controller_url)
        res = dm.add_fob(fob_id, owner_name or f"Fob {fob_id}")
        record_id = res[1] if res and len(res) > 1 else None
        return {'status': 'success', 'fob_id': fob_id, 'record_id': record_id}

    def delete_fob(self, fob_id, controller_url=None, data_manager=None):
        """Deletes an existing key fob via REST API or direct fallback."""
        try:
            params = {'controller_url': controller_url} if controller_url else None
            resp = requests.delete(f"{self.api_url}/api/fob/{fob_id}", params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log_info(f"ApiClient.delete_fob fallback to DataManager: {e}")

        dm = data_manager or self._get_data_manager(controller_url)
        dm.del_fob(fob_id)
        return {'status': 'success', 'fob_id': fob_id, 'deleted': True}

    def del_fob(self, fob_id, controller_url=None, data_manager=None):
        """Alias for delete_fob."""
        return self.delete_fob(fob_id, controller_url=controller_url, data_manager=data_manager)

    def update_fob_permissions(self, record_id, permissions, controller_url=None, data_manager=None):
        """Updates permissions for a key fob via REST API or direct fallback."""
        payload = {
            'record_id': record_id,
            'permissions': permissions,
            'controller_url': controller_url
        }
        try:
            resp = requests.put(f"{self.api_url}/api/fob/permissions", json=payload, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log_info(f"ApiClient.update_fob_permissions fallback to DataManager: {e}")

        target_perms = []
        if isinstance(permissions, dict):
            for k, v in permissions.items():
                target_perms.append((int(k), bool(v)))
        elif isinstance(permissions, list):
            for item in permissions:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    target_perms.append((int(item[0]), bool(item[1])))

        dm = data_manager or self._get_data_manager(controller_url)
        dm.set_permissions(target_perms, record_id)
        return {'status': 'success', 'record_id': record_id, 'permissions': target_perms}

    def set_permissions(self, permissions, record_id=None, controller_url=None, data_manager=None):
        """Alias for update_fob_permissions supporting flexible argument order."""
        if isinstance(permissions, (int, str)) and record_id is not None:
            record_id, permissions = permissions, record_id
        return self.update_fob_permissions(record_id, permissions, controller_url=controller_url, data_manager=data_manager)

    def get_permissions_record(self, record_id, controller_url=None, data_manager=None):
        """Retrieves permissions record for a given hardware record ID via REST API or DataManager fallback."""
        try:
            params = {'controller_url': controller_url} if controller_url else None
            resp = requests.get(f"{self.api_url}/api/fob/record/{record_id}/permissions", params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success' and 'permissions' in data:
                    return data.get('permissions')
        except Exception as e:
            log_info(f"ApiClient.get_permissions_record fallback to DataManager: {e}")

        dm = data_manager or self._get_data_manager(controller_url)
        return dm.get_permissions_record(record_id)

    def get_controller_fobs(self, controller_url=None, data_manager=None):
        """Retrieves key fobs list stored on the hardware controller."""
        try:
            params = {'controller_url': controller_url} if controller_url else None
            resp = requests.get(f"{self.api_url}/api/controller/fobs", params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json().get('fobs', [])
        except Exception as e:
            log_info(f"ApiClient.get_controller_fobs fallback to DataManager: {e}")

        dm = data_manager or self._get_data_manager(controller_url)
        return dm.get_keyfobs() or []

    def get_swipes(self, period='24h'):
        """Retrieves card swipe activity via REST API."""
        try:
            resp = requests.get(f"{self.api_url}/api/swipes", params={'period': period}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get('swipes', [])
        except Exception as e:
            log_info(f"ApiClient.get_swipes notice: {e}")

        return []
