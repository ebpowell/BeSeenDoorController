import time
import os
import re
import threading
import math
from datetime import datetime, date, timedelta

from door_controller.common_lib.utils import log_info, log_error, load_config, extract_cidr, parse_door_name
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.controller_scheduler import ControllerScheduler
from door_controller.key_management_application.collect_metrics import collect_metrics_stats
from door_controller.common_lib.door_controller import ExternalSystemError

class ExternalSystemError(Exception):
    """Raised when the door controller system returns a non-200 status code."""
    def __init__(self, status_code, response_body=None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Request failed with status code: {status_code}")


class AccessSynchronizer(ControllerScheduler):
    """
        Update the permissions for the fobs on a door controller based on the database schedule rules
        Add any missing fobs to the controller and set permissions. 
    """
    def __init__(self, username, password, config):  
        db_mgr = FobDatabaseManager(config.get('settings', {}).get('postgres_connect_string'))
        super().__init__(db_mgr, use_runtime_schedule=True)
        self.username = username
        self.password = password
        self.db_mgr = db_mgr
        self.config = config
        self.recovery_delay = config.get('settings', {}).get('recovery_delay')
        self.max_retries = config.get('settings', {}).get('retry_attempts')
        self.throttle_delay = config.get('settings', {}).get('throttle_delay')
        self.max_batch_size = config.get('settings', {}).get('max_batch_size')
        self.num_batches = config.get('settings', {}).get('num_batches')
        if hasattr(self.db_mgr, 'ensure_db_functions'):
            self.db_mgr.ensure_db_functions()

    def execute_action(self, controller_url, limit_changes=None):
        """
        Executes Section 1 (Pre-check), Section 2 (4-batch Sync with recovery delays), and Section 3 (Post-check).
        Allows 5 seconds between sections and batches for the controller board hardware to recover.
        Targeted specifically to controller_url so telemetry collection aligns cleanly with controller sync.
        """
        # Section 1: Sync (4 batches with 5s recovery delays)
        log_info(f"Section 1/2: Executing 4-batch permissions synchronization for controller: {controller_url}")
        result = self.synchronize_access(controller_url, limit_changes=limit_changes, num_batches=self.num_batches,
                                          max_batch_size=self.max_batch_size, 
                                          throttle_delay=self.throttle_delay)

        log_info(f"Section 1 Complete. Pausing {self.recovery_delay} seconds for controller board recovery...")
        time.sleep(self.recovery_delay)

        # Section 2: Post-check
        log_info(f"Section 2/2: Executing post-synchronization data quality collection for controller: {controller_url}")
        try:
            collect_metrics_stats(sync_phase='post_sync', target_controller_url=controller_url, config=self.config)
        except Exception as e:
            log_error(f"Post-sync metrics collection error for {controller_url}: {e}")
        log_info(f"Section 2 Complete for controller{controller_url}")
        return result

    def extract_cidr(self, url):
        return extract_cidr(url)

    def parse_door_name(self, name):
        return parse_door_name(name)

    def get_expected_permissions(self, fob_id, cidr):
        # Densify the expected permissions from the database for a given fob_id and controller CIDR
        # Need a door count to generate a default permissions dictionary if no results are found
        lst_doors = self.db_mgr.get_door_details(cidr)
        if not lst_doors:
            log_error(f"No doors found for CIDR {cidr}. Cannot generate expected permissions.")
            return {}
        lst_results = self.db_mgr.get_expected_permissions(fob_id, cidr)
        if not lst_results:
            # Generate a default permissions dictionary with all doors set to False
            default_perms = {door_no: False for door_no in range(1, len(lst_doors) + 1)}  # Assuming doors are numbered 1 to 4
            return default_perms
        else:
            return lst_results

    def synchronize_access(
        self, 
        controller_url, 
        limit_changes=None, 
        num_batches=None, 
        max_batch_size=10, 
        throttle_delay=0.15
    ):
        """
        Executes synchronization for a single controller using database as single source of truth.
        Divides fob processing into dynamic size-based batches (target max_batch_size, default 10) or num_batches
        with recovery_delay seconds (default 5s) between batches, and throttle_delay micro-delays between requests
        to prevent controller board overload.
        """
        log_info(f"Starting synchronization for controller: {controller_url}")
        
        changes_made = 0
        cidr = extract_cidr(controller_url)
        
        # Synchronize dynamic clubhouse reservation permissions
        try:
            if hasattr(self.db_mgr, 'sync_clubhouse_reservation_permissions'):
                self.db_mgr.sync_clubhouse_reservation_permissions()
        except Exception as e:
            log_error(f"Error syncing clubhouse reservation permissions: {e}")
            
        # Fetch expected fobs from database
        try:
            groups = self.db_mgr.get_groups_for_controller(cidr) if hasattr(self.db_mgr, 'get_groups_for_controller') else None
            db_fobs = []
            if groups and isinstance(groups, (list, tuple)):
                for group in groups:
                    gid = group.get('group_id') if isinstance(group, dict) else group
                    db_fobs.extend(self.db_mgr.list_fobs(group_id=gid))
            if not db_fobs:
                db_fobs = self.db_mgr.list_fobs()
            db_fobs_keys = sorted(list({int(f['fob_id']) for f in db_fobs if isinstance(f, dict) and 'fob_id' in f}))
        except Exception as e:
            log_error(f"Error fetching expected fobs from database: {e}")
            return False
            
        total_fobs = len(db_fobs_keys)
        log_info(f"Postgres database fobs count: {total_fobs}")
        
        # Instantiate DataManager
        # *** TO DO **: Pass retry_sleep from config if available, else default to 1 second
        if hasattr(self.db_mgr, 'get_retry_sleep'):
            retry_sleep = self.db_mgr.get_retry_sleep()
        else:
            retry_sleep = self.recovery_delay
        data_manager = DataManager(controller_url, self.username, self.password, retry_sleep)

        if total_fobs == 0:
            log_info(f"No fobs to synchronize for controller: {controller_url}")
            return True

        # Dynamic, Size-Based Batch Calculation
        if num_batches is None:
            num_batches = math.ceil(total_fobs / max_batch_size) if total_fobs > 0 else 1

        chunk_size = math.ceil(total_fobs / num_batches) if total_fobs > 0 else 1
        fob_batches = [db_fobs_keys[i:i + chunk_size] for i in range(0, total_fobs, chunk_size)]

        log_info(f"Divided {total_fobs} fobs into {len(fob_batches)} dynamic batch(es) "
                 f"(Target size: ~{chunk_size} fobs) for controller {controller_url}")

        fobs_to_add = []
        limit_reached = False
        for batch_idx, batch_fobs in enumerate(fob_batches, start=1):
            if limit_reached:
                break

            log_info(f"Processing Batch {batch_idx}/{len(fob_batches)} ({len(batch_fobs)} fobs) for controller {controller_url}...")
            
            for fob_id in batch_fobs:
                if throttle_delay > 0:
                    time.sleep(throttle_delay)

                rec_id = None
                try:
                    rec_id = data_manager.get_record_id(fob_id)
                except Exception as e:
                    log_error(f"Failed to check Fob {fob_id} existence on controller {controller_url}. Error: {e}")
                    
                if not rec_id:
                    log_info(f"Record ID not found for Fob {fob_id}. Queueing for follow-on addition to controller {controller_url}.")
                    owner = self.db_mgr.get_owner_for_fobid(fob_id)
                    owner_name = owner[:30] if owner else f"Fob {fob_id}"
                    fobs_to_add.append((fob_id, owner_name))
                    continue

                try:
                    current_perms_rows = data_manager.get_permissions_record(rec_id)
                    if current_perms_rows is None:
                        log_error(f"Could not retrieve permissions for Fob {fob_id} (Record ID {rec_id}) on controller {controller_url}, purging")
                        # DELETE FOB
                        data_manager.del_fob(fob_id)
                        continue

                    current_perms = {}
                    for perm_row in current_perms_rows:
                        door_name = perm_row[2]
                        door_no = parse_door_name(door_name)
                        allow_str = perm_row[3]
                        allow = (allow_str == "Allow")
                        if door_no is not None:
                            current_perms[door_no] = allow
                            
                    expected_perms = self.get_expected_permissions(fob_id, cidr)
                    
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
                            limit_reached = True
                            break
                        log_info(f"ACL mismatch detected for Fob {fob_id} (Record ID {rec_id}) on {controller_url}. "
                                 f"Current: {current_perms}, Expected: {expected_perms}. Syncing...")
                        response = data_manager.set_permissions(target_perms, rec_id)
                        if response is None:
                            raise ExternalSystemError(
                                status_code=500, 
                                response_body="Connection failed. Max retries reached with no response."
                            )
                        
                        if getattr(response, 'status_code', None) != 200:
                            raise ExternalSystemError(
                                status_code=getattr(response, 'status_code', 500),
                                response_body=getattr(response, 'text', '')
                            )
                        changes_made += 1
                        with self.db_mgr._get_connection() as conn:
                            with conn.cursor() as cur:
                                self.db_mgr.log_audit_action(
                                    cur, 'system', 'Sync ACL Rules',
                                    f"Updated ACL rules for Fob {fob_id} (Record ID {rec_id}) on controller {controller_url} to {target_perms}"
                                )
                            conn.commit()
                    # else:
                    #     log_info(f"ACL rules for Fob {fob_id} on {controller_url} are up-to-date.")

                except ExternalSystemError as e:
                    print(f"Error updating permissions: {e} (Status: {e.status_code})")
                    print(f"Response details: {e.response_body}")
                        
                except Exception as e:
                    log_error(f"Error syncing ACL rules for Fob {fob_id} on controller {controller_url}: {e}")

            # Allow recovery_delay (5s) between batches so the controller hardware recovers
            if batch_idx < len(fob_batches) and not limit_reached:
                log_info(f"Batch {batch_idx}/{len(fob_batches)} complete for {controller_url}. Pausing {self.recovery_delay} seconds for board recovery...")
                time.sleep(self.recovery_delay)

        # Process follow-on missing fob additions after existing fob ACL sync completes
        if fobs_to_add and not limit_reached:
            log_info(f"Main sync complete. Processing {len(fobs_to_add)} missing fob(s) in follow-on pass for controller {controller_url}...")
            time.sleep(self.recovery_delay)

            for fob_id, owner_name in fobs_to_add:
                if limit_changes is not None and changes_made >= limit_changes:
                    log_info(f"Change limit of {limit_changes} reached. Skipping remaining missing fob additions on {controller_url}.")
                    break

                try:
                    log_info(f"Follow-on pass: Adding Fob {fob_id} ({owner_name}) to controller {controller_url}...")
                    add_fob_result = data_manager.add_fob(fob_id, owner_name)
                    time.sleep(self.recovery_delay)

                    if add_fob_result and add_fob_result[1]:
                        rec_id = add_fob_result[1]
                        log_info(f"Fob:{fob_id} owned by: {owner_name} was added as record: {rec_id} to controller: {controller_url}")
                        
                        log_info(f"Updating permissions for record: {rec_id}")
                        expected_perms = self.get_expected_permissions(fob_id, cidr)
                        target_perms_new = [(door_no, expected_perms.get(door_no, False)) for door_no in (1, 2, 3, 4)]
                        response = data_manager.set_permissions(target_perms_new, rec_id)
                        changes_made += 1
                        time.sleep(self.recovery_delay)
                    else:
                        log_error(f"Fob {fob_id} addition returned no record ID on controller {controller_url}.")
                except ExternalSystemError as e:
                    log_error(f"ExternalSystemError adding Fob {fob_id} on {controller_url}: Status {e.status_code}")
                except Exception as e:
                    log_error(f"Error adding Fob {fob_id} in follow-on pass on controller {controller_url}: {e}")

        log_info(f"Finished synchronization for controller: {controller_url}. Total changes made: {changes_made}")
        return True

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
    parser.add_argument("-c", "--config", type=str, default=None, help="Path to configuration file (optional).")

    args = parser.parse_args(argv)

    log_info("Starting global door controller synchronization routine.")
    if args.config:
        config = load_config(args.config)
    else:
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
    # TO DO: Consider passing max_retries and retry_sleep from config if available, else default to 1 second
    synchronizer = AccessSynchronizer(username, password, config)

    if args.daemon:
        log_info("Running in daemon/scheduler mode with multi-threading.")
        
        # Start a thread for each controller
        threads = synchronizer.start_scheduler_threads(urls, limit_changes=limit_changes)
        
        # Keep the main thread alive since daemon threads will exit if the main thread exits
        try:
            while True:
                # WE can repeat every five minutes....
                time.sleep(1)
        except KeyboardInterrupt:
            log_info("Scheduler daemon stopped by user request.")
    else:
        # Run-once mode: run synchronizations in parallel threads and wait for them to finish
        log_info("Running single synchronization run with built-in pre- and post-sync metrics collection.")
        threads = []
        for url in urls:
            t = threading.Thread(
                target=synchronizer.execute_action,
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