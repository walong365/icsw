#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2014 Andreas Lang-Nevyjel, init.at
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

""" checks installed servers on system """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import argparse
import commands
import datetime
import logging_tools
import process_tools
import psutil
import stat
import subprocess
import time
try:
    import django
    django.setup()
except:
    config_tools = None
else:
    try:
        import config_tools
    except:
        config_tools = None

EXTRA_SERVER_DIR = "/opt/cluster/etc/extra_servers.d"


def check_processes(name, pids, pid_thread_dict, any_ok):
    ret_state = 7
    unique_pids = {key: pids.count(key) for key in set(pids)}
    pids_found = {key: pid_thread_dict.get(key, 1) for key in set(pids)}
    num_started = sum(unique_pids.values()) if unique_pids else 0
    num_found = sum(pids_found.values()) if pids_found else 0
    # check for extra Nagios2.x thread
    if any_ok and num_found:
        ret_state = 0
    elif num_started == num_found:
        ret_state = 0
    return ret_state, num_started, num_found

INSTANCE_XML = """
<instances>
    <instance name="hoststatus" check_type="simple" pid_file_name="hoststatus_zmq" process_name="hoststatus_zmq" runs_on="node" version_file="/opt/cluster/sbin/_hoststatus_version.py">
    </instance>
    <instance name="logging-server" runs_on="node" pid_file_name="logserver/logserver.pid" has_force_stop="1" meta_server_name="logserver" version_file="%{INIT_BASE}/%{NAME}/version.py">
    </instance>
    <instance name="meta-server" runs_on="node"  has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
    </instance>
    <instance name="host-monitoring" runs_on="node" pid_file_name="collserver/collserver.pid"  has_force_stop="1" meta_server_name="collserver" version_file="%{INIT_BASE}/%{NAME}/version.py">
    </instance>
    <instance name="package-client" runs_on="node"  has_force_stop="1" pid_file_name="package-client/package-client.pid" version_file="%{INIT_BASE}/package_install/client/version.py">
    </instance>
    <instance name="gmond" runs_on="node" pid_file_name="">
    </instance>
    <instance name="logcheck-server" pid_file_name="logcheck-server/logcheck-server.pid" has_force_stop="1" meta_server_name="logcheck" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>syslog_server</config_name>
        </config_names>
    </instance>
    <instance name="package-server" pid_file_name="package-server/package-server.pid" has_force_stop="1" version_file="%{INIT_BASE}/package_install/server/version.py">
        <config_names>
            <config_name>package_server</config_name>
        </config_names>
    </instance>
    <instance name="mother" pid_file_name="mother/mother.pid" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>mother_server</config_name>
        </config_names>
    </instance>
    <!-- collectd is checked via process_name to take the python side-process into account -->
    <instance name="collectd-init" runs_on="server" has_force_stop="1" pid_file_name="collectd-init/collectd-init.pid" meta_server_name="collectd-init" version_file="%{INIT_BASE}/collectd/version.py">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="memcached" check_type="simple" pid_file_name="memcached/memcached.pid" any_threads_ok="1" runs_on="system">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="nginx" check_type="simple" pid_file_name="nginx.pid" any_threads_ok="1" runs_on="system">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="icinga" check_type="simple" pid_file_name="/opt/icinga/var/icinga.lock" any_threads_ok="1" runs_on="system">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="uwsgi-init" check_type="simple" pid_file_name="uwsgi-init.pid" any_threads_ok="1" runs_on="system">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="rrdcached" check_type="threads_by_pid_file" any_threads_ok="1" runs_on="system" pid_file_name="rrdcached/rrdcached.pid" startstop="0">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="rrd-grapher" pid_file_name="rrd-grapher/rrd-grapher.pid" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="rms-server" pid_file_name="rms-server/rms-server.pid" has_force_stop="1" meta_server_name="rms_server" version_file="%{INIT_BASE}/rms/sge_server_version.py">
        <config_names>
            <config_name>sge_server</config_name>
            <config_name>rms_server</config_name>
        </config_names>
    </instance>
    <instance name="cluster-server" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="discovery-server" pid_file_name="discovery-server/discovery-server.pid" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>discovery_server</config_name>
        </config_names>
    </instance>
    <instance name="cluster-config-server" pid_file_name="cluster-config-server/cluster-config-server.pid" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>config_server</config_name>
        </config_names>
    </instance>
    <instance name="host-relay" pid_file_name="collrelay/collrelay.pid" has_force_stop="1" meta_server_name="collrelay" version_file="%{INIT_BASE}/host_monitoring/version.py">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="snmp-relay" pid_file_name="snmp-relay/snmp-relay.pid" has_force_stop="1" version_file="%{INIT_BASE}/snmp_relay/version.py">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="md-config-server" pid_file_name="md-config-server/md-config-server.pid" has_force_stop="1" version_file="%{INIT_BASE}/%{NAME}/version.py">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>-
    </instance>
</instances>
"""


def get_instance_xml():
    instance_xml = etree.fromstring(INSTANCE_XML)  # @UndefinedVariable
    # check for additional instances
    if os.path.isdir(EXTRA_SERVER_DIR):
        for entry in os.listdir(EXTRA_SERVER_DIR):
            if entry.endswith(".xml"):
                try:
                    add_inst_list = etree.fromstring(open(os.path.join(EXTRA_SERVER_DIR, entry), "r").read())  # @UndefinedVariable
                except:
                    print(
                        "cannot read entry '{}' from {}: {}".format(
                            entry,
                            EXTRA_SERVER_DIR,
                            process_tools.get_except_info(),
                        )
                    )
                else:
                    for sub_inst in add_inst_list.findall("instance"):
                        instance_xml.append(sub_inst)
    for cur_el in instance_xml.findall("instance"):
        name = cur_el.attrib["name"]
        for key, def_value in [
            ("runs_on", "server"),
            ("check_type", "threads_by_pid_file"),
            ("any_threads_ok", "0"),
            ("pid_file_name", "{}.pid".format(name)),
            ("init_script_name", name),
            ("startstop", "1"),
            ("checked", "0"),
            ("to_check", "0"),
            ("process_name", name),
            ("meta_server_name", name),
        ]:
            if key not in cur_el.attrib:
                cur_el.attrib[key] = def_value
    return instance_xml


def check_system(opt_ns):
    INIT_BASE = "/opt/python-init/lib/python/site-packages/initat"
    instance_xml = get_instance_xml()
    set_all_servers = True if (opt_ns.server == ["ALL"] or opt_ns.instance == ["ALL"]) else False
    set_all_nodes = True if (opt_ns.node == ["ALL"] or opt_ns.instance == ["ALL"]) else False
    set_all_system = True if (opt_ns.system == ["ALL"] or opt_ns.instance == ["ALL"]) else False
    if set_all_servers:
        opt_ns.server = instance_xml.xpath(".//*[@runs_on='server']/@name", smart_strings=False)
    if set_all_nodes:
        opt_ns.node = instance_xml.xpath(".//*[@runs_on='node']/@name", smart_strings=False)
    if set_all_system:
        opt_ns.system = instance_xml.xpath(".//*[@runs_on='system']/@name", smart_strings=False)
    for cur_el in instance_xml.xpath(".//instance[@runs_on]", smart_strings=False):
        if cur_el.attrib["name"] in getattr(opt_ns, cur_el.attrib["runs_on"]) or cur_el.attrib["name"] in opt_ns.instance:
            cur_el.attrib["to_check"] = "1"
    act_proc_dict = process_tools.get_proc_list_new()
    pid_thread_dict = process_tools.get_process_id_list(True, True)
    r_stat, out = commands.getstatusoutput("chkconfig --list")
    stat_dict = {}
    if not r_stat:
        for line in out.split("\n"):
            if line.count("0:") and line.count("1:"):
                key, level_list = line.split(None, 1)
                level_list = [int(level) for level, _flag in [entry.split(":") for entry in level_list.strip().split()] if _flag == "on" and level.isdigit()]
                stat_dict[key.lower()] = level_list
    for entry in instance_xml.findall("instance[@to_check='1']"):
        if config_tools and not opt_ns.no_database and entry.find(".//config_names/config_name") is not None:
            dev_config = config_tools.device_with_config(entry.findtext(".//config_names/config_name"))
        else:
            dev_config = None
        name = entry.attrib["name"]
        entry.attrib["checked"] = "1"
        if entry.attrib["init_script_name"] in stat_dict:
            entry.append(
                E.runlevels(
                    *[E.runlevel("{:d}".format(cur_rl)) for cur_rl in stat_dict.get(entry.attrib["init_script_name"], [])]
                )
            )
        act_pids = []
        init_script_name = os.path.join("/etc", "init.d", entry.attrib["init_script_name"])
        if entry.attrib["check_type"] == "simple":
            if os.path.isfile(init_script_name):
                act_pids = []
                for _proc in psutil.process_iter():
                    try:
                        if _proc.is_running() and _proc.name() == entry.attrib["process_name"]:
                            act_pids.append(_proc.pid)
                    except psutil.NoSuchProcess:
                        pass
                if act_pids:
                    act_state, act_str = (0, "running")
                else:
                    act_state, act_str = (7, "not running")
            else:
                act_state, act_str = (5, "not installed")
            entry.append(E.state_info(act_str, state="{:d}".format(act_state)))
            entry.attrib["check_source"] = "simple"
        elif entry.attrib["check_type"] == "threads_by_pid_file":
            pid_file_name = entry.attrib["pid_file_name"]
            if pid_file_name == "":
                # no pid file
                pass
            elif not pid_file_name.startswith("/"):
                pid_file_name = os.path.join("/var", "run", pid_file_name)
            if pid_file_name and os.path.isfile(pid_file_name):
                ms_name = None
                # do we need a loop here ?
                for c_name in set([entry.attrib["meta_server_name"]]):
                    cur_ms_name = os.path.join("/var", "lib", "meta-server", c_name)
                    if os.path.exists(cur_ms_name):
                        ms_name = cur_ms_name
                        break
                if ms_name:
                    # check according to meta-serer block
                    pid_time = os.stat(ms_name)[stat.ST_CTIME]
                    ms_block = process_tools.meta_server_info(ms_name)
                    ms_block.check_block(pid_thread_dict, act_proc_dict)
                    diff_dict = {key: value for key, value in ms_block.bound_dict.iteritems() if value}
                    diff_threads = sum(ms_block.bound_dict.values())
                    act_pids = ms_block.pids_found
                    num_started = len(act_pids)
                    if diff_threads:
                        act_state = 7
                        num_found = num_started
                        num_diff = diff_threads
                    else:
                        act_state = 0
                        num_found = num_started
                        num_diff = 0
                    # print ms_block.pids, ms_block.pid_check_string
                    entry.attrib["check_source"] = "meta"
                else:
                    pid_time = os.stat(pid_file_name)[stat.ST_CTIME]
                    act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
                    act_state, num_started, num_found = check_processes(name, act_pids, pid_thread_dict, True if int(entry.attrib["any_threads_ok"]) else False)
                    num_diff = 0
                    diff_dict = {}
                    entry.attrib["check_source"] = "pid"
                entry.append(
                    E.state_info(
                        *[
                            E.diff_info(
                                pid="{:d}".format(key),
                                diff="{:d}".format(value)
                            ) for key, value in diff_dict.iteritems()
                        ],
                        num_started="{:d}".format(num_started),
                        num_found="{:d}".format(num_found),
                        num_diff="{:d}".format(num_diff),
                        pid_time="{:d}".format(pid_time),
                        state="{:d}".format(act_state)
                    ),
                )
            else:
                if os.path.isfile(init_script_name):
                    if pid_file_name == "":
                        # only used for gmond ?
                        found_procs = {}
                        for key, value in act_proc_dict.iteritems():
                            try:
                                if value.name() == entry.attrib["process_name"]:
                                    found_procs[key] = (value, pid_thread_dict.get(value.pid, 1))
                            except psutil.NoSuchProcess:
                                pass
                        act_pids = sum([[key] * value[1] for key, value in found_procs.iteritems()], [])
                        threads_found = sum([value[1] for value in found_procs.itervalues()])
                        _info = E.state_info(
                            num_diff="0",
                            state="0" if act_pids else "7",
                        )
                        if threads_found:
                            _info.attrib.update(
                                {
                                    "num_started": "{:d}".format(threads_found),
                                    "num_found": "{:d}".format(threads_found),
                                }
                            )
                        entry.append(_info)
                    else:
                        entry.append(
                            E.state_info(
                                "no threads",
                                state="7",
                            )
                        )
                else:
                    entry.append(
                        E.state_info(
                            "not installed",
                            state="5",
                        )
                    )
        else:
            entry.append(E.state_info("unknown check_type '{}'".format(entry.attrib["check_type"]), state="1"))
        entry.append(
            E.pids(
                *[E.pid("{:d}".format(cur_pid), count="{:d}".format(act_pids.count(cur_pid))) for cur_pid in set(act_pids)]
                )
            )
        if entry.attrib["runs_on"] == "server":
            if dev_config is not None:
                srv_type_list = [_e.replace("-", "_") for _e in entry.xpath(".//config_names/config_name/text()", smart_strings=False)]
                found = False
                for srv_type in srv_type_list:
                    if srv_type in dev_config:
                        found = True
                        sql_info = dev_config[srv_type][0]
                        if not sql_info.effective_device:
                            # FIXME ?
                            act_state = 5
                        break
                if not found:
                    sql_info = "not set ({})".format(", ".join(srv_type_list))
            else:
                sql_info = "no db_con"
        else:
            sql_info = "node"
        if type(sql_info) == str:
            entry.append(
                E.sql_info(str(sql_info))
                )
        else:
            entry.append(
                E.sql_info("{} ({})".format(
                    sql_info.server_info_str,
                    sql_info.config_name),
                )
            )
        entry.append(
            E.memory_info(
                "{:d}".format(sum(process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids))) if act_pids else "",
                )
            )
        if "version_file" in entry.attrib:
            entry.attrib["version_ok"] = "0"
            try:
                _path = entry.attrib["version_file"].replace("%{INIT_BASE}", INIT_BASE).replace("%{NAME}", entry.attrib["name"].replace("-", "_"))
                if os.path.exists(_path):
                    _lines = file(_path, "r").read().split("\n")
                    _vers_lines = [_line for _line in _lines if _line.startswith("VERSION_STRING")]
                    if _vers_lines:
                        entry.attrib["version_ok"] = "1"
                        entry.attrib["version"] = _vers_lines[0].split("=", 1)[1].strip().replace('"', "").replace("'", "")
                    else:
                        entry.attrib["version"] = "no version lines found in '{}'".format(_path)
                else:
                    entry.attrib["version"] = "{} missing".format(_path)
            except:
                entry.attrib["version"] = "error getting version: {}".format(process_tools.get_except_info())
    return instance_xml


def get_default_ns():
    def_ns = argparse.Namespace(
        all=True, instance=[], system=[], server=[], node=[], runlevel=True, memory=True, database=True, pid=True, time=True, thread=True, no_database=False, version=True,
    )
    return def_ns


def show_xml(opt_ns, res_xml, iteration=0):
    # color strings (green / yellow / red / normal)
    col_str_dict = {
        0: "\033[1;32m",
        1: "\033[1;33m",
        2: "\033[1;31m",
        3: "\033[m\017"
    }
    rc_dict = {
        0: (0, "running"),
        1: (2, "error"),
        5: (1, "skipped"),
        6: (1, "not install"),
        7: (2, "dead")
    }
    rc_strs = {
        key: "{}{}{}".format(col_str_dict[wc], value, col_str_dict[3]) for key, (wc, value) in rc_dict.iteritems()
    }
    out_bl = logging_tools.new_form_list()
    types = ["node", "server", "system"]
    _list = sum([res_xml.xpath("instance[@checked='1' and @runs_on='{}']".format(_type)) for _type in types], [])
    for act_struct in _list:
        cur_line = [logging_tools.form_entry(act_struct.attrib["name"], header="Name")]
        cur_line.append(logging_tools.form_entry(act_struct.attrib["runs_on"], header="type"))
        cur_line.append(logging_tools.form_entry(act_struct.attrib.get("check_source", "N/A"), header="source"))
        if opt_ns.time or opt_ns.thread:
            s_info = act_struct.find("state_info")
            if "num_started" not in s_info.attrib:
                cur_line.append(logging_tools.form_entry(s_info.text))
            else:
                num_started, num_found, num_diff, pid_time, any_ok = (
                    int(s_info.get("num_started")),
                    int(s_info.get("num_found")),
                    int(s_info.get("num_diff")),
                    int(s_info.get("pid_time", "0")),
                    True if int(act_struct.attrib["any_threads_ok"]) else False
                )
                # print etree.tostring(act_struct, pretty_print=True)
                if any_ok:
                    ret_str = "{} running".format(logging_tools.get_plural("thread", num_found))
                else:
                    diffs_found = s_info.findall("diff_info")
                    if diffs_found:
                        diff_str = ", [diff: {}]".format(
                            ", ".join(
                                [
                                    "{:d}: {:d}".format(int(cur_diff.attrib["pid"]), int(cur_diff.attrib["diff"])) for cur_diff in diffs_found
                                ]
                            )
                        )
                    else:
                        diff_str = ""
                    if num_diff < 0:
                        ret_str = "{} {} missing{}".format(
                            logging_tools.get_plural("thread", -num_diff),
                            num_diff == 1 and "is" or "are",
                            diff_str,
                            )
                    elif num_diff > 0:
                        ret_str = "{} too much{}".format(
                            logging_tools.get_plural("thread", num_diff),
                            diff_str,
                        )
                    else:
                        ret_str = "the thread is running" if num_started == 1 else "all {:d} threads running".format(num_started)
                if opt_ns.time:
                    if pid_time:
                        diff_time = max(0, time.mktime(time.localtime()) - pid_time)
                        diff_days = int(diff_time / (3600 * 24))
                        diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                        diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                        diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                        ret_str += ", stable since {}{:02d}:{:02d}:{:02d} ({})".format(
                            diff_days and "{}, ".format(logging_tools.get_plural("day", diff_days)) or "",
                            diff_hours,
                            diff_mins,
                            diff_secs,
                            time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                    else:
                        ret_str += ", no pid found"
                cur_line.append(logging_tools.form_entry(ret_str, header="Thread and time info" if opt_ns.time else "Thread info"))
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
            cur_line.append(logging_tools.form_entry(act_struct.findtext("sql_info"), header="DB info"))
        if opt_ns.runlevel:
            if act_struct.find("runlevels") is not None:
                rlevs = act_struct.xpath("runlevels/runlevel/text()", smart_strings=False)
                if len(rlevs):
                    cur_line.append(
                        logging_tools.form_entry(
                            "{} {}".format(
                                logging_tools.get_plural("level", rlevs, 0),
                                ", ".join([r_lev for r_lev in rlevs])
                            ),
                            header="runlevels"
                        )
                    )
                else:
                    cur_line.append(logging_tools.form_entry("no runlevels", header="runlevels"))
            else:
                cur_line.append(logging_tools.form_entry("<no runlevel info>", header="runlevels"))
        if opt_ns.memory:
            cur_mem = act_struct.find("memory_info").text
            if cur_mem.isdigit():
                mem_str = process_tools.beautify_mem_info(int(cur_mem))
            else:
                # no pids hence no memory info
                mem_str = "no pids"
            cur_line.append(logging_tools.form_entry_right(mem_str, header="Memory"))
        if opt_ns.version:
            if "version" in act_struct.attrib:
                _version = act_struct.attrib["version"]
            else:
                _version = ""
            cur_line.append(logging_tools.form_entry_right(_version, header="Version"))
        cur_state = int(act_struct.find("state_info").get("state", "1"))
        cur_line.append(logging_tools.form_entry(rc_strs[cur_state], header="status"))
        if not opt_ns.failed or (opt_ns.failed and cur_state in [1, 7]):
            out_bl.append(cur_line)
    print(datetime.datetime.now().strftime("%a, %d. %b %Y %d %H:%M:%S"))
    # _lines = unicode(out_bl).split("\n")
    # if iteration and len(_lines) > 2:
    #    print "\n".join(_lines[2:])
    # else:
    #    print "\n".join(_lines)
    print(unicode(out_bl))


def do_action_xml(opt_ns, res_xml, mode):
    structs = res_xml.findall("instance[@checked='1' and @startstop='1']")
    if not opt_ns.quiet:
        print(
            "{}ing {}: {}".format(
                mode,
                logging_tools.get_plural("instance", len(structs)),
                ", ".join([cur_el.attrib["name"] for cur_el in structs])
            )
        )
    for cur_el in structs:
        cur_name = cur_el.attrib["name"]
        init_script = os.path.join("/", "etc", "init.d", cur_el.get("init_script_name", cur_name))
        if os.path.exists(init_script):
            op_mode = "start" if mode == "start" else ("force-{}".format(mode) if opt_ns.force and int(cur_el.get("has_force_stop", "0")) else mode)
            cur_com = "{} {}".format(
                init_script, op_mode
            )
            if not opt_ns.quiet:
                print("calling {}".format(cur_com))
            _ret_val = subprocess.call(cur_com, shell=True)
        else:
            if not opt_ns.quiet:
                print(
                    "init-script '{}' for {} does not exist".format(
                        init_script,
                        cur_name,
                    )
                )


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview (%(default)s)")
    my_parser.add_argument("-T", dest="time", action="store_true", default=False, help="full time info (implies -t,  %(default)s)")
    my_parser.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info (%(default)s)")
    my_parser.add_argument("-d", dest="database", action="store_true", default=False, help="show database info (%(default)s)")
    my_parser.add_argument("-r", dest="runlevel", action="store_true", default=False, help="runlevel info (%(default)s)")
    my_parser.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption (%(default)s)")
    my_parser.add_argument("-a", dest="almost_all", action="store_true", default=False, help="almost all of the above, except time and DB info (%(default)s)")
    my_parser.add_argument("-A", dest="all", action="store_true", default=False, help="all of the above (%(default)s)")
    my_parser.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
    my_parser.add_argument("-v", dest="version", default=False, action="store_true", help="show version info [%(default)s]")
    my_parser.add_argument("--instance", type=str, nargs="+", default=[], help="general instance names (%(default)s)")
    my_parser.add_argument("--node", type=str, nargs="+", default=[], help="node entity names (%(default)s)")
    my_parser.add_argument("--server", type=str, nargs="+", default=[], help="server entity names (%(default)s)")
    my_parser.add_argument("--system", type=str, nargs="+", default=[], help="system entity names (%(default)s)")
    my_parser.add_argument("--mode", type=str, default="show", choices=["show", "stop", "start", "restart"], help="operation mode [%(default)s]")
    my_parser.add_argument("--force", default=False, action="store_true", help="call force-stop if available [%(default)s]")
    my_parser.add_argument("--failed", default=False, action="store_true", help="show only instances in failed state [%(default)s]")
    my_parser.add_argument("--every", default=0, type=int, help="check again every N seconds, only available for show [%(default)s]")
    my_parser.add_argument("--no-database", default=False, action="store_true", help="disable use of database [%(default)s]")
    opt_ns = my_parser.parse_args()
    if opt_ns.all or opt_ns.almost_all:
        opt_ns.thread = True
        opt_ns.pid = True
        opt_ns.runlevel = True
        opt_ns.memory = True
        opt_ns.version = True
    if opt_ns.all:
        opt_ns.time = True
        opt_ns.database = True
    if os.getuid():
        print("Not running as root, information may be incomplete, disabling display of memory")
        opt_ns.memory = False
    ret_xml = check_system(opt_ns)
    if not len(ret_xml.findall("instance[@checked='1']")):
        print("Nothing to do")
        sys.exit(1)

    if opt_ns.mode == "show":
        _iter = 0
        while True:
            try:
                show_xml(opt_ns, ret_xml, _iter)
                if opt_ns.every:
                    time.sleep(opt_ns.every)
                    ret_xml = check_system(opt_ns)
                    _iter += 1
                else:
                    break
            except KeyboardInterrupt:
                print("exiting...")
                break
    elif opt_ns.mode in ["start", "stop", "restart"]:
        do_action_xml(opt_ns, ret_xml, opt_ns.mode)

if __name__ == "__main__":
    main()
