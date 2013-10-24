#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import argparse
import commands
import extra_server_tools
import logging_tools
import process_tools
import stat
import time
try:
    import config_tools
except:
    config_tools = None
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport

def check_threads(name, pids, any_ok):
    # print name, pids, any_ok
    ret_state = 7
    unique_pids = dict([(key, pids.count(key)) for key in set(pids)])
    pids_found = dict([(key, 0) for key in set(pids)])
    for pid in unique_pids.keys():
        stat_f = "/proc/%d/status" % (pid)
        if os.path.isfile(stat_f):
            stat_dict = dict([line.strip().lower().split(":", 1) for line in file(stat_f, "r").read().replace("\t", " ").split("\n") if line.count(":") and line.strip()])
            if "threads" in stat_dict:
                pids_found[pid] += int(stat_dict.get("threads", "1"))
            else:
                pids_found[pid] += 1
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
    <instance name="hoststatus" check_type="simple" pid_file_name="hoststatus_zmq" process_name="hoststatus_zmq" runs_on="node">
    </instance>
    <instance name="logging-server" runs_on="node" pid_file_name="logserver/logserver.pid">
    </instance>
    <instance name="meta-server" runs_on="node">
    </instance>
    <instance name="host-monitoring" runs_on="node" pid_file_name="collserver/collserver.pid">
    </instance>
    <instance name="package-client" runs_on="node">
    </instance>
    <instance name="gmond" runs_on="node">
    </instance>
    <instance name="logcheck-server">
        <config_names>
            <config_name>syslog_server</config_name>
        </config_names>
    </instance>
    <instance name="package-server" pid_file_name="package-server/package-server.pid">
        <config_names>
            <config_name>package_server</config_name>
        </config_names>
    </instance>
    <instance name="mother" pid_file_name="mother/mother.pid">
        <config_names>
            <config_name>mother_server</config_name>
        </config_names>
    </instance>
    <instance name="collectd" check_type="threads_by_pid_file" any_threads_ok="1">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="memcached" check_type="threads_by_pid_file" pid_file_name="memcached/memcached.pid" any_threads_ok="1">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="rrdcached" check_type="threads_by_pid_file" any_threads_ok="1">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="rrd-grapher" pid_file_name="rrd-grapher/rrd-grapher.pid">
        <config_names>
            <config_name>rrd_server</config_name>
        </config_names>
    </instance>
    <instance name="sge-server">
        <config_names>
            <config_name>sge_server</config_name>
        </config_names>
    </instance>
    <instance name="cluster-server">
        <config_names>
            <config_name>server</config_name>
        </config_names>
    </instance>
    <instance name="cluster-config-server" pid_file_name="cluster-config-server/cluster-config-server.pid">
        <config_names>
            <config_name>config_server</config_name>
        </config_names>
    </instance>
    <instance name="host-relay" pid_file_name="collrelay/collrelay.pid">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="snmp-relay" pid_file_name="snmp-relay/snmp-relay.pid">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="md-config-server" pid_file_name="md-config-server/md-config-server.pid">
        <config_names>
            <config_name>monitor_server</config_name>
            <config_name>monitor_master</config_name>
        </config_names>
    </instance>
    <instance name="cransys" pid_file_name="cransys-server.pid" init_script_name="cransys">
        <config_names>
            <config_name>cransys_server</config_name>
        </config_names>
    </instance>
</instances>
"""

def check_system(opt_ns):
    if not opt_ns.server and not opt_ns.node:
        set_default_nodes, set_default_servers = (True , True)
    else:
        set_default_nodes, set_default_servers = (False, False)
    if opt_ns.server == ["ALL"]:
        set_default_servers = True
    if opt_ns.node == ["ALL"]:
        set_default_nodes = True
    instance_xml = etree.fromstring(INSTANCE_XML)
    for cur_el in instance_xml.findall("instance"):
        name = cur_el.attrib["name"]
        for key, def_value in [
            ("runs_on", "server"),
            ("check_type", "threads_by_pid_file"),
            ("any_threads_ok", "0"),
            ("pid_file_name", "%s.pid" % (name)),
            ("init_script_name", name),
            ("checked", "0"),
            ("to_check", "1"),
            ("process_name", name),
            ]:
            if not key in cur_el.attrib:
                cur_el.attrib[key] = def_value
    if not set_default_servers:
        for server_el in instance_xml.xpath(".//*[@runs_on='server']"):
            if server_el.attrib["name"] not in opt_ns.server:
                server_el.attrib["to_check"] = "0"
    if not set_default_nodes:
        for node_el in instance_xml.xpath(".//*[@runs_on='node']"):
            if node_el.attrib["name"] not in opt_ns.node:
                node_el.attrib["to_check"] = "0"
    act_proc_dict = process_tools.get_proc_list()
    r_stat, out = commands.getstatusoutput("chkconfig --list")
    stat_dict = {}
    if not r_stat:
        for line in out.split("\n"):
            if line.count("0:") and line.count("1:"):
                key, level_list = line.split(None, 1)
                level_list = [int(level) for level, _flag in [entry.split(":") for entry in level_list.strip().split()] if _flag == "on" and level.isdigit()]
                stat_dict[key.lower()] = level_list
    if config_tools:
        dev_config = config_tools.device_with_config("%")
    else:
        dev_config = None
    for entry in instance_xml.findall("instance[@to_check='1']"):
        entry.attrib["checked"] = "1"
        if entry.attrib["init_script_name"] in stat_dict:
            entry.append(
                E.runlevels(
                    *[E.runlevel("%d" % (cur_rl)) for cur_rl in stat_dict.get(entry.attrib["init_script_name"], [])]
                )
            )
        # print name, check_struct
        # act_info_dict = {"name" : name}
        act_pids = []
        init_script_name = os.path.join("/etc/init.d/%s" % (entry.attrib["init_script_name"]))
        if entry.attrib["check_type"] == "simple":
            if os.path.isfile(init_script_name):
                running_procs = [pid for pid in act_proc_dict.values() if pid["name"] == entry.attrib["process_name"]]
                if running_procs:
                    act_state, act_str = (0, "running")
                    act_pids = [p_struct["pid"] for p_struct in running_procs]
                else:
                    act_state, act_str = (7, "not running")
            else:
                act_state, act_str = (5, "not installed")
            entry.append(E.state_info(act_str, state="%d" % (act_state)))
        elif entry.attrib["check_type"] == "threads_by_pid_file":
            pid_file_name = entry.attrib["pid_file_name"]
            if not pid_file_name.startswith("/"):
                pid_file_name = "/var/run/%s" % (pid_file_name)
            if os.path.isfile(pid_file_name):
                pid_time = os.stat(pid_file_name)[stat.ST_CTIME]
                act_pids = [int(line.strip()) for line in file(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
                act_state, num_started, num_found = check_threads(name, act_pids, True if int(entry.attrib["any_threads_ok"]) else False)
                entry.append(E.state_info(num_started="%d" % (num_started), num_found="%d" % (num_found), pid_time="%d" % (pid_time), state="%d" % (act_state)))
            else:
                if os.path.isfile(init_script_name):
                    entry.append(E.state_info("no threads", state="7"))
                else:
                    entry.append(E.state_info("not installed", state="5"))
        else:
            entry.append(E.state_info("unknown check_type '%s'" % (entry.attrib["check_type"]), state="1"))
        entry.append(
            E.pids(
                *[E.pid("%d" % (cur_pid), count="%d" % (act_pids.count(cur_pid))) for cur_pid in set(act_pids)]
                )
            )
        # act_info_dict["pids"] = dict([(key, act_pids.count(key)) for key in set(act_pids)])
        if entry.attrib["runs_on"] == "server":
            if dev_config is not None:
                srv_type_list = [_e.replace("-", "_") for _e in entry.xpath(".//config_names/config_name/text()")]
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
                    sql_info = "not set (%s)" % (", ".join(srv_type_list))
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
                E.sql_info("%s (%s)" % (
                    sql_info.server_info_str,
                    sql_info.config_name),
                )
            )
        entry.append(
            E.memory_info(
                "%d" % (sum(process_tools.get_mem_info(cur_pid) for cur_pid in set(act_pids))) if act_pids else "",
                )
            )
    return instance_xml

def get_default_ns():
    def_ns = argparse.Namespace(all=True, server=[], node=[], runlevel=True, memory=True, database=True, pid=True, time=True, thread=True)
    return def_ns

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview (%(default)s)")
    my_parser.add_argument("-T", dest="time", action="store_true", default=False, help="full time info (implies -t,  %(default)s)")
    my_parser.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info (%(default)s)")
    my_parser.add_argument("-d", dest="database", action="store_true", default=False, help="show database info (%(default)s)")
    my_parser.add_argument("-r", dest="runlevel", action="store_true", default=False, help="runlevel info (%(default)s)")
    my_parser.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption (%(default)s)")
    my_parser.add_argument("-a", dest="all", action="store_true", default=False, help="all of the above (%(default)s)")
    my_parser.add_argument("--node", type=str, nargs="+", default=[], help="node checks (%(default)s)")
    my_parser.add_argument("--server", type=str, nargs="+", default=[], help="server checks (%(default)s)")
    opt_ns = my_parser.parse_args()
    if os.getuid():
        print "Not running as UID, information may be incomplete"
    ret_xml = check_system(opt_ns)
    if not len(ret_xml.findall("instance[@checked='1']")):
        print "Nothing to check"
        sys.exit(1)
    # color strings (green / yellow / red / normal)
    col_str_dict = {0 : "\033[1;32m",
                    1 : "\033[1;33m",
                    2 : "\033[1;31m",
                    3 : "\033[m\017"}
    rc_dict = {0 : (0, "running"),
               1 : (2, "error"),
               5 : (1, "skipped"),
               6 : (1, "not install"),
               7 : (2, "dead")}
    rc_strs = dict([(key, "%s%s%s" % (col_str_dict[wc], value, col_str_dict[3]))
                    for key, (wc, value) in rc_dict.iteritems()])
    out_bl = logging_tools.form_list()
    head_l = ["Name"]
    if opt_ns.time or opt_ns.all:
        if opt_ns.thread or opt_ns.all:
            head_l.append("Thread and time info")
        else:
            head_l.append("Thread info")
    if opt_ns.pid or opt_ns.all:
        head_l.append("PIDs")
    if opt_ns.database or opt_ns.all:
        head_l.append("DB Info")
    if opt_ns.runlevel or opt_ns.all:
        head_l.append("runlevel(s)")
    if opt_ns.memory or opt_ns.all:
        head_l.append("Memory")
    head_l.append("state")
    out_bl.set_header_string(0, head_l)
    # import pprint
    # pprint.pprint(ret_dict)
    for act_struct in ret_xml.findall("instance[@checked='1']"):
        out_list = [act_struct.attrib["name"]]
        if opt_ns.time or opt_ns.all:
            s_info = act_struct.find("state_info")
            if "num_started" not in s_info.attrib:
                out_list.append(s_info.text)
            else:
                num_started, num_found, pid_time, any_ok = (
                    int(s_info.get("num_started")),
                    int(s_info.get("num_found")),
                    int(s_info.get("pid_time")),
                    True if int(act_struct.attrib["any_threads_ok"]) else False)
                if any_ok:
                    ret_str = "%s running" % (logging_tools.get_plural("thread", num_found))
                else:
                    num_miss = num_started - num_found
                    if num_miss > 0:
                        ret_str = "%s %s missing" % (
                            logging_tools.get_plural("thread", num_miss),
                            num_miss == 1 and "is" or "are")
                    elif num_miss < 0:
                        ret_str = "%s too much" % (
                            logging_tools.get_plural("thread", -num_miss))
                    else:
                        ret_str = "the thread is running" if num_started == 1 else "all %d threads running" % (num_started)
                if opt_ns.thread or opt_ns.all:
                    diff_time = max(0, time.mktime(time.localtime()) - pid_time)
                    diff_days = int(diff_time / (3600 * 24))
                    diff_hours = int((diff_time - 3600 * 24 * diff_days) / 3600)
                    diff_mins = int((diff_time - 3600 * (24 * diff_days + diff_hours)) / 60)
                    diff_secs = int(diff_time - 60 * (60 * (24 * diff_days + diff_hours) + diff_mins))
                    ret_str += ", stable since %s%02d:%02d:%02d (%s)" % (
                        diff_days and "%s, " % (logging_tools.get_plural("day", diff_days)) or "",
                        diff_hours, diff_mins, diff_secs,
                        time.strftime("%a, %d. %b %Y, %H:%M:%S", time.localtime(pid_time)))
                out_list.append(ret_str)
        if opt_ns.pid or opt_ns.all:
            pid_dict = {}
            for cur_pid in act_struct.findall(".//pids/pid"):
                pid_dict[int(cur_pid.text)] = int(cur_pid.get("count", "1"))
            if pid_dict:
                p_list = sorted(pid_dict.keys())
                if max(pid_dict.values()) == 1:
                    out_list.append(logging_tools.compress_num_list(p_list))
                else:
                    out_list.append(",".join(["%d%s" % (
                        key,
                        " (%d)" % (pid_dict[key]) if pid_dict[key] > 1 else "") for key in p_list]))
            else:
                out_list.append("no PIDs")
        if opt_ns.database or opt_ns.all:
            out_list.append(act_struct.findtext("sql_info"))
        if opt_ns.runlevel or opt_ns.all:
            if act_struct.find("runlevels") is not None:
                rlevs = act_struct.xpath("runlevels/runlevel/text()")
                if len(rlevs):
                    out_list.append("%s %s" % (
                        logging_tools.get_plural("level", rlevs, 0),
                        ", ".join([r_lev for r_lev in rlevs])))
                else:
                    out_list.append("no runlevels")
            else:
                out_list.append("<no runlevel info>")
        if opt_ns.memory or opt_ns.all:
            cur_mem = act_struct.find("memory_info").text
            if cur_mem.isdigit():
                mem_str = process_tools.beautify_mem_info(int(cur_mem))
            else:
                mem_str = "no pids"
            out_list.append(mem_str)
        out_list.append(rc_strs[int(act_struct.find("state_info").get("state", "1"))])
        out_bl.add_line(out_list)
    print out_bl

if __name__ == "__main__":
    main()

