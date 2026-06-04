-- Database Initialization Script for BeSeenDoorController
-- Refactored for Property-Owner relationship

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS key_fobs;
CREATE SCHEMA IF NOT EXISTS door_controller;
CREATE SCHEMA IF NOT EXISTS dataload;

-- Drop existing tables to rebuild with new model
DROP TABLE IF EXISTS key_fobs.fobs CASCADE;
DROP TABLE IF EXISTS key_fobs.property_owners CASCADE;
DROP TABLE IF EXISTS key_fobs.properties CASCADE;
DROP TABLE IF EXISTS key_fobs.fob_replacements CASCADE;
DROP TABLE IF EXISTS key_fobs.users CASCADE;
DROP TABLE IF EXISTS key_fobs.audit_logs CASCADE;
DROP TABLE IF EXISTS key_fobs.role_properties CASCADE;
DROP TABLE IF EXISTS key_fobs.groups CASCADE;
DROP TABLE IF EXISTS key_fobs.group_permissions CASCADE;
DROP TABLE IF EXISTS key_fobs.property_group_permissions CASCADE;

-- Create key_fobs.properties table (Fixed Fact Table)
CREATE TABLE key_fobs.properties (
    property_id INT PRIMARY KEY,
    address VARCHAR(255) UNIQUE NOT NULL
);

-- Create key_fobs.property_owners table
CREATE TABLE key_fobs.property_owners (
    property_id INT PRIMARY KEY REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    owner_name VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create key_fobs.fobs table (Fobs linked to property_id)
CREATE TABLE key_fobs.fobs (
    fob_id INT PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create key_fobs.fob_replacements table
CREATE TABLE key_fobs.fob_replacements (
    replacement_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    replaced_fob_id INT NOT NULL,
    new_fob_id INT NOT NULL,
    replaced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create key_fobs.users table
CREATE TABLE key_fobs.users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'operator',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create key_fobs.groups table
CREATE TABLE key_fobs.groups (
    group_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Create key_fobs.group_permissions table
CREATE TABLE key_fobs.group_permissions (
    perm_id SERIAL PRIMARY KEY,
    start_date DATE,
    end_date DATE,
    start_time TIME,
    end_time TIME,
    door_id INT,
    allow BOOLEAN,
    group_id INT REFERENCES key_fobs.groups(group_id) ON DELETE CASCADE
);

-- Create key_fobs.property_group_permissions table
CREATE TABLE key_fobs.property_group_permissions (
    prop_grp_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
    group_id INT NOT NULL REFERENCES key_fobs.groups(group_id) ON DELETE CASCADE,
    UNIQUE (group_id, property_id)
);

-- Create key_fobs.audit_logs table
CREATE TABLE key_fobs.audit_logs (
    log_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create key_fobs.vint_acl_data table (Access Control List Rules)
CREATE TABLE IF NOT EXISTS key_fobs.vint_acl_data (
    fob_id INT NOT NULL,
    door_id INT NOT NULL,
    door_no INT,
    controller_ip CIDR NOT NULL,
    allow BOOLEAN DEFAULT TRUE,
    start_time TIME DEFAULT '00:00:00',
    end_time TIME DEFAULT '23:59:59',
    start_date DATE DEFAULT '2000-01-01',
    end_date DATE DEFAULT '2099-12-31',
    PRIMARY KEY (fob_id, door_id, controller_ip)
);

-- Create door_controller.system_fobs table
CREATE TABLE IF NOT EXISTS door_controller.system_fobs (
    controller_record_id SERIAL PRIMARY KEY,
    fob_id INT NOT NULL,
    controller_ip CIDR NOT NULL,
    record_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Drop and recreate f_get_permissions function
DROP FUNCTION IF EXISTS key_fobs.f_get_permissions(INT, CIDR, TIME, DATE);
CREATE OR REPLACE FUNCTION key_fobs.f_get_permissions (
    p_fob_id INT, 
    p_controller_ip CIDR, 
    p_the_time TIME, 
    p_the_date DATE
)
RETURNS TABLE (
    door_no INT,
    allow INT
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(vad.door_no, vad.door_id)::INT, 
        vad.allow::INT
    FROM 
        key_fobs.vint_acl_data vad
    WHERE 
        vad.fob_id = p_fob_id
        AND vad.controller_ip = p_controller_ip
        AND p_the_time BETWEEN vad.start_time AND vad.end_time
        AND p_the_date BETWEEN vad.start_date AND vad.end_date;
END;
$$;

-- Drop and recreate f_get_acl_changes function
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

-- Seed Fixed Properties Fact Data
INSERT INTO key_fobs.properties (property_id, address) VALUES
(10001, '101 Wentworth Ave'),
(10002, '102 Wentworth Ave'),
(10003, '103 Wentworth Ave'),
(10004, '104 Wentworth Ave')
ON CONFLICT (property_id) DO NOTHING;

-- Seed Current Property Owners
INSERT INTO key_fobs.property_owners (property_id, owner_name) VALUES
(10001, 'John Doe'),
(10002, 'Alice Smith'),
(10003, 'Bob Johnson'),
(10004, 'Charlie Brown')
ON CONFLICT (property_id) DO NOTHING;

-- Seed Fobs assigned to Properties
INSERT INTO key_fobs.fobs (fob_id, property_id) VALUES
(1001, 10001),
(1002, 10002),
(1003, 10003),
(1004, 10004)
ON CONFLICT (fob_id) DO NOTHING;

-- Seed access control list (same as before)
INSERT INTO key_fobs.vint_acl_data (fob_id, door_id, door_no, controller_ip, allow) VALUES
(1001, 1, 1, '69.21.119.147/32', TRUE),
(1001, 2, 2, '69.21.119.147/32', TRUE),
(1002, 1, 1, '69.21.119.147/32', TRUE),
(1002, 2, 2, '69.21.119.148/32', FALSE),
(1003, 1, 1, '69.21.119.148/32', TRUE)
ON CONFLICT (fob_id, door_id, controller_ip) DO NOTHING;

-- Seed default admin user
INSERT INTO key_fobs.users (username, password_hash, role) VALUES
('admin', 'scrypt:32768:8:1$UDYUXN3FvmA7ycHA$bf9b6642937663d449b6ad4fefb75d3cb64cf3827465a1504a61327fbc621f6366df1fe5cc802e51bbd7c003bd59a71e862ab7a0e7b7aefad8cbe96def8cb75c', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Seed default operator user
INSERT INTO key_fobs.users (username, password_hash, role) VALUES
('operator1', 'scrypt:32768:8:1$ZVaLpzN1RXIy1tU9$b27d5ceffc458b36245d348a8ac9129ab46f0548559c13e35da3f8f48e8355a548aaa256f096e2fd5e5309f6bf5359e6adbaf49114a3f5f5acd2608dbaa46147', 'operator')
ON CONFLICT (username) DO NOTHING;

-- Seed default groups
INSERT INTO key_fobs.groups (group_id, name) VALUES
(1, 'operator'),
(2, 'manager'),
(3, 'staff')
ON CONFLICT (group_id) DO NOTHING;

-- Seed initial property group permissions mappings (operator has access to property 10001 - 101 Wentworth Ave)
INSERT INTO key_fobs.property_group_permissions (property_id, group_id) VALUES
(10001, 1)
ON CONFLICT DO NOTHING;
