import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash
from door_controller.common_lib.utils import load_config, log_info, extract_cidr

class FobDatabaseManager:
    def __init__(self, conn_str=None):
        if conn_str:
            self.conn_str = conn_str
        else:
            config = load_config()
            self.conn_str = config.get('settings', {}).get('postgres_connect_string')
            if not self.conn_str:
                raise ValueError("postgres_connect_string not found in config.")

    _functions_ensured = False

    def ensure_db_functions(self):
        if FobDatabaseManager._functions_ensured:
            return
        try:
            conn = self._get_connection()
            if hasattr(conn, '_mock_name') or type(conn).__name__ in ('MagicMock', 'Mock'):
                return
            with conn:
                with conn.cursor() as cur:
                    # 0. Ensure fee and early_setup columns exist in key_fobs.clubhouse_reservations
                    cur.execute("""
                        ALTER TABLE key_fobs.clubhouse_reservations 
                        ADD COLUMN IF NOT EXISTS fee DECIMAL(10,2) DEFAULT 15.00,
                        ADD COLUMN IF NOT EXISTS early_setup BOOLEAN DEFAULT FALSE;
                    """)

                    # 0b. Ensure key_fobs.reservation_blocks table exists and is seeded
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS key_fobs.reservation_blocks (
                            block_id SERIAL PRIMARY KEY,
                            block_key VARCHAR(50) UNIQUE NOT NULL,
                            block_name VARCHAR(100) NOT NULL,
                            start_time TIME NOT NULL,
                            end_time TIME NOT NULL,
                            display_order INT DEFAULT 1,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );

                        INSERT INTO key_fobs.reservation_blocks (block_key, block_name, start_time, end_time, display_order) VALUES
                        ('block1', 'Block 1: Morning', '08:00:00', '12:00:00', 1),
                        ('block2', 'Block 2: Afternoon', '13:00:00', '17:00:00', 2),
                        ('block3', 'Block 3: Evening', '18:00:00', '23:00:00', 3)
                        ON CONFLICT (block_key) DO NOTHING;
                    """)

                    # 0c. Ensure key_fobs.reservation_fee_config table exists and is seeded
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS key_fobs.reservation_fee_config (
                            config_key VARCHAR(50) PRIMARY KEY,
                            fee_amount DECIMAL(10,2) NOT NULL,
                            description TEXT,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );

                        INSERT INTO key_fobs.reservation_fee_config (config_key, fee_amount, description) VALUES
                        ('single_block_fee', 15.00, 'Fee for reserving a single time block'),
                        ('multi_block_fee', 30.00, 'Flat rate fee for reserving 2 or 3 time blocks')
                        ON CONFLICT (config_key) DO NOTHING;
                    """)

                    # 1. Backfill NULL month/day columns in group_permissions from start_date/end_date if columns exist
                    cur.execute(
                        """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'key_fobs' AND table_name = 'group_permissions';
                        """
                    )
                    gp_cols = {row[0] for row in cur.fetchall()}
                    if 'start_month' in gp_cols and 'start_day_of_month' in gp_cols:
                        cur.execute("""
                            UPDATE key_fobs.group_permissions
                            SET 
                                start_month = COALESCE(start_month, EXTRACT(MONTH FROM start_date)::int),
                                start_day_of_month = COALESCE(start_day_of_month, EXTRACT(DAY FROM start_date)::int),
                                end_month = COALESCE(end_month, EXTRACT(MONTH FROM end_date)::int),
                                end_day_of_month = COALESCE(end_day_of_month, EXTRACT(DAY FROM end_date)::int)
                            WHERE (start_month IS NULL OR start_day_of_month IS NULL OR end_month IS NULL OR end_day_of_month IS NULL)
                              AND start_date IS NOT NULL;
                        """)

                    # 2. Check if key_fobs.vint_acl_data is a VIEW and recreate with null-safe expressions
                    cur.execute(
                        """
                        SELECT table_type 
                        FROM information_schema.tables 
                        WHERE table_schema = 'key_fobs' AND table_name = 'vint_acl_data';
                        """
                    )
                    v_row = cur.fetchone()
                    if v_row and v_row[0] == 'VIEW':
                        cur.execute("""
                            CREATE OR REPLACE VIEW key_fobs.vint_acl_data AS
                            SELECT 
                                k.fob_id,
                                gp.door_id,
                                d.door_no,
                                d.controller_ip,
                                gp.allow,
                                gp.start_time,
                                gp.end_time,
                                COALESCE(
                                    CASE 
                                        WHEN gp.start_day_of_month IS NOT NULL AND gp.start_month IS NOT NULL 
                                        THEN to_date(concat(gp.start_day_of_month::text, '-', gp.start_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text)
                                        ELSE NULL
                                    END,
                                    gp.start_date,
                                    '2000-01-01'::date
                                ) AS start_date,
                                COALESCE(
                                    CASE 
                                        WHEN gp.end_day_of_month IS NOT NULL AND gp.end_month IS NOT NULL 
                                        THEN to_date(concat(gp.end_day_of_month::text, '-', gp.end_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text)
                                        ELSE NULL
                                    END,
                                    gp.end_date,
                                    '2099-12-31'::date
                                ) AS end_date
                            FROM key_fobs.group_permissions gp
                            JOIN key_fobs.groups g ON gp.group_id = g.group_id
                            JOIN key_fobs.property_group_permissions pgp ON g.group_id = pgp.group_id
                            JOIN key_fobs.properties p ON pgp.property_id = p.property_id
                            JOIN key_fobs.keyfobs k ON p.property_id = k.property_id
                            JOIN door_controller.door d ON gp.door_id = d.door_id;
                        """)

                    # 3. Create or replace f_get_permissions function
                    cur.execute("""
                        CREATE OR REPLACE FUNCTION key_fobs.f_get_permissions (
                            p_fob_id INT, 
                            p_controller_ip CIDR
                        )
                        RETURNS TABLE (
                            door_no INT,
                            allow INT
                        ) 
                        LANGUAGE plpgsql
                        AS $$
                        BEGIN
                            DROP TABLE IF EXISTS temp_doors;

                            CREATE TEMP TABLE temp_doors AS
                            SELECT d.door_no, 0 AS allow
                            FROM door_controller.door d
                            WHERE d.controller_ip = p_controller_ip;

                            WITH permissions AS (
                                SELECT k.fob_id, MAX(pgp.group_id) AS group_id 
                                FROM key_fobs.keyfobs k 
                                JOIN key_fobs.property_group_permissions pgp 
                                  ON k.property_id = pgp.property_id 
                                GROUP BY k.fob_id, k.property_id
                            ),
                            allow_times AS ( 
                                SELECT 
                                    p.fob_id,
                                    COALESCE(
                                        CASE 
                                            WHEN gp.start_day_of_month IS NOT NULL AND gp.start_month IS NOT NULL 
                                            THEN to_date(concat(gp.start_day_of_month::text, '-', gp.start_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text)
                                            ELSE NULL
                                        END,
                                        gp.start_date,
                                        '2000-01-01'::date
                                    ) AS start_date,
                                    COALESCE(
                                        CASE 
                                            WHEN gp.end_day_of_month IS NOT NULL AND gp.end_month IS NOT NULL 
                                            THEN to_date(concat(gp.end_day_of_month::text, '-', gp.end_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text)
                                            ELSE NULL
                                        END,
                                        gp.end_date,
                                        '2099-12-31'::date
                                    ) AS end_date,
                                    gp.start_time,
                                    gp.end_time,
                                    d.door_no,
                                    d.controller_ip
                                FROM permissions p
                                JOIN key_fobs.group_permissions gp 
                                  ON p.group_id = gp.group_id
                                JOIN door_controller.door d 
                                  ON gp.door_id = d.door_id
                                WHERE gp.allow = true
                            )
                            UPDATE temp_doors td
                            SET allow = 1
                            FROM allow_times atm
                            WHERE td.door_no = atm.door_no
                              AND atm.fob_id = p_fob_id
                              AND atm.controller_ip = p_controller_ip
                              AND (atm.start_time IS NULL OR CURRENT_TIME >= atm.start_time::time)
                              AND (atm.end_time IS NULL OR CURRENT_TIME <= atm.end_time::time)
                              AND CURRENT_DATE >= atm.start_date
                              AND CURRENT_DATE <= atm.end_date;   

                            RETURN QUERY
                            SELECT td.door_no, td.allow FROM temp_doors td;

                            DROP TABLE IF EXISTS temp_doors;
                        END;
                        $$;
                    """)
                    cur.execute("ALTER TABLE key_fobs.clubhouse_reservations ADD COLUMN IF NOT EXISTS event_type VARCHAR(50) DEFAULT 'Private Event';")
                conn.commit()
            FobDatabaseManager._functions_ensured = True
        except Exception as e:
            log_info(f"Database function auto-update notice: {e}")

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

    def search_properties(self, query):
        """
        Search properties by address or owner name.
        """
        log_info(f"Database: Searching properties with query '{query}'")
        search_pattern = f"%{query}%"
        sql = """
            SELECT DISTINCT
                p.property_id, p.address,
                CONCAT(o.first_name, ' ', o.last_name) AS owner_name
            FROM key_fobs.properties p
            LEFT JOIN key_fobs.owners o ON p.property_id = o.property_id
            WHERE p.address ILIKE %s OR CONCAT(o.first_name, ' ', o.last_name) ILIKE %s OR CAST(p.property_id AS TEXT) ILIKE %s
            ORDER BY p.address ASC
            LIMIT 50;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (search_pattern, search_pattern, search_pattern))
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
                    details = f"Fob {fob_id} assigned to property {property_id}, replacing old Fob {replaced_fob_id}"
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
                        """
                        INSERT INTO key_fobs.group_permissions 
                            (perm_id, start_date, end_date, start_time, end_time, door_id, allow, group_id)
                        VALUES (
                            (SELECT COALESCE(MAX(perm_id), 0) + 1 FROM key_fobs.group_permissions),
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        RETURNING perm_id;
                        """,
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

    def list_reservation_blocks(self):
        """
        Fetch all active reservation blocks ordered by display_order.
        """
        log_info("Database: Fetching active reservation blocks.")
        query = """
            SELECT block_id, block_key, block_name, start_time, end_time, display_order, is_active
            FROM key_fobs.reservation_blocks
            WHERE is_active = TRUE
            ORDER BY display_order ASC, start_time ASC;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            log_info(f"Database: Error listing reservation blocks: {e}")
            return [
                {'block_key': 'block1', 'block_name': 'Block 1: Morning', 'start_time': '08:00:00', 'end_time': '12:00:00', 'display_order': 1},
                {'block_key': 'block2', 'block_name': 'Block 2: Afternoon', 'start_time': '13:00:00', 'end_time': '17:00:00', 'display_order': 2},
                {'block_key': 'block3', 'block_name': 'Block 3: Evening', 'start_time': '18:00:00', 'end_time': '23:00:00', 'display_order': 3},
            ]

    def get_reservation_fee_config(self):
        """
        Fetch reservation fee configuration dictionary mapping config_key to float fee_amount.
        """
        log_info("Database: Fetching reservation fee configuration.")
        query = """
            SELECT config_key, fee_amount
            FROM key_fobs.reservation_fee_config;
        """
        defaults = {'single_block_fee': 15.00, 'multi_block_fee': 30.00, 'early_setup_fee': 15.00}
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
                    if rows:
                        for row in rows:
                            defaults[row['config_key']] = float(row['fee_amount'])
        except Exception as e:
            log_info(f"Database: Error fetching fee config: {e}")
        return defaults

    def has_reservations_in_previous_24h(self, target_date):
        """
        Checks if any clubhouse reservation exists on the calendar in the 24 hours prior to target_date.
        """
        if isinstance(target_date, str):
            target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        elif isinstance(target_date, datetime.datetime):
            target_date = target_date.date()

        prev_day = target_date - datetime.timedelta(days=1)
        query = """
            SELECT COUNT(*) FROM key_fobs.clubhouse_reservations
            WHERE reservation_date >= %s AND reservation_date <= %s;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (prev_day, prev_day))
                count = cur.fetchone()[0]
                return count > 0

    def list_reservations(self):
        """
        List all clubhouse reservations, joined with properties and owners.
        Sorted by reservation_date ASC, from_time ASC.
        """
        log_info("Database: Fetching all clubhouse reservations.")
        query = """
            SELECT 
                r.reservation_id, r.property_id, r.reservation_date, 
                r.from_time, r.to_time, r.payment_made, r.deposit_on_file, r.agreement_received,
                COALESCE(r.fee, 15.00) AS fee, COALESCE(r.early_setup, FALSE) AS early_setup,
                COALESCE(r.event_type, 'Private Event') AS event_type, r.created_at,
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
                        blocks=None, early_setup=False, fee=None,
                        payment_made=False, deposit_on_file=False, agreement_received=False,
                        event_type='Private Event', username='system'):
        """
        Add a new clubhouse reservation and logs to the user audit logs.
        Calculates pricing dynamically from fee configuration table or event type rules.
        Enforces 24-hour prior calendar availability rule if early_setup is requested.
        Enforces that Community Organization events cannot request early set-up.
        """
        log_info(f"Database: Adding reservation for property_id={property_id} on {reservation_date} (blocks={blocks}, event_type={event_type}, early_setup={early_setup})")
        
        if event_type == 'Community Organization' and early_setup:
            raise ValueError("Early set-up is not allowed for Community Organization events.")

        if isinstance(reservation_date, str):
            res_date_obj = datetime.datetime.strptime(reservation_date, "%Y-%m-%d").date()
        elif isinstance(reservation_date, datetime.datetime):
            res_date_obj = reservation_date.date()
        else:
            res_date_obj = reservation_date

        if early_setup:
            if self.has_reservations_in_previous_24h(res_date_obj):
                raise ValueError("Early set-up is not allowed because another reservation exists in the previous 24 hours.")

        active_blocks = self.list_reservation_blocks()
        block_map = {}
        for b in active_blocks:
            s_time = str(b['start_time']) if hasattr(b['start_time'], 'strftime') else str(b['start_time'])
            e_time = str(b['end_time']) if hasattr(b['end_time'], 'strftime') else str(b['end_time'])
            block_map[b['block_key']] = (s_time, e_time)

        block_tuples = []
        if blocks:
            for b in blocks:
                if b in block_map:
                    block_tuples.append(block_map[b])
        elif from_time or to_time:
            block_tuples.append((from_time, to_time))
        else:
            if active_blocks:
                b0 = active_blocks[0]
                s0 = str(b0['start_time']) if hasattr(b0['start_time'], 'strftime') else str(b0['start_time'])
                e0 = str(b0['end_time']) if hasattr(b0['end_time'], 'strftime') else str(b0['end_time'])
                block_tuples.append((s0, e0))
            else:
                block_tuples.append(('08:00:00', '23:00:00'))

        num_blocks = len(block_tuples)
        if fee is not None:
            calc_fee = float(fee)
        else:
            if event_type == 'Community Organization':
                calc_fee = 15.00 if num_blocks >= 2 else 7.50
            else:
                fee_config = self.get_reservation_fee_config()
                base_fee = fee_config.get('multi_block_fee', 30.00) if num_blocks > 1 else fee_config.get('single_block_fee', 15.00)
                setup_surcharge = fee_config.get('early_setup_fee', 15.00) if early_setup else 0.00
                calc_fee = base_fee + setup_surcharge

        fee_per_block = calc_fee / num_blocks if num_blocks > 0 else 15.00

        reservation_ids = []
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT address FROM key_fobs.properties WHERE property_id = %s;", (property_id,))
                prop_row = cur.fetchone()
                address = prop_row[0] if prop_row else f"ID {property_id}"

                query = """
                    INSERT INTO key_fobs.clubhouse_reservations 
                        (property_id, reservation_date, from_time, to_time, payment_made, deposit_on_file, agreement_received, fee, early_setup, event_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING reservation_id;
                """
                for f_t, t_t in block_tuples:
                    from_time_val = f_t if f_t else None
                    to_time_val = t_t if t_t else None
                    cur.execute(query, (property_id, reservation_date, from_time_val, to_time_val, payment_made, deposit_on_file, agreement_received, fee_per_block, early_setup, event_type))
                    res_id = cur.fetchone()[0]
                    reservation_ids.append(res_id)

                details = f"Reserved clubhouse for '{address}' on {reservation_date} ({num_blocks} block(s), Fee: ${calc_fee:.2f}, Type: {event_type}, Early Setup: {early_setup})"
                self.log_audit_action(cur, username, "Add Clubhouse Reservation", details)
            conn.commit()
        return reservation_ids[0] if reservation_ids else None

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

    def sync_clubhouse_reservation_permissions(self, now=None, username='system'):
        """
        Synchronizes property membership in Group ID 8 (Clubhouse Rental) based on active reservations.
        When payment_made, deposit_on_file, and agreement_received are all True, and the current time 'now'
        falls within [start_datetime, end_datetime], the property is granted Group ID 8 permissions in
        key_fobs.property_group_permissions. When expired or not eligible, Group ID 8 is revoked.
        """
        if now is None:
            now = datetime.datetime.now()
            
        log_info(f"Database: Syncing clubhouse reservation permissions for timestamp: {now}")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Ensure Group ID 8 exists in key_fobs.groups
                cur.execute(
                    "INSERT INTO key_fobs.groups (group_id, name) VALUES (8, 'Clubhouse Rental') ON CONFLICT (group_id) DO NOTHING;"
                )
                
                # 2. Query all reservations where payment_made, deposit_on_file, and agreement_received are True
                cur.execute(
                    """
                    SELECT property_id, reservation_date, from_time, to_time
                    FROM key_fobs.clubhouse_reservations
                    WHERE payment_made = TRUE 
                      AND deposit_on_file = TRUE 
                      AND agreement_received = TRUE;
                    """
                )
                rows = cur.fetchall()
                
                active_property_ids = set()
                for prop_id, res_date, f_time, t_time in rows:
                    start_t = f_time if f_time else datetime.time(0, 0, 0)
                    end_t = t_time if t_time else datetime.time(23, 59, 59)
                    
                    start_dt = datetime.datetime.combine(res_date, start_t)
                    end_dt = datetime.datetime.combine(res_date, end_t)
                    
                    if start_dt <= now <= end_dt:
                        active_property_ids.add(prop_id)
                
                # 3. Query current properties mapped to Group ID 8 in property_group_permissions
                cur.execute(
                    "SELECT property_id FROM key_fobs.property_group_permissions WHERE group_id = 8;"
                )
                current_property_ids = {row[0] for row in cur.fetchall()}
                
                # 4. Grant Group 8 to active properties not currently in Group 8
                to_grant = active_property_ids - current_property_ids
                for p_id in to_grant:
                    cur.execute(
                        """
                        INSERT INTO key_fobs.property_group_permissions (property_id, group_id)
                        VALUES (%s, 8)
                        ON CONFLICT (group_id, property_id) DO NOTHING;
                        """,
                        (p_id,)
                    )
                    self.log_audit_action(
                        cur, username, "Grant Clubhouse Rental Group",
                        f"Granted temporary clubhouse rental access (group 8) to property {p_id}"
                    )
                    log_info(f"Database: Granted temporary clubhouse rental access (group 8) to property {p_id}")
                
                # 5. Revoke Group 8 from properties currently in Group 8 that are no longer active
                to_revoke = current_property_ids - active_property_ids
                for p_id in to_revoke:
                    cur.execute(
                        "DELETE FROM key_fobs.property_group_permissions WHERE property_id = %s AND group_id = 8;",
                        (p_id,)
                    )
                    self.log_audit_action(
                        cur, username, "Revoke Clubhouse Rental Group",
                        f"Revoked temporary clubhouse rental access (group 8) from property {p_id}"
                    )
                    log_info(f"Database: Revoked temporary clubhouse rental access (group 8) from property {p_id}")
                
                conn.commit()
                return {
                    'granted': list(to_grant),
                    'revoked': list(to_revoke),
                    'active': list(active_property_ids)
                }

    def get_runtimes_for_date(self, target_date, controller_ip=None):
        """
        Retrieves unique permission change runtimes for a given date, including
        clubhouse reservation start and end times.
        """
        if isinstance(target_date, datetime.datetime):
            target_date = target_date.date()
        # log_info(f"Database: Fetching permission change runtimes for {target_date} (controller_ip: {controller_ip})")
        times_set = set()
        
        if controller_ip:
            query = "SELECT DISTINCT run_times FROM key_fobs.f_get_runtimes(%s::date, %s::cidr) ORDER BY run_times ASC;"
            params = (target_date, controller_ip)
        else:
            query = "SELECT DISTINCT run_times FROM key_fobs.f_get_runtimes(%s::date) ORDER BY run_times ASC;"
            params = (target_date,)
            
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    if row[0]:
                        times_set.add(row[0])
                        
                # Also include start/end times for eligible clubhouse reservations on target_date
                try:
                    cur.execute(
                        """
                        SELECT from_time, to_time 
                        FROM key_fobs.clubhouse_reservations
                        WHERE reservation_date = %s
                          AND payment_made = TRUE
                          AND deposit_on_file = TRUE
                          AND agreement_received = TRUE;
                        """,
                        (target_date,)
                    )
                    for f_time, t_time in cur.fetchall():
                        if f_time:
                            times_set.add(f_time)
                        if t_time:
                            times_set.add(t_time)
                except Exception as e:
                    log_info(f"Notice fetching reservation times: {e}")
                    
        return sorted(list(times_set))
            
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

    def get_expected_permissions(self, fob_id, cidr):
            """
            Helper to get expected permissions for a fob_id on a given controller from database.
            """
            query = """
                SELECT door_no, allow
                FROM key_fobs.f_get_permissions(%s, %s);
            """
            expected = {}
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # print(query, (fob_id, cidr))
                    cur.execute(query, (fob_id, cidr))
                    for door_no, allow in cur.fetchall():
                        expected[int(door_no)] = allow
            return expected

    def get_door_details(self, controller_ip=None):
        """
        Retrieves door details (door_id, door_no, door_desc, controller_ip) from door_controller.door.
        controller_ip is an optional paramter if you want to limit the list to a single door
        """
        if controller_ip:
            if controller_ip[-3:] != '/32': # Assume just IP Address, not CIDR, so append /32 to make it a valid CIDR for the query
                cidr = extract_cidr(controller_ip)
            else:
                cidr = controller_ip
            query = """
                SELECT door_id, door_no, door_desc, controller_ip 
                FROM door_controller.door 
                where controller_ip = %s 
                ORDER BY door_id ASC;"""
        else:
            cidr = None
            query = """
                            SELECT door_id, door_no, door_desc, controller_ip 
                            FROM door_controller.door 
                            ORDER BY door_id ASC;"""

        log_info("Database: Fetching door details.")
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if cidr is not None:
                    cur.execute(query, (cidr,))
                else:
                    cur.execute(query)
                return cur.fetchall()

    def list_access_rules(self):
        """
        List all door access control rules (group permissions).
        Only positive 'Allow' rules are stored and retrieved. If no allow rule exists
        for a group/door/time, access is implicitly forbidden.
        """
        log_info("Database: Fetching all positive allow access rules.")
        query = """
            SELECT 
                gp.perm_id,
                g.group_id,
                g.name AS group_name,
                d.door_id,
                d.door_desc,
                gp.start_date,
                gp.end_date,
                EXTRACT(MONTH FROM gp.start_date)::INT AS start_month,
                EXTRACT(DAY FROM gp.start_date)::INT AS start_day,
                EXTRACT(MONTH FROM gp.end_date)::INT AS end_month,
                EXTRACT(DAY FROM gp.end_date)::INT AS end_day,
                gp.start_time,
                gp.end_time,
                gp.allow
            FROM key_fobs.group_permissions gp
            JOIN key_fobs.groups g ON gp.group_id = g.group_id
            JOIN door_controller.door d ON gp.door_id = d.door_id
            WHERE COALESCE(gp.allow, TRUE) = TRUE
            ORDER BY g.name ASC, d.door_desc ASC, gp.perm_id ASC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def add_access_rule(self, group_id, door_id, start_month, start_day, end_month, end_day,
                        start_time=None, end_time=None, allow=True, username='system'):
        """
        Add a new positive Allow access rule specifying start month, start day, end month, end day,
        door_id, group_id, unlock/lock times. All stored rules are positive Allow intervals.
        """
        log_info(f"Database: Adding positive allow access rule for group_id={group_id}, door_id={door_id} by user={username}")
        current_year = datetime.date.today().year
        try:
            start_date = datetime.date(current_year, int(start_month), int(start_day))
            end_date = datetime.date(current_year, int(end_month), int(end_day))
        except (ValueError, TypeError) as ve:
            raise ValueError(f"Invalid month/day range: {ve}")

        # Empty strings to None conversion for optional time fields
        start_time_val = start_time if start_time else None
        end_time_val = end_time if end_time else None
        allow_val = True  # Always store positive allow rules

        start_m = int(start_month)
        start_d = int(start_day)
        end_m = int(end_month)
        end_d = int(end_day)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Check table columns in key_fobs.group_permissions
                cur.execute(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'key_fobs' AND table_name = 'group_permissions';
                    """
                )
                cols = {row[0] for row in cur.fetchall()}

                # Verify group
                cur.execute("SELECT name FROM key_fobs.groups WHERE group_id = %s;", (group_id,))
                group_row = cur.fetchone()
                if not group_row:
                    raise ValueError(f"Group ID {group_id} not found.")
                group_name = group_row[0]

                # Verify door
                cur.execute("SELECT door_desc FROM door_controller.door WHERE door_id = %s;", (door_id,))
                door_row = cur.fetchone()
                if not door_row:
                    raise ValueError(f"Door ID {door_id} not found.")
                door_desc = door_row[0]

                if 'start_day_of_month' in cols and 'start_month' in cols:
                    query = """
                        INSERT INTO key_fobs.group_permissions 
                            (perm_id, group_id, door_id, start_date, end_date, start_time, end_time, allow,
                             start_month, start_day_of_month, end_month, end_day_of_month)
                        VALUES (
                            (SELECT COALESCE(MAX(perm_id), 0) + 1 FROM key_fobs.group_permissions),
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        RETURNING perm_id;
                    """
                    cur.execute(query, (group_id, door_id, start_date, end_date, start_time_val, end_time_val, allow_val,
                                        start_m, start_d, end_m, end_d))
                else:
                    query = """
                        INSERT INTO key_fobs.group_permissions 
                            (perm_id, group_id, door_id, start_date, end_date, start_time, end_time, allow)
                        VALUES (
                            (SELECT COALESCE(MAX(perm_id), 0) + 1 FROM key_fobs.group_permissions),
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        RETURNING perm_id;
                    """
                    cur.execute(query, (group_id, door_id, start_date, end_date, start_time_val, end_time_val, allow_val))
                perm_id = cur.fetchone()[0]

                details = f"Added positive Allow access rule ID {perm_id}: Group '{group_name}', Door '{door_desc}', Dates: {start_date} to {end_date}, Times: {start_time_val} to {end_time_val}"
                self.log_audit_action(cur, username, "Add Access Rule", details)

            conn.commit()
        return perm_id


    def delete_access_rule(self, perm_id, username='system'):
        """
        Delete an access rule by perm_id.
        """
        return self.remove_group_permission(perm_id, username=username)

    def update_access_rule_times(self, perm_id, start_time=None, end_time=None, username='system'):
        """
        Update the unlock (start_time) and lock (end_time) times for an existing access rule by perm_id.
        Returns True if updated, False if not found.
        """
        log_info(f"Database: Updating times for access rule {perm_id} (start_time={start_time}, end_time={end_time}) by user '{username}'")
        start_time_val = start_time if start_time else None
        end_time_val = end_time if end_time else None

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Fetch details for audit log
                cur.execute(
                    """
                    SELECT g.name, d.door_desc 
                    FROM key_fobs.group_permissions gp
                    JOIN key_fobs.groups g ON gp.group_id = g.group_id
                    JOIN door_controller.door d ON gp.door_id = d.door_id
                    WHERE gp.perm_id = %s;
                    """,
                    (perm_id,)
                )
                rule_row = cur.fetchone()
                if not rule_row:
                    return False
                
                group_name, door_desc = rule_row

                cur.execute(
                    """
                    UPDATE key_fobs.group_permissions
                    SET start_time = %s, end_time = %s
                    WHERE perm_id = %s;
                    """,
                    (start_time_val, end_time_val, perm_id)
                )
                rowcount = cur.rowcount
                if rowcount > 0:
                    details = f"Updated times for access rule #{perm_id} (Group '{group_name}', Door '{door_desc}'): unlock={start_time_val}, lock={end_time_val}"
                    self.log_audit_action(cur, username, "Update Access Rule Times", details)
            conn.commit()
        return rowcount > 0



