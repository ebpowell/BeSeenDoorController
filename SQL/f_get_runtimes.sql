-- get the permission change schedule for a given date 

create or replace function key_fobs.f_get_runtimes(p_date DATE)
returns table (run_times TIME,
				controller_ip CIDR)
language sql
as
$$
		with runtime as (
		select distinct start_time runtime, vad.controller_ip
		from key_fobs.vint_acl_data vad 
		where start_date<= p_date
		and end_date >= p_date
		union
		select distinct end_time runtime, vad.controller_ip
		from key_fobs.vint_acl_data vad 
		where start_date<= p_date
		and end_date >= p_date
		)
		select distinct runtime, rt.controller_ip from runtime rt
		order by runtime asc;
$$;

SELECT * FROM key_fobs.f_get_runtimes(CURRENT_DATE);

