drop FUNCTION key_fobs.f_get_permissions;

CREATE OR REPLACE FUNCTION key_fobs.f_get_permissions (
    p_fob_id INT, 
    p_controller_ip CIDR, 
    p_the_time TIME, 
    p_the_date DATE
)
RETURNS TABLE (
    door_no INT,  -- Ensure these data types match your table schema
    allow INT
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        vad.door_no::INT, 
        vad.allow::INT
    FROM 
        key_fobs.vint_acl_data vad
    WHERE 
        vad.fob_id = p_fob_id
        AND vad.controller_ip = p_controller_ip
        AND p_the_time::time > vad.start_time::time
        AND p_the_time::time < vad.end_time::time
        AND p_the_date > vad.start_date 
        AND p_the_date < vad.end_date;
END;
$$;


SELECT * FROM key_fobs.f_get_permissions(12345, '69.21.119.147/32', NOW(), CURRENT_DATE);


 SELECT 
        vad.door_no::INT, 
        vad.allow::INT
    FROM 
        key_fobs.vint_acl_data vad
    WHERE 
        vad.fob_id = 12345
        AND vad.controller_ip = '69.21.119.147/32'
        AND NOW()::time > vad.start_time::time
        AND NOW()::time < vad.end_time::time
        AND CURRENT_DATE > vad.start_date 
        AND CURRENT_DATE < vad.end_date;

