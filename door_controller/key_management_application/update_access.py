import time
import os
import re
import threading
from datetime import datetime, date, timedelta

from door_controller.common_lib.utils import log_info, log_error, load_config, extract_cidr, parse_door_name
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.key_management_application.db_manager import FobDatabaseManager
from door_controller.common_lib.controller_scheduler import ControllerScheduler

from door_controller.key_management_application.collect_metrics import collect_metrics_stats

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
    def __init__(self, username, password, db_mgr_or_config):  
        if hasattr(db_mgr_or_config, '_get_connection') or hasattr(db_mgr_or_config, 'list_fobs'):
            db_mgr = db_mgr_or_config
        else:
            db_mgr = FobDatabaseManager(db_mgr_or_config)
            
        super().__init__(db_mgr, use_runtime_schedule=True)
        self.username = username
        self.password = password
        self.db_config = db_mgr.conn_str
        self.db_mgr = db_mgr
        if hasattr(self.db_mgr, 'ensure_db_functions'):
            self.db_mgr.ensure_db_functions()

    def execute_action(self, controller_url, limit_changes=None):
        """
        Executes pre-sync data quality collection, access synchronization, and post-sync data quality collection.
        """
        log_info(f"Executing pre-synchronization metrics collection for controller: {controller_url}")
        try:
            collect_metrics_stats(sync_phase='pre_sync')
        except Exception as e:
            log_error(f"Pre-sync metrics collection error for {controller_url}: {e}")

        result = self.synchronize_access(controller_url, limit_changes=limit_changes)

        log_info(f"Executing post-synchronization metrics collection for controller: {controller_url}")
        try:
            collect_metrics_stats(sync_phase='post_sync')
        except Exception as e:
            log_error(f"Post-sync metrics collection error for {controller_url}: {e}")

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

    def synchronize_access(self, controller_url, limit_changes=None):
        """
        Executes synchronization for a single controller using database as single source of truth.
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
            db_fobs = self.db_mgr.list_fobs()
            db_fobs_keys = {int(f['fob_id']) for f in db_fobs}
        except Exception as e:
            log_error(f"Error fetching expected fobs from database: {e}")
            return False
            
        log_info(f"Postgres database fobs count: {len(db_fobs_keys)}")
        
        # Instantiate DataManager
        data_manager = DataManager(controller_url, self.username, self.password)
        
        # Iterate over database fobs and synchronize
        for fob_id in db_fobs_keys:
            try:
                rec_id = data_manager.get_record_id(fob_id)
            except Exception as e:
                log_error(f"Failed to check Fob {fob_id} existence on controller {controller_url}. Error: {e}")
                # continue
                
            if not rec_id:
                log_info(f"Record ID not found for Fob {fob_id}. Adding to controller {controller_url}.")
                owner = self.db_mgr.get_owner_for_fobid(fob_id)
                owner_name = owner[:30] if owner else f"Fob {fob_id}"
                try:
                    add_fob_result = data_manager.add_fob(fob_id, owner_name)
                    if add_fob_result:
                        if add_fob_result[1]:
                            rec_id = add_fob_result[1]
                            log_info(f"Fob:{fob_id} owned by: {owner_name} was added as record: {rec_id} to controller: {controller_url}")
                            
                            # Get permissions for Fobid from database
                            log_info(f"Updating permissions for record: {rec_id}")
                            expected_perms = self.get_expected_permissions(fob_id, cidr)
                            target_perms_new = [(door_no, expected_perms.get(door_no, False)) for door_no in (1, 2, 3, 4)]
                            # Update the controller
                            response = data_manager.set_permissions(target_perms_new, rec_id)
                            changes_made += 1
                            continue
                        else:
                            log_error(f"Fob: {fob_id} not added;")
                            continue
                    else:
                        log_error(f"Fob: {fob_id} addition failed;")
                        continue
                except Exception as e:
                    log_error(f"Failed to add Fob {fob_id} to controller {controller_url}. Error: {e}")
                    continue
                    
            log_info(f"Checking ACL rules for Fob {fob_id} (Record ID: {rec_id}) on controller {controller_url}")
            try:
                # Fetch current permissions from controller
                current_perms_rows = data_manager.get_permissions_record(rec_id)
                if current_perms_rows is None:
                    log_error(f"Could not retrieve permissions for Fob {fob_id} (Record ID {rec_id}) on controller {controller_url}")
                    # continue
                    # Add the fob and set permissions
                    try:
                        add_fob_result = data_manager.add_fob(fob_id, owner_name[:30])
                        if add_fob_result:
                            if add_fob_result[1]:
                                rec_id = add_fob_result[1]
                                log_info(f"Fob:{fob_id} owned by: {owner_name} was added as record: {rec_id} to controller: {controller_url}")
                                
                                # Get permissions for Fobid from database
                                log_info(f"Updating permissions for record: {rec_id}")
                                expected_perms = self.get_expected_permissions(fob_id, cidr)
                                target_perms_new = [(door_no, expected_perms.get(door_no, False)) for door_no in (1, 2, 3, 4)]
                                # Update the controller
                                response = data_manager.set_permissions(target_perms_new, rec_id)
                                changes_made += 1
                                continue
                            else:
                                log_error(f"Fob: {fob_id} not added;")
                                continue
                        else:
                            log_error(f"Fob: {fob_id} addition failed;")
                            continue
                    except Exception as e:
                        log_error(f"Failed to add Fob {fob_id} to controller {controller_url}. Error: {e}")
                        continue

                current_perms = {}
                for perm_row in current_perms_rows:
                    door_name = perm_row[2]
                    door_no = parse_door_name(door_name)
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
                    response = data_manager.set_permissions(target_perms, rec_id)
                    # 1. Handle a completely failed request (e.g., max retries hit, returning None)
                    if response is None:
                        raise ExternalSystemError(
                            status_code=500, 
                            response_body="Connection failed. Max retries reached with no response."
                        )
                    
                    # 2. Check for non-200 status codes
                    if response.status_code != 200:
                        raise ExternalSystemError(
                            status_code=response.status_code,
                            response_body=getattr(response, 'text', '') # Safe access to body text if it exists
                        )
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

            except ExternalSystemError as e:
                    # Log the exact details, then either handle it or re-raise it
                    print(f"Error updating permissions: {e} (Status: {e.status_code})")
                    print(f"Response details: {e.response_body}")
                    
            except Exception as e:
                log_error(f"Error syncing ACL rules for Fob {fob_id} on controller {controller_url}: {e}")
                
        log_info(f"Finished synchronization for controller: {controller_url}")
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