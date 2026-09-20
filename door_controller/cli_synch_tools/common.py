"""
Common setup and initialization helper for CLI & Database Synchronization tools.
Eliminates code duplication across CLI tool scripts.
"""

from door_controller.common_lib.utils import load_config, log_info, get_current_timestamp
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.api_client import ApiClient
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

    db_connect_str = config.get('settings', {}).get('postgres_connect_string')
    db = None
    if db_connect_str:
        try:
            db = postgres(db_connect_str)
        except Exception as e:
            log_info(f"Notice: PostgreSQL connection deferred or failed: {e}")

    api_client = ApiClient()

    return config, db, api_client
