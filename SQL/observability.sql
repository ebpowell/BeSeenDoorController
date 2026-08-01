-- Observability Schema Extensions for Database Metrics

-- Create controller_metrics table
CREATE TABLE IF NOT EXISTS door_controller.controller_metrics (
    metric_id SERIAL PRIMARY KEY,
    metric_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    controller_ip CIDR,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metadata JSONB
);

-- View: compare assigned fobs vs fobs present on controllers
drop view if exists door_controller.vint_system_assigned_fob_compare;
CREATE OR REPLACE VIEW door_controller.vint_system_assigned_fob_compare AS
WITH latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip)
        fob_id,
        controller_ip,
        record_time
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
),
assigned_fobs AS (
    SELECT DISTINCT fob_id
    FROM key_fobs.keyfobs
)
SELECT 
    a.fob_id AS assigned_fob_id,
    s.fob_id AS system_fob_id,
    s.controller_ip,
    s.record_time
FROM assigned_fobs a
FULL OUTER JOIN latest_system_fobs s
ON a.fob_id = s.fob_id;

-- View: assigned fobs missing from specific controllers
drop view if exists door_controller.vext_system_missing_assigned_fobs;
CREATE OR REPLACE VIEW door_controller.vext_system_missing_assigned_fobs AS
WITH active_controllers AS (
    SELECT DISTINCT controller_ip 
    FROM door_controller.door 
    WHERE controller_ip IS NOT NULL
),
expected_fob_controllers AS (
    SELECT k.fob_id, c.controller_ip
    FROM key_fobs.keyfobs k
    CROSS JOIN active_controllers c
),
latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip)
        fob_id,
        controller_ip
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
)
SELECT 
    efc.fob_id AS assigned_fob_id,
    efc.controller_ip
FROM expected_fob_controllers efc
LEFT JOIN latest_system_fobs lsf
ON efc.fob_id = lsf.fob_id AND efc.controller_ip = lsf.controller_ip
WHERE lsf.fob_id IS NULL;

-- View: fobs present on controllers that are not assigned in the system
drop view if exists door_controller.vext_system_unassigned_fobs;
CREATE OR REPLACE VIEW door_controller.vext_system_unassigned_fobs AS
WITH latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip)
        fob_id,
        controller_ip
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
)
SELECT 
    lsf.fob_id AS system_fob_id,
    lsf.controller_ip
FROM latest_system_fobs lsf
LEFT JOIN key_fobs.keyfobs k
ON lsf.fob_id = k.fob_id
WHERE k.fob_id IS NULL;
