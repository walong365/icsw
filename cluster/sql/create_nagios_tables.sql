--
-- Copyright (C) 2001,2002,2003,2004,2008 Andreas Lang-Nevyjel, init.at
--
-- Send feedback to: <lang-nevyjel@init.at>
--
-- This file is part of cluster-backbone
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

-- contact[<contact_name>]=<contact_alias>;<svc_notification_period>;<host_notification_period>;<svc_notify_recovery>;<svc_notify_critical>;<svc_notify_warning>;lt;host_notify_recovery>;<host_notify_down>;<host_notify_unreachable>;<service_notify_commands>;<host_notify_commands>;<email_address>;<pager>

-- nagios check command (OK)
drop table if exists ng_check_command;
create table ng_check_command (
  ng_check_command_idx int not null primary key auto_increment,
-- link to config
  config int default 0,
-- link to new config
  new_config int default 0,
-- link to ng_check_command_type
  ng_check_command_type int not null,
  ng_service_templ int default 0,
  name varchar(64) not null,
  command_line varchar(255) not null,
-- description
  description varchar(64) default '',
-- link to device (or zero for global config)
  device int default 0,
  date timestamp
);
delete from table_r where name='ng_check_command';
insert into table_r values(null, 'ng_check_command', null);

-- nagios check command type
drop table if exists ng_check_command_type;
create table ng_check_command_type (
  ng_check_command_type_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  date timestamp
);
delete from table_r where name='ng_check_command_type';
insert into table_r values(null, 'ng_check_command_type', null);

-- nagios contact (OK)
drop table if exists ng_contact;
create table ng_contact (
  ng_contact_idx int not null primary key auto_increment,
-- link to contact
  user int,
-- link to ng_period
  snperiod int,
-- link to ng_period
  hnperiod int,
  snrecovery int default 1,
  sncritical int default 1,
  snwarning int default 0,
  snunknown int default 1,
  hnrecovery int default 1,
  hndown int default 1,
  hnunreachable int default 1,
  sncommand varchar(64) default 'notify-by-email',
  hncommand varchar(64) default 'host-notify-by-email',
  date timestamp
);
delete from table_r where name='ng_contact';
insert into table_r values(null, 'ng_contact', null);

-- nagios time period definition (OK)
drop table if exists ng_period;
create table ng_period (
  ng_period_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  alias varchar(128),
  sunrange varchar(16) default "00:00-24:00",
  monrange varchar(16) default "00:00-24:00",
  tuerange varchar(16) default "00:00-24:00",
  wedrange varchar(16) default "00:00-24:00",
  thurange varchar(16) default "00:00-24:00",
  frirange varchar(16) default "00:00-24:00",
  satrange varchar(16) default "00:00-24:00",
  date timestamp
);
delete from table_r where name='ng_period';
insert into table_r values(null, 'ng_period', null);

-- connection between device_group and contactgroup (OK)
drop table if exists ng_device_contact;
create table ng_device_contact (
  ng_device_contact_idx int not null primary key auto_increment,
  device_group int not null,
  ng_contactgroup int not null,
  date timestamp
);
delete from table_r where name='ng_device_contact';
insert into table_r values(null, 'ng_device_contact', null);

-- contactgroup (OK)
drop table if exists ng_contactgroup;
create table ng_contactgroup (
  ng_contactgroup_idx int not null primary key auto_increment,
  name varchar(64) not null,
  alias varchar(128),
  date timestamp
);
delete from table_r where name='ng_contactgroup';
insert into table_r values(null, 'ng_contactgroup', null);

-- connects contact and contactgroup (OK)
drop table if exists ng_ccgroup;
create table ng_ccgroup (
  ng_ccgroup_idx int not null primary key auto_increment,
  ng_contact int not null,
  ng_contactgroup int not null,
  date timestamp
);
delete from table_r where name='ng_ccgroup';
insert into table_r values(null, 'ng_ccgroup', null);

-- service[<host>]=<description>;<volatile>;<check_period>;<max_attempts>;<check_interval>;<retry_interval>;<contactgroups>;<notification_interval>;<notification_period>;<notify_recovery>;<notify_critical>;<notify_warning>;<event_handler>;<check_command>

-- service template (OK)
drop table if exists ng_service_templ;
create table ng_service_templ (
  ng_service_templ_idx int not null primary key auto_increment,
  name varchar(64),
  volatile int default 0,
-- link to ng_period
  nsc_period int,
  max_attempts int default 1,
  check_interval int default 2,
  retry_interval int default 1,
  ninterval int default 1,
-- link to nsn_period
  nsn_period int,
  nrecovery int default 1,
  ncritical int default 1,
  nwarning int default 0,
  nunknown int default 1,
  date timestamp
);
delete from table_r where name='ng_service_templ';
insert into table_r values(null, 'ng_service_templ', null);

-- connects contactgroups and service templates (OK)
drop table if exists ng_cgservicet;
create table ng_cgservicet (
  ng_cgservicet_idx int not null primary key auto_increment,
  ng_contactgroup int not null,
  ng_service_templ int not null,
  date timestamp
);
delete from table_r where name='ng_cgservicet';
insert into table_r values(null, 'ng_cgservicet', null);

-- nagios service (obsolete ?)
drop table if exists ng_service;
create table ng_service (
  ng_service_idx int not null primary key auto_increment,
  name varchar(64) not null,
  alias varchar(64),
  command varchar(64),
-- for example warning value
  parameter1 varchar(64) default '',
-- for example critical value
  parameter2 varchar(64) default '',
  parameter3 varchar(64) default '',
  parameter4 varchar(64) default '',
  date timestamp
);
delete from table_r where name='ng_service';
insert into table_r values(null, 'ng_service', null);

-- additional host variables (OK)
drop table if exists ng_device_templ;
create table ng_device_templ (
  ng_device_templ_idx int not null primary key auto_increment,
  name varchar(64) unique not null,
-- default value for service templates
  ng_service_templ int,
  ccommand varchar(64) default 'check-host-alive',
  max_attempts int default 1,
  ninterval int default 1,
-- link to periods
  ng_period int,
  nrecovery int default 1,
  ndown int default 1,
  nunreachable int default 1,
-- one if this is the default ng_device_templ
  is_default int default 0,
  date timestamp
);
delete from table_r where name='ng_device_templ';
insert into table_r values(null, 'ng_device_templ', null);

-- -- forces certain services to a given servicetemplate (for ng_device_templ)
-- drop table if exists ng_sst_ng_device_templ;
-- create table ng_sst_ng_device_templ (
--   ng_sst_ng_device_templ_idx int not null primary key auto_increment,
-- -- link to service,
--   ng_service int not null,
-- -- link to servicetemplate
--   ng_service_templ int not null,
-- -- link to ng_device_templ
--   ng_device_templ int not null,
--   date timestamp
-- );
-- delete from table_r where name='ng_sst_ng_device_templ';
-- insert into table_r values(null, 'ng_sst_ng_device_templ', null);

-- -- forces certain services to a given servicetemplate (for device)
-- drop table if exists ng_sst_device;
-- create table ng_sst_device (
--   ng_sst_device_idx int not null primary key auto_increment,
-- -- link to service,
--   ng_service int not null,
-- -- link to servicetemplate
--   ng_service_templ int not null,
-- -- link to device
--   device int not null,
--   date timestamp
-- );
-- delete from table_r where name='ng_sst_device';
-- insert into table_r values(null, 'ng_sst_device', null);

-- extended host information (OK)
drop table if exists ng_ext_host;
create table ng_ext_host (
  ng_ext_host_idx int not null primary key auto_increment,
  name varchar(64) unique not null,
--  notes varchar(128) default "";
  icon_image varchar(64) default "",
  icon_image_alt varchar(64) default "",
  vrml_image varchar(64) default "",
  statusmap_image varchar(64) default "",
  date timestamp
);

delete from table_r where name='ng_ext_host';
insert into table_r values(null, 'ng_ext_host', null);

