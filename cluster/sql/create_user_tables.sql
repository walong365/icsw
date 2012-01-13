--
-- Copyright (C) 2001,2002,2003,2004,2005,2006,2009 Andreas Lang, init.at
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

DROP TABLE IF EXISTS ggroup;
CREATE TABLE ggroup (
  ggroup_idx int not null primary key auto_increment,
  active bool default 0,
  ggroupname varchar(16) not null unique,
  gid       int unique not null,
  homestart text default "",
  scratchstart text default "",
  respvname varchar(255) default "",
  respnname varchar(255) default "",
  resptitan varchar(255) default "",
  respemail varchar(255) default "",
  resptel   varchar(255) default "",
  respcom   varchar(255) default "",
  groupcom    varchar(255) default "",
  date timestamp
);
DELETE FROM table_r WHERE name='ggroup';
INSERT INTO table_r VALUES(null, 'ggroup', null);

-- user data
DROP TABLE IF EXISTS user;
CREATE TABLE user (
  user_idx int not null primary key auto_increment,
  active bool default 0,
  login varchar(255) not null unique,
  uid   int not null unique,
  ggroup int not null,
-- allowed aliases separated by spaces
  aliases text default "",
-- index to deviceconfig export-entry for home
  export     int default 0,
-- index to deviceconfig export-entry for scratch
  export_scr int default 0,
  home    text default "",
  scratch text default "",
  shell  varchar(255) default "/bin/false",
  password varchar(16) default "xxxx",
  cluster_contact int default 0,
  uservname varchar(255) default "",
  usernname varchar(255) default "",
  usertitan varchar(255) default "",
  useremail varchar(255) default "",
  userpager varchar(255) default "",
  usertel   varchar(255) default "",
  usercom  varchar(255) default "",
  nt_password varchar(128) default "",
  lm_password varchar(128) default "",
  date timestamp
);
DELETE FROM table_r WHERE name='user';
INSERT INTO table_r VALUES(null, 'user', null);

-- session data
DROP TABLE IF EXISTS session_data;
CREATE TABLE session_data (
  session_data_idx int not null primary key auto_increment,
  session_id char(32) not null unique,
  value text not null,
-- link to user
  user_idx int not null,
-- from where
  remote_addr text,
-- alias name when alias login
  alias varchar(128) default '',
  login_time datetime,
  logout_time datetime,
  forced_logout int default 0,
-- flag to rebuild server_routes
  rebuild_server_routes int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='session_data';
INSERT INTO table_r VALUES(null, 'session_data', null);

-- user-sge-server
DROP TABLE IF EXISTS sge_user_con;
CREATE TABLE sge_user_con (
  sge_user_con_idx int not null primary key auto_increment,
  user int not null,
  sge_config int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='sge_user_con';
INSERT INTO table_r VALUES(null, 'sge_user_con', null);

-- user vars
DROP TABLE IF EXISTS user_var;
CREATE TABLE user_var (
  user_var_idx int not null primary key auto_increment,
  user int not null,
  name varchar(63) not null,
  hidden int default 1,
-- type, (s)tring, (i)nteger, (l)ist, (b)ool, (d)ictionary
  type varchar(1) default 's',
-- editable
  editable int default 0,
-- value
  value blob default '',
-- description
  description text default '',
  date timestamp
);
DELETE FROM table_r WHERE name='user_var';
INSERT INTO table_r VALUES(null, 'user_var', null);

DROP TABLE IF EXISTS ggroupcap;
CREATE TABLE ggroupcap (
  ggroupcap_idx int not null primary key auto_increment,
  ggroup int not null,
  capability int not null,
  key ggroup(ggroup),
  key capability(capability),
  date timestamp
);
DELETE FROM table_r WHERE name='ggroupcap';
INSERT INTO table_r VALUES(null, 'ggroupcap', null);

DROP TABLE IF EXISTS usercap;
CREATE TABLE usercap (
  usercap_idx int not null primary key auto_increment,
  user int not null,
  capability int not null,
-- cannot use user as key
  key userx(user),
  key capability(capability),
  date timestamp
);
DELETE FROM table_r WHERE name='usercap';
INSERT INTO table_r VALUES(null, 'usercap', null);

-- DROP TABLE IF EXISTS capability_group;
-- CREATE TABLE capability_group (
--   capability_group_idx int not null primary key auto_increment,
--   name varchar(15) not null unique,
--   priority int default 0,
--   description varchar(255) default "unset",
--   date timestamp
-- );
-- DELETE FROM table_r WHERE name='capability_group';
-- INSERT INTO table_r VALUES(null, 'capability_group', null);

-- no capability_groups, top-capabilities are now the capability groups
DROP TABLE IF EXISTS capability;
CREATE TABLE capability (
  capability_idx int not null primary key auto_increment,
  name varchar(15) not null unique,
-- ccapability_group int default 0,
-- capability_group_name varchar(4) default '',
  mother_capability int default 0,
  mother_capability_name varchar(15) default '',
  priority int default 0,
-- default value for new groups
  defvalue int default 0,
-- global enabler
  enabled int default 1,
  description varchar(255) default "unset",
  modulename varchar(128) default '',
  left_string varchar(64) default '',
  right_string varchar(128) default '',
-- deprecated
--  php_enabled int default 1,
--  python_enabled int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='capability';
INSERT INTO table_r VALUES(null, 'capability', null);

-- user-ggroup table (for secondary groups)
DROP TABLE IF EXISTS user_ggroup;
CREATE TABLE user_ggroup (
  user_ggroup_idx int not null primary key auto_increment,
  ggroup int not null,
  user int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='user_ggroup';
INSERT INTO table_r VALUES(null, 'user_ggroup', null);

-- user-device-login table (for allowed devices)
DROP TABLE IF EXISTS user_device_login;
CREATE TABLE user_device_login (
  user_device_login_idx int not null primary key auto_increment,
  user int not null,
  device int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='user_device_login';
INSERT INTO table_r VALUES(null, 'user_device_login', null);
