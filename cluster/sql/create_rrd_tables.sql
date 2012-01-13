--
-- Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
--
-- Send feedback to: <lang@init.at>
--
-- This file is part of rms-tools
--
-- This program is free software; you can redistribute it and/or modify
-- it under the terms of the GNU General Public License Version 2 as
-- published by the Free Software Foundation.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program; if not, write to the Free Software
-- Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
--

-- rrd_set
drop table if exists rrd_set ;
create table rrd_set (
  rrd_set_idx int not null primary key auto_increment,
-- link to device
  device int,
-- filename relative to RRD_HOME (defined in rrd_server)
  filename varchar(255) default '',
  date timestamp,
  key device(device)
);
delete from table_r where name='rrd_set';
insert into table_r values(null, 'rrd_set', null);

-- rrd_class
drop table if exists rrd_class ;
create table rrd_class (
  rrd_class_idx int not null primary key auto_increment,
  name varchar(255) not null unique,
  step int default 60 not null,
  heartbeat int default 60 not null,
  date timestamp
);
delete from table_r where name='rrd_class';
insert into table_r values(null, 'rrd_class', null);

-- rrd_rra
drop table if exists rrd_rra ;
create table rrd_rra (
  rrd_rra_idx int not null primary key auto_increment,
-- rrd_class
  rrd_class int not null,
-- Consolidation function
  cf varchar(64) not null,
  steps int not null,
  rows int not null,
  xff float default 0.5,
  date timestamp
);
delete from table_r where name='rrd_rra';
insert into table_r values(null, 'rrd_rra', null);

-- rrd_data
drop table if exists rrd_data ;
create table rrd_data (
  rrd_data_idx int not null primary key auto_increment,
-- link to rrd_set (and hence to machine)
  rrd_set int,
-- full description (with .)
  descr varchar(255) not null,
-- description parts
  descr1 varchar(63) not null,
  descr2 varchar(63) default '',
  descr3 varchar(63) default '',
  descr4 varchar(63) default '',
  unit varchar(32),
  info varchar(128),
-- data source
  from_snmp int default 0,
  base int default 1,
  factor real default 1.,
  var_type varchar(1) default 'i',
  date timestamp,
  key rrd_set(rrd_set)
);
delete from table_r where name='rrd_data';
insert into table_r values(null, 'rrd_data', null);

-- new rrd_data
drop table if exists new_rrd_data ;
create table new_rrd_data (
  new_rrd_data_idx int not null primary key auto_increment,
-- link to rrd_set (and hence to machine)
  device int,
  descr varchar(255),
  descr1 varchar(64),
  descr2 varchar(64),
  descr3 varchar(64),
  descr4 varchar(64),
  unit varchar(32),
  info varchar(128),
-- data source
  from_snmp int default 0,
  base int default 1,
  factor real default 1.,
  var_type varchar(1) default 'i',
  date timestamp,
  key device(device)
);
delete from table_r where name='new_rrd_data';
insert into table_r values(null, 'new_rrd_data', null);

-- cluster events
DROP TABLE IF EXISTS cluster_event ;
CREATE TABLE cluster_event (
  cluster_event_idx int not null primary key auto_increment,
-- short name (also command to send to mother)
  name varchar(32) unique not null,
-- longer descrption
  description varchar(128),
-- color for webinterface
  color varchar(6) default "ff0f5f",
-- command for mother
  command varchar(64) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='cluster_event';
INSERT INTO table_r VALUES(null,"cluster_event", null);

-- configurable cluster events
drop table if exists ccl_event;
create table ccl_event (
  ccl_event_idx int not null primary key auto_increment,
-- link to device
  device int not null,
-- link to rrd_data
  rrd_data int not null,
-- class (this class and the ones with a lower priority are affected if set), used in conjunction with ccl_hloc_con
  device_class int,
-- threshold
  threshold float,
-- threshold class (1 for upper th, -1 for lower, 0 for crossing)
  threshold_class int not null,
  cluster_event int default 0,
-- hysteresis range (if a event has been triggered, one of the next data readings must exceed
-- the threshold_value by a margin of +/- hysteresis/2 
  hysteresis real default 0.,
-- disabled
  disabled int default 0,
  date timestamp
);
delete from table_r where name='ccl_event';
insert into table_r values(null, 'ccl_event', null);

-- connects ccl_events and device_location
drop table if exists ccl_dloc_con;
create table ccl_dloc_con (
  ccl_dloc_con_idx int not null primary key auto_increment,
-- ccl_event
  ccl_event int not null,
--  device location
  device_location int not null,
  date timestamp
);
delete from table_r where name='ccl_dloc_con';
insert into table_r values(null, 'ccl_dloc_con', null);

-- connects ccl_events and device_groups
drop table if exists ccl_dgroup_con;
create table ccl_dgroup_con (
  ccl_dgroup_con_idx int not null primary key auto_increment,
-- ccl_event
  ccl_event int not null,
--  device location
  device_group int not null,
  date timestamp
);
delete from table_r where name='ccl_dgroup_con';
insert into table_r values(null, 'ccl_dgroup_con', null);

-- connects ccl_events and user (for mail sending)
drop table if exists ccl_user_con;
create table ccl_user_con (
  ccl_user_con_idx int not null primary key auto_increment,
-- ccl_event
  ccl_event int not null,
--  device location
  user int not null,
  date timestamp
);
delete from table_r where name='ccl_user_con';
insert into table_r values(null, 'ccl_user_con', null);

-- configurable cluster event logging
drop table if exists ccl_event_log;
create table ccl_event_log (
  ccl_event_log_idx int not null primary key auto_increment,
-- device this event belongs to
  device int,
-- ccl_event responsible for this event
  ccl_event int,
-- cluster_event 
  cluster_event int,
-- active or passive
  passive int default 1,
  date timestamp
);
delete from table_r where name='ccl_event_log';
insert into table_r values(null, 'ccl_event_log', null);

-- data cache for rrd-collector
drop table if exists rrd_data_store;
create table rrd_data_store (
  rrd_data_store_idx int not null primary key auto_increment,
-- device this event belongs to
  device int not null,
-- received time
  recv_time int not null,
-- data
  data blob not null,
  date timestamp,
  key device(device)
);
delete from table_r where name='rrd_data_store';
insert into table_r values(null, 'rrd_data_store', null);
