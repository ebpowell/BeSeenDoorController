# Example of common utility functions used by multiple tools
import datetime
import logging
import os

# Configure basic logging for all tools using this utility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_current_timestamp():
    """Returns the current timestamp in ISO format."""
    return datetime.datetime.now().isoformat()


def log_info(message):
    """Logs an informational message."""
    logging.info(message)


def log_error(message, exc_info=False):
    """Logs an error message, optionally with exception info."""
    logging.error(message, exc_info=exc_info)


def load_config(config_filename="config.yaml"):
    """
    Loads a YAML configuration file.
    Assumes config.yaml is in a 'data' subfolder within the package,
    or at a path mounted via Docker volume.
    """
    try:
        import yaml  # This dependency would be in requirements.txt
        # Construct path relative to the package, or look in a well-known volume mount point
        # For simplicity, let's assume it's directly accessible if mounted, or in a default path
        # config_path = os.path.join(os.getenv('APP_CONFIG_DIR', '/app/data'), config_filename)
        config_path = os.path.join(os.getenv('APP_CONFIG_DIR', './data'), config_filename)
        if not os.path.exists(config_path):
            log_info(f"Config file not found at {config_path}. Attempting to load from package default.")
            # Fallback for default config if not mounted externally
            # This requires the data folder to be copied into the image
            import pkgutil
            config_data = pkgutil.get_data('door_controller', os.path.join('data', config_filename))
            if config_data:
                return yaml.safe_load(config_data)
            else:
                log_error(f"Default config '{config_filename}' not found within package.")
                return {}

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        log_error(f"Configuration file not found: {config_path}")
        return {}
    except Exception as e:
        log_error(f"Error loading config file {config_path}: {e}", exc_info=True)
        return {}