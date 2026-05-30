# Example of common utility functions used by multiple tools
import datetime
import logging
import os
import webbrowser

# Configure basic logging for all tools using this utility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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


def load_config(config_filename="config.yaml"):
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
    webbrowser.open_new_tab("temp.html")