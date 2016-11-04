# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import unicode_literals, print_function

import os
import shutil

from django.db.models import Q

from initat.cluster.backbone.models import device, user
from initat.md_config_server.config import FlatMonBaseConfig, MonFileContainer, MonDirContainer, \
    CfgEmitStats
from initat.tools import logging_tools, process_tools
from .global_config import global_config
from ..mixins import NagVisMixin

__all__ = [
    b"MainConfig",
    b"MainConfigContainer",
]


class MainConfigContainer(object):
    def __init__(self, process, monitor_server, **kwargs):
        self.__process = process
        self.__slave_name = kwargs.get("slave_name", None)
        if self.__slave_name:
            self.__dir_offset = os.path.join("slaves", self.__slave_name)
        else:
            self.__dir_offset = "master"
        self.monitor_server = monitor_server
        # is this the config for the main server ?
        self.master = True if not self.__slave_name else False
        self.log("init MainConfigContainer")

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            u"[mcc{}] {}".format(
                " {}".format(self.__slave_name) if self.__slave_name else "",
                what
            ),
            level
        )

    def serialize(self):
        return {
            "slave_name": self.__slave_name,
            "dir_offset": self.__dir_offset,
            "monitor_server": self.monitor_server.idx,
            "master": self.master,
        }


class MainConfig(dict, NagVisMixin):
    def __init__(self, proc, ser_dict):
        dict.__init__(self)
        # container for all configs for a given monitor server (master or slave)
        self.__process = proc
        self.__slave_name = ser_dict["slave_name"]
        self.__dir_offset = ser_dict["dir_offset"]
        self.monitor_server = device.objects.get(Q(pk=ser_dict["monitor_server"]))
        # is this the config for the main server ?
        self.master = ser_dict["master"]
        self.allow_write_entries = global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]
        # create directories
        self._create_directories()
        # clean them if necessary
        self._clear_etc_dir()
        self._create_base_config_entries()
        self.write_entries()
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

    @property
    def is_valid(self):
        ht_conf_names = [key for key, value in self.iteritems() if isinstance(value, MonFileContainer)]
        invalid = sorted(
            [
                key for key in ht_conf_names if not self[key].is_valid
            ]
        )
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

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            u"[mc{}] {}".format(
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
            "var/spool/checkresults"
        ]
        if process_tools.get_sys_bits() == 64:
            dir_names.append("lib64")
        _main_dir = global_config["MD_BASEDIR"]
        # dir dict for writing on disk
        self.__w_dir_dict = {
            dir_name: os.path.normpath(os.path.join(_main_dir, self.__dir_offset, dir_name)) for dir_name in dir_names
        }
        # dir dict for referencing
        self.__r_dir_dict = {
            dir_name: os.path.normpath(os.path.join(_main_dir, dir_name)) for dir_name in dir_names
        }
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
                full_path = os.path.join(self.__w_dir_dict["etc"], dir_e)
                if os.path.isfile(full_path):
                    try:
                        os.unlink(full_path)
                    except:
                        self.log(
                            "Cannot delete file {}: {}".format(
                                full_path,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )

    def _create_base_config_entries(self):
        _md_type = global_config["MD_TYPE"]
        _md_basedir = global_config["MD_BASEDIR"]
        resource_file = MonFileContainer("resource")
        resource_cfg = FlatMonBaseConfig("flat", "resource")
        resource_file.add_object(resource_cfg)
        if os.path.isfile(os.path.join(_md_basedir, "libexec", "check_dns")):
            resource_cfg["$USER1$"] = os.path.join(
                _md_basedir,
                "libexec",
            )
        else:
            resource_cfg["$USER1$"] = os.path.join(
                _md_basedir,
                "lib",
            )
        resource_cfg["$USER2$"] = "/opt/cluster/sbin/ccollclientzmq -t {:d}".format(global_config["CCOLLCLIENT_TIMEOUT"])
        resource_cfg["$USER3$"] = "/opt/cluster/sbin/csnmpclientzmq -t {:d}".format(global_config["CSNMPCLIENT_TIMEOUT"])
        main_values = [
            (
                "log_file",
                os.path.join(
                    self.__r_dir_dict["var"],
                    "{}.log".format(_md_type),
                )
            ),
            ("cfg_file", []),
            (
                "resource_file",
                os.path.join(
                    self.__r_dir_dict["etc"],
                    "{}.cfg".format(resource_cfg.name),
                )
            ),
            ("{}_user".format(_md_type), "idmon"),
            ("{}_group".format(_md_type), "idg"),
            ("check_external_commands", 1),
            ("command_check_interval", 1),
            ("command_file", self.get_command_name()),
            ("command_check_interval", "5s"),
            ("lock_file", os.path.join(self.__r_dir_dict["var"], global_config["MD_LOCK_FILE"])),
            ("temp_file", os.path.join(self.__r_dir_dict["var"], "temp.tmp")),
            ("log_rotation_method", "d"),
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
            ("state_retention_file", os.path.join(self.__r_dir_dict["var"], "retention.dat")),
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
            ("admin_email", "cluster@init.at"),
            ("admin_pager", "????"),
            # ("debug_file"      , os.path.join(self.__r_dir_dict["var"], "icinga.dbg")),
            # ("debug_level"     , -1),
            # ("debug_verbosity" , 2),
            # NDO stuff
        ]
        lib_dir_name = "lib64" if process_tools.get_sys_bits() == 64 else "lib"
        for sub_dir_name in ["df_settings", "manual"]:
            sub_dir = os.path.join(self.__w_dir_dict["etc"], sub_dir_name)
            if os.path.isdir(sub_dir):
                shutil.rmtree(sub_dir)
        main_values.extend(
            [
                (
                    "broker_module", [],
                ),
                (
                    "broker_module", "{} {}".format(
                        os.path.join(
                            self.__r_dir_dict[lib_dir_name],
                            "mk-livestatus",
                            "livestatus.o"
                        ),
                        os.path.join(
                            self.__r_dir_dict["var"],
                            "live"
                        )
                    )
                ),
                (
                    "event_broker_options", -1
                )
            ]
        )
        main_values.append(
            ("cfg_dir", []),
        )
        if self.master:
            # main_values.append(
            #     ("cfg_dir", os.path.join(self.__r_dir_dict["etc"], "manual")),
            # )
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
        else:
            # add global event handlers
            main_values.extend(
                [
                    ("ochp_command", "ochp-command"),
                    ("ocsp_command", "ocsp-command"),
                    ("stalking_event_handlers_for_hosts", 1),
                    ("stalking_event_handlers_for_services", 1),
                ]
            )
        main_values.extend(
            [
                ("object_cache_file", os.path.join(self.__r_dir_dict["var"], "object.cache")),
                ("use_large_installation_tweaks", "1"),
                ("enable_environment_macros", "0"),
                ("max_service_check_spread", global_config["MAX_SERVICE_CHECK_SPREAD"]),
                ("max_host_check_spread", global_config["MAX_HOST_CHECK_SPREAD"]),
            ]
        )
        main_file = MonFileContainer(global_config["MAIN_CONFIG_NAME"])
        main_cfg = FlatMonBaseConfig(
            "flat",
            global_config["MAIN_CONFIG_NAME"],
            *main_values
        )
        main_file.add_object(main_cfg)
        for log_descr, en in [
            ("notifications", 1),
            ("service_retries", 1),
            ("host_retries", 1),
            ("event_handlers", 1),
            ("initial_states", 1),  # this must be true for log parsing
            ("external_commands", 1 if global_config["LOG_EXTERNAL_COMMANDS"] else 0),
            ("passive_checks", 1 if global_config["LOG_PASSIVE_CHECKS"] else 0)
        ]:
            main_cfg["log_{}".format(log_descr)] = en
        for to_descr, to in [
            ("service_check", 60),
            ("host_check", 30),
            ("event_handler", 30),
            ("notification", 30),
            ("ocsp", 5),
            ("perfdata", 5)
        ]:
            main_cfg["{}_timeout".format(to_descr)] = to
        for th_descr, th in [
            ("low_service", 5.0),
            ("high_service", 20.0),
            ("low_host", 5.0),
            ("high_host", 20.0)
        ]:
            main_cfg["{}_flap_threshold".format(th_descr)] = th
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
            def_user = "{}admin".format(_md_type)
        cgi_file = MonFileContainer("cgi")
        cgi_config = FlatMonBaseConfig(
            "flat",
            "cgi",
            *[
                (
                    "main_config_file", os.path.join(
                        self.__r_dir_dict["etc"],
                        "{}.cfg".format(global_config["MAIN_CONFIG_NAME"])
                    )
                ),
                ("physical_html_path", "{}".format(self.__r_dir_dict["share"])),
                ("url_html_path", "/{}".format(_md_type)),
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
                ("authorized_for_all_service_commands", def_user),
                ("tac_show_only_hard_state", 1),
            ]
        )
        cgi_file.add_object(cgi_config)
        self[main_file.name] = main_file
        self[cgi_file.name] = cgi_file
        self[resource_file.name] = resource_file
        if self.master:
            # wsgi config
            uwsgi_file = MonFileContainer("/opt/cluster/etc/uwsgi/icinga.wsgi.ini")
            if os.path.isfile("/etc/debian_version"):
                www_user, www_group = ("www-data", "www-data")
            elif os.path.isfile("/etc/redhat-release") or os.path.islink("/etc/redhat-release"):
                www_user, www_group = ("apache", "apache")
            else:
                www_user, www_group = ("wwwrun", "www")
            wsgi_config = FlatMonBaseConfig(
                "flat",
                "uwsgi",
                *[
                    ("[uwsgi]", None),
                    ("chdir", self.__r_dir_dict[""]),
                    ("plugin-dir", os.path.join("/opt/cluster", lib_dir_name)),
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
                ]
            )
            uwsgi_file.add_object(wsgi_config)
            self[uwsgi_file.name] = uwsgi_file
        if global_config["ENABLE_NAGVIS"] and self.master:
            self.NV_create_base_entries()

    def _create_access_entries(self):
        if self.master:
            self.log("creating http_users.cfg file")
            # create htpasswd
            htp_file = os.path.join(self.__r_dir_dict["etc"], "http_users.cfg")
            file(htp_file, "w").write(
                "\n".join(
                    [
                        "{}:{{SSHA}}{}".format(
                            cur_u.login,
                            cur_u.password_ssha.split(":", 1)[1]
                        ) for cur_u in user.objects.filter(
                            Q(active=True)
                        ) if cur_u.password_ssha.count(":")
                    ] + [""]
                ).encode("utf8")
            )
            if global_config["ENABLE_NAGVIS"]:
                self.NV_create_access_entries()

    def write_entries(self):
        if not self.__allow_write_entries:
            self.log("writing entries not allowed", logging_tools.LOG_LEVEL_WARN)
            return 0
        w_stats = CfgEmitStats()
        for key, stuff in self.iteritems():
            stuff.write_content(w_stats, self.__w_dir_dict["etc"], self.log)
        if w_stats.count:
            self.log(
                "wrote {} in {}".format(
                    w_stats.info,
                    w_stats.runtime,
                )
            )
        else:
            self.log("no config files written")
        return w_stats.total_count

    def add_config(self, config):
        if config.name in self:
            self.log("replacing config {}".format(config.name), logging_tools.LOG_LEVEL_WARN)
        self[config.name] = config

    def dump_logs(self):
        self.log("starting dump of buffered logs")
        for key, value in self.iteritems():
            for _line, _what in value.buffered_logs:
                self.log(_line, _what)
        self.log("done")

    def __setitem__(self, key, value):
        # print "SI", key, type(value)
        super(MainConfig, self).__setitem__(key, value)
        _main_cfg_name = global_config["MAIN_CONFIG_NAME"]
        new_file_keys, new_dir_keys, new_resource_keys = ([], [], [])
        for key, value in self.iteritems():
            _path = value.get_file_name(
                self.__r_dir_dict["etc"]
            )
            if isinstance(value, MonDirContainer):
                new_dir_keys.append(_path)
            elif isinstance(value, MonFileContainer):
                if value.name in ["cgi", _main_cfg_name]:
                    # ignore main and cgi config file
                    pass
                elif value.name.startswith("/"):
                    # ignore files not residing in etc tree
                    pass
                elif value.name.startswith("resource"):
                    new_resource_keys.append(_path)
                else:
                    new_file_keys.append(_path)
        # print new_file_keys
        old_file_keys = self[_main_cfg_name].object_list[0]["cfg_file"]
        old_dir_keys = self[_main_cfg_name].object_list[0]["cfg_dir"]
        old_resource_keys = self[_main_cfg_name].object_list[0]["resource_file"]
        write_cfg = False
        if old_file_keys != new_file_keys:
            self[_main_cfg_name].object_list[0]["cfg_file"] = new_file_keys
            write_cfg = True
        if old_dir_keys != new_dir_keys:
            self[_main_cfg_name].object_list[0]["cfg_dir"] = new_dir_keys
            write_cfg = True
        if old_resource_keys != new_resource_keys:
            self[_main_cfg_name].object_list[0]["resource_file"] = new_resource_keys
            write_cfg = True
        if write_cfg:
            self.write_entries()
