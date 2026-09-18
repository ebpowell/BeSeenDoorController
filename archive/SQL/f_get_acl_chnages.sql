drop function key_fobs.f_get_acl_changes;

CREATE OR REPLACE FUNCTION key_fobs.f_get_acl_changes(
    check_now TIMESTAMP, 
    check_future TIMESTAMP
)
RETURNS TABLE (
    fob_id INT,
    door_id INT,
    controller_ip CIDR,
    old_allow BOOLEAN,
    new_allow BOOLEAN,
    change_type TEXT
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH acl_at_start AS (
        SELECT v.fob_id, v.door_id, v.controller_ip, v.allow
        FROM key_fobs.vint_acl_data v
        WHERE check_now::time BETWEEN v.start_time AND v.end_time
          AND check_now::date BETWEEN v.start_date AND v.end_date
    ),
    acl_at_future AS (
        SELECT v.fob_id, v.door_id, v.controller_ip, v.allow
        FROM key_fobs.vint_acl_data v
        WHERE check_future::time BETWEEN v.start_time AND v.end_time
          AND check_future::date BETWEEN v.start_date AND v.end_date
    )
    SELECT 
        COALESCE(s.fob_id, f.fob_id) AS fob_id,
        COALESCE(s.door_id, f.door_id) AS door_id,
        COALESCE(s.controller_ip, f.controller_ip) AS controller_ip,
        s.allow AS old_allow,
        f.allow AS new_allow,
        CASE 
            WHEN s.fob_id IS NULL THEN 'ADDED'
            WHEN f.fob_id IS NULL THEN 'REMOVED'
            WHEN s.allow != f.allow THEN 'TOGGLED'
            ELSE 'NO_CHANGE'
        END AS change_type
    FROM acl_at_start s
    FULL OUTER JOIN acl_at_future f 
        ON s.fob_id = f.fob_id 
        AND s.door_id = f.door_id 
        AND s.controller_ip = f.controller_ip
    WHERE (s.allow IS DISTINCT FROM f.allow); -- Only return actual changes
END;
$$;



SELECT * FROM key_fobs.f_get_acl_changes(NOW()::timestamp, '2026-01-01 12:00:00');
