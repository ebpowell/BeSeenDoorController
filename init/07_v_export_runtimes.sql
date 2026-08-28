drop view if exists key_fobs.v_export_runtimes;
create or replace view key_fobs.v_export_runtimes as
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
                                    d.controller_ip,
                                    gp.group_id 
                                FROM permissions p
                                JOIN key_fobs.group_permissions gp 
                                  ON p.group_id = gp.group_id
                                JOIN door_controller.door d 
                                  ON gp.door_id = d.door_id
                                WHERE gp.allow = true
                            )
                            select distinct controller_ip, atm.start_time, end_time,atm.start_date, atm.end_date, group_id
                            FROM allow_times atm
--                            union
--                            select distinct controller_ip, atm.end_time  run_time,atm.start_date run_time, atm.end_date, group_id
--                            FROM allow_times atm;
						
