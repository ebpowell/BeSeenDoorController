-- get the permission change schedule for a given date 

create or replace function key_fobs.f_get_runtimes(p_date DATE, p_controller_ip CIDR DEFAULT NULL)
returns table (run_times TIME,
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
        SELECT DISTINCT start_time runtime, vad.controller_ip
        FROM key_fobs.v_export_runtimes vad 
        WHERE start_date <= p_date
          AND end_date >= p_date
          AND (p_controller_ip IS NULL OR vad.controller_ip = p_controller_ip)
        UNION
        SELECT DISTINCT end_time runtime, vad.controller_ip
        FROM key_fobs.v_export_runtimes vad 
        WHERE start_date <= p_date
          AND end_date >= p_date
          AND (p_controller_ip IS NULL OR vad.controller_ip = p_controller_ip)
    )
    SELECT DISTINCT runtime, rt.controller_ip FROM runtime rt
    ORDER BY runtime ASC;
END;
$$;

SELECT * FROM key_fobs.f_get_runtimes(CURRENT_DATE);
