#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012,2013 Andreas Lang-Nevyjel, init.at
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
""" config part of md-config-server """

import configfile
import process_tools

global_config = configfile.get_global_config(process_tools.get_programm_name())

import base64
import binascii
import cluster_location
import codecs
import config_tools
import ConfigParser
import logging_tools
import os
import re
import server_command
import shutil
import sqlite3
import stat
import time
from lxml.builder import E # @UnresolvedImport

from initat.md_config_server import constants

try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

from django.conf import settings
from django.db.models import Q
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
     mon_ext_host, mon_check_command, mon_period, mon_contact, \
     mon_contactgroup, mon_service_templ, netdevice, network, network_type, net_ip, \
     user, mon_host_cluster, mon_service_cluster, config, md_check_data_store, category, \
     category_tree, TOP_MONITORING_CATEGORY, mon_notification, config_str, config_int, host_check_command

class var_cache(dict):
    def __init__(self, cdg):
        super(var_cache, self).__init__(self)
        self.__cdg = cdg
    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__%d" % (cur_dev.device_group_id),
            "dev__%d" % (cur_dev.pk))
        if global_key not in self:
            def_dict = {"SNMP_VERSION"         : 2,
                        "SNMP_READ_COMMUNITY"  : "public",
                        "SNMP_WRITE_COMMUNITY" : "private"}
            # read global configs
            self[global_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=self.__cdg))])
            # update with def_dict
            for key, value in def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = value
        if dg_key not in self:
            # read device_group configs
            self[dg_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device))])
        if dev_key not in self:
            # read device configs
            self[dev_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev))])
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n in [(dev_key, "d"), (dg_key, "g"), (global_key, "c")]:
            info_dict[key_n] = 0
            for s_key, s_value in self.get(key, {}).iteritems():
                if s_key not in ret_dict:
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        return ret_dict, info_dict

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
            route = master_cfg["monitor_server"][0].get_route_to_other_device(self.__build_process.router_obj, slave_cfg, allow_route_to_other_networks=True)
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
            # target config version directory for distribute
            self.__tcv_dict = {}
            self.dist_ok = True
            self.__send_version = None
        else:
            self.__dir_offset = ""
            # self.__main_dir = os.path.join(self.__main_dir, "slaves", self.__slave_name)
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
    @property
    def var_dir(self):
        return self.__r_dir_dict["var"]
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
    def keys(self):
        return self.__dict.keys()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_process.log("[mc%s] %s" % (
            " %s" % (self.__slave_name) if self.__slave_name else "",
            what), level)
    def get_command_name(self):
        return os.path.join(
            self.__r_dir_dict["var"],
            "ext_com" if global_config["MD_TYPE"] == "nagios" else "icinga.cmd")
    def file_content_info(self, srv_com):
        file_name, version, file_status = (
            srv_com["file_name"].text,
            int(srv_com["version"].text),
            int(srv_com["result"].attrib["state"]),
        )
        self.log("file_content_status for %s is %s (%d), version %d" % (
            file_name,
            srv_com["result"].attrib["reply"],
            file_status,
            version,
            ), file_status)
        if type(self.__tcv_dict[file_name]) in [int, long]:
            if self.__tcv_dict[file_name] == version:
                if file_status in [logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_WARN]:
                    self.__tcv_dict[file_name] = True
                else:
                    self.__tcv_dict[file_name] = False
            else:
                self.log("key %s has waits for different version: %d != %d" % (file_name, version, self.__tcv_dict[file_name]), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("key %s already set to %s" % (file_name, str(self.__tcv_dict[file_name])), logging_tools.LOG_LEVEL_ERROR)
        self._show_pending_info()
    def check_for_resend(self):
        if not self.dist_ok and self.__send_version and abs(self.send_time - time.time()) > 60:
            self.log("resending files")
            self.distribute()
    def distribute(self, cur_version=None):
        if cur_version:
            self.__send_version = cur_version
        if self.slave_ip:
            send_version = self.__send_version
            if send_version:
                self.send_time = time.time()
                self.dist_ok = False
                self.log("start send to slave (version %d)" % (send_version))
                self.__build_process.send_pool_message("register_slave", self.slave_ip, self.monitor_server.uuid)
                srv_com = server_command.srv_command(
                    command="register_master",
                    host="DIRECT",
                    port="0",
                    master_ip=self.master_ip,
                    master_port="%d" % (constants.SERVER_COM_PORT))
                time.sleep(0.2)
                self.__build_process.send_command(self.monitor_server.uuid, unicode(srv_com))
                # send content of /etc
                dir_offset = len(self.__w_dir_dict["etc"])
                for cur_dir, dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                    rel_dir = cur_dir[dir_offset + 1:]
                    for cur_file in file_names:
                        full_r_path = os.path.join(self.__w_dir_dict["etc"], rel_dir, cur_file)
                        full_w_path = os.path.join(self.__r_dir_dict["etc"], rel_dir, cur_file)
                        if os.path.isfile(full_r_path):
                            self.__tcv_dict[full_w_path] = send_version
                            srv_com = server_command.srv_command(
                                command="file_content",
                                host="DIRECT",
                                slave_name=self.__slave_name,
                                port="0",
                                uid="%d" % (os.stat(full_r_path)[stat.ST_UID]),
                                gid="%d" % (os.stat(full_r_path)[stat.ST_GID]),
                                version="%d" % (send_version),
                                file_name="%s" % (full_w_path),
                                content=base64.b64encode(file(full_r_path, "r").read())
                            )
                            self.__build_process.send_command(self.monitor_server.uuid, unicode(srv_com))
                srv_com = server_command.srv_command(
                    command="call_command",
                    host="DIRECT",
                    port="0",
                    version="%d" % (send_version),
                    cmdline="/etc/init.d/icinga reload")
                self.__build_process.send_command(self.monitor_server.uuid, unicode(srv_com))
                self._show_pending_info()
            else:
                self.log("no send version set", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("slave has no valid IP-address, skipping send", logging_tools.LOG_LEVEL_ERROR)
    def _show_pending_info(self):
        pend_keys = [key for key, value in self.__tcv_dict.iteritems() if type(value) != bool]
        error_keys = [key for key, value in self.__tcv_dict.iteritems() if value == False]
        self.log("%d total, %s pending, %s error" % (
            len(self.__tcv_dict),
            logging_tools.get_plural("remote file", len(pend_keys)),
            logging_tools.get_plural("remote file", len(error_keys))),
                 )
        if not pend_keys and not error_keys:
            self.log("actual distribution_set %d is OK" % (self.__send_version))
            self.dist_ok = True
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
            "var/spool",
            "var/spool/checkresults"]
        if process_tools.get_sys_bits() == 64:
            dir_names.append("lib64")
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
        if self.master:
            self.log("not clearing %s dir (master)" % (self.__w_dir_dict["etc"]))
        else:
            self.log("not clearing %s dir (slave)" % (self.__w_dir_dict["etc"]))
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
                    # ("file_group", ""),
                    ("file_mode", "660"),
                    # ("http_proxy", ""),
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
                    ("base", "%s/" % (os.path.normpath(global_config["NAGVIS_DIR"]))),
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
                    # ("stylesheet", ""),
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
                # ("backend_merlinmy_1", [
                #    ("backendtype", "merlinmy"),
                #    ("dbhost", "localhost"),
                #    ("dbport", 3306),
                #    ("dbname", "merlin"),
                #    ("dbuser", "merlin"),
                #    ("dbpass", "merlin"),
                #    ("maxtimewithoutupdate", 180),
                #    ("htmlcgi", "/nagios/cgi-bin"),
                #    ]),
                # ("rotation_demo", [
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
                    # ("unreachable_ack_bgcolor", ""),
                    # ("unreachable_downtime_bgcolor", ""),
                    ("down_bgcolor", "#FF0000"),
                    ("down_color", "#FF0000"),
                    # ("down_ack_bgcolor", ""),
                    # ("down_downtime_bgcolor", ""),
                    ("critical_bgcolor", "#FF0000"),
                    ("critical_color", "#FF0000"),
                    # ("critical_ack_bgcolor", ""),
                    # ("critical_downtime_bgcolor", ""),
                    ("warning_bgcolor", "#FFFF00"),
                    ("warning_color", "#FFFF00"),
                    # ("warning_ack_bgcolor", ""),
                    # ("warning_downtime_bgcolor", ""),
                    ("unknown_bgcolor", "#FFCC66"),
                    ("unknown_color", "#FFCC66"),
                    # ("unknown_ack_bgcolor", ""),
                    # ("unknown_downtime_bgcolor", ""),
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
                    # ("unknown_sound", ""),
                    # ("error_sound", ""),
                    # ("up_sound", ""),
                    # ("ok_sound", ""),
                    # ("unchecked_sound", ""),
                    # ("pending_sound", ""),

                ])
                ]:
                nagvis_main_cfg.add_section(sect_name)
                for key, value in var_list:
                    nagvis_main_cfg.set(sect_name, key, unicode(value))
            with open(os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php")    , "wb") as nvm_file:
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
        ndomod_cfg = base_config(
            NDOMOD_NAME,
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
            ndo2db_cfg = base_config(
                NDO2DB_NAME,
                belongs_to_ndo=True,
                values=[
                    ("ndo2db_user"            , "idnagios"),
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
        enable_perf = global_config["ENABLE_PNP"] or global_config["ENABLE_COLLECTD"]
        main_values = [
            ("log_file"                         , "%s/%s.log" % (
                self.__r_dir_dict["var"],
                global_config["MD_TYPE"])),
            ("cfg_file"                         , []),
            ("resource_file"                    , "%s/%s.cfg" % (
                self.__r_dir_dict["etc"],
                resource_cfg.get_name())),
            ("%s_user" % (global_config["MD_TYPE"]) , "idnagios"),
            ("%s_group" % (global_config["MD_TYPE"]), "idg"),
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
            ("retain_state_information"         , global_config["RETAIN_SERVICE_STATUS"]), # if self.master else 0),
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
            ("process_performance_data"         , (1 if enable_perf else 0) if self.master else 0),
            ("obsess_over_services"             , 1 if not self.master else 0),
            ("obsess_over_hosts"                , 1 if not self.master else 0),
            ("check_for_orphaned_services"      , 0),
            ("check_service_freshness"          , 0),
            ("freshness_check_interval"         , 15),
            ("enable_flap_detection"            , 1 if global_config["ENABLE_FLAP_DETECTION"] else 0),
            ("low_service_flap_threshold"       , 25),
            ("high_service_flap_threshold"      , 50),
            ("low_host_flap_threshold"          , 25),
            ("high_host_flap_threshold"         , 50),
            ("date_format"                      , "euro"),
            ("illegal_object_name_chars"        , r"~!$%^&*|'\"<>?),()"),
            ("illegal_macro_output_chars"       , r"~$&|'\"<>"),
            ("admin_email"                      , "lang-nevyjel@init.at"),
            ("admin_pager"                      , "????"),
            # ("debug_file"      , os.path.join(self.__r_dir_dict["var"], "icinga.dbg")),
            # ("debug_level"     , -1),
            # ("debug_verbosity" , 2),
            # NDO stuff
        ]
        lib_dir_name = "lib64" if process_tools.get_sys_bits() == 64 else "lib"
        for sub_dir_name in ["device.d"]:
            sub_dir = os.path.join(self.__w_dir_dict["etc"], sub_dir_name)
            if not os.path.isdir(sub_dir):
                os.mkdir(sub_dir)
        for sub_dir_name in ["df_settings", "manual"]:
            sub_dir = os.path.join(self.__w_dir_dict["etc"], sub_dir_name)
            if os.path.isdir(sub_dir):
                shutil.rmtree(sub_dir)
        if self.master:
            main_values.append(
                ("cfg_dir", os.path.join(self.__r_dir_dict["etc"], "manual")),
            )
            if global_config["ENABLE_LIVESTATUS"]:
                main_values.extend([
                    ("*broker_module", "%s/mk-livestatus/livestatus.o %s/live" % (
                        self.__r_dir_dict[lib_dir_name],
                        self.__r_dir_dict["var"]))
                ])
            if enable_perf:
                if global_config["ENABLE_COLLECTD"]:
                    main_values.extend([
                        ("service_perfdata_file"         , os.path.join(self.__r_dir_dict["var"], "service-perfdata")),
                        ("host_perfdata_file"            , os.path.join(self.__r_dir_dict["var"], "host-perfdata")),
                        ("service_perfdata_file_template", "<rec type='service' time='$TIMET$' host='$HOSTNAME$' sdesc='$SERVICEDESC$' perfdata='$SERVICEPERFDATA$' com='$SERVICECHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$' ss='$SERVICESTATE$' sstype='$SERVICESTATETYPE$'/>"),
                        ("host_perfdata_file_template"   , "<rec type='host' time='$TIMET$' host='$HOSTNAME$' perfdata='$HOSTPERFDATA$' com='$HOSTCHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$'/>"),
                    ])
                else:
                    main_values.extend([
                        ("service_perfdata_file"         , os.path.join(global_config["PNP_DIR"], "var/service-perfdata")),
                        ("host_perfdata_file"            , os.path.join(global_config["PNP_DIR"], "var/host-perfdata")),
                        ("service_perfdata_file_template", "DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$"),
                        ("host_perfdata_file_template"   , "DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$"),
                    ])
                main_values.extend([
                    # ("host_perfdata_command"   , "process-host-perfdata"),
                    # ("service_perfdata_command", "process-service-perfdata"),
                    ("service_perfdata_file_mode"               , "a"),
                    ("service_perfdata_file_processing_interval", "15"),
                    ("service_perfdata_file_processing_command" , "process-service-perfdata-file"),
                    ("host_perfdata_file_mode"                  , "a"),
                    ("host_perfdata_file_processing_interval"   , "15"),
                    ("host_perfdata_file_processing_command"    , "process-host-perfdata-file"),
                ])
            if global_config["ENABLE_NDO"]:
                if global_config["MD_TYPE"] == "nagios":
                    main_values.append(("*broker_module", "%s/ndomod-%dx.o config_file=%s/%s.cfg" % (
                        self.__r_dir_dict["bin"],
                        global_config["MD_VERSION"],
                        self.__r_dir_dict["etc"],
                        NDOMOD_NAME)))
                else:
                    if os.path.exists(os.path.join(self.__r_dir_dict[lib_dir_name], "idomod.so")):
                        main_values.append(
                            ("*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                                self.__r_dir_dict[lib_dir_name],
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
                ("cfg_dir"                , []),
                ("ochp_command"           , "ochp-command"),
                ("ocsp_command"           , "ocsp-command"),
                ("stalking_event_handlers_for_hosts"   , 1),
                ("stalking_event_handlers_for_services", 1),
            ])
        if global_config["MD_VERSION"] >= 3 or global_config["MD_TYPE"] == "icinga":
            main_values.extend(
                [
                    ("object_cache_file"            , "%s/object.cache" % (self.__r_dir_dict["var"])),
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
                             ("notification" , 30), ("ocsp"      , 5), ("perfdata"     , 5)]:
            main_cfg["%s_timeout" % (to_descr)] = to
        for th_descr, th in [("low_service", 5.0), ("high_service", 20.0),
                             ("low_host"   , 5.0), ("high_host"   , 20.0)]:
            main_cfg["%s_flap_threshold" % (th_descr)] = th
        admin_list = list([cur_u.login for cur_u in user.objects.filter(Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)) if cur_u.has_perm("backbone.all_devices")])
        if admin_list:
            def_user = ",".join(admin_list)
        else:
            def_user = "%sadmin" % (global_config["MD_TYPE"])
        cgi_config = base_config(
            "cgi",
            is_host_file=True,
            values=[("main_config_file"         , "%s/%s.cfg" % (
                self.__r_dir_dict["etc"], global_config["MAIN_CONFIG_NAME"])),
                    ("physical_html_path"       , "%s" % (self.__r_dir_dict["share"])),
                    ("url_html_path"            , "/%s" % (global_config["MD_TYPE"])),
                    ("show_context_help"        , 0),
                    ("use_authentication"       , 1),
                    # ("default_user_name"        , def_user),
                    ("default_statusmap_layout" , 5),
                    ("default_statuswrl_layout" , 4),
                    ("refresh_rate"             , 60),
                    ("lock_author_name"         , 1),
                    ("authorized_for_system_information"       , def_user),
                    ("authorized_for_system_commands"          , def_user),
                    ("authorized_for_configuration_information", def_user),
                    ("authorized_for_all_hosts"                , def_user),
                    ("authorized_for_all_host_commands"        , def_user),
                    ("authorized_for_all_services"             , def_user),
                    ("authorized_for_all_service_commands"     , def_user)] +
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
                www_user, www_group = ("www-data", "www-data")
            elif os.path.isfile("/etc/redhat-release") or os.path.islink("/etc/redhat-release"):
                www_user, www_group = ("apache", "apache")
            else:
                www_user, www_group = ("wwwrun", "www")
            wsgi_config = base_config(
                "uwsgi",
                is_host_file=True,
                headers=["[uwsgi]"],
                values=[
                    ("chdir"           , self.__r_dir_dict[""]),
                    ("plugin-dir"      , "/opt/cluster/%s" % (lib_dir_name)),
                    ("cgi-mode"        , "true"),
                    ("master"          , "true"),
                    # set vacuum to false because of problems with uwsgi 1.9
                    ("vacuum"          , "false"),
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
                    # ("route"           , "^/icinga/cgi-bin basicauth:Monitor,init:init"),
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
                    cur_u.password_ssha.split(":", 1)[1]) for cur_u in user.objects.filter(Q(active=True)) if cur_u.password_ssha.count(":")] + [""]))
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
                    # pprint.pprint(perms_dict)
                    cur_c.execute("INSERT INTO roles2perms VALUES(%d, %d)" % (
                        admin_role_id,
                        perms_dict["*.*.*"]))
                    role_dict = dict([(cur_role[1].lower().split()[0], cur_role[0]) for cur_role in cur_c.execute("SELECT * FROM roles")])
                    self.log("role dict: %s" % (", ".join(["%s=%d" % (key, value) for key, value in role_dict.iteritems()])))
                    # get nagivs root points
                    nagvis_rds = device.objects.filter(Q(automap_root_nagvis=True)).select_related("domain_tree_node", "device_group")
                    self.log("%s: %s" % (logging_tools.get_plural("NagVIS root device", len(nagvis_rds)),
                                         ", ".join([unicode(cur_dev) for cur_dev in nagvis_rds])))
                    devg_lut = {}
                    for cur_dev in nagvis_rds:
                        devg_lut.setdefault(cur_dev.device_group.pk, []).append(cur_dev.full_name)
                    for cur_u in user.objects.filter(Q(active=True) & Q(mon_contact__pk__gt=0)).prefetch_related("allowed_device_groups"):
                        # check for admin
                        if cur_u.has_perm("backbone.all_devices"):
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
                                        try:
                                            perms_dict[perm_name] = cur_c.execute("INSERT INTO perms VALUES(Null, '%s', '%s', '%s')" % (
                                                perm_name.split(".")[0].title(),
                                                perm_name.split(".")[1],
                                                perm_name.split(".")[2]
                                                )).lastrowid
                                            self.log("permission '%s' has id %d" % (perm_name, perms_dict[perm_name]))
                                        except:
                                            self.log("cannot create permission '%s': %s" % (perm_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                                        add_perms.append(perm_name)
                            # add perms
                            for new_perm in add_perms:
                                if new_perm in perms_dict:
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
            if isinstance(stuff, base_config) or isinstance(stuff, host_type_config) or isinstance(stuff, config_dir):
                if isinstance(stuff, config_dir):
                    cfg_written.extend(stuff.create_content(self.__w_dir_dict["etc"]))
                else:
                    if isinstance(stuff, base_config):
                        act_cfg_name = stuff.get_file_name(self.__w_dir_dict["etc"])
                    else:
                        act_cfg_name = os.path.normpath(os.path.join(
                            self.__w_dir_dict["etc"],
                            "%s.cfg" % (key)))
                    # print "*", key, act_cfg_name
                    stuff.create_content()
                    if stuff.act_content != stuff.old_content:
                        try:
                            codecs.open(act_cfg_name, "w", "utf-8").write(u"\n".join(stuff.act_content + [u""]))
                        except IOError:
                            self.log(
                                "Error writing content of %s to %s: %s" % (
                                    key,
                                    act_cfg_name,
                                    process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_CRITICAL)
                            stuff.act_content = []
                        else:
                            os.chmod(act_cfg_name, 0644)
                            cfg_written.append(key)
                    elif not stuff.act_content:
                        # crate empty config file
                        empty_cfg_written.append(act_cfg_name)
                        self.log("creating empty file %s" % (act_cfg_name),
                                 logging_tools.LOG_LEVEL_WARN)
                        open(act_cfg_name, "w").write("\n")
                    else:
                        # no change
                        pass
        end_time = time.time()
        if cfg_written:
            self.log(
                "wrote %s (%s) in %s" % (
                    logging_tools.get_plural("config_file", len(cfg_written)),
                    ", ".join(cfg_written),
                    logging_tools.get_diff_time_str(end_time - start_time)
                )
            )
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
    def add_config_dir(self, config_dir):
        self[config_dir.get_name()] = config_dir
    def __setitem__(self, key, value):
        self.__dict[key] = value
        config_keys = self.__dict.keys()
        new_file_keys = sorted([
            "%s/%s.cfg" % (self.__r_dir_dict["etc"], key) for key, value in self.__dict.iteritems() if
            (not isinstance(value, base_config) or not (value.is_host_file or value.belongs_to_ndo)) and (not isinstance(value, config_dir))
        ])
        old_file_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"]
        new_dir_keys = sorted(["%s/%s" % (self.__r_dir_dict["etc"], key) for key, value in self.__dict.iteritems() if isinstance(value, config_dir)])
        old_dir_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_dir"]
        write_cfg = False
        if old_file_keys != new_file_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"] = new_file_keys
            write_cfg = True
        if old_dir_keys != new_dir_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_dir"] = new_dir_keys
            write_cfg = True
        if write_cfg:
            self._write_entries()
    def __getitem__(self, key):
        return self.__dict[key]

class base_config(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.__dict, self.__key_list = ({}, [])
        self.is_host_file = kwargs.get("is_host_file", False)
        self.belongs_to_ndo = kwargs.get("belongs_to_ndo", False)
        self.headers = kwargs.get("headers", [])
        for key, value in kwargs.get("values", []):
            self[key] = value
        self.act_content = []
    def get_name(self):
        return self.__name
    def get_file_name(self, etc_dir):
        if self.__name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(etc_dir, "%s.cfg" % (self.__name)))
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

class nag_config(dict):
    def __init__(self, obj_type, name, **kwargs):
        self.obj_type = obj_type
        self._name = name
        super(nag_config, self).__init__()
        self.update(kwargs)
    def __setitem__(self, key, value):
        if key in self:
            val_p = super(nag_config, self).__getitem__(key).split(",")
            if "-" in val_p:
                val_p.remove("-")
            if value not in val_p:
                val_p.append(value)
            super(nag_config, self).__setitem__(key, ",".join(val_p))
        else:
            super(nag_config, self).__setitem__(key, value)
    def __getitem__(self, key):
        if key == "name":
            return self._name
        else:
            return super(nag_config, self).__getitem__(key)

class host_type_config(object):
    def __init__(self, build_process):
        self.__build_proc = build_process
        self.act_content, self.prev_content = ([], [])
    def clear(self):
        self.__obj_list, self.__dict = ([], {})
    def is_valid(self):
        return True
    def create_content(self):
        # if self.act_content:
        self.old_content = self.act_content
        self.act_content = self.get_content()
    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, level)
    def get_content(self):
        cn = self.get_name()
        act_list = self.get_object_list()
        dest_type = self.get_name()
        content = []
        if act_list:
            for act_le in act_list:
                content.extend(
                    ["define %s {" % (dest_type)] + \
                    ["  %s %s" % (act_key, unicode(val)) for act_key, val in act_le.iteritems()] + \
                    ["}", ""]
                )
            self.log("created %s for %s" % (
                logging_tools.get_plural("entry", len(act_list)),
                dest_type))
        return content
    def get_xml(self):
        res_xml = getattr(E, "%s_list" % (self.get_name()))()
        for act_le in self.get_object_list():
            res_xml.append(getattr(E, self.get_name())(**dict([(key, unicode(value)) for key, value in act_le.iteritems()])))
        return [res_xml]

class time_periods(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_time_periods_from_db()
    def get_name(self):
        return "timeperiod"
    def _add_time_periods_from_db(self):
        for cur_per in mon_period.objects.all():
            nag_conf = nag_config("timeperiod",
                                  cur_per.name,
                                  timeperiod_name=cur_per.name,
                                  alias=cur_per.alias or "-")
            for short_s, long_s in [
                ("mon", "monday"), ("tue", "tuesday"), ("wed", "wednesday"), ("thu", "thursday"),
                ("fri", "friday"), ("sat", "saturday"), ("sun", "sunday")]:
                nag_conf[long_s] = getattr(cur_per, "%s_range" % (short_s))
            self.__dict[cur_per.pk] = nag_conf
            self.__obj_list.append(nag_conf)
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()

class all_service_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        # dict : which host has which service_group defined
        self.__host_srv_lut = {}
        self.cat_tree = category_tree()
        self._add_servicegroups_from_db()
    def get_name(self):
        return "servicegroup"
    def _add_servicegroups_from_db(self):
        for cat_pk in self.cat_tree.get_sorted_pks():
            cur_cat = self.cat_tree[cat_pk]
            nag_conf = nag_config("servicegroup",
                                  cur_cat.full_name,
                                  servicegroup_name=cur_cat.full_name,
                                  alias="%s group" % (cur_cat.full_name))
            self.__host_srv_lut[cur_cat.full_name] = set()
            self.__dict[cur_cat.pk] = nag_conf
            self.__obj_list.append(nag_conf)
    def clear_host(self, host_name):
        for key, value in self.__host_srv_lut.iteritems():
            if host_name in value:
                value.remove(host_name)
    def add_host(self, host_name, srv_groups):
        for srv_group in srv_groups.split(","):
            self.__host_srv_lut[srv_group].add(host_name)
    def get_object_list(self):
        return [obj for obj in self.__obj_list if self.__host_srv_lut[obj["name"]]]
    def values(self):
        return self.__dict.values()

class all_commands(host_type_config):
    def __init__(self, gen_conf, build_proc):
        check_command.gen_conf = gen_conf
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)
    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_notify_commands()
        self._add_commands_from_db(gen_conf)
    def get_name(self):
        return "command"
    def _expand_str(self, in_str):
        for key, value in self._str_repl_dict.iteritems():
            in_str = in_str.replace(key, value)
        return in_str
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
        send_sms_prog = "/opt/icinga/bin/sendsms"
        from_addr = "%s@%s" % (global_config["MD_TYPE"],
                               global_config["FROM_ADDR"])

        self._str_repl_dict = {
            "$INIT_MONITOR_INFO$" : "%s %s" % (md_type, md_vers),
            "$INIT_CLUSTER_NAME$" : "%s" % (cluster_name),
        }

        self.__obj_list.append(
            nag_config(
                "command",
                "dummy-notify",
                command_name="dummy-notify",
                command_line="/usr/bin/true",
            )
        )
        for cur_not in mon_notification.objects.filter(Q(enabled=True)):
            if cur_not.channel == "mail":
                command_line = r"%s -f '%s' -s '%s' -t $CONTACTEMAIL$ -- '%s'" % (
                    send_mail_prog,
                    from_addr,
                    self._expand_str(cur_not.subject),
                    self._expand_str(cur_not.content),
                )
            else:
                command_line = r"%s $CONTACTPAGER$ '%s'" % (
                    send_sms_prog,
                    self._expand_str(cur_not.content),
                )
            nag_conf = nag_config(
                "command",
                cur_not.name,
                command_name=cur_not.name,
                command_line=command_line.replace("\n", "\\n"),
            )
            self.__obj_list.append(nag_conf)
    def _add_commands_from_db(self, gen_conf):
        command_names = set()
        for hc_com in host_check_command.objects.all():
            cur_nc = nag_config(
                                "command",
                                hc_com.name,
                                command_name=hc_com.name,
                                command_line=hc_com.command_line)
            self.__obj_list.append(cur_nc)
            command_names.add(hc_com.name)
        ngc_re1 = re.compile("^\@(?P<special>\S+)\@(?P<comname>\S+)$")
        check_coms = list(mon_check_command.objects.all()
                          .prefetch_related("categories")
                          .select_related("mon_service_templ", "config"))
        enable_perfd = global_config["ENABLE_PNP"] or global_config["ENABLE_COLLECTD"]
        if enable_perfd and gen_conf.master:
            if global_config["ENABLE_COLLECTD"]:
                check_coms += [
                    mon_check_command(
                        name="process-service-perfdata-file",
                        command_line="/opt/cluster/sbin/send_collectd_zmq %s/service-perfdata" % (
                            gen_conf.var_dir
                            ),
                        description="Process service performance data",
                        ),
                    mon_check_command(
                        name="process-host-perfdata-file",
                        command_line="/opt/cluster/sbin/send_collectd_zmq %s/host-perfdata" % (
                            gen_conf.var_dir
                            ),
                        description="Process host performance data",
                        ),
                ]
            else:
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
                            global_config["PNP_DIR"]
                            ),
                        description="Process host performance data",
                        ),
                ]
        for ngc in check_coms + [
            mon_check_command(
                name="ochp-command",
                command_line="$USER2$ -m DIRECT -s ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"%s\"" % ("$HOSTOUTPUT$|$HOSTPERFDATA$" if enable_perfd else "$HOSTOUTPUT$"),
                description="OCHP Command"
                ),
            mon_check_command(
                name="ocsp-command",
                command_line="$USER2$ -m DIRECT -s ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"%s\" " % ("$SERVICEOUTPUT$|$SERVICEPERFDATA$" if enable_perfd else "$SERVICEOUTPUT$"),
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
            # pprint.pprint(ngc)
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
            if ngc.pk:
                cats = ngc.categories.all().values_list("full_name", flat=True)
            else:
                cats = [TOP_MONITORING_CATEGORY]
            cc_s = check_command(
                ngc_name,
                ngc.command_line,
                ngc.config.name if ngc.config_id else None,
                ngc.mon_service_templ.name if ngc.mon_service_templ_id else None,
                ngc.description,
                ngc.device_id,
                special,
                servicegroup_names=cats,
                enable_perfdata=ngc.enable_perfdata,
                db_entry=ngc,
                volatile=ngc.volatile,
            )
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
            not_h_list = list(contact.notifications.filter(Q(channel="mail") & Q(not_type="host") & Q(enabled=True)))
            not_s_list = list(contact.notifications.filter(Q(channel="mail") & Q(not_type="service") & Q(enabled=True)))
            if len(contact.user.pager) > 5:
                # check for pager number
                not_h_list.extend(list(contact.notifications.filter(Q(channel="sms") & Q(not_type="host") & Q(enabled=True))))
                not_s_list.extend(list(contact.notifications.filter(Q(channel="sms") & Q(not_type="service") & Q(enabled=True))))
            if contact.mon_alias:
                alias = contact.mon_alias
            elif contact.user.comment:
                alias = contact.user.comment
            else:
                alias = full_name
            nag_conf = nag_config(
                "contact",
                full_name,
                contact_name=contact.user.login,
                host_notification_period=gen_conf["timeperiod"][contact.hnperiod_id]["name"],
                service_notification_period=gen_conf["timeperiod"][contact.snperiod_id]["name"],
                alias=alias,
            )
            if not_h_list:
                nag_conf["host_notification_commands"] = ",".join([entry.name for entry in not_h_list])
            else:
                nag_conf["host_notification_commands"] = "dummy-notify"
            if not_s_list:
                nag_conf["service_notification_commands"] = ",".join([entry.name for entry in not_s_list])
            else:
                nag_conf["service_notification_commands"] = "dummy-notify"
            for targ_opt, pairs in [
                ("host_notification_options"   , [("hnrecovery", "r"), ("hndown"    , "d"), ("hnunreachable", "u"), ("hflapping", "f"), ("hplanned_downtime", "s")]),
                ("service_notification_options", [("snrecovery", "r"), ("sncritical", "c"), ("snwarning"    , "w"), ("snunknown", "u"), ("sflapping", "f"), ("splanned_downtime", "s")])]:
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
# #        if False:
# #            for std_user in user.objects.filter(Q(mon_contact=None) & (Q(active=True))):
# #                devg_ok = len(std_user.allowed_device_groups.all()) > 0 or User.objects.get(Q(username=std_user.login)).has_perm("backbone.all_devices")
# #                if devg_ok:
# #                    full_name = ("%s %s" % (std_user.first_name, std_user.last_name)).strip().replace(" ", "_") or std_user.login
# #                    nag_conf = nag_config(
# #                        full_name,
# #                        contact_name=std_user.login,
# #                        alias=std_user.comment or full_name,
# #                        host_notifications_enabled=0,
# #                        service_notifications_enabled=0,
# #                        host_notification_commands="host-notify-by-email",
# #                        service_notification_commands="notify-by-email",
# #                    )
# #                    self.__obj_list.append(nag_conf)
# #                    #self.__dict[contact.pk] = nag_conf
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
        self.__dict[0] = nag_config(
            "contactgroup",
            global_config["NONE_CONTACT_GROUP"],
            contactgroup_name=global_config["NONE_CONTACT_GROUP"],
            alias="None group")
        for cg_group in mon_contactgroup.objects.all().prefetch_related("members"):
            nag_conf = nag_config(
                "contactgroup",
                cg_group.name,
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
        self.cat_tree = category_tree()
        self._add_host_groups_from_db(gen_conf)
    def get_name(self):
        return "hostgroup"
    def _add_host_groups_from_db(self, gen_conf):
        if gen_conf.has_key("device.d"):
            host_pks = gen_conf["device.d"].host_pks
            host_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(device_group__pk__in=host_pks)
            if host_pks:
                # hostgroups by devicegroups
                # distinct is important here
                for h_group in device_group.objects.filter(host_filter).prefetch_related("device_group").distinct():
                    nag_conf = nag_config(
                        "hostgroup",
                        h_group.name,
                        hostgroup_name=h_group.name,
                        alias=h_group.description or h_group.name,
                        members="-")
                    self.__dict[h_group.pk] = nag_conf
                    self.__obj_list.append(nag_conf)
                    nag_conf["members"] = ",".join([cur_dev.full_name for cur_dev in h_group.device_group.filter(Q(pk__in=host_pks))])
                # hostgroups by categories
                for cat_pk in self.cat_tree.get_sorted_pks():
                    cur_cat = self.cat_tree[cat_pk]
                    nag_conf = nag_config(
                        "hostgroup",
                        cur_cat.full_name,
                        hostgroup_name=cur_cat.full_name,
                        alias=cur_cat.comment or cur_cat.full_name,
                        members="-")
                    nag_conf["members"] = ",".join([cur_dev.full_name for cur_dev in cur_cat.device_set.filter(host_filter).filter(Q(pk__in=host_pks))])
                    if nag_conf["members"]:
                        self.__obj_list.append(nag_conf)
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

class config_dir(object):
    def __init__(self, name, gen_conf, build_proc):
        self.name = "%s.d" % (name)
        self.__build_proc = build_proc
        self.host_pks = set()
        self.refresh(gen_conf)
        self.act_content, self.prev_content = ([], [])
    def clear(self):
        self.__dict = {}
    def refresh(self, gen_conf):
        # ???
        self.clear()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, log_level)
    def get_name(self):
        return self.name
    def add_device(self, c_list, host):
        host_conf = c_list[0]
        self.host_pks.add(host.pk)
        self[host_conf["name"]] = c_list
    def values(self):
        return self.__dict.values()
    def __contains__(self, key):
        return key in self.__dict
    def __getitem__(self, key):
        return self.__dict[key]
    def __setitem__(self, key, value):
        self.__dict[key] = value
    def __delitem__(self, key):
        del self.__dict[key]
    def has_key(self, key):
        return self.__dict.has_key(key)
    def keys(self):
        return self.__dict.keys()
    def create_content(self, etc_dir):
        cfg_written = []
        # check for missing files, FIXME
        cfg_dir = os.path.join(etc_dir, self.name)
        self.log("creating entries in %s" % (cfg_dir))
        new_entries = set()
        for key in sorted(self.keys()):
            new_entries.add("%s.cfg" % (key))
            cfg_name = os.path.join(cfg_dir, "%s.cfg" % (key))
            # check for changed content, FIXME
            content = self._create_sub_content(key)
            try:
                codecs.open(cfg_name, "w", "utf-8").write(u"\n".join(content + [u""]))
            except IOError:
                self.log(
                    "Error writing content of %s to %s: %s" % (
                        key,
                        cfg_name,
                        process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_CRITICAL)
            else:
                os.chmod(cfg_name, 0644)
                cfg_written.append(key)
        present_entries = set(os.listdir(cfg_dir))
        del_entries = present_entries - new_entries
        if del_entries:
            self.log("removing %s from %s" % (logging_tools.get_plural("entry", len(del_entries)),
                                              cfg_dir), logging_tools.LOG_LEVEL_WARN)
            for del_entry in del_entries:
                full_name = os.path.join(cfg_dir, del_entry)
                try:
                    os.unlink(full_name)
                except:
                    self.log("cannot remove %s: %s" % (
                        full_name,
                        process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removed %s" % (full_name), logging_tools.LOG_LEVEL_WARN)
        return cfg_written
    def _create_sub_content(self, key):
        content = []
        for entry in self[key]:
            content.extend(
                ["define %s {" % (entry.obj_type)] + \
                ["  %s %s" % (act_key, unicode(val)) for act_key, val in entry.iteritems()] + \
                ["}", ""])
        return content
    def get_xml(self):
        res_dict = {}
        for key, value in self.__dict.iteritems():
            prev_tag = None
            for entry in value:
                if entry.obj_type != prev_tag:
                    if entry.obj_type not in res_dict:
                        res_xml = getattr(E, "%s_list" % (entry.obj_type))()
                        res_dict[entry.obj_type] = res_xml
                    else:
                        res_xml = res_dict[entry.obj_type]
                    prev_tag = entry.obj_type
                res_xml.append(getattr(E, entry.obj_type)(**dict([(key, unicode(value)) for key, value in entry.iteritems()])))
        return list(res_dict.itervalues())

class all_hosts(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
    def refresh(self, gen_conf):
        pass
    def get_name(self):
        return "host"
    def get_object_list(self):
        return []

class all_hosts_extinfo(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
    def refresh(self, gen_conf):
        pass
    def get_name(self):
        return "hostextinfo"
    def get_object_list(self):
        return []

class all_services(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
    def refresh(self, gen_conf):
        pass
    def get_name(self):
        return "service"
    def get_object_list(self):
        return []

class check_command(object):
    def __init__(self, name, com_line, config, template, descr, device=0, special=None, **kwargs):
        self.__name = name
        self.__com_line = com_line
        self.config = config
        self.template = template
        self.device = device
        self.servicegroup_names = kwargs.get("servicegroup_names", [TOP_MONITORING_CATEGORY])
        self.__descr = descr.replace(",", ".")
        self.enable_perfdata = kwargs.get("enable_perfdata", False)
        self.volatile = kwargs.get("volatile", False)
        self.__special = special
        self.mon_check_command = None
        if "db_entry" in kwargs:
            if kwargs["db_entry"].pk:
                self.mon_check_command = kwargs["db_entry"]
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
        """
        handle the various input formats:

        ${ARG#:var_name:default}
        ${ARG#:var_name:default}$
        ${ARG#:default}
        ${ARG#:default}$
        $ARG#$

        """
        com_re = re.compile("^(?P<pre_text>.*?)((\${ARG(?P<arg_num_1>\d+):(?P<var_name>[^:^}]+?)(\:(?P<default>[^}]+))*}\$*)|(\$ARG(?P<arg_num_2>\d+)\$))+(?P<post_text>.*)$")
        cur_line = self.command_line
        # where to start the match to avoid infinite loop
        s_idx = 0
        while True:
            cur_m = com_re.match(cur_line[s_idx:])
            if cur_m:
                m_dict = cur_m.groupdict()
                # check for -X or --Y switch
                prev_part = m_dict["pre_text"].strip().split()

                if prev_part and prev_part[-1].startswith("-"):
                    prev_part = prev_part[-1]
                else:
                    prev_part = None
                if m_dict["arg_num_2"] is not None:
                    # short form
                    arg_name = "ARG%s" % (m_dict["arg_num_2"])
                else:
                    arg_name = "ARG%s" % (m_dict["arg_num_1"])
                    var_name, default_value = (m_dict["var_name"], m_dict["default"])
                    if var_name:
                        self.__default_values[arg_name] = (var_name, default_value)
                    elif default_value is not None:
                        self.__default_values[arg_name] = default_value
                pre_text, post_text = (m_dict["pre_text"] or "",
                                       m_dict["post_text"] or "")
                cur_line = "%s%s$%s$%s" % (
                    cur_line[:s_idx],
                    pre_text,
                    arg_name,
                    post_text)
                s_idx += len(pre_text) + len(arg_name) + 2
                if prev_part:
                    arg_lut[prev_part] = arg_name
                else:
                    arg_list.append(arg_name)
                self.__num_args += 1
            else:
                break
        self.__md_com_line = cur_line
        if self.command_line == self.md_command_line:
            self.log("command_line in/out is '%s'" % (self.command_line))
        else:
            self.log("command_line in     is '%s'" % (self.command_line))
            self.log("command_line out    is '%s'" % (self.md_command_line))
        if arg_lut:
            self.log("lut : %s; %s" % (
                logging_tools.get_plural("key", len(arg_lut)),
                ", ".join(["'%s' => '%s'" % (key, value) for key, value in arg_lut.iteritems()])
            ))
        if arg_list:
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
        return nag_config(
            "command",
            self.__name,
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
        for dev_templ in mon_device_templ.objects.all().select_related("host_check_command"):
            self[dev_templ.pk] = dev_templ
            if dev_templ.is_default:
                self.__default = dev_templ
        self.log(
            "Found %s (%s)" % (logging_tools.get_plural("device_template", len(self.keys())),
                               ", ".join([cur_dt.name for cur_dt in self.itervalues()])))
        if self.__default:
            self.log(
                "Found default device_template named '%s'" % (self.__default.name))
        else:
            if self.keys():
                self.__default = self.values()[0]
                self.log(
                    "No default device_template found, using '%s'" % (self.__default.name),
                    logging_tools.LOG_LEVEL_WARN)
            else:
                self.log(
                    "No device_template founds, skipping configuration....",
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
        # dc.execute("SELECT ng.*, nc.name AS ncname FROM ng_service_templ ng LEFT JOIN ng_cgservicet ngc ON ngc.ng_service_templ=ng.ng_service_templ_idx LEFT JOIN ng_contactgroup nc ON ngc.ng_contactgroup=nc.ng_contactgroup_idx")
        for srv_templ in mon_service_templ.objects.all().prefetch_related(
            "mon_device_templ_set",
            "mon_contactgroup_set"):
            # db_rec["contact_groups"] = set()
            # generate notification options
            not_options = []
            for long_name, short_name in [("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u"), ("nflapping", "f"), ("nplanned_downtime", "s")]:
                if getattr(srv_templ, long_name):
                    not_options.append(short_name)
            if not not_options:
                not_options.append("n")
            srv_templ.notification_options = not_options
            self[srv_templ.pk] = srv_templ
            self[srv_templ.name] = srv_templ
            srv_templ.contact_groups = set(srv_templ.mon_contactgroup_set.all().values_list("name", flat=True))
        if self.keys():
            self.__default = self.keys()[0]
        self.log("Found %s (%s)" % (
            logging_tools.get_plural("device_template", len(self.keys())),
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

