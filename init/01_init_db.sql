-- Database Initialization Script for BeSeenDoorController
-- Clean schema creation matching current database views, queries, and application functions

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS key_fobs;
CREATE SCHEMA IF NOT EXISTS door_controller;
CREATE SCHEMA IF NOT EXISTS dataload;
CREATE SCHEMA IF NOT EXISTS webgui;

-- Drop existing tables/views to rebuild cleanly
DROP VIEW IF EXISTS key_fobs.vint_acl_data CASCADE;
DROP VIEW IF EXISTS door_controller.v_keyswipes CASCADE;
DROP VIEW IF EXISTS door_controller.vint_controller_allowed_access CASCADE;
DROP VIEW IF EXISTS door_controller.vint_system_assigned_fob_compare CASCADE;
DROP VIEW IF EXISTS door_controller.vext_system_missing_assigned_fobs CASCADE;
DROP VIEW IF EXISTS door_controller.vext_system_unassigned_fobs CASCADE;

DROP TABLE IF EXISTS webgui.users CASCADE;
DROP TABLE IF EXISTS key_fobs.clubhouse_deposits CASCADE;
DROP TABLE IF EXISTS key_fobs.clubhouse_reservations CASCADE;
DROP TABLE IF EXISTS key_fobs.reservation_blocks CASCADE;
DROP TABLE IF EXISTS key_fobs.reservation_fee_config CASCADE;
DROP TABLE IF EXISTS key_fobs.property_group_permissions CASCADE;
DROP TABLE IF EXISTS key_fobs.group_permissions CASCADE;
DROP TABLE IF EXISTS key_fobs.groups CASCADE;
DROP TABLE IF EXISTS key_fobs.audit_logs CASCADE;
DROP TABLE IF EXISTS key_fobs.fob_replacements CASCADE;
DROP TABLE IF EXISTS key_fobs.keyfobs CASCADE;
DROP TABLE IF EXISTS key_fobs.owners CASCADE;
DROP TABLE IF EXISTS key_fobs.property_owners CASCADE;
DROP TABLE IF EXISTS key_fobs.properties CASCADE;
DROP TABLE IF EXISTS door_controller.door CASCADE;
DROP TABLE IF EXISTS door_controller.system_fobs CASCADE;
DROP TABLE IF EXISTS door_controller.t_keyswipes CASCADE;
DROP TABLE IF EXISTS door_controller.access_list_from_controller CASCADE;
DROP TABLE IF EXISTS door_controller.controller_metrics CASCADE;

-- 1. Create webgui.users table
CREATE TABLE webgui.users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'ManagementCo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create key_fobs.properties table
CREATE TABLE key_fobs.properties (
    property_id INT PRIMARY KEY,
    address VARCHAR(255) UNIQUE NOT NULL,
    knox_co_lot_id INT
);

-- 3. Create key_fobs.owners table
CREATE TABLE key_fobs.owners (
    owner_id SERIAL PRIMARY KEY,
    property_id INT REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    last_name VARCHAR(100),
    first_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create key_fobs.keyfobs table
CREATE TABLE key_fobs.keyfobs (
    keyfob_id SERIAL,
    fob_id INT PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Create key_fobs.fob_replacements table
CREATE TABLE key_fobs.fob_replacements (
    replacement_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    replaced_fob_id INT NOT NULL,
    new_fob_id INT NOT NULL,
    replaced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Create key_fobs.groups table
CREATE TABLE key_fobs.groups (
    group_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- 7. Create key_fobs.group_permissions table
CREATE TABLE key_fobs.group_permissions (
    perm_id SERIAL PRIMARY KEY,
    group_id INT REFERENCES key_fobs.groups(group_id) ON DELETE CASCADE,
    door_id INT,
    allow BOOLEAN DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    start_time TIME,
    end_time TIME,
    start_month INT,
    start_day_of_month INT,
    end_month INT,
    end_day_of_month INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Create key_fobs.property_group_permissions table
CREATE TABLE key_fobs.property_group_permissions (
    prop_grp_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    group_id INT NOT NULL REFERENCES key_fobs.groups(group_id) ON DELETE CASCADE,
    UNIQUE (group_id, property_id)
);

-- 9. Create key_fobs.audit_logs table
CREATE TABLE key_fobs.audit_logs (
    log_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Create key_fobs.clubhouse_reservations table
CREATE TABLE key_fobs.clubhouse_reservations (
    reservation_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    reservation_date DATE NOT NULL,
    from_time TIME,
    to_time TIME,
    payment_made BOOLEAN NOT NULL DEFAULT FALSE,
    deposit_on_file BOOLEAN NOT NULL DEFAULT FALSE,
    agreement_received BOOLEAN NOT NULL DEFAULT FALSE,
    fee DECIMAL(10,2) DEFAULT 15.00,
    early_setup BOOLEAN NOT NULL DEFAULT FALSE,
    event_type VARCHAR(50) DEFAULT 'Private Event',
    reschedule_required BOOLEAN DEFAULT FALSE,
    event_name VARCHAR(150),
    event_description TEXT,
    deposit_added_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Create key_fobs.reservation_blocks table
CREATE TABLE key_fobs.reservation_blocks (
    block_id SERIAL PRIMARY KEY,
    block_key VARCHAR(50) UNIQUE NOT NULL,
    block_name VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    display_order INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 12. Create key_fobs.reservation_fee_config table
CREATE TABLE key_fobs.reservation_fee_config (
    config_key VARCHAR(50) PRIMARY KEY,
    fee_amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. Create key_fobs.clubhouse_deposits table
CREATE TABLE key_fobs.clubhouse_deposits (
    deposit_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    reservation_id INT,
    amount DECIMAL(10,2) NOT NULL DEFAULT 150.00,
    deposit_status VARCHAR(30) NOT NULL DEFAULT 'On File',
    deposit_date DATE NOT NULL DEFAULT CURRENT_DATE,
    date_added DATE NOT NULL DEFAULT CURRENT_DATE,
    check_or_ref_no VARCHAR(100),
    received_by VARCHAR(100),
    refund_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. Create door_controller.door table
CREATE TABLE door_controller.door (
    door_id INT PRIMARY KEY,
    door_no INT,
    door_desc VARCHAR(255),
    controller INT,
    controller_ip CIDR
);

-- 15. Create door_controller.system_fobs table
CREATE TABLE door_controller.system_fobs (
    fob_record_id SERIAL PRIMARY KEY,
    fob_id INT NOT NULL,
    controller_id INT,
    controller_ip CIDR NOT NULL,
    controller INT,
    controller_record_id INT,
    record_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 16. Create door_controller.t_keyswipes table
CREATE TABLE door_controller.t_keyswipes (
    record_id BIGINT PRIMARY KEY,
    fob_id BIGINT,
    status TEXT,
    door INT,
    swipe_timestamp TEXT,
    door_controller_ip TEXT
);

-- 17. Create door_controller.access_list_from_controller table
CREATE TABLE door_controller.access_list_from_controller (
    record_id INT,
    fob_id INT,
    door_controller INT,
    status TEXT,
    door_id INT,
    controller_ip CIDR,
    record_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 18. Create door_controller.controller_metrics table
CREATE TABLE door_controller.controller_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    controller_ip CIDR,
    metric_name VARCHAR NOT NULL,
    metric_value NUMERIC NOT NULL,
    metadata JSONB
);

-- 19. Create View key_fobs.vint_acl_data
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

-- 20. Create View door_controller.v_keyswipes
CREATE OR REPLACE VIEW door_controller.v_keyswipes AS
SELECT tks.record_id,
    tks.fob_id,
    tks.status,
    tks.door,
    d.door_desc,
    to_timestamp(tks.swipe_timestamp, 'YYYY-MM-DD HH24:MI:SS'::text) AS swipe_time,
    o.last_name,
    p.address
FROM door_controller.t_keyswipes tks
JOIN door_controller.door d ON (d.controller_ip::inet = ltrim(tks.door_controller_ip, 'http://')::cidr::inet AND d.door_no = tks.door)
RIGHT JOIN key_fobs.keyfobs kf ON kf.fob_id = tks.fob_id
JOIN key_fobs.owners o ON kf.property_id = o.property_id
JOIN key_fobs.properties p ON p.property_id = kf.property_id
WHERE tks.record_id IS NOT NULL
ORDER BY to_timestamp(tks.swipe_timestamp, 'YYYY-MM-DD HH24:MI:SS'::text) DESC;

-- 21. Create View door_controller.vint_controller_allowed_access
CREATE OR REPLACE VIEW door_controller.vint_controller_allowed_access AS
WITH contler_allowed_access AS (
    SELECT alfc.fob_id,
       alfc.record_time,
       alfc.door_id,
       alfc.controller_ip
    FROM door_controller.access_list_from_controller alfc
    WHERE alfc.status = 'Allow'
)
SELECT caa.fob_id,
   caa.record_time,
   d.door_desc
FROM contler_allowed_access caa
JOIN door_controller.door d ON (d.controller_ip::inet = caa.controller_ip::inet AND d.door_no = caa.door_id);

-- 22. Create View door_controller.vint_system_assigned_fob_compare
CREATE OR REPLACE VIEW door_controller.vint_system_assigned_fob_compare AS
WITH latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip) fob_id, controller_ip, record_time
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
), assigned_fobs AS (
    SELECT DISTINCT fob_id FROM key_fobs.keyfobs
)
SELECT a.fob_id AS assigned_fob_id,
   s.fob_id AS system_fob_id,
   s.controller_ip,
   s.record_time
FROM assigned_fobs a
FULL JOIN latest_system_fobs s ON a.fob_id = s.fob_id;

-- 23. Create View door_controller.vext_system_missing_assigned_fobs
CREATE OR REPLACE VIEW door_controller.vext_system_missing_assigned_fobs AS
WITH active_controllers AS (
    SELECT DISTINCT controller_ip FROM door_controller.door WHERE controller_ip IS NOT NULL
), expected_fob_controllers AS (
    SELECT k.fob_id, c.controller_ip
    FROM key_fobs.keyfobs k CROSS JOIN active_controllers c
), latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip) fob_id, controller_ip
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
)
SELECT efc.fob_id AS assigned_fob_id, efc.controller_ip
FROM expected_fob_controllers efc
LEFT JOIN latest_system_fobs lsf ON (efc.fob_id = lsf.fob_id AND efc.controller_ip::inet = lsf.controller_ip::inet)
WHERE lsf.fob_id IS NULL;

-- 24. Create View door_controller.vext_system_unassigned_fobs
CREATE OR REPLACE VIEW door_controller.vext_system_unassigned_fobs AS
WITH latest_system_fobs AS (
    SELECT DISTINCT ON (fob_id, controller_ip) fob_id, controller_ip
    FROM door_controller.system_fobs
    ORDER BY fob_id, controller_ip, record_time DESC
)
SELECT lsf.fob_id AS system_fob_id, lsf.controller_ip
FROM latest_system_fobs lsf
LEFT JOIN key_fobs.keyfobs k ON lsf.fob_id = k.fob_id
WHERE k.fob_id IS NULL;

-- 25. Create Function key_fobs.f_get_acl_changes
DROP FUNCTION IF EXISTS key_fobs.f_get_acl_changes(TIMESTAMP, TIMESTAMP);
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
    WHERE (s.allow IS DISTINCT FROM f.allow);
END;
$$;

-- Seed Default Doors
INSERT INTO door_controller.door (door_id, door_no, door_desc, controller, controller_ip) VALUES
(1, 1, 'Front Door', 1, '69.21.119.147/32'),
(2, 2, 'Back Door', 1, '69.21.119.147/32'),
(3, 1, 'Gate 1', 2, '69.21.119.148/32'),
(4, 2, 'Gate 2', 2, '69.21.119.148/32')
ON CONFLICT (door_id) DO NOTHING;

-- Seed Default Reservation Blocks
INSERT INTO key_fobs.reservation_blocks (block_key, block_name, start_time, end_time, display_order) VALUES
('block1', 'Block 1: Morning', '08:00:00', '12:00:00', 1),
('block2', 'Block 2: Afternoon', '13:00:00', '17:00:00', 2),
('block3', 'Block 3: Evening', '18:00:00', '23:00:00', 3)
ON CONFLICT (block_key) DO NOTHING;

-- Seed Default Fee Config
INSERT INTO key_fobs.reservation_fee_config (config_key, fee_amount, description) VALUES
('single_block_fee', 15.00, 'Fee for reserving a single time block'),
('multi_block_fee', 30.00, 'Flat rate fee for reserving 2 or 3 time blocks')
ON CONFLICT (config_key) DO NOTHING;

-- Seed Fixed Properties Fact Data
INSERT INTO key_fobs.properties (property_id, address) VALUES
(10001, '101 Wentworth Ave'),
(10002, '102 Wentworth Ave'),
(10003, '103 Wentworth Ave'),
(10004, '104 Wentworth Ave')
ON CONFLICT (property_id) DO NOTHING;

-- Seed Property Owners
INSERT INTO key_fobs.owners (property_id, last_name, first_name) VALUES
(10001, 'Doe', 'John'),
(10002, 'Smith', 'Alice'),
(10003, 'Johnson', 'Bob'),
(10004, 'Brown', 'Charlie')
ON CONFLICT DO NOTHING;

-- Seed Fobs assigned to Properties
INSERT INTO key_fobs.keyfobs (fob_id, property_id) VALUES
(1001, 10001),
(1002, 10002),
(1003, 10003),
(1004, 10004)
ON CONFLICT (fob_id) DO NOTHING;

-- Seed Default webgui.users
INSERT INTO webgui.users (username, password_hash, role) VALUES
('admin', 'scrypt:32768:8:1$UDYUXN3FvmA7ycHA$bf9b6642937663d449b6ad4fefb75d3cb64cf3827465a1504a61327fbc621f6366df1fe5cc802e51bbd7c003bd59a71e862ab7a0e7b7aefad8cbe96def8cb75c', 'SysAdmin'),
('operator1', 'scrypt:32768:8:1$ZVaLpzN1RXIy1tU9$b27d5ceffc458b36245d348a8ac9129ab46f0548559c13e35da3f8f48e8355a548aaa256f096e2fd5e5309f6bf5359e6adbaf49114a3f5f5acd2608dbaa46147', 'ManagementCo'),
('secretary1', 'scrypt:32768:8:1$OXHMh3mcsjXjh3Ao$f03cc7cf93913694a180c9c2b444904769012a7fdceae0289e4fe1b6da0a1dc6c88f5592c76a2a5ca9d0f8bbf50162add0ddc4e7ef954758f5fecee8be5fe905', 'Secretary')
ON CONFLICT (username) DO NOTHING;

-- Seed Default Groups
INSERT INTO key_fobs.groups (group_id, name) VALUES
(1, 'ManagementCo'),
(2, 'Secretary'),
(3, 'SysAdmin')
ON CONFLICT (group_id) DO NOTHING;

-- Seed initial property group permissions mappings
INSERT INTO key_fobs.property_group_permissions (property_id, group_id) VALUES
(10001, 1)
ON CONFLICT DO NOTHING;
