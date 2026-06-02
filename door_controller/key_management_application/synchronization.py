import time
import os
import re
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
        SELECT o.owner_name
        FROM key_fobs.fobs f
        JOIN key_fobs.properties p ON f.property_id = p.property_id
        LEFT JOIN key_fobs.property_owners o ON p.property_id = o.property_id
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


def synchronize_controller(url, username, password, db_mgr):
    """
    Executes synchronization for a single controller.
    """
    log_info(f"Starting synchronization for controller: {url}")
    
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
    if fobs_to_expunge:
        log_info(f"Expunging {len(fobs_to_expunge)} fobs from controller {url}")
        for fob_id in fobs_to_expunge:
            rec_id = controller_fobs[fob_id]
            log_info(f"Deleting Fob {fob_id} (Record ID: {rec_id}) from controller {url}")
            try:
                # Call del_fob
                res_code = data_manager.del_fob(login_data, rec_id)
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
            log_info(f"Adding Fob {fob_id} (Owner: {owner_name}) to controller {url}")
            try:
                # Call add_fob
                res_code = data_manager.add_fob(fob_id, owner_name)
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
    if fobs_to_expunge or fobs_to_add:
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
                log_info(f"ACL mismatch detected for Fob {fob_id} (Record ID {rec_id}) on {url}. "
                         f"Current: {current_perms}, Expected: {expected_perms}. Syncing...")
                data_manager.set_permissions(target_perms, rec_id)
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


def main():
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
        
    for url in urls:
        synchronize_controller(url, username, password, db_mgr)
        
    log_info("Global door controller synchronization routine completed.")


if __name__ == '__main__':
    main()
