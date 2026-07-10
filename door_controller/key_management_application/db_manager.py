import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash
from door_controller.common_lib.utils import load_config, log_info

class FobDatabaseManager:
    def __init__(self, conn_str=None):
        if conn_str:
            self.conn_str = conn_str
        else:
            config = load_config()
            self.conn_str = config.get('settings', {}).get('postgres_connect_string')
            if not self.conn_str:
                raise ValueError("postgres_connect_string not found in config.")

    def _get_connection(self):
        return psycopg2.connect(self.conn_str)

    def authenticate_user(self, username, password):
        """
        Authenticate a user using werkzeug password hash check.
        Returns a dict with username and role, or None if authentication fails.
        """
        log_info(f"Database: Authenticating user '{username}'")
        query = "SELECT password_hash, role FROM webgui.users WHERE username = %s;"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (username,))
                user = cur.fetchone()
                if user and check_password_hash(user['password_hash'], password):
                    return {'username': username, 'role': user['role']}
        return None

    def log_audit_action(self, cur, username, action, details=None):
        """
        Helper method to log an action to key_fobs.audit_logs.
        Accepts an active cursor to run within the calling transaction.
        """
        log_info(f"Audit Log: user={username}, action={action}, details={details}")
        query = """
            INSERT INTO key_fobs.audit_logs (username, action, details)
            VALUES (%s, %s, %s);
        """
        cur.execute(query, (username, action, details))

    def list_audit_logs(self):
        """
        List all user actions audit logs.
        """
        log_info("Database: Fetching audit logs.")
        query = """
            SELECT log_id, username, action, details, created_at
            FROM key_fobs.audit_logs
            ORDER BY created_at DESC
            LIMIT 100;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def list_group_properties(self, group_id=None):
        """
        List properties associated with groups.
        Optionally filter by specific group_id.
        Returns group_id, group_name, property_id, property address, and owner name.
        """
        log_info(f"Database: Fetching group-property mappings. Filter group_id={group_id}")
        
        if group_id:
            query = """
                SELECT 
                    g.group_id, g.name AS group_name, 
                    p.property_id, p.address,
                    concat(o.first_name, ' ', o.last_name) AS owner_name
                FROM key_fobs.groups g
                JOIN key_fobs.property_group_permissions pgp ON g.group_id = pgp.group_id
                JOIN key_fobs.properties p ON pgp.property_id = p.property_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE g.group_id = %s
                ORDER BY p.address ASC;
            """
            params = (group_id,)
        else:
            query = """
                SELECT 
                    g.group_id, g.name AS group_name, 
                    p.property_id, p.address,
                    concat(o.first_name, ' ', o.last_name) AS owner_name
                FROM key_fobs.groups g
                JOIN key_fobs.property_group_permissions pgp ON g.group_id = pgp.group_id
                JOIN key_fobs.properties p ON pgp.property_id = p.property_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                ORDER BY g.name ASC, p.address ASC;
            """
            params = ()
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def assign_property_to_group(self, group_id, property_id, username='system'):
        """
        Assign a property to a group by creating an entry in property_group_permissions.
        Returns True if successful, raises ValueError if group or property doesn't exist.
        """
        log_info(f"Database: Assigning property {property_id} to group {group_id} by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Verify group exists
                cur.execute("SELECT name FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                group_row = cur.fetchone()
                if not group_row:
                    raise ValueError(f"Group ID {group_id} not found.")
                group_name = group_row[0]
                
                # Verify property exists
                cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                prop_row = cur.fetchone()
                if not prop_row:
                    raise ValueError(f"Property ID {property_id} not found.")
                address = prop_row[0]
                
                # Insert property-group mapping
                try:
                    cur.execute(
                        "INSERT INTO key_fobs.property_group_permissions (property_id, group_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                        (property_id, group_id)
                    )
                    rowcount = cur.rowcount
                    if rowcount > 0:
                        self.log_audit_action(cur, username, "Assign Property to Group", 
                                            f"Assigned property '{address}' to group '{group_name}'")
                    conn.commit()
                    return rowcount > 0
                except Exception as e:
                    conn.rollback()
                    log_info(f"Database: Error assigning property to group: {e}")
                    raise

    def unassign_property_from_group(self, group_id, property_id, username='system'):
        """
        Unassign a property from a group by removing the entry in property_group_permissions.
        Returns True if removed, False if not found.
        """
        log_info(f"Database: Unassigning property {property_id} from group {group_id} by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get property and group info for audit log
                cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                prop_row = cur.fetchone()
                address = prop_row[0] if prop_row else str(property_id)
                
                cur.execute("SELECT name FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                group_row = cur.fetchone()
                group_name = group_row[0] if group_row else str(group_id)
                
                # Delete the property-group mapping
                cur.execute(
                    "DELETE FROM key_fobs.property_group_permissions WHERE group_id = %s AND property_id = %s;",
                    (group_id, property_id)
                )
                rowcount = cur.rowcount
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Revoke Property from Group", 
                                        f"Revoked property '{address}' from group '{group_name}'")
                conn.commit()
        return rowcount > 0

    def list_fobs(self, group_id=None):
        """
        List all key fobs, optionally filtered by group membership.
        If group_id is provided, returns only fobs from properties assigned to that group.
        """
        log_info(f"Database: Fetching all fobs. Filter group_id={group_id}")
        
        if group_id:
            query = """
                SELECT DISTINCT 
                    f.fob_id, p.property_id, p.address, 
                    CONCAT(o.first_name, ' ', o.last_name) AS owner_name, 
                    f.created_at, f.updated_at,
                    g.group_id, g.name AS group_name
                FROM key_fobs.keyfobs f
                JOIN key_fobs.properties p ON f.property_id = p.property_id
                JOIN key_fobs.property_group_permissions pgp ON p.property_id = pgp.property_id
                JOIN key_fobs.groups g ON pgp.group_id = g.group_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE g.group_id = %s
                ORDER BY f.fob_id ASC;
            """
            params = (group_id,)
        else:
            query = """
                SELECT 
                    f.fob_id, p.property_id, p.address, 
                    CONCAT(o.first_name, ' ', o.last_name) AS owner_name, 
                    f.created_at, f.updated_at
                FROM key_fobs.keyfobs f
                JOIN key_fobs.properties p ON f.property_id = p.property_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                ORDER BY f.fob_id ASC;
            """
            params = ()
            
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def list_properties(self, group_id=None):
        """
        List all properties and their current owners, optionally filtered by group membership.
        If group_id is provided, returns only properties assigned to that group.
        """
        log_info(f"Database: Fetching all properties. Filter group_id={group_id}")
        
        if group_id:
            query = """
                SELECT DISTINCT 
                    p.property_id, p.address, p.knox_co_lot_id,
                    CONCAT(o.first_name, ' ', o.last_name) AS owner_name,
                    g.group_id, g.name AS group_name
                FROM key_fobs.properties p
                JOIN key_fobs.property_group_permissions pgp ON p.property_id = pgp.property_id
                JOIN key_fobs.groups g ON pgp.group_id = g.group_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE g.group_id = %s
                ORDER BY p.address ASC;
            """
            params = (group_id,)
        else:
            query = """
                SELECT 
                    p.property_id, p.address, p.knox_co_lot_id,
                    CONCAT(o.first_name, ' ', o.last_name) AS owner_name
                FROM key_fobs.properties p
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                ORDER BY p.address ASC;
            """
            params = ()
            
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def list_replacement_logs(self):
        """
        List replacement log metadata containing old and new fob IDs with addresses and timestamps.
        """
        log_info("Database: Fetching replacement logs.")
        query = """
            SELECT r.replacement_id, p.address, r.replaced_fob_id, r.new_fob_id, r.replaced_at
            FROM key_fobs.fob_replacements r
            JOIN key_fobs.properties p ON r.property_id = p.property_id
            ORDER BY r.replaced_at DESC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def add_fob(self, fob_id, property_id, replaced_fob_id=None, username='system'):
        """
        Add a new fob assigned to a property. Optionally replaces an old fob and logs the transaction.
        Raises ValueError if fob_id already exists.
        """
        log_info(f"Database: Adding fob_id={fob_id} assigned to property_id={property_id} (replacing={replaced_fob_id}) by user={username}")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Verify new fob doesn't exist
                cur.execute("SELECT 1 FROM key_fobs.keyfobs WHERE fob_id = %s;", (fob_id,))
                if cur.fetchone():
                    raise ValueError(f"Fob ID {fob_id} already exists.")
                
                # 2. If replacement is requested, delete old fob and log replacement
                if replaced_fob_id is not None:
                    cur.execute("DELETE FROM key_fobs.keyfobs WHERE fob_id = %s;", (replaced_fob_id,))
                    cur.execute(
                        """
                        INSERT INTO key_fobs.fob_replacements (property_id, replaced_fob_id, new_fob_id)
                        VALUES (%s, %s, %s);
                        """,
                        (property_id, replaced_fob_id, fob_id)
                    )
                    action = "Replace Fob"
                    details = f"Fob {new_fob_id} assigned to property {property_id}, replacing old Fob {replaced_fob_id}"
                else:
                    action = "Assign Fob"
                    details = f"Fob {fob_id} assigned to property {property_id}"
                
                # 3. Insert new fob
                cur.execute(
                    """
                    INSERT INTO key_fobs.keyfobs (fob_id, property_id)
                    VALUES (%s, %s);
                    """,
                    (fob_id, property_id)
                )
                
                # 4. Log to audit trails
                self.log_audit_action(cur, username, action, details)
                
            conn.commit()
        log_info(f"Database: Fob {fob_id} assigned to property {property_id} successfully.")

    def remove_fob(self, fob_id, username='system'):
        """
        Remove an existing fob. Returns True if removed, False if not found.
        """
        log_info(f"Database: Attempting to remove fob_id={fob_id} by user={username}")
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM key_fobs.keyfobs WHERE fob_id = %s;", (fob_id,))
                rowcount = cur.rowcount
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Remove Fob", f"Removed Fob {fob_id}")
            conn.commit()
        success = rowcount > 0
        if success:
            log_info(f"Database: Fob {fob_id} removed successfully.")
        else:
            log_info(f"Database: Fob {fob_id} not found for removal.")
        return success

    def update_property_owner(self, property_id, owner_name, username='system'):
        """
        Update (upsert) the owner of a property. All fobs under this property
        will inherit the new owner. Returns True on success.
        """
        log_info(f"Database: Updating owner of property_id={property_id} to '{owner_name}' by user={username}")
        # query = """
        #     INSERT INTO key_fobs.owners (property_id, first_name, last_name, updated_at)
        #     VALUES (%s, %s, CURRENT_TIMESTAMP)
        #     ON CONFLICT (property_id) DO UPDATE
        #     SET owner_name = EXCLUDED.owner_name, updated_at = EXCLUDED.updated_at;
        # """
        last_name, first_name = (owner_name.split(' ', 1) + [""])[:2]  # Simple split for first and last name
        query = "UPDATE key_fobs.owners SET last_name = %s, first_name = %s, updated_at = CURRENT_TIMESTAMP WHERE property_id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (last_name, first_name, property_id))
                rowcount = cur.rowcount
                
                # Trigger an update on the fobs' updated_at so that tracking triggers are aware of the trickle-down
                fob_update_query = """
                    UPDATE key_fobs.keyfobs
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE property_id = %s;
                """
                cur.execute(fob_update_query, (property_id,))
                
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Update Property Owner", f"Updated property {property_id} owner to '{owner_name}'")
            conn.commit()
            
        success = rowcount > 0
        log_info(f"Database: Property {property_id} owner updated successfully.")
        return success

    def list_groups(self):
        """
        List all groups with their basic information.
        Returns group_id and name for each group.
        """
        log_info("Database: Fetching all groups.")
        query = "SELECT group_id, name FROM key_fobs.groups ORDER BY name ASC;"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def get_group_id_by_name(self, name):
        """
        Get the group_id for a given group name.
        """
        log_info(f"Database: Finding group_id for name '{name}'")
        query = "SELECT group_id FROM key_fobs.groups WHERE name = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (name,))
                row = cur.fetchone()
                return row[0] if row else None

    def get_group_permissions(self, group_id):
        """
        Get all door permissions for a specific group, including time windows and access status.
        Returns detailed permission records.
        """
        log_info(f"Database: Fetching permissions for group {group_id}.")
        query = """
            SELECT 
                g.group_id, g.name AS group_name,
                gp.perm_id, gp.door_id, gp.allow,
                gp.start_date, gp.end_date,
                gp.start_time, gp.end_time
            FROM key_fobs.groups g
            JOIN key_fobs.group_permissions gp ON g.group_id = gp.group_id
            WHERE g.group_id = %s
            ORDER BY gp.door_id ASC, gp.start_date ASC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (group_id,))
                return cur.fetchall()

    def assign_door_permission_to_group(self, group_id, door_id, allow=True,
                                       start_date=None, end_date=None,
                                       start_time=None, end_time=None, username='system'):
        """
        Assign a door permission to a group with optional time windows.
        Returns perm_id if successful, raises ValueError if group doesn't exist.
        
        Args:
            group_id: The group to grant permission to
            door_id: The door to grant access to
            allow: Boolean indicating if access is allowed (True) or denied (False)
            start_date: Start date for the permission window (optional, YYYY-MM-DD format)
            end_date: End date for the permission window (optional, YYYY-MM-DD format)
            start_time: Start time of day for permission (optional, HH:MM:SS format)
            end_time: End time of day for permission (optional, HH:MM:SS format)
            username: User making the change for audit logging
        """
        log_info(f"Database: Assigning door {door_id} permission to group {group_id} by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Verify group exists
                cur.execute("SELECT name FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                group_row = cur.fetchone()
                if not group_row:
                    raise ValueError(f"Group ID {group_id} not found.")
                group_name = group_row[0]
                
                # Insert group permission
                try:
                    cur.execute(
                        "INSERT INTO key_fobs.group_permissions (start_date, end_date, start_time, end_time, door_id, allow, group_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING perm_id;",
                        (start_date, end_date, start_time, end_time, door_id, allow, group_id)
                    )
                    perm_id = cur.fetchone()[0]
                    
                    access_type = "allowed" if allow else "denied"
                    time_window = f"from {start_date} to {end_date}" if start_date and end_date else "all times"
                    details = f"Group '{group_name}' permission to door {door_id} ({access_type}) {time_window}"
                    self.log_audit_action(cur, username, "Assign Door Permission to Group", details)
                    
                    conn.commit()
                    return perm_id
                except Exception as e:
                    conn.rollback()
                    log_info(f"Database: Error assigning door permission to group: {e}")
                    raise

    def remove_group_permission(self, perm_id, username='system'):
        """
        Remove a specific group permission by permission ID.
        Returns True if removed, False if not found.
        """
        log_info(f"Database: Removing group permission {perm_id} by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get permission details for audit log
                cur.execute(
                    "SELECT g.name, gp.door_id, gp.allow FROM key_fobs.group_permissions gp JOIN key_fobs.groups g ON gp.group_id = g.group_id WHERE gp.perm_id = %s;",
                    (perm_id,)
                )
                perm_row = cur.fetchone()
                if perm_row:
                    group_name, door_id, allow = perm_row
                    access_type = "allowed" if allow else "denied"
                    details = f"Removed permission {perm_id}: Group '{group_name}' door {door_id} ({access_type})"
                else:
                    details = f"Attempted to remove non-existent permission {perm_id}"
                
                cur.execute("DELETE FROM key_fobs.group_permissions WHERE perm_id = %s;", (perm_id,))
                rowcount = cur.rowcount
                
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Remove Group Permission", details)
                
                conn.commit()
        
        return rowcount > 0

    def create_group(self, name, username='system'):
        """
        Create a new group with the given name.
        Returns group_id if successful, raises ValueError if group name already exists.
        """
        log_info(f"Database: Creating new group '{name}' by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "INSERT INTO key_fobs.groups (name) VALUES (%s) RETURNING group_id;",
                        (name,)
                    )
                    group_id = cur.fetchone()[0]
                    self.log_audit_action(cur, username, "Create Group", f"Created group '{name}' (ID: {group_id})")
                    conn.commit()
                    return group_id
                except psycopg2.IntegrityError:
                    conn.rollback()
                    raise ValueError(f"Group name '{name}' already exists.")
                except Exception as e:
                    conn.rollback()
                    log_info(f"Database: Error creating group: {e}")
                    raise

    def delete_group(self, group_id, username='system'):
        """
        Delete a group and all its associated permissions and property mappings.
        Returns True if deleted, False if group not found.
        Raises Exception if deletion fails due to constraints.
        """
        log_info(f"Database: Deleting group {group_id} by user '{username}'")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get group info for audit log
                cur.execute("SELECT name FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                group_row = cur.fetchone()
                if not group_row:
                    return False
                
                group_name = group_row[0]
                try:
                    # Cascading delete: remove permissions first, then property mappings, then group
                    cur.execute("DELETE FROM key_fobs.group_permissions WHERE group_id = %s;", (group_id,))
                    perm_count = cur.rowcount
                    
                    cur.execute("DELETE FROM key_fobs.property_group_permissions WHERE group_id = %s;", (group_id,))
                    prop_count = cur.rowcount
                    
                    cur.execute("DELETE FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                    group_count = cur.rowcount
                    
                    if group_count > 0:
                        details = f"Deleted group '{group_name}' with {perm_count} permissions and {prop_count} property mappings"
                        self.log_audit_action(cur, username, "Delete Group", details)
                    
                    conn.commit()
                    return group_count > 0
                except Exception as e:
                    conn.rollback()
                    log_info(f"Database: Error deleting group: {e}")
                    raise

    def list_reservations(self):
        """
        List all clubhouse reservations, joined with properties and owners.
        Sorted by reservation_date ASC, from_time ASC.
        """
        log_info("Database: Fetching all clubhouse reservations.")
        query = """
            SELECT 
                r.reservation_id, r.property_id, r.reservation_date, 
                r.from_time, r.to_time, r.payment_made, r.deposit_on_file, r.agreement_received, r.created_at,
                p.address,
                CONCAT(o.first_name, ' ', o.last_name) AS owner_name
            FROM key_fobs.clubhouse_reservations r
            JOIN key_fobs.properties p ON r.property_id = p.property_id
            LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
            ORDER BY r.reservation_date ASC, r.from_time ASC NULLS FIRST;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def add_reservation(self, property_id, reservation_date, from_time=None, to_time=None, 
                        payment_made=False, deposit_on_file=False, agreement_received=False, username='system'):
        """
        Add a new clubhouse reservation and logs to the user audit logs.
        """
        log_info(f"Database: Adding reservation for property_id={property_id} on {reservation_date}")
        query = """
            INSERT INTO key_fobs.clubhouse_reservations 
                (property_id, reservation_date, from_time, to_time, payment_made, deposit_on_file, agreement_received)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING reservation_id;
        """
        # Convert empty strings to None for optional time fields
        from_time_val = from_time if from_time else None
        to_time_val = to_time if to_time else None
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                prop_row = cur.fetchone()
                address = prop_row[0] if prop_row else f"ID {property_id}"
                
                cur.execute(query, (property_id, reservation_date, from_time_val, to_time_val, payment_made, deposit_on_file, agreement_received))
                reservation_id = cur.fetchone()[0]
                
                time_str = f" from {from_time_val} to {to_time_val}" if from_time_val else ""
                details = f"Reserved clubhouse for '{address}' on {reservation_date}{time_str} (Payment: {payment_made}, Deposit: {deposit_on_file}, Agreement: {agreement_received})"
                self.log_audit_action(cur, username, "Add Clubhouse Reservation", details)
            conn.commit()
        return reservation_id

    def delete_reservation(self, reservation_id, username='system'):
        """
        Delete a clubhouse reservation and logs to the user audit logs.
        """
        log_info(f"Database: Deleting reservation_id={reservation_id} by user={username}")
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get reservation details for audit logging
                cur.execute("""
                    SELECT r.reservation_date, p.address 
                    FROM key_fobs.clubhouse_reservations r
                    JOIN key_fobs.properties p ON r.property_id = p.property_id
                    WHERE r.reservation_id = %s;
                """, (reservation_id,))
                row = cur.fetchone()
                if row:
                    res_date, address = row
                    details = f"Deleted clubhouse reservation for '{address}' on {res_date}"
                else:
                    details = f"Deleted non-existent reservation {reservation_id}"
                
                cur.execute("DELETE FROM key_fobs.clubhouse_reservations WHERE reservation_id = %s;", (reservation_id,))
                rowcount = cur.rowcount
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Delete Clubhouse Reservation", details)
            conn.commit()
        return rowcount > 0

    def update_reservation_status(self, reservation_id, field, value, username='system'):
        """
        Update a status boolean field (payment_made, deposit_on_file, or agreement_received) for a clubhouse reservation.
        """
        if field not in ['payment_made', 'deposit_on_file', 'agreement_received']:
            raise ValueError(f"Invalid field: {field}")
            
        log_info(f"Database: Updating reservation_id={reservation_id} field {field} to {value} by user={username}")
        
        query = f"""
            UPDATE key_fobs.clubhouse_reservations
            SET {field} = %s
            WHERE reservation_id = %s;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.reservation_date, p.address 
                    FROM key_fobs.clubhouse_reservations r
                    JOIN key_fobs.properties p ON r.property_id = p.property_id
                    WHERE r.reservation_id = %s;
                """, (reservation_id,))
                row = cur.fetchone()
                if row:
                    res_date, address = row
                    details = f"Updated clubhouse reservation for '{address}' on {res_date}: set {field} = {value}"
                else:
                    details = f"Updated reservation {reservation_id}: set {field} = {value}"
                
                cur.execute(query, (value, reservation_id))
                rowcount = cur.rowcount
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Update Clubhouse Reservation", details)
            conn.commit()
        return rowcount > 0

    def search_properties(self, search_query):
        """
        Search properties and owners where the address or owner name matches the search_query.
        Returns property_id, address, and owner name.
        """
        log_info(f"Database: Searching properties with query '{search_query}'")
        query = """
            SELECT 
                p.property_id, p.address,
                CONCAT(o.first_name, ' ', o.last_name) AS owner_name
            FROM key_fobs.properties p
            LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
            WHERE p.address ILIKE %s 
               OR o.first_name ILIKE %s 
               OR o.last_name ILIKE %s 
               OR CONCAT(o.first_name, ' ', o.last_name) ILIKE %s
            ORDER BY p.address ASC
            LIMIT 10;
        """
        like_query = f"%{search_query}%"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (like_query, like_query, like_query, like_query))
                return cur.fetchall()

    def get_runtimes_for_date(self, target_date, controller_ip=None):
        """
        Retrieves unique permission change runtimes for a given date.
        """
        if isinstance(target_date, datetime.datetime):
            target_date = target_date.date()
        log_info(f"Database: Fetching permission change runtimes for {target_date} (controller_ip: {controller_ip})")
        if controller_ip:
            query = "SELECT DISTINCT run_times FROM key_fobs.f_get_runtimes(%s::date, %s::cidr) ORDER BY run_times ASC;"
            params = (target_date, controller_ip)
        else:
            query = "SELECT DISTINCT run_times FROM key_fobs.f_get_runtimes(%s::date) ORDER BY run_times ASC;"
            params = (target_date,)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                # results = cur.fetchall()
                return [row[0] for row in cur.fetchall()]
            
    def get_owner_for_fobid(self, fob_id):
        """
        Retrieves the owner for a given FobID
        """
        query = 'SELECT concat(o.first_name, \' \', o.last_name) from key_fobs.owners o ' \
                'join key_fobs.properties p on o.property_id = p.property_id ' \
                'join key_fobs.keyfobs kf on p.property_id = kf.property_id ' \
                'where kf.fob_id = %s;'
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (fob_id,))
                row = cur.fetchone()
                return row[0] if row else None
