"""
Common setup and initialization helper for CLI & Database Synchronization tools.
Eliminates code duplication across CLI tool scripts.
"""

import os

from door_controller.common_lib.utils import load_config, log_info, get_current_timestamp
from door_controller.common_lib.pg_database import postgres
from door_controller.api_client import ApiClient
from door_controller import __version__


def init_cli_tool(tool_name):
    """
    Common entry initialization function for CLI tools.
    Loads configuration, sets up database connection and API client,
    and logs startup metadata.
    
    Returns:
        (config: dict, db: postgres, api_client: ApiClient)
    """
    log_info(f"--- Starting {tool_name} (v{__version__}) at {get_current_timestamp()} ---")
    config = load_config()
    if not config:
        log_info("No configuration loaded.")
        raise RuntimeError("Configuration could not be loaded.")

    log_info(f"Loaded config app_name: {config.get('app_name', 'N/A')}")
    log_info(f"Configured log_level: {config.get('settings', {}).get('log_level', 'N/A')}")
    # Check environment variable first (docker container standard), fallback to config
    env_api = os.getenv('API_URL') or os.getenv('BESEEN_API_URL')
    if env_api:
        api_url = env_api
    else:
        server_cfg = config.get('settings', {}).get('api_server', {})
        host = server_cfg.get('host', '127.0.0.1')
        port = server_cfg.get('port', 5000)
        api_url = f"http://{host}:{port}"

    api_client = ApiClient(api_url=api_url)
    return api_client