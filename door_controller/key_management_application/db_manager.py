import psycopg2
from psycopg2.extras import RealDictCursor
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

    def list_fobs(self):
        """
        List all key fobs, including their property address and current inherited owner.
        """
        log_info("Database: Fetching all fobs with property and owner info.")
        query = """
            SELECT f.fob_id, p.property_id, p.address, o.owner_name, f.created_at, f.updated_at
            FROM key_fobs.fobs f
            JOIN key_fobs.properties p ON f.property_id = p.property_id
            LEFT JOIN key_fobs.property_owners o ON p.property_id = o.property_id
            ORDER BY f.fob_id ASC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()

    def list_properties(self):
        """
        List all properties (fact table) and their current owners.
        """
        log_info("Database: Fetching all properties.")
        query = """
            SELECT p.property_id, p.address, o.owner_name
            FROM key_fobs.properties p
            LEFT JOIN key_fobs.property_owners o ON p.property_id = o.property_id
            ORDER BY p.address ASC;
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
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

    def add_fob(self, fob_id, property_id, replaced_fob_id=None):
        """
        Add a new fob assigned to a property. Optionally replaces an old fob and logs the transaction.
        Raises ValueError if fob_id already exists.
        """
        log_info(f"Database: Adding fob_id={fob_id} assigned to property_id={property_id} (replacing={replaced_fob_id})")
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Verify new fob doesn't exist
                cur.execute("SELECT 1 FROM key_fobs.fobs WHERE fob_id = %s;", (fob_id,))
                if cur.fetchone():
                    raise ValueError(f"Fob ID {fob_id} already exists.")
                
                # 2. If replacement is requested, delete old fob and log replacement
                if replaced_fob_id is not None:
                    cur.execute("DELETE FROM key_fobs.fobs WHERE fob_id = %s;", (replaced_fob_id,))
                    cur.execute(
                        """
                        INSERT INTO key_fobs.fob_replacements (property_id, replaced_fob_id, new_fob_id)
                        VALUES (%s, %s, %s);
                        """,
                        (property_id, replaced_fob_id, fob_id)
                    )
                
                # 3. Insert new fob
                cur.execute(
                    """
                    INSERT INTO key_fobs.fobs (fob_id, property_id)
                    VALUES (%s, %s);
                    """,
                    (fob_id, property_id)
                )
            conn.commit()
        log_info(f"Database: Fob {fob_id} assigned to property {property_id} successfully.")

    def remove_fob(self, fob_id):
        """
        Remove an existing fob. Returns True if removed, False if not found.
        """
        log_info(f"Database: Attempting to remove fob_id={fob_id}")
        query = "DELETE FROM key_fobs.fobs WHERE fob_id = %s;"
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (fob_id,))
                rowcount = cur.rowcount
            conn.commit()
        success = rowcount > 0
        if success:
            log_info(f"Database: Fob {fob_id} removed successfully.")
        else:
            log_info(f"Database: Fob {fob_id} not found for removal.")
        return success

    def update_property_owner(self, property_id, owner_name):
        """
        Update (upsert) the owner of a property. All fobs under this property
        will inherit the new owner. Returns True on success.
        """
        log_info(f"Database: Updating owner of property_id={property_id} to '{owner_name}'")
        query = """
            INSERT INTO key_fobs.property_owners (property_id, owner_name, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (property_id) DO UPDATE
            SET owner_name = EXCLUDED.owner_name, updated_at = EXCLUDED.updated_at;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (property_id, owner_name))
                rowcount = cur.rowcount
            conn.commit()
        
        # Trigger an update on the fobs' updated_at so that tracking triggers are aware of the trickle-down
        fob_update_query = """
            UPDATE key_fobs.fobs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE property_id = %s;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(fob_update_query, (property_id,))
            conn.commit()
            
        success = rowcount > 0
        log_info(f"Database: Property {property_id} owner updated successfully.")
        return success
