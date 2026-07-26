import time
import os
import re
import threading
from datetime import datetime, date, timedelta

from door_controller.common_lib.utils import log_info, log_error, load_config, extract_cidr, parse_door_name

class ControllerScheduler:
     def __init__(self, controller_urls, recurrence_interval, limit_changes=None, reference_time=None):
          pass


def derive_run_schedule(self, controller_ip, reference_time=None):
        """
        Derives the run-schedule for the next 24 hours based on when permissions change
        throughout the day using key_fobs.f_get_runtimes.
        """
        ref = reference_time or datetime.now()
        today = ref.date()
        tomorrow = today + timedelta(days=1)
        
        # Fetch runtimes for today and tomorrow
        today_times = self.db_mgr.get_runtimes_for_date(today, controller_ip)
        tomorrow_times = self.db_mgr.get_runtimes_for_date(tomorrow, controller_ip)
        
        schedule = []
        
        # Helper to combine date and time
        def add_to_schedule(d, t_list):
            for t in t_list:
                if (t.hour == 0 and t.minute == 0) or (t.hour == 23 and t.minute == 59):
                    continue
                dt = datetime.combine(d, t)
                # Filter for future times within the next 24 hours relative to reference_time
                if ref < dt <= ref + timedelta(hours=24):
                    schedule.append(dt)
                    
        add_to_schedule(today, today_times)
        add_to_schedule(tomorrow, tomorrow_times)
        
        schedule.sort()
        # print(f"Controller {controller_ip} schedule: \n", schedule)
        return schedule

def run_controller_sync_loop(self, controller_url, limit_changes=None):
        """
        The main daemon scheduling loop running in its own thread for a specific controller.
        """
        log_info(f"Starting schedule check loop for controller: {controller_url}")
        
        # Initial startup synchronization to ensure consistency
        now = datetime.now()
        if (now.hour == 0 and now.minute == 0) or (now.hour == 23 and now.minute == 59):
            log_info(f"Skipping initial startup synchronization for {controller_url} at {now.strftime('%H:%M')} because it matches 12:00am/11:59pm.")
        else:
            log_info(f"Executing initial startup synchronization for {controller_url}...")
            self.synchronize_access(controller_url, limit_changes=limit_changes)
            
        last_sync_time = datetime.now()
        log_info(f"Initial synchronization complete for {controller_url}. Daemon scheduler started. last_sync_time={last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        controller_ip = extract_cidr(controller_url)
        
        while True:
            try:
                now = datetime.now()
                # Handle time backward adjustments or resets
                if now < last_sync_time:
                    last_sync_time = now
                    
                # Cap the lookback window to 24 hours to keep schedule calculation bounded
                if now - last_sync_time > timedelta(hours=24):
                    log_info(f"last_sync_time for {controller_url} is older than 24 hours. Resetting check window to the last 24 hours.")
                    last_sync_time = now - timedelta(hours=24)
                    
                # Derive schedule from the last sync time
                schedule = self.derive_run_schedule(controller_ip, reference_time=last_sync_time)
                
                # Check for any events that have occurred up to 'now'
                pending_events = [dt for dt in schedule if dt <= now]
                
                if pending_events:
                    log_info(f"Triggering synchronization for {controller_url} scheduled times: {[dt.strftime('%H:%M:%S') for dt in pending_events]}")
                    self.synchronize_access(controller_url, limit_changes=limit_changes)
                    last_sync_time = now
                    
            except Exception as e:
                log_error(f"Error in scheduler daemon loop for {controller_url}: {e}", exc_info=True)
                
            time.sleep(30)

def start_scheduler_threads(self, controller_urls, limit_changes=None):
    """
    Spawns a separate daemon thread for each controller in the controller_urls list.
    Each thread executes run_controller_sync_loop on its own schedule.
    """
    threads = []
    for url in controller_urls:
        t = threading.Thread(
            target=self.run_controller_sync_loop,
            args=(url, limit_changes),
            name=f"SyncThread-{url}"
        )
        t.daemon = True
        t.start()
        threads.append(t)
    return threads

