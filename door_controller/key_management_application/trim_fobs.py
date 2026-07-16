import time
import os
import re
import threading
from datetime import datetime, date, timedelta

from door_controller.common_lib.utils import log_info, log_error, load_config
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.pg_database import postgres
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.key_management_application.db_manager import FobDatabaseManager


class RemoveOrphanedFobs:
    """ 
    Remove FobIDs from the controller that are not present in the database.
    """

    def __init__(self, username, password, db_config):  
        self.username = username
        self.password = password
        self.db_config = db_config
        self.db_mgr = FobDatabaseManager(db_config)

    def extract_cidr(self, url):
        """
        Extracts the IP and appends '/32' subnet mask from a given controller URL.
        """
        ip_port = url.split("://")[-1]
        ip = ip_port.split(":")[0]
        return f"{ip}/32"

    def get_all_fobs_from_controller(self, url):
        """
        Retrieves all fobs from the controller by using ww_data_extractor.
        """
        pg_db = postgres(self.db_mgr.conn_str)
        extractor = ww_data_extractor(self.username, self.password, url, pg_db)
        
        # Extract fob list to dataload.fobs_slop
        extractor.get_system_fob_list()
        
        # Query all fobs from dataload.fobs_slop
        cidr = self.extract_cidr(url)
        query = """
            SELECT record_id, fob_id
            FROM dataload.fobs_slop
            WHERE controller_ip = %s;
        """
        fobs = []
        with self.db_mgr._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (cidr,))
                for record_id, fob_id in cur.fetchall():
                    # Format: [record_id, fob_id] as strings to match original format
                    fobs.append([str(record_id), str(fob_id)])
                    
        # Clean up/purge the slop table
        pg_db.purge_fob_records(f"'{cidr}'")
        
        return fobs

    def remove_orphans(self, controller_url, limit_changes=None):
        """
        Executes synchronization for a single controller using database as single source of truth.
        """
        log_info(f"Starting orphan removal for controller: {controller_url}")
        
        changes_made = 0
        
        # 1. Fetch current fobs from controller
        try:
            fobs_on_controller = self.get_all_fobs_from_controller(controller_url)
        except Exception as e:
            log_error(f"Error fetching fobs from controller {controller_url}: {e}")
            return False
            
        controller_fobs = {} # fob_id -> record_id
        for row in fobs_on_controller:
            try:
                rec_id = int(row[0])
                fob_id = int(row[1])
                controller_fobs[fob_id] = rec_id
            except (ValueError, TypeError):
                continue
                
        # 2. Fetch expected fobs from database
        try:
            db_fobs = self.db_mgr.list_fobs() # returns dicts with fob_id
            db_fobs_keys = {int(f['fob_id']) for f in db_fobs}
        except Exception as e:
            log_error(f"Error fetching fobs from database: {e}")
            return False
            
        controller_fobs_keys = set(controller_fobs.keys())
        
        log_info(f"Controller {controller_url} active fobs count: {len(controller_fobs_keys)}")
        log_info(f"Postgres database fobs count: {len(db_fobs_keys)}")
    
        # 3. Expunge extra fobs on controller
        fobs_to_expunge = controller_fobs_keys - db_fobs_keys
        if fobs_to_expunge:
            log_info(f"Expunging {len(fobs_to_expunge)} fobs from controller {controller_url}")
            data_manager = DataManager(controller_url, self.username, self.password)
            for fob_id in fobs_to_expunge:
                rec_id = controller_fobs[fob_id]
                if limit_changes is not None and changes_made >= limit_changes:
                    log_info(f"Change limit of {limit_changes} reached. Skipping deletion of Fob {fob_id} (Record ID: {rec_id}) from controller {controller_url}.")
                    break
                log_info(f"Deleting Fob {fob_id} (Record ID: {rec_id}) from controller {controller_url}")
                try:
                    # Call del_fob
                    res_code = data_manager.del_fob(rec_id)
                    if res_code is None:
                        log_error(f"Failed to delete Fob {fob_id} (Record ID: {rec_id}) from controller {controller_url}. No response code returned.")
                        continue
                    elif res_code == 200:    
                        changes_made += 1
                        # Log to DB audit logs
                        with self.db_mgr._get_connection() as conn:
                            with conn.cursor() as cur:
                                self.db_mgr.log_audit_action(
                                    cur, 'system', 'Sync Expunge Fob',
                                    f"Deleted Fob {fob_id} (Record ID {rec_id}) from controller {controller_url} (status: {res_code})"
                                )
                            conn.commit()
                    else:
                        log_error(f"Failed to delete Fob {fob_id} (Record ID: {rec_id}) from controller {controller_url}. HTTP status code: {res_code}")
                except Exception as e:
                    log_error(f"Failed to delete Fob {fob_id} from controller {controller_url}: {e}")
        
        log_info(f"Finished orphan removal for controller: {controller_url}")
        return True

    def run_controller_sync_loop(self, controller_url, recurrence_interval, limit_changes=None):
        """
        The main daemon scheduling loop running in its own thread for a specific controller.
        It runs remove_orphans periodically based on the recurrence interval.
        """
        log_info(f"Starting schedule check loop for controller: {controller_url} with recurrence interval {recurrence_interval} seconds")
        
        # Initial run on startup
        log_info(f"Executing initial startup orphan removal for {controller_url}...")
        self.remove_orphans(controller_url, limit_changes=limit_changes)
        
        while True:
            try:
                # Sleep for the configured recurrence interval
                time.sleep(recurrence_interval)
                
                log_info(f"Triggering scheduled orphan removal for controller {controller_url}...")
                self.remove_orphans(controller_url, limit_changes=limit_changes)
            except Exception as e:
                log_error(f"Error in scheduler daemon loop for {controller_url}: {e}", exc_info=True)

    def start_scheduler_threads(self, controller_urls, recurrence_interval, limit_changes=None):
        """
        Spawns a separate daemon thread for each controller in the controller_urls list.
        Each thread executes run_controller_sync_loop on its own recurrence schedule.
        """
        threads = []
        for url in controller_urls:
            t = threading.Thread(
                target=self.run_controller_sync_loop,
                args=(url, recurrence_interval, limit_changes),
                name=f"SyncThread-{url}"
            )
            t.daemon = True
            t.start()
            threads.append(t)
        return threads


def main(argv=None):
    import sys
    import argparse
    
    if argv is None:
        if any('unittest' in arg or 'pytest' in arg for arg in sys.argv) or (len(sys.argv) > 1 and sys.argv[1] == 'discover'):
            argv = []
        else:
            argv = sys.argv[1:]
            
    parser = argparse.ArgumentParser(description="Remove orphaned fobs from door controllers.")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as a daemon scheduling periodic updates.")
    parser.add_argument("-l", "--limit-changes", type=int, default=None, help="Limit the number of mutating changes applied per controller.")
    args = parser.parse_args(argv)

    log_info("Starting global door controller orphan removal routine.")
    config = load_config()
    if not config:
        log_error("Failed to load configuration.")
        return
        
    connect_string = config.get('settings', {}).get('postgres_connect_string')
    if not connect_string:
        log_error("Postgres connection string not configured.")
        return
        
    username = config.get('settings', {}).get('username')
    password = config.get('settings', {}).get('password')
    urls = config.get('settings', {}).get('urls', [])
    
    if not urls:
        log_info("No door controller URLs configured for synchronization.")
        return

    limit_changes = args.limit_changes
    if limit_changes is None:
        limit_changes = config.get('settings', {}).get('limit_changes')
        
    if limit_changes is not None:
        log_info(f"Applying synchronization change limit: {limit_changes} changes per controller.")

    # Read recurrence from config (default to 3600 seconds if not specified)
    recurrence_interval = config.get('settings', {}).get('recurrence', 3600)
    log_info(f"Configured recurrence interval: {recurrence_interval} seconds.")

    # Instantiate the RemoveOrphanedFobs once
    synchronizer = RemoveOrphanedFobs(username, password, connect_string)

    if args.daemon:
        log_info("Running in daemon/scheduler mode with multi-threading.")
        
        # Start a thread for each controller
        threads = synchronizer.start_scheduler_threads(urls, recurrence_interval, limit_changes=limit_changes)
        
        # Keep the main thread alive since daemon threads will exit if the main thread exits
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_info("Scheduler daemon stopped by user request.")
    else:
        # Run-once mode: run synchronizations in parallel threads and wait for them to finish
        log_info("Running single orphan removal run in parallel threads.")
        threads = []
        for url in urls:
            t = threading.Thread(
                target=synchronizer.remove_orphans,
                args=(url, limit_changes),
                name=f"SyncThread-Once-{url}"
            )
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        log_info("Global door controller orphan removal routine completed.")


if __name__ == '__main__':
    main()