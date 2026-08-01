#!/usr/bin/env python3
"""
CLI tool to collect door controller system metrics and run statistical audits.
Writes results to door_controller.controller_metrics table for Grafana visualization.
"""

import sys
import os
import random
import json
import argparse
import psycopg2
from psycopg2.extras import Json
import urllib.parse

# Resolve project path and imports
project_path = '/app'
if not os.path.exists(project_path):
    project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_path not in sys.path:
    sys.path.append(project_path)

os.environ['APP_CONFIG_DIR'] = os.path.join(project_path, 'config')

from door_controller.common_lib.utils import load_config, log_info, log_error
from door_controller.common_lib.data_manager import DataManager

def ensure_metrics_table_exists(cur):
    """Ensure the controller_metrics table exists in the database."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS door_controller.controller_metrics (
            metric_id SERIAL PRIMARY KEY,
            metric_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            controller_ip CIDR,
            metric_name VARCHAR(100) NOT NULL,
            metric_value NUMERIC NOT NULL,
            metadata JSONB
        );
    """)

def get_active_controllers(cur):
    """Retrieve distinct controller IPs from the door table."""
    cur.execute("SELECT DISTINCT controller_ip FROM door_controller.door WHERE controller_ip IS NOT NULL;")
    return [row[0] for row in cur.fetchall()]

def get_active_fobs(cur):
    """Retrieve all active fob IDs in the system."""
    cur.execute("SELECT distinct fob_id FROM key_fobs.keyfobs;")
    return [row[0] for row in cur.fetchall()]

def get_expected_permissions(cur, fob_id, controller_ip):
    """Get the expected permissions for a fob from f_get_permissions function."""
    cur.execute("""
        SELECT door_no, allow 
        FROM key_fobs.f_get_permissions(%s, %s::cidr, NOW()::time, CURRENT_DATE);
    """, (fob_id, f"{controller_ip}/32"))
    return {row[0]: bool(row[1]) for row in cur.fetchall()}

def record_metric(cur, controller_ip, name, value, metadata=None):
    """Insert a single metric row into the database."""
    cur.execute("""
        INSERT INTO door_controller.controller_metrics (controller_ip, metric_name, metric_value, metadata)
        VALUES (%s, %s, %s, %s);
    """, (controller_ip, name, value, Json(metadata) if metadata else None))

def main():
    parser = argparse.ArgumentParser(description="Door Controller Observability Metrics Collector")
    parser.add_argument("--sample-size", type=int, default=None, help="Minimum number of fobs to audit")
    parser.add_argument("--sample-percent", type=float, default=None, help="Percentage of total fobs to audit")
    args = parser.parse_args()

    log_info("Starting door controller metrics collection...")

    config = load_config()
    settings = config.get('settings', {})
    conn_str = settings.get('postgres_connect_string')
    username = settings.get('username')
    password = settings.get('password')
    urls = settings.get('urls', [])

    # Resolve sample parameters: CLI parameter takes highest priority, then config settings, then default fallback values
    cli_sample_size = args.sample_size
    cli_sample_percent = args.sample_percent

    config_sample_size = settings.get('metrics_sample_size')
    config_sample_percent = settings.get('metrics_sample_percent')

    sample_size = cli_sample_size if cli_sample_size is not None else (config_sample_size if config_sample_size is not None else 20)
    sample_percent = cli_sample_percent if cli_sample_percent is not None else (config_sample_percent if config_sample_percent is not None else 5.0)

    if not conn_str:
        log_error("postgres_connect_string not found in configuration. Exiting.")
        sys.exit(1)

    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
    except Exception as e:
        log_error(f"Failed to connect to PostgreSQL database: {e}")
        sys.exit(1)

    try:
        ensure_metrics_table_exists(cur)
        conn.commit()

        active_controllers = get_active_controllers(cur)
        active_fobs = get_active_fobs(cur)

        # 1. Record Database-Only Views Metrics
        # Missing Assigned Fobs View Metrics
        cur.execute("""
            SELECT controller_ip, count(*) 
            FROM door_controller.vext_system_missing_assigned_fobs 
            GROUP BY controller_ip;
        """)
        missing_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Unassigned Fobs View Metrics
        cur.execute("""
            SELECT controller_ip, count(*) 
            FROM door_controller.vext_system_unassigned_fobs 
            GROUP BY controller_ip;
        """)
        unassigned_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Record DB-only metrics for each active controller
        for controller_ip in active_controllers:
            ip_str = str(controller_ip)
            m_count = missing_counts.get(controller_ip, 0)
            u_count = unassigned_counts.get(controller_ip, 0)
            record_metric(cur, ip_str, 'missing_assigned_fobs_count', m_count)
            record_metric(cur, ip_str, 'unassigned_fobs_count', u_count)

        # 2. Select statistical sample of active fobs to audit
        total_fobs = len(active_fobs)
        sample_count = max(sample_size, int(total_fobs * (sample_percent / 100.0)))
        sample_count = min(sample_count, total_fobs)

        if sample_count > 0:
            audited_sample = random.sample(active_fobs, sample_count)
        else:
            audited_sample = []

        log_info(f"Auditing a random sample of {len(audited_sample)} fobs out of {total_fobs} total assigned fobs.")

        # 3. Query controllers and audit sample fobs
        for url in urls:
            parsed = urllib.parse.urlparse(url)
            controller_ip = parsed.hostname
            if not controller_ip:
                # Fallback if no schema is parsed
                controller_ip = url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]

            log_info(f"Auditing controller {url} (IP: {controller_ip})")

            audited_fobs_count = 0
            mismatched_permissions_count = 0
            missing_fobs_count = 0
            controller_online = 1

            mismatched_fob_ids = []
            missing_fob_ids = []

            try:
                dm = DataManager(url, username, password)
                # Test connectivity
                nav = dm.navigate()
                if not nav or nav.status_code != 200:
                    raise Exception("Failed to navigate to controller dashboard.")

                for fob_id in audited_sample:
                    audited_fobs_count += 1
                    try:
                        record_id = dm.get_record_id(fob_id)
                        if record_id is None:
                            missing_fobs_count += 1
                            mismatched_permissions_count += 1
                            missing_fob_ids.append(fob_id)
                            continue

                        # Fetch actual permissions from controller
                        actual_rows = dm.get_permissions_record(record_id)
                        actual_perms = {}
                        if actual_rows:
                            for row in actual_rows:
                                door_name = row[2]
                                digits = ''.join(c for c in door_name if c.isdigit())
                                door_no = int(digits) if digits else None
                                allow = (row[3] == "Allow")
                                if door_no is not None:
                                    actual_perms[door_no] = allow

                        # Fetch expected permissions from Postgres
                        expected_perms = get_expected_permissions(cur, fob_id, controller_ip)

                        # Compare permissions across all 4 doors
                        mismatch = False
                        for door_no in (1, 2, 3, 4):
                            act = actual_perms.get(door_no, False)
                            exp = expected_perms.get(door_no, False)
                            if act != exp:
                                mismatch = True
                                break

                        if mismatch:
                            mismatched_permissions_count += 1
                            mismatched_fob_ids.append(fob_id)

                    except Exception as e:
                        log_error(f"Error auditing Fob {fob_id} on {url}: {e}")
                        mismatched_permissions_count += 1
                        mismatched_fob_ids.append(fob_id)

            except Exception as e:
                log_error(f"Controller {url} is offline or returned errors: {e}")
                controller_online = 0

            # Calculate rates
            if audited_fobs_count > 0:
                mismatch_rate = mismatched_permissions_count / audited_fobs_count
            else:
                mismatch_rate = 0.0
            integrity_score = 1.0 - mismatch_rate

            # Record controller metrics
            record_metric(cur, controller_ip, 'controller_online', controller_online)
            
            if controller_online == 1:
                metadata = {
                    'audited_fob_ids': audited_sample,
                    'mismatched_fob_ids': mismatched_fob_ids,
                    'missing_fob_ids': missing_fob_ids
                }
                record_metric(cur, controller_ip, 'audited_fobs_count', audited_fobs_count)
                record_metric(cur, controller_ip, 'mismatched_permissions_count', mismatched_permissions_count)
                record_metric(cur, controller_ip, 'missing_fobs_count', missing_fobs_count)
                record_metric(cur, controller_ip, 'mismatch_rate', mismatch_rate, metadata)
                record_metric(cur, controller_ip, 'integrity_score', integrity_score, metadata)

        conn.commit()
        log_info("Metrics collection successfully completed and recorded.")

    except Exception as e:
        conn.rollback()
        log_error(f"Failed to collect and record metrics: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
