select count(*) from system_swipes ss where door_controller= 'http://69.21.119.148';
select MAX(record_id) - min(record_id) from system_swipes ss where door_controller =  'http://69.21.119.148' ;
select min(timestamp) from system_swipes ss where ss.door_controller = 'http://69.21.119.148' ;
select min(record_id) from system_swipes ss where ss.door_controller = 'http://69.21.119.148' ;


--Find uplicates
select count(*), record_id from system_swipes ss group BY record_id;

--Find the time a fob spent at the pool (door 3 or Door 4)
select count(*) from (select distinct * from system_swipes ss where door_controller= 'http://69.21.119.148')

--Extrasct the unique records into a working dataset
create TABLE keyswipes as select distinct * from system_swipes ss;
select count(*) from keyswipes;

--Now we cna start analyzing....
select count(*) from system_fobs;
select max(record_id) from system_fobs;

select distinct * from system_fobs;

drop view v_access_list;
create view v_access_list as
select distinct record_id, fob_id, 
CASE 
	when substr(controller, length(controller)+1, -3) == '148' then 1
	else 2
	end as door_controller,
	cast(status as text) status, 
	substr(door,2 ,1) door_id,
	substr(controller, length(controller)+1, -3) as controller_ip
from access_control ac ;


