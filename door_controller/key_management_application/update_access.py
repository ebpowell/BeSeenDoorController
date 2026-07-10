import time
import os
import re
import threading
from datetime import datetime, date, timedelta

from door_controller.common_lib.utils import log_info, log_error, load_config
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.common_lib.pg_database import postgres
from door_controller.key_management_application.db_manager import FobDatabaseManager


class AccessSynchronizer:
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

    def parse_door_name(self, door_name):
        """
        Parses door name like "Door 01" to an integer.
        """
        if not door_name:
            return None
        digits = ''.join(c for c in door_name if c.isdigit())
        if digits:
            return int(digits)
        return None

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

    def get_owner_for_fob(self, fob_id):
        """
        Helper to get property owner name for a fob_id from database.
        """
        query = """
            SELECT concat(o.first_name, ' ', o.last_name) owner_name
            FROM key_fobs.keyfobs f
            JOIN key_fobs.properties p ON f.property_id = p.property_id
            LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
            WHERE f.fob_id = %s;
        """
        with self.db_mgr._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (fob_id,))
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
        return f"Fob {fob_id}"

    def get_expected_permissions(self, fob_id, cidr):
        """
        Helper to get expected permissions for a fob_id on a given controller from database.
        """
        query = """
            SELECT door_no, allow
            FROM key_fobs.vint_acl_data
            WHERE fob_id = %s AND controller_ip = %s
            and start_time <= now()::time and (end_time is null or end_time >= now()::time)
            and start_date <= now()::date and (end_date is null or end_date >= now()::date);
        """
        expected = {}
        with self.db_mgr._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (fob_id, cidr))
                for door_no, allow in cur.fetchall():
                    expected[int(door_no)] = bool(allow)
        return expected

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
                dt = datetime.combine(d, t)
                # Filter for future times within the next 24 hours relative to reference_time
                if ref < dt <= ref + timedelta(hours=24):
                    schedule.append(dt)
                    
        add_to_schedule(today, today_times)
        add_to_schedule(tomorrow, tomorrow_times)
        
        schedule.sort()
        return schedule

    def synchronize_access(self, controller_url, limit_changes=None):
        """
        Executes synchronization for a single controller.
        """
        log_info(f"Starting synchronization for controller: {controller_url}")
        
        changes_made = 0
        cidr = self.extract_cidr(controller_url)
        
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
        db_fobs = self.db_mgr.list_fobs() # returns dicts with fob_id
        db_fobs_keys = {int(f['fob_id']) for f in db_fobs}
        controller_fobs_keys = set(controller_fobs.keys())
        
        log_info(f"Controller {controller_url} active fobs count: {len(controller_fobs_keys)}")
        log_info(f"Postgres database fobs count: {len(db_fobs_keys)}")
        
        # Instantiate DataManager and ww_data_extractor
        data_manager = DataManager(controller_url, self.username, self.password)
        extractor = ww_data_extractor(self.username, self.password, controller_url, None)
        
        # 3. Expunge extra fobs on controller
        fobs_to_expunge = controller_fobs_keys - db_fobs_keys
        actual_fob_changes = False
        if fobs_to_expunge:
            log_info(f"Expunging {len(fobs_to_expunge)} fobs from controller {controller_url}")
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
                        actual_fob_changes = True
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
                    
        # 4. Add missing fobs to controller
        fobs_to_add = db_fobs_keys - controller_fobs_keys
        if fobs_to_add:
            log_info(f"Adding {len(fobs_to_add)} missing fobs to controller {controller_url}")
            for fob_id in fobs_to_add:
                owner_name = self.get_owner_for_fob(fob_id)
                if limit_changes is not None and changes_made >= limit_changes:
                    log_info(f"Change limit of {limit_changes} reached. Skipping addition of Fob {fob_id} (Owner: {owner_name}) to controller {controller_url}.")
                    break
                log_info(f"Adding Fob {fob_id} (Owner: {owner_name}) to controller {controller_url}")
                try:
                    # Call add_fob
                    res_resp = data_manager.add_fob(fob_id, owner_name)
                    if res_resp is None:
                        log_error(f"Failed to add Fob {fob_id} to controller {controller_url}. No response returned.")
                        continue
                    elif res_resp.status_code == 200:
                        changes_made += 1
                        actual_fob_changes = True
                        # Log to DB audit logs
                        with self.db_mgr._get_connection() as conn:
                            with conn.cursor() as cur:
                                self.db_mgr.log_audit_action(
                                    cur, 'system', 'Sync Add Fob',
                                    f"Added Fob {fob_id} (Owner {owner_name}) to controller {controller_url} (status: {res_resp.status_code})"
                                )
                            conn.commit()
                    else:
                        log_error(f"Failed to add Fob {fob_id} to controller {controller_url}. HTTP status code: {res_resp.status_code}")
                except Exception as e:
                    log_error(f"Failed to add Fob {fob_id} to controller {controller_url}: {e}")
                    
        # 5. Re-fetch current fobs from controller if any changes were made
        if actual_fob_changes:
            try:
                fobs_on_controller = self.get_all_fobs_from_controller(controller_url)
                controller_fobs = {}
                for row in fobs_on_controller:
                    try:
                        rec_id = int(row[0])
                        fob_id = int(row[1])
                        controller_fobs[fob_id] = rec_id
                    except (ValueError, TypeError):
                        continue
                controller_fobs_keys = set(controller_fobs.keys())
            except Exception as e:
                log_error(f"Error re-fetching fobs from controller {controller_url}: {e}")
                return False
                
        # 6. Check and Sync ACL permissions
        fobs_to_sync_acl = db_fobs_keys & controller_fobs_keys
        for fob_id in fobs_to_sync_acl:
            rec_id = controller_fobs[fob_id]
            log_info(f"Checking ACL rules for Fob {fob_id} (Record ID: {rec_id}) on controller {controller_url}")
            try:
                # Fetch current permissions from controller
                current_perms_rows = extractor.get_permissions_record(rec_id)
                if current_perms_rows is None:
                    log_error(f"Could not retrieve permissions for Fob {fob_id} (Record ID {rec_id})")
                    continue
                    
                current_perms = {}
                for perm_row in current_perms_rows:
                    door_name = perm_row[2]
                    door_no = self.parse_door_name(door_name)
                    allow_str = perm_row[3]
                    allow = (allow_str == "Allow")
                    if door_no is not None:
                        current_perms[door_no] = allow
                        
                # Get expected permissions from database
                expected_perms = self.get_expected_permissions(fob_id, cidr)
                
                # Compare
                delta = False
                target_perms = []
                for door_no, current_allow in current_perms.items():
                    expected_allow = expected_perms.get(door_no, False)
                    target_perms.append((door_no, expected_allow))
                    if current_allow != expected_allow:
                        delta = True
                        
                if delta:
                    if limit_changes is not None and changes_made >= limit_changes:
                        log_info(f"Change limit of {limit_changes} reached. Skipping ACL sync for Fob {fob_id} (Record ID: {rec_id}) on controller {controller_url}.")
                        break
                    log_info(f"ACL mismatch detected for Fob {fob_id} (Record ID {rec_id}) on {controller_url}. "
                             f"Current: {current_perms}, Expected: {expected_perms}. Syncing...")
                    data_manager.set_permissions(target_perms, rec_id)
                    changes_made += 1
                    # Log to DB audit logs
                    with self.db_mgr._get_connection() as conn:
                        with conn.cursor() as cur:
                            self.db_mgr.log_audit_action(
                                cur, 'system', 'Sync ACL Rules',
                                f"Updated ACL rules for Fob {fob_id} (Record ID {rec_id}) on controller {controller_url} to {target_perms}"
                            )
                        conn.commit()
                else:
                    log_info(f"ACL rules for Fob {fob_id} on {controller_url} are up-to-date.")
                    
            except Exception as e:
                log_error(f"Error syncing ACL rules for Fob {fob_id} on controller {controller_url}: {e}")
                
        log_info(f"Finished synchronization for controller: {controller_url}")
        return True

    def run_controller_sync_loop(self, controller_url, limit_changes=None):
        """
        The main daemon scheduling loop running in its own thread for a specific controller.
        """
        log_info(f"Starting schedule check loop for controller: {controller_url}")
        
        # Initial startup synchronization to ensure consistency
        log_info(f"Executing initial startup synchronization for {controller_url}...")
        self.synchronize_access(controller_url, limit_changes=limit_changes)
            
        last_sync_time = datetime.now()
        log_info(f"Initial synchronization complete for {controller_url}. Daemon scheduler started. last_sync_time={last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        controller_ip = self.extract_cidr(controller_url)
        
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


def main(argv=None):
    import sys
    import argparse
    
    if argv is None:
        if any('unittest' in arg or 'pytest' in arg for arg in sys.argv) or (len(sys.argv) > 1 and sys.argv[1] == 'discover'):
            argv = []
        else:
            argv = sys.argv[1:]
            
    parser = argparse.ArgumentParser(description="Synchronize door controllers with database fobs and ACLs.")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run as a daemon scheduling periodic updates.")
    parser.add_argument("-l", "--limit-changes", type=int, default=None, help="Limit the number of mutating changes applied per controller.")
    args = parser.parse_args(argv)

    log_info("Starting global door controller synchronization routine.")
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

    # Instantiate the AccessSynchronizer once
    synchronizer = AccessSynchronizer(username, password, connect_string)

    if args.daemon:
        log_info("Running in daemon/scheduler mode with multi-threading.")
        
        # Start a thread for each controller
        threads = synchronizer.start_scheduler_threads(urls, limit_changes=limit_changes)
        
        # Keep the main thread alive since daemon threads will exit if the main thread exits
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_info("Scheduler daemon stopped by user request.")
    else:
        # Run-once mode: run synchronizations in parallel threads and wait for them to finish
        log_info("Running single synchronization run in parallel threads.")
        threads = []
        for url in urls:
            t = threading.Thread(
                target=synchronizer.synchronize_access,
                args=(url, limit_changes),
                name=f"SyncThread-Once-{url}"
            )
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        log_info("Global door controller synchronization routine completed.")


if __name__ == '__main__':
    main()