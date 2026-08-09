drop view door_controller.v_export_keyswipe_validation;
create or replace view door_controller.v_export_keyswipe_validation as
with input_data as 
(
	select fob_id::int,concat(split_part(door_controller_ip,'://', 2),'/32')::cidr cidr, swipe_timestamp::time swipe_time, swipe_timestamp::date swipe_date, status, door 
	from door_controller.t_keyswipes
	where status not like 'Remo%'
	and swipe_timestamp::date > '2026-01-01'
)
select i.fob_id,  o.last_name, d.door_desc, status, swipe_time, swipe_date, key_fobs.f_get_permissions(i.fob_id, i.door ,cidr , swipe_time, swipe_date ) perm_val,
case when key_fobs.f_get_permissions(i.fob_id, i.door ,cidr , swipe_time, swipe_date ) = 1 and i.status = 'Allow' then 'Valid'
when key_fobs.f_get_permissions(i.fob_id, i.door ,cidr , swipe_time, swipe_date ) = 0 and i.status = 'Forbid' then 'Valid'
else 'Invalid'
end as denial_state
from input_data i
full outer join key_fobs.keyfobs k  
on i.fob_id = k.fob_id 
inner join key_fobs.properties p 
on k.property_id = p.property_id 
inner join key_fobs.owners o 
on o.property_id =p.property_id
inner join door_controller.door d  
on i.door = d.door_no 
and i.cidr = d.controller_ip 
where swipe_date > '2026-01-01'
union
select i.fob_id,  'Unknown' last_name, d.door_desc, status, swipe_time, swipe_date, 0 perm_val, 'Valid' denial_state
from input_data i
inner join door_controller.door d
on d.door_no = i.door
and d.controller_ip = i.cidr
where i.fob_id not in (select fob_id from key_fobs.keyfobs)
order by swipe_date desc, swipe_time asc;