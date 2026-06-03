--
-- PostgreSQL database dump
--

\restrict ZDl46PCdkryVDzjFgFtQwdH4qjLytXEo48cVOyUniWtoKAqKF0CZnhIy8rRLlwO

-- Dumped from database version 16.14
-- Dumped by pg_dump version 18.4 (Ubuntu 18.4-0ubuntu0.26.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: dataload; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA dataload;


ALTER SCHEMA dataload OWNER TO wentworth_user;

--
-- Name: door_controller; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA door_controller;


ALTER SCHEMA door_controller OWNER TO wentworth_user;

--
-- Name: finances; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA finances;


ALTER SCHEMA finances OWNER TO wentworth_user;

--
-- Name: key_fobs; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA key_fobs;


ALTER SCHEMA key_fobs OWNER TO wentworth_user;

--
-- Name: pool_monitor; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA pool_monitor;


ALTER SCHEMA pool_monitor OWNER TO wentworth_user;

--
-- Name: webpage; Type: SCHEMA; Schema: -; Owner: wentworth_user
--

CREATE SCHEMA webpage;


ALTER SCHEMA webpage OWNER TO wentworth_user;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_list_from_controller_slop; Type: TABLE; Schema: dataload; Owner: wentworth_user
--

CREATE TABLE dataload.access_list_from_controller_slop (
    record_id integer,
    fob_id integer,
    door_controller integer,
    status text,
    door_id integer,
    controller_ip cidr,
    record_time timestamp with time zone
);


ALTER TABLE dataload.access_list_from_controller_slop OWNER TO wentworth_user;

--
-- Name: fobs_slop; Type: TABLE; Schema: dataload; Owner: wentworth_user
--

CREATE TABLE dataload.fobs_slop (
    record_id integer,
    fob_id integer,
    controller_ip cidr,
    record_time timestamp with time zone
);


ALTER TABLE dataload.fobs_slop OWNER TO wentworth_user;

--
-- Name: fobs_slop_record_id_seq; Type: SEQUENCE; Schema: dataload; Owner: wentworth_user
--

CREATE SEQUENCE dataload.fobs_slop_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE dataload.fobs_slop_record_id_seq OWNER TO wentworth_user;

--
-- Name: fobs_slop_record_id_seq; Type: SEQUENCE OWNED BY; Schema: dataload; Owner: wentworth_user
--

ALTER SEQUENCE dataload.fobs_slop_record_id_seq OWNED BY dataload.fobs_slop.record_id;


--
-- Name: t_keyswipes_slop; Type: TABLE; Schema: dataload; Owner: wentworth_user
--

CREATE TABLE dataload.t_keyswipes_slop (
    record_id bigint,
    fob_id bigint,
    status text,
    door integer,
    swipe_timestamp text,
    door_controller_ip text
);


ALTER TABLE dataload.t_keyswipes_slop OWNER TO wentworth_user;

--
-- Name: door; Type: TABLE; Schema: door_controller; Owner: wentworth_user
--

CREATE TABLE door_controller.door (
    door_id integer NOT NULL,
    door_no integer,
    door_desc character varying,
    controller integer,
    controller_ip cidr
);


ALTER TABLE door_controller.door OWNER TO wentworth_user;

--
-- Name: v_fob_slop_append; Type: VIEW; Schema: dataload; Owner: wentworth_user
--

CREATE VIEW dataload.v_fob_slop_append AS
 SELECT DISTINCT fs.record_id,
    fs.fob_id,
    fs.record_time,
    d.controller AS controller_id
   FROM (dataload.fobs_slop fs
     JOIN door_controller.door d ON (((fs.controller_ip)::inet = (d.controller_ip)::inet)));


ALTER VIEW dataload.v_fob_slop_append OWNER TO wentworth_user;

--
-- Name: access_list_from_controller; Type: TABLE; Schema: door_controller; Owner: wentworth_user
--

CREATE TABLE door_controller.access_list_from_controller (
    record_id integer,
    fob_id integer,
    status text,
    door_id integer,
    controller_ip cidr,
    record_time timestamp with time zone,
    acl_record_id integer NOT NULL
);


ALTER TABLE door_controller.access_list_from_controller OWNER TO wentworth_user;

--
-- Name: access_list_from_controller_acl_record_id_seq; Type: SEQUENCE; Schema: door_controller; Owner: wentworth_user
--

CREATE SEQUENCE door_controller.access_list_from_controller_acl_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE door_controller.access_list_from_controller_acl_record_id_seq OWNER TO wentworth_user;

--
-- Name: access_list_from_controller_acl_record_id_seq; Type: SEQUENCE OWNED BY; Schema: door_controller; Owner: wentworth_user
--

ALTER SEQUENCE door_controller.access_list_from_controller_acl_record_id_seq OWNED BY door_controller.access_list_from_controller.acl_record_id;


--
-- Name: system_fobs; Type: TABLE; Schema: door_controller; Owner: wentworth_user
--

CREATE TABLE door_controller.system_fobs (
    fob_record_id integer NOT NULL,
    fob_id integer NOT NULL,
    controller_id integer,
    record_time timestamp with time zone NOT NULL,
    controller integer,
    controller_ip cidr,
    controller_record_id integer
);


ALTER TABLE door_controller.system_fobs OWNER TO wentworth_user;

--
-- Name: fobs_record_id_seq; Type: SEQUENCE; Schema: door_controller; Owner: wentworth_user
--

CREATE SEQUENCE door_controller.fobs_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE door_controller.fobs_record_id_seq OWNER TO wentworth_user;

--
-- Name: fobs_record_id_seq; Type: SEQUENCE OWNED BY; Schema: door_controller; Owner: wentworth_user
--

ALTER SEQUENCE door_controller.fobs_record_id_seq OWNED BY door_controller.system_fobs.fob_record_id;


--
-- Name: t_keyswipes; Type: TABLE; Schema: door_controller; Owner: wentworth_user
--

CREATE TABLE door_controller.t_keyswipes (
    record_id bigint,
    fob_id bigint,
    status text,
    door integer,
    swipe_timestamp text,
    door_controller_ip text
);


ALTER TABLE door_controller.t_keyswipes OWNER TO wentworth_user;

--
-- Name: v_keyswipes; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_keyswipes AS
 SELECT tks.record_id,
    tks.fob_id,
    tks.status,
    tks.door,
    d.door_desc,
    to_timestamp(tks.swipe_timestamp, 'YYYY-MM-DD HH24:MI:SS'::text) AS swipe_time,
    d.controller AS door_controller,
    d.controller_ip
   FROM (door_controller.t_keyswipes tks
     JOIN door_controller.door d ON ((((d.controller_ip)::inet = ((ltrim(tks.door_controller_ip, 'http://'::text))::cidr)::inet) AND (d.door_no = tks.door))))
  ORDER BY (to_timestamp(tks.swipe_timestamp, 'YYYY-MM-DD HH24:MI:SS'::text)) DESC;


ALTER VIEW door_controller.v_keyswipes OWNER TO wentworth_user;

--
-- Name: group_permissions; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.group_permissions (
    perm_id integer NOT NULL,
    start_date date,
    end_date date,
    start_time time without time zone,
    end_time time without time zone,
    door_id integer,
    allow boolean,
    group_id integer
);


ALTER TABLE key_fobs.group_permissions OWNER TO wentworth_user;

--
-- Name: groups; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.groups (
    group_id integer NOT NULL,
    name character varying
);


ALTER TABLE key_fobs.groups OWNER TO wentworth_user;

--
-- Name: keyfobs; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.keyfobs (
    keyfob_id integer NOT NULL,
    property_id integer NOT NULL,
    fob_id integer NOT NULL
);


ALTER TABLE key_fobs.keyfobs OWNER TO wentworth_user;

--
-- Name: owners; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.owners (
    owner_id integer NOT NULL,
    first_name character varying,
    last_name character varying,
    property_id integer NOT NULL
);


ALTER TABLE key_fobs.owners OWNER TO wentworth_user;

--
-- Name: properties; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.properties (
    property_id integer NOT NULL,
    address character varying NOT NULL,
    knox_co_lot_id integer
);


ALTER TABLE key_fobs.properties OWNER TO wentworth_user;

--
-- Name: property_group_permissions; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.property_group_permissions (
    prop_grp_id integer NOT NULL,
    property_id integer NOT NULL,
    group_id integer NOT NULL
);


ALTER TABLE key_fobs.property_group_permissions OWNER TO wentworth_user;

--
-- Name: v_2025_fob_list; Type: VIEW; Schema: key_fobs; Owner: wentworth_user
--

CREATE VIEW key_fobs.v_2025_fob_list AS
 SELECT DISTINCT g.name AS group_name,
    o.last_name,
    p.address,
    k.fob_id
   FROM (((((key_fobs.groups g
     JOIN key_fobs.group_permissions gp ON ((g.group_id = gp.group_id)))
     JOIN key_fobs.property_group_permissions pgp ON ((g.group_id = pgp.group_id)))
     JOIN key_fobs.properties p ON ((p.property_id = pgp.property_id)))
     JOIN key_fobs.owners o ON ((o.property_id = p.property_id)))
     JOIN key_fobs.keyfobs k ON ((p.property_id = k.property_id)))
  WHERE ((gp.allow = true) AND (g.group_id = 7) AND ((p.address)::text !~~ '%429 Gwin%'::text))
  ORDER BY p.address, o.last_name;


ALTER VIEW key_fobs.v_2025_fob_list OWNER TO wentworth_user;

--
-- Name: v_pool_annual_family_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_pool_annual_family_usage AS
 WITH family_usage AS (
         WITH pool_swipes AS (
                 SELECT count(*) AS swipe_count,
                    vfl.last_name,
                    vfl.address,
                    EXTRACT(year FROM vk.swipe_time) AS year
                   FROM (door_controller.v_keyswipes vk
                     JOIN key_fobs.v_2025_fob_list vfl ON ((vk.fob_id = vfl.fob_id)))
                  WHERE ((vk.door_desc)::text ~~ 'Pool%'::text)
                  GROUP BY vfl.last_name, (EXTRACT(year FROM vk.swipe_time)), vfl.address
                  ORDER BY (EXTRACT(year FROM vk.swipe_time)) DESC
                )
         SELECT pool_swipes.swipe_count,
            pool_swipes.last_name,
            pool_swipes.address,
            pool_swipes.year
           FROM pool_swipes
          WHERE (pool_swipes.swipe_count > 10)
        )
 SELECT count(*) AS count,
    year
   FROM family_usage
  GROUP BY year;


ALTER VIEW door_controller.v_pool_annual_family_usage OWNER TO wentworth_user;

--
-- Name: v_pool_daily_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_pool_daily_usage AS
 SELECT date(swipe_time) AS record_date,
    count(*) AS record_count
   FROM door_controller.v_keyswipes tks
  WHERE ((door_desc)::text ~~ 'Pool%'::text)
  GROUP BY (date(swipe_time))
  ORDER BY (date(swipe_time));


ALTER VIEW door_controller.v_pool_daily_usage OWNER TO wentworth_user;

--
-- Name: v_pool_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_pool_usage AS
 WITH usage_data AS (
         WITH family_year AS (
                 WITH family_usage AS (
                         WITH court_swipes AS (
                                 SELECT count(*) AS swipe_count,
                                    vfl.address
                                   FROM ((door_controller.v_keyswipes vk
                                     JOIN key_fobs.v_2025_fob_list vfl ON ((vk.fob_id = vfl.fob_id)))
                                     JOIN door_controller.door d ON (((d.door_no = vk.door) AND (d.controller = vk.door_controller))))
                                  WHERE ((d.door_desc)::text ~~ 'Pool%'::text)
                                  GROUP BY vfl.last_name, vfl.address
                                )
                         SELECT court_swipes.swipe_count,
                            court_swipes.address
                           FROM court_swipes
                          ORDER BY court_swipes.swipe_count
                        )
                 SELECT family_usage.address,
                    family_usage.swipe_count
                   FROM family_usage
                  GROUP BY family_usage.swipe_count, family_usage.address
                ), total_swipes AS (
                 SELECT count(*) AS tot_swipe_count
                   FROM ((door_controller.v_keyswipes vks
                     JOIN door_controller.door d ON (((vks.door_controller = d.controller) AND (vks.door = d.door_no))))
                     JOIN key_fobs.v_2025_fob_list vfl ON ((vks.fob_id = vfl.fob_id)))
                  WHERE ((d.door_desc)::text ~~ 'Pool%'::text)
                )
         SELECT round((((fy.swipe_count)::numeric / (a.tot_swipe_count)::numeric) * (100)::numeric), 1) AS percent_swipes,
            fy.address
           FROM total_swipes a,
            family_year fy
        )
 SELECT sum(usage_data.percent_swipes) AS swipe_percent,
    'Other'::character varying AS prop_address
   FROM usage_data
  WHERE (usage_data.percent_swipes <= (2)::numeric)
UNION
 SELECT usage_data.percent_swipes AS swipe_percent,
    usage_data.address AS prop_address
   FROM usage_data
  WHERE (usage_data.percent_swipes > (2)::numeric);


ALTER VIEW door_controller.v_pool_usage OWNER TO wentworth_user;

--
-- Name: v_pool_usage_sats; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_pool_usage_sats AS
 WITH family_year AS (
         WITH family_usage AS (
                 WITH court_swipes AS (
                         SELECT count(*) AS swipe_count,
                            vfl.last_name,
                            vfl.address,
                            EXTRACT(year FROM vk.swipe_time) AS year
                           FROM ((door_controller.v_keyswipes vk
                             JOIN key_fobs.v_2025_fob_list vfl ON ((vk.fob_id = vfl.fob_id)))
                             JOIN door_controller.door d ON (((d.door_no = vk.door) AND (d.controller = vk.door_controller))))
                          WHERE ((d.door_desc)::text ~~ 'Pool%'::text)
                          GROUP BY vfl.last_name, (EXTRACT(year FROM vk.swipe_time)), vfl.address
                          ORDER BY (EXTRACT(year FROM vk.swipe_time)) DESC
                        )
                 SELECT court_swipes.swipe_count,
                    court_swipes.last_name,
                    court_swipes.address,
                    court_swipes.year
                   FROM court_swipes
                  ORDER BY court_swipes.year DESC, court_swipes.swipe_count
                )
         SELECT family_usage.address,
            family_usage.swipe_count,
            family_usage.year
           FROM family_usage
          GROUP BY family_usage.year, family_usage.swipe_count, family_usage.address
        ), annual_swipes AS (
         SELECT count(*) AS annual_swipe_count,
            EXTRACT(year FROM vks.swipe_time) AS year
           FROM (door_controller.v_keyswipes vks
             JOIN door_controller.door d ON (((vks.door_controller = d.controller) AND (vks.door = d.door_no))))
          WHERE ((d.door_desc)::text ~~ 'Pool%'::text)
          GROUP BY (EXTRACT(year FROM vks.swipe_time))
        )
 SELECT round((((fy.swipe_count)::numeric / (a.annual_swipe_count)::numeric) * (100)::numeric), 1) AS percent_swipes,
    fy.year,
    fy.address
   FROM (annual_swipes a
     JOIN family_year fy ON ((a.year = fy.year)));


ALTER VIEW door_controller.v_pool_usage_sats OWNER TO wentworth_user;

--
-- Name: v_tannis_court_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_tannis_court_usage AS
 WITH usage_data AS (
         WITH family_year AS (
                 WITH family_usage AS (
                         WITH court_swipes AS (
                                 SELECT count(*) AS swipe_count,
                                    vfl.address
                                   FROM ((door_controller.v_keyswipes vk
                                     JOIN key_fobs.v_2025_fob_list vfl ON ((vk.fob_id = vfl.fob_id)))
                                     JOIN door_controller.door d ON (((d.door_no = vk.door) AND (d.controller = vk.door_controller))))
                                  WHERE ((d.door_desc)::text ~~ 'Tennis%'::text)
                                  GROUP BY vfl.last_name, vfl.address
                                )
                         SELECT court_swipes.swipe_count,
                            court_swipes.address
                           FROM court_swipes
                          ORDER BY court_swipes.swipe_count
                        )
                 SELECT family_usage.address,
                    family_usage.swipe_count
                   FROM family_usage
                  GROUP BY family_usage.swipe_count, family_usage.address
                ), total_swipes AS (
                 SELECT count(*) AS tot_swipe_count
                   FROM ((door_controller.v_keyswipes vks
                     JOIN door_controller.door d ON (((vks.door_controller = d.controller) AND (vks.door = d.door_no))))
                     JOIN key_fobs.v_2025_fob_list vfl ON ((vks.fob_id = vfl.fob_id)))
                  WHERE ((d.door_desc)::text ~~ 'Tennis%'::text)
                )
         SELECT round((((fy.swipe_count)::numeric / (a.tot_swipe_count)::numeric) * (100)::numeric), 1) AS percent_swipes,
            fy.address
           FROM total_swipes a,
            family_year fy
        )
 SELECT sum(usage_data.percent_swipes) AS swipe_percent,
    'Other'::character varying AS prop_address
   FROM usage_data
  WHERE (usage_data.percent_swipes <= (2)::numeric)
UNION
 SELECT usage_data.percent_swipes AS swipe_percent,
    usage_data.address AS prop_address
   FROM usage_data
  WHERE (usage_data.percent_swipes > (2)::numeric);


ALTER VIEW door_controller.v_tannis_court_usage OWNER TO wentworth_user;

--
-- Name: v_tennis_annual_family_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_tennis_annual_family_usage AS
 WITH family_usage AS (
         WITH tennis_swipes AS (
                 SELECT count(*) AS swipe_count,
                    vfl.last_name,
                    vfl.address,
                    EXTRACT(year FROM vk.swipe_time) AS year
                   FROM (door_controller.v_keyswipes vk
                     JOIN key_fobs.v_2025_fob_list vfl ON ((vk.fob_id = vfl.fob_id)))
                  WHERE ((vk.door_desc)::text ~~ 'Tennis%'::text)
                  GROUP BY vfl.last_name, (EXTRACT(year FROM vk.swipe_time)), vfl.address
                  ORDER BY (EXTRACT(year FROM vk.swipe_time)) DESC
                )
         SELECT tennis_swipes.swipe_count,
            tennis_swipes.last_name,
            tennis_swipes.address,
            tennis_swipes.year
           FROM tennis_swipes
          WHERE (tennis_swipes.swipe_count > 10)
        )
 SELECT count(*) AS count,
    year
   FROM family_usage
  GROUP BY year;


ALTER VIEW door_controller.v_tennis_annual_family_usage OWNER TO wentworth_user;

--
-- Name: v_tenniscourt_daily_usage; Type: VIEW; Schema: door_controller; Owner: wentworth_user
--

CREATE VIEW door_controller.v_tenniscourt_daily_usage AS
 SELECT date(swipe_time) AS record_date,
    count(*) AS record_count
   FROM door_controller.v_keyswipes tks
  WHERE ((door_desc)::text ~~ 'Tennis%'::text)
  GROUP BY (date(swipe_time))
  ORDER BY (date(swipe_time));


ALTER VIEW door_controller.v_tenniscourt_daily_usage OWNER TO wentworth_user;

--
-- Name: budget_categories_values_hist; Type: TABLE; Schema: finances; Owner: wentworth_user
--

CREATE TABLE finances.budget_categories_values_hist (
    record_id integer NOT NULL,
    category character varying,
    amount numeric,
    year integer
);


ALTER TABLE finances.budget_categories_values_hist OWNER TO wentworth_user;

--
-- Name: budget_categories_values_hist_record_id_seq; Type: SEQUENCE; Schema: finances; Owner: wentworth_user
--

CREATE SEQUENCE finances.budget_categories_values_hist_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE finances.budget_categories_values_hist_record_id_seq OWNER TO wentworth_user;

--
-- Name: budget_categories_values_hist_record_id_seq; Type: SEQUENCE OWNED BY; Schema: finances; Owner: wentworth_user
--

ALTER SEQUENCE finances.budget_categories_values_hist_record_id_seq OWNED BY finances.budget_categories_values_hist.record_id;


--
-- Name: users; Type: TABLE; Schema: key_fobs; Owner: wentworth_user
--

CREATE TABLE key_fobs.users (
    user_id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(20) DEFAULT 'operator'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE key_fobs.users OWNER TO wentworth_user;

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: key_fobs; Owner: wentworth_user
--

CREATE SEQUENCE key_fobs.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE key_fobs.users_user_id_seq OWNER TO wentworth_user;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: key_fobs; Owner: wentworth_user
--

ALTER SEQUENCE key_fobs.users_user_id_seq OWNED BY key_fobs.users.user_id;


--
-- Name: v_2025_homeowner_fob_list; Type: VIEW; Schema: key_fobs; Owner: wentworth_user
--

CREATE VIEW key_fobs.v_2025_homeowner_fob_list AS
 SELECT DISTINCT g.name AS group_name,
    o.last_name,
    p.address,
    k.fob_id
   FROM (((((key_fobs.groups g
     JOIN key_fobs.group_permissions gp ON ((g.group_id = gp.group_id)))
     JOIN key_fobs.property_group_permissions pgp ON ((g.group_id = pgp.group_id)))
     JOIN key_fobs.properties p ON ((p.property_id = pgp.property_id)))
     JOIN key_fobs.owners o ON ((o.property_id = p.property_id)))
     JOIN key_fobs.keyfobs k ON ((p.property_id = k.property_id)))
  WHERE ((gp.allow = true) AND (g.group_id = 7))
  ORDER BY p.address, o.last_name;


ALTER VIEW key_fobs.v_2025_homeowner_fob_list OWNER TO wentworth_user;

--
-- Name: v_group_permissions; Type: VIEW; Schema: key_fobs; Owner: wentworth_user
--

CREATE VIEW key_fobs.v_group_permissions AS
 SELECT g.name,
    d.door_desc,
    gp.start_date,
    gp.end_date,
    gp.start_time,
    gp.end_time
   FROM ((key_fobs.groups g
     JOIN key_fobs.group_permissions gp ON ((g.group_id = gp.group_id)))
     JOIN door_controller.door d ON ((d.door_id = gp.door_id)))
  WHERE (gp.allow = true);


ALTER VIEW key_fobs.v_group_permissions OWNER TO wentworth_user;

--
-- Name: v_special_access_fobs; Type: VIEW; Schema: key_fobs; Owner: wentworth_user
--

CREATE VIEW key_fobs.v_special_access_fobs AS
 SELECT DISTINCT g.name AS group_name,
    o.last_name,
    k.fob_id
   FROM (((((key_fobs.groups g
     JOIN key_fobs.group_permissions gp ON ((g.group_id = gp.group_id)))
     JOIN key_fobs.property_group_permissions pgp ON ((g.group_id = pgp.group_id)))
     JOIN key_fobs.properties p ON ((p.property_id = pgp.property_id)))
     JOIN key_fobs.owners o ON ((o.property_id = p.property_id)))
     JOIN key_fobs.keyfobs k ON ((p.property_id = k.property_id)))
  WHERE ((gp.allow = true) AND (g.group_id <> 7));


ALTER VIEW key_fobs.v_special_access_fobs OWNER TO wentworth_user;

--
-- Name: v_system_fobids_to_remove; Type: VIEW; Schema: key_fobs; Owner: wentworth_user
--

CREATE VIEW key_fobs.v_system_fobids_to_remove AS
 WITH system_fobs AS (
         SELECT DISTINCT access_list_from_controller.fob_id
           FROM door_controller.access_list_from_controller
        )
 SELECT sf.fob_id
   FROM (key_fobs.keyfobs k
     FULL JOIN system_fobs sf ON ((sf.fob_id = k.fob_id)))
  WHERE (k.fob_id IS NULL);


ALTER VIEW key_fobs.v_system_fobids_to_remove OWNER TO wentworth_user;

--
-- Name: pool_monitors; Type: TABLE; Schema: pool_monitor; Owner: wentworth_user
--

CREATE TABLE pool_monitor.pool_monitors (
    monitor_id integer NOT NULL,
    frist_name character varying,
    last_name character varying,
    property_id integer
);


ALTER TABLE pool_monitor.pool_monitors OWNER TO wentworth_user;

--
-- Name: newtable_monitor_id_seq; Type: SEQUENCE; Schema: pool_monitor; Owner: wentworth_user
--

CREATE SEQUENCE pool_monitor.newtable_monitor_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE pool_monitor.newtable_monitor_id_seq OWNER TO wentworth_user;

--
-- Name: newtable_monitor_id_seq; Type: SEQUENCE OWNED BY; Schema: pool_monitor; Owner: wentworth_user
--

ALTER SEQUENCE pool_monitor.newtable_monitor_id_seq OWNED BY pool_monitor.pool_monitors.monitor_id;


--
-- Name: payroll_date; Type: TABLE; Schema: pool_monitor; Owner: wentworth_user
--

CREATE TABLE pool_monitor.payroll_date (
    pr_date_id integer NOT NULL,
    payroll_date date
);


ALTER TABLE pool_monitor.payroll_date OWNER TO wentworth_user;

--
-- Name: payroll_date_pr_date_id_seq; Type: SEQUENCE; Schema: pool_monitor; Owner: wentworth_user
--

CREATE SEQUENCE pool_monitor.payroll_date_pr_date_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE pool_monitor.payroll_date_pr_date_id_seq OWNER TO wentworth_user;

--
-- Name: payroll_date_pr_date_id_seq; Type: SEQUENCE OWNED BY; Schema: pool_monitor; Owner: wentworth_user
--

ALTER SEQUENCE pool_monitor.payroll_date_pr_date_id_seq OWNED BY pool_monitor.payroll_date.pr_date_id;


--
-- Name: pool_monitor_schedule; Type: TABLE; Schema: pool_monitor; Owner: wentworth_user
--

CREATE TABLE pool_monitor.pool_monitor_schedule (
    schedule_date character varying(50),
    first_name character varying(50)
);


ALTER TABLE pool_monitor.pool_monitor_schedule OWNER TO wentworth_user;

--
-- Name: v_monitor_fobs; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_monitor_fobs AS
 SELECT kf.fob_id,
    pm.frist_name AS first_name,
    pm.last_name
   FROM (pool_monitor.pool_monitors pm
     JOIN key_fobs.keyfobs kf ON ((pm.property_id = kf.property_id)));


ALTER VIEW pool_monitor.v_monitor_fobs OWNER TO wentworth_user;

--
-- Name: v_fob_schedule; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_fob_schedule AS
 SELECT mf.fob_id,
    pms.schedule_date,
    mf.first_name,
    mf.last_name
   FROM (pool_monitor.pool_monitor_schedule pms
     JOIN pool_monitor.v_monitor_fobs mf ON (((mf.first_name)::text = (pms.first_name)::text)));


ALTER VIEW pool_monitor.v_fob_schedule OWNER TO wentworth_user;

--
-- Name: v_pool_duty; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_pool_duty AS
 WITH potential_swipes AS (
         SELECT vfs_1.fob_id,
            to_timestamp((vfs_1.schedule_date)::text, 'MM/DD/YYYY'::text) AS schedule_date
           FROM (door_controller.v_keyswipes vk
             JOIN pool_monitor.v_fob_schedule vfs_1 ON ((vk.fob_id = vfs_1.fob_id)))
          WHERE ((vk.swipe_time > to_timestamp(concat(vfs_1.schedule_date, ':18:00'), 'MM/DD/YYYY:HH24:MI'::text)) AND (vk.swipe_time < (to_timestamp(concat(vfs_1.schedule_date, ':10:00'), 'MM/DD/YYYY:HH24:MI'::text) + '1 day'::interval)) AND ((vk.door_desc)::text ~~ 'Pool%'::text))
        )
 SELECT DISTINCT (ps.schedule_date)::date AS schedule_date,
    vfs.first_name,
    vfs.last_name,
    (concat(EXTRACT(year FROM ps.schedule_date), '-', EXTRACT(month FROM ps.schedule_date), '-', '01'))::date AS payroll_date
   FROM (pool_monitor.v_fob_schedule vfs
     JOIN potential_swipes ps ON (((ps.fob_id = vfs.fob_id) AND (ps.schedule_date = to_timestamp((vfs.schedule_date)::text, 'MM/DD/YYY'::text)))))
  ORDER BY ((ps.schedule_date)::date);


ALTER VIEW pool_monitor.v_pool_duty OWNER TO wentworth_user;

--
-- Name: v_missed_days; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_missed_days AS
 SELECT p.schedule_date,
    p.first_name
   FROM (pool_monitor.pool_monitor_schedule p
     FULL JOIN pool_monitor.v_pool_duty v ON ((to_date((p.schedule_date)::text, 'MM/DD/YYYY'::text) = v.schedule_date)))
  WHERE ((v.first_name IS NULL) AND (to_date((p.schedule_date)::text, 'MM/DD/YYYY'::text) > to_date('5/17/2025'::text, 'MM/DD/YYYY'::text)));


ALTER VIEW pool_monitor.v_missed_days OWNER TO wentworth_user;

--
-- Name: v_payroll; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_payroll AS
 SELECT count(*) AS duty_days,
    concat(first_name, ' ', last_name) AS name,
    payroll_date
   FROM pool_monitor.v_pool_duty
  GROUP BY first_name, last_name, payroll_date
  ORDER BY payroll_date;


ALTER VIEW pool_monitor.v_payroll OWNER TO wentworth_user;

--
-- Name: v_payroll_checksum; Type: VIEW; Schema: pool_monitor; Owner: wentworth_user
--

CREATE VIEW pool_monitor.v_payroll_checksum AS
 SELECT sum(duty_days) AS sum,
    payroll_date
   FROM pool_monitor.v_payroll vp
  GROUP BY payroll_date;


ALTER VIEW pool_monitor.v_payroll_checksum OWNER TO wentworth_user;

--
-- Name: pool_events; Type: TABLE; Schema: public; Owner: wentworth_user
--

CREATE TABLE public.pool_events (
    eventid integer NOT NULL,
    event_date date,
    event_desc character varying
);


ALTER TABLE public.pool_events OWNER TO wentworth_user;

--
-- Name: pool_events_eventid_seq; Type: SEQUENCE; Schema: public; Owner: wentworth_user
--

CREATE SEQUENCE public.pool_events_eventid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pool_events_eventid_seq OWNER TO wentworth_user;

--
-- Name: pool_events_eventid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wentworth_user
--

ALTER SEQUENCE public.pool_events_eventid_seq OWNED BY public.pool_events.eventid;


--
-- Name: v_system_assigned_fob_compare; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_system_assigned_fob_compare AS
 WITH system_fob_list AS (
         SELECT DISTINCT system_fobs.fob_id,
            system_fobs.controller_id
           FROM door_controller.system_fobs
          ORDER BY system_fobs.fob_id
        )
 SELECT k.fob_id AS assigned_fob_id,
    fsl.fob_id AS sysem_fob_id,
    fsl.controller_id
   FROM (key_fobs.keyfobs k
     FULL JOIN system_fob_list fsl ON ((k.fob_id = fsl.fob_id)))
  ORDER BY k.fob_id;


ALTER VIEW public.v_system_assigned_fob_compare OWNER TO wentworth_user;

--
-- Name: v_error_fobid_on_single_controller; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_error_fobid_on_single_controller AS
 WITH controller_count AS (
         SELECT count(v_system_assigned_fob_compare.controller_id) AS controller_count,
            v_system_assigned_fob_compare.sysem_fob_id
           FROM public.v_system_assigned_fob_compare
          GROUP BY v_system_assigned_fob_compare.sysem_fob_id
        )
 SELECT sysem_fob_id
   FROM controller_count
  WHERE (controller_count = 1);


ALTER VIEW public.v_error_fobid_on_single_controller OWNER TO wentworth_user;

--
-- Name: v_error_detail_fobid_single_controller; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_error_detail_fobid_single_controller AS
 SELECT DISTINCT sc.sysem_fob_id,
    d.controller_ip
   FROM ((public.v_error_fobid_on_single_controller sc
     LEFT JOIN door_controller.system_fobs ac ON ((sc.sysem_fob_id = ac.fob_id)))
     LEFT JOIN door_controller.door d ON ((d.controller = ac.controller_id)))
  ORDER BY sc.sysem_fob_id;


ALTER VIEW public.v_error_detail_fobid_single_controller OWNER TO wentworth_user;

--
-- Name: v_fob_ids_to_remove; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_fob_ids_to_remove AS
 WITH controllers AS (
         SELECT DISTINCT door.controller,
            door.controller_ip
           FROM door_controller.door
        )
 SELECT DISTINCT vsafc.sysem_fob_id,
    vsafc.controller_id,
    d.controller_ip
   FROM (public.v_system_assigned_fob_compare vsafc
     JOIN controllers d ON ((d.controller = vsafc.controller_id)))
  WHERE (vsafc.assigned_fob_id IS NULL)
  ORDER BY vsafc.controller_id;


ALTER VIEW public.v_fob_ids_to_remove OWNER TO wentworth_user;

--
-- Name: v_fobcount_comparison; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_fobcount_comparison AS
 WITH fob_list AS (
         SELECT DISTINCT system_fobs.fob_id,
            system_fobs.controller_id
           FROM door_controller.system_fobs
          ORDER BY system_fobs.fob_id
        )
 SELECT count(fob_id) AS count,
    controller_id
   FROM fob_list
  GROUP BY controller_id;


ALTER VIEW public.v_fobcount_comparison OWNER TO wentworth_user;

--
-- Name: v_pool_event_attendance; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_pool_event_attendance AS
 WITH family_date AS (
         SELECT DISTINCT date(vk.swipe_time) AS event_date,
            vk.fob_id,
            pe.event_desc
           FROM (door_controller.v_keyswipes vk
             JOIN public.pool_events pe ON ((date(vk.swipe_time) = pe.event_date)))
          GROUP BY (date(vk.swipe_time)), vk.fob_id, pe.event_desc
        )
 SELECT count(fob_id) AS families,
    event_date,
    event_desc
   FROM family_date
  GROUP BY event_date, event_desc
  ORDER BY event_date;


ALTER VIEW public.v_pool_event_attendance OWNER TO wentworth_user;

--
-- Name: v_system_missing_assigned_fobs; Type: VIEW; Schema: public; Owner: wentworth_user
--

CREATE VIEW public.v_system_missing_assigned_fobs AS
 SELECT assigned_fob_id,
    sysem_fob_id,
    controller_id
   FROM public.v_system_assigned_fob_compare
  WHERE ((sysem_fob_id IS NULL) AND (assigned_fob_id > 0));


ALTER VIEW public.v_system_missing_assigned_fobs OWNER TO wentworth_user;

--
-- Name: members; Type: TABLE; Schema: webpage; Owner: wentworth_user
--

CREATE TABLE webpage.members (
    resident_name character varying(50),
    email character varying(50),
    last_sign_in timestamp without time zone,
    street_address character varying(50)
);


ALTER TABLE webpage.members OWNER TO wentworth_user;

--
-- Name: online_payments; Type: TABLE; Schema: webpage; Owner: wentworth_user
--

CREATE TABLE webpage.online_payments (
    date text,
    description text,
    amount numeric
);


ALTER TABLE webpage.online_payments OWNER TO wentworth_user;

--
-- Name: page_details; Type: TABLE; Schema: webpage; Owner: wentworth_user
--

CREATE TABLE webpage.page_details (
    pd_id integer NOT NULL,
    page_name character varying,
    login_req character varying,
    online_payment character varying,
    admin boolean,
    static boolean
);


ALTER TABLE webpage.page_details OWNER TO wentworth_user;

--
-- Name: page_details_pd_id_seq; Type: SEQUENCE; Schema: webpage; Owner: wentworth_user
--

CREATE SEQUENCE webpage.page_details_pd_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE webpage.page_details_pd_id_seq OWNER TO wentworth_user;

--
-- Name: page_details_pd_id_seq; Type: SEQUENCE OWNED BY; Schema: webpage; Owner: wentworth_user
--

ALTER SEQUENCE webpage.page_details_pd_id_seq OWNED BY webpage.page_details.pd_id;


--
-- Name: page_hits; Type: TABLE; Schema: webpage; Owner: wentworth_user
--

CREATE TABLE webpage.page_hits (
    page character varying(50),
    page_views integer,
    avg_time_on_page character varying(50),
    exit_rate character varying(50),
    data_date date
);


ALTER TABLE webpage.page_hits OWNER TO wentworth_user;

--
-- Name: fobs_slop record_id; Type: DEFAULT; Schema: dataload; Owner: wentworth_user
--

ALTER TABLE ONLY dataload.fobs_slop ALTER COLUMN record_id SET DEFAULT nextval('dataload.fobs_slop_record_id_seq'::regclass);


--
-- Name: access_list_from_controller acl_record_id; Type: DEFAULT; Schema: door_controller; Owner: wentworth_user
--

ALTER TABLE ONLY door_controller.access_list_from_controller ALTER COLUMN acl_record_id SET DEFAULT nextval('door_controller.access_list_from_controller_acl_record_id_seq'::regclass);


--
-- Name: system_fobs fob_record_id; Type: DEFAULT; Schema: door_controller; Owner: wentworth_user
--

ALTER TABLE ONLY door_controller.system_fobs ALTER COLUMN fob_record_id SET DEFAULT nextval('door_controller.fobs_record_id_seq'::regclass);


--
-- Name: budget_categories_values_hist record_id; Type: DEFAULT; Schema: finances; Owner: wentworth_user
--

ALTER TABLE ONLY finances.budget_categories_values_hist ALTER COLUMN record_id SET DEFAULT nextval('finances.budget_categories_values_hist_record_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: key_fobs; Owner: wentworth_user
--

ALTER TABLE ONLY key_fobs.users ALTER COLUMN user_id SET DEFAULT nextval('key_fobs.users_user_id_seq'::regclass);


--
-- Name: payroll_date pr_date_id; Type: DEFAULT; Schema: pool_monitor; Owner: wentworth_user
--

ALTER TABLE ONLY pool_monitor.payroll_date ALTER COLUMN pr_date_id SET DEFAULT nextval('pool_monitor.payroll_date_pr_date_id_seq'::regclass);


--
-- Name: pool_monitors monitor_id; Type: DEFAULT; Schema: pool_monitor; Owner: wentworth_user
--

ALTER TABLE ONLY pool_monitor.pool_monitors ALTER COLUMN monitor_id SET DEFAULT nextval('pool_monitor.newtable_monitor_id_seq'::regclass);


--
-- Name: pool_events eventid; Type: DEFAULT; Schema: public; Owner: wentworth_user
--

ALTER TABLE ONLY public.pool_events ALTER COLUMN eventid SET DEFAULT nextval('public.pool_events_eventid_seq'::regclass);


--
-- Name: page_details pd_id; Type: DEFAULT; Schema: webpage; Owner: wentworth_user
--

ALTER TABLE ONLY webpage.page_details ALTER COLUMN pd_id SET DEFAULT nextval('webpage.page_details_pd_id_seq'::regclass);


--
-- Name: access_list_from_controller access_list_from_controller_pk; Type: CONSTRAINT; Schema: door_controller; Owner: wentworth_user
--

ALTER TABLE ONLY door_controller.access_list_from_controller
    ADD CONSTRAINT access_list_from_controller_pk PRIMARY KEY (acl_record_id);


--
-- Name: system_fobs fobs_pk; Type: CONSTRAINT; Schema: door_controller; Owner: wentworth_user
--

ALTER TABLE ONLY door_controller.system_fobs
    ADD CONSTRAINT fobs_pk PRIMARY KEY (fob_record_id);


--
-- Name: budget_categories_values_hist budget_categories_values_hist_pk; Type: CONSTRAINT; Schema: finances; Owner: wentworth_user
--

ALTER TABLE ONLY finances.budget_categories_values_hist
    ADD CONSTRAINT budget_categories_values_hist_pk PRIMARY KEY (record_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: key_fobs; Owner: wentworth_user
--

ALTER TABLE ONLY key_fobs.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: key_fobs; Owner: wentworth_user
--

ALTER TABLE ONLY key_fobs.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: pool_monitors newtable_pk; Type: CONSTRAINT; Schema: pool_monitor; Owner: wentworth_user
--

ALTER TABLE ONLY pool_monitor.pool_monitors
    ADD CONSTRAINT newtable_pk PRIMARY KEY (monitor_id);


--
-- Name: payroll_date payroll_date_pk; Type: CONSTRAINT; Schema: pool_monitor; Owner: wentworth_user
--

ALTER TABLE ONLY pool_monitor.payroll_date
    ADD CONSTRAINT payroll_date_pk PRIMARY KEY (pr_date_id);


--
-- Name: pool_events newtable_pk; Type: CONSTRAINT; Schema: public; Owner: wentworth_user
--

ALTER TABLE ONLY public.pool_events
    ADD CONSTRAINT newtable_pk PRIMARY KEY (eventid);


--
-- PostgreSQL database dump complete
--

\unrestrict ZDl46PCdkryVDzjFgFtQwdH4qjLytXEo48cVOyUniWtoKAqKF0CZnhIy8rRLlwO

