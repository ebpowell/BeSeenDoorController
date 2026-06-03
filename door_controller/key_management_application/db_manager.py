import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash
from door_controller.common_lib.utils import load_config, log_info

.ownerclass FobDatabaseManager:
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
        query = "SELECT password_hash, role FROM key_fobs.users WHERE username = %s;"
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

    def list_role_properties(self):
        """
        List all role properties mappings.
        """
        log_info("Database: Fetching role properties mappings.")
        query = """
            SELECT rp.role, rp.property_id, p.address
            FROM key_fobs.role_properties rp
            JOIN key_fobs.properties p ON rp.property_id = p.property_id
            ORDER BY rp.role ASC, p.address ASC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def assign_property_to_role(self, role, property_id, username='system'):
        """
        Assign access to a property address for a specific role.
        """
        log_info(f"Database: Assigning property {property_id} to role '{role}' by user '{username}'")
        query = """
            INSERT INTO key_fobs.role_properties (role, property_id)
            VALUES (%s, %s)
            ON CONFLICT (role, property_id) DO NOTHING;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (role, property_id))
                rowcount = cur.rowcount
                if rowcount > 0:
                    cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                    row = cur.fetchone()
                    address = row[0] if row else str(property_id)
                    self.log_audit_action(cur, username, "Assign Role Access", f"Assigned access to '{address}' for role '{role}'")
            conn.commit()
        return True

    def unassign_property_from_role(self, role, property_id, username='system'):
        """
        Unassign access to a property address from a specific role.
        """
        log_info(f"Database: Unassigning property {property_id} from role '{role}' by user '{username}'")
        query = """
            DELETE FROM key_fobs.role_properties
            WHERE role = %s AND property_id = %s;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                row = cur.fetchone()
                address = row[0] if row else str(property_id)
                
                cur.execute(query, (role, property_id))
                rowcount = cur.rowcount
                if rowcount > 0:
                    self.log_audit_action(cur, username, "Revoke Role Access", f"Revoked access to '{address}' for role '{role}'")
            conn.commit()
        return rowcount > 0

    def list_fobs(self, role=None):
        """
        List all key fobs, optionally filtered if the user's role is not admin.
        """
        log_info(f"Database: Fetching all fobs. Filter role={role}")
        if role and role != 'admin':
            query = """
                SELECT f.fob_id, p.property_id, p.address, CONCAT(o.first_name, ' ', o.last_name) AS owner_name, f.created_at, f.updated_at
                FROM key_fobs.keyfobs f
                JOIN key_fobs.properties p ON f.property_id = p.property_id
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE p.property_id IN (SELECT property_id FROM key_fobs.role_properties WHERE role = %s)
                ORDER BY f.fob_id ASC;
            """
            params = (role,)
        else:
            query = """
                SELECT f.fob_id, p.property_id, p.address, CONCAT(o.first_name, ' ', o.last_name) AS owner_name, f.created_at, f.updated_at
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

    def list_properties(self, role=None):
        """
        List all properties (fact table) and their current owners, optionally filtered by role.
        """
        log_info(f"Database: Fetching all properties. Filter role={role}")
        if role and role != 'admin':
            query = """
                SELECT p.property_id, p.address, CONCAT(o.first_name, ' ', o.last_name) AS owner_name
                FROM key_fobs.properties p
                LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
                WHERE p.property_id IN (SELECT property_id FROM key_fobs.role_properties WHERE role = %s)
                ORDER BY p.address ASC;
            """
            params = (role,)
        else:
            query = """
                SELECT p.property_id, p.address, CONCAT(o.first_name, ' ', o.last_name) AS owner_name
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
        query = """
            INSERT INTO key_fobs.owners (property_id, first_name, last_name, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (property_id) DO UPDATE
            SET owner_name = EXCLUDED.owner_name, updated_at = EXCLUDED.updated_at;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (property_id, owner_name))
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
