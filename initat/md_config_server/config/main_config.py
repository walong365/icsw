# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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

from django.conf import settings
from django.db.models import Q
from initat.cluster.backbone.models import device, user
from initat.md_config_server.config.base_config import base_config
from initat.md_config_server.config.config_dir import config_dir
from initat.md_config_server.config.host_type_config import host_type_config
import ConfigParser
import base64
import binascii
import codecs
import config_tools
import configfile
import logging_tools
import os
import process_tools
import shutil
import sqlite3
import time

global_config = configfile.get_global_config(process_tools.get_programm_name())


__all__ = [
    "main_config",
]


class main_config(object):
    def __init__(self, proc, monitor_server, **kwargs):
        self.__process = proc
        self.__slave_name = kwargs.get("slave_name", None)
        self.__main_dir = global_config["MD_BASEDIR"]
        self.distributed = kwargs.get("distributed", False)
        if self.__slave_name:
            self.__dir_offset = os.path.join("slaves", self.__slave_name)
            master_cfg = config_tools.device_with_config("monitor_server")
            slave_cfg = config_tools.server_check(
                host_name=monitor_server.full_name,
                server_type="monitor_slave",
                fetch_network_info=True
            )
            self.slave_uuid = monitor_server.uuid
            route = master_cfg["monitor_server"][0].get_route_to_other_device(self.__process.router_obj, slave_cfg)
            if not route:
                self.slave_ip = None
                self.master_ip = None
                self.log("no route to slave %s found" % (unicode(monitor_server)), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.slave_ip = route[0][3][1][0]
                self.master_ip = route[0][2][1][0]
                self.log(
                    "IP-address of slave {} is {} (master: {})".format(
                        unicode(monitor_server),
                        self.slave_ip,
                        self.master_ip
                    )
                )
        else:
            self.__dir_offset = ""
            # self.__min_dir = os.path.join(self.__main_dir, "slaves", self.__slave_name)
        self.monitor_server = monitor_server
        self.master = True if not self.__slave_name else False
        self.__dict = {}
        self._create_directories()
        self._clear_etc_dir()
        self.allow_write_entries = global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]
        self._create_base_config_entries()
        self._write_entries()
        self.allow_write_entries = True

    @property
    def allow_write_entries(self):
        return self.__allow_write_entries

    @allow_write_entries.setter
    def allow_write_entries(self, val):
        self.__allow_write_entries = val

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
            self.log(
                "{} invalid: {}".format(
                    logging_tools.get_plural("host_type config", len(invalid)),
                    ", ".join(invalid)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            return False
        else:
            return True

    def refresh(self):
        # refreshes host- and contactgroup definition
        self["contactgroup"].refresh(self)
        self["hostgroup"].refresh(self)

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            "[mc{}] {}".format(
                " {}".format(self.__slave_name) if self.__slave_name else "",
                what
            ),
            level
        )

    def get_command_name(self):
        return os.path.join(self.__r_dir_dict["var"], "icinga.cmd")

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
                self.log("Creating directory {}".format(full_path))
                os.makedirs(full_path)
            else:
                self.log("already exists : {}".format(full_path))

    def _clear_etc_dir(self):
        if self.master:
            self.log("not clearing {} dir (master)".format(self.__w_dir_dict["etc"]))
        else:
            self.log("clearing {} dir (slave)".format(self.__w_dir_dict["etc"]))
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
            try:
                nv_target = os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php")
                with open(nv_target, "wb") as nvm_file:
                    nvm_file.write("; <?php return 1; ?>\n")
                    nagvis_main_cfg.write(nvm_file)
            except IOError:
                self.log("error creating %s: %s" % (
                    nv_target,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            # clear SALT
            config_php = os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php")
            if os.path.exists(config_php):
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
                self.log("config.php '%s' does not exist" % (config_php), logging_tools.LOG_LEVEL_ERROR)
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
                ("instance_name", "clusternagios"),
                ("output_type", "unixsocket"),
                ("output", "%s/ido.sock" % (self.__r_dir_dict["var"])),
                ("tcp_port", 5668),
                ("output_buffer_items", 5000),
                ("buffer_file", "%s/ndomod.tmp" % (self.__r_dir_dict["var"])),
                ("file_rotation_interval", 14400),
                ("file_rotation_timeout", 60),
                ("reconnect_interval", 15),
                ("reconnect_warning_interval", 15),
                ("debug_level", 0),
                ("debug_verbosity", 0),
                ("debug_file", os.path.join(self.__r_dir_dict["var"], "ndomod.debug")),
                ("data_processing_options", global_config["NDO_DATA_PROCESSING_OPTIONS"]),
                ("config_output_options", 2)])
        if not sql_suc:
            self.log("error reading sql_file '%s', no ndo2b_cfg to write" % (sql_file),
                     logging_tools.LOG_LEVEL_ERROR)
            ndo2db_cfg = None
        elif "monitor" not in settings.DATABASES:
            self.log("no 'monitor' database defined in settings.py",
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
                    ("ndo2db_user", "idnagios"),
                    ("ndo2db_group", "idg"),
                    ("socket_type", "unix"),
                    ("socket_name", "%s/ido.sock" % (self.__r_dir_dict["var"])),
                    ("tcp_port", 5668),
                    ("db_servertype", db_server),
                    ("db_host", sql_dict["MYSQL_HOST"]),
                    ("db_port", sql_dict["PORT"]),
                    ("db_name", sql_dict["NAGIOS_DATABASE"]),
                    ("db_prefix", "%s_" % (global_config["MD_TYPE"])),
                    ("db_user", sql_dict["MYSQL_USER"]),
                    ("db_pass", sql_dict["MYSQL_PASSWD"]),
                    # time limits one week
                    ("max_timedevents_age", 1440),
                    ("max_systemcommands_age", 1440),
                    ("max_servicechecks_age", 1440),
                    ("max_hostchecks_age", 1440),
                    ("max_eventhandlers_age", 1440),
                    ("debug_level", 0),
                    ("debug_verbosity", 1),
                    ("debug_file", "%s/ndo2db.debug" % (self.__r_dir_dict["var"])),
                    ("max_debug_file_size", 1000000)])
        main_values = [
            ("log_file", "{}/{}.log".format(
                self.__r_dir_dict["var"],
                global_config["MD_TYPE"]
            )),
            ("cfg_file", []),
            ("resource_file", "%s/%s.cfg" % (
                self.__r_dir_dict["etc"],
                resource_cfg.get_name())),
            ("%s_user" % (global_config["MD_TYPE"]), "idnagios"),
            ("%s_group" % (global_config["MD_TYPE"]), "idg"),
            ("check_external_commands", 1),
            ("command_check_interval", 1),
            ("command_file", self.get_command_name()),
            ("command_check_interval", "5s"),
            ("lock_file", "%s/%s" % (self.__r_dir_dict["var"], global_config["MD_LOCK_FILE"])),
            ("temp_file", "%s/temp.tmp" % (self.__r_dir_dict["var"])),
            ("log_rotation_method", "h"),
            ("log_archive_path", self.__r_dir_dict["var/archives"]),
            ("use_syslog", 0),
            ("host_inter_check_delay_method", "s"),
            ("service_inter_check_delay_method", "s"),
            ("service_interleave_factor", "s"),
            # ("enable_predictive_service_dependency_checks", 1 if global_config["USE_HOST_DEPENDENCIES"] else 0),
            ("enable_predictive_host_dependency_checks", 1 if global_config["USE_HOST_DEPENDENCIES"] else 0),
            ("translate_passive_host_checks", 1 if global_config["TRANSLATE_PASSIVE_HOST_CHECKS"] else 0),
            ("max_concurrent_checks", global_config["MAX_CONCURRENT_CHECKS"]),
            ("passive_host_checks_are_soft", 1 if global_config["PASSIVE_HOST_CHECKS_ARE_SOFT"] else 0),
            ("service_reaper_frequency", 12),
            ("sleep_time", 1),
            ("retain_state_information", 1 if global_config["RETAIN_SERVICE_STATUS"] else 0),  # if self.master else 0),
            ("state_retention_file", "%s/retention.dat" % (self.__r_dir_dict["var"])),
            ("retention_update_interval", 60),
            ("use_retained_program_state", 1 if global_config["RETAIN_PROGRAM_STATE"] else 0),
            ("use_retained_scheduling_info", 0),
            ("interval_length", 60 if not self.master else 60),
            ("use_aggressive_host_checking", 0),
            ("execute_service_checks", 1),
            ("accept_passive_host_checks", 1),
            ("accept_passive_service_checks", 1),
            ("enable_notifications", 1 if self.master else 0),
            ("enable_event_handlers", 1),
            ("process_performance_data", (1 if global_config["ENABLE_COLLECTD"] else 0) if self.master else 0),
            ("obsess_over_services", 1 if not self.master else 0),
            ("obsess_over_hosts", 1 if not self.master else 0),
            ("check_for_orphaned_services", 0),
            ("check_service_freshness", 1 if global_config["CHECK_SERVICE_FRESHNESS"] else 0),
            ("service_freshness_check_interval", global_config["SERVICE_FRESHNESS_CHECK_INTERVAL"]),
            ("check_host_freshness", 1 if global_config["CHECK_HOST_FRESHNESS"] else 0),
            ("host_freshness_check_interval", global_config["HOST_FRESHNESS_CHECK_INTERVAL"]),
            ("freshness_check_interval", 15),
            ("enable_flap_detection", 1 if global_config["ENABLE_FLAP_DETECTION"] else 0),
            ("low_service_flap_threshold", 25),
            ("high_service_flap_threshold", 50),
            ("low_host_flap_threshold", 25),
            ("high_host_flap_threshold", 50),
            ("date_format", "euro"),
            ("illegal_object_name_chars", r"~!$%^&*|'\"<>?),()"),
            ("illegal_macro_output_chars", r"~$&|'\"<>"),
            ("admin_email", "lang-nevyjel@init.at"),
            ("admin_pager", "????"),
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
            if global_config["ENABLE_COLLECTD"]:
                # setup perf
                # collectd data:
                main_values.extend(
                    [
                        (
                            "service_perfdata_file",
                            os.path.join(self.__r_dir_dict["var"], "service-perfdata")
                        ),
                        (
                            "host_perfdata_file",
                            os.path.join(self.__r_dir_dict["var"], "host-perfdata")
                        ),
                        (
                            "service_perfdata_file_template",
                            "<rec type='service' uuid='$_HOSTUUID$' time='$TIMET$' host='$HOSTNAME$' sdesc='$SERVICEDESC$' "
                            "perfdata='$SERVICEPERFDATA$' com='$SERVICECHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$' "
                            "ss='$SERVICESTATE$' sstype='$SERVICESTATETYPE$'/>"
                        ),
                        (
                            "host_perfdata_file_template",
                            "<rec type='host' uuid='$_HOSTUUID$' time='$TIMET$' host='$HOSTNAME$' perfdata='$HOSTPERFDATA$' "
                            "com='$HOSTCHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$'/>"
                        ),
                    ]
                )
                # general data:
                main_values.extend(
                    [
                        # ("host_perfdata_command"   , "process-host-perfdata"),
                        # ("service_perfdata_command", "process-service-perfdata"),
                        ("service_perfdata_file_mode", "a"),
                        ("service_perfdata_file_processing_interval", "15"),
                        ("service_perfdata_file_processing_command", "process-service-perfdata-file"),
                        ("host_perfdata_file_mode", "a"),
                        ("host_perfdata_file_processing_interval", "15"),
                        ("host_perfdata_file_processing_command", "process-host-perfdata-file"),
                    ]
                )
            if global_config["ENABLE_NDO"]:
                if os.path.exists(os.path.join(self.__r_dir_dict[lib_dir_name], "idomod.so")):
                    main_values.append(
                        ("*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                            self.__r_dir_dict[lib_dir_name],
                            self.__r_dir_dict["etc"],
                            NDOMOD_NAME)))
                else:
                    main_values.append(
                        (
                            "*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                                self.__r_dir_dict["lib"],
                                self.__r_dir_dict["etc"],
                                NDOMOD_NAME
                            )
                        )
                    )
            main_values.append(
                ("event_broker_options", -1 if global_config["ENABLE_LIVESTATUS"] else global_config["EVENT_BROKER_OPTIONS"])
            )
        else:
            # add global event handlers
            main_values.extend([
                ("cfg_dir", []),
                ("ochp_command", "ochp-command"),
                ("ocsp_command", "ocsp-command"),
                ("stalking_event_handlers_for_hosts", 1),
                ("stalking_event_handlers_for_services", 1),
            ])
        main_values.extend(
            [
                ("object_cache_file", "%s/object.cache" % (self.__r_dir_dict["var"])),
                ("use_large_installation_tweaks", "1"),
                ("enable_environment_macros", "0"),
                ("max_service_check_spread", global_config["MAX_SERVICE_CHECK_SPREAD"]),
                ("max_host_check_spread", global_config["MAX_HOST_CHECK_SPREAD"]),
            ])
        main_cfg = base_config(global_config["MAIN_CONFIG_NAME"],
                               is_host_file=True,
                               values=main_values)
        for log_descr, en in [
            ("notifications", 1),
            ("service_retries", 1),
            ("host_retries", 1),
            ("event_handlers", 1),
            ("initial_states", 1),  # this must be true for log parsing
            ("external_commands", 1 if global_config["LOG_EXTERNAL_COMMANDS"] else 0),
            ("passive_checks", 1 if global_config["LOG_PASSIVE_CHECKS"] else 0)
        ]:
            main_cfg["log_%s" % (log_descr)] = en
        for to_descr, to in [
            ("service_check", 60),
            ("host_check", 30),
            ("event_handler", 30),
            ("notification", 30),
            ("ocsp", 5),
            ("perfdata", 5)
        ]:
            main_cfg["%s_timeout" % (to_descr)] = to
        for th_descr, th in [
            ("low_service", 5.0),
            ("high_service", 20.0),
            ("low_host", 5.0),
            ("high_host", 20.0)
        ]:
            main_cfg["%s_flap_threshold" % (th_descr)] = th
        _uo = user.objects  # @UndefinedVariable
        admin_list = list(
            [
                cur_u.login for cur_u in _uo.filter(
                    Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)
                ) if cur_u.has_perm("backbone.device.all_devices")
            ]
        )
        if admin_list:
            def_user = ",".join(admin_list)
        else:
            def_user = "%sadmin" % (global_config["MD_TYPE"])
        cgi_config = base_config(
            "cgi",
            is_host_file=True,
            values=[
                (
                    "main_config_file", "%s/%s.cfg" % (
                        self.__r_dir_dict["etc"], global_config["MAIN_CONFIG_NAME"]
                    )
                ),
                ("physical_html_path", "%s" % (self.__r_dir_dict["share"])),
                ("url_html_path", "/%s" % (global_config["MD_TYPE"])),
                ("show_context_help", 0),
                ("use_authentication", 1),
                # ("default_user_name"        , def_user),
                ("default_statusmap_layout", 5),
                ("default_statuswrl_layout", 4),
                ("refresh_rate", 60),
                ("lock_author_name", 1),
                ("authorized_for_system_information", def_user),
                ("authorized_for_system_commands", def_user),
                ("authorized_for_configuration_information", def_user),
                ("authorized_for_all_hosts", def_user),
                ("authorized_for_all_host_commands", def_user),
                ("authorized_for_all_services", def_user),
                ("authorized_for_all_service_commands", def_user)] +
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
                    ("chdir", self.__r_dir_dict[""]),
                    ("plugin-dir", "/opt/cluster/%s" % (lib_dir_name)),
                    ("cgi-mode", "true"),
                    ("master", "true"),
                    # set vacuum to false because of problems with uwsgi 1.9
                    ("vacuum", "false"),
                    ("workers", 4),
                    ("harakiri-verbose", 1),
                    ("plugins", "cgi"),
                    ("socket", os.path.join(self.__r_dir_dict["var"], "uwsgi.sock")),
                    ("uid", www_user),
                    ("gid", www_group),
                    ("cgi", self.__r_dir_dict["sbin"]),
                    ("no-default-app", "true"),
                    ("cgi-timeout", 3600),
                    ("pidfile", os.path.join(self.__r_dir_dict["var"], "wsgi.pid")),
                    ("daemonize", os.path.join(self.__r_dir_dict["var"], "wsgi.log")),
                    ("chown-socket", www_user),
                    ("no-site", "true"),
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
            file(htp_file, "w").write(
                "\n".join(
                    ["{}:{{SSHA}}{}".format(
                        cur_u.login,
                        cur_u.password_ssha.split(":", 1)[1]
                    ) for cur_u in user.objects.filter(Q(active=True)) if cur_u.password_ssha.count(":")] + [""]  # @UndefinedVariable
                )
            )
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
                    self.log(
                        "found {}: {}".format(
                            logging_tools.get_plural("table", len(all_tables)),
                            ", ".join(sorted(all_tables))
                        )
                    )
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
                    self.log(
                        "{}: {}".format(
                            logging_tools.get_plural("NagVIS root device", len(nagvis_rds)),
                            ", ".join([unicode(cur_dev) for cur_dev in nagvis_rds])
                        )
                    )
                    devg_lut = {}
                    for cur_dev in nagvis_rds:
                        devg_lut.setdefault(cur_dev.device_group.pk, []).append(cur_dev.full_name)
                    for cur_u in user.objects.filter(Q(active=True) & Q(mon_contact__pk__gt=0)).prefetch_related("allowed_device_groups"):  # @UndefinedVariable
                        # check for admin
                        if cur_u.has_perm("backbone.device.all_devices"):
                            target_role = "admins"
                        else:
                            # create special role
                            target_role = cur_u.login
                            role_dict[target_role] = cur_c.execute("INSERT INTO roles VALUES(Null, '%s')" % (cur_u.login)).lastrowid
                            add_perms = ["auth.logout.*", "overview.view.*", "general.*.*", "user.setoption.*"]
                            perm_names = []
                            for cur_devg in cur_u.allowed_device_groups.values_list("pk", flat=True):
                                for dev_name in devg_lut.get(cur_devg, []):
                                    perm_names.extend(
                                        [
                                            "map.view.{}".format(dev_name),
                                            "automap.view.{}".format(dev_name),
                                        ]
                                    )
                            for perm_name in perm_names:
                                if perm_name not in perms_dict:
                                    try:
                                        perms_dict[perm_name] = cur_c.execute(
                                            "INSERT INTO perms VALUES(Null, '%s', '%s', '%s')" % (
                                                perm_name.split(".")[0].title(),
                                                perm_name.split(".")[1],
                                                perm_name.split(".")[2]
                                            )
                                        ).lastrowid
                                        self.log("permission '%s' has id %d" % (perm_name, perms_dict[perm_name]))
                                    except:
                                        self.log(
                                            "cannot create permission '{}': {}".format(
                                                perm_name,
                                                process_tools.get_except_info()
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
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
        if not self.__allow_write_entries:
            self.log("writing entries not allowed", logging_tools.LOG_LEVEL_WARN)
            return 0
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
            if global_config["DEBUG"]:
                self.log(
                    "wrote {} ({}) in {}".format(
                        logging_tools.get_plural("config_file", len(cfg_written)),
                        ", ".join(cfg_written),
                        logging_tools.get_diff_time_str(end_time - start_time)
                    )
                )
            else:
                self.log(
                    "wrote {} in {}".format(
                        logging_tools.get_plural("config_file", len(cfg_written)),
                        logging_tools.get_diff_time_str(end_time - start_time)
                    )
                )
        else:
            self.log("no config files written")
        return len(cfg_written) + len(empty_cfg_written)

    def has_config(self, config_name):
        return config_name in self

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

    def __contains__(self, key):
        return key in self.__dict

    def __getitem__(self, key):
        return self.__dict[key]
