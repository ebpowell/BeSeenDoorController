-- get the permission change schedule for a given date 

create or replace function key_fobs.f_get_runtimes(p_date DATE, p_controller_ip CIDR)
returns table (run_times TIME,
				controller_ip CIDR)
language sql
as
$$

		with rule_dates AS
		(
			select distinct start_time, end_time, d.controller_ip,
			to_date(concat(gp.start_day_of_month::text, '-', gp.start_month::text, '-', date_part('year'::text, now())::text), 'DD-MM-YYYY'::text) AS start_date,
    		to_date(concat(gp.end_day_of_month::text, '-', gp.end_month::text, '-', date_part('year'::text, now())::text), 'DD-MM-YYYY'::text) AS end_date
			from key_fobs.group_permissions gp
			inner join door_controller.door d 
			on gp.door_id = d.door_id 
			where gp.controller_ip = p_controller_ip
			and gp.allow = true
		), runtime as 
		(
		select distinct start_time runtime, rd.controller_ip
		from rule_dates rd 
		where start_date<= p_date
		and end_date >= p_date
		and controller_ip = p_controller_ip
		union
		select distinct end_time runtime, rd.controller_ip
		from rule_dates rd	
		where start_date<= p_date
		and end_date >= p_date
		and controller_ip = p_controller_ip
		)
		select distinct runtime, rt.controller_ip from runtime rt
		order by runtime asc;
$$;

SELECT * FROM key_fobs.f_get_runtimes(CURRENT_DATE);

