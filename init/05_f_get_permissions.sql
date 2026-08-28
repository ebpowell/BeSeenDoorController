DROP FUNCTION IF EXISTS key_fobs.f_get_permissions(INT, CIDR);

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
    -- Drop temporary table if it already exists in the current session
    DROP TABLE IF EXISTS temp_doors;

    -- Create temporary table with default allow = 0
    CREATE TEMP TABLE temp_doors AS
    SELECT d.door_no, 0 AS allow
    FROM door_controller.door d
    WHERE d.controller_ip = p_controller_ip;

    -- Update allow status based on permission rules and current timestamp
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
      AND CURRENT_TIME >= atm.start_time::time
      AND CURRENT_TIME <= atm.end_time::time
      AND CURRENT_DATE >= atm.start_date
      AND CURRENT_DATE <= atm.end_date;   

    -- Return output and cleanup temp table
    RETURN QUERY
    SELECT td.door_no, td.allow FROM temp_doors td;

    DROP TABLE IF EXISTS temp_doors;
END;
$$;