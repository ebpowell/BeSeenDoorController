-- get the permission change schedule for a given date 

create or replace function key_fobs.f_get_group_for_runtime(p_controller_ip CIDR DEFAULT NULL)
returns table (group_id TIME,
				controller_ip CIDR)
language plpgsql
as
$$
DECLARE
    v_lock_key BIGINT;
    v_lock_acquired BOOLEAN;
BEGIN
    -- Prevent concurrent container execution via transaction-level advisory lock
    v_lock_key := hashtext('f_get_runtimes_' || COALESCE(p_controller_ip::text, 'all'))::bigint;
    v_lock_acquired := pg_try_advisory_xact_lock(v_lock_key);

    IF NOT v_lock_acquired THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH runtime AS (
        SELECT DISTINCT vad.controller_ip, group_id
        FROM key_fobs.v_export_runtimes vad 
        WHERE start_date <= current_date
          AND end_date >= current_date
          and start_time <= current_time
          and end_time >= current_time
          AND (p_controller_ip IS NULL OR vad.controller_ip = p_controller_ip)
        UNION
        SELECT DISTINCT vad.controller_ip, group_id
        FROM key_fobs.v_export_runtimes vad 
        WHERE start_date <= current_date
          AND end_date >= current_date
          AND start_time <= current_time
          AND end_time >= current_time
          AND (p_controller_ip IS NULL OR vad.controller_ip = p_controller_ip)
    )
    SELECT DISTINCT rt.controller_ip, group_id FROM runtime rt;
END;
$$;

SELECT * FROM key_fobs.f_get_group_for_runtime('69.21.119.148/32');
