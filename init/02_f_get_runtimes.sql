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
    WITH rule_dates AS
    (
        SELECT DISTINCT start_time, end_time, d.controller_ip,
            to_date(concat(gp.start_day_of_month::text, '-', gp.start_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text) AS start_date,
            to_date(concat(gp.end_day_of_month::text, '-', gp.end_month::text, '-', date_part('year'::text, (now() AT TIME ZONE 'America/New_York'))::text), 'DD-MM-YYYY'::text) AS end_date
        FROM key_fobs.group_permissions gp
        INNER JOIN door_controller.door d 
            ON gp.door_id = d.door_id 
        WHERE (p_controller_ip IS NULL OR d.controller_ip = p_controller_ip)
          AND gp.allow = true
    ), runtime AS 
    (
        SELECT DISTINCT start_time runtime, rd.controller_ip
        FROM rule_dates rd 
        WHERE start_date <= p_date
          AND end_date >= p_date
          AND (p_controller_ip IS NULL OR rd.controller_ip = p_controller_ip)
        UNION
        SELECT DISTINCT end_time runtime, rd.controller_ip
        FROM rule_dates rd	
        WHERE start_date <= p_date
          AND end_date >= p_date
          AND (p_controller_ip IS NULL OR rd.controller_ip = p_controller_ip)
    )
    SELECT DISTINCT runtime, rt.controller_ip FROM runtime rt
    ORDER BY runtime ASC;
END;
$$;

SELECT * FROM key_fobs.f_get_runtimes(CURRENT_DATE,  '69.21.119.148/32');
