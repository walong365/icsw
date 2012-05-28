#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012 Andreas Lang-Nevyjel, init.at
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
""" server to configure the nagios or icinga monitoring daemon, now for 0MQ clients """

import pkg_resources
pkg_resources.require("MySQL_python")
import zmq
import MySQLdb
import sys
import os
import re
import configfile
import os.path
import time
import signal
import commands
import pprint
import logging_tools
import process_tools
import mysql_tools
import server_command
import threading_tools
import config_tools
from md_config_server import special_commands
try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

# nagios constants
NAG_HOST_UNKNOWN     = -1
NAG_HOST_UP          = 0
NAG_HOST_DOWN        = 1
NAG_HOST_UNREACHABLE = 2

# default port
SERVER_COM_PORT = 8010
TEMPLATE_NAME = "t"
SQL_ACCESS = "cluster_full_access"

class main_config(object):
    def __init__(self, b_proc):
        self.__build_process = b_proc
        self.__main_dir = global_config["MD_BASEDIR"]
        self.__dict = {}
        self._create_directories()
        self._clear_etc_dir()
        self._create_base_config_entries()
        self._write_entries()
    def is_valid(self):
        ht_conf_names = [key for key, value in self.__dict.iteritems() if isinstance(value, host_type_config)]
        invalid = sorted([key for key in ht_conf_names if not self[key].is_valid()])
        if invalid:
            self.log("%s invalid: %s" % (logging_tools.get_plural("host_type config", len(invalid)),
                                         ", ".join(invalid)),
                     logging_tools.LOG_LEVEL_ERROR)
            return False
        else:
            return True
    def refresh(self, dc):
        # refreshes host- and contactgroup definition
        self["contactgroup"].refresh(dc, self)
        self["hostgroup"].refresh(dc, self)
    def has_key(self, key):
        return self.__dict.has_key(key)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_process.log("[mc] %s" % (what), level)
    def _create_directories(self):
        self.__dir_dict = dict([(dir_name, os.path.normpath("%s/%s" % (self.__main_dir, dir_name))) for dir_name in
                                ["", "etc", "var", "share", "archives", "ssl", "bin"]])
        for dir_name, full_path in self.__dir_dict.iteritems():
            if not os.path.exists(full_path):
                self.log("Creating directory %s" % (full_path))
                os.makedirs(full_path)
            else:
                self.log("already exists : %s" % (full_path))
    def _clear_etc_dir(self):
        for dir_e in os.listdir(self.__dir_dict["etc"]):
            full_path = "%s/%s" % (self.__dir_dict["etc"], dir_e)
            if os.path.isfile(full_path):
                try:
                    os.unlink(full_path)
                except:
                    self.log("Cannot delete file %s: %s" % (full_path, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
    def _create_base_config_entries(self):
        # read sql info
        sql_file = "/etc/sysconfig/cluster/mysql.cf"
        sql_suc, sql_dict = configfile.readconfig(sql_file, 1)
        resource_cfg = base_config("resource", is_host_file=True)
        resource_cfg["$USER1$"] = "/opt/%s/libexec" % (global_config["MD_TYPE"])
        resource_cfg["$USER2$"] = "/opt/cluster/sbin/ccollclientzmq -t %d" % (global_config["CCOLLCLIENT_TIMEOUT"])
        resource_cfg["$USER3$"] = "/opt/cluster/sbin/csnmpclientzmq -t %d" % (global_config["CSNMPCLIENT_TIMEOUT"])
        NDOMOD_NAME, NDO2DB_NAME = ("ndomod",
                                    "ndo2db")
        ndomod_cfg = base_config(NDOMOD_NAME,
                                 belongs_to_ndo=True,
                                 values=[("instance_name"              , "clusternagios"),
                                         ("output_type"                , "unixsocket"),
                                         ("output"                     , "%s/ndo.sock" % (self.__dir_dict["var"])),
                                         ("tcp_port"                   , 5668),
                                         ("output_buffer_items"        , 5000),
                                         ("buffer_file"                , "%s/ndomod.tmp" % (self.__dir_dict["var"])),
                                         ("file_rotation_interval"     , 14400),
                                         ("file_rotation_timeout"      , 60),
                                         ("reconnect_interval"         , 15),
                                         ("reconnect_warning_interval" , 15),
                                         ("data_processing_options"    , global_config["NDO_DATA_PROCESSING_OPTIONS"]),
                                         ("config_output_options"      , 2)])
        if not sql_suc:
            self.log("error reading sql_file '%s', no ndo2b_cfg to write" % (sql_file),
                     logging_tools.LOG_LEVEL_ERROR)
            ndo2db_cfg = None
        else:
            ndo2db_cfg = base_config(NDO2DB_NAME,
                                     belongs_to_ndo=True,
                                     values=[("ndo2db_user"            , "idnagios"),
                                             ("ndo2db_group"           , "idg"),
                                             ("socket_type"            , "unix"),
                                             ("socket_name"            , "%s/ndo.sock" % (self.__dir_dict["var"])),
                                             ("tcp_port"               , 5668),
                                             ("db_servertype"          , "mysql"),
                                             ("db_host"                , sql_dict["MYSQL_HOST"]),
                                             ("db_port"                , sql_dict["MYSQL_PORT"]),
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
                                             ("debug_file"             , "/opt/%s/var/ndo2db.debug" % (global_config["MD_TYPE"])),
                                             ("max_debug_file_size"    , 1000000)])
        manual_dir = "%s/manual" % (self.__dir_dict["etc"])
        if not os.path.isdir(manual_dir):
            os.mkdir(manual_dir)
        settings_dir = "%s/df_settings" % (self.__dir_dict["etc"])
        if not os.path.isdir(settings_dir):
            os.mkdir(settings_dir)
        main_values = [("log_file"                         , "%s/%s.log" % (self.__dir_dict["var"],
                                                                            global_config["MD_TYPE"])),
                       ("cfg_file"                         , []),
                       ("cfg_dir"                          , manual_dir),
                       ("resource_file"                    , "%s/%s.cfg" % (self.__dir_dict["etc"], resource_cfg.get_name())),
                       ("%s_user" % (global_config["MD_TYPE"]) , "idnagios"),
                       ("%s_group" % (global_config["MD_TYPE"]) , "idg"),
                       ("check_external_commands"          , 1),
                       ("command_check_interval"           , 1),
                       ("command_file"                     , "%s/ext_com" % (self.__dir_dict["var"])),
                       ("lock_file"                        , "%s/%s" % (self.__dir_dict["var"], global_config["MD_LOCK_FILE"])),
                       ("temp_file"                        , "%s/temp.tmp" % (self.__dir_dict["var"])),
                       ("log_rotation_method"              , "d"),
                       ("log_archive_path"                 , self.__dir_dict["archives"]),
                       ("use_syslog"                       , 0),
                       ("host_inter_check_delay_method"    , "s"),
                       ("service_inter_check_delay_method" , "s"),
                       ("service_interleave_factor"        , "s"),
                       ("max_concurrent_checks"            , global_config["MAX_CONCURRENT_CHECKS"]),
                       ("service_reaper_frequency"         , 12),
                       ("sleep_time"                       , 1),
                       ("retain_state_information"         , global_config["RETAIN_SERVICE_STATUS"]),
                       ("state_retention_file"             , "%s/retention.dat" % (self.__dir_dict["var"])),
                       ("retention_update_interval"        , 60),
                       ("use_retained_program_state"       , 0),
                       ("interval_length"                  , 60),
                       ("use_agressive_host_checking"      , 0),
                       ("execute_service_checks"           , 1),
                       ("accept_passive_service_checks"    , 1),
                       ("enable_notifications"             , 1),
                       ("enable_event_handlers"            , 0),
                       ("process_performance_data"         , 0),
                       ("obsess_over_services"             , 0),
                       ("check_for_orphaned_services"      , 0),
                       ("check_service_freshness"          , 1),
                       ("freshness_check_interval"         , 15),
                       ("enable_flap_detection"            , 0),
                       ("date_format"                      , "euro"),
                       ("illegal_object_name_chars"        , r"~!$%^&*|'\"<>?),()"),
                       ("illegal_macro_output_chars"       , r"~$&|'\"<>"),
                       ("admin_email"                      , "lang-nevyjel@init.at"),
                       ("admin_pager"                      , "????"),
                       # NDO stuff
                       ("event_broker_options"             , global_config["EVENT_BROKER_OPTIONS"])]
        if global_config["MD_TYPE"] == "nagios":
            main_values.append(("broker_module" , "%s/ndomod-%dx.o config_file=%s/%s.cfg" % (self.__dir_dict["bin"],
                                                                                             global_config["MD_VERSION"],
                                                                                             self.__dir_dict["etc"],
                                                                                             NDOMOD_NAME)))
        else:
            main_values.append(("broker_module" , "%s/idomod.o config_file=%s/%s.cfg" % (self.__dir_dict["bin"],
                                                                                         self.__dir_dict["etc"],
                                                                                         NDOMOD_NAME)))
        if global_config["MD_VERSION"] >= 3:
            main_values.extend([("object_cache_file"            , "%s/object.cache" % (self.__dir_dict["var"])),
                                ("use_large_installation_tweaks", "1"),
                                ("enable_environment_macros"    , "0"),
                                ("max_service_check_spread"     , global_config["MAX_SERVICE_CHECK_SPREAD"])])
        else:
            # values for Nagios 1.x, 2.x
            main_values.extend([("comment_file"                     , "%s/comment.log" % (self.__dir_dict["var"])),
                                ("downtime_file"                    , "%s/downtime.log" % (self.__dir_dict["var"]))])
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
        def_user = "nagiosadmin"
        cgi_config = base_config("cgi",
                                 is_host_file=True,
                                 values=[("main_config_file"         , "%s/%s.cfg" % (self.__dir_dict["etc"], global_config["MAIN_CONFIG_NAME"])),
                                         ("physical_html_path"       , "%s" % (self.__dir_dict["share"])),
                                         ("url_html_path"            , "/%s" % (global_config["MD_TYPE"])),
                                         ("show_context_help"        , 0),
                                         ("use_authentication"       , 1),
                                         ("default_user_name"        , def_user),
                                         ("default_statusmap_layout" , 5),
                                         ("default_statuswrl_layout" , 4),
                                         ("refresh_rate"             , 60),
                                         ("authorized_for_system_information"        , def_user),
                                         ("authorized_for_system_commands"           , def_user),
                                         ("authorized_for_configuration_information" , def_user),
                                         ("authorized_for_all_hosts"                 , def_user),
                                         ("authorized_for_all_host_commands"         , def_user),
                                         ("authorized_for_all_services"              , def_user),
                                         ("authorized_for_all_service_commands"      , def_user)] + [("tac_show_only_hard_state", 1)] if (global_config["MD_TYPE"] == "icinga" and global_config["MD_RELEASE"] >= 6) else [])
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
    def _write_entries(self):
        cfg_written, empty_cfg_written = ([], [])
        start_time = time.time()
        for key, stuff in self.__dict.iteritems():
            if isinstance(stuff, base_config) or isinstance(stuff, host_type_config):
                act_cfg_name = os.path.normpath("%s/%s.cfg" % (self.__dir_dict["etc"], key))
                stuff.create_content()
                if stuff.act_content != stuff.old_content:
                    try:
                        open(act_cfg_name, "w").write("\n".join(stuff.act_content + [""]))
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
        new_keys = sorted(["%s/%s.cfg" % (self.__dir_dict["etc"], key) for key, value in self.__dict.iteritems() if not isinstance(value, base_config) or not (value.is_host_file or value.belongs_to_ndo)])
        old_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"]
        if old_keys != new_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"] = new_keys
            self._write_entries()
    def __getitem__(self, key):
        return self.__dict[key]

class base_config(object):
    def __init__(self, name, **args):
        self.__name = name
        self.__dict, self.__key_list = ({}, [])
        self.is_host_file   = args.get("is_host_file", False)
        self.belongs_to_ndo = args.get("belongs_to_ndo", False)
        for key, value in args.get("values", []):
            self[key] = value
        self.act_content = []
    def get_name(self):
        return self.__name
    def __setitem__(self, key, value):
        if key not in self.__key_list:
            self.__key_list.append(key)
        self.__dict[key] = value
    def __getitem__(self, key):
        return self.__dict[key]
    def create_content(self):
        self.old_content = self.act_content
        c_lines = []
        last_key = None
#         if self.__name == "cgi":
#             print key_list
        for key in self.__key_list:
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self.__dict[key]
            if type(value) == type([]):
                pass
            elif type(value) in [type(0), type(0L)]:
                value = [str(value)]
            else:
                value = [value]
            for act_v in value:
                c_lines.append("%s=%s" % (key, act_v))
        self.act_content = c_lines
        
class nag_config(object):
    def __init__(self, name, **args):
        self.__name = name
        self.entries = {}
        self.keys = []
        for key, value in args.iteritems():
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
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_time_periods_from_db(dc)
    def get_name(self):
        return "timeperiod"
    def _add_time_periods_from_db(self, dc):
        dc.execute("SELECT * FROM ng_period")
        for db_rec in dc.fetchall():
            nag_conf = nag_config(db_rec["name"],
                                  timeperiod_name=db_rec["name"],
                                  alias=db_rec["alias"])
            for short_s, long_s in [("mon", "monday"), ("tue", "tuesday" ), ("wed", "wednesday"), ("thu", "thursday"),
                                    ("fri", "friday"), ("sat", "saturday"), ("sun", "sunday"   )]:
                nag_conf[long_s] = db_rec["%srange" % (short_s)]
            self.__dict[db_rec["ng_period_idx"]] = nag_conf
            self.__obj_list.append(nag_conf)
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_servicegroups(host_type_config):
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        # dict : which host has which service_group defined
        self.__host_srv_lut = {}
        self._add_servicegroups_from_db(dc)
    def get_name(self):
        return "servicegroup"
    def _add_servicegroups_from_db(self, dc):
        dc.execute("SELECT * FROM ng_check_command_type")
        for db_rec in dc.fetchall():
            nag_conf = nag_config(db_rec["name"],
                                  servicegroup_name=db_rec["name"],
                                  alias="%s group" % (db_rec["name"]))
            self.__host_srv_lut[db_rec["name"]] = set()
            self.__dict[db_rec["ng_check_command_type_idx"]] = nag_conf
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
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_notify_commands(dc)
        self._add_commands_from_db(dc)
    def get_name(self):
        return "command"
    def _add_notify_commands(self, dc):
        dc.execute("SELECT d.device_idx FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx AND dg.cluster_device_group")
        if dc.rowcount:
            cd_idx = dc.fetchone()["device_idx"]
            self.log("ClusterDeviceGroup idx is %d" % (cd_idx))
            dv = configfile.device_variable(dc, cd_idx, "CLUSTER_NAME")
            if not dv.is_set():
                dv.set_stuff(description="Name of the Cluster")
                dv.set_value("new_cluster")
                dv.update(dc)
            cluster_name = dv.get_value()
        else:
            cluster_name = "N/A"
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
                              command_line=r"%s -f '%s' -s '$NOTIFICATIONTYPE$ alert - $HOSTNAME$@%s ($HOSTALIAS$)/$SERVICEDESC$ is $SERVICESTATE$' -t $CONTACTEMAIL$ '***** %s %s *****\n\n" % (send_mail_prog,
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
                              command_line=r"%s -f '%s'  -s 'Host $HOSTSTATE$ alert for $HOSTNAME$@%s' -t $CONTACTEMAIL$ '***** %s %s *****\n\n" % (send_mail_prog,
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
    def _add_commands_from_db(self, dc):
        ngc_re1 = re.compile("^\@(?P<special>\S+)\@(?P<comname>\S+)$")
        dc.execute("SELECT ng.*, cs.name AS st_name, ngt.name AS servicegroup_name FROM ng_check_command_type ngt, ng_check_command ng LEFT JOIN ng_service_templ cs ON ng.ng_service_templ=cs.ng_service_templ_idx WHERE " + \
                       "ngt.ng_check_command_type_idx=ng.ng_check_command_type")
        for ngc in [db_rec for db_rec in dc.fetchall()] + \
                [{"name"                 : "check-host-alive",
                  "command_line"         : "$USER2$ -m localhost ping $HOSTADDRESS$ %d %.2f" % (global_config["CHECK_HOST_ALIVE_PINGS"],
                                                                                                global_config["CHECK_HOST_ALIVE_TIMEOUT"]),
                  "description"          : "Check-host-alive command via ping",
                  "device"               : 0,
                  "st_name"              : None,
                  "new_config"           : None},
                 {"name"                 : "check-host-alive-2",
                  "command_line"         : "$USER2$ -m $HOSTADDRESS$ version",
                  "description"          : "Check-host-alive command via collserver",
                  "device"               : 0,
                  "st_name"              : None,
                  "new_config"           : None}]:
            #pprint.pprint(ngc)
            # build / extract ngc_name
            re1m = ngc_re1.match(ngc["name"])
            if re1m:
                ngc_name, special = (re1m.group("comname"), re1m.group("special"))
            else:
                ngc_name, special = (ngc["name"], None)
            if ngc.has_key("ng_check_command_idx"):
                ngc_name = "%s_%d" % (ngc_name, ngc["ng_check_command_idx"])
            cc_s = check_command(ngc_name, ngc["command_line"], ngc["new_config"], ngc["st_name"], ngc["description"], ngc["device"], special, servicegroup_name=ngc.get("servicegroup_name", "other"))
            nag_conf = cc_s.get_nag_config()
            self.__obj_list.append(nag_conf)
            self.__dict[nag_conf["command_name"]] = cc_s
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
    
class all_contacts(host_type_config):
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_contacts_from_db(dc, gen_conf)
    def get_name(self):
        return "contact"
    def _add_contacts_from_db(self, dc, gen_conf):
        dc.execute("SELECT * FROM ng_contact ng, user u WHERE ng.user = u.user_idx")
        for contact in dc.fetchall():
            full_name = ("%s %s" % (contact["uservname"], contact["usernname"])).strip().replace(" ", "_")
            if not full_name:
                full_name = contact["login"]
            hn_command = contact["hncommand"]
            sn_command = contact["sncommand"]
            if len(contact["userpager"]) > 5:
                # check for pager number
                hn_command = "%s,host-notify-by-sms" % (hn_command)
                sn_command = "%s,notify-by-sms" % (sn_command)
            nag_conf = nag_config(full_name,
                                  contact_name=full_name,
                                  host_notification_period=gen_conf["timeperiod"][contact["hnperiod"]]["name"],
                                  service_notification_period=gen_conf["timeperiod"][contact["snperiod"]]["name"],
                                  host_notification_commands=hn_command,
                                  service_notification_commands=sn_command,
                                  alias=contact["usercom"] or full_name)
            for targ_opt, pairs in [("host_notification_options"   , [("hnrecovery", "r"), ("hndown"    , "d"), ("hnunreachable", "u")]),
                                    ("service_notification_options", [("snrecovery", "r"), ("sncritical", "c"), ("snwarning"    , "w"), ("snunknown", "u")])]:
                act_a = []
                for long_s, short_s in pairs:
                    if contact[long_s]:
                        act_a.append(short_s)
                if not act_a:
                    act_a = ["n"]
                nag_conf[targ_opt] = ",".join(act_a)
            u_mail = contact["useremail"] or "root@localhost"
            nag_conf["email"] = u_mail
            nag_conf["pager"] = contact["userpager"] or "----"
            self.__obj_list.append(nag_conf)
            self.__dict[contact["ng_contact_idx"]] = nag_conf
    def __getitem__(self, key):
        return self.__dict[key]
    def get_object_list(self):
        return self.__obj_list
    def values(self):
        return self.__dict.values()
        
class all_contact_groups(host_type_config):
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(dc, gen_conf)
    def refresh(self, dc, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_contact_groups_from_db(dc, gen_conf)
    def get_name(self):
        return "contactgroup"
    def _add_contact_groups_from_db(self, dc, gen_conf):
        # none group
        self.__dict[0] = nag_config(global_config["NONE_CONTACT_GROUP"],
                                    contactgroup_name=global_config["NONE_CONTACT_GROUP"],
                                    alias="None group")
        dc.execute("SELECT * FROM ng_contactgroup ng LEFT JOIN ng_ccgroup ngc ON ngc.ng_contactgroup = ng.ng_contactgroup_idx ORDER BY ng.ng_contactgroup_idx")
        nag_conf = None
        for cg_group in dc.fetchall():
            print "*", cg_group
            if not self.__dict.has_key(cg_group["ng_contactgroup_idx"]):
                ## new nag_conf, check last one
                #if nag_conf:
                #    if nag_conf["members"] != "-":
                #        self.__obj_list.append(nag_conf)
                nag_conf = nag_config(cg_group["name"],
                                      contactgroup_name=cg_group["name"],
                                      alias=cg_group["alias"])
                self.__dict[cg_group["ng_contactgroup_idx"]] = nag_conf
            if cg_group["ng_contact"]:
                nag_conf["members"] = gen_conf["contact"][cg_group["ng_contact"]]["name"]
        self.__obj_list = self.__dict.values()
        #if nag_conf:
        #    if nag_conf["members"] != "-":
        #        self.__obj_list.append(nag_conf)
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
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(dc, gen_conf)
    def refresh(self, dc, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_host_groups_from_db(dc, gen_conf)
    def get_name(self):
        return "hostgroup"
    def _add_host_groups_from_db(self, dc, gen_conf):
        if gen_conf.has_key("host"):
            all_hosts_written = gen_conf["host"].keys()
            sql_add_str = " OR ".join(["d.name='%s'" % (x) for x in all_hosts_written])
            # hostgroups
            if sql_add_str:
                sql_str = "SELECT dg.*, d.name FROM device_group dg, device d WHERE d.device_group = dg.device_group_idx AND (%s) ORDER BY dg.device_group_idx" % (sql_add_str)
                dc.execute(sql_str)
                for h_group in dc.fetchall():
                    if not self.__dict.has_key(h_group["device_group_idx"]):
                        nag_conf = nag_config(h_group["name"],
                                              hostgroup_name=h_group["name"],
                                              alias=h_group["description"] or h_group["name"],
                                              members="-")
                        self.__dict[h_group["device_group_idx"]] = nag_conf
                        self.__obj_list.append(nag_conf)
                    if h_group["d.name"]:
                        nag_conf["members"] = h_group["d.name"]
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
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(dc, gen_conf)
    def refresh(self, dc, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_hosts_from_db(dc, gen_conf)
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
    def _add_hosts_from_db(self, dc, gen_conf):
        pass
    
class all_hosts_extinfo(host_type_config):
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(dc, gen_conf)
    def refresh(self, dc, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_hosts_from_db(dc, gen_conf)
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
    def _add_hosts_from_db(self, dc, gen_conf):
        pass
    
class all_services(host_type_config):
    def __init__(self, dc, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(dc, gen_conf)
    def refresh(self, dc, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_services_from_db(dc, gen_conf)
    def get_name(self):
        return "service"
    def get_object_list(self):
        return self.__obj_list
    def append(self, value):
        self.__obj_list.append(value)
    def values(self):
        return self.__obj_list
    def remove_host(self, host_obj):
        self.__obj_list.remove(host_obj)
    def _add_services_from_db(self, dc, gen_conf):
        pass
    
class check_command(object):
    def __init__(self, name, com_line, config, template, descr, device=0, special=None, **args):
        self.__name = name
        self.__com_line = com_line
        self.config = config
        self.template = template
        self.device = device
        self.servicegroup_name = args.get("servicegroup_name", "other")
        self.__descr = descr.replace(",", ".")
        self.__special = special
        self._generate_md_com_line()
    def get_num_args(self):
        return self.__num_args
    def get_default_value(self, arg_name, def_value):
        return self.__default_values.get(arg_name, def_value)
    def _generate_md_com_line(self):
        self.__num_args, self.__default_values = (0, {})
        # parse command_line
        com_parts, new_parts = (self.__com_line.split(), [])
        for com_part in com_parts:
            try:
                if com_part.startswith("${") and com_part.endswith("}"):
                    arg_name, var_name, default_value = com_part[2:-1].split(":")
                    new_parts.append("$%s$" % (arg_name))
                    self.__default_values[arg_name] = (var_name, default_value)
                    self.__num_args += 1
                elif com_part.startswith("$ARG") and com_part.endswith("$"):
                    new_parts.append(com_part)
                    self.__num_args += 1
                else:
                    new_parts.append(com_part)
            except:
                # need some logging, FIXME
                new_parts.append(com_part)
        self.__md_com_line = " ".join(new_parts)
    def correct_argument_list(self, in_list, dev_variables):
        if not in_list and self.__num_args:
            in_list = [""] * self.__num_args
        out_list = []
        for idx, item in zip(range(1, len(in_list) + 1), in_list):
            arg_name = "ARG%d" % (idx)
            if self.__default_values.has_key(arg_name) and not item:
                var_name = self.__default_values[arg_name][0]
                if dev_variables.has_key(var_name):
                    item = dev_variables[var_name]
                else:
                    item = self.__default_values[arg_name][1]
            out_list.append(item)
        #if out_list:
        #    print "*", self.__name, "-"*20
        #    print "i", in_list, dev_variables
        #    print "o", out_list
        return out_list
    def get_nag_config(self):
        return nag_config(self.__name,
                          command_name=self.__name,
                          command_line=self.__md_com_line)
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
    def __repr__(self):
        return "%s (%s)" % (self.__name, self.__com_line)
        
class device_templates(object):
    def __init__(self, dc, build_proc):
        self.__build_proc = build_proc
        self.__default = 0
        self.__dict = {}
        dc.execute("SELECT * FROM ng_device_templ")
        for db_rec in dc.fetchall():
            self.__dict[db_rec["ng_device_templ_idx"]] = db_rec
            if db_rec["is_default"]:
                self.__default = db_rec["ng_device_templ_idx"]
        self.log("Found %s (%s)" % (logging_tools.get_plural("device_template", len(self.__dict.keys())),
                                    ", ".join([x["name"] for x in self.__dict.values()])))
        if self.__default:
            self.log("Found default device_template named '%s'" % (self[self.__default]["name"]))
        else:
            if self.__dict:
                self.__default = self.__dict.keys()[0]
                self.log("No default device_template found, using '%s'" % (self[self.__default]["name"]),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("No device_template founds, skipping configuration....",
                         logging_tools.LOG_LEVEL_ERROR)
    def is_valid(self):
        return self.__default and True or False
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[device_templates] %s" % (what), level)
    def __getitem__(self, key):
        act_key = key or self.__default
        if not self.__dict.has_key(act_key):
            self.log("key %d not known, using default %d" % (act_key, self.__default),
                     logging_tools.LOG_LEVEL_ERROR)
            act_key = self.__default
        return self.__dict[act_key]

class service_templates(object):
    def __init__(self, dc, build_proc):
        self.__build_proc = build_proc
        self.__default = 0
        self.__dict = {}
        dc.execute("SELECT ng.*, nc.name AS ncname FROM ng_service_templ ng LEFT JOIN ng_cgservicet ngc ON ngc.ng_service_templ=ng.ng_service_templ_idx LEFT JOIN ng_contactgroup nc ON ngc.ng_contactgroup=nc.ng_contactgroup_idx")
        for db_rec in dc.fetchall():
            if not self.__dict.has_key(db_rec["ng_service_templ_idx"]):
                db_rec["contact_groups"] = set()
                # generate notification options
                not_options = []
                for long_name, short_name in [("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u")]:
                    if db_rec[long_name]:
                        not_options.append(short_name)
                if not not_options:
                    not_options.append("n")
                db_rec["notification_options"] = not_options
                self.__dict[db_rec["ng_service_templ_idx"]] = db_rec
                self.__dict[db_rec["name"]] = db_rec
            if db_rec["ncname"]:
                self[db_rec["ng_service_templ_idx"]]["contact_groups"].add(db_rec["ncname"])
        if self.__dict:
            self.__default = self.__dict.keys()[0]
        self.log("Found %s (%s)" % (logging_tools.get_plural("device_template", len(self.__dict.keys())),
                                    ", ".join([x["name"] for x in self.__dict.values()])))
    def is_valid(self):
        return True
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[service_templates] %s" % (what), level)
    def __getitem__(self, key):
        act_key = key or self.__default
        if not self.__dict.has_key(act_key):
            self.log("key %d not known, using default %d" % (act_key, self.__default),
                     logging_tools.LOG_LEVEL_ERROR)
            act_key = self.__default
        return self.__dict[act_key]
    def has_key(self, key):
        return self.__dict.has_key(key)

##        
##class logging_thread(threading_tools.thread_obj):
##    def __init__(self, glob_config, loc_config):
##        self.__sep_str = "-" * 50
##        self.__glob_config, self.__loc_config = (glob_config, loc_config)
##        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
##        threading_tools.thread_obj.__init__(self, "logging", queue_size=500, priority=10)
##        self.register_func("log", self._log)
##        self.register_func("update", self._update)
##        self.register_func("mach_log", self._mach_log)
##        self.register_func("set_queue_dict", self._set_queue_dict)
##        self.register_func("delay_request", self._delay_request)
##    def thread_running(self):
##        self.send_pool_message(("new_pid", (self.name, self.pid)))
##        root = self.__glob_config["LOG_DIR"]
##        if not os.path.exists(root):
##            os.makedirs(root)
##        glog_name = "%s/log" % (root)
##        self.__glob_log = logging_tools.logfile(glog_name)
##        self.__glob_log.write(self.__sep_str)
##        self.__glob_log.write("Opening log")
##        # array of delay-requests
##        self.__delay_array = []
##    def _update(self):
##        # handle delay-requests
##        act_time = time.time()
##        new_d_array = []
##        for target_queue, arg, r_time in self.__delay_array:
##            if r_time < act_time:
##                self.log("sending delayed object")
##                target_queue.put(arg)
##            else:
##                new_d_array.append((target_queue, arg, r_time))
##        self.__delay_array = new_d_array
##    def _delay_request(self, (target_queue, arg, delay)):
##        self.log("append to delay_array (delay=%s)" % (logging_tools.get_plural("second", delay)))
##        self.__delay_array.append((target_queue, arg, time.time() + delay))
##    def _set_queue_dict(self, q_dict):
##        self.__queue_dict = q_dict
##    def loop_end(self):
##        for mach in self.__machlogs.keys():
##            self.__machlogs[mach].write("Closing log")
##            self.__machlogs[mach].close()
##        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
##        self.__glob_log.write("Closing log")
##        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
##        self.send_pool_message(("remove_pid", (self.name, self.pid)))
##        self.__glob_log.close()
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        self._mach_log((self.name, what, lev, ""))
##    def _log(self, (s_thread, what, lev)):
##        self._mach_log((s_thread, what, lev, ""))
##    def _mach_log(self, (s_thread, what, lev, mach)):
##        if mach == "":
##            handle, pre_str = (self.__glob_log, "")
##        else:
##            handle, pre_str = self._get_handle(mach)
##        if handle is None:
##            self.__glob_cache.append((s_thread, what, lev, mach))
##        else:
##            log_act = []
##            if self.__glob_cache:
##                for c_s_thread, c_what, c_lev, c_mach in self.__glob_cache:
##                    c_handle, c_pre_str = self._get_handle(c_mach)
##                    self._handle_log(c_handle, c_s_thread, c_pre_str, c_what, c_lev, c_mach)
##                self.__glob_cache = []
##            self._handle_log(handle, s_thread, pre_str, what, lev, mach)
##    def _handle_log(self, handle, s_thread, pre_str, what, lev, mach):
##        if type(lev) not in [type(0), type(0L)]:
##            handle.write("type of level is not int: %s, %s, %s, %s" % (lev,
##                                                                       s_thread,
##                                                                       pre_str,
##                                                                       what))
##        else:
##            handle.write("%-5s(%s) : %s%s" % (logging_tools.get_log_level_str(lev),
##                                              s_thread,
##                                              pre_str,
##                                              what))
##    def _remove_handle(self, name):
##        self.log("Closing log for device %s" % (name))
##        self._mach_log((self.name, "(%s) : Closing log" % (self.name), logging_tools.LOG_LEVEL_OK, name))
##        self.__machlogs[name].close()
##        del self.__machlogs[name]
##    def _get_handle(self, name):
##        devname_dict = {}
##        if self.__machlogs.has_key(name):
##            handle, pre_str = (self.__machlogs[name], "")
##        else:
##            machdir = "%s/%s" % (self.__glob_config["LOG_DIR"], name)
##            if not os.path.exists(machdir):
##                self.log("Creating dir %s for %s" % (machdir, name))
##                os.makedirs(machdir)
##            self.__machlogs[name] = logging_tools.logfile("%s/log" % (machdir))
##            self.__machlogs[name].write(self.__sep_str)
##            self.__machlogs[name].write("Opening log")
##            #glog.write("# of open machine logs: %d" % (len(self.__machlogs.keys())))
##            handle, pre_str = (self.__machlogs[name], "")
##        return (handle, pre_str)

class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
        self.__nagios_lock_file_name = "%s/var/%s" % (global_config["MD_BASEDIR"], global_config["MD_LOCK_FILE"])
        self.__mach_loggers = {}
        self.__db_con = mysql_tools.dbcon_container()
        self.__gen_config = main_config(self)
        self.register_func("rebuild_config", self._rebuild_config)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
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
        c_stat, out = commands.getstatusoutput("%s/bin/%s -v %s/etc/%s.cfg" % (global_config["MD_BASEDIR"],
                                                                               global_config["MD_TYPE"],
                                                                               global_config["MD_BASEDIR"],
                                                                               global_config["MD_TYPE"]))
        if c_stat:
            self.log("Checking the %s-configuration resulted in an error (%d)" % (global_config["MD_TYPE"],
                                                                                  c_stat),
                     logging_tools.LOG_LEVEL_ERROR)
            #print out
            ret_stat = 0
        else:
            self.log("Checking the %s-configuration returned no error" % (global_config["MD_TYPE"]))
            ret_stat = 1
        return ret_stat, out
    def _reload_nagios(self):
        start_nagios, restart_nagios = (False, False)
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
                    self.log("Cannot read %s LockFile named '%s', trying to start %s" % (global_config["MD_TYPE"],
                                                                                         self.__nagios_lock_file_name,
                                                                                         global_config["MD_TYPE"]),
                             logging_tools.LOG_LEVEL_WARN)
                    start_nagios = True
                else:
                    pid = file(self.__nagios_lock_file_name).read().strip()
                    try:
                        pid = int(pid)
                    except:
                        self.log("PID read from '%s' is not an integer (%s, %s), trying to restart %s" % (self.__nagios_lock_file_name,
                                                                                                          str(pid),
                                                                                                          process_tools.get_except_info(),
                                                                                                          global_config["MD_TYPE"]),
                                 logging_tools.LOG_LEVEL_ERROR)
                        restart_nagios = True
                    else:
                        try:
                            os.kill(pid, signal.SIGHUP)
                        except OSError:
                            self.log("Error signaling pid %d with SIGHUP (%d), trying to restart %s (%s)" % (pid,
                                                                                                             signal.SIGHUP,
                                                                                                             global_config["MD_TYPE"],
                                                                                                             process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                            restart_nagios = True
                        else:
                            self.log("Successfully signaled pid %d with SIGHUP (%d)" % (pid, signal.SIGHUP))
            else:
                self.log("Nagios LockFile '%s' not found, trying to start %s" % (self.__nagios_lock_file_name,
                                                                                 global_config["MD_TYPE"]),
                         logging_tools.LOG_LEVEL_WARN)
                start_nagios = True
        if start_nagios:
            self.log("Trying to start %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s start" % (global_config["MD_TYPE"]))
        elif restart_nagios:
            self.log("Trying to restart %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s restart" % (global_config["MD_TYPE"]))
        else:
            log_lines = []
        if log_lines:
            for log_line in log_lines:
                self.log(log_line)
    def _rebuild_config(self, *args, **kwargs):
        print args, kwargs
        h_list = args[0] if len(args) else []
        rebuild_it = True
        dc = self.__db_con.get_connection(SQL_ACCESS)
        dc.execute("SELECT d.device_idx FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx AND dg.cluster_device_group")
        if dc.rowcount:
            cdg_idx = dc.fetchone()["device_idx"]
            dc.execute("SELECT * FROM device_variable WHERE name='hopcount_rebuild_in_progress' AND device=%d" % (cdg_idx))
            if dc.rowcount:
                self.log("hopcount_rebuild in progress, delaying request", logging_tools.LOG_LEVEL_WARN)
                # delay request
                self.__log_queue.put(("delay_request", (self.get_thread_queue(), ("rebuild_config", h_list), global_config["MAIN_LOOP_TIMEOUT"] / 2)))
                # no rebuild
                rebuild_it = False
        else:
            self.log("no cluster_device_group, unable to check validity of hopcount_table", logging_tools.LOG_LEVEL_ERROR)
        if rebuild_it:
            rebuild_gen_config = False
            if global_config["ALL_HOSTS_NAME"] in h_list:
                self.log("rebuilding complete config")
                rebuild_gen_config = True
            else:
                self.log("rebuilding config for %s: %s" % (logging_tools.get_plural("host", len(h_list)),
                                                           logging_tools.compress_list(h_list)))
            if not self.__gen_config:
                rebuild_gen_config = True
            if rebuild_gen_config:
                self._create_general_config(dc)
                h_list = []
            bc_valid = self.__gen_config.is_valid()
            if bc_valid:
                # get device templates
                dev_templates = device_templates(dc, self)
                # get serivce templates
                serv_templates = service_templates(dc, self)
                if dev_templates.is_valid() and serv_templates.is_valid():
                    pass
                else:
                    bc_valid = False
            if bc_valid:
                self._create_host_config_files(dc, h_list, dev_templates, serv_templates)
                # refresh implies _write_entries
                self.__gen_config.refresh(dc)
            cfgs_written = self.__gen_config._write_entries()
            if bc_valid and (cfgs_written or rebuild_gen_config):
                self._reload_nagios()
            # FIXME
            #self.__queue_dict["command_queue"].put(("config_rebuilt", h_list or [global_config["ALL_HOSTS_NAME"]]))
        dc.release()
    def _create_general_config(self, dc):
        start_time = time.time()
        self._check_image_maps(dc)
        self._create_gen_config_files(dc)
        end_time = time.time()
        self.log("creating the total general config took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _create_gen_config_files(self, dc):
        start_time = time.time()
        # misc commands (sending of mails)
        self.__gen_config.add_config(all_commands(dc, self.__gen_config, self))
        # servicegroups
        self.__gen_config.add_config(all_servicegroups(dc, self.__gen_config, self))
        # timeperiods
        self.__gen_config.add_config(time_periods(dc, self.__gen_config, self))
        # contacts
        self.__gen_config.add_config(all_contacts(dc, self.__gen_config, self))
        # contactgroups
        self.__gen_config.add_config(all_contact_groups(dc, self.__gen_config, self))
        # hostgroups
        self.__gen_config.add_config(all_host_groups(dc, self.__gen_config, self))
        # hosts
        self.__gen_config.add_config(all_hosts(dc, self.__gen_config, self))
        # hosts_extinfo
        self.__gen_config.add_config(all_hosts_extinfo(dc, self.__gen_config, self))
        # services
        self.__gen_config.add_config(all_services(dc, self.__gen_config, self))
        end_time = time.time()
        self.log("created host_configs in %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _get_ng_ext_hosts(self, dc):
        dc.execute("SELECT * FROM ng_ext_host")
        all_image_stuff = dict([(x["ng_ext_host_idx"], x) for x in dc.fetchall()])
        return all_image_stuff
    def _check_image_maps(self, dc):
        min_width, max_width, min_height, max_height = (16, 64, 16, 64)
        all_image_stuff = self._get_ng_ext_hosts(dc)
        self.log("Found %s" % (logging_tools.get_plural("ext_host entry", len(all_image_stuff.keys()))))
        logos_dir = "%s/share/images/logos" % (global_config["MD_BASEDIR"])
        base_names = []
        if os.path.isdir(logos_dir):
            logo_files = os.listdir(logos_dir)
            for log_line in [x.split(".")[0] for x in logo_files]:
                if log_line not in base_names:
                    if "%s.png" % (log_line) in logo_files and "%s.gd2" % (log_line) in logo_files:
                        base_names.append(log_line)
        if base_names:
            stat, out = commands.getstatusoutput("file %s" % (" ".join(["%s/%s.png" % (logos_dir, x) for x in base_names])))
            if stat:
                self.log("error getting filetype of %s" % (logging_tools.get_plural("logo", len(base_names))), logging_tools.LOG_LEVEL_ERROR)
            else:
                base_names = []
                for logo_name, logo_data in [(os.path.basename(y[0].strip()), [z.strip() for z in y[1].split(",") if z.strip()]) for y in [x.strip().split(":", 1) for x in out.split("\n")] if len(y) == 2]:
                    if len(logo_data) == 4:
                        width, height = [int(x.strip()) for x in logo_data[1].split("x")]
                        if min_width <= width and width <= max_width and min_height <= height and height <= max_height:
                            base_names.append(logo_name[:-4])
        all_images_present = [x["name"] for x in all_image_stuff.values()]
        all_images_present_lower = [x.lower() for x in all_images_present]
        base_names_lower = [x.lower() for x in base_names]
        new_images = [x for x in base_names if x.lower() not in all_images_present_lower]
        del_images = [x for x in all_images_present if x.lower() not in base_names_lower]
        for new_image in new_images:
            dc.execute("INSERT INTO ng_ext_host VALUES(0, '%s', '%s.png', '', '', '%s.gd2',null)" % (new_image, new_image, new_image))
        for del_image in del_images:
            dc.execute("DELETE FROM ng_ext_host WHERE name='%s'" % (del_image))
        self.log("Inserted %s, deleted %s" % (logging_tools.get_plural("new ext_host_entry", len(new_images)),
                                              logging_tools.get_plural("ext_host_entry", len(del_images))))
    def _get_int_str(self, i_val, size=3):
        if i_val:
            return ("%%%dd" % (size)) % (i_val)
        else:
            return ("%%%ds" % (size)) % ("-")
    def _get_my_net_idxs(self, dc, server_idxs):
        dc.execute("SELECT nd.netdevice_idx FROM netdevice nd WHERE (%s)" % (" OR ".join(["nd.device=%d" % (x) for x in server_idxs])))
        my_net_idxs = [x.values()[0] for x in dc.fetchall()]
        return my_net_idxs
    def _create_host_config_files(self, dc, hosts, dev_templates, serv_templates):
        start_time = time.time()
        server_idxs = [global_config["SERVER_IDX"]]
        # get additional idx if host is virtual server
        sql_info = config_tools.server_check(dc=dc, server_type="nagios_master")
        if sql_info.server_device_idx and sql_info.server_device_idx != global_config["SERVER_IDX"]:
            server_idxs.append(sql_info.server_device_idx)
        # get netip-idxs of own host
        my_net_idxs = self._get_my_net_idxs(dc, server_idxs)
        main_dir = global_config["MD_BASEDIR"]
        etc_dir = os.path.normpath("%s/etc" % (main_dir))
        # get ext_hosts stuff
        ng_ext_hosts = self._get_ng_ext_hosts(dc)
        # all hosts
        dc.execute("SELECT d.device_idx, d.name, dt.identifier, d.bootserver FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type")
        all_hosts_dict = dict([(x["device_idx"], x) for x in dc.fetchall()])
        # check_hosts
        if hosts:
            sel_str, host_info_str = ("(%s)" % (" OR ".join(["d.name='%s'" % (x) for x in hosts])), "%d" % (len(hosts)))
        else:
            sel_str, host_info_str = (" 1 ", "all")
        dc.execute("SELECT d.*, dt.identifier FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND %s" % (sel_str))
        #host_cfg_dict=
        check_hosts = dict([(x["device_idx"], x) for x in dc.fetchall()])
        # get config variables
        sql_str = "SELECT d.name, dc.new_config FROM new_config c INNER JOIN device d INNER JOIN device_group dg INNER JOIN device_config dc LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND %s ORDER BY d.name" % (sel_str)
        dc.execute(sql_str)
        all_configs = {}
        for db_rec in dc.fetchall():
            all_configs.setdefault(db_rec["name"], []).append(db_rec["new_config"])
        first_contactgroup_name = self.__gen_config["contactgroup"][self.__gen_config["contactgroup"].keys()[0]]["name"]
        contact_group_dict = {}
        # get contact groups
        sql_str = "SELECT ndc.ng_contactgroup, d.name FROM device d, ng_contactgroup nc, device_group dg LEFT JOIN ng_device_contact ndc ON ndc.device_group=dg.device_group_idx WHERE d.device_group = dg.device_group_idx AND ndc.ng_contactgroup=nc.ng_contactgroup_idx AND (%s) ORDER BY dg.device_group_idx" % (sel_str)
        dc.execute(sql_str)
        for db_rec in dc.fetchall():
            if self.__gen_config["contactgroup"].has_key(db_rec["ng_contactgroup"]):
                cg_name = self.__gen_config["contactgroup"][db_rec["ng_contactgroup"]]["name"]
            else:
                self.log("contagroup_idx %s for device %s not found, using first from contactgroups (%s)" % (str(db_rec["ng_contactgroup"]),
                                                                                                             db_rec["name"],
                                                                                                             first_contactgroup_name),
                         logging_tools.LOG_LEVEL_ERROR)
                cg_name = first_contactgroup_name
            contact_group_dict.setdefault(db_rec["name"], []).append(cg_name)
        # get valid and invalid network types
        dc.execute("SELECT nt.identifier FROM network_type nt WHERE (%s)" % (" OR ".join(["nt.identifier='%s'" % (x) for x in ["p", "o"]])))
        valid_nwt_list = [x.values()[0] for x in dc.fetchall()]
        dc.execute("SELECT nt.identifier FROM network_type nt WHERE (%s)" % (" AND ".join(["nt.identifier!='%s'" % (x) for x in ["p", "o"]])))
        invalid_nwt_list = [x.values()[0] for x in dc.fetchall()]
        # get all network devices (needed for relaying)
        dc.execute("SELECT i.ip, d.name, n.netdevice_idx, nt.identifier FROM device d, netdevice n, netip i, network nw, network_type nt WHERE n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND nw.network_type=nt.network_type_idx AND i.network = nw.network_idx")
        all_net_devices = {"i" : {},
                           "v" : {}}
        for db_rec in dc.fetchall():
            n_t, n_n, n_d, n_i = (db_rec["identifier"], db_rec["name"], db_rec["netdevice_idx"], db_rec["ip"])
            if n_t in valid_nwt_list:
                n_t = "v"
            else:
                n_t = "i"
            if not all_net_devices[n_t].has_key(n_n):
                all_net_devices[n_t][n_n] = {}
            if not all_net_devices[n_t][n_n].has_key(n_d):
                all_net_devices[n_t][n_n][n_d] = []
            all_net_devices[n_t][n_n][n_d].append(n_i)
        #pprint.pprint(all_net_devices)
        # get all masterswitch connections
        dc.execute("SELECT d.device_idx, ms.device FROM device d, msoutlet ms WHERE ms.slave_device = d.device_idx")
        all_ms_connections = {}
        for db_rec in dc.fetchall():
            all_ms_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        # get all device relationships
        all_dev_relationships = {}
        dc.execute("SELECT * FROM device_relationship")
        for db_rec in dc.fetchall():
            all_dev_relationships[db_rec["domain_device"]] = db_rec
        # get all ibm bladecenter connections
        dc.execute("SELECT d.device_idx, ib.device FROM device d, ibc_connection ib WHERE ib.slave_device = d.device_idx")
        all_ib_connections = {}
        for db_rec in dc.fetchall():
            all_ib_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        #print all_net_devices
        host_nc, service_nc  = (self.__gen_config["host"], self.__gen_config["service"])
        hostext_nc = self.__gen_config["hostextinfo"]
        # delete host if already present in host_table
        for host_idx, host in check_hosts.iteritems():
            del_list = [x for x in host_nc.values() if x["name"] == host["name"]]
            for del_h in del_list:
                del_list_2 = [x for x in service_nc.values() if x["host_name"] == del_h["name"]]
                for del_h_2 in del_list_2:
                    service_nc.remove_host(del_h_2)
                # delete hostextinfo for nagios V1.x
                if hostext_nc.has_key(del_h["name"]):
                    del hostext_nc[del_h["name"]]
                del host_nc[del_h["name"]]
        # build lookup-table
        host_lut = dict([[check_hosts[k]["name"], k] for k in check_hosts.keys()])
        host_names = sorted(host_lut.keys())
        for host_name in host_names:
            start_time = time.time()
            host_idx = host_lut[host_name]
            host = check_hosts[host_idx]
            self.__cached_mach_name = host["name"]
            glob_log_str = "Starting build of config for device %20s" % (host["name"])
            self.mach_log("Starting build of config", logging_tools.LOG_LEVEL_OK, host["name"])
            num_ok, num_warning, num_error = (0, 0, 0)
            #print "%s : %s" % (host["name"], host["identifier"])
            if all_net_devices["v"].has_key(host["name"]):
                net_devices = all_net_devices["v"][host["name"]]
            elif all_net_devices["i"].has_key(host["name"]):
                self.mach_log("Device %s has no valid netdevices associated, using invalid ones..." % (host["name"]),
                                      logging_tools.LOG_LEVEL_WARN)
                net_devices = all_net_devices["i"][host["name"]]
            else:
                self.mach_log("Device %s has no netdevices associated, skipping..." % (host["name"]),
                                      logging_tools.LOG_LEVEL_ERROR)
                num_error += 1
                net_devices = []
            if net_devices:
                #print mni_str_s, mni_str_d, dev_str_s, dev_str_d
                # get correct netdevice for host
                if host["name"] == global_config["SERVER_SHORT_NAME"]:
                    valid_ips, traces, relay_ip = (["127.0.0.1"], [host_idx], "")
                else:
                    valid_ips, traces, relay_ip = self._get_target_ip_info(dc, my_net_idxs, all_net_devices, net_devices, host_idx, all_hosts_dict, check_hosts)
                    if not valid_ips:
                        num_error += 1
                act_def_dev = dev_templates[host["ng_device_templ"]]
                if valid_ips and act_def_dev:
                    valid_ip = valid_ips[0]
                    self.mach_log("Found %s for host %s : %s, using %s" % (logging_tools.get_plural("target ip", len(valid_ips)),
                                                                           host["name"],
                                                                           ", ".join(valid_ips),
                                                                           valid_ip))
                    if relay_ip:
                        self.mach_log(" - contact via relay-ip %s" % (relay_ip))
                    if not serv_templates.has_key(act_def_dev["ng_service_templ"]):
                        self.log("Default service_template not found in service_templates", logging_tools.LOG_LEVEL_WARN)
                    else:
                        act_def_serv = serv_templates[act_def_dev["ng_service_templ"]]
                        # tricky part: check the actual service_template for the various services
                        self.mach_log("Using default device_template '%s' and service_template '%s' for host %s" % (act_def_dev["name"], act_def_serv["name"], host["name"]))
                        # get device variables
                        dev_variables = {}
                        sql_str = "SELECT v.name, v.var_type, v.val_str, v.val_int, v.val_blob, v.val_date, v.val_time FROM device_variable v WHERE v.device=%d" % (host_idx)
                        dc.execute(sql_str)
                        for db_rec in dc.fetchall():
                            var_name = db_rec["name"]
                            if db_rec["var_type"] == "s":
                                dev_variables[var_name] = db_rec["val_str"]
                            elif db_rec["var_type"] == "i":
                                dev_variables[var_name] = str(db_rec["val_int"])
                            elif db_rec["var_type"] == "b":
                                dev_variables[var_name] = str(db_rec["val_blob"])
                        # get snmp related variables
                        sql_str = "SELECT sc.* FROM snmp_class sc WHERE sc.snmp_class_idx=%d" % (host["snmp_class"])
                        dc.execute(sql_str)
                        if dc.rowcount:
                            db_rec = dc.fetchone()
                            dev_variables["SNMP_VERSION"] = "%d" % (db_rec["snmp_version"])
                            dev_variables["SNMP_COMMUNITY"] = db_rec["read_community"]
                        self.mach_log("device has %s" % (logging_tools.get_plural("device_variable", len(dev_variables.keys()))))
                        # now we have the device- and service template
                        act_host = nag_config(host["name"])
                        act_host["host_name"] = host["name"]
                        # set alias
                        if host["alias"]:
                            act_host["alias"] = host["alias"]
                        else:
                            act_host["alias"] = host["name"]
                        act_host["address"] = relay_ip and "%s:%s" % (relay_ip, valid_ip) or valid_ip
                        # check for parents
                        parents = []
                        # rule 1: APC Masterswitches have their bootserver set as parent
                        if host["identifier"] in ["AM", "IBC"] and host["bootserver"]:
                            parents.append(all_hosts_dict[host["bootserver"]]["name"])
                        # rule 2: Devices connected to an apc have this apc set as parent
                        elif all_ms_connections.has_key(host_idx):
                            for pd in all_ms_connections[host_idx]:
                                if all_hosts_dict[pd]["name"] not in parents:
                                    # disable circular references
                                    if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                        self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                    else:
                                        parents.append(all_hosts_dict[pd]["name"])
                        # rule 3: Devices connected to an ibc have this ibc set as parent
                        elif all_ib_connections.has_key(host_idx):
                            for pd in all_ib_connections[host_idx]:
                                if all_hosts_dict[pd]["name"] not in parents:
                                    # disable circular references
                                    if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                        self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                    else:
                                        parents.append(all_hosts_dict[pd]["name"])
                        # rule 4: Devices have their xen/vmware-parent set as parent
                        elif all_dev_relationships.has_key(host_idx) and all_hosts_dict.has_key(all_dev_relationships[host_idx]["host_device"]):
                            act_rel = all_dev_relationships[host_idx]
                            # disable circular references
                            if host["identifier"] == "H" and host["name"] == global_config["SERVER_SHORT_NAME"]:
                                self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[act_rel["host_device"]]["name"]))
                            else:
                                parents.append(all_hosts_dict[act_rel["host_device"]]["name"])
                        # rule 5: Check routing
                        else:
                            self.mach_log("No direct parent(s) found, registering trace")
                            if host["bootserver"] != host_idx and host["bootserver"]:
                                traces.append(host_idx)
                            if len(traces) > 1:
                                act_host["possible_parents"] = traces
                                #print traces, host["name"], all_hosts_dict[traces[1]]["name"]
                                #parents += [all_hosts_dict[traces[1]]["name"]]
                            #print "No parent set for %s" % (host["name"])
                        if parents:
                            self.mach_log("settings %s: %s" % (logging_tools.get_plural("parent", len(parents)),
                                                                       ", ".join(sorted(parents))))
                            act_host["parents"] = ",".join(parents)
                        act_host["retain_status_information"] = global_config["RETAIN_HOST_STATUS"]
                        act_host["max_check_attempts"]        = act_def_dev["max_attempts"]
                        act_host["notification_interval"]     = act_def_dev["ninterval"]
                        act_host["notification_period"]       = self.__gen_config["timeperiod"][act_def_dev["ng_period"]]["name"]
                        act_host["checks_enabled"]            = 1
                        host_groups = set(contact_group_dict.get(host["name"], []))
                        if host_groups:
                            act_host["contact_groups"] = ",".join(host_groups)
                        else:
                            act_host["contact_groups"] = global_config["NONE_CONTACT_GROUP"]
                        self.mach_log("contact groups for host: %s" % (", ".join(sorted(host_groups)) or "none"))
                        if host["nagios_checks"]:
                            act_host["check_command"]             = act_def_dev["ccommand"]
                            # check for notification options
                            not_a = []
                            for what, shortcut in [("nrecovery", "r"), ("ndown", "d"), ("nunreachable", "u")]:
                                if act_def_dev[what]:
                                    not_a.append(shortcut)
                            if not not_a:
                                not_a.append("n")
                            act_host["notification_options"] = ",".join(not_a)
                            # check for hostextinfo
                            if host["ng_ext_host"] and ng_ext_hosts.has_key(host["ng_ext_host"]):
                                if (global_config["MD_TYPE"] == "nagios" and global_config["MD_VERSION"] > 1) or (global_config["MD_TYPE"] == "icinga"):
                                    # handle for nagios 2
                                    act_hostext_info = nag_config(host["name"])
                                    act_hostext_info["host_name"] = host["name"]
                                    for key in ["icon_image", "statusmap_image"]:
                                        act_hostext_info[key] = ng_ext_hosts[host["ng_ext_host"]][key]
                                    hostext_nc[host["name"]] = act_hostext_info
                                else:
                                    self.log("don't know how to handle hostextinfo for %s_version %d" % (global_config["MD_TYPE"],
                                                                                                         global_config["MD_VERSION"]),
                                             logging_tools.LOG_LEVEL_ERROR)
                            # clear host from servicegroups
                            self.__gen_config["servicegroup"].clear_host(host_name)
                            # get check_commands and templates
                            conf_names = all_configs.get(host["name"], [])
                            conf_dict = dict([(x["command_name"], x) for x in self.__gen_config["command"].values() if x.get_config() in conf_names and (x.get_device() == 0 or x.get_device() == host["device_idx"])])
                            # old code, use only_ping config
                            #if host["identifier"] == "NB" or host["identifier"] == "AM" or host["identifier"] == "S":
                            #    # set config-dict for netbotzes, APC Masterswitches and switches to ping
                            #    conf_dict = dict([(x["command_name"], x) for x in self.__gen_config["checkcommand"]["struct"].values() if x["command_name"].startswith("check_ping")])
                            #print host["name"], conf_dict
                            # now conf_dict is a list of all service-checks defined for this host
                            #pprint.pprint(conf_dict)
                            # list of already used checks
                            used_checks = []
                            conf_names = sorted(conf_dict.keys())
                            for conf_name in conf_names:
                                s_check = conf_dict[conf_name]
                                if s_check.get_description() in used_checks:
                                    self.mach_log("Check %s (%s) already used, ignoring .... (CHECK CONFIG !)" % (s_check.get_description(), s_check["command_name"]), logging_tools.LOG_LEVEL_WARN)
                                    num_warning += 1
                                else:
                                    used_checks.append(s_check.get_description())
                                    special = s_check.get_special()
                                    if special:
                                        sc_array = []
                                        try:
                                            cur_special = getattr(special_commands, "special_%s" % (special.lower()))(self, dc, s_check, host, valid_ip, global_config)
                                        except:
                                            self.log("unable to initialize special '%s': %s" % (special,
                                                                                                process_tools.get_except_info()),
                                                     logging_tools.LOG_LEVEL_CRITICAL)
                                        else:
                                            # calling handle to return a list of checks with format
                                            # [(description, [ARG1, ARG2, ARG3, ...]), (...)]
                                            try:
                                                sc_array = cur_special()#.handle(s_check, host, dc, self, valid_ip, global_config=global_config)
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
                                        sc_array = [(s_check.get_description(), [])]
                                        # contact_group is only written if contact_group is responsible for the host and the service_template
                                    serv_temp = serv_templates[s_check.get_template(act_def_serv["name"])]
                                    serv_cgs = set(serv_temp["contact_groups"]).intersection(host_groups)
                                    self.mach_log("  adding check %-30s (%2d p), template %s, %s" % (s_check["command_name"], len(sc_array),
                                                                                                     s_check.get_template(act_def_serv["name"]),
                                                                                                     "cg: %s" % (", ".join(sorted(serv_cgs))) if serv_cgs else "no cgs"))
                                    for sc_name, sc in sc_array:
                                        act_serv = nag_config(sc_name)
                                        act_serv["service_description"]   = sc_name.replace("(", "[").replace(")", "]")
                                        act_serv["host_name"]             = host["name"]
                                        act_serv["is_volatile"]           = serv_temp["volatile"]
                                        act_serv["check_period"]          = self.__gen_config["timeperiod"][serv_temp["nsc_period"]]["name"]
                                        act_serv["max_check_attempts"]    = serv_temp["max_attempts"]
                                        act_serv["normal_check_interval"] = serv_temp["check_interval"]
                                        act_serv["retry_check_interval"]  = serv_temp["retry_interval"]
                                        act_serv["notification_interval"] = serv_temp["ninterval"]
                                        act_serv["notification_options"]  = ",".join(serv_temp["notification_options"])
                                        act_serv["notification_period"]   = self.__gen_config["timeperiod"][serv_temp["nsn_period"]]["name"]
                                        if serv_cgs:
                                            act_serv["contact_groups"] = ",".join(serv_cgs)
                                        else:
                                            act_serv["contact_groups"] = global_config["NONE_CONTACT_GROUP"]
                                        act_serv["servicegroups"]         = s_check.servicegroup_name
                                        self.__gen_config["servicegroup"].add_host(host_name, act_serv["servicegroups"])
                                        act_serv["check_command"]         = "!".join([s_check["command_name"]] + s_check.correct_argument_list(sc, dev_variables))
                                        if act_host["check_command"] == "check-host-alive-2" and s_check["command_name"].startswith("check_ping"):
                                            self.mach_log("   removing command %s because of %s" % (s_check["command_name"],
                                                                                                    act_host["check_command"]))
                                        else:
                                            num_ok += 1
                                            service_nc.append(act_serv)
                            host_nc[act_host["name"]] = act_host
                        else:
                            self.mach_log("Host %s is disabled" % (host["name"]))
                else:
                    self.mach_log("No valid IPs found or no default_device_template found", logging_tools.LOG_LEVEL_ERROR)
            info_str = "finished with %s warnings and %s errors (%3d ok) in %s" % (self._get_int_str(num_warning),
                                                                                   self._get_int_str(num_error),
                                                                                   num_ok,
                                                                                   logging_tools.get_diff_time_str(time.time() - start_time))
            glob_log_str += ", %s" % (info_str)
            self.log(glob_log_str)
            self.mach_log(info_str)
        host_names = host_nc.keys()
        for host in host_nc.values():
            if host.has_key("possible_parents"):
                p_parents = host["possible_parents"]
                for parent_idx in p_parents:
                    parent = all_hosts_dict[parent_idx]["name"]
                    if parent in host_names and parent != host["name"]:
                        host["parents"] = ",".join([parent])
                        self.mach_log("Setting parent to %s" % (parent), logging_tools.LOG_LEVEL_OK, host["name"])
                        break
                del host["possible_parents"]
        end_time = time.time()
        self.log("created configs for %s hosts in %s" % (host_info_str,
                                                         logging_tools.get_diff_time_str(end_time - start_time)))
    def _get_target_ip_info(self, dc, my_net_idxs, all_net_devices, net_devices, host_idx, all_hosts_dict, check_hosts):
        mni_str_s = " OR ".join(["h.s_netdevice=%d" % (x) for x in my_net_idxs])
        traces, relay_ip = ([], "")
        host = all_hosts_dict[host_idx]
        dev_str_d = " OR ".join(["h.d_netdevice=%d" % (x) for x in net_devices.keys()])
        dc.execute("SELECT h.s_netdevice, h.d_netdevice, h.trace, h.value FROM hopcount h WHERE (%s) AND (%s) ORDER BY h.value" % (mni_str_s, dev_str_d))
        #targ_netdev_ds = dc.fetchone()
        targ_netdev_idxs = None
        for targ_netdev_ds in dc.fetchall():
            targ_netdev_idxs = [targ_netdev_ds[k] for k in ["s_netdevice", "d_netdevice"] if targ_netdev_ds[k] not in my_net_idxs]
            if not targ_netdev_idxs:
                # special case: peers defined but only local netdevices found, maybe alias ?
                targ_netdev_idxs = [targ_netdev_ds["s_netdevice"]]
            if len([True for x in targ_netdev_idxs if net_devices.has_key(x)]):
                if targ_netdev_ds["trace"]:
                    traces = [int(x) for x in targ_netdev_ds["trace"].split(":")]
                    if traces[0] != host_idx:
                        traces.reverse()
                break
            else:
                targ_netdev_idxs = None
        if not targ_netdev_idxs:
            self.mach_log("Cannot reach host %s (check peer_information)" % (host["name"]), logging_tools.LOG_LEVEL_ERROR)
            valid_ips = []
        else:
            valid_ips = (",".join([",".join([y for y in net_devices[x]]) for x in targ_netdev_idxs])).split(",")
            r_dev_idx = check_hosts[host_idx]["relay_device"]
            if r_dev_idx:
                relay_host = all_hosts_dict[r_dev_idx]
                if all_net_devices["v"].has_key(relay_host["name"]):
                    relay_net_devices = all_net_devices["v"][relay_host["name"]]
                    dev_str_d = " OR ".join(["h.d_netdevice=%d" % (x) for x in relay_net_devices.keys()])
                    dc.execute("SELECT h.s_netdevice, h.d_netdevice, h.trace FROM hopcount h WHERE (%s) AND (%s) ORDER BY h.value" % (mni_str_s, dev_str_d))
                    relay_netdev_ds = dc.fetchone()
                    if relay_netdev_ds:
                        relay_netdev_idxs = [relay_netdev_ds[k] for k in ["s_netdevice", "d_netdevice"] if relay_netdev_ds[k] not in my_net_idxs]
                        if not relay_netdev_idxs:
                            # special case: peers defined but only local netdevices found, mabye alias ?
                            relay_netdev_idxs = [relay_netdev_ds["s_netdevice"]]
                        if relay_netdev_ds["trace"]:
                            relay_traces = [int(x) for x in relay_netdev_ds["trace"].split(":")]
                            if relay_traces[0] != r_dev_idx:
                                relay_traces.reverse()
                        else:
                            relay_traces = []
                    else:
                        relay_netdev_idxs = None
                else:
                    relay_netdev_idxs = None
                if not relay_netdev_idxs:
                    self.log("Cannot reach relay_host %s (check peer_information)" % (relay_host["name"]), logging_tools.LOG_LEVEL_ERROR)
                    valid_ips = []
                else:
                    relay_ip = (",".join([",".join([y for y in relay_net_devices[x]]) for x in relay_netdev_idxs])).split(",")[0]
        return valid_ips, traces, relay_ip

class command_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("com_con", self._com_con)
        self.register_func("rebuild_config", self._rebuild_config)
        self.register_func("config_rebuilt", self._config_rebuilt)
        self.register_func("set_net_stuff", self._set_net_stuff)
        self.__net_server = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        # pending ... config requests sent to build_thread
        # waiting ... config requests waiting to be sent to the built_thread
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_net_stuff(self, (net_server)):
        self.log("Got net_server")
        self.__net_server = net_server
    def _com_con(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            tcp_obj.add_to_out_buffer("error no valid server_command")
            self.log("Got invalid data from host %s (port %d): %s" % (tcp_obj.get_src_host(),
                                                                      tcp_obj.get_src_port(),
                                                                      in_data[0:20]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            srv_com_name = server_com.get_command()
            call_func = {"status"                : self._status,
                         "reload_config"         : self._reload_config,
                         "rebuild_host_config"   : self._rebuild_host_config,
                         "host_config_done"      : self._host_config_done}.get(srv_com_name, None)
            if call_func:
                call_func(tcp_obj, server_com)
            else:
                self.log("Got unknown server_command '%s' from host %s (port %d)" % (srv_com_name,
                                                                                     tcp_obj.get_src_host(),
                                                                                     tcp_obj.get_src_port()),
                         logging_tools.LOG_LEVEL_WARN)
                res_str = "unknown command %s" % (srv_com_name)
                tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result=res_str),
                                          res_str)
    def _status(self, tcp_obj, s_com):
        tp = self.get_thread_pool()
        num_threads, num_ok = (tp.num_threads(False),
                               tp.num_threads_running(False))
        if num_ok == num_threads:
            ret_str = "ok all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
        else:
            ret_str = "error only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
        server_reply = server_command.server_reply()
        server_reply.set_ok_result(ret_str)
        tcp_obj.add_to_out_buffer(server_reply, "status")
    def _reload_config(self, tcp_obj, s_com):
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                   result="ok reloading config"),
                                  "reload_config")
    def _rebuild_host_config(self, tcp_obj, s_com):
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                   result="ok rebuilding config"),
                                  "rebuild_host_config")
        self._rebuild_config(s_com.get_nodes())
    def _host_config_done(self, tcp_obj, s_com):
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                   result="ok rebuilding config"),
                                  "rebuild_config")
        self._rebuild_config(s_com.get_nodes())
    def _rebuild_config(self, hosts):
        if hosts:
            self.log("Got rebuild config for %s: %s" % (logging_tools.get_plural("host", len(hosts)),
                                                        logging_tools.compress_list(hosts)))
        else:
            self.log("Got rebuild config for all hosts")
            hosts = [self.__loc_config["ALL_HOSTS_NAME"]]
        self._enqueue_rebuild_request(hosts)
    def _enqueue_rebuild_request(self, hosts):
        self.__hosts_waiting.update(hosts)
        if self.__hosts_pending:
            self.log(" ... waiting list has now %s: %s" % (logging_tools.get_plural("entry", len(self.__hosts_waiting)),
                                                           logging_tools.compress_list(self.__hosts_waiting)))
        else:
            self.__hosts_pending = set([x for x in self.__hosts_waiting])
            self.__hosts_waiting = set()
            if self.__hosts_pending:
                self._send_build_requests()
    def _send_build_requests(self):
        if self.__loc_config["ALL_HOSTS_NAME"] in self.__hosts_pending:
            self.__hosts_pending = set([self.__loc_config["ALL_HOSTS_NAME"]])
        self.__queue_dict["build_queue"].put(("rebuild_config", self.__hosts_pending))
    def _config_rebuilt(self, h_list):
        done_list = [x for x in h_list if x     in self.__hosts_pending]
        err_list  = [x for x in h_list if x not in self.__hosts_pending]
        self.__hosts_pending.difference_update(h_list)
        if done_list:
            self.log("Reconfigured Nagios with the following %s: '%s'" % (logging_tools.get_plural("host", len(done_list)),
                                                                          logging_tools.compress_list(done_list)))
        if err_list:
            self.log("Strange: Reconfigured Nagios with %s: '%s'" % (logging_tools.get_plural("unknown host", len(err_list)),
                                                                     logging_tools.compress_list(err_list)),
                     logging_tools.LOG_LEVEL_WARN)
        self._enqueue_rebuild_request([])

class db_verify_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.register_func("validate", self._validate_db)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _validate_db(self, **kwargs):
        db_con = mysql_tools.dbcon_container()
        dc = db_con.get_connection(SQL_ACCESS)
        self.log("starting to validate database")
        sql_file = "/etc/sysconfig/cluster/mysql.cf"
        sql_suc, sql_dict = configfile.readconfig(sql_file, 1)
        dbv_struct = mysql_tools.db_validate(self.log, dc, database=sql_dict["NAGIOS_DATABASE"])
        dbv_struct.repair_tables()
        del dbv_struct
        dc.release()
        del db_con

class server_process(threading_tools.process_pool):
    def __init__(self, db_con):
        self.__log_cache, self.__log_template = ([], None)
        self.__db_con = db_con
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        #self.register_func("new_pid", self._new_pid)
        #self.register_func("remove_pid", self._remove_pid)
        # prepare directories
        #self._prepare_directories()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._check_nagios_version(dc)
        self._check_relay_version(dc)
        self._log_config()
        self._check_nagios_db(dc)
        dc.release()
        self._init_network_sockets()
        self.add_process(db_verify_process("db_verify"), start=True)
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
        dc = self.__db_con.get_connection(SQL_ACCESS)
        sql_str = "SELECT nhs.current_state AS host_status, nh.display_name AS host_name FROM nagiosdb.%s_hoststatus nhs, nagiosdb.%s_hosts nh WHERE nhs.host_object_id=nh.host_object_id" % (
            global_config["MD_TYPE"],
            global_config["MD_TYPE"])
        nag_suc = dc.execute(sql_str)
        if nag_suc:
            nag_dict = dict([(db_rec["host_name"], db_rec["host_status"]) for db_rec in dc.fetchall()])
            num_tot, num_up, num_down = (len(nag_dict.keys()),
                                         nag_dict.values().count(NAG_HOST_UP),
                                         nag_dict.values().count(NAG_HOST_DOWN))
            num_unknown = num_tot - (num_up + num_down)
            self.log("nagios status is: %d up, %d down, %d unknown (%d total)" % (num_up, num_down, num_unknown, num_tot))
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
        dc.release()
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        # FIXME, not implemented, AL 20120319
        #configfile.write_config(dc, "nagios_master", global_config)
    def _check_nagios_version(self, dc):
        start_time = time.time()
        md_version, md_type = ("unknown", "unknown")
        for t_daemon in ["icinga", "nagios"]:
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
                md_type = t_daemon
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
        dv = configfile.device_variable(dc, global_config["SERVER_IDX"], "md_version", description="Version of the Monitor-daemon RPM", value=md_version)
        if dv.is_set():
            dv.set_value(md_version)
            dv.update(dc)
        dc.execute("SELECT d.device_idx FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx AND dg.cluster_device_group")
        if dc.rowcount:
            cdg_idx = dc.fetchone()["device_idx"]
            dv = configfile.device_variable(dc, cdg_idx, "md_version", description="Version of the Monitor-daemon RPM", value=md_version, force_update=True)
            dv = configfile.device_variable(dc, cdg_idx, "md_type", description="Type of the Monitor-daemon RPM", value=md_type, force_update=True)
        if md_version == "unknown":
            self.log("No installed monitor-daemon found (version set to %s)" % (md_version), logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed monitor-daemon %s, version %s" % (md_type, md_version))
        end_time = time.time()
        self.log("monitor-daemon version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _check_relay_version(self, dc):
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
                self._rewrite_nagios_snmp(dc)
        # device_variable local to the server
        if relay_version == "unknown":
            self.log("No installed host-relay found", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed host-relay version %s" % (relay_version))
        end_time = time.time()
        self.log("host-relay version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _rewrite_nagios_snmp(self, dc):
        # step 1: host-relay to snmp-relay
        dc.execute("SELECT * FROM ng_check_command")
        for db_rec in dc.fetchall():
            comline = db_rec["command_line"]
            if comline.startswith("$USER2$") and comline.count(" snmp "):
                new_comline = comline.replace("USER2", "USER3").replace("snmp -S ", "").replace("--arg0=", "").replace("--arg0 ", "-w ").replace("--arg1 ", "-c ")
                self.log("rewriting comline for %s (step 1)" % (db_rec["name"]))
                dc.execute("UPDATE ng_check_command SET command_line=%s WHERE ng_check_command_idx=%s", (new_comline,
                                                                                                         db_rec["ng_check_command_idx"]))
        # step 2: insert community and version
        dc.execute("SELECT * FROM ng_check_command")
        for db_rec in dc.fetchall():
            comline = db_rec["command_line"]
            com_parts = comline.split()
            if com_parts[0] == "$USER3$" and com_parts[3] != "-C":
                # shift arguments by 2
                new_comline = comline
                for arg_num in xrange(11, 2, -1):
                    new_comline = new_comline.replace("ARG%d" % (arg_num - 2), "ARG%d" % (arg_num))
                new_comline = new_comline.replace("$HOSTADDRESS$", "$HOSTADDRESS$ -C ${ARG1:SNMP_COMMUNITY:public} -V ${ARG2:SNMP_VERSION:2}")
                self.log("rewriting comline for %s (step 2)" % (db_rec["name"]))
                dc.execute("UPDATE ng_check_command SET command_line=%s WHERE ng_check_command_idx=%s", (new_comline,
                                                                                                         db_rec["ng_check_command_idx"]))
    def _check_nagios_db(self, dc):
        # add keys for hostname and stuff
        if global_config["MD_TYPE"] == "nagios" and global_config["MD_VERSION"] == 1:
            self.log("Checking Nagios DB (for Nagios 1.x) ...")
            table_dict = {"hoststatus"    : ["host_name"],
                          "servicestatus" : ["host_name", "service_status"]}
            for db_name, db_stuff in table_dict.iteritems():
                dc.execute("DESCRIBE nagiosdb.%s" % (db_name))
                db_dict = dict([(x["Field"], x) for x in dc.fetchall()])
                for name, stuff in db_dict.iteritems():
                    if name in db_stuff and not stuff["Key"]:
                        dc.execute("ALTER TABLE nagiosdb.%s ADD KEY %s(%s)" % (db_name, name, name))
                        self.log("  added key %s to table %s" % (name, db_name))
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
        self.__com_queue.put(("rebuild_config", []))
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
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=4)
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
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "ms")
        client.setsockopt(zmq.HWM, 256)
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
                srv_com["result"] = {"state" : server_command.SRV_REPLY_STATE_OK,
                                     "reply" : "ok"}
                # blabla
                srv_com["result"].attrib.update({"reply" : "ok processed command",
                                                 "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                self.com_socket.send_unicode(unicode(srv_com))
        else:
            self.log("wrong count of input data frames: %d, first one is %s" % (len(in_data),
                                                                               in_data[0]),
                     logging_tools.LOG_LEVEL_ERROR)
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

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                , configfile.str_c_var("idnagios", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var([])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name,
                                                                 prog_name))),
        ("COM_PORT"            , configfile.int_c_var(SERVER_COM_PORT)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    db_con = mysql_tools.dbcon_container()
    try:
        dc = db_con.get_connection("cluster_full_access")
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    sql_info = config_tools.server_check(dc=dc, server_type="nagios_master")
    global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.server_device_idx))])
    ret_state = 256
    if not global_config["SERVER_IDX"]:
        sys.stderr.write(" %s is no md-config-server, exiting..." % (long_host_name))
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if sql_info.num_servers > 1:
        print "Database error for host %s (nagios_config): too many entries found (%d)" % (long_host_name, sql_info.num_servers)
        dc.release()
        sys.exit(5)
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(process_tools.create_log_source_entry(dc, global_config["SERVER_IDX"], "nagios_master", "Nagios / Icinga Monitor")))])
    if not global_config["LOG_SOURCE_IDX"]:
        print "Too many log_source with my id present, exiting..."
        dc.release()
        sys.exit(5)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name, ignore_names=["nagios", "icinga"],
                                                         exclude=configfile.get_manager_pid())
    configfile.read_config_from_db(global_config, dc, "nagios_master", [
        ("COM_PORT"                    , configfile.int_c_var(8010)),
        ("NETSPEED_WARN_MULT"          , configfile.float_c_var(0.85)),
        ("NETSPEED_CRITICAL_MULT"      , configfile.float_c_var(0.95)),
        ("NETSPEED_DEFAULT_VALUE"      , configfile.int_c_var(10000000)),
        ("CHECK_HOST_ALIVE_PINGS"      , configfile.int_c_var(3)),
        ("CHECK_HOST_ALIVE_TIMEOUT"    , configfile.float_c_var(5.0)),
        ("NONE_CONTACT_GROUP"          , configfile.str_c_var("none_group")),
        ("LOG_DIR"                     , configfile.str_c_var("/var/log/cluster/md-config-server")),
        ("FROM_ADDR"                   , configfile.str_c_var(long_host_name)),
        ("MAIN_LOOP_TIMEOUT"           , configfile.int_c_var(30)),
        ("RETAIN_HOST_STATUS"          , configfile.int_c_var(1)),
        ("RETAIN_SERVICE_STATUS"       , configfile.int_c_var(1)),
        ("NDO_DATA_PROCESSING_OPTIONS" , configfile.int_c_var(1 | 4 | 8 | 16 | 64 | 128 | 2048 | 4096 | 8192 | 524288 | 262144 | 1048576 | 2097152)),
        ("EVENT_BROKER_OPTIONS"        , configfile.int_c_var(1 | 4 | 8 | 64 | 128 | 512 | 1024 | 4096 | 32768 | 65536 | 131072)),
        ("CCOLLCLIENT_TIMEOUT"         , configfile.int_c_var(6)),
        ("CSNMPCLIENT_TIMEOUT"         , configfile.int_c_var(20)),
        ("MAX_SERVICE_CHECK_SPREAD"    , configfile.int_c_var(5)),
        ("MAX_CONCURRENT_CHECKS"       , configfile.int_c_var(500)),
        ("ALL_HOSTS_NAME"              , configfile.str_c_var("***ALL***")),
        ("SERVER_SHORT_NAME"           , configfile.str_c_var(mach_name)),
    ])
    dc.release()
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "md-config-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging md-config-server on %s" % (long_host_name)
    ret_state = server_process(db_con).loop()
    sys.exit(ret_state)

if __name__  == "__main__":
    main()
