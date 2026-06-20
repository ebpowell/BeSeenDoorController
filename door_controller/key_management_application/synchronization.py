import time
import os
import re
from datetime import datetime, date, timedelta
from door_controller.common_lib.utils import log_info, log_error, load_config
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.fobs import key_fobs
from door_controller.common_lib.data_extractor import ww_data_extractor
from door_controller.key_management_application.db_manager import FobDatabaseManager


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


def get_all_fobs_from_controller(url, username, password):
    """
    Retrieves all fobs from the controller in memory.
    """
    obj_keyfobs = key_fobs(url, username, password)
    
    # 1. Authenticate
    data = {
        'username': username,
        'pwd': password,
        'logid': '20101222'
    }
    response = obj_keyfobs.connect(data)
    if not response or response.status_code != 200:
        raise Exception(f"Failed to authenticate with controller {url}")
        
    fobs = []
    
    # 2. Fetch page 1
    obj_keyfobs.session.headers['Referer'] = url + '/ACT_ID_1'
    page_url = url + '/ACT_ID_21'
    page_data = {'s2': 'Users'}
    response = obj_keyfobs.get_httpresponse(page_url, page_data)
    if not response or response.status_code != 200:
        return fobs
        
    batch = obj_keyfobs.parse_fobs_data(response.text)
    if not batch:
        return fobs
        
    fobs.extend(batch)
    
    # Keep paging until we get an empty batch or the same last index
    next_index = int(batch[-1][0])
    visited_indices = {next_index}
    
    for _ in range(100):
        # Fetch next page
        obj_keyfobs.session.headers['Referer'] = url + '/ACT_ID_21' if len(fobs) <= 20 else url + '/ACT_ID_325'
        page_url = url + '/ACT_ID_325'
        page_data = {
            'PC': f"000{next_index-19}",
            'PE': f"000{next_index}",
            'PN': 'Next'
        }
        response = obj_keyfobs.get_httpresponse(page_url, page_data)
        if not response or response.status_code != 200:
            break
            
        batch = obj_keyfobs.parse_fobs_data(response.text)
        if not batch:
            break
            
        new_records = [r for r in batch if int(r[0]) not in [int(f[0]) for f in fobs]]
        if not new_records:
            break
            
        fobs.extend(new_records)
        if len(batch) < 20:
            break
        next_index = int(batch[-1][0])
        if next_index in visited_indices:
            break
        visited_indices.add(next_index)
        
    return fobs


def get_owner_for_fob(db_mgr, fob_id):
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
    with db_mgr._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (fob_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    return f"Fob {fob_id}"


def get_expected_permissions(db_mgr, fob_id, cidr):
    """
    Helper to get expected permissions for a fob_id on a given controller from database.
    """
    query = """
        SELECT door_no, allow
        FROM key_fobs.vint_acl_data
        WHERE fob_id = %s AND controller_ip = %s;
    """
    expected = {}
    with db_mgr._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (fob_id, cidr))
            for door_no, allow in cur.fetchall():
                expected[int(door_no)] = bool(allow)
    return expected


def synchronize_controller(url, username, password, db_mgr, limit_changes=None):
    """
    Executes synchronization for a single controller.
    """
    log_info(f"Starting synchronization for controller: {url}")
    
    changes_made = 0
    cidr = url[7:] + '/32'
    
    # 1. Fetch current fobs from controller
    try:
        fobs_on_controller = get_all_fobs_from_controller(url, username, password)
    except Exception as e:
        log_error(f"Error fetching fobs from controller {url}: {e}")
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
    db_fobs = db_mgr.list_fobs() # returns dicts with fob_id
    db_fobs_keys = {int(f['fob_id']) for f in db_fobs}
    controller_fobs_keys = set(controller_fobs.keys())
    
    log_info(f"Controller {url} active fobs count: {len(controller_fobs_keys)}")
    log_info(f"Postgres database fobs count: {len(db_fobs_keys)}")
    
    # Instantiate DataManager and ww_data_extractor
    data_manager = DataManager(url, username, password)
    extractor = ww_data_extractor(username, password, url, None)
    login_data = {
        'username': username,
        'pwd': password,
        'logid': '20101222'
    }
    
    # 3. Expunge extra fobs on controller
    fobs_to_expunge = controller_fobs_keys - db_fobs_keys
    actual_fob_changes = False
    if fobs_to_expunge:
        log_info(f"Expunging {len(fobs_to_expunge)} fobs from controller {url}")
        for fob_id in fobs_to_expunge:
            rec_id = controller_fobs[fob_id]
            if limit_changes is not None and changes_made >= limit_changes:
                log_info(f"Change limit of {limit_changes} reached. Skipping deletion of Fob {fob_id} (Record ID: {rec_id}) from controller {url}.")
                continue
            log_info(f"Deleting Fob {fob_id} (Record ID: {rec_id}) from controller {url}")
            try:
                # Call del_fob
                res_code = data_manager.del_fob(login_data, rec_id)
                changes_made += 1
                actual_fob_changes = True
                # Log to DB audit logs
                with db_mgr._get_connection() as conn:
                    with conn.cursor() as cur:
                        db_mgr.log_audit_action(
                            cur, 'system', 'Sync Expunge Fob',
                            f"Deleted Fob {fob_id} (Record ID {rec_id}) from controller {url} (status: {res_code})"
                        )
                    conn.commit()
            except Exception as e:
                log_error(f"Failed to delete Fob {fob_id} from controller {url}: {e}")
                
    # 4. Add missing fobs to controller
    fobs_to_add = db_fobs_keys - controller_fobs_keys
    if fobs_to_add:
        log_info(f"Adding {len(fobs_to_add)} missing fobs to controller {url}")
        for fob_id in fobs_to_add:
            owner_name = get_owner_for_fob(db_mgr, fob_id)
            if limit_changes is not None and changes_made >= limit_changes:
                log_info(f"Change limit of {limit_changes} reached. Skipping addition of Fob {fob_id} (Owner: {owner_name}) to controller {url}.")
                continue
            log_info(f"Adding Fob {fob_id} (Owner: {owner_name}) to controller {url}")
            try:
                # Call add_fob
                res_code = data_manager.add_fob(fob_id, owner_name)
                changes_made += 1
                actual_fob_changes = True
                # Log to DB audit logs
                with db_mgr._get_connection() as conn:
                    with conn.cursor() as cur:
                        db_mgr.log_audit_action(
                            cur, 'system', 'Sync Add Fob',
                            f"Added Fob {fob_id} (Owner {owner_name}) to controller {url}"
                        )
                    conn.commit()
            except Exception as e:
                log_error(f"Failed to add Fob {fob_id} to controller {url}: {e}")
                
    # 5. Re-fetch current fobs from controller if any changes were made
    if actual_fob_changes:
        try:
            fobs_on_controller = get_all_fobs_from_controller(url, username, password)
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
            log_error(f"Error re-fetching fobs from controller {url}: {e}")
            return False
            
    # 6. Check and Sync ACL permissions
    fobs_to_sync_acl = db_fobs_keys & controller_fobs_keys
    for fob_id in fobs_to_sync_acl:
        rec_id = controller_fobs[fob_id]
        log_info(f"Checking ACL rules for Fob {fob_id} (Record ID: {rec_id}) on controller {url}")
        try:
            # Fetch current permissions from controller
            current_perms_rows = extractor.get_permissions_record(rec_id)
            if current_perms_rows is None:
                log_error(f"Could not retrieve permissions for Fob {fob_id} (Record ID {rec_id})")
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
            expected_perms = get_expected_permissions(db_mgr, fob_id, cidr)
            
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
                    log_info(f"Change limit of {limit_changes} reached. Skipping ACL sync for Fob {fob_id} (Record ID: {rec_id}) on controller {url}.")
                    continue
                log_info(f"ACL mismatch detected for Fob {fob_id} (Record ID {rec_id}) on {url}. "
                         f"Current: {current_perms}, Expected: {expected_perms}. Syncing...")
                data_manager.set_permissions(target_perms, rec_id)
                changes_made += 1
                # Log to DB audit logs
                with db_mgr._get_connection() as conn:
                    with conn.cursor() as cur:
                        db_mgr.log_audit_action(
                            cur, 'system', 'Sync ACL Rules',
                            f"Updated ACL rules for Fob {fob_id} (Record ID {rec_id}) on controller {url} to {target_perms}"
                        )
                    conn.commit()
            else:
                log_info(f"ACL rules for Fob {fob_id} on {url} are up-to-date.")
                
        except Exception as e:
            log_error(f"Error syncing ACL rules for Fob {fob_id} on controller {url}: {e}")
            
    log_info(f"Finished synchronization for controller: {url}")
    return True


def derive_run_schedule(db_mgr, reference_time=None):
    """
    Derives the run-schedule for the next 24 hours based on when permissions change
    throughout the day using key_fobs.f_get_runtimes.
    """
    ref = reference_time or datetime.now()
    today = ref.date()
    tomorrow = today + timedelta(days=1)
    
    # Fetch runtimes for today and tomorrow
    today_times = db_mgr.get_runtimes_for_date(today)
    tomorrow_times = db_mgr.get_runtimes_for_date(tomorrow)
    
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
        
    db_mgr = FobDatabaseManager(connect_string)
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

    if args.daemon:
        log_info("Running in daemon/scheduler mode.")
        
        # Initial startup synchronization to ensure consistency
        log_info("Executing initial startup synchronization...")
        for url in urls:
            synchronize_controller(url, username, password, db_mgr, limit_changes=limit_changes)
            
        last_sync_time = datetime.now()
        log_info(f"Initial synchronization complete. Daemon scheduler started. last_sync_time={last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while True:
            try:
                now = datetime.now()
                # Handle time backward adjustments or resets
                if now < last_sync_time:
                    last_sync_time = now
                    
                # Cap the lookback window to 24 hours to keep schedule calculation bounded
                if now - last_sync_time > timedelta(hours=24):
                    log_info("last_sync_time is older than 24 hours. Resetting check window to the last 24 hours.")
                    last_sync_time = now - timedelta(hours=24)
                    
                # Derive schedule from the last sync time
                schedule = derive_run_schedule(db_mgr, reference_time=last_sync_time)
                
                # Check for any events that have occurred up to 'now'
                pending_events = [dt for dt in schedule if dt <= now]
                
                if pending_events:
                    log_info(f"Triggering synchronization for scheduled times: {[dt.strftime('%H:%M:%S') for dt in pending_events]}")
                    for url in urls:
                        synchronize_controller(url, username, password, db_mgr, limit_changes=limit_changes)
                    last_sync_time = now
                    
            except Exception as e:
                log_error(f"Error in scheduler daemon loop: {e}", exc_info=True)
                
            time.sleep(30)
    else:
        # Run-once mode
        try:
            schedule = derive_run_schedule(db_mgr)
            log_info("Derived synchronization run-schedule for the next 24 hours:")
            if schedule:
                for dt in schedule:
                    log_info(f" - Sync scheduled at: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                log_info(" - No permission changes detected in the next 24 hours.")
        except Exception as e:
            log_error(f"Failed to derive synchronization run-schedule: {e}")
        
        for url in urls:
            synchronize_controller(url, username, password, db_mgr, limit_changes=limit_changes)
            
        log_info("Global door controller synchronization routine completed.")


if __name__ == '__main__':
    main()
