# Example of common utility functions used by multiple tools
import datetime
import logging
import os
import webbrowser
import sys

# Configure basic logging for all tools using this utility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)
                    ]
)


def get_current_timestamp():
    """Returns the current timestamp in ISO format."""
    return datetime.datetime.now().isoformat()


def log_info(message):
    """Logs an informational message."""
    message = f"{get_current_timestamp()} - {message}"
    logging.info(message)


def log_error(message, exc_info=False):
    """Logs an error message, optionally with exception info."""
    message = f"{get_current_timestamp()} - {message}"
    logging.error(message, exc_info=exc_info)

def log_warning(message, exc_info=False):
    """Logs a warning message, optionally with exception info."""
    message = f"{get_current_timestamp()} - {message}"
    logging.warning(message, exc_info=exc_info)



def load_config(config_filename = 'config.yaml'):
    """
    Loads a YAML configuration file.
    Searches in candidate directories (APP_CONFIG_DIR, /app/config, /etc/door_controller,
    ~/.config/door_controller, or ./config).
    If the file does not exist, attempts to initialize it with default package settings
    in the first writable location so it can be edited/updated on the host system.
    """
    try:
        import yaml
        import pkgutil

        # 1. Determine list of candidate directories to search
        if config_filename == 'config.yaml': #We haven't passed a paramter, so we can use the default config.yaml and APP_CONFIG_DIR environment variable
            candidate_dirs = []
            env_dir = os.getenv('APP_CONFIG_DIR')
            if env_dir:
                candidate_dirs.append(env_dir)
            else:
                candidate_dirs.extend([
                    '/app/config',
                    '/etc/door_controller',
                    os.path.expanduser('~/.config/door_controller'),
                    './config'
                ])

            # 2. Search for the file in the candidate directories
            config_path = None
            for directory in candidate_dirs:
                possible_path = os.path.join(directory, config_filename)
                if os.path.exists(possible_path):
                    config_path = possible_path
                    break
        else:
            # If a specific config file path is provided, use it directly
            config_path = config_filename if os.path.exists(config_filename) else None

        # 3. If file exists, load it
        if config_path:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)

        # 4. If file does not exist, load default from package and try to initialize in a writable directory
        log_info(f"Config file not found in candidate directories: {candidate_dirs}. Attempting fallback.")
        config_data = pkgutil.get_data('door_controller', os.path.join('config', config_filename))
        if not config_data:
            log_error(f"Default config '{config_filename}' not found within package.")
            return {}

        default_config = yaml.safe_load(config_data)

        for directory in candidate_dirs:
            try:
                os.makedirs(directory, exist_ok=True)
                init_path = os.path.join(directory, config_filename)
                with open(init_path, 'wb') as f:
                    f.write(config_data)
                log_info(f"Initialized external config file with default settings at {init_path}")
                return default_config
            except Exception:
                continue

        log_info("Could not initialize config file in any candidate directory. Using package default in-memory.")
        return default_config

    except Exception as e:
        log_error(f"Error loading config file: {e}", exc_info=True)
        return {}

def render_output(html_string):
# html_string = "<h1>Hello World!</h1><p>This will open in your browser.</p>"

# Open from a string
    webbrowser.open_new_tab(f"data:text/html,{html_string}")

    # Or save to a file and open the file
    with open("temp.html", "w") as f:
        f.write(html_string)
    webbrowser.open_new_tab("temp.html")\

def extract_cidr(url):
    """
    Extracts the IP and appends '/32' subnet mask from a given controller URL.
    """
    ip_port = url.split("://")[-1]
    ip = ip_port.split(":")[0]
    return f"{ip}/32"

def parse_door_name(door_name):
    """
    Parses door name like "Door 01" to an integer.
    """
    if not door_name:
        return None
    digits = ''.join(c for c in door_name if c.isdigit())
    if digits:
        return int(digits)
    return None


def get_ssl_config(cli_args=None):
    """
    Resolves SSL configuration options from CLI arguments, environment variables, or config.yaml.
    """
    cfg = {
        'enabled': False,
        'cert': None,
        'key': None
    }
    
    try:
        config_data = load_config()
        ssl_section = config_data.get('ssl', {}) if isinstance(config_data, dict) else {}
        cfg['enabled'] = bool(ssl_section.get('enabled', False))
        cfg['cert'] = ssl_section.get('cert_file') or ssl_section.get('cert')
        cfg['key'] = ssl_section.get('key_file') or ssl_section.get('key')
    except Exception as e:
        log_info(f"Notice: Unable to parse ssl section from config file: {e}")

    env_ssl = os.environ.get('SSL_ENABLED', '').strip().lower()
    if env_ssl in ('true', '1', 'yes', 'on'):
        cfg['enabled'] = True
    elif env_ssl in ('false', '0', 'no', 'off'):
        cfg['enabled'] = False

    env_cert = os.environ.get('SSL_CERT') or os.environ.get('SSL_CERT_PATH') or os.environ.get('SSL_CERT_FILE')
    if env_cert:
        cfg['cert'] = env_cert

    env_key = os.environ.get('SSL_KEY') or os.environ.get('SSL_KEY_PATH') or os.environ.get('SSL_KEY_FILE')
    if env_key:
        cfg['key'] = env_key

    if cli_args:
        if getattr(cli_args, 'ssl', False):
            cfg['enabled'] = True
        if getattr(cli_args, 'cert', None):
            cfg['cert'] = getattr(cli_args, 'cert')
        if getattr(cli_args, 'key', None):
            cfg['key'] = getattr(cli_args, 'key')

    return cfg


def get_ssl_context(ssl_cfg):
    """
    Returns Flask/WSGI ssl_context based on resolved ssl_cfg.
    - If enabled and cert/key exist: returns (cert_path, key_path).
    - If enabled and no valid cert/key provided: returns 'adhoc'.
    - If disabled: returns None.
    """
    if not ssl_cfg or not ssl_cfg.get('enabled'):
        return None

    cert = ssl_cfg.get('cert')
    key = ssl_cfg.get('key')

    if cert and key:
        if os.path.exists(cert) and os.path.exists(key):
            return (cert, key)
        else:
            log_info(f"SSL Warning: Certificate path ({cert}) or Key path ({key}) not found on disk. Falling back to adhoc SSL context.")
            return 'adhoc'
    else:
        return 'adhoc'


def configure_app_security(app_instance, ssl_enabled=False):
    """
    Configures session cookie security flags and security headers on the Flask app.
    """
    app_instance.config['SESSION_COOKIE_HTTPONLY'] = True
    app_instance.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app_instance.config['SSL_ENABLED'] = ssl_enabled
    
    if ssl_enabled:
        app_instance.config['SESSION_COOKIE_SECURE'] = True
    else:
        app_instance.config['SESSION_COOKIE_SECURE'] = False

