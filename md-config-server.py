#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" server to configure the nagios or icinga monitoring daemon	 """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import zmq
import re
import configfile
import os.path
import time
import signal
import commands
import pprint
import logging_tools
import process_tools
import cluster_location
import server_command
import threading_tools
import config_tools
import codecs
import sqlite3
from initat.md_config_server.config import global_config
from initat.md_config_server import special_commands
try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"
from django.db.models import Q
from django.contrib.auth.models import User
from django.db import connection, connections
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
     mon_service, mon_ext_host, mon_check_command, mon_check_command_type, mon_period, mon_contact, \
     mon_contactgroup, mon_service_templ, netdevice, network, network_type, net_ip, hopcount, \
     user, mon_host_cluster, mon_service_cluster, config, route_generation
from django.conf import settings
import base64
import uuid_tools
import stat
import ConfigParser
import hashlib
import binascii
import operator

# nagios constants
NAG_HOST_UNKNOWN     = -1
NAG_HOST_UP          = 0
NAG_HOST_DOWN        = 1
NAG_HOST_UNREACHABLE = 2

# default port
SERVER_COM_PORT = 8010
TEMPLATE_NAME = "t"

IDOMOD_PROCESS_PROCESS_DATA           = 2 ** 0
IDOMOD_PROCESS_TIMED_EVENT_DATA       = 2 ** 1
IDOMOD_PROCESS_LOG_DATA               = 2 ** 2
IDOMOD_PROCESS_SYSTEM_COMMAND_DATA    = 2 ** 3
IDOMOD_PROCESS_EVENT_HANDLER_DATA     = 2 ** 4
IDOMOD_PROCESS_NOTIFICATION_DATA      = 2 ** 5
IDOMOD_PROCESS_SERVICE_CHECK_DATA     = 2 ** 6
IDOMOD_PROCESS_HOST_CHECK_DATA        = 2 ** 7
IDOMOD_PROCESS_COMMENT_DATA           = 2 ** 8
IDOMOD_PROCESS_DOWNTIME_DATA          = 2 ** 9
IDOMOD_PROCESS_FLAPPING_DATA          = 2 ** 10
IDOMOD_PROCESS_PROGRAM_STATUS_DATA    = 2 ** 11
IDOMOD_PROCESS_HOST_STATUS_DATA       = 2 ** 12
IDOMOD_PROCESS_SERVICE_STATUS_DATA    = 2 ** 13
IDOMOD_PROCESS_ADAPTIVE_PROGRAM_DATA  = 2 ** 14
IDOMOD_PROCESS_ADAPTIVE_HOST_DATA     = 2 ** 15
IDOMOD_PROCESS_ADAPTIVE_SERVICE_DATA  = 2 ** 16
IDOMOD_PROCESS_EXTERNAL_COMMAND_DATA  = 2 ** 17
IDOMOD_PROCESS_OBJECT_CONFIG_DATA     = 2 ** 18
IDOMOD_PROCESS_MAIN_CONFIG_DATA       = 2 ** 19
IDOMOD_PROCESS_AGGREGATED_STATUS_DATA = 2 ** 20
IDOMOD_PROCESS_RETENTION_DATA         = 2 ** 21
IDOMOD_PROCESS_ACKNOWLEDGEMENT_DATA   = 2 ** 22
IDOMOD_PROCESS_STATECHANGE_DATA       = 2 ** 23
IDOMOD_PROCESS_CONTACT_STATUS_DATA    = 2 ** 24
IDOMOD_PROCESS_ADAPTIVE_CONTACT_DATA  = 2 ** 25
 
BROKER_PROGRAM_STATE        = 2 ** 0
BROKER_TIMED_EVENTS         = 2 ** 1
BROKER_SERVICE_CHECKS       = 2 ** 2
BROKER_HOST_CHECKS          = 2 ** 3
BROKER_EVENT_HANDLERS       = 2 ** 4
BROKER_LOGGED_DATA          = 2 ** 5
BROKER_NOTIFICATIONS        = 2 ** 6
BROKER_FLAPPING_DATA        = 2 ** 7
BROKER_COMMENT_DATA         = 2 ** 8
BROKER_DOWNTIME_DATA        = 2 ** 9
BROKER_SYSTEM_COMMANDS      = 2 ** 10
BROKER_OCP_DATA             = 2 ** 11
BROKER_STATUS_DATA          = 2 ** 12
BROKER_ADAPTIVE_DATA        = 2 ** 13
BROKER_EXTERNALCOMMAND_DATA = 2 ** 14
BROKER_RETENTION_DATA       = 2 ** 15
BROKER_ACKNOWLEDGEMENT_DATA = 2 ** 16
BROKER_STATECHANGE_DATA     = 2 ** 17
BROKER_RESERVED18           = 2 ** 18
BROKER_RESERVED19           = 2 ** 19

class snmp_settings(object):
    def __init__(self, cdg):
        self.__cdg = cdg
        self.__snmp_vars = {}
    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__%d" % (cur_dev.device_group_id),
            "dev__%d" % (cur_dev.pk))
        if global_key not in self.__snmp_vars:
            # read global configs
            self.__snmp_vars["GLOBAL"] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=self.__cdg) & Q(name__istartswith="snmp_"))])
        if dg_key not in self.__snmp_vars:
            # read device_group configs
            self.__snmp_vars[dg_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device) & Q(name__istartswith="snmp_"))])
        if dev_key not in self.__snmp_vars:
            # read device configs
            self.__snmp_vars[dev_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev) & Q(name__istartswith="snmp_"))])
        ret_dict = {
            "SNMP_VERSION"         : 2,
            "SNMP_READ_COMMUNITY"  : "public",
            "SNMP_WRITE_COMMUNITY" : "private"}
        for s_key in ret_dict.iterkeys():
            for key in [dev_key, dg_key, global_key]:
                if s_key in self.__snmp_vars[key]:
                    ret_dict[s_key] = self.__snmp_vars[key][s_key]
                    break
        return ret_dict
        
class main_config(object):
    def __init__(self, b_proc, monitor_server, **kwargs):
        self.__build_process = b_proc
        self.__slave_name = kwargs.get("slave_name", None)
        self.__main_dir = global_config["MD_BASEDIR"]
        self.distributed = kwargs.get("distributed", False)
        if self.__slave_name:
            self.__dir_offset = os.path.join("slaves", self.__slave_name)
            master_cfg = config_tools.device_with_config("monitor_server")
            slave_cfg = config_tools.server_check(
                short_host_name=monitor_server.name,
                server_type="monitor_slave",
                fetch_network_info=True)
            self.slave_uuid = monitor_server.uuid
            route = master_cfg["monitor_server"][0].get_route_to_other_device(slave_cfg, allow_route_to_other_networks=True)
            if not route:
                self.slave_ip = None
                self.master_ip = None
                self.log("no route to slave %s found" % (unicode(monitor_server)), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.slave_ip = route[0][3][1][0]
                self.master_ip = route[0][2][1][0]
                self.log("IP-address of slave %s is %s (master: %s)" % (
                    unicode(monitor_server),
                    self.slave_ip,
                    self.master_ip
                ))
        else:
            self.__dir_offset = ""
            #self.__main_dir = os.path.join(self.__main_dir, "slaves", self.__slave_name)
        self.monitor_server = monitor_server
        self.master = True if not self.__slave_name else False
        self.__dict = {}
        self._create_directories()
        self._clear_etc_dir()
        self._create_base_config_entries()
        self._write_entries()
    @property
    def slave_name(self):
        return self.__slave_name
    def is_valid(self):
        ht_conf_names = [key for key, value in self.__dict.iteritems() if isinstance(value, host_type_config)]
        invalid = sorted([key for key in ht_conf_names if not self[key].is_valid()])
        if invalid:
            self.log("%s invalid: %s" % (
                logging_tools.get_plural("host_type config", len(invalid)),
                ", ".join(invalid)),
                     logging_tools.LOG_LEVEL_ERROR)
            return False
        else:
            return True
    def refresh(self):
        # refreshes host- and contactgroup definition
        self["contactgroup"].refresh(self)
        self["hostgroup"].refresh(self)
    def has_key(self, key):
        return self.__dict.has_key(key)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_process.log("[mc%s] %s" % (
            " %s" % (self.__slave_name) if self.__slave_name else "",
            what), level)
    def get_command_name(self):
        return os.path.join(
            self.__r_dir_dict["var"],
            "ext_com" if global_config["MD_TYPE"] == "nagios" else "icinga.cmd")
    def distribute(self):
        if self.slave_ip:
            self.log("start send to slave")
            self.__build_process.send_pool_message("register_slave", self.slave_ip, self.monitor_server.uuid)
            srv_com = server_command.srv_command(
                command="register_master",
                host="DIRECT",
                port="0",
                master_ip=self.master_ip,
                master_port="%d" % (SERVER_COM_PORT))
            time.sleep(0.2)
            self.__build_process.send_pool_message("send_command", self.monitor_server.uuid, unicode(srv_com))
            # send content of /etc
            for cur_file in os.listdir(self.__w_dir_dict["etc"]):
                full_r_path = os.path.join(self.__w_dir_dict["etc"], cur_file)
                full_w_path = os.path.join(self.__r_dir_dict["etc"], cur_file)
                if os.path.isfile(full_r_path):
                    srv_com = server_command.srv_command(
                        command="file_content",
                        host="DIRECT",
                        port="0",
                        uid="%d" % (os.stat(full_r_path)[stat.ST_UID]),
                        gid="%d" % (os.stat(full_r_path)[stat.ST_GID]),
                        file_name="%s" % (full_w_path),
                        content=base64.b64encode(file(full_r_path, "r").read())
                    )
                    self.__build_process.send_pool_message("send_command", self.monitor_server.uuid, unicode(srv_com))
            srv_com = server_command.srv_command(
                command="call_command",
                host="DIRECT",
                port="0",
                cmdline="/etc/init.d/icinga reload")
            self.__build_process.send_pool_message("send_command", self.monitor_server.uuid, unicode(srv_com))
        else:
            self.log("slave has no valid IP-address, skipping send", logging_tools.LOG_LEVEL_ERROR)
    def _create_directories(self):
        dir_names = [
            "",
            "etc",
            "var",
            "share",
            "var/archives",
            "ssl",
            "bin",
            "sbin",
            "lib",
            "lib64",
            "var/spool",
            "var/spool/checkresults"]
        # dir dict for writing on disk
        self.__w_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, self.__dir_offset, dir_name))) for dir_name in dir_names])
        # dir dict for referencing
        self.__r_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, dir_name))) for dir_name in dir_names])
        for dir_name, full_path in self.__w_dir_dict.iteritems():
            if not os.path.exists(full_path):
                self.log("Creating directory %s" % (full_path))
                os.makedirs(full_path)
            else:
                self.log("already exists : %s" % (full_path))
    def _clear_etc_dir(self):
        for dir_e in os.listdir(self.__w_dir_dict["etc"]):
            full_path = "%s/%s" % (self.__w_dir_dict["etc"], dir_e)
            if os.path.isfile(full_path):
                try:
                    os.unlink(full_path)
                except:
                    self.log("Cannot delete file %s: %s" % (full_path, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
    def _create_nagvis_base_entries(self):
        if os.path.isdir(global_config["NAGVIS_DIR"]):
            self.log("creating base entries for nagvis (under %s)" % (global_config["NAGVIS_DIR"]))
            # 
            nagvis_main_cfg = ConfigParser.RawConfigParser(allow_no_value=True)
            for sect_name, var_list in [
                ("global", [
                    ("audit_log", 1),
                    ("authmodule", "CoreAuthModSQLite"),
                    ("authorisationmodule", "CoreAuthorisationModSQLite"),
                    ("controls_size", 10),
                    ("dateformat", "Y-m-d H:i:s"),
                    ("dialog_ack_sticky", 1),
                    ("dialog_ack_notify", 1),
                    ("dialog_ack_persist", 0),
                    #("file_group", ""),
                    ("file_mode", "660"),
                    #("http_proxy", ""),
                    ("http_timeout", 10),
                    ("language_detection", "user,session,browser,config"),
                    ("language", "en_US"),
                    ("logonmodule", "LogonMixed"),
                    ("logonenvvar", "REMOTE_USER"),
                    ("logonenvcreateuser", 1),
                    ("logonenvcreaterole", "Guests"),
                    ("refreshtime", 60),
                    ("sesscookiedomain", "auto-detect"),
                    ("sesscookiepath", "/nagvis"),
                    ("sesscookieduration", "86400"),
                    ("startmodule", "Overview"),
                    ("startaction", "view"),
                    ("startshow", ""),
                    ]),
                ("paths", [
                    ("base", "%s/"% (os.path.normpath(global_config["NAGVIS_DIR"]))),
                    ("htmlbase", global_config["NAGVIS_URL"]),
                    ("htmlcgi", "/icinga/cgi-bin"),
                    ]),
                ("defaults", [
                    ("backend", "live_1"),
                    ("backgroundcolor", "#ffffff"),
                    ("contextmenu", 1),
                    ("contexttemplate", "default"),
                    ("event_on_load", 0),
                    ("event_repeat_interval", 0),
                    ("event_repeat_duration", -1),
                    ("eventbackground", 0),
                    ("eventhighlight", 1),
                    ("eventhighlightduration", 10000),
                    ("eventhighlightinterval", 500),
                    ("eventlog", 0),
                    ("eventloglevel", "info"),
                    ("eventlogevents", 24),
                    ("eventlogheight", 75),
                    ("eventloghidden", 1),
                    ("eventscroll", 1),
                    ("eventsound", 1),
                    ("headermenu", 1),
                    ("headertemplate", "default"),
                    ("headerfade", 1),
                    ("hovermenu", 1),
                    ("hovertemplate", "default"),
                    ("hoverdelay", 0),
                    ("hoverchildsshow", 0),
                    ("hoverchildslimit", 100),
                    ("hoverchildsorder", "asc"),
                    ("hoverchildssort", "s"),
                    ("icons", "std_medium"),
                    ("onlyhardstates", 0),
                    ("recognizeservices", 1),
                    ("showinlists", 1),
                    ("showinmultisite", 1),
                    #("stylesheet", ""),
                    ("urltarget", "_self"),
                    ("hosturl", "[htmlcgi]/status.cgi?host=[host_name]"),
                    ("hostgroupurl", "[htmlcgi]/status.cgi?hostgroup=[hostgroup_name]"),
                    ("serviceurl", "[htmlcgi]/extinfo.cgi?type=2&host=[host_name]&service=[service_description]"),
                    ("servicegroupurl", "[htmlcgi]/status.cgi?servicegroup=[servicegroup_name]&style=detail"),
                    ("mapurl", "[htmlbase]/index.php?mod=Map&act=view&show=[map_name]"),
                    ("view_template", "default"),
                    ("label_show", 0),
                    ("line_weather_colors", "10:#8c00ff,25:#2020ff,40:#00c0ff,55:#00f000,70:#f0f000,85:#ffc000,100:#ff0000"),
                    ]),
                ("index", [
                    ("backgroundcolor", "#ffffff"),
                    ("cellsperrow", 4),
                    ("headermenu", 1),
                    ("headertemplate", "default"),
                    ("showmaps", 1),
                    ("showgeomap", 0),
                    ("showrotations", 1),
                    ("showmapthumbs", 0),
                    ]),
                ("automap", [
                    ("defaultparams", "&childLayers=2"),
                    ("defaultroot", ""),
                    ("graphvizpath", "/opt/cluster/bin/"),
                    ]),
                ("wui", [
                   ("maplocktime", 5),
                   ("grid_show", 0),
                   ("grid_color", "#D5DCEF"),
                   ("grid_steps", 32),
                   ]),
                ("worker", [
                    ("interval", "10"),
                    ("requestmaxparams", 0),
                    ("requestmaxlength", 1900),
                    ("updateobjectstates", 30),
                    ]),
                ("backend_live_1", [
                    ("backendtype", "mklivestatus"),
                    ("statushost", ""),
                    ("socket", "unix:/opt/icinga/var/live"),
                    ]),
                ("backend_ndomy_1", [
                    ("backendtype", "ndomy"),
                    ("statushost", ""),
                    ("dbhost", "localhost"),
                    ("dbport", 3306),
                    ("dbname", "nagios"),
                    ("dbuser", "root"),
                    ("dbpass", ""),
                    ("dbprefix", "nagios_"),
                    ("dbinstancename", "default"),
                    ("maxtimewithoutupdate", 180),
                    ("htmlcgi", "/nagios/cgi-bin"),
                    ]),
                ("backend_merlinmy_1", [
                    ("backendtype", "merlinmy"),
                    ("dbhost", "localhost"),
                    ("dbport", 3306),
                    ("dbname", "merlin"),
                    ("dbuser", "merlin"),
                    ("dbpass", "merlin"),
                    ("maxtimewithoutupdate", 180),
                    ("htmlcgi", "/nagios/cgi-bin"),
                    ]),
                #("rotation_demo", [
                #    ("maps", "demo-germany,demo-ham-racks,demo-load,demo-muc-srv1,demo-geomap,demo-automap"),
                #    ("interval", 15),
                #    ]),
                ("states", [
                    ("down", 10),
                    ("down_ack", 6),
                    ("down_downtime", 6),
                    ("unreachable", 9),
                    ("unreachable_ack", 6),
                    ("unreachable_downtime", 6),
                    ("critical", 8),
                    ("critical_ack", 6),
                    ("critical_downtime", 6),
                    ("warning", 7),
                    ("warning_ack", 5),
                    ("warning_downtime", 5),
                    ("unknown", 4),
                    ("unknown_ack", 3),
                    ("unknown_downtime", 3),
                    ("error", 4),
                    ("error_ack", 3),
                    ("error_downtime", 3),
                    ("up", 2),
                    ("ok", 1),
                    ("unchecked", 0),
                    ("pending", 0),
                    ("unreachable_bgcolor", "#F1811B"),
                    ("unreachable_color", "#F1811B"),
                    #("unreachable_ack_bgcolor", ""),
                    #("unreachable_downtime_bgcolor", ""),
                    ("down_bgcolor", "#FF0000"),
                    ("down_color", "#FF0000"),
                    #("down_ack_bgcolor", ""),
                    #("down_downtime_bgcolor", ""),
                    ("critical_bgcolor", "#FF0000"),
                    ("critical_color", "#FF0000"),
                    #("critical_ack_bgcolor", ""),
                    #("critical_downtime_bgcolor", ""),
                    ("warning_bgcolor", "#FFFF00"),
                    ("warning_color", "#FFFF00"),
                    #("warning_ack_bgcolor", ""),
                    #("warning_downtime_bgcolor", ""),
                    ("unknown_bgcolor", "#FFCC66"),
                    ("unknown_color", "#FFCC66"),
                    #("unknown_ack_bgcolor", ""),
                    #("unknown_downtime_bgcolor", ""),
                    ("error_bgcolor", "#0000FF"),
                    ("error_color", "#0000FF"),
                    ("up_bgcolor", "#00FF00"),
                    ("up_color", "#00FF00"),
                    ("ok_bgcolor", "#00FF00"),
                    ("ok_color", "#00FF00"),
                    ("unchecked_bgcolor", "#C0C0C0"),
                    ("unchecked_color", "#C0C0C0"),
                    ("pending_bgcolor", "#C0C0C0"),
                    ("pending_color", "#C0C0C0"),
                    ("unreachable_sound", "std_unreachable.mp3"),
                    ("down_sound", "std_down.mp3"),
                    ("critical_sound", "std_critical.mp3"),
                    ("warning_sound", "std_warning.mp3"),
                    #("unknown_sound", ""),
                    #("error_sound", ""),
                    #("up_sound", ""),
                    #("ok_sound", ""),
                    #("unchecked_sound", ""),
                    #("pending_sound", ""),

                ])
                ]:
                nagvis_main_cfg.add_section(sect_name)
                for key, value in var_list:
                    nagvis_main_cfg.set(sect_name, key, unicode(value))
            with open(os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php")	, "wb") as nvm_file:
                nvm_file.write("; <?php return 1; ?>\n")
                nagvis_main_cfg.write(nvm_file)
            # clear SALT
            config_php = os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php")
            lines = file(config_php, "r").read().split("\n")
            new_lines, save = ([], False)
            for cur_line in lines:
                if cur_line.lower().count("auth_password_salt") and len(cur_line) > 60:
                    # remove salt
                    cur_line = "define('AUTH_PASSWORD_SALT', '');"
                    save = True
                new_lines.append(cur_line)
            if save:
                self.log("saving %s" % (config_php))
                file(config_php, "w").write("\n".join(new_lines))
        else:
            self.log("no nagvis_directory '%s' found" % (global_config["NAGVIS_DIR"]), logging_tools.LOG_LEVEL_ERROR)
    def _create_base_config_entries(self):
        # read sql info
        sql_file = "/etc/sysconfig/cluster/mysql.cf"
        sql_suc, sql_dict = configfile.readconfig(sql_file, 1)
        resource_cfg = base_config("resource", is_host_file=True)
        if os.path.isfile("/opt/%s/libexec/check_dns" % (global_config["MD_TYPE"])):
            resource_cfg["$USER1$"] = "/opt/%s/libexec" % (global_config["MD_TYPE"])
        else:
            resource_cfg["$USER1$"] = "/opt/%s/lib" % (global_config["MD_TYPE"])
        resource_cfg["$USER2$"] = "/opt/cluster/sbin/ccollclientzmq -t %d" % (global_config["CCOLLCLIENT_TIMEOUT"])
        resource_cfg["$USER3$"] = "/opt/cluster/sbin/csnmpclientzmq -t %d" % (global_config["CSNMPCLIENT_TIMEOUT"])
        NDOMOD_NAME, NDO2DB_NAME = ("ndomod",
                                    "ndo2db")
        ndomod_cfg = base_config(NDOMOD_NAME,
                                 belongs_to_ndo=True,
                                 values=[
                                     ("instance_name"              , "clusternagios"),
                                     ("output_type"                , "unixsocket"),
                                         ("output"                     , "%s/ido.sock" % (self.__r_dir_dict["var"])),
                                         ("tcp_port"                   , 5668),
                                         ("output_buffer_items"        , 5000),
                                         ("buffer_file"                , "%s/ndomod.tmp" % (self.__r_dir_dict["var"])),
                                         ("file_rotation_interval"     , 14400),
                                         ("file_rotation_timeout"      , 60),
                                         ("reconnect_interval"         , 15),
                                         ("reconnect_warning_interval" , 15),
                                         ("debug_level"                , 0),
                                         ("debug_verbosity"            , 0),
                                         ("debug_file"                 , os.path.join(self.__r_dir_dict["var"], "ndomod.debug")),
                                         ("data_processing_options"    , global_config["NDO_DATA_PROCESSING_OPTIONS"]),
                                         ("config_output_options"      , 2)])
        if not sql_suc:
            self.log("error reading sql_file '%s', no ndo2b_cfg to write" % (sql_file),
                     logging_tools.LOG_LEVEL_ERROR)
            ndo2db_cfg = None
        else:
            nag_engine = settings.DATABASES["monitor"]["ENGINE"]
            db_server = "pgsql" if nag_engine.count("psycopg") else "mysql"
            if db_server == "mysql":
                sql_dict["PORT"] = 3306
            else:
                sql_dict["PORT"] = 5432
            ndo2db_cfg = base_config(NDO2DB_NAME,
                                     belongs_to_ndo=True,
                                     values=[("ndo2db_user"            , "idnagios"),
                                             ("ndo2db_group"           , "idg"),
                                             ("socket_type"            , "unix"),
                                             ("socket_name"            , "%s/ido.sock" % (self.__r_dir_dict["var"])),
                                             ("tcp_port"               , 5668),
                                             ("db_servertype"          , db_server),
                                             ("db_host"                , sql_dict["MYSQL_HOST"]),
                                             ("db_port"                , sql_dict["PORT"]),
                                             ("db_name"                , sql_dict["NAGIOS_DATABASE"]),
                                             ("db_prefix"              , "%s_" % (global_config["MD_TYPE"])),
                                             ("db_user"                , sql_dict["MYSQL_USER"]),
                                             ("db_pass"                , sql_dict["MYSQL_PASSWD"]),
                                             # time limits one week
                                             ("max_timedevents_age"    , 1440),
                                             ("max_systemcommands_age" , 1440),
                                             ("max_servicechecks_age"  , 1440),
                                             ("max_hostchecks_age"     , 1440),
                                             ("max_eventhandlers_age"  , 1440),
                                             ("debug_level"            , 0),
                                             ("debug_verbosity"        , 1),
                                             ("debug_file"             , "%s/ndo2db.debug" % (self.__r_dir_dict["var"])),
                                             ("max_debug_file_size"    , 1000000)])
        manual_dir = "%s/manual" % (self.__w_dir_dict["etc"])
        if not os.path.isdir(manual_dir):
            os.mkdir(manual_dir)
        settings_dir = "%s/df_settings" % (self.__w_dir_dict["etc"])
        if not os.path.isdir(settings_dir):
            os.mkdir(settings_dir)
        main_values = [("log_file"                         , "%s/%s.log" % (self.__r_dir_dict["var"],
                                                                            global_config["MD_TYPE"])),
                       ("cfg_file"                         , []),
                       ("cfg_dir"                          , os.path.join(self.__r_dir_dict["etc"], "manual")),
                       ("resource_file"                    , "%s/%s.cfg" % (self.__r_dir_dict["etc"], resource_cfg.get_name())),
                       ("%s_user" % (global_config["MD_TYPE"]) , "idnagios"),
                       ("%s_group" % (global_config["MD_TYPE"]) , "idg"),
                       ("check_external_commands"          , 1),
                       ("command_check_interval"           , 1),
                       ("command_file"                     , self.get_command_name()),
                       ("command_check_interval"           , "5s"),
                       ("lock_file"                        , "%s/%s" % (self.__r_dir_dict["var"], global_config["MD_LOCK_FILE"])),
                       ("temp_file"                        , "%s/temp.tmp" % (self.__r_dir_dict["var"])),
                       ("log_rotation_method"              , "d"),
                       ("log_archive_path"                 , self.__r_dir_dict["var/archives"]),
                       ("use_syslog"                       , 0),
                       ("host_inter_check_delay_method"    , "s"),
                       ("service_inter_check_delay_method" , "s"),
                       ("service_interleave_factor"        , "s"),
                       ("max_concurrent_checks"            , global_config["MAX_CONCURRENT_CHECKS"]),
                       ("service_reaper_frequency"         , 12),
                       ("sleep_time"                       , 1),
                       ("retain_state_information"         , global_config["RETAIN_SERVICE_STATUS"]),# if self.master else 0),
                       ("state_retention_file"             , "%s/retention.dat" % (self.__r_dir_dict["var"])),
                       ("retention_update_interval"        , 60),
                       ("use_retained_program_state"       , 0),
                       ("use_retained_scheduling_info"     , 0),
                       ("interval_length"                  , 60 if not self.master else 60),
                       ("use_aggressive_host_checking"     , 0),
                       ("execute_service_checks"           , 1),
                       ("accept_passive_host_checks"       , 1),
                       ("accept_passive_service_checks"    , 1),
                       ("enable_notifications"             , 1 if self.master else 0),
                       ("enable_event_handlers"            , 1),
                       ("process_performance_data"         , (1 if global_config["ENABLE_PNP"] else 0) if self.master else 0),
                       ("obsess_over_services"             , 1 if not self.master else 0),
                       ("obsess_over_hosts"                , 1 if not self.master else 0),
                       ("check_for_orphaned_services"      , 0),
                       ("check_service_freshness"          , 0),
                       ("freshness_check_interval"         , 15),
                       ("enable_flap_detection"            , 0),
                       ("date_format"                      , "euro"),
                       ("illegal_object_name_chars"        , r"~!$%^&*|'\"<>?),()"),
                       ("illegal_macro_output_chars"       , r"~$&|'\"<>"),
                       ("admin_email"                      , "lang-nevyjel@init.at"),
                       ("admin_pager"                      , "????"),
                       #("debug_file"      , os.path.join(self.__r_dir_dict["var"], "icinga.dbg")),
                       #("debug_level"     , -1),
                       #("debug_verbosity" , 2),
                       # NDO stuff
                       ]
        if self.master:
            if global_config["ENABLE_LIVESTATUS"]:
                main_values.extend([
                    ("*broker_module", "%s/mk-livestatus/livestatus.o %s/live" % (
                    self.__r_dir_dict["lib64"],
                    self.__r_dir_dict["var"]))
                ])
            if global_config["ENABLE_PNP"]:
                main_values.extend([
                    #("host_perfdata_command"   , "process-host-perfdata"),
                    #("service_perfdata_command", "process-service-perfdata"),
                    ("service_perfdata_file", os.path.join(global_config["PNP_DIR"], "var/service-perfdata")),
                    ("service_perfdata_file_template", "DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$"),
                    ("service_perfdata_file_mode", "a"),
                    ("service_perfdata_file_processing_interval", "15"),
                    ("service_perfdata_file_processing_command", "process-service-perfdata-file"),
                    
                    ("host_perfdata_file", os.path.join(global_config["PNP_DIR"], "var/host-perfdata")),
                    ("host_perfdata_file_template", "DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$"),
                    ("host_perfdata_file_mode", "a"),
                    ("host_perfdata_file_processing_interval", "15"),
                    ("host_perfdata_file_processing_command" , "process-host-perfdata-file"),
                ])
            if global_config["ENABLE_NDO"]:
                if global_config["MD_TYPE"] == "nagios":
                    main_values.append(("*broker_module", "%s/ndomod-%dx.o config_file=%s/%s.cfg" % (
                        self.__r_dir_dict["bin"],
                        global_config["MD_VERSION"],
                        self.__r_dir_dict["etc"],
                        NDOMOD_NAME)))
                else:
                    if os.path.exists(os.path.join(self.__r_dir_dict["lib64"], "idomod.so")):
                        main_values.append(
                            ("*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                                self.__r_dir_dict["lib64"],
                                self.__r_dir_dict["etc"],
                                NDOMOD_NAME)))
                    else:
                        main_values.append(
                            ("*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                                self.__r_dir_dict["lib"],
                                self.__r_dir_dict["etc"],
                                NDOMOD_NAME)))
            main_values.append(
                ("event_broker_options"             , -1 if global_config["ENABLE_LIVESTATUS"] else global_config["EVENT_BROKER_OPTIONS"])
            )
        else:
            # add global event handlers
            main_values.extend([
                ("ochp_command"           , "ochp-command"),
                ("ocsp_command"           , "ocsp-command"),
                ("stalking_event_handlers_for_hosts"   , 1),
                ("stalking_event_handlers_for_services", 1),
            ])
        if global_config["MD_VERSION"] >= 3 or global_config["MD_TYPE"] == "icinga":
            main_values.extend([("object_cache_file"            , "%s/object.cache" % (self.__r_dir_dict["var"])),
                                ("use_large_installation_tweaks", "1"),
                                ("enable_environment_macros"    , "0"),
                                ("max_service_check_spread"     , global_config["MAX_SERVICE_CHECK_SPREAD"]),
                                ("max_host_check_spread"        , global_config["MAX_HOST_CHECK_SPREAD"]),
                                ])
        else:
            # values for Nagios 1.x, 2.x
            main_values.extend([("comment_file"                     , "%s/comment.log" % (self.__r_dir_dict["var"])),
                                ("downtime_file"                    , "%s/downtime.log" % (self.__r_dir_dict["var"]))])
        main_cfg = base_config(global_config["MAIN_CONFIG_NAME"],
                               is_host_file=True,
                               values=main_values)
        for log_descr, en in [("notifications" , 1), ("service_retries", 1), ("host_retries"     , 1),
                              ("event_handlers", 1), ("initial_states" , 0), ("external_commands", 1),
                              ("passive_checks", 1)]:
            main_cfg["log_%s" % (log_descr)] = en
        for to_descr, to in [("service_check", 60), ("host_check", 30), ("event_handler", 30),
                             ("notification" , 30), ("ocsp"      , 5 ), ("perfdata"     , 5 )]:
            main_cfg["%s_timeout" % (to_descr)] = to
        for th_descr, th in [("low_service", 5.0), ("high_service", 20.0),
                             ("low_host"   , 5.0), ("high_host"   , 20.0)]:
            main_cfg["%s_flap_threshold" % (th_descr)] = th
        def_user = "%sadmin" % (global_config["MD_TYPE"])
        cgi_config = base_config("cgi",
                                 is_host_file=True,
                                 values=[("main_config_file"         , "%s/%s.cfg" % (
                                     self.__r_dir_dict["etc"], global_config["MAIN_CONFIG_NAME"])),
                                         ("physical_html_path"       , "%s" % (self.__r_dir_dict["share"])),
                                         ("url_html_path"            , "/%s" % (global_config["MD_TYPE"])),
                                         ("show_context_help"        , 0),
                                         ("use_authentication"       , 1),
                                         #("default_user_name"        , def_user),
                                         ("default_statusmap_layout" , 5),
                                         ("default_statuswrl_layout" , 4),
                                         ("refresh_rate"             , 60),
                                         ("lock_author_name"         , 1),
                                         ("authorized_for_system_information"        , def_user),
                                         ("authorized_for_system_commands"           , def_user),
                                         ("authorized_for_configuration_information" , def_user),
                                         ("authorized_for_all_hosts"                 , def_user),
                                         ("authorized_for_all_host_commands"         , def_user),
                                         ("authorized_for_all_services"              , def_user),
                                         ("authorized_for_all_service_commands"      , def_user)] + 
                                 [("tac_show_only_hard_state", 1)] if (global_config["MD_TYPE"] == "icinga" and global_config["MD_RELEASE"] >= 6) else [])
        if sql_suc:
            pass
        else:
            self.log("Error reading SQL-config %s" % (sql_file), logging_tools.LOG_LEVEL_ERROR)
        self[main_cfg.get_name()] = main_cfg
        self[ndomod_cfg.get_name()] = ndomod_cfg
        if ndo2db_cfg:
            self[ndo2db_cfg.get_name()] = ndo2db_cfg
        self[cgi_config.get_name()] = cgi_config
        self[resource_cfg.get_name()] = resource_cfg
        if self.master:
            # wsgi config
            if os.path.isfile("/etc/debian_version"):
                www_user, www_group = ("apache", "apache")
            else:
                www_user, www_group = ("wwwrun", "www")
            wsgi_config = base_config(
                "wsgi",
                is_host_file=True,
                headers=["[uwsgi]"],
                values=[
                    ("chdir"           , self.__r_dir_dict[""]),
                    ("plugin-dir"      , "/opt/cluster/lib64"),
                    ("cgi-mode"        , "true"),
                    ("master"          , "true"),
                    ("vacuum"          , "true"),
                    ("workers"         , 16),
                    ("harakiri-verbose", 1),
                    ("plugins"         , "cgi"),
                    ("socket"          , os.path.join(self.__r_dir_dict["var"], "uwsgi.sock")),
                    ("uid"             , www_user),
                    ("gid"             , www_group),
                    ("cgi"             , self.__r_dir_dict["sbin"]),
                    ("no-default-app"  , "true"),
                    ("pidfile"         , os.path.join(self.__r_dir_dict["var"], "wsgi.pid")),
                    ("daemonize"       , os.path.join(self.__r_dir_dict["var"], "wsgi.log")),
                    ("chown-socket"    , www_user),
                    ("no-site"         , "true"),
                    #("route"           , "^/icinga/cgi-bin basicauth:Monitor,init:init"),
                ])
            self[wsgi_config.get_name()] = wsgi_config
        if global_config["ENABLE_NAGVIS"] and self.master:
            self._create_nagvis_base_entries()
    def _create_access_entries(self):
        if self.master:
            self.log("creating http_users.cfg file")
            # create htpasswd
            htp_file = os.path.join(self.__r_dir_dict["etc"], "http_users.cfg")
            file(htp_file, "w").write("\n".join(
                ["%s:{SSHA}%s" % (
                    cur_u.login,
                    cur_u.password_ssha.split(":", 1)[1]) for cur_u in user.objects.filter(Q(active=True))] + [""]))
            if global_config["ENABLE_NAGVIS"]:
                # modify auth.db
                auth_db = os.path.join(global_config["NAGVIS_DIR"], "etc", "auth.db")
                self.log("modifying authentication info in %s" % (auth_db))
                try:
                    conn = sqlite3.connect(auth_db)
                except:
                    self.log("cannot create connection: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    cur_c = conn.cursor()
                    cur_c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    # tables
                    all_tables = [value[0] for value in cur_c.fetchall()]
                    self.log("found %s: %s" % (logging_tools.get_plural("table", len(all_tables)),
                                               ", ".join(sorted(all_tables))))
                    # delete previous users
                    cur_c.execute("DELETE FROM users2roles")
                    cur_c.execute("DELETE FROM users")
                    cur_c.execute("DELETE FROM roles")
                    cur_c.execute("DELETE FROM roles2perms")
                    admin_role_id = cur_c.execute("INSERT INTO roles VALUES(Null, 'admins')").lastrowid
                    perms_dict = dict([("%s.%s.%s" % (
                        cur_perm[1].lower(),
                        cur_perm[2].lower(),
                        cur_perm[3].lower()), cur_perm[0]) for cur_perm in cur_c.execute("SELECT * FROM perms")])
                    #pprint.pprint(perms_dict)
                    cur_c.execute("INSERT INTO roles2perms VALUES(%d, %d)" % (
                        admin_role_id,
                        perms_dict["*.*.*"]))
                    role_dict = dict([(cur_role[1].lower().split()[0], cur_role[0]) for cur_role in cur_c.execute("SELECT * FROM roles")])
                    self.log("role dict: %s" % (", ".join(["%s=%d" % (key, value) for key, value in role_dict.iteritems()])))
                    # get nagivs root points
                    nagvis_rds = device.objects.filter(Q(automap_root_nagvis=True)).select_related("device_group")
                    self.log("%s: %s" % (logging_tools.get_plural("NagVIS root device", len(nagvis_rds)),
                                         ", ".join([unicode(cur_dev) for cur_dev in nagvis_rds])))
                    devg_lut = {}
                    for cur_dev in nagvis_rds:
                        devg_lut.setdefault(cur_dev.device_group.pk, []).append(cur_dev.name)
                    for cur_u in user.objects.filter(Q(active=True)).prefetch_related("allowed_device_groups"):
                        # check for admin
                        if User.objects.get(Q(username=cur_u.login)).has_perm("backbone.all_devices"):
                            target_role = "admins"
                        else:
                            # create special role
                            target_role = cur_u.login
                            role_dict[target_role] = cur_c.execute("INSERT INTO roles VALUES(Null, '%s')" % (cur_u.login)).lastrowid
                            add_perms = ["auth.logout.*", "overview.view.*", "general.*.*", "user.setoption.*"]
                            for cur_devg in cur_u.allowed_device_groups.values_list("pk", flat=True):
                                for dev_name in devg_lut.get(cur_devg, []):
                                    perm_name = "map.view.%s" % (dev_name)
                                    if perm_name not in perms_dict:
                                        perms_dict[perm_name] = cur_c.execute("INSERT INTO perms VALUES(Null, '%s', '%s', '%s')" % (
                                            perm_name.split(".")[0].title(),
                                            perm_name.split(".")[1],
                                            perm_name.split(".")[2]
                                        )).lastrowid
                                        self.log("permission '%s' has id %d" % (perm_name, perms_dict[perm_name]))
                                    add_perms.append(perm_name)
                            # add perms
                            for new_perm in add_perms:
                                cur_c.execute("INSERT INTO roles2perms VALUES(%d, %d)" % (
                                    role_dict[target_role],
                                    perms_dict[new_perm]))
                            self.log("creating new role '%s' with perms %s" % (
                                target_role,
                                ", ".join(add_perms)
                            ))
                        self.log("creating user '%s' with role %s" % (
                            unicode(cur_u),
                            target_role,
                        ))
                        new_userid = cur_c.execute("INSERT INTO users VALUES(Null, '%s', '%s')" % (
                            cur_u.login,
                            binascii.hexlify(base64.b64decode(cur_u.password.split(":", 1)[1])),
                        )).lastrowid
                        cur_c.execute("INSERT INTO users2roles VALUES(%d, %d)" % (
                            new_userid,
                            role_dict[target_role],
                        ))
                    conn.commit()
                    conn.close()
    def _write_entries(self):
        cfg_written, empty_cfg_written = ([], [])
        start_time = time.time()
        for key, stuff in self.__dict.iteritems():
            if isinstance(stuff, base_config) or isinstance(stuff, host_type_config):
                act_cfg_name = os.path.normpath("%s/%s.cfg" % (self.__w_dir_dict["etc"], key))
                stuff.create_content()
                if stuff.act_content != stuff.old_content:
                    try:
                        codecs.open(act_cfg_name, "w", "Utf-8").write(u"\n".join(stuff.act_content + [u""]))
                    except IOError:
                        self.log("Error writing content of %s to %s: %s" % (key, act_cfg_name, process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_CRITICAL)
                        stuff.act_content = []
                    else:
                        os.chmod(act_cfg_name, 0644)
                        cfg_written.append(key)
                elif not os.path.isfile(act_cfg_name) and not stuff.act_content:
                    empty_cfg_written.append(act_cfg_name)
                    self.log("creating empty file %s" % (act_cfg_name),
                             logging_tools.LOG_LEVEL_WARN)
                    open(act_cfg_name, "w").write("\n")
                else:
                    # no change
                    pass
        end_time = time.time()
        if cfg_written:
            self.log("wrote %s (%s) in %s" % (logging_tools.get_plural("config_file", len(cfg_written)),
                                              ", ".join(cfg_written),
                                              logging_tools.get_diff_time_str(end_time - start_time)))
        else:
            self.log("no config files written")
        return len(cfg_written) + len(empty_cfg_written)
    def has_config(self, config_name):
        return self.has_key(config_name)
    def get_config(self, config_name):
        return self[config_name]
    def add_config(self, config):
        if self.has_config(config.get_name()):
            config.set_previous_config(self.get_config(config.get_name()))
        self[config.get_name()] = config
    def __setitem__(self, key, value):
        self.__dict[key] = value
        config_keys = self.__dict.keys()
        new_keys = sorted(["%s/%s.cfg" % (self.__r_dir_dict["etc"], key) for key, value in self.__dict.iteritems() if not isinstance(value, base_config) or not (value.is_host_file or value.belongs_to_ndo)])
        old_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"]
        if old_keys != new_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"] = new_keys
            self._write_entries()
    def __getitem__(self, key):
        return self.__dict[key]

class base_config(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.__dict, self.__key_list = ({}, [])
        self.is_host_file   = kwargs.get("is_host_file", False)
        self.belongs_to_ndo = kwargs.get("belongs_to_ndo", False)
        self.headers = kwargs.get("headers", [])
        for key, value in kwargs.get("values", []):
            self[key] = value
        self.act_content = []
    def get_name(self):
        return self.__name
    def __setitem__(self, key, value):
        if key.startswith("*"):
            key, multiple = (key[1:], True)
        else:
            multiple = False
        if key not in self.__key_list:
            self.__key_list.append(key)
        if multiple:
            self.__dict.setdefault(key, []).append(value)
        else:
            self.__dict[key] = value
    def __getitem__(self, key):
        return self.__dict[key]
    def create_content(self):
        self.old_content = self.act_content
        c_lines = []
        last_key = None
        for key in self.__key_list:
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self.__dict[key]
            if type(value) == list:
                pass
            elif type(value) in [int, long]:
                value = [str(value)]
            else:
                value = [value]
            for act_v in value:
                c_lines.append("%s=%s" % (key, act_v))
        self.act_content = self.headers + c_lines
        
class nag_config(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.entries = {}
        self.keys = []
        for key, value in kwargs.iteritems():
            self[key] = value
    def __setitem__(self, key, value):
        if key in self.keys:
            val_p = self.entries[key].split(",")
            if "-" in val_p:
                val_p.remove("-")
            if value not in val_p:
                val_p.append(value)
            self.entries[key] = ",".join(val_p)
        else:
            self.keys.append(key)
            self.entries[key] = value
    def pop_entry(self, key):
        val = self.entries[key]
        del self.entries[key]
        self.keys.remove(key)
        return val
    def __getitem__(self, key):
        if key == "name":
            return self.__name
        else:
            return self.entries[key]
    def has_key(self, key):
        return self.entries.has_key(key)
    def __delitem__(self, key):
        del self.entries[key]
        del self.keys[self.keys.index(key)]

class host_type_config(object):
    def __init__(self, build_process):
        self.__build_proc = build_process
        self.act_content, self.prev_content = ([], [])
    def is_valid(self):
        return True
    def create_content(self):
        #if self.act_content:
        self.old_content = self.act_content
        #bla_idx, self.act_content = self.get_content()
        self.act_content = self.get_simple_content()
    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, level)
    def get_simple_content(self):
        cn = self.get_name()
        act_list = self.get_object_list()
        dest_type = self.get_name()
        content = []
        if act_list:
            for act_le in act_list:
                content.extend(["define %s {" % (dest_type)] + \
                               ["  %s %s" % (act_key, val) for act_key, val in act_le.entries.iteritems()] + \
                               ["}", ""])
            self.log("created %s for %s" % (logging_tools.get_plural("entry", len(act_list)),
                                            dest_type))
        return content
    def get_content(self, upper_idx=0):
        cn = self.get_name()
        act_list = self.get_object_list()
        content = []
        log_lines = []
        if act_list:
            dest_type = self.get_name()
            last_key = "%s_name" % (dest_type)
            start_time = time.time()
            log_lines.append("Generating config for '%s', type '%s' ... " % (cn, dest_type or "<not set>"))
            index_key_dict = {}
            act_key_idx = 0
            key_hash_list, key_hash_dict = ([], {})
            for act_le in act_list:
                local_key_hash = []
                for key, value in [(a, b) for a, b in act_le.entries.iteritems() if a not in ["possible_parents"]]:
                    if key not in index_key_dict.keys():
                        index_key_dict[key] = ".%d" % (act_key_idx)
                        act_key_idx += 1
                    local_key_hash.append(index_key_dict[key])
                local_key_hash.sort()
                local_key_hash = "".join(local_key_hash)
                if local_key_hash not in key_hash_list:
                    key_hash_list.append(local_key_hash)
                key_hash_idx = key_hash_list.index(local_key_hash)
                key_hash_dict.setdefault(key_hash_idx, []).append(act_le)
            for hash_idx, obj_list in key_hash_dict.iteritems():
                loc_list = [x for x in obj_list]
                all_keys_dict = {}
                for act_obj in obj_list:
                    for key, value in act_obj.entries.iteritems():
                        all_keys_dict.setdefault(key, {}).setdefault(value, 0)
                        all_keys_dict[key][value] += 1
                key_div_dict = {}
                for key, value in all_keys_dict.iteritems():
                    key_div_dict.setdefault(max(value.values()), []).append(key)
                # all diversities, reverse sorted (highest to lowest)
                all_divs = sorted(key_div_dict.keys(), reverse=True)
                sorted_keys = sum([key_div_dict[x] for x in all_divs], [])
                if last_key in sorted_keys:
                    sorted_keys.remove(last_key)
                    sorted_keys.append(last_key)
                log_lines.append("Key list is %s, last key is %s" % (", ".join(sorted_keys), last_key))
                # config tree
                upper_idx = self._add_leafs(content, dest_type, sorted_keys, all_keys_dict, upper_idx, upper_idx, 1, loc_list, [])
            end_time = time.time()
            diff_time = end_time - start_time
            log_lines.append(" - took %s" % (logging_tools.get_diff_time_str(diff_time)))
        # log_lines
        #for log_line in log_lines:
        #    self.log(log_line)
        return upper_idx, content
    def _add_leafs(self, content, c_type, in_list, ak_dict, mother_service, start_idx, first_entry, loc_list, add_lines):
        my_idx = start_idx
        act_key = in_list[0]
        iter_list = []
        for val in ak_dict[act_key].keys():
            act_list = sorted([x for x in loc_list if x.entries[act_key] == val])
            if act_list:
                iter_list.append((val, act_list))
        if len(in_list) > 1:
            meta_def = len(iter_list) == 1
            for val, act_list in iter_list:
                if len(act_list) == 1 or meta_def:
                    my_idx = self._add_leafs(content, c_type, in_list[1:], ak_dict, mother_service, my_idx, first_entry, act_list, add_lines + ["  %s %s" % (act_key, val)])
                else:
                    my_idx += 1
                    content.extend(["define %s {" % (c_type),
                                    "  register 0",
                                    "  name %s_%d" % (TEMPLATE_NAME, my_idx),
                                    "  %s %s" % (act_key, val)] + \
                                   (not first_entry and ["  use %s_%d" % (TEMPLATE_NAME, mother_service)] or []) + \
                                   add_lines + ["}", ""])
                    my_idx = self._add_leafs(content, c_type, in_list[1:], ak_dict, my_idx, my_idx, 0, act_list, [])
        else:
            val_list = sorted([x for x, y in iter_list])
            if act_key == "host_name":
                content.extend(["define %s {" % (c_type)] + \
                               (not first_entry and ["  use %s_%d" % (TEMPLATE_NAME, mother_service)] or []) + \
                               add_lines + ["  %s %s" % (act_key, ",".join(val_list)), "}", ""])
            else:
                for val in val_list:
                    content.extend(["define %s {" % (c_type)] + \
                                   (not first_entry and ["  use %s_%d" % (TEMPLATE_NAME, mother_service)] or []) + \
                                   add_lines + ["  %s %s" % (act_key, val), "}", ""])
        return my_idx
    
class time_periods(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_time_periods_from_db()
    def get_name(self):
        return "timeperiod"
    def _add_time_periods_from_db(self):
        for cur_per in mon_period.objects.all():
            nag_conf = nag_config(cur_per.name,
                                  timeperiod_name=cur_per.name,
                                  alias=cur_per.alias or "-")
            for short_s, long_s in [
                ("mon", "monday"), ("tue", "tuesday" ), ("wed", "wednesday"), ("thu", "thursday"),
                ("fri", "friday"), ("sat", "saturday"), ("sun", "sunday"   )]:
                nag_conf[long_s] = getattr(cur_per, "%s_range" % (short_s))
            self.__dict[cur_per.pk] = nag_conf
            self.__obj_list.append(nag_conf)
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_servicegroups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        # dict : which host has which service_group defined
        self.__host_srv_lut = {}
        self._add_servicegroups_from_db()
    def get_name(self):
        return "servicegroup"
    def _add_servicegroups_from_db(self):
        for cur_cct in mon_check_command_type.objects.all():
            nag_conf = nag_config(cur_cct.name,
                                  servicegroup_name=cur_cct.name,
                                  alias="%s group" % (cur_cct.name))
            self.__host_srv_lut[cur_cct.name] = set()
            self.__dict[cur_cct.pk] = nag_conf
            self.__obj_list.append(nag_conf)
    def clear_host(self, host_name):
        for key, value in self.__host_srv_lut.iteritems():
            if host_name in value:
                value.remove(host_name)
    def add_host(self, host_name, srv_group):
        self.__host_srv_lut[srv_group].add(host_name)
    def get_object_list(self):
        return [obj for obj in self.__obj_list if self.__host_srv_lut[obj["name"]]]
    def values(self):
        return self.__dict.values()
    
class all_commands(host_type_config):
    def __init__(self, gen_conf, build_proc):
        check_command.gen_conf = gen_conf
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_notify_commands()
        self._add_commands_from_db(gen_conf)
    def get_name(self):
        return "command"
    def _add_notify_commands(self):
        try:
            cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            cluster_name = "N/A"
        else:
            dv = cluster_location.db_device_variable(cdg, "CLUSTER_NAME", description="name of the cluster")
            if not dv.is_set():
                dv.set_value("new_cluster")
                dv.update()
            cluster_name = dv.get_value()
        md_vers = global_config["MD_VERSION_STRING"]
        md_type = global_config["MD_TYPE"]
        if os.path.isfile("/usr/local/sbin/send_mail.py"):
            send_mail_prog = "/usr/local/sbin/send_mail.py"
        else:
            send_mail_prog = "/usr/local/bin/send_mail.py"
        from_addr = "%s@%s" % (global_config["MD_TYPE"],
                               global_config["FROM_ADDR"])
        # Nagios V2.x
        nag_conf = nag_config("notify-by-email",
                              command_name="notify-by-email",
                              command_line=r"%s -f '%s' -s '$NOTIFICATIONTYPE$ alert - $HOSTNAME$@%s ($HOSTALIAS$)/$SERVICEDESC$ is $SERVICESTATE$' -t $CONTACTEMAIL$ '***** %s %s *****\n\n" % (
                                  send_mail_prog,
                                  from_addr,
                                  cluster_name,
                                  md_type,
                                  md_vers) + \
                              r"Notification Type: $NOTIFICATIONTYPE$\n\nCluster: %s\nService: $SERVICEDESC$\nHost   : $HOSTALIAS$\nAddress: $HOSTADDRESS$\n" % (cluster_name) + \
                              r"State  : $SERVICESTATE$\n\nDate/Time: $LONGDATETIME$\n\nAdditional Info:\n\n$SERVICEOUTPUT$'")
        self.__obj_list.append(nag_conf)
        nag_conf = nag_config("notify-by-sms",
                              command_name="notify-by-sms",
                              command_line="/opt/icinga/bin/sendsms $CONTACTPAGER$ '$NOTIFICATIONTYPE$ alert - $SERVICEDESC$ is $SERVICESTATE$ on $HOSTNAME$'")
        self.__obj_list.append(nag_conf)
        nag_conf = nag_config("host-notify-by-email",
                              command_name="host-notify-by-email",
                              command_line=r"%s -f '%s'  -s 'Host $HOSTSTATE$ alert for $HOSTNAME$@%s' -t $CONTACTEMAIL$ '***** %s %s *****\n\n" % (
                                  send_mail_prog,
                                  from_addr,
                                  cluster_name,
                                  md_type,
                                  md_vers) + \
                              r"Notification Type: $NOTIFICATIONTYPE$\n\nCluster: %s\nHost   : $HOSTNAME$\nState  : $HOSTSTATE$\nAddress: $HOSTADDRESS$\nInfo   : $HOSTOUTPUT$\n\nDate/Time: $LONGDATETIME$'" % (cluster_name))
        self.__obj_list.append(nag_conf)
        nag_conf = nag_config("host-notify-by-sms",
                              command_name="host-notify-by-sms",
                              command_line="/opt/icinga/bin/sendsms $CONTACTPAGER$ '$HOSTSTATE$ alert for $HOSTNAME$ ($HOSTADDRESS$)'")
        self.__obj_list.append(nag_conf)
    def _add_commands_from_db(self, gen_conf):
        ngc_re1 = re.compile("^\@(?P<special>\S+)\@(?P<comname>\S+)$")
        check_coms = list(mon_check_command.objects.all().select_related("mon_check_command_type",
                                                                         "mon_service_templ"))
        if global_config["ENABLE_PNP"] and gen_conf.master:
            check_coms += [
                mon_check_command(
                    name="process-service-perfdata-file",
                    command_line="/usr/bin/perl %s/lib/process_perfdata.pl --bulk=%s/var/service-perfdata" % (
                        global_config["PNP_DIR"],
                        global_config["PNP_DIR"]
                        ),
                    description="Process service performance data",
                    ),
                mon_check_command(
                    name="process-host-perfdata-file",
                    command_line="/usr/bin/perl %s/lib/process_perfdata.pl  --bulk=%s/var/host-perfdata" % (
                        global_config["PNP_DIR"],
                        global_config["PNP_DIR"]),
                    description="Process host performance data",
                    ),
            ]
        command_names = set()
        for ngc in check_coms + [
            mon_check_command(
                name="check-host-alive",
                command_line="$USER2$ -m localhost ping $HOSTADDRESS$ %d %.2f" % (
                    global_config["CHECK_HOST_ALIVE_PINGS"],
                    global_config["CHECK_HOST_ALIVE_TIMEOUT"]),
                description="Check-host-alive command via ping",
                enable_perfdata=global_config["ENABLE_PNP"],
                ),
            mon_check_command(
                name="check-host-ok",
                command_line="$USER1$/check_dummy 0 up",
                description="Check-host-ok, always up",
                enable_perfdata=False,
                ),
            mon_check_command(
                name="check-host-down",
                command_line="$USER1$/check_dummy 2 down",
                description="Check-host-down, always down",
                enable_perfdata=False,
                ),
            mon_check_command(
                name="check-host-alive-2",
                command_line="$USER2$ -m $HOSTADDRESS$ version",
                description="Check-host-alive command via collserver",
                enable_perfdata=global_config["ENABLE_PNP"],
                ),
            mon_check_command(
                name="ochp-command",
                command_line="$USER2$ -m DIRECT -s ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"%s\"" % ("$HOSTOUTPUT$|$HOSTPERFDATA$" if global_config["ENABLE_PNP"] else "$HOSTOUTPUT$"),
                description="OCHP Command"
                ),
            mon_check_command(
                name="ocsp-command",
                command_line="$USER2$ -m DIRECT -s ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"%s\" " % ("$SERVICEOUTPUT$|$SERVICEPERFDATA$" if global_config["ENABLE_PNP"] else "$SERVICEOUTPUT$"),
                description="OCSP Command"
                ),
            mon_check_command(
                name="check_service_cluster",
                command_line="$USER1$/check_cluster --service -l $ARG1$ -w $ARG2$ -c $ARG3$ -d $ARG4$",
                description="Check Service Cluster"
                ),
            mon_check_command(
                name="check_host_cluster",
                command_line="$USER1$/check_cluster --host -l $ARG1$ -w $ARG2$ -c $ARG3$ -d $ARG4$",
                description="Check Host Cluster"
                ),
            ]:
            #pprint.pprint(ngc)
            # build / extract ngc_name
            re1m = ngc_re1.match(ngc.name)
            if re1m:
                ngc_name, special = (re1m.group("comname"), re1m.group("special"))
            else:
                ngc_name, special = (ngc.name, None)
            name_postfix = 0
            while True:
                if ngc_name not in command_names:
                    break
                else:
                    name_postfix += 1
                    if "%s_%d" % (ngc_name, name_postfix) not in command_names:
                        break
            if name_postfix:
                ngc_name = "%s_%d" % (ngc_name, name_postfix)
            command_names.add(ngc_name)
            cc_s = check_command(ngc_name,
                                 ngc.command_line,
                                 ngc.config.name if ngc.config_id else None,
                                 ngc.mon_service_templ.name if ngc.mon_service_templ_id else None,
                                 ngc.description,
                                 ngc.device_id,
                                 special,
                                 servicegroup_name=ngc.mon_check_command_type.name if ngc.mon_check_command_type_id else "other",
                                 enable_perfdata=ngc.enable_perfdata)
            nag_conf = cc_s.get_nag_config()
            self.__obj_list.append(nag_conf)
            self.__dict[nag_conf["command_name"]] = cc_s
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
    def __getitem__(self, key):
        return self.__dict[key]
    
class all_contacts(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_contacts_from_db(gen_conf)
    def get_name(self):
        return "contact"
    def _add_contacts_from_db(self, gen_conf):
        for contact in mon_contact.objects.all().select_related("user"):
            full_name = ("%s %s" % (contact.user.first_name, contact.user.last_name)).strip().replace(" ", "_")
            if not full_name:
                full_name = contact.user.login
            hn_command = contact.hncommand
            sn_command = contact.sncommand
            if len(contact.user.pager) > 5:
                # check for pager number
                hn_command = "%s,host-notify-by-sms" % (hn_command)
                sn_command = "%s,notify-by-sms" % (sn_command)
            nag_conf = nag_config(
                full_name,
                contact_name=contact.user.login,
                host_notification_period=gen_conf["timeperiod"][contact.hnperiod_id]["name"],
                service_notification_period=gen_conf["timeperiod"][contact.snperiod_id]["name"],
                host_notification_commands=hn_command,
                service_notification_commands=sn_command,
                alias=contact.user.comment or full_name)
            for targ_opt, pairs in [
                ("host_notification_options"   , [("hnrecovery", "r"), ("hndown"    , "d"), ("hnunreachable", "u")]),
                ("service_notification_options", [("snrecovery", "r"), ("sncritical", "c"), ("snwarning"    , "w"), ("snunknown", "u")])]:
                act_a = []
                for long_s, short_s in pairs:
                    if getattr(contact, long_s):
                        act_a.append(short_s)
                if not act_a:
                    act_a = ["n"]
                nag_conf[targ_opt] = ",".join(act_a)
            u_mail = contact.user.email or "root@localhost"
            nag_conf["email"] = u_mail
            nag_conf["pager"] = contact.user.pager or "----"
            self.__obj_list.append(nag_conf)
            self.__dict[contact.pk] = nag_conf
        # add all contacts not used in mon_contacts but somehow related to a device (and active)
        for std_user in user.objects.filter(Q(mon_contact=None) & (Q(active=True))):
            devg_ok = len(std_user.allowed_device_groups.all()) > 0 or User.objects.get(Q(username=std_user.login)).has_perm("backbone.all_devices")
            if devg_ok:
                full_name = ("%s %s" % (std_user.first_name, std_user.last_name)).strip().replace(" ", "_") or std_user.login
                nag_conf = nag_config(
                    full_name,
                    contact_name=std_user.login,
                    alias=std_user.comment or full_name,
                    host_notifications_enabled=0,
                    service_notifications_enabled=0,
                    host_notification_commands="host-notify-by-email",
                    service_notification_commands="notify-by-email",
                )
                self.__obj_list.append(nag_conf)
                #self.__dict[contact.pk] = nag_conf
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_contact_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_contact_groups_from_db(gen_conf)
    def get_name(self):
        return "contactgroup"
    def _add_contact_groups_from_db(self, gen_conf):
        # none group
        self.__dict[0] = nag_config(global_config["NONE_CONTACT_GROUP"],
                                    contactgroup_name=global_config["NONE_CONTACT_GROUP"],
                                    alias="None group")
        for cg_group in mon_contactgroup.objects.all().prefetch_related("members"):
            nag_conf = nag_config(cg_group.name,
                                  contactgroup_name=cg_group.name,
                                  alias=cg_group.alias)
            self.__dict[cg_group.pk] = nag_conf
            for member in cg_group.members.all():
                nag_conf["members"] = gen_conf["contact"][member.pk]["contact_name"]
        self.__obj_list = self.__dict.values()
    def has_key(self, key):
        return self.__dict.has_key(key)
    def keys(self):
        return self.__dict.keys()
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_host_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_host_groups_from_db(gen_conf)
    def get_name(self):
        return "hostgroup"
    def _add_host_groups_from_db(self, gen_conf):
        if gen_conf.has_key("host"):
            all_hosts_written = gen_conf["host"].keys()
            filter_obj = Q(name__in=all_hosts_written)
            #sql_add_str = " OR ".join(["d.name='%s'" % (x) for x in all_hosts_written])
            # hostgroups
            if all_hosts_written:
                # distinct is important here
                for h_group in device_group.objects.filter(Q(device_group__name__in=all_hosts_written)).prefetch_related("device_group").distinct():
                    nag_conf = nag_config(h_group.name,
                                          hostgroup_name=h_group.name,
                                          alias=h_group.description or h_group.name,
                                          members="-")
                    self.__dict[h_group.pk] = nag_conf
                    self.__obj_list.append(nag_conf)
                    nag_conf["members"] = ",".join(h_group.device_group.filter(Q(name__in=all_hosts_written)).values_list("name", flat=True))
            else:
                self.log("empty SQL-Str for in _add_host_groups_from_db()",
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no host-dict found in gen_dict",
                     logging_tools.LOG_LEVEL_WARN)
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_hosts(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        #self._add_hosts_from_db(gen_conf)
    def get_name(self):
        return "host"
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
    def __setitem__(self, key, value):
        self.__dict[key] = value
        self.__obj_list.append(value)
    def __delitem__(self, key):
        self.__obj_list.remove(self.__dict[key])
        del self.__dict[key]
    def has_key(self, key):
        return self.__dict.has_key(key)
    def keys(self):
        return self.__dict.keys()
    #def _add_hosts_from_db(self, gen_conf):
    #    pass
    
class all_hosts_extinfo(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_hosts_from_db(gen_conf)
    def get_name(self):
        return "hostextinfo"
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
    def __setitem__(self, key, value):
        self.__dict[key] = value
        self.__obj_list.append(value)
    def __delitem__(self, key):
        self.__obj_list.remove(self.__dict[key])
        del self.__dict[key]
    def has_key(self, key):
        return self.__dict.has_key(key)
    def keys(self):
        return self.__dict.keys()
    def _add_hosts_from_db(self, gen_conf):
        pass
    
class all_services(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_services_from_db(gen_conf)
    def get_name(self):
        return "service"
    def get_object_list(self):
        return self.__obj_list
    def append(self, value):
        self.__obj_list.append(value)
    def extend(self, value):
        self.__obj_list.extend(value)
    def values(self):
        return self.__obj_list
    def remove_host(self, host_obj):
        self.__obj_list.remove(host_obj)
    def _add_services_from_db(self, gen_conf):
        pass
    
class check_command(object):
    def __init__(self, name, com_line, config, template, descr, device=0, special=None, **kwargs):
        self.__name = name
        self.__com_line = com_line
        self.config = config
        self.template = template
        self.device = device
        self.servicegroup_name = kwargs.get("servicegroup_name", "other")
        self.__descr = descr.replace(",", ".")
        self.enable_perfdata = kwargs.get("enable_perfdata", False)
        self.__special = special
        self._generate_md_com_line()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        check_command.gen_conf.log("[cc %s] %s" % (self.__name, what), log_level)
    @property
    def command_line(self):
        return self.__com_line
    @property
    def md_command_line(self):
        return self.__md_com_line
    def get_num_args(self):
        return self.__num_args
    def get_default_value(self, arg_name, def_value):
        return self.__default_values.get(arg_name, def_value)
    def _generate_md_com_line(self):
        """
        parses command line, also builds argument lut
        lut format: commandline switch -> ARG#
        list format : ARG#, ARG#, ...
        """
        self.__num_args, self.__default_values = (0, {})
        arg_lut, arg_list = ({}, [])
        # parse command_line
        com_parts, new_parts = (self.command_line.split(), [])
        prev_part = None
        for com_part in com_parts:
            try:
                """
                handle the various input formats:
                
                ${ARG#:var_name:default}
                ${ARG#:var_name:default}$
                ${ARG#:default}
                ${ARG#:default}$
                """
                if com_part.startswith("${") and (com_part.endswith("}") or com_part.endswith("}$")):
                    if com_part.endswith("}$"):
                        com_part = com_part[2:-2]
                    else:
                        com_part = com_part[2:-1]
                    if com_part.count(":") == 2:
                        arg_name, var_name, default_value = com_part.split(":")
                    elif com_part.count(":") == 1:
                        arg_name, default_value = com_part.split(":")
                        var_name = None
                    else:
                        arg_name = com_part
                        default_value, var_name = (None, None)
                    if prev_part:
                        arg_lut[prev_part] = arg_name
                    else:
                        arg_list.append(arg_name)
                    new_parts.append("$%s$" % (arg_name))
                    if var_name:
                        self.__default_values[arg_name] = (var_name, default_value)
                    elif default_value is not None:
                        self.__default_values[arg_name] = default_value
                    self.__num_args += 1
                    prev_part = None
                elif com_part.startswith("$ARG") and com_part.endswith("$"):
                    arg_name = com_part[1:-1]
                    if prev_part:
                        arg_lut[prev_part] = arg_name
                    else:
                        arg_list.append(arg_name)
                    new_parts.append(com_part)
                    self.__num_args += 1
                    prev_part = None
                else:
                    new_parts.append(com_part)
                    prev_part = com_part
            except:
                # need some logging, FIXME
                new_parts.append(com_part)
        self.__md_com_line = " ".join(new_parts)
        self.log("command_line in  is '%s'" % (self.command_line))
        self.log("command_line out is '%s'" % (self.md_command_line))
        self.log("lut : %s; %s" % (
            logging_tools.get_plural("key", len(arg_lut)),
            ", ".join(["'%s' => '%s'" % (key, value) for key, value in arg_lut.iteritems()])
        ))
        self.log("list: %s; %s" % (
            logging_tools.get_plural("item", len(arg_list)),
            ", ".join(arg_list)
        ))
        self.__arg_lut, self.__arg_list = (arg_lut, arg_list)
    def correct_argument_list(self, arg_temp, dev_variables):
        out_list = []
        for arg_name in arg_temp.argument_names:
            value = arg_temp[arg_name]
            if self.__default_values.has_key(arg_name) and not value:
                dv_value = self.__default_values[arg_name]
                if type(dv_value) == tuple:
                    # var_name and default_value
                    var_name = self.__default_values[arg_name][0]
                    if dev_variables.has_key(var_name):
                        value = dev_variables[var_name]
                    else:
                        value = self.__default_values[arg_name][1]
                else:
                    # only default_value
                    value = self.__default_values[arg_name]
            if type(value) in [int, long]:
                out_list.append("%d" % (value))
            else:
                out_list.append(value)
        return out_list
    def get_nag_config(self):
        return nag_config(self.__name,
                          command_name=self.__name,
                          command_line=self.md_command_line)
    def __getitem__(self, k):
        if k == "command_name":
            return self.__name
    def get_device(self):
        return self.device
    def get_special(self):
        return self.__special
    def get_config(self):
        return self.config
    def get_template(self, default):
        if self.template:
            return self.template
        else:
            return default
    def get_description(self):
        if self.__descr:
            return self.__descr
        else:
            return self.__name
    @property
    def name(self):
        return self.__name
    @property
    def arg_ll(self):
        """
        returns lut and list 
        """
        return (self.__arg_lut, self.__arg_list)
    def __repr__(self):
        return "%s [%s]" % (self.__name, self.command_line)
        
class device_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = None
        for dev_templ in mon_device_templ.objects.all():
            self[dev_templ.pk] = dev_templ
            if dev_templ.is_default:
                self.__default = dev_templ
        self.log("Found %s (%s)" % (logging_tools.get_plural("device_template", len(self.keys())),
                                    ", ".join([cur_dt.name for cur_dt in self.itervalues()])))
        if self.__default:
            self.log("Found default device_template named '%s'" % (self.__default.name))
        else:
            if self.keys():
                self.__default = self.values()[0]
                self.log("No default device_template found, using '%s'" % (self.__default.name),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("No device_template founds, skipping configuration....",
                         logging_tools.LOG_LEVEL_ERROR)
    def is_valid(self):
        return self.__default and True or False
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[device_templates] %s" % (what), level)
    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if not self.has_key(act_key):
            self.log("key %s not known, using default %s (%d)" % (
                str(act_key),
                unicode(self.__default),
                self.__default.pk),
                     logging_tools.LOG_LEVEL_ERROR)
            act_key = self.__default.pk
        return super(device_templates, self).__getitem__(act_key)

class service_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = 0
        #dc.execute("SELECT ng.*, nc.name AS ncname FROM ng_service_templ ng LEFT JOIN ng_cgservicet ngc ON ngc.ng_service_templ=ng.ng_service_templ_idx LEFT JOIN ng_contactgroup nc ON ngc.ng_contactgroup=nc.ng_contactgroup_idx")
        for srv_templ in mon_service_templ.objects.all().prefetch_related(
            "mon_device_templ_set",
            "mon_contactgroup_set"):
            #db_rec["contact_groups"] = set()
            # generate notification options
            not_options = []
            for long_name, short_name in [("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u")]:
                if getattr(srv_templ, long_name):
                    not_options.append(short_name)
            if not not_options:
                not_options.append("n")
            srv_templ.notification_options = not_options
            self[srv_templ.pk]   = srv_templ
            self[srv_templ.name] = srv_templ
            srv_templ.contact_groups = set(srv_templ.mon_contactgroup_set.all().values_list("name", flat=True))
##            if db_rec["ncname"]:
##                self[db_rec["ng_service_templ_idx"]]["contact_groups"].add(db_rec["ncname"])
        if self.keys():
            self.__default = self.keys()[0]
        self.log("Found %s (%s)" % (logging_tools.get_plural("device_template", len(self.keys())),
                                    ", ".join([cur_v.name for cur_v in self.values()])))
    def is_valid(self):
        return True
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[service_templates] %s" % (what), level)
    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if not self.has_key(act_key):
            self.log("key %d not known, using default %s (%d)" % (
                str(act_key),
                unicode(self.__default),
                self.__default.pk),
                     logging_tools.LOG_LEVEL_ERROR)
            act_key = self.__default.pk
        return super(service_templates, self).__getitem__(act_key)

class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
        self.__nagios_lock_file_name = "%s/var/%s" % (global_config["MD_BASEDIR"], global_config["MD_LOCK_FILE"])
        connection.close()
        self.__mach_loggers = {}
        # slave configs
        slave_servers = device.objects.filter(Q(device_config__config__name="monitor_slave"))
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        self.__gen_config = main_config(self, master_server, distributed=True if len(slave_servers) else False)
        self.send_pool_message("external_cmd_file", self.__gen_config.get_command_name())
        self.__slave_configs = {}
        if len(slave_servers):
            self.log("found %s: %s" % (logging_tools.get_plural("slave_server", len(slave_servers)),
                                       ", ".join(sorted([cur_dev.name for cur_dev in slave_servers]))))
            for cur_dev in slave_servers:
                self.__slave_configs[cur_dev.pk] = main_config(self, cur_dev, slave_name=cur_dev.name, 
                                                               master_server=master_server)
        else:
            self.log("no slave-servers found")
        self.register_func("rebuild_config", self._rebuild_config)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        for mach_logger in self.__mach_loggers.itervalues():
            mach_logger.close()
        self.__log_template.close()
    def mach_log(self, what, lev=logging_tools.LOG_LEVEL_OK, mach_name=None, **kwargs):
        if mach_name is None:
            mach_name = self.__cached_mach_name
        else:
            self.__cached_mach_name = mach_name
        if mach_name not in self.__mach_loggers:
            self.__mach_loggers[mach_name] = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           mach_name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=self.zmq_context,
                init_logger=True)
        self.__mach_loggers[mach_name].log(lev, what)
        if kwargs.get("global_flag", False):
            self.log(what, lev)
    def _check_nagios_config(self):
        c_stat, out = commands.getstatusoutput("%s/bin/%s -v %s/etc/%s.cfg" % (
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"],
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"]))
        if c_stat:
            self.log("Checking the %s-configuration resulted in an error (%d)" % (
                global_config["MD_TYPE"],
                c_stat),
                     logging_tools.LOG_LEVEL_ERROR)
            ret_stat = 0
        else:
            self.log("Checking the %s-configuration returned no error" % (global_config["MD_TYPE"]))
            ret_stat = 1
        return ret_stat, out
    def _reload_nagios(self):
        start_daemon, restart_daemon = (False, False)
        cs_stat, cs_out = self._check_nagios_config()
        if not cs_stat:
            self.log("Checking the %s-config resulted in an error, not trying to (re)start" % (global_config["MD_TYPE"]), logging_tools.LOG_LEVEL_ERROR)
            self.log("error_output has %s" % (logging_tools.get_plural("line", cs_out.split("\n"))),
                     logging_tools.LOG_LEVEL_ERROR)
            for line in cs_out.split("\n"):
                if line.strip().lower().startswith("error"):
                    self.log(" - %s" % (line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if os.path.isfile(self.__nagios_lock_file_name):
                try:
                    pid = file(self.__nagios_lock_file_name, "r").read().strip()
                except:
                    self.log("Cannot read %s LockFile named '%s', trying to start %s" % (
                        global_config["MD_TYPE"],
                        self.__nagios_lock_file_name,
                        global_config["MD_TYPE"]),
                             logging_tools.LOG_LEVEL_WARN)
                    start_daemon = True
                else:
                    pid = file(self.__nagios_lock_file_name).read().strip()
                    try:
                        pid = int(pid)
                    except:
                        self.log("PID read from '%s' is not an integer (%s, %s), trying to restart %s" % (
                            self.__nagios_lock_file_name,
                            str(pid),
                            process_tools.get_except_info(),
                            global_config["MD_TYPE"]),
                                 logging_tools.LOG_LEVEL_ERROR)
                        restart_daemon = True
                    else:
                        try:
                            os.kill(pid, signal.SIGHUP)
                        except OSError:
                            self.log("Error signaling pid %d with SIGHUP (%d), trying to restart %s (%s)" % (
                                pid,
                                signal.SIGHUP,
                                global_config["MD_TYPE"],
                                process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                            restart_daemon = True
                        else:
                            self.log("Successfully signaled pid %d with SIGHUP (%d)" % (pid, signal.SIGHUP))
            else:
                self.log("Nagios LockFile '%s' not found, trying to start %s" % (self.__nagios_lock_file_name,
                                                                                 global_config["MD_TYPE"]),
                         logging_tools.LOG_LEVEL_WARN)
                start_daemon = True
        if start_daemon:
            self.log("Trying to start %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s start" % (global_config["MD_TYPE"]))
        elif restart_daemon:
            self.log("Trying to restart %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s restart" % (global_config["MD_TYPE"]))
        else:
            log_lines = []
        if log_lines:
            for log_line in log_lines:
                self.log(log_line)
    def _rebuild_config(self, *args, **kwargs):
        if global_config["DEBUG"]:
            cur_query_count = len(connection.queries)
        h_list = args[0] if len(args) else []
        rebuild_it = True
        try:
            cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            self.log("no cluster_device_group, unable to check validity of hopcount_table", logging_tools.LOG_LEVEL_ERROR)
        else:
            try:
                reb_var = device_variable.objects.get(Q(device=cdg) & Q(name="hopcount_rebuild_in_progress"))
            except device_variable.DoesNotExist:
                pass
            else:
                self.log("hopcount_rebuild in progress, delaying request", logging_tools.LOG_LEVEL_WARN)
                # delay request
                self.__log_queue.put(("delay_request", (self.get_thread_queue(), ("rebuild_config", h_list), global_config["MAIN_LOOP_TIMEOUT"] / 2)))
                # no rebuild
                rebuild_it = False
        if rebuild_it:
            # latest routing generation
            latest_gen = route_generation.objects.filter(Q(valid=True)).order_by("-pk")
            if len(latest_gen):
                latest_gen = latest_gen[0]
                if latest_gen.dirty:
                    rebuild_routing = True
                else:
                    rebuild_routing = False
            else:
                latest_gen = None
                rebuild_routing = True
            if rebuild_routing:
                self.log("latest route_generation (%s) is marked as dirty, forcing rebuild" % (unicode(latest_gen) if latest_gen else "no generations found"), logging_tools.LOG_LEVEL_WARN)
                srv_com = server_command.srv_command(command="rebuild_hopcount")
                targ_str = "tcp://localhost:8004"
                cs_sock = self.zmq_context.socket(zmq.DEALER)
                identity_str = "md_config_server::%d" % (os.getpid())
                timeout = 10
                cs_sock.setsockopt(zmq.IDENTITY, identity_str)
                cs_sock.setsockopt(zmq.LINGER, timeout)
                cs_sock.connect(targ_str)
                s_time = time.time()
                cs_sock.send_unicode(unicode(srv_com))
                if cs_sock.poll(timeout * 1000):
                    recv_str = cs_sock.recv()
                else:
                    self.log("error while communication with %s after %s: timeout" % (
                        targ_str,
                        logging_tools.get_plural("second", timeout)), logging_tools.LOG_LEVEL_ERROR)
                    recv_str = None
                if recv_str:
                    self.log("send rebuild_hocount to %s, took %s" % (
                        targ_str,
                        logging_tools.get_diff_time_str(time.time() - s_time)))
                    next_gen = latest_gen.generation + 1 if latest_gen else 1
                    self.log("waiting for generation %d to become valid" % (next_gen))
                    s_time = time.time()
                    # wait for up to 60 seconds
                    for idx in xrange(60):
                        time.sleep(1)
                        try:
                            latest_gen = route_generation.objects.get(
                                Q(valid=True) &
                                Q(build=False) &
                                Q(generation=next_gen))
                        except route_generation.DoesNotExist:
                            self.log("still waiting...")
                        else:
                            self.log("done after %d iterations" % (idx + 1))
                            break
            else:
                self.log("latest route_generation %s is valid" % (unicode(latest_gen)))
            # fetch SNMP-stuff of cluster
            snmp_stack = snmp_settings(cdg)
            rebuild_gen_config = False
            if global_config["ALL_HOSTS_NAME"] in h_list:
                self.log("rebuilding complete config (for master and %s)" % (
                    logging_tools.get_plural("slave", len(self.__slave_configs))
                ))
                rebuild_gen_config = True
            else:
                # FIXME, handle host-related config for only specified slaves
                self.log("rebuilding config for %s: %s" % (logging_tools.get_plural("host", len(h_list)),
                                                           logging_tools.compress_list(h_list)))
            if not self.__gen_config:
                rebuild_gen_config = True
            if rebuild_gen_config:
                self._create_general_config()
                h_list = []
            bc_valid = self.__gen_config.is_valid()
            if bc_valid:
                # get device templates
                dev_templates = device_templates(self)
                # get serivce templates
                serv_templates = service_templates(self)
                if dev_templates.is_valid() and serv_templates.is_valid():
                    pass
                else:
                    bc_valid = False
            if bc_valid:
                # build distance map
                self.latest_gen = latest_gen
                cur_dmap = self._build_distance_map(self.__gen_config.monitor_server)
                for cur_gc in [self.__gen_config] + self.__slave_configs.values():
                    self._create_host_config_files(cur_gc, h_list, dev_templates, serv_templates, snmp_stack, cur_dmap)
                    if cur_gc.master:
                        # recreate access files
                        cur_gc._create_access_entries()
                    # refresh implies _write_entries
                    cur_gc.refresh()
                    if not cur_gc.master:
                        cur_gc._write_entries()
                        cur_gc.distribute()
            cfgs_written = self.__gen_config._write_entries()
            if bc_valid and (cfgs_written or rebuild_gen_config):
                # send reload to remote instance ?
                self._reload_nagios()
            # FIXME
            #self.__queue_dict["command_queue"].put(("config_rebuilt", h_list or [global_config["ALL_HOSTS_NAME"]]))
        if global_config["DEBUG"]:
            tot_query_count = len(connection.queries) - cur_query_count
            self.log("queries issued: %d" % (tot_query_count))
            #for q_idx, act_sql in enumerate(connection.queries[cur_query_count:], 1):
            #    self.log(" %4d %s" % (q_idx, act_sql["sql"][:120]))
    def _build_distance_map(self, root_node):
        self.log("building distance map, root node is '%s'" % (root_node))
        # exclude all without attached netdevices
        dm_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.exclude(netdevice=None).prefetch_related("netdevice_set")])
        nd_dict = dict([(pk, set(cur_dev.netdevice_set.all().values_list("pk", flat=True))) for pk, cur_dev in dm_dict.iteritems()])
        for cur_dev in dm_dict.itervalues():
            # set 0 for root_node, -1 for all other devices
            cur_dev.md_dist_level = 0 if cur_dev.pk == root_node.pk else -1
        all_pks = set(dm_dict.keys())
        max_level = 0
        # limit for loop
        for cur_iter in xrange(128):
            self.log("dm_run %d" % (cur_iter))
            run_again = False
            # iterate until all nodes have a valid dist_level set
            src_nodes = set([key for key, value in dm_dict.iteritems() if value.md_dist_level >= 0])
            dst_nodes = all_pks - src_nodes
            self.log("%s, %s" % (logging_tools.get_plural("source node", len(src_nodes)),
                                 logging_tools.get_plural("dest node", len(dst_nodes))))
            src_nds = reduce(operator.ior, [nd_dict[key] for key in src_nodes], set())
            dst_nds = reduce(operator.ior, [nd_dict[key] for key in dst_nodes], set())
            # only single-hop hopcounts
            for cur_hc in hopcount.objects.filter(
                Q(route_generation=self.latest_gen) &
                Q(s_netdevice__in=src_nds) &
                Q(d_netdevice__in=dst_nds) &
                Q(trace_length=2)):
                if cur_hc.s_netdevice_id == cur_hc.d_netdevice_id:
                    # loop, skip
                    pass
                else:
                    #dst_nds = [val for val in [cur_hc.s_netdevice_id, cur_hc.d_netdevice_id] if val not in src_nds]
                    trace = [int(val) for val in cur_hc.trace.split(":")]
                    # direct attached
                    if trace[0] in src_nodes:
                        src_dev, dst_dev = (dm_dict[trace[0]], dm_dict[trace[1]])
                    else:
                        src_dev, dst_dev = (dm_dict[trace[1]], dm_dict[trace[0]])
                    new_level = src_dev.md_dist_level + 1
                    if dst_dev.md_dist_level >= 0 and new_level > dst_dev.md_dist_level:
                        self.log("pushing node %s farther away from root (%d => %d)" % (
                            unicode(dst_dev),
                            dst_dev.md_dist_level,
                            new_level))
                    dst_dev.md_dist_level = max(dst_dev.md_dist_level, new_level)
                    max_level = max(max_level, dst_dev.md_dist_level)
                    run_again = True
            if not run_again:
                break
        self.log("max distance level: %d" % (max_level))
        nodes_ur = [unicode(value) for value in dm_dict.itervalues() if value.md_dist_level < 0]
        if nodes_ur:
            self.log("%s: %s" % (
                logging_tools.get_plural("unroutable node", len(nodes_ur)),
                ", ".join(sorted(nodes_ur))
            )
                     )
        for level in xrange(max_level + 1):
            self.log("nodes in level %d: %s" % (
                level,
                len([True for value in dm_dict.itervalues() if value.md_dist_level == level])
            )
                     )
        return dict([(key, value.md_dist_level) for key, value in dm_dict.iteritems()])
    def _create_general_config(self):
        start_time = time.time()
        self._check_image_maps()
        self._create_gen_config_files([self.__gen_config] + self.__slave_configs.values())
        end_time = time.time()
        self.log("creating the total general config took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _create_gen_config_files(self, gc_list):
        for cur_gc in gc_list:
            start_time = time.time()
            # misc commands (sending of mails)
            cur_gc.add_config(all_commands(cur_gc, self))
            # servicegroups
            cur_gc.add_config(all_servicegroups(cur_gc, self))
            # timeperiods
            cur_gc.add_config(time_periods(cur_gc, self))
            # contacts
            cur_gc.add_config(all_contacts(cur_gc, self))
            # contactgroups
            cur_gc.add_config(all_contact_groups(cur_gc, self))
            # hostgroups
            cur_gc.add_config(all_host_groups(cur_gc, self))
            # hosts
            cur_gc.add_config(all_hosts(cur_gc, self))
            # hosts_extinfo
            cur_gc.add_config(all_hosts_extinfo(cur_gc, self))
            # services
            cur_gc.add_config(all_services(cur_gc, self))
            end_time = time.time()
            cur_gc.log("created host_configs in %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _get_ng_ext_hosts(self):
        all_ext_hosts = dict([(cur_ext.pk, cur_ext) for cur_ext in mon_ext_host.objects.all()])
        return all_ext_hosts
    def _check_image_maps(self):
        min_width, max_width, min_height, max_height = (16, 64, 16, 64)
        all_image_stuff = self._get_ng_ext_hosts()
        self.log("Found %s" % (logging_tools.get_plural("ext_host entry", len(all_image_stuff.keys()))))
        logos_dir = "%s/share/images/logos" % (global_config["MD_BASEDIR"])
        base_names = []
        if os.path.isdir(logos_dir):
            logo_files = os.listdir(logos_dir)
            for log_line in [entry.split(".")[0] for entry in logo_files]:
                if log_line not in base_names:
                    if "%s.png" % (log_line) in logo_files and "%s.gd2" % (log_line) in logo_files:
                        base_names.append(log_line)
        if base_names:
            stat, out = commands.getstatusoutput("file %s" % (" ".join([os.path.join(logos_dir, "%s.png" % (entry)) for entry in base_names])))
            if stat:
                self.log("error getting filetype of %s" % (logging_tools.get_plural("logo", len(base_names))), logging_tools.LOG_LEVEL_ERROR)
            else:
                base_names = []
                for logo_name, logo_data in [
                    (os.path.basename(y[0].strip()), [z.strip() for z in y[1].split(",") if z.strip()]) for y in [
                        line.strip().split(":", 1) for line in out.split("\n")] if len(y) == 2]:
                    if len(logo_data) == 4:
                        width, height = [int(value.strip()) for value in logo_data[1].split("x")]
                        if min_width <= width and width <= max_width and min_height <= height and height <= max_height:
                            base_names.append(logo_name[:-4])
                        else:
                            self.log("width or height (%d x %d) not in range ([%d - %d] x [%d - %d])" % (
                                width,
                                height,
                                min_width,
                                max_width,
                                min_height,
                                max_height))
        all_images_present = set([eh.name for eh in all_image_stuff.values()])
        all_images_present_lower = set([name.lower() for name in all_images_present])
        base_names_lower = set([name.lower() for name in base_names])
        new_images = base_names_lower - all_images_present_lower
        del_images = all_images_present_lower - base_names_lower
        for new_image in new_images:
            mon_ext_host(name=new_image,
                         icon_image="%s.png" % (new_image),
                         statusmap_image="%s.gd2" % (new_image)).save()
        if del_images:
            mon_ext_host.objects.filter(Q(name__in=del_images)).delete()
        self.log("Inserted %s, deleted %s" % (logging_tools.get_plural("new ext_host_entry", len(new_images)),
                                              logging_tools.get_plural("ext_host_entry", len(del_images))))
    def _get_int_str(self, i_val, size=3):
        if i_val:
            return ("%%%dd" % (size)) % (i_val)
        else:
            return ("%%%ds" % (size)) % ("-")
    def _create_single_host_config(self,
                                   cur_gc,
                                   host,
                                   check_hosts,
                                   d_map,
                                   my_net_idxs,
                                   all_hosts_dict,
                                   dev_templates,
                                   serv_templates,
                                   snmp_stack,
                                   all_access,
                                   # not used right now
                                   #all_ms_connections,
                                   #all_ib_connections,
                                   #all_dev_relationships,
                                   contact_group_dict,
                                   ng_ext_hosts,
                                   all_configs,
                                   nagvis_maps,
                                   ):
        start_time = time.time()
        # set some vars
        host_nc, service_nc, hostext_nc  = (cur_gc["host"], cur_gc["service"], cur_gc["hostextinfo"])
        if cur_gc.master:
            check_for_passive_checks = True
        else:
            check_for_passive_checks = False
        checks_are_active = True
        if check_for_passive_checks:
            if host.monitor_server_id and host.monitor_server_id != cur_gc.monitor_server.pk:
                checks_are_active = False
        #h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        self.__cached_mach_name = host.name
        self.mach_log("-------- %s ---------" % ("master" if cur_gc.master else "slave %s" % (cur_gc.slave_name)))
        glob_log_str = "Starting build of config for device %32s%s (%10s), distance level is %3d" % (
            host.name[:32],
            "*" if len(host.name) > 32 else " ",
            "active" if checks_are_active else "passive",
            d_map.get(host.pk, -1),
        )
        self.mach_log("Starting build of config", logging_tools.LOG_LEVEL_OK, host.name)
        num_ok, num_warning, num_error = (0, 0, 0)
        #print "%s : %s" % (host["name"], host["identifier"])
        if host.valid_ips:
            net_devices = host.valid_ips
        elif host.invalid_ips:
            self.mach_log("Device %s has no valid netdevices associated, using invalid ones..." % (host.name),
                          logging_tools.LOG_LEVEL_WARN)
            net_devices = host.invalid_ips
        else:
            self.mach_log("Device %s has no netdevices associated, skipping..." % (host.name),
                          logging_tools.LOG_LEVEL_ERROR)
            num_error += 1
            net_devices = {}
        if net_devices:
            #print mni_str_s, mni_str_d, dev_str_s, dev_str_d
            # get correct netdevice for host
            if host.name == global_config["SERVER_SHORT_NAME"]:
                valid_ips, traces = (["127.0.0.1"], [(1, 0, [host.pk])])
            else:
                valid_ips, traces = self._get_target_ip_info(my_net_idxs, net_devices, host.pk, all_hosts_dict, check_hosts)
                if not valid_ips:
                    num_error += 1
            act_def_dev = dev_templates[host.mon_device_templ_id or 0]
            if valid_ips and act_def_dev:
                valid_ip = valid_ips[0]
                self.mach_log("Found %s for host %s : %s, using %s" % (
                    logging_tools.get_plural("target ip", len(valid_ips)),
                    host.name,
                    ", ".join(valid_ips),
                    valid_ip))
                if not serv_templates.has_key(act_def_dev.mon_service_templ_id):
                    self.log("Default service_template not found in service_templates", logging_tools.LOG_LEVEL_WARN)
                else:
                    act_def_serv = serv_templates[act_def_dev.mon_service_templ_id]
                    # tricky part: check the actual service_template for the various services
                    self.mach_log("Using default device_template '%s' and service_template '%s' for host %s" % (
                        act_def_dev.name,
                        act_def_serv.name,
                        host.name))
                    # get device variables
                    dev_variables = {}
                    for cur_var in device_variable.objects.filter(Q(device=host)):
                        var_name = cur_var.name
                        dev_variables[var_name] = unicode(cur_var.value)
                    dev_variables.update(snmp_stack.get_vars(host))
                    self.mach_log("device has %s" % (
                        logging_tools.get_plural("device_variable", len(dev_variables.keys()))))
                    # now we have the device- and service template
                    act_host = nag_config(host.name)
                    act_host["host_name"] = host.name
                    # action url
                    if global_config["ENABLE_PNP"]:
                        act_host["process_perf_data"] = 1 if host.enable_perfdata else 0
                        if host.enable_perfdata:
                            act_host["action_url"] = "%s/index.php/graph?host=$HOSTNAME$&srv=_HOST_" % (global_config["PNP_URL"])
                    # deep copy needed here
                    c_list = [entry for entry in all_access]
                    # set alias
                    if host.device_group.user_set.all():
                        c_list.extend([cur_u.login for cur_u in host.device_group.user_set.all()])
                    if c_list:
                        act_host["contacts"] = ",".join(c_list)
                    act_host["alias"] = host.alias or host.name
                    act_host["address"] = valid_ip
                    # check for parents
                    parents = []
                    # rule 1: APC Masterswitches have their bootserver set as parent
                    if host.device_type.identifier in ["AM", "IBC"] and host.bootserver_id:
                        parents.append(all_hosts_dict[host.bootserver_id].name)
                    # rule 2: Devices connected to an apc have this apc set as parent
                    #elif all_ms_connections.has_key(host.pk):
                        #for pd in all_ms_connections[host.pk]:
                            #if all_hosts_dict[pd]["name"] not in parents:
                                ## disable circular references
                                #if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                    #self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                #else:
                                    #parents.append(all_hosts_dict[pd]["name"])
                    # rule 3: Devices connected to an ibc have this ibc set as parent
                    #elif all_ib_connections.has_key(host.pk):
                        #for pd in all_ib_connections[host.pk]:
                            #if all_hosts_dict[pd]["name"] not in parents:
                                ## disable circular references
                                #if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                    #self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                #else:
                                    #parents.append(all_hosts_dict[pd]["name"])
                    # rule 4: Devices have their xen/vmware-parent set as parent
                    #elif all_dev_relationships.has_key(host.pk) and all_hosts_dict.has_key(all_dev_relationships[host.pk]["host_device"]):
                        #act_rel = all_dev_relationships[host.pk]
                        ## disable circular references
                        #if host["identifier"] == "H" and host["name"] == global_config["SERVER_SHORT_NAME"]:
                            #self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[act_rel["host_device"]]["name"]))
                        #else:
                            #parents.append(all_hosts_dict[act_rel["host_device"]]["name"])
                    # rule 5: Check routing
                    else:
                        self.mach_log("No direct parent(s) found, registering trace")
                        if host.bootserver_id != host.pk and host.bootserver_id:
                            traces.append((1, 0, [host.pk]))
                        if traces and len(traces[0][2]) > 1:
                            act_host["possible_parents"] = traces
                            #print traces, host["name"], all_hosts_dict[traces[1]]["name"]
                            #parents += [all_hosts_dict[traces[1]]["name"]]
                        #print "No parent set for %s" % (host["name"])
                    if parents:
                        self.mach_log("settings %s: %s" % (
                            logging_tools.get_plural("parent", len(parents)),
                            ", ".join(sorted(parents))))
                        act_host["parents"] = ",".join(parents)
                    act_host["retain_status_information"] = global_config["RETAIN_HOST_STATUS"]
                    act_host["max_check_attempts"]        = act_def_dev.max_attempts
                    act_host["notification_interval"]     = act_def_dev.ninterval
                    act_host["notification_period"]       = cur_gc["timeperiod"][act_def_dev.mon_period_id]["name"]
                    act_host["checks_enabled"]            = 1
                    act_host["%s_checks_enabled" % ("active" if checks_are_active else "passive")] = 1
                    act_host["%s_checks_enabled" % ("passive" if checks_are_active else "active")] = 0
                    if checks_are_active and not cur_gc.master:
                        # trace changes
                        act_host["obsess_over_host"] = 1
                    host_groups = set(contact_group_dict.get(host.name, []))
                    act_host["contact_groups"] = ",".join(host_groups) if host_groups else global_config["NONE_CONTACT_GROUP"]
                    act_host["contacts"] = ""
                    self.mach_log("contact groups for host: %s" % (
                        ", ".join(sorted(host_groups)) or "none"))
                    if host.monitor_checks:
                        if valid_ip == "0.0.0.0":
                            self.mach_log("IP address is '%s', host is assumed to be always up" % (unicode(valid_ip)))
                            act_host["check_command"] = "check-host-ok"
                        else:
                            act_host["check_command"] = act_def_dev.ccommand
                        # check for nagvis map
                        if host.automap_root_nagvis:
                            map_file = os.path.join(global_config["NAGVIS_DIR"], "etc", "maps", "%s.cfg" % (host.name))
                            map_dict = {
                                "sources"      : "automap",
                                "alias"        : host.comment or host.name,
                                "parent_map"   : "",
                                "iconset"      : "std_big",
                                "child_layers" : 10,
                                "backend_id"   : "live_1",
                                "root"         : host.name,
                                "label_show"   : "1",
                                "label_border" : "transparent",
                                "render_mode"  : "directed",
                                "rankdir"      : "TB",
                                "width"        : 800,
                                "height"       : 600,
                                "header_menu"  : True,
                                "hover_menu"   : True,
                                "context_menu" : True,
                                # special flag for anovis
                                "use_childs_for_overview_icon" : False,
                            }
                            try:
                                map_h = codecs.open(map_file, "w", "utf-8")
                            except:
                                self.mach_log("cannot open %s: %s" % (map_file,
                                                                      process_tools.get_except_info()),
                                              logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                nagvis_maps.add(map_file)
                                map_h.write("define global {\n")
                                for key, value in map_dict.iteritems():
                                    if type(value) == bool:
                                        value = "1" if value else "0"
                                    elif type(value) in [int, long]:
                                        value = "%d" % (value)
                                    map_h.write(u"    %s=%s\n" % (key, value))
                                map_h.write("}\n")
                                map_h.close()
                        # check for notification options
                        not_a = []
                        for what, shortcut in [("nrecovery", "r"), ("ndown", "d"), ("nunreachable", "u")]:
                            if getattr(act_def_dev, what):
                                not_a.append(shortcut)
                        if not not_a:
                            not_a.append("n")
                        act_host["notification_options"] = ",".join(not_a)
                        # check for hostextinfo
                        if host.mon_ext_host_id and ng_ext_hosts.has_key(host.mon_ext_host_id):
                            if (global_config["MD_TYPE"] == "nagios" and global_config["MD_VERSION"] > 1) or (global_config["MD_TYPE"] == "icinga"):
                                # handle for nagios 2
                                act_hostext_info = nag_config(host.name)
                                act_hostext_info["host_name"] = host.name
                                for key in ["icon_image", "statusmap_image"]:
                                    act_hostext_info[key] = getattr(ng_ext_hosts[host.mon_ext_host_id], key)
                                hostext_nc[host.name] = act_hostext_info
                            else:
                                self.log("don't know how to handle hostextinfo for %s_version %d" % (
                                    global_config["MD_TYPE"],
                                    global_config["MD_VERSION"]),
                                         logging_tools.LOG_LEVEL_ERROR)
                        # clear host from servicegroups
                        cur_gc["servicegroup"].clear_host(host.name)
                        # get check_commands and templates
                        conf_names = set(all_configs.get(host.name, []))
                        # cluster config names
                        cconf_names = set(host.devs_mon_service_cluster.all().values_list("mon_check_command__name", flat=True))
                        # build lut
                        conf_dict = dict([(cur_c["command_name"], cur_c) for cur_c in cur_gc["command"].values() if 
                                          (cur_c.get_config() in conf_names and (not(cur_c.get_device()) or cur_c.get_device() == host.pk)) or
                                          cur_c["command_name"] in cconf_names])
                        # old code, use only_ping config
                        #if host["identifier"] == "NB" or host["identifier"] == "AM" or host["identifier"] == "S":
                        #    # set config-dict for netbotzes, APC Masterswitches and switches to ping
                        #    conf_dict = dict([(x["command_name"], x) for x in self.__gen_config["checkcommand"]["struct"].values() if x["command_name"].startswith("check_ping")])
                        #print host["name"], conf_dict
                        # now conf_dict is a list of all service-checks defined for this host
                        #pprint.pprint(conf_dict)
                        # list of already used checks
                        used_checks = set()
                        conf_names = sorted(conf_dict.keys())
                        for conf_name in conf_names:
                            s_check = conf_dict[conf_name]
                            if s_check.name in used_checks:
                                self.mach_log("%s (%s) already used, ignoring .... (CHECK CONFIG !)" % (
                                    s_check.get_description(),
                                    s_check["command_name"]), logging_tools.LOG_LEVEL_WARN)
                                num_warning += 1
                            else:
                                used_checks.add(s_check.name)
                                special = s_check.get_special()
                                if special:
                                    sc_array = []
                                    try:
                                        cur_special = getattr(special_commands, "special_%s" % (special.lower()))(self, s_check, host, valid_ip, global_config)
                                    except:
                                        self.log("unable to initialize special '%s': %s" % (
                                            special,
                                            process_tools.get_except_info()),
                                                 logging_tools.LOG_LEVEL_CRITICAL)
                                    else:
                                        # calling handle to return a list of checks with format
                                        # [(description, [ARG1, ARG2, ARG3, ...]), (...)]
                                        try:
                                            sc_array = cur_special()
                                        except:
                                            exc_info = process_tools.exception_info()
                                            self.log("error calling special %s:" % (special),
                                                     logging_tools.LOG_LEVEL_CRITICAL)
                                            for line in exc_info.log_lines:
                                                self.log(" - %s" % (line), logging_tools.LOG_LEVEL_CRITICAL)
                                            sc_array = []
                                        finally:
                                            cur_special.cleanup()
                                else:
                                    sc_array = [special_commands.arg_template(s_check, s_check.get_description())]
                                    # contact_group is only written if contact_group is responsible for the host and the service_template
                                serv_temp = serv_templates[s_check.get_template(act_def_serv.name)]
                                serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                sc_list = self.get_service(host, act_host, s_check, sc_array, act_def_serv, serv_cgs, checks_are_active, serv_temp, cur_gc, dev_variables)
                                service_nc.extend(sc_list)
                                num_ok += len(sc_list)
                        # add cluster checks
                        mhc_checks = host.main_mon_host_cluster.all().prefetch_related("devices")
                        if len(mhc_checks):
                            self.mach_log("adding %s" % (logging_tools.get_plural("host_cluster check", len(mhc_checks))))
                            for mhc_check in mhc_checks:
                                dev_names = ",".join(["$HOSTSTATEID:%s$" % (cur_dev.name) for cur_dev in mhc_check.devices.all()])
                                s_check = cur_gc["command"]["check_host_cluster"]
                                serv_temp = serv_templates[mhc_check.mon_service_templ_id]
                                serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                sub_list = self.get_service(
                                    host,
                                    act_host,
                                    s_check,
                                    [special_commands.arg_template(
                                        s_check,
                                        "%s %s" % (s_check.get_description(), mhc_check.description),
                                        arg1=mhc_check.description,
                                        arg2=mhc_check.warn_value,
                                        arg3=mhc_check.error_value,
                                        arg4=dev_names)
                                     ],
                                    act_def_serv,
                                    serv_cgs,
                                    checks_are_active,
                                    serv_temp,
                                    cur_gc,
                                    dev_variables)
                                service_nc.extend(sub_list)
                                num_ok += len(sub_list)
                        # add service checks
                        msc_checks = host.main_mon_service_cluster.all().prefetch_related("devices")
                        if len(msc_checks):
                            self.mach_log("adding %s" % (logging_tools.get_plural("service_cluster check", len(mhc_checks))))
                            for msc_check in msc_checks:
                                c_com = cur_gc["command"][msc_check.mon_check_command.name]
                                dev_names = ",".join(["$SERVICESTATEID:%s:%s$" % (cur_dev.name, c_com.get_description()) for cur_dev in mhc_check.devices.all()])
                                s_check = cur_gc["command"]["check_service_cluster"]
                                serv_temp = serv_templates[msc_check.mon_service_templ_id]
                                serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                sub_list = self.get_service(
                                    host,
                                    act_host,
                                    s_check,
                                    [special_commands.arg_template(
                                        s_check,
                                        s_check.get_description(), 
                                        arg1=msc_check.description,
                                        arg2=msc_check.warn_value,
                                        arg3=msc_check.error_value,
                                        arg4=dev_names)
                                     ],
                                    act_def_serv,
                                    serv_cgs,
                                    checks_are_active,
                                    serv_temp,
                                    cur_gc,
                                    dev_variables)
                                service_nc.extend(sub_list)
                                num_ok += len(sub_list)
                        host_nc[act_host["name"]] = act_host
                    else:
                        self.mach_log("Host %s is disabled" % (host.name))
            else:
                self.mach_log("No valid IPs found or no default_device_template found", logging_tools.LOG_LEVEL_ERROR)
        info_str = "finished with %s warnings and %s errors (%3d ok) in %s" % (
            self._get_int_str(num_warning),
            self._get_int_str(num_error),
            num_ok,
            logging_tools.get_diff_time_str(time.time() - start_time))
        glob_log_str = "%s, %s" % (glob_log_str, info_str)
        self.log(glob_log_str)
        self.mach_log(info_str)
    def _create_host_config_files(self, cur_gc, hosts, dev_templates, serv_templates, snmp_stack, d_map):
        """
        d_map : distance map
        """
        start_time = time.time()
        # get contacts with access to all devices
        all_access = list(user.objects.filter(Q(login__in=[cur_u.username for cur_u in User.objects.filter(is_active=True) if cur_u.has_perm("backbone.all_devices")])).values_list("login", flat=True))
        self.log("users with access to all devices: %s" % (", ".join(sorted(all_access))))
        server_idxs = [cur_gc.monitor_server.pk]
        # get netip-idxs of own host
        my_net_idxs = set(netdevice.objects.filter(Q(device__in=server_idxs)).values_list("pk", flat=True))
        main_dir = global_config["MD_BASEDIR"]
        etc_dir = os.path.normpath("%s/etc" % (main_dir))
        # get ext_hosts stuff
        ng_ext_hosts = self._get_ng_ext_hosts()
        # all hosts
        all_hosts_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.all().select_related("device_type")])
        # check_hosts
        if hosts:
            h_filter = Q(name__in=hosts)
        else:
            h_filter = Q()
        # add master/slave related filters
        if cur_gc.master:
            pass
            #h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        else:
            h_filter &= Q(monitor_server=cur_gc.monitor_server)
        # dictionary with all parent / slave relations
        ps_dict = {}
        for ps_config in config.objects.exclude(Q(parent_config=None)).select_related("parent_config"):
            ps_dict[ps_config.name] = ps_config.parent_config.name
        check_hosts = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.filter(h_filter)])
        for cur_dev in check_hosts.itervalues():
            # set default values
            cur_dev.valid_ips = {}
            cur_dev.invalid_ips = {}
        meta_devices = dict([(md.device_group.pk, md) for md in device.objects.filter(Q(device_type__identifier='MD')).prefetch_related("device_config_set", "device_config_set__config").select_related("device_group")])
        all_configs = {}
        for cur_dev in device.objects.filter(h_filter).prefetch_related("device_config_set", "device_config_set__config"):
            loc_config = [cur_dc.config.name for cur_dc in cur_dev.device_config_set.all()]
            if cur_dev.device_group_id in meta_devices:
                loc_config.extend([cur_dc.config.name for cur_dc in meta_devices[cur_dev.device_group_id].device_config_set.all()])
            # expand with parent
            while True:
                new_confs = set([ps_dict[cur_name] for cur_name in loc_config if cur_name in ps_dict]) - set(loc_config)
                if new_confs:
                    loc_config.extend(list(new_confs))
                else:
                    break
            all_configs[cur_dev.name] = loc_config
        # get config variables
        first_contactgroup_name = cur_gc["contactgroup"][cur_gc["contactgroup"].keys()[0]]["name"]
        contact_group_dict = {}
        # get contact groups
        if hosts:
            host_info_str = logging_tools.get_plural("host", len(hosts))
            ct_groups = mon_contactgroup.objects.filter(Q(device_groups__device__name__in=hosts))
        else:
            host_info_str = "all"
            ct_groups = mon_contactgroup.objects.all()
        ct_group = ct_groups.prefetch_related("device_groups", "device_groups__device")
        for ct_group in ct_groups:
            if cur_gc["contactgroup"].has_key(ct_group.pk):
                cg_name = cur_gc["contactgroup"][ct_group.pk]["name"]
            else:
                self.log("contagroup_idx %s for device %s not found, using first from contactgroups (%s)" % (
                    unicode(ct_group),
                    ct_group.name,
                    first_contactgroup_name),
                         logging_tools.LOG_LEVEL_ERROR)
                cg_name = first_contactgroup_name
            for h_name in ct_group.device_groups.all().values_list("device_group__name", flat=True):
                contact_group_dict.setdefault(h_name, []).append(ct_group.name)
        # get valid and invalid network types
        valid_nwt_list = set(network_type.objects.filter(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        invalid_nwt_list = set(network_type.objects.exclude(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        # get all network devices (needed for relaying)
        for n_i, n_n, n_t, n_d, d_pk in net_ip.objects.all().values_list("ip", "netdevice__device__name", "network__network_type__identifier", "netdevice__pk", "netdevice__device__pk"):
            if d_pk in check_hosts:
                cur_host = check_hosts[d_pk]
                getattr(cur_host, "valid_ips" if n_t in valid_nwt_list else "invalid_ips").setdefault(n_d, []).append(n_i)
        # get all masterswitch connections, FIXME
        #dc.execute("SELECT d.device_idx, ms.device FROM device d, msoutlet ms WHERE ms.slave_device = d.device_idx")
        all_ms_connections = {}
        #for db_rec in dc.fetchall():
        #    all_ms_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        # get all device relationships
        all_dev_relationships = {}
        # FIXME
        #dc.execute("SELECT * FROM device_relationship")
        #for db_rec in dc.fetchall():
        #    all_dev_relationships[db_rec["domain_device"]] = db_rec
        # get all ibm bladecenter connections
        # FIXME
        #dc.execute("SELECT d.device_idx, ib.device FROM device d, ibc_connection ib WHERE #ib.slave_device = d.device_idx")
        all_ib_connections = {}
        #for db_rec in dc.fetchall():
        #    all_ib_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        host_nc, service_nc, hostext_nc  = (cur_gc["host"], cur_gc["service"], cur_gc["hostextinfo"])
        # delete host if already present in host_table
        for host_pk, host in check_hosts.iteritems():
            del_list = set([cur_dev for cur_dev in host_nc.values() if cur_dev.name == host.name])
            for del_h in del_list:
                del_list_2 = [cur_dev for cur_dev in service_nc.values() if cur_dev["host_name"] == del_h.name]
                for del_h_2 in del_list_2:
                    service_nc.remove_host(del_h_2)
                # delete hostextinfo for nagios V1.x
                if hostext_nc.has_key(del_h.name):
                    del hostext_nc[del_h.name]
                del host_nc[del_h.name]
        # build lookup-table
        nagvis_maps = set()
        for host_name, host in sorted([(cur_dev.name, cur_dev) for cur_dev in check_hosts.itervalues()]):
            self._create_single_host_config(
                cur_gc,
                host,
                check_hosts,
                d_map,
                my_net_idxs,
                all_hosts_dict,
                dev_templates,
                serv_templates,
                snmp_stack,
                all_access,
                #all_ms_connections,
                #all_ib_connections,
                #all_dev_relationships,
                contact_group_dict,
                ng_ext_hosts,
                all_configs,
                nagvis_maps,
            )
        host_names = host_nc.keys()
        for host in host_nc.values():
            if host.has_key("possible_parents"):
                parent_list = []
                p_parents = host["possible_parents"]
                #print "*", p_parents
                for p_val, nd_val, p_list in p_parents:
                    # skip first host (is self)
                    host_pk = p_list.pop(0)
                    for parent_idx in p_list:
                        if d_map[host_pk] > d_map[parent_idx]:
                            parent = all_hosts_dict[parent_idx].name
                            if parent in host_names and parent != host["name"]:
                                parent_list.append(parent)
                                # exit inner loop
                                break
                        else:
                            break
                del host["possible_parents"]
                if parent_list:
                    host["parents"] = ",".join(set(parent_list))
                    self.mach_log("Setting parent to %s" % (", ".join(parent_list)), logging_tools.LOG_LEVEL_OK, host["name"])
        # remove old nagvis maps
        self.log("created %s" % (logging_tools.get_plural("nagvis map", len(nagvis_maps))))
        nagvis_map_dir = os.path.join(global_config["NAGVIS_DIR"], "etc", "maps")
        if os.path.isdir(nagvis_map_dir):
            for entry in os.listdir(nagvis_map_dir):
                full_name = os.path.join(nagvis_map_dir, entry)
                if full_name not in nagvis_maps:
                    self.log("removing old nagvis mapfile %s" % (full_name))
                    try:
                        os.unlink(full_name)
                    except:
                        self.log("error removing %s: %s" % (full_name, 
                                                            process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
        end_time = time.time()
        self.log("created configs for %s hosts in %s" % (
            host_info_str,
            logging_tools.get_diff_time_str(end_time - start_time)))
    def get_service(self, host, act_host, s_check, sc_array, act_def_serv, serv_cgs, checks_are_active, serv_temp, cur_gc, dev_variables):
        self.mach_log("  adding check %-30s (%2d p), template %s, %s" % (
            s_check["command_name"],
            len(sc_array),
            s_check.get_template(act_def_serv.name),
            "cg: %s" % (", ".join(sorted(serv_cgs))) if serv_cgs else "no cgs"))
        ret_field = []
        #for sc_name, sc in sc_array:
        for arg_temp in sc_array:
            act_serv = nag_config(arg_temp.info)
            act_serv["%s_checks_enabled" % ("active" if checks_are_active else "passive")] = 1
            act_serv["%s_checks_enabled" % ("passive" if checks_are_active else "active")] = 0
            act_serv["service_description"]   = arg_temp.info.replace("(", "[").replace(")", "]")
            act_serv["host_name"]             = host.name
            act_serv["is_volatile"]           = serv_temp.volatile
            act_serv["check_period"]          = cur_gc["timeperiod"][serv_temp.nsc_period_id]["name"]
            act_serv["max_check_attempts"]    = serv_temp.max_attempts
            act_serv["normal_check_interval"] = serv_temp.check_interval
            act_serv["retry_check_interval"]  = serv_temp.retry_interval
            act_serv["notification_interval"] = serv_temp.ninterval
            act_serv["notification_options"]  = ",".join(serv_temp.notification_options)
            act_serv["notification_period"]   = cur_gc["timeperiod"][serv_temp.nsn_period_id]["name"]
            if serv_cgs:
                act_serv["contact_groups"] = ",".join(serv_cgs)
            else:
                act_serv["contact_groups"] = global_config["NONE_CONTACT_GROUP"]
            if not checks_are_active:
                act_serv["check_freshness"] = 0
                act_serv["freshness_threshold"] = 3600
            if checks_are_active and not cur_gc.master:
                # trace
                act_serv["obsess_over_service"] = 1
            if global_config["ENABLE_PNP"]:
                act_serv["process_perf_data"] = 1 if (host.enable_perfdata and s_check.enable_perfdata) else 0
                if host.enable_perfdata and s_check.enable_perfdata:
                    act_serv["action_url"] = "%s/index.php/graph?host=$HOSTNAME$&srv=$SERVICEDESC$" % (global_config["PNP_URL"])
            act_serv["servicegroups"]         = s_check.servicegroup_name
            cur_gc["servicegroup"].add_host(host.name, act_serv["servicegroups"])
            act_serv["check_command"]         = "!".join([s_check["command_name"]] + s_check.correct_argument_list(arg_temp, dev_variables))
            if act_host["check_command"] == "check-host-alive-2" and s_check["command_name"].startswith("check_ping"):
                self.mach_log("   removing command %s because of %s" % (s_check["command_name"],
                                                                        act_host["check_command"]))
            else:
                ret_field.append(act_serv)
        return ret_field
    def _get_target_ip_info(self, my_net_idxs, net_devices, host_pk, all_hosts_dict, check_hosts):
        host = all_hosts_dict[host_pk]
        traces = []
        targ_netdev_idxs = None
        for targ_netdev_ds in hopcount.objects.filter(
            Q(route_generation=self.latest_gen) &
            Q(s_netdevice__in=my_net_idxs) &
            Q(d_netdevice__in=net_devices.keys())):
            targ_netdev_idxs = [getattr(targ_netdev_ds, key) for key in ["s_netdevice_id", "d_netdevice_id"] if getattr(targ_netdev_ds, key) not in my_net_idxs]
            if not targ_netdev_idxs:
                # special case: peers defined but only local netdevices found, maybe alias ?
                targ_netdev_idxs = [targ_netdev_ds.s_netdevice_id]
            if any([net_devices.has_key(key) for key in targ_netdev_idxs]):
                if targ_netdev_ds.trace:
                    loc_traces = [int(val) for val in targ_netdev_ds.trace.split(":")]
                    if loc_traces[0] != host_pk:
                        loc_traces.reverse()
                traces.append((targ_netdev_ds.value, targ_netdev_idxs[0], loc_traces))
                #break
        traces = sorted(traces)
        if not traces:
            self.mach_log("Cannot reach host %s (check peer_information)" % (host.name),
                          logging_tools.LOG_LEVEL_ERROR)
            valid_ips = []
        else:
            valid_ips = sum([net_devices[nd_pk] for val, nd_pk, loc_trace in traces], [])
            #(",".join([",".join([y for y in net_devices[x]]) for x in targ_netdev_idxs])).split(",")
        return valid_ips, traces
        
class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "md-config-server.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        connection.close()
        #self.register_func("new_pid", self._new_pid)
        #self.register_func("remove_pid", self._remove_pid)
        # prepare directories
        #self._prepare_directories()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._check_nagios_version()
        self._check_relay_version()
        self._log_config()
        self._init_network_sockets()
        self.register_func("register_slave", self._register_slave)
        self.register_func("send_command", self._send_command)
        self.__external_cmd_file = None
        self.register_func("external_cmd_file", self._set_external_cmd_file)
        #self.add_process(db_verify_process("db_verify"), start=True)
        self.add_process(build_process("build"), start=True)
        self._init_em()
        self.register_timer(self._check_db, 3600, instant=True)
        self.register_timer(self._update, 30, instant=True)
        #self.__last_update = time.time() - self.__glob_config["MAIN_LOOP_TIMEOUT"]
        self.send_to_process("build", "rebuild_config", global_config["ALL_HOSTS_NAME"])
    def _check_db(self):
        self.send_to_process("db_verify", "validate")
    def _init_em(self):
        self.__esd, self.__nvn = ("/tmp/.machvect_es", "nagios_ov")
        init_ok = False
        if os.path.isdir(self.__esd):
            ofile = "%s/%s.mvd" % (self.__esd, self.__nvn)
            try:
                file(ofile, "w").write("\n".join(["nag.tot:0:Number of devices monitored by %s:1:1:1" % (global_config["MD_TYPE"]),
                                                  "nag.up:0:Number of devices up:1:1:1",
                                                  "nag.down:0:Number of devices down:1:1:1",
                                                  "nag.unknown:0:Number of devices unknown:1:1:1",
                                                  ""]))
            except:
                self.log("cannot write %s: %s" % (ofile, process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                init_ok = True
        self.__em_ok = init_ok
    def _update(self):
        #dc = self.__db_con.get_connection(SQL_ACCESS)
        #sql_str = "SELECT nhs.current_state AS host_status, nh.display_name AS host_name FROM nagiosdb.%s_hoststatus #nhs, nagiosdb.%s_hosts nh WHERE nhs.host_object_id=nh.host_object_id" % (	
        #    global_config["MD_TYPE"],
        #    global_config["MD_TYPE"])
        sql_str = "SELECT nhs.current_state AS host_status, nh.display_name AS host_name FROM %s_hoststatus nhs, %s_hosts nh WHERE nhs.host_object_id=nh.host_object_id" % (	
            global_config["MD_TYPE"],
            global_config["MD_TYPE"])
        cursor = connections["monitor"].cursor()
        nag_suc = cursor.execute(sql_str)
        nag_dict = dict([(db_rec[1], db_rec[0]) for db_rec in cursor.fetchall()])
        num_tot, num_up, num_down = (len(nag_dict.keys()),
                                     nag_dict.values().count(NAG_HOST_UP),
                                     nag_dict.values().count(NAG_HOST_DOWN))
        num_unknown = num_tot - (num_up + num_down)
        self.log("%s status is: %d up, %d down, %d unknown (%d total)" % (global_config["MD_TYPE"],
                                                                          num_up,
                                                                          num_down,
                                                                          num_unknown,
                                                                          num_tot))
        if not self.__em_ok:
            self._init_em()
        if self.__em_ok:
            ofile = "%s/%s.mvv" % (self.__esd, self.__nvn)
            try:
                file(ofile, "w").write("\n".join(["nag.tot:i:%d" % (num_tot),
                                                  "nag.up:i:%d" % (num_up),
                                                  "nag.down:i:%d" % (num_down),
                                                  "nag.unknown:i:%d" % (num_unknown),
                                                  ""]))
            except:
                self.log("cannot write to file %s: %s" % (ofile,
                                                          process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                pass
        cursor.close()
    def _log_config(self):
        self.log("Config info:")	
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        cluster_location.write_config("monitor_server", global_config)
    def _check_nagios_version(self):
        start_time = time.time()
        md_version, md_type = ("unknown", "unknown")
        for t_daemon in ["icinga", "icinga-init", "nagios", "nagios-init"]:
            if os.path.isfile("/etc/debian_version"):
                cstat, cout = commands.getstatusoutput("dpkg -s %s" % (t_daemon))
                if not cstat:
                    deb_version = [y for y in [x.strip() for x in cout.split("\n")] if y.startswith("Version")]
                    if deb_version:
                        md_version = deb_version[0].split(":")[1].strip()
                    else:
                        self.log("No Version-info found in dpkg-list", logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package %s not found in dpkg-list" % (t_daemon), logging_tools.LOG_LEVEL_ERROR)
            else:
                cstat, cout = commands.getstatusoutput("rpm -q %s" % (t_daemon))
                if not cstat:
                    rpm_m = re.match("^%s-(?P<version>.*)$" % (t_daemon), cout.split()[0].strip())
                    if rpm_m:
                        md_version = rpm_m.group("version")
                    else:
                        self.log("Cannot parse %s" % (cout.split()[0].strip()), logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package %s not found in RPM db" % (t_daemon), logging_tools.LOG_LEVEL_ERROR)
            if md_version != "unknown":
                md_type = t_daemon.split("-")[0]
                break
        # save to local config
        if md_version[0].isdigit():
            global_config.add_config_entries([
                ("MD_TYPE"          , configfile.str_c_var(md_type)),
                ("MD_VERSION"       , configfile.int_c_var(int(md_version.split(".")[0]))),
                ("MD_RELEASE"       , configfile.int_c_var(int(md_version.split(".")[1]))),
                ("MD_VERSION_STRING", configfile.str_c_var(md_version)),
                ("MD_BASEDIR"       , configfile.str_c_var("/opt/%s" % (md_type))),
                ("MAIN_CONFIG_NAME" , configfile.str_c_var(md_type)),
                ("MD_LOCK_FILE"     , configfile.str_c_var("%s.lock" % (md_type))),
            ])
        # device_variable local to the server
        dv = cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_version", description="Version of the Monitor-daemon pacakge", value=md_version)
##        if dv.is_set():
##            dv.set_value(md_version)
##            dv.update(dc)
        cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_version", description="Version of the Monitor-daemon RPM", value=md_version, force_update=True)
        cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_type", description="Type of the Monitor-daemon RPM", value=md_type, force_update=True)
        if md_version == "unknown":
            self.log("No installed monitor-daemon found (version set to %s)" % (md_version), logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed monitor-daemon %s, version %s" % (md_type, md_version))
        end_time = time.time()
        self.log("monitor-daemon version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _check_relay_version(self):
        start_time = time.time()
        relay_version = "unknown"
        if os.path.isfile("/etc/debian_version"):
            cstat, cout = commands.getstatusoutput("dpkg -s host-relay")
            if not cstat:
                deb_version = [y for y in [x.strip() for x in cout.split("\n")] if y.startswith("Version")]
                if deb_version:
                    relay_version = deb_version[0].split(":")[1].strip()
                else:
                    self.log("No Version-info found in dpkg-list", logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("Package host-relay not found in dpkg-list", logging_tools.LOG_LEVEL_ERROR)
        else:
            cstat, cout = commands.getstatusoutput("rpm -q host-relay")
            if not cstat:
                rpm_m = re.match("^host-relay-(?P<version>.*)$", cout.split()[0].strip())
                if rpm_m:
                    relay_version = rpm_m.group("version")
                else:
                    self.log("Cannot parse %s" % (cout.split()[0].strip()), logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("Package host-relay not found in RPM db", logging_tools.LOG_LEVEL_ERROR)
        if relay_version != "unknown":
            relay_split = [int(value) for value in relay_version.split("-")[0].split(".")]
            has_snmp_relayer = False
            if relay_split[0] > 0 or (len(relay_split) == 2 and (relay_split[0] == 0 and relay_split[1] > 4)):
                has_snmp_relayer = True
            if has_snmp_relayer:
                global_config.add_config_entries([("HAS_SNMP_RELAYER", configfile.bool_c_var(True))])
                self.log("host-relay package has snmp-relayer, rewriting database entries for nagios")
        # device_variable local to the server
        if relay_version == "unknown":
            self.log("No installed host-relay found", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed host-relay version %s" % (relay_version))
        end_time = time.time()
        self.log("host-relay version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", global_config["ALL_HOSTS_NAME"])
        submit_c, log_lines = process_tools.submit_at_command("/etc/init.d/host-relay reload")
        for log_line in log_lines:
            self.log(log_line)
        # needed ? FIXME
        #submit_c, log_lines = process_tools.submit_at_command("/etc/init.d/snmp-relay reload")
        #for log_line in log_lines:
        #    self.log(log_line)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("md-config-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/md-config-server start"
            msi_block.stop_command = "/etc/init.d/md-config-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _register_slave(self, *args, **kwargs):
        src_proc, src_id, slave_ip, slave_uuid = args
        conn_str = "tcp://%s:%d" % (slave_ip,
                                    2004)
        if conn_str not in self.__slaves:
            self.log("connecting to slave on %s (%s)" % (conn_str, slave_uuid))
            self.com_socket.connect(conn_str)
            self.__slaves[conn_str] = slave_uuid
    def _handle_ocp_event(self, in_com):
        com_type = in_com["command"].text
        targ_list = [cur_arg.text for cur_arg in in_com.xpath(None, ".//ns:arguments")[0]]
        target_com = {
            "ocsp-event" : "PROCESS_SERVICE_CHECK_RESULT",
            "ochp-event" : "PROCESS_HOST_CHECK_RESULT"}[com_type]
        # rewrite state information
        state_idx, error_state = (1, 1) if com_type == "ochp-event" else (2, 2)
        targ_list[state_idx] = "%d" % ({
            "ok"          : 0,
            "up"          : 0,
            "warning"     : 1,
            "down"        : 1,
            "unreachable" : 2,
            "critical"    : 2,
            "unknown"     : 3}.get(targ_list[state_idx].lower(), error_state))
        if com_type == "ocsp-event":
            pass
        else:
            pass
        out_line = "[%d] %s;%s\n" % (
            int(time.time()),
            target_com,
            ";".join(targ_list))
        if self.__external_cmd_file:
            try:
                file(self.__external_cmd_file, "w").write(out_line)
            except:
                self.log("error writing to %s: %s" % (
                    self.__external_cmd_file,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                raise
        else:
            self.log("no external cmd_file defined", logging_tools.LOG_LEVEL_ERROR)
    def _send_command(self, *args, **kwargs):
        src_proc, src_id, slave_uuid, srv_com = args
        full_uuid = "urn:uuid:%s:relayer" % (slave_uuid)
        self.log("init send of %s bytes to %s" % (len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)
        self.log("done")
    def _set_external_cmd_file(self, *args, **kwargs):
        src_proc, src_id, ext_name = args
        self.log("setting external cmd_file to '%s'" % (ext_name))
        self.__external_cmd_file = ext_name
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "%s:monitor_master" % (uuid_tools.get_uuid().get_urn()))
        client.setsockopt(zmq.SNDHWM, 256)
        client.setsockopt(zmq.RCVHWM, 256)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
            self.__slaves = {}
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(in_data) == 2:
            src_id, data = in_data
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log("error interpreting command: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                # send something back
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                self.com_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                self.log("got command '%s' from '%s'" % (cur_com,
                                                         srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = False
                if cur_com == "rebuild_host_config":
                    send_return = True
                    self.send_to_process("build", "rebuild_config", global_config["ALL_HOSTS_NAME"])
                elif cur_com in ["ocsp-event", "ochp-event"]:
                    self._handle_ocp_event(srv_com)
                if send_return:
                    srv_com["result"] = None
                    # blabla
                    srv_com["result"].attrib.update({"reply" : "ok processed command %s" % (cur_com),
                                                     "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.com_socket.send_unicode(unicode(srv_com))
                else:
                    del cur_com
        else:
            self.log("wrong count of input data frames: %d, first one is %s" % (len(in_data),
                                                                                in_data[0]),
                     logging_tools.LOG_LEVEL_ERROR)
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.com_socket.close()
        self.__log_template.close()
    def thread_loop_post(self):
        if self.__em_ok:
            for f_name in ["%s/%s.mvd" % (self.__esd, self.__nvn),
                           "%s/%s.mvv" % (self.__esd, self.__nvn)]:
                if os.path.isfile(f_name):
                    try:
                        os.unlink(f_name)
                    except:
                        self.log("cannot delete file %s: %s" % (f_name,
                                                                process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                , configfile.str_c_var("idnagios", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var([])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name,
                                                                   prog_name))),
        ("COM_PORT"            , configfile.int_c_var(SERVER_COM_PORT)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (prog_name,
                                           VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="monitor_server")
    if not sql_info.effective_device:
        print "not a monitor_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(
            prog_name + ".py",
            ignore_names=["nagios", "icinga"],
            exclude=configfile.get_manager_pid())

    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("mon-server", "Cluster MonitoringServer", device=sql_info.effective_device).pk))])

    cluster_location.read_config_from_db(global_config, "monitor_server", [
        ("COM_PORT"                    , configfile.int_c_var(SERVER_COM_PORT)),
        ("NETSPEED_WARN_MULT"          , configfile.float_c_var(0.85)),
        ("NETSPEED_CRITICAL_MULT"      , configfile.float_c_var(0.95)),
        ("NETSPEED_DEFAULT_VALUE"      , configfile.int_c_var(10000000)),
        ("CHECK_HOST_ALIVE_PINGS"      , configfile.int_c_var(3)),
        ("CHECK_HOST_ALIVE_TIMEOUT"    , configfile.float_c_var(5.0)),
        ("ENABLE_PNP"                  , configfile.bool_c_var(False)),
        ("ENABLE_LIVESTATUS"           , configfile.bool_c_var(True)),
        ("ENABLE_NDO"                  , configfile.bool_c_var(False)),
        ("ENABLE_NAGVIS"               , configfile.bool_c_var(False)),
        ("PNP_DIR"                     , configfile.str_c_var("/opt/pnp4nagios")),
        ("PNP_URL"                     , configfile.str_c_var("/pnp4nagios")),
        ("NAGVIS_DIR"                  , configfile.str_c_var("/opt/nagvis4icinga")),
        ("NAGVIS_URL"                  , configfile.str_c_var("/nagvis")),
        ("NONE_CONTACT_GROUP"          , configfile.str_c_var("none_group")),
        ("FROM_ADDR"                   , configfile.str_c_var(long_host_name)),
        ("MAIN_LOOP_TIMEOUT"           , configfile.int_c_var(30)),
        ("RETAIN_HOST_STATUS"          , configfile.int_c_var(1)),
        ("RETAIN_SERVICE_STATUS"       , configfile.int_c_var(1)),
        ("NDO_DATA_PROCESSING_OPTIONS" , configfile.int_c_var((2 ** 26 - 1) - (IDOMOD_PROCESS_TIMED_EVENT_DATA - IDOMOD_PROCESS_SERVICE_CHECK_DATA + IDOMOD_PROCESS_HOST_CHECK_DATA))),
        ("EVENT_BROKER_OPTIONS"        , configfile.int_c_var((2 ** 20 - 1) - (BROKER_TIMED_EVENTS + BROKER_SERVICE_CHECKS + BROKER_HOST_CHECKS))),
        ("CCOLLCLIENT_TIMEOUT"         , configfile.int_c_var(6)),
        ("CSNMPCLIENT_TIMEOUT"         , configfile.int_c_var(20)),
        ("MAX_SERVICE_CHECK_SPREAD"    , configfile.int_c_var(5)),
        ("MAX_HOST_CHECK_SPREAD"       , configfile.int_c_var(5)),
        ("MAX_CONCURRENT_CHECKS"       , configfile.int_c_var(500)),
        ("ALL_HOSTS_NAME"              , configfile.str_c_var("***ALL***")),
        ("SERVER_SHORT_NAME"           , configfile.str_c_var(mach_name)),
    ])
    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/md-config-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    if global_config["ENABLE_NAGVIS"]:
        process_tools.fix_directories(global_config["USER"], global_config["GROUP"], [
            {"name"     : os.path.join(global_config["NAGVIS_DIR"], "etc"),
             "walk_dir" : False},
            {"name"     : os.path.join(global_config["NAGVIS_DIR"], "etc", "maps"),
             "walk_dir" : False}
        ])
        process_tools.fix_files(global_config["USER"], global_config["GROUP"], [
            os.path.join(global_config["NAGVIS_DIR"], "etc", "auth.db"),
            os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php"),
            os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php"),
        ])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
    else:
        print "Debugging md-config-server on %s" % (long_host_name)
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__  == "__main__":
    main()
