
from door_controller.common_lib.utils import log_info, log_error, load_config
from door_controller.common_lib.swipes import fob_swipes








if __name__ == "__main__":
    config = load_config()
    urls = config.get('settings', {}).get('urls')
    for url in urls:
        log_info(f"Fetching swipes from {url}")
        try:
            swipes_client = fob_swipes(url, config.get('settings', {}).get('username'), config.get('settings', {}).get('password'))
            swipes = swipes_client.get_swipe_range(iterations=10, rec_id_start=20083)
            log_info(f"Retrieved {len(swipes)} swipe entries from {url}.")
        except Exception as e:
            log_error(f"Error fetching swipes from {url}: {e}")

