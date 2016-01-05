#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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

""" container for service checks """

import os
import time

from initat.constants import GEN_CS_NAME
from initat.tools import logging_tools, process_tools, config_store

DB_VALID = False

try:
    from initat.cluster.backbone import db_tools
except:
    # client, db_tools not installed
    db_tools = None
else:
    if db_tools.is_reachable():
        DB_VALID = True

if DB_VALID:
    try:
        from initat.cluster.backbone.version_functions import get_database_version, \
            get_models_version, is_debug_run
    except:
        # old import
        from initat.cluster.backbone.models.version_functions import get_database_version, \
            get_models_version, is_debug_run
else:
    # not present
    get_database_version = None
    get_models_version = None
    is_debug_run = None
from .constants import *
from .tools import query_local_meta_server
from .service import Service

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

try:
    from django.conf import settings
except:
    settings = None
    config_tools = None
    License = None
else:
    from django.db import connection, OperationalError, DatabaseError, InterfaceError
    _cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
    try:
        _sm = _cs["mode.is.satellite"]
    except:
        _sm = False
    if _sm:
        config_tools = None
        License = None
    else:
        if db_tools.is_reachable():
            import django
            django.setup()
            from initat.tools import config_tools
            try:
                from initat.cluster.backbone.models import License, LicenseState
            except ImportError:
                License = None
                LicenseState = None
        else:
            config_tools = None
            License = None


class ServiceContainer(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__act_proc_dict = None
        self.__valid_licenses = None
        self.update_version_tuple()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SrvC] {}".format(what), log_level)

    def filter_msi_file_name(self, check_list, file_name):
        return [entry for entry in check_list if entry.msi_name == file_name]

    @property
    def proc_dict(self):
        return self.__act_proc_dict

    @property
    def valid_licenses(self):
        return self.__valid_licenses

    def update_proc_dict(self):
        self.__act_proc_dict = process_tools.get_proc_list()

    def update_valid_licenses(self):
        if License:
            try:
                self.__valid_licenses = License.objects.get_valid_licenses()
            except AttributeError:
                # catch transient error, see UCS integration
                # 10 File '/opt/python-init/lib/python2.7/site-packages/initat/meta_server/server.py', line 349 in _check_processes
                # 11  - 349 : _res_list = self.container.check_system(self.def_ns, self.server_instance.tree)
                # 12 File '/opt/python-init/lib/python2.7/site-packages/initat/icsw/service/container.py', line 110 in check_system
                # 13  - 110 : self.update_valid_licenses()
                # 14 File '/opt/python-init/lib/python2.7/site-packages/initat/icsw/service/container.py', line 88 in update_valid_licenses
                # 15  - 88 : self.__valid_licenses = License.objects.get_valid_licenses()
                # 16 <type 'exceptions.AttributeError'> ('_LicenseManager' object has no attribute 'get_valid_licenses')Exception in process 'main'
                self.__valid_licenses = None
            except (OperationalError, DatabaseError, InterfaceError):
                try:
                    connection.close()
                except:
                    pass
                self.__valid_licenses = None
        else:
            self.__valid_licenses = None

    def update_version_tuple(self):
        if get_database_version is None:
            if not hasattr(self, "model_version"):
                self.model_version = "0"
                self.model_version_changed = False
                # do not log, always true on client
                # self.log("cannot get model version, file missing ... ?", logging_tools.LOG_LEVEL_WARN)
        else:
            _database_v = get_database_version()
            _model_v = get_models_version()
            if not hasattr(self, "model_version"):
                self.model_version = _model_v
                self.model_version_changed = False
                self.log("Model version is {}".format(_model_v))
            else:
                if _model_v != self.model_version:
                    _cs = "Model version changed from {} to {}".format(
                        self.model_version,
                        _model_v,
                    )
                    if not is_debug_run():
                        self.model_version_changed = True
                        self.log(
                            "{}".format(
                                _cs
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log(
                            "{} (ignoring due to debug run)".format(
                                _cs,
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )

    def check_service(self, entry, use_cache=True, refresh=True, version_changed=False, meta_result=None):
        if not use_cache or not self.__act_proc_dict:
            self.update_proc_dict()
            self.update_valid_licenses()
        entry.check(
            self.__act_proc_dict,
            refresh=refresh,
            config_tools=config_tools,
            valid_licenses=self.valid_licenses,
            version_changed=version_changed,
            meta_result=meta_result,
        )

    def apply_filter(self, service_list, instance_xml):
        check_list = instance_xml.tree.xpath(".//instance[@runs_on]", smart_strings=False)
        if service_list:
            check_list = [Service(_entry, self.__log_com) for _entry in check_list if _entry.get("name") in service_list]
            found_names = set([_srv.name for _srv in check_list])
            mis_names = set(service_list) - found_names
            if mis_names:
                self.log(
                    "{} not found: {}".format(
                        logging_tools.get_plural("service", len(mis_names)),
                        ", ".join(sorted(list(mis_names))),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            check_list = [Service(_entry, self.__log_com) for _entry in check_list]
        return check_list

    # main entry point: check_system
    def check_system(self, opt_ns, instance_xml):
        check_list = self.apply_filter(opt_ns.service, instance_xml)
        self.update_proc_dict()
        self.update_valid_licenses()
        self.update_version_tuple()
        if opt_ns.tstate:
            meta_result = query_local_meta_server(instance_xml, "overview", services=[_srv.name for _srv in check_list])
            # check for valid meta-server result
            if meta_result is not None:
                if meta_result.get_log_tuple()[1] > logging_tools.LOG_LEVEL_WARN:
                    meta_result = None
        else:
            meta_result = None
        for entry in check_list:
            self.check_service(entry, use_cache=True, refresh=True, version_changed=self.model_version_changed, meta_result=meta_result)
        # if self._config_check_errors:
        #    self.log(
        #        "{} not ok ({}), triggering model check".format(
        #            logging_tools.get_plural("config check", len(self._config_check_errors)),
        #            ", ".join(self._config_check_errors),
        #        )
        #    )
        #    if self.__model_md5:
        #        if _get_fp(self.__model_md5) != _get_fp(self.get_models_md5()):
        #            self.log("models have changed, forcing all services with DB-checks to state dead")
        #            self.__models_changed = True
        return check_list

    def decide(self, subcom, service):
        # based on the entry state and the command given in opt_ns decide what to do
        return {
            "error": {
                "start": ["cleanup", "start"],
                "stop": ["cleanup"],
                "restart": ["cleanup", "start"],
                "debug": ["cleanup", "debug"],
                "reload": [],
            },
            "warn": {
                "start": ["stop", "wait", "cleanup", "start"],
                "stop": ["stop", "wait", "cleanup"],
                "restart": ["stop", "wait", "cleanup", "start"],
                "debug": ["stop", "wait", "cleanup", "debug"],
                "reload": ["reload"],
            },
            "ok": {
                "start": [],
                "stop": ["stop", "wait", "cleanup"],
                "restart": ["signal_restart", "stop", "wait", "cleanup", "start"],
                "debug": ["signal_restart", "stop", "wait", "cleanup", "debug"],
                "reload": ["reload"],
            }
        }[service.run_state][subcom]

    def instance_to_form_list(self, opt_ns, res_xml):
        prc_dict = {
            SERVICE_OK: ("running", "ok"),
            SERVICE_DEAD: ("error", "critical"),
            SERVICE_INCOMPLETE: ("incomplete", "critical"),
            SERVICE_NOT_INSTALLED: ("not installed", "warning"),
            SERVICE_NOT_CONFIGURED: ("not configured", "warning"),
        }
        crc_dict = {
            CONF_STATE_RUN: ("run", "ok"),
            CONF_STATE_STOP: ("stop", "critical"),
            CONF_STATE_IP_MISMATCH: ("ip mismatch", "critical"),
        }
        meta_dict = {
            TARGET_STATE_RUNNING: ("run", "ok"),
            TARGET_STATE_STOPPED: ("stop", "critical"),
        }
        if License is not None:
            lic_dict = {
                -1: ("-", ""),
                LicenseState.none: ("no license", "critical"),
                LicenseState.violated: ("parameter violated", "critical"),
                LicenseState.valid: ("valid", "ok"),
                LicenseState.grace: ("in grace", "warning"),
                LicenseState.expired: ("expired", "critical"),
                # LicenseState.ip_mismatch: ("ip mismatch", "critical"),
            }
        else:
            lic_dict = None
        out_bl = logging_tools.new_form_list()
        types = sorted(list(set(res_xml.xpath(".//instance/@runs_on", start_strings=False))))
        _list = sum(
            [
                res_xml.xpath("instance[result and @runs_on='{}']".format(_type)) for _type in types
            ],
            []
        )
        for act_struct in _list:
            _res = act_struct.find("result")
            p_state = int(act_struct.find(".//process_state_info").get("state", SERVICE_DEAD))
            c_state = int(act_struct.find(".//configured_state_info").get("state", CONF_STATE_STOP))
            if not opt_ns.failed or (opt_ns.failed and p_state not in [SERVICE_OK]):
                cur_line = [logging_tools.form_entry(act_struct.attrib["name"], header="Name")]
                cur_line.append(logging_tools.form_entry(act_struct.attrib["runs_on"], header="runson"))
                cur_line.append(logging_tools.form_entry(_res.find("process_state_info").get("check_source", "N/A"), header="source"))
                if opt_ns.thread:
                    s_info = act_struct.find(".//process_state_info")
                    if "num_started" not in s_info.attrib:
                        cur_line.append(logging_tools.form_entry(s_info.text))
                    else:
                        num_diff, any_ok = (
                            int(s_info.get("num_diff")),
                            True if int(act_struct.attrib["any_threads_ok"]) else False
                        )
                        # print etree.tostring(act_struct, pretty_print=True)
                        num_pids = len(_res.findall(".//pids/pid"))
                        da_name = ""
                        if any_ok:
                            pass
                        else:
                            if num_diff < 0:
                                da_name = "critical"
                            elif num_diff > 0:
                                da_name = "warning"
                        cur_line.append(logging_tools.form_entry(s_info.attrib["proc_info_str"], header="Thread info", display_attribute=da_name))
                if opt_ns.started:
                    start_time = int(act_struct.find(".//process_state_info").get("start_time", "0"))
                    if start_time:
                        diff_time = max(0, time.mktime(time.localtime()) - start_time)
                        diff_days = int(diff_time / (3600 * 24))
                        diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                        diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                        diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                        ret_str = "{}".format(
                            time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(start_time))
                        )
                    else:
                        ret_str = "no start info found"
                    cur_line.append(logging_tools.form_entry(ret_str, header="started"))
                if opt_ns.pid:
                    pid_dict = {}
                    for cur_pid in act_struct.findall(".//pids/pid"):
                        pid_dict[int(cur_pid.text)] = int(cur_pid.get("count", "1"))
                    if pid_dict:
                        p_list = sorted(pid_dict.keys())
                        if max(pid_dict.values()) == 1:
                            cur_line.append(logging_tools.form_entry(logging_tools.compress_num_list(p_list), header="pids"))
                        else:
                            cur_line.append(
                                logging_tools.form_entry(
                                    ",".join(["{:d}{}".format(
                                        key,
                                        " ({:d})".format(pid_dict[key]) if pid_dict[key] > 1 else "") for key in p_list]
                                    ),
                                    header="pids"
                                )
                            )
                    else:
                        cur_line.append(logging_tools.form_entry("no PIDs", header="pids"))
                if opt_ns.config:
                    cur_line.append(logging_tools.form_entry(act_struct.find(".//config_info").text, header="config info"))
                if opt_ns.memory:
                    cur_mem = act_struct.find(".//memory_info")
                    if cur_mem is not None:
                        mem_str = process_tools.beautify_mem_info(int(cur_mem.text))
                    else:
                        # no pids hence no memory info
                        mem_str = ""
                    cur_line.append(logging_tools.form_entry_right(mem_str, header="Memory"))
                if opt_ns.version:
                    if "version" in _res.attrib:
                        _version = _res.attrib["version"]
                    else:
                        _version = ""
                    cur_line.append(logging_tools.form_entry_right(_version, header="Version"))
                _lic_info = _res.find("license_info")
                _lic_state = int(_lic_info.attrib["state"])
                if lic_dict is None:
                    cur_line.append(
                        logging_tools.form_entry(
                            "---",
                            header="License",
                        )
                    )
                else:
                    cur_line.append(
                        logging_tools.form_entry(
                            lic_dict[_lic_state][0],
                            header="License",
                            display_attribute=lic_dict[_lic_state][1],
                        )
                    )
                cur_line.append(
                    logging_tools.form_entry(
                        prc_dict[p_state][0],
                        header="PState",
                        display_attribute=prc_dict[p_state][1],
                    )
                )
                cur_line.append(
                    logging_tools.form_entry(
                        crc_dict[c_state][0],
                        header="CState",
                        display_attribute=crc_dict[c_state][1],
                    )
                )
                if opt_ns.tstate:
                    _meta_res = act_struct.find(".//meta_result")
                    if _meta_res is not None:
                        t_state = int(_meta_res.get("target_state"))
                        cur_line.append(
                            logging_tools.form_entry(
                                meta_dict[t_state][0],
                                header="TState",
                                display_attribute=meta_dict[t_state][1],
                            )
                        )
                    else:
                        cur_line.append(
                            logging_tools.form_entry(
                                "unknown",
                                header="TState",
                                display_attribute="warning",
                            )
                        )
                out_bl.append(cur_line)
        return out_bl
