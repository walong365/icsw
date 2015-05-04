#!/usr/bin/python-init -Ot
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

from initat.tools import logging_tools
from initat.tools import process_tools

from .service import Service
from .constants import *

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

try:
    from django.conf import settings
except:
    settings = None
    config_tools = None
else:
    from django.db import connection
    try:
        _sm = settings.SATELLITE_MODE
    except:
        _sm = False
    if _sm:
        config_tools = None
    else:
        import django
        try:
            django.setup()
        except:
            config_tools = None
        else:
            from initat.tools import config_tools


class ServiceContainer(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__config_tools = None
        self.__act_proc_dict = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SrvC] {}".format(what), log_level)

    def filter_msi_file_name(self, check_list, file_name):
        return [entry for entry in check_list if entry.msi_name == file_name]

    @property
    def proc_dict(self):
        return self.__act_proc_dict

    def update_proc_dict(self):
        self.__act_proc_dict = process_tools.get_proc_list()

    def check_service(self, entry, use_cache=True, refresh=True):
        if not use_cache or not self.__act_proc_dict:
            self.update_proc_dict()
        entry.check(self.__act_proc_dict, refresh=refresh, config_tools=config_tools)

    def apply_filter(self, service_list, instance_xml):
        check_list = instance_xml.xpath(".//instance[@runs_on]", smart_strings=False)
        if service_list:
            check_list = [Service(_entry, self.__log_com) for _entry in check_list if _entry.get("name") in service_list]
        else:
            check_list = [Service(_entry, self.__log_com) for _entry in check_list]
        return check_list

    # main entry point: check_system
    def check_system(self, opt_ns, instance_xml):
        check_list = self.apply_filter(opt_ns.service, instance_xml)
        self.update_proc_dict()
        for entry in check_list:
            self.check_service(entry, use_cache=True, refresh=True)
        return check_list

    def decide(self, subcom, service):
        # based on the entry state and the command given in opt_ns decide what to do
        return {
            False: {
                "start": ["cleanup", "start"],
                "stop": ["cleanup"],
                "restart": ["cleanup", "start"],
                "debug": ["cleanup", "debug"],
            },
            True: {
                "start": [],
                "stop": ["stop", "wait", "cleanup"],
                "restart": ["signal_restart", "stop", "wait", "cleanup", "start"],
                "debug": ["signal_restart", "stop", "wait", "cleanup", "debug"],
            }
        }[service.is_running][subcom]

    def instance_to_form_list(self, opt_ns, res_xml):
        rc_dict = {
            SERVICE_OK: ("running", "ok"),
            SERVICE_DEAD: ("error", "critical"),
            SERVICE_NOT_INSTALLED: ("not installed", "warning"),
            SERVICE_NOT_CONFIGURED: ("not configured", "warning"),
        }
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
            cur_state = int(act_struct.find(".//state_info").get("state", "1"))
            if not opt_ns.failed or (opt_ns.failed and cur_state not in [SERVICE_OK]):
                cur_line = [logging_tools.form_entry(act_struct.attrib["name"], header="Name")]
                cur_line.append(logging_tools.form_entry(act_struct.attrib["runs_on"], header="type"))
                cur_line.append(logging_tools.form_entry(_res.find("state_info").get("check_source", "N/A"), header="source"))
                if opt_ns.thread:
                    s_info = act_struct.find(".//state_info")
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
                    start_time = int(act_struct.find(".//state_info").get("start_time", "0"))
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
                if opt_ns.database:
                    cur_line.append(logging_tools.form_entry(_res.findtext("sql_info"), header="DB info"))
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
                cur_line.append(
                    logging_tools.form_entry(
                        rc_dict[cur_state][0],
                        header="status",
                        display_attribute=rc_dict[cur_state][1],
                    )
                )
                out_bl.append(cur_line)
        return out_bl
