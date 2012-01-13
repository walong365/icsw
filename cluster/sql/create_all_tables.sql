--
-- Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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

-- table_references
DROP TABLE IF EXISTS table_r;
CREATE TABLE table_r (
  table_r_idx int not null primary key auto_increment,
  name varchar(64) unique not null,
  date timestamp
);
INSERT INTO table_r VALUES(null, 'table_r', null);

-- generic stuff
-- obsolete as of 2006-03-11 (approx.), no implemented via cluster_device_group -> META_device -> device_variable
DROP TABLE IF EXISTS genstuff;
CREATE TABLE genstuff (
  genstuff_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  description varchar(128),
  value varchar(64),
  date timestamp
);
DELETE FROM table_r WHERE name='genstuff';
INSERT INTO table_r VALUES(null, 'genstuff', null);

-- device group
DROP TABLE IF EXISTS device_group;
CREATE TABLE device_group (
  device_group_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  description varchar(128) not null,
-- link to meta-device
  device int default 0,
-- flag if this is the main device-group
  cluster_device_group int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='device_group';
INSERT INTO table_r VALUES(null, 'device_group', null);

-- device selection
DROP TABLE IF EXISTS device_selection;
CREATE TABLE device_selection (
  device_selection_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
-- 0 for all users and user_idx for specific users
  user int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='device_selection';
INSERT INTO table_r VALUES(null, 'device_selection', null);

-- device-device selection link
DROP TABLE IF EXISTS device_device_selection;
CREATE TABLE device_device_selection (
  device_device_selection_idx int not null primary key auto_increment,
  device_selection int not null,
  device int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='device_device_selection';
INSERT INTO table_r VALUES(null, 'device_device_selection', null);

-- device_type table
DROP TABLE IF EXISTS device_type;
CREATE TABLE device_type (
  device_type_idx int not null primary key auto_increment,
-- H for normal Host
-- AM for APC Masterswitch
-- NB for Netbotz devices
-- S for Switch
-- R Raid Box
-- P Printer
-- MD Meta device
  identifier varchar(8) not null unique,
  description varchar(64) not null unique,
  date timestamp
);
DELETE FROM table_r WHERE name='device_type';
INSERT INTO table_r VALUES(null, 'device_type', null);

-- device_shape table
DROP TABLE IF EXISTS device_shape;
CREATE TABLE device_shape (
  device_shape_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  description varchar(64) not null,
  x_dim real default 0.,
  y_dim real default 0.,
  z_dim real default 0.,
  date timestamp
);
DELETE FROM table_r WHERE name='device_shape';
INSERT INTO table_r VALUES(null, 'device_shape', null);

-- device_relationship table; xen host
DROP TABLE IF EXISTS device_relationship;
CREATE TABLE device_relationship (
  device_relationship_idx int not null primary key auto_increment,
  host_device int not null,
  domain_device int not null,
  relationship ENUM("xen") default 'xen',
  date timestamp
);
DELETE FROM table_r WHERE name='device_relationship';
INSERT INTO table_r VALUES(null, 'device_relationship', null);

-- xen_device table
DROP TABLE IF EXISTS xen_device;
CREATE TABLE xen_device (
  xen_device_idx int not null primary key auto_increment,
-- link to device
  device int not null,
-- memory for device (in MB)
  memory int not null default 256,
-- max_memory
  max_memory int not null default 256,
-- builder
  builder ENUM("hvm", "linux") default 'linux',
-- extra line
  cmdline varchar(255) default 'root=/dev/hda1 xencons=tty 3',
-- vcpus
  vcpus int default 1 not null,
  date timestamp
);
DELETE FROM table_r WHERE name='xen_device';
INSERT INTO table_r VALUES(null, 'xen_device', null);

-- xen_vbd table
DROP TABLE IF EXISTS xen_vbd;
CREATE TABLE xen_vbd (
  xen_vbd_idx int not null primary key auto_increment,
-- link to xen_device
  xen_device int not null,
-- type
  vbd_type ENUM("phy", "nfs", "iscsi") default "phy",
-- arguments, depending on vbd_type
  sarg0 varchar(255) default '',
  sarg1 varchar(255) default '',
  sarg2 varchar(255) default '',
  sarg3 varchar(255) default '',
  iarg0 int default 0,
  iarg1 int default 0,
  iarg2 int default 0,
  iarg3 int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='xen_vbd';
INSERT INTO table_r VALUES(null, 'xen_vbd', null);

-- device table
DROP TABLE IF EXISTS device;
CREATE TABLE device (
  device_idx int not null primary key auto_increment,
-- device name
  name varchar(64) not null unique,
-- device_group
  device_group int not null,
-- device_type
  device_type int not null,
-- AX-number
  axnumber varchar(64) default '',
-- device alias
  alias varchar(128) default '',
-- device comment
  comment varchar(128) default '',
-- snmp class
  snmp_class int default 0,
---- MasterSwitch related fields
--  mswitch int default 0,
--  outlet int default 0,
-- Switch related fields,
  switch int default 0,
  switchport int default 0,
-- nagios tag
  ng_device_templ int default 0,
-- nagios extended host info
  ng_ext_host int default 0,
-- device location
  device_location int default 0,
-- device class
  device_class int default 0,
-- rrd class
  rrd_class int default 0,
-- save rrd_vectors
  save_rrd_vectors int default 0,
-- valid etherboot-setup
  etherboot_valid int default 0,
-- kernel stuff
  kernel_append varchar(128) default '',
  newkernel varchar(64) default '',
  new_kernel int default 0,
  actkernel varchar(64) default '',
  act_kernel int default 0,
  act_kernel_build int default 0,
  kernelversion varchar(64) default '',
  stage1_flavour varchar(16) default '',
-- xen stuff
-- memory for dom0 if xen-kernel
  dom0_memory int default 524288,
  xen_guest int default 0,
-- image stuff
  newimage varchar(255) default '',
  new_image int default 0,
  actimage varchar(255) default '',
  act_image int default 0,
  imageversion varchar(64) default '',
-- partition stuff
  partition_table int default 0,
  act_partition_table int default 0,
-- partition device
  partdev varchar(64) default '',
  fixed_partdev int default 0,
-- is node bz2-capable?
  bz2_capable int default 1,
-- new stuff
  newstate int default 0,
-- rsync flag
-- 0 ... disable rsync
-- 1 ... rsync only for install
-- 2 ... rsync on every boot
  rsync int default 0,
  rsync_compressed int default 1,
-- link to production network
  prod_link int default 0,
-- received/requested states
  recvstate text default '',
  reqstate text default '',
-- link to booting netdevice (new version)
  bootnetdevice int default 0,
-- bootserver (link to device)
  bootserver int default 0,
-- reachable via bootserver
  reachable_via_bootserver int default 0,
-- 1 if machine is greedy
  dhcp_mac int default 0,
-- 1 if we have to write to the dhcp server
  dhcp_write int default 1,
-- 1 if dhcp-info was written to the dhcp server
  dhcp_written int default 0,
-- latest dhcp_error str
  dhcp_error varchar(255) default '',
-- propagation level
  propagation_level int default 0,
-- last install/boot/kernel info
  last_install varchar(64) default '',
  last_boot varchar(64) default '',
  last_kernel varchar(64) default '',
-- root passwd (encrypted)
  root_passwd varchar(64) default '',
-- device mode (0 ... no check, 1 ... keep_running)
  device_mode int default 0,
-- relaying device (for checks into other networks)
  relay_device int default 0,
-- device has to be checked from nagios
  nagios_checks int default 1,
-- viewable in bootcontrol
  show_in_bootcontrol int default 1,
-- cpuinfo blob
  cpu_info longblob default '',
  date timestamp,
  key (device_group)
);
DELETE FROM table_r WHERE name='device';
INSERT INTO table_r VALUES(null, 'device', null);

-- device variable
DROP TABLE IF EXISTS device_variable;
CREATE TABLE device_variable (
  device_variable_idx int not null primary key auto_increment,
-- link to device
  device int not null,
-- public (i.e. editable)
  is_public int default 0,
  name varchar(255) not null,
-- description 
  description varchar(255) default '',
-- type, string, integer, blob, date, time 
  var_type ENUM("s", "i", "b", "d", "t") not null,
  val_str text default '',
  val_int int default 0,
  val_blob blob default '',
  val_date datetime,
  val_time time,
  date timestamp,
  key (device)
);
INSERT INTO table_r VALUES(null, 'device_variable', null);

DROP TABLE IF EXISTS apc_device;
CREATE TABLE apc_device (
  apc_device_idx int not null primary key auto_increment,
-- link to device
  device int not null,
  power_on_delay int default 0,
  reboot_delay int default 0,
-- one of masterswitch, rpdu
  apc_type varchar(255) default '',
-- version info, delimeted by first char
  version_info text default '',
-- number of outlets
  num_outlets int default 0,
  date timestamp
);
INSERT INTO table_r VALUES(null, 'apc_device', null);

DROP TABLE IF EXISTS ibc_device;
CREATE TABLE ibc_device (
  ibc_device_idx int not null primary key auto_increment,
-- link to device
  device int not null,
  blade_type varchar(64) default 'not set',
  num_blades int default 0,
  date timestamp
);
INSERT INTO table_r VALUES(null, 'ibc_device', null);

-- dmi entries
DROP TABLE IF EXISTS dmi_entry;
CREATE TABLE dmi_entry (
  dmi_entry_idx int not null primary key auto_increment,
  device int not null,
  dmi_type int not null,
  handle int not null,
  dmi_length int not null,
  info varchar(255) not null,
  date timestamp
);
INSERT INTO table_r VALUES(null, 'dmi_entry', null);

-- dmi keys
DROP TABLE IF EXISTS dmi_key;
CREATE TABLE dmi_key (
  dmi_key_idx int not null primary key auto_increment,
  dmi_entry int not null,
  key_string varchar(255) not null,
  value_string varchar(255) default '',
  date timestamp,
  key (dmi_entry)
);
INSERT INTO table_r VALUES(null, 'dmi_key', null);

-- dmi ext_keys
DROP TABLE IF EXISTS dmi_ext_key;
CREATE TABLE dmi_ext_key (
  dmi_ext_key_idx int not null primary key auto_increment,
  dmi_key int not null,
  ext_value_string varchar(255) not null,
  date timestamp,
  key (dmi_key)
);
INSERT INTO table_r VALUES(null, 'dmi_ext_key', null);

-- hw_entry_type
DROP TABLE IF EXISTS hw_entry_type;
CREATE TABLE hw_entry_type (
  hw_entry_type_idx int not null primary key auto_increment,
  identifier varchar(8) not null,
  description varchar(255) not null,
  iarg0_descr varchar(255),
  iarg1_descr varchar(255),
  sarg0_descr varchar(255),
  sarg1_descr varchar(255),
  date timestamp
);
INSERT INTO table_r VALUES(null, 'hw_entry_type', null);

-- hw_entry
DROP TABLE IF EXISTS hw_entry;
CREATE TABLE hw_entry (
  hw_entry_idx int not null primary key auto_increment,
  device int not null ,
  hw_entry_type int not null,
  iarg0 int,
  iarg1 int,
  sarg0 varchar(255),
  sarg1 varchar(255),
  date timestamp
);
INSERT INTO table_r VALUES(null, 'hw_entry', null);

-- pci_entry
DROP TABLE IF EXISTS pci_entry;
CREATE TABLE pci_entry (
  pci_entry_idx int not null primary key auto_increment,
  device_idx int not null ,
  domain int,
  bus int,
  slot int,
  func int,
  vendor varchar(6) not null,
  vendorname varchar(64) not null,
  device varchar(6) not null,
  devicename varchar(64) not null,
  class varchar(6) not null,
  classname varchar(64) not null,
  subclass varchar(6) not null,
  subclassname varchar(64) not null,
  revision varchar(32) not null,
  date timestamp,
  key (device_idx)
);
INSERT INTO table_r VALUES(null, 'pci_entry', null);

-- netip
DROP TABLE IF EXISTS netip;
CREATE TABLE netip (
  netip_idx int not null primary key auto_increment,
  ip varchar(16) not null ,
  network int not null,
-- link to netdevice
  netdevice int not null,
-- penalty
  penalty int default 0,
-- aliases (space separated) for this ip
  alias varchar(255) default '',
-- is alias exclusive?
  alias_excl int default 0,
  date timestamp,
  key (netdevice)
);
INSERT INTO table_r VALUES(null, 'netip', null);

-- netdevice
DROP TABLE IF EXISTS netdevice;
CREATE TABLE netdevice (
  netdevice_idx int not null primary key auto_increment,
-- link to device
  device int not null ,
-- device name
  devname varchar(12) not null ,
  macadr varchar(59) default '00:00:00:00:00:00',
  driver_options varchar(224) default '',
-- old speed, deprecated
  speed int default 0,
-- netdevice_speed
  netdevice_speed int not null,
  driver varchar(128) default '',
-- one if this netdevice is able to route
  routing int default 0,
-- penalty (for routing netdevices)
  penalty int default 0,
-- dhcp_device (one for devices able to receive a dhcp-request even if there is no ip-address from a bootnet is associated with them)
  dhcp_device int default 0,
-- ethtool_options
  ethtool_options int default 0,
-- fake macaddr
  fake_macadr varchar(59) default '00:00:00:00:00:00',
-- link to network_device_type
  network_device_type int default 0,
-- description
  description varchar(255) default '',
-- flag is bridge
  is_bridge int default 0,
-- bridge to connect to
  bridge_name varchar(255) default '',
-- vlan id
  vlan_id int default 0,
  date timestamp,
  key (device)
);
DELETE FROM table_r WHERE name='netdevice';
INSERT INTO table_r VALUES(null, 'netdevice', null);

-- netdevice_speed
DROP TABLE IF EXISTS netdevice_speed;
CREATE TABLE netdevice_speed (
  netdevice_speed_idx int not null primary key auto_increment,
  speed_bps bigint default 0,
-- set to one if this speed can be checked via ethtool
  check_via_ethtool int default 0,
-- full duplex ?
  full_duplex int default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='netdevice_speed';
INSERT INTO table_r VALUES(null, 'netdevice_speed', null);

-- CREATE TABLE netdeviceip (
--   netdeviceip_idx int not null primary key auto_increment,
--   netdevice int,
--   netip int,
--   date timestamp
-- );

-- INSERT INTO table_r VALUES(null, 'netdeviceip', null);

-- network_type
DROP TABLE IF EXISTS network_type;
CREATE TABLE network_type (
  network_type_idx int not null primary key auto_increment,
-- unique identifier
-- B for boot
-- P for production
-- O for other
-- S for slave
  identifier char(1) not null unique,
  description varchar(64) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='network_type';
INSERT INTO table_r VALUES(null, 'network_type', null);

-- network_device_type
DROP TABLE IF EXISTS network_device_type;
CREATE TABLE network_device_type (
  network_device_type_idx int not null primary key auto_increment,
  identifier varchar(16) not null unique,
  description varchar(64) not null,
  mac_bytes int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='network_device_type';
INSERT INTO table_r VALUES(null, 'network_device_type', null);

-- network_network_device_type
DROP TABLE IF EXISTS network_network_device_type;
CREATE TABLE network_network_device_type (
  network_network_device_type_idx int not null primary key auto_increment,
  network int not null,
  network_device_type int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='network_network_device_type';
INSERT INTO table_r VALUES(null, 'network_network_device_type', null);

-- network
DROP TABLE IF EXISTS network;
CREATE TABLE network (
  network_idx int not null primary key auto_increment,
-- identifier
  identifier varchar(128) not null unique,
-- link to type
  network_type int not null,  
--   # 1 for boot net (172.17.X.Y)
--   is_boot int default 0,
--   # 1 for net-selectable net (was: Production or Test Network)
--   is_production int default 0,
--   # 1 if this is a slave net to another net (for example an mpi-network bound to a production net)
--   is_slave int default 0,
-- master network; network is a slave_network if master_network is != 0
  master_network int default 0,
-- 1 if for this network the short hostnames should be created
  short_names int default 0,
-- network name (i.e. init.at, ...)
  name varchar(64),
-- penalty for taking this path
  penalty int not null default 1,
-- postfix (FQHostName=<MACHINE.NAME><POSTFIX>.<NAME>
  postfix varchar(4) default '',
  info varchar(128) default '???',
  network varchar(15),
  netmask varchar(15),
  broadcast varchar(15),
  gateway varchar(15) default '0.0.0.0',
  gw_pri int default 0,
-- flag to write nameserver config
  write_bind_config int default 1,
-- flag to write configs of other networks
  write_other_network_config int default 0,
-- start of auto-set ips
  start_range varchar(15) default '0.0.0.0',
-- end of auto-set ips
  end_range varchar(15) default '0.0.0.0',
  date timestamp
);
DELETE FROM table_r WHERE name='network';
INSERT INTO table_r VALUES(null, 'network', null);

-- Master outlets
DROP TABLE IF EXISTS msoutlet;
CREATE TABLE msoutlet (
  msoutlet_idx int not null primary key auto_increment,
-- link to masterswitch device
  device int not null,
-- link to device connected to this outlet
  slave_device int default 0,
-- short info (for example PS1,PS2 ...)
  slave_info varchar(64) default '',
-- outlet number
  outlet int not null,
  state varchar(32) default '',
-- target values,
  t_power_on_delay int default 0,
  t_power_off_delay int default 0,
  t_reboot_delay int default 0,
-- readings from the apc
  power_on_delay int default 0,
  power_off_delay int default 0,
  reboot_delay int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='msoutlet';
INSERT INTO table_r VALUES(null, 'msoutlet', null);

-- Master outlets
DROP TABLE IF EXISTS ibc_connection;
CREATE TABLE ibc_connection (
  ibc_connection_idx int not null primary key auto_increment,
-- link to IBM Blade Center device
  device int not null,
-- link to device connected to this outlet
  slave_device int default 0,
-- short info (for example PS1,PS2 ...)
  slave_info varchar(64) default '',
-- blade number
  blade int not null,
  state varchar(32) default '',
-- exists
  blade_exists int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='ibc_connection';
INSERT INTO table_r VALUES(null, 'ibc_connection', null);

-- status
DROP TABLE IF EXISTS status;
CREATE TABLE status (
  status_idx int not null primary key auto_increment,
  status varchar(128) not null unique,
-- link to production network
  prod_link int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='status';
INSERT INTO table_r VALUES(null, 'status', null);

-- connects new_config structure with devices (also meta-devices)
-- device_config
DROP TABLE IF EXISTS device_config;
CREATE TABLE device_config (
  device_config_idx int not null primary key auto_increment,
  device int not null,
  new_config int not null,
  key (new_config),
  key (device),
  date timestamp
);
DELETE FROM table_r WHERE name='device_config';
INSERT INTO table_r VALUES(null, 'device_config', null);

-- new configure entries
DROP TABLE IF EXISTS new_config;
CREATE TABLE new_config (
  new_config_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  description varchar(255) not null,
  priority int default 0,
  new_config_type int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='new_config';
INSERT INTO table_r VALUES(null, 'new_config', null);

-- cluster functionality
-- links to one or more new_configs; is in fact some kind of super-config with more options
DROP TABLE IF EXISTS cluster_functionality;
CREATE TABLE cluster_functionality (
  cluster_functionality_idx int not null primary key auto_increment,
  name varchar(255) not null unique,
  description varchar(255) not null,
-- coma-separated list of runlevel-scripts
  runlevelscripts text default '',
  date timestamp
);
DELETE FROM table_r WHERE name='cluster_functionality';
INSERT INTO table_r VALUES(null, 'cluster_functionality', null);

-- links between cluster functionality and new_config
DROP TABLE IF EXISTS cluster_functionality_new_config;
CREATE TABLE cluster_functionality_new_config (
  cluster_functionality_new_config_idx int not null primary key auto_increment,
  cluster_functionality int not null,
  new_config int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='cluster_functionality_new_config';
INSERT INTO table_r VALUES(null, 'cluster_functionality_new_config', null);

-- config_type
DROP TABLE IF EXISTS config_type;
CREATE TABLE config_type (
  config_type_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
-- s server stuff
-- n node stuff
-- h hardware stuff
  identifier varchar(2) not null unique,
  description varchar(128) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='config_type';
INSERT INTO table_r VALUES(null, 'config_type', null);

-- new_config_type
DROP TABLE IF EXISTS new_config_type;
CREATE TABLE new_config_type (
  new_config_type_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
  description varchar(255) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='new_config_type';
INSERT INTO table_r VALUES(null, 'new_config_type', null);

-- written config for files
DROP TABLE IF EXISTS wc_files;
CREATE TABLE wc_files (
  wc_files_idx int not null primary key auto_increment,
-- link to device
  device int not null,
-- integer number on disk
  disk_int int default 0,
-- link to (first) config
  config varchar(128) default '',
-- uid,gid and mode
  uid int default 0,
  gid int default 0,
  mode int default 0,
-- dest type, one of 'l', 'f' or 'd' (or 'e' for error)
  dest_type varchar(1) not null,
-- name of source
  source varchar(255) not null,
-- name of destination
  dest varchar(255) not null,
-- error flag
  error_flag int default 0,
-- content
  content longblob default '',
  date timestamp
);
DELETE FROM table_r WHERE name='wc_files';
INSERT INTO table_r VALUES(null, 'wc_files', null);

-- config_script
DROP TABLE IF EXISTS config_script;
CREATE TABLE config_script (
  config_script_idx int not null primary key auto_increment,
  name varchar(64) not null,
  descr varchar(255) not null,
-- enable/disable
  enabled int default 1,
-- priority
  priority int default 0,
-- link to new_config
  new_config int not null,
  value longtext default '',
  error_text longtext default '',
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='config_script';
INSERT INTO table_r VALUES(null, 'config_script', null);

-- config_int
DROP TABLE IF EXISTS config_int;
CREATE TABLE config_int (
  config_int_idx int not null primary key auto_increment,
  name varchar(64) not null,
  descr varchar(255) not null,
-- link to config
  config int default 0,
-- link to new_config
  new_config int default 0,
  value int default 0,
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='config_int';
INSERT INTO table_r VALUES(null, 'config_int', null);

-- config_str
DROP TABLE IF EXISTS config_str;
CREATE TABLE config_str (
  config_str_idx int not null primary key auto_increment,
  name varchar(64) not null,
  descr varchar(255) not null,
-- link to config
  config int default 0,
-- link to new_config
  new_config int default 0,
  value longtext default '',
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='config_str';
INSERT INTO table_r VALUES(null, 'config_str', null);

-- config_bool
DROP TABLE IF EXISTS config_bool;
CREATE TABLE config_bool (
  config_bool_idx int not null primary key auto_increment,
  name varchar(64) not null,
  descr varchar(255) not null,
-- link to config
  config int default 0,
-- link to new_config
  new_config int default 0,
  value int default 0,
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='config_bool';
INSERT INTO table_r VALUES(null, 'config_bool', null);

-- config_blob
DROP TABLE IF EXISTS config_blob;
CREATE TABLE config_blob (
  config_blob_idx int not null primary key auto_increment,
  name varchar(64) not null,
  descr varchar(255) not null,
-- link to config
  config int default 0,
-- link to new_config
  new_config int default 0,
  value blob default '',
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='config_blob';
INSERT INTO table_r VALUES(null, 'config_blob', null);

DROP TABLE IF EXISTS snmp_class;
CREATE TABLE snmp_class (
  snmp_class_idx int not null primary key auto_increment,
  name varchar(64) not null,
-- description field, is used as info
  descr varchar(255) not null,
-- read/write community
  read_community varchar(64) default 'public' not null,
  write_community varchar(64) default 'private' not null,
-- snmp_version; 1,2 or 3
  snmp_version int default 2,
-- update frequency in seconds
  update_freq int default 60,
  date timestamp
);
DELETE FROM table_r WHERE name='snmp_class';
INSERT INTO table_r VALUES(null, 'snmp_class', null);

-- snmp_mib
DROP TABLE IF EXISTS snmp_mib;
CREATE TABLE snmp_mib (
  snmp_mib_idx int not null primary key auto_increment,
  name varchar(64) not null unique,
-- description field, is used as info
  descr varchar(255) default '',
-- mib
  mib varchar(128) not null,
-- key for rrd-server (for example temp, lo.rx usw.)
  rrd_key varchar(64) not null,
-- similar stuff to rrd_data
  unit varchar (32),
  base int default 1,
  factor real default 1.,
  var_type varchar(1) default 'i',
-- special command for parsing
  special_command varchar(255) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='snmp_mib';
INSERT INTO table_r VALUES(null, 'snmp_mib', null);

-- snmp_config
DROP TABLE IF EXISTS snmp_config;
CREATE TABLE snmp_config (
  snmp_config_idx int not null primary key auto_increment,
-- link to config		
  config int default 0,
  new_config int default 0,
  snmp_mib int not null,
-- link to device or 0 for global config
  device int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='snmp_config';
INSERT INTO table_r VALUES(null, 'snmp_config', null);

-- macbootlogtables
DROP TABLE IF EXISTS macbootlog;
CREATE TABLE macbootlog (
  macbootlog_idx int not null primary key auto_increment,
  device int default 0,
  type varchar(32) not null,
  ip varchar(32) not null,
  macadr varchar(64) not null,
  log_source int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='macbootlog';
INSERT INTO table_r VALUES(null, 'macbootlog', null);

-- macignoretables
DROP TABLE IF EXISTS mac_ignore;
CREATE TABLE mac_ignore (
  mac_ignore_idx int not null primary key auto_increment,
  macadr varchar(64) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='mac_ignore';
INSERT INTO table_r VALUES(null, 'mac_ignore', null);

-- images
DROP TABLE IF EXISTS image;
CREATE TABLE image (
  image_idx int not null primary key auto_increment,
  name varchar(64),
  source varchar(128),
  version int default 1,
  `release` int default 0,
  builds int default 0,
  build_machine varchar(64),
  device int default 0,
  build_lock int default 0,
  size_string text default '',
  sys_vendor varchar(64) default '',
  sys_version varchar(64) default '',
  sys_release varchar(64) default '',
-- bitcount for system
  bitcount int default 0,
-- link to architecture
  architecture int default 0,
-- last build was a full build ?
  full_build int default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='image';
INSERT INTO table_r VALUES(null, 'image', null);

-- images
DROP TABLE IF EXISTS image_excl;
CREATE TABLE image_excl (
  image_excl_idx int not null primary key auto_increment,
-- link to image
  image int not null,
  exclude_path text not null,
  valid_for_install int default 1,
  valid_for_upgrade int default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='image_excl';
INSERT INTO table_r VALUES(null, 'image_excl', null);

-- kernel
DROP TABLE IF EXISTS kernel;
CREATE TABLE kernel (
  kernel_idx int not null primary key auto_increment,
-- kernel name
  name varchar(128) NOT NULL,
-- kernel version
  kernel_version varchar(128) NOT NULL,
-- major minor patchlevel
  major varchar(64) default '???',
  minor varchar(64) default '???',
  patchlevel varchar(64) default '???',
-- kernel version
  version int default 1,
-- kernel release
  `release` int default 0,
-- number of builds
  builds int default 0,
-- name of latest build machine
  build_machine varchar(64),
-- master server for this kernel
  master_server int default 0,
-- master server role (mother or xen)
  master_role varchar(64) default 'mother',
-- link to build device (if resolvable)
  device int default 0,
-- build lock (not really necessary...)
  build_lock int default 0,
-- name of config-file
  config_name varchar(64) default '',
-- cpu architecture
  cpu_arch varchar(64) default '???',
-- sub cpu architecture
  sub_cpu_arch varchar(64) default '???',
-- kernel target dir
  target_dir varchar(255) default '',
-- comment
  comment text default '',
-- enabled 
  enabled int default 1,
-- initrd version
  initrd_version int default 1,
-- initrd_built
  initrd_built datetime,
-- actual module list, comma separated
  module_list text default '',
-- target module list, comma separated
  target_module_list text default '',
-- is a xen_host kernel ?
  xen_host_kernel int default 0,
-- is a xen_guest kernel ?
  xen_guest_kernel int default 0,
-- bitcount in kernel, zero for unknown
  bitcount int default 0,
-- stage1/2 OK flags    
  stage1_lo_present     int default 0,
  stage1_cpio_present   int default 0,
  stage1_cramfs_present int default 0,
  stage2_present        int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='kernel';
INSERT INTO table_r VALUES(null, 'kernel', null);

-- kernel_log
DROP TABLE IF EXISTS kernel_log;
CREATE TABLE kernel_log (
  kernel_log_idx int not null primary key auto_increment,
-- link to kernel
  kernel int not null,
-- link to device which kernel_server attribute
  device int not null,
-- kernel_syncer role (mother or xen)
  syncer_role varchar(64) default 'mother',
-- log_level, see logging_tools.py
  log_level int default 0,
-- link to build device (if resolvable)
  log_str text default '',
  date timestamp
);
DELETE FROM table_r WHERE name='kernel_log';
INSERT INTO table_r VALUES(null, 'kernel_log', null);

-- kernel_local_info
DROP TABLE IF EXISTS kernel_local_info;
CREATE TABLE kernel_local_info (
  kernel_local_info_idx int not null primary key auto_increment,
-- link to kernel
  kernel int not null,
-- link to device which kernel_server attribute
  device int not null,
-- kernel_syncer role (mother or xen)
  syncer_role varchar(64) default 'mother',
-- info blob
  info_blob blob default '',
  date timestamp
);
DELETE FROM table_r WHERE name='kernel_local_info';
INSERT INTO table_r VALUES(null, 'kernel_local_info', null);

-- kernel_build
DROP TABLE IF EXISTS kernel_build;
CREATE TABLE kernel_build (
  kernel_build_idx int not null primary key auto_increment,
-- link to kernel
  kernel int not null,
-- name build machine
  build_machine varchar(64),
-- link to build device (if resolvable)
  device int default 0,
-- kernel version
  version int default 1,
-- release
  `release` int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='kernel_build';
INSERT INTO table_r VALUES(null, 'kernel_build', null);

-- device connection table
DROP TABLE IF EXISTS device_connection ;
CREATE TABLE device_connection (
  device_connection_idx int not null primary key auto_increment,
-- parent device
  parent int not null,
-- child device
  child int not null,
  date timestamp
);
DELETE FROM table_r WHERE name='device_connection';
INSERT INTO table_r VALUES(null, 'device_connection', null);

-- device location
DROP TABLE IF EXISTS device_location;
CREATE TABLE device_location (
  device_location_idx int not null primary key auto_increment,
  location varchar(64),
  date timestamp
);
DELETE FROM table_r WHERE name='device_location';
INSERT INTO table_r VALUES(null, 'device_location', null);

-- device classes
DROP TABLE IF EXISTS device_class;
CREATE TABLE device_class (
  device_class_idx int not null primary key auto_increment,
  classname varchar(64),
  priority int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='device_class';
INSERT INTO table_r VALUES(null, 'device_class', null);

-- log_source
DROP TABLE IF EXISTS log_source;
CREATE TABLE log_source (
  log_source_idx int not null primary key auto_increment,
-- identifier
  identifier varchar(64) not null,
-- name
  name varchar(64) not null,
-- device index
  device int default 0,
-- description
  description varchar(255) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='log_source';
INSERT INTO table_r VALUES(null, 'log_source', null);

-- log entry status
DROP TABLE IF EXISTS log_status;
CREATE TABLE log_status (
  log_status_idx int not null primary key auto_increment,
-- identifier, 
-- possible: 'c' ... critical, log_level 200
--           'e' ... error,    log_level 100
--           'w' ... warning,  log_level 50
--           'i' ... info,     log_level 0
--           'n' ... notice,   log_level -50
  identifier varchar(4) default 'c',
-- log_level. corresponds with the identifier
-- the higher the log_level the more severe ist the log_entry
  log_level int default 0,
  name varchar(64) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='log_status';
INSERT INTO table_r VALUES(null, 'log_status', null);

-- device log
DROP TABLE IF EXISTS devicelog;
CREATE TABLE devicelog (
  devicelog_idx int not null primary key auto_increment,
-- device, 0 for cluster
  device int default 0,
-- who made the entry
-- references to log_source table
  log_source int default 0,
-- link to user if log_source->'identifier'=='user'
-- describes boottype if log_source->'identifier'=='node'
--   1 ... boot maintenance, 2 ... boot (into prod), 3 ... reseting, 4 ... halting, 5 ... DHCP request
  user int default 0,
-- log_status
  log_status int default 0,
  text varchar(255) default '',
  key (device),
  key (log_source),
  key (user),
  key (log_status),
  date timestamp
);
DELETE FROM table_r WHERE name='devicelog';
INSERT INTO table_r VALUES(null, 'devicelog', null);

-- extended log
DROP TABLE IF EXISTS extended_log;
CREATE TABLE extended_log (
  extended_log_idx int not null primary key auto_increment,
-- devicelog entry
  devicelog int,
  log_source int default 0,
  user int default 0,
-- users (comma-separated)
  users varchar(255) default '',
-- subject (comma-separated)
  subject varchar(255) default '',
-- description 
  description text default '',
  key devicelog(devicelog),
  date timestamp
);
DELETE FROM table_r WHERE name='extended_log';
INSERT INTO table_r VALUES(null, 'extended_log', null);

-- peer information
DROP TABLE IF EXISTS peer_information;
CREATE TABLE peer_information (
  peer_information_idx int not null primary key auto_increment,
-- source netdevice; source is treated as the 'mother'
  s_netdevice int not null,
-- destination netdevice; destination is treated as the 'child'
  d_netdevice int not null,
-- penalty for taking this path
  penalty int not null default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='peer_information';
INSERT INTO table_r VALUES(null, 'peer_information', null);

-- peer information
DROP TABLE IF EXISTS hopcount;
CREATE TABLE hopcount (
  hopcount_idx int not null primary key auto_increment,
-- source netdevice; source is treated as the 'mother'
  s_netdevice int not null,
-- destination netdevice; destination is treated as the 'child'
  d_netdevice int not null,
-- penalty for taking this path
  value int default 0,
-- trace from source to destination
  trace varchar(255) default '',
  key (s_netdevice),
  key (d_netdevice),
  date timestamp
);
DELETE FROM table_r WHERE name='hopcount';
INSERT INTO table_r VALUES(null, 'hopcount', null);

-- filesystem
DROP TABLE IF EXISTS partition_fs;
CREATE TABLE partition_fs (
  partition_fs_idx int not null primary key auto_increment,
-- name to be used in fstab
  name varchar(16) unique not null,
-- identifier. Can be:
-- f ..... Filesystem
-- s ..... SwapSpace
-- d ..... Dummy partition
-- e ..... extended partition
  identifier char(1) not null default 'f',
  descr varchar(255) default '',
  hexid char(2) default "00" not null,
  date timestamp
);
DELETE FROM table_r WHERE name='partition_fs';
INSERT INTO table_r VALUES(null, 'partition_fs', null);

-- partition stuff
DROP TABLE IF EXISTS partition_table;
CREATE TABLE partition_table (
  partition_table_idx int not null primary key auto_increment,
-- name
  name varchar(64) unique not null,
  description varchar(128) default '',
-- table valid
  valid int default 0,
-- modify bootloader 
  modify_bootloader int default 1,
  date timestamp
);
DELETE FROM table_r WHERE name='partition_table';
INSERT INTO table_r VALUES(null, 'partition_table', null);

-- lvm_vg
DROP TABLE IF EXISTS lvm_vg;
CREATE TABLE lvm_vg (
  lvm_vg_idx int not null primary key auto_increment,
-- partition table this vg is part of
  partition_table int not null,
-- name
  name varchar(64) not null,
  date timestamp
);
DELETE FROM table_r WHERE name='lvm_vg';
INSERT INTO table_r VALUES(null, 'lvm_vg', null);

-- lvm_lv
DROP TABLE IF EXISTS lvm_lv;
CREATE TABLE lvm_lv (
  lvm_lv_idx int not null primary key auto_increment,
-- partition table this lv is part of
  partition_table int not null,
-- vg this lvm is part of
  lvm_vg int not null,
-- size
  size bigint default 0,
-- mountput
  mountpoint varchar(64) default "" not null,
-- mount options
  mount_options varchar(128) default '',
-- freq-field for fstab
  fs_freq int default 0,
-- passno-field for fstab
  fs_passno int default 2,
-- name
  name varchar(64) not null,
-- filesystem
  partition_fs int default 0,
-- thresholds for warning / critical
  warn_threshold int default 0,
  crit_threshold int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='lvm_lv';
INSERT INTO table_r VALUES(null, 'lvm_lv', null);

-- partition_disc
DROP TABLE IF EXISTS partition_disc;
CREATE TABLE partition_disc (
  partition_disc_idx int not null primary key auto_increment,
-- partition table this disc is part of
  partition_table int not null,
  disc varchar(64) not null,
  priority int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='partition_disc';
INSERT INTO table_r VALUES(null, 'partition_disc', null);

DROP TABLE IF EXISTS partition;
CREATE TABLE partition (
  partition_idx int not null primary key auto_increment,
-- partition disc
  partition_disc int not null,
-- mountput
  mountpoint varchar(64) default "" not null,
-- fstype; if null the partition_hex is used as partition-id
  partition_hex varchar(2) default '00',
-- size in MB
  size int default 0,
-- mount options
  mount_options varchar(128) default '',
-- partition number
  pnum int default 1 not null,
-- bootable flag
  bootable int default 0,
-- freq-field for fstab
  fs_freq int default 0,
-- passno-field for fstab
  fs_passno int default 2,
-- filesystem
  partition_fs int default 0,
-- lut info (for /dev/disk-by and so on)
  lut_blob longblob default "",
-- thresholds for warning / critical
  warn_threshold int default 0,
  crit_threshold int default 0,
  date timestamp
);
DELETE FROM table_r WHERE name='partition';
INSERT INTO table_r VALUES(null, 'partition', null);

DROP TABLE IF EXISTS sys_partition;
CREATE TABLE sys_partition (
  sys_partition_idx int not null primary key auto_increment,
-- partition table
  partition_table int not null,
-- name 
  name varchar(64) not null,
-- mountput
  mountpoint varchar(64) not null,
-- mount options
  mount_options varchar(128) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='sys_partition';
INSERT INTO table_r VALUES(null, 'sys_partition', null);

DROP TABLE IF EXISTS netbotz_picture;
CREATE TABLE netbotz_picture (
  netbotz_picture_idx int not null primary key auto_increment,
-- netbotz
  device int not null,
-- year month day hour minute second
  year int not null,
  month int not null,
  day int not null,
  hour int not null,
  minute int not null,
  second int not null,
-- path
  path varchar(255) default '',
  date timestamp
);
DELETE FROM table_r WHERE name='netbotz_picture';
INSERT INTO table_r VALUES(null, 'netbotz_picture', null);
