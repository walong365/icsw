--
-- Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
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

-- packages
DROP TABLE IF EXISTS package;
CREATE TABLE package (
  package_idx int not null primary key auto_increment,
  name varchar(128) not null,
  version varchar(255) not null,
  `release` varchar(255) not null,
  architecture int,
  size int,
  pgroup text default '' not null,
  summary text default '' not null,
  distribution int,
  vendor int,
  buildtime int default 0,
  buildhost varchar(255) default 'not set',
  packager varchar(255) default 'not set',
  date timestamp
);
DELETE FROM table_r WHERE name='package';
INSERT INTO table_r VALUES(null, 'package', null);

-- architecture info
DROP TABLE IF EXISTS architecture;
CREATE TABLE architecture (
  architecture_idx int not null primary key auto_increment,
  architecture text not null,
  date timestamp
);
DELETE FROM table_r WHERE name='architecture';
INSERT INTO table_r VALUES(null, 'architecture', null);

-- distribution info
DROP TABLE IF EXISTS distribution;
CREATE TABLE distribution (
  distribution_idx int not null primary key auto_increment,
  distribution text not null,
  date timestamp
);
DELETE FROM table_r WHERE name='distribution';
INSERT INTO table_r VALUES(null, 'distribution', null);

-- vendor info
DROP TABLE IF EXISTS vendor;
CREATE TABLE vendor (
  vendor_idx int not null primary key auto_increment,
  vendor text not null,
  date timestamp
);
DELETE FROM table_r WHERE name='vendor';
INSERT INTO table_r VALUES(null, 'vendor', null);

-- package-image connection
DROP TABLE IF EXISTS pi_connection;
CREATE TABLE pi_connection (
  pi_connection_idx int not null primary key auto_increment,
  package int not null,
  image int not null,
  install_time int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='pi_connection';
INSERT INTO table_r VALUES(null, 'pi_connection', null);

-- inst_packages ; installable packages
DROP TABLE IF EXISTS inst_package;
CREATE TABLE inst_package (
  inst_package_idx int not null primary key auto_increment,
-- link to package
  package int not null,
-- where to find the package (for the nodes)
  location text default '' not null,
-- native, set to 1 if package has to be installed via a direct rpm-call (problems with xorg-x11-Mesa on SUSE 9.3)
  native int default 1,
  last_build int,
-- present on disk,
  present_on_disk int default 1,
-- package set
  package_set int default 0,
  date timestamp,
  key (package)
);
DELETE FROM table_r WHERE name='inst_package';
INSERT INTO table_r VALUES(null, 'inst_package', null);

-- rsync_device ; connection between rsync-configs and device
DROP TABLE IF EXISTS device_rsync_config;
CREATE TABLE device_rsync_config (
  device_rsync_config_idx int not null primary key auto_increment,
-- link to device_config for rsync
  new_config int not null,
-- link to device
  device int not null,
-- last rsync
  last_rsync_time datetime default 0,
-- status, textfield
  status text default '' not null,
  date timestamp,
  key (new_config),
  key (device)
);
DELETE FROM table_r WHERE name='device_rsync_config';
INSERT INTO table_r VALUES(null, 'device_rsync_config', null);

-- instp_device ; connection between installable packages and devices
DROP TABLE IF EXISTS instp_device;
CREATE TABLE instp_device (
  instp_device_idx int not null primary key auto_increment,
-- link to inst_package
  inst_package int not null,
-- link to device
  device int not null,
-- install, set to 1 if package has to be installed
  install int default 0,
-- upgrade, set to 1 if package has to be upgraded
  `upgrade` int default 0,
-- del, set to 1 if package has to be deleted
  del int default 0,
-- nodeps, set to 1 if package has to be installed with --nodeps
  nodeps int default 0,
-- force, set to 1 if package has to be installed with --force
  forceflag int default 0,
-- status, textfield
  status text default '' not null,
-- install time
  install_time datetime default 0,
-- number of error_lines
  error_line_num int default 0,
-- error lines, delimeter is "\n"
  error_lines text default '' not null,
  date timestamp,
  key (inst_package),
  key (device)
);
DELETE FROM table_r WHERE name='instp_device';
INSERT INTO table_r VALUES(null, 'instp_device', null);

-- application ; 
DROP TABLE IF EXISTS application;
CREATE TABLE application (
  application_idx int not null primary key auto_increment,
-- name
  name varchar(128) not null unique,
-- description
  description text default '' not null,
  date timestamp
);
DELETE FROM table_r WHERE name='application';
INSERT INTO table_r VALUES(null, 'application', null);

-- connection between application and device_group
DROP TABLE IF EXISTS app_devgroup_con;
CREATE TABLE app_devgroup_con (
  app_devgroup_con_idx int not null primary key auto_increment,
-- application
  application int not null,
-- device_group
  device_group int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='app_devgroup_con';
INSERT INTO table_r VALUES(null, 'app_devgroup_con', null);

-- connection between application and inst_package
DROP TABLE IF EXISTS app_instpack_con;
CREATE TABLE app_instpack_con (
  app_instpack_con_idx int not null primary key auto_increment,
-- application
  application int not null,
-- inst_package
  inst_package int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='app_instpack_con';
INSERT INTO table_r VALUES(null, 'app_instpack_con', null);

-- connection between application and configuration
DROP TABLE IF EXISTS app_config_con;
CREATE TABLE app_config_con (
  app_config_con_idx int not null primary key auto_increment,
-- application
  application int not null,
-- inst_package
  config int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='app_config_con';
INSERT INTO table_r VALUES(null, 'app_config_con', null);

-- package set
DROP TABLE IF EXISTS package_set;
CREATE TABLE package_set (
  package_set_idx int not null primary key auto_increment,
  name varchar(255) not null unique,
  date timestamp
);
DELETE FROM table_r WHERE name='package_set';
INSERT INTO table_r VALUES(null, 'package_set', null);

-- DROP TABLE IF EXISTS application;
-- CREATE TABLE application (
--   application_idx int not null primary key auto_increment,
--   date timestamp
-- );
-- DELETE FROM table_r WHERE name='application';
-- INSERT INTO table_r VALUES(null, 'application', null);
