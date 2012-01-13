--
-- Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
--
-- Send feedback to: <lang@init.at>
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

-- SGE complexes
DROP TABLE IF EXISTS sge_complex;
CREATE TABLE sge_complex (
  sge_complex_idx int not null primary key auto_increment,
  name varchar(128) unique not null,
  total_time varchar(64) default '00:10:00',
  slot_time varchar(64) default '00:10:00',
  pe_slots_min int default 1,
  pe_slots_max int default 1,
  default_queue varchar(64) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='sge_complex';
INSERT INTO table_r VALUES(null, 'sge_complex', null);

-- valid for the sun gridengine
DROP TABLE IF EXISTS sge_project;
CREATE TABLE sge_project (
  sge_project_idx int not null primary key auto_increment,
  name varchar(128) unique not null,
  oticket real default 0.,
  fshare real default 0.,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_project';
INSERT INTO table_r VALUES(null, 'sge_project', null);

DROP TABLE IF EXISTS sge_userlist_type;
CREATE TABLE sge_userlist_type (
  sge_userlist_type_idx int not null primary key auto_increment,
  name varchar(64) unique not null,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_userlist_type';
INSERT INTO table_r VALUES(null, 'sge_userlist_type', null);

DROP TABLE IF EXISTS sge_userlist;
CREATE TABLE sge_userlist (
  sge_userlist_idx int not null primary key auto_increment,
  name varchar(128) unique not null,
  oticket real default 0.,
  fshare real default 0.,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_userlist';
INSERT INTO table_r VALUES(null, 'sge_userlist', null);

DROP TABLE IF EXISTS sge_ul_ult;
CREATE TABLE sge_ul_ult (
  sge_ul_ult_idx int not null primary key auto_increment,
  sge_userlist int not null,
  sge_userlist_type int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_ul_ult';
INSERT INTO table_r VALUES(null, 'sge_ul_ult', null);

DROP TABLE IF EXISTS sge_user;
CREATE TABLE sge_user (
  sge_user_idx int not null primary key auto_increment,
  name varchar(128) unique not null,
  oticket real default 0.,
  fshare real default 0.,
  default_project int default 0,
  cluster_user int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_user';
INSERT INTO table_r VALUES(null, 'sge_user', null);

DROP TABLE IF EXISTS sge_job;
CREATE TABLE sge_job (
  sge_job_idx int not null primary key auto_increment,
-- job userid, consists of jobnumber, taskid and submit-time
  job_uid varchar(255) unique not null default '???',
  jobname varchar(128) not null,
  jobnum int not null,
  taskid int default 0,
  jobowner varchar(128) not null,
  jobgroup varchar(128) not null,
-- log entry relative to sge_log, was 'jobs'/job_uid
  log_path text default '' not null,
-- link to sge_user
  sge_user int default 0,
  queue_time datetime,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_job';
INSERT INTO table_r VALUES(null, 'sge_job', null);

DROP TABLE IF EXISTS sge_job_run;
CREATE TABLE sge_job_run (
  sge_job_run_idx int not null primary key auto_increment,
-- link to sge_job_log
  sge_job int not null,
  account varchar(128) not null default 'sge',
-- department
  sge_userlist int default 0,
  sge_project int default 0,
  priority int default 0,
  granted_pe varchar(64) not null default 'none',
  slots int default 1,
  failed int default 0,
  failed_str varchar(255) default 'unknown',
  exit_status int default 0,
  masterq varchar(128) not null,
  start_time datetime,
  start_time_sge datetime,
  end_time datetime,
  end_time_sge datetime,
  sge_ru_wallclock int default 0,
  sge_cpu int default 0,
  sge_mem float default 0.0,
  sge_io int default 0,
  sge_iow int default 0,
  sge_maxvmem int default 0,
  sge_parsed int default 0,
  date timestamp,
  key (sge_job)
);
DELETE FROM table_r WHERE name='sge_job_run';
INSERT INTO table_r VALUES(null, 'sge_job_run', null);

DROP TABLE IF EXISTS sge_pe_host;
CREATE TABLE sge_pe_host (
  sge_pe_host_idx int not null primary key auto_increment,
  sge_job_run int not null,
-- link to device
  device int default 0,
-- hostname
  hostname varchar(128) default '' not null,
  num_slots int default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_pe_host';
INSERT INTO table_r VALUES(null, 'sge_pe_host', null);

DROP TABLE IF EXISTS sge_queue;
CREATE TABLE sge_queue (
  sge_queue_idx int not null primary key auto_increment,
  queue_name varchar(128) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_queue';
INSERT INTO table_r VALUES(null, 'sge_queue', null);

DROP TABLE IF EXISTS sge_host;
CREATE TABLE sge_host (
  sge_host_idx int not null primary key auto_increment,
-- host name from config
  host_name varchar(128) not null,
-- link to device (may become invalid)
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_host';
INSERT INTO table_r VALUES(null, 'sge_host', null);

DROP TABLE IF EXISTS sge_log;
CREATE TABLE sge_log (
  sge_log_idx int not null primary key auto_increment,
-- link to sge_job, may be zero
  sge_job int default 0,
-- link to sge_queue, may be zero
  sge_queue int default 0,
-- link to sge_host, may be zero
  sge_host int default 0,
  log_level int default 0,
  log_str varchar(255) not null,
  date timestamp,
  key (sge_queue),
  key (sge_host),
  key (sge_job)
);
DELETE FROM table_r WHERE name='sge_log';
INSERT INTO table_r VALUES(null, 'sge_log', null);

