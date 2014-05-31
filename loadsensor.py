#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2010,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" python interface to emulate a loadsensor for SGE """

from initat.host_monitoring import hm_classes
import commands
import license_tool # @UnresolvedImport
import logging_tools
import os
import process_tools
import re
import server_command
import sge_license_tools
import stat
import sys
import time
import zmq

class error(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class term_error(error):
    def __init__(self):
        pass

class alarm_error(error):
    def __init__(self):
        pass

class stop_error(error):
    def __init__(self):
        pass

class int_error(error):
    def __init__(self):
        pass

def raw_read(fd):
    ret_str = ""
    while True:
        in_byte = os.read(fd, 1)
        if len(in_byte):
            if ord(in_byte) == 10:
                break
            ret_str = "{}{}".format(ret_str, in_byte)
    return ret_str

def parse_actual_license_usage(log_template, actual_licenses, act_conf, lc_dict):
    configured_lics = []
    if not os.path.isdir(act_conf["LM_UTIL_PATH"]):
        log_template.error("Error: LM_UTIL_PATH '%s' is not directory" % (act_conf["LM_UTIL_PATH"]))
    else:
        # build different license-server calls
        all_server_addrs = dict([("%d@%s" % (act_lic.get_port(), act_lic.get_host()), True) for act_lic in actual_licenses.values() if act_lic.get_license_type() == "simple"]).keys()
        # print "asa:", all_server_addrs
        q_s_time = time.time()
        for server_addr in all_server_addrs:
            if not server_addr in lc_dict:
                lc_dict[server_addr] = license_tool.license_check(
                    lmutil_path=os.path.join(
                        act_conf["LM_UTIL_PATH"],
                        act_conf["LM_UTIL_COMMAND"]),
                    port=int(server_addr.split("@")[0]),
                    server=server_addr.split("@")[1],
                    log_com=log_template.log)
            srv_result = lc_dict[server_addr].check()
        q_e_time = time.time()
        log_template.info(
            "%s to query, took %s: %s" % (
                logging_tools.get_plural("license server", len(all_server_addrs)),
                logging_tools.get_diff_time_str(q_e_time - q_s_time),
                ", ".join(all_server_addrs)))
        for cur_lic in srv_result.xpath(".//license[@name]", smart_strings=False):
            name = cur_lic.attrib["name"]
            act_lic = actual_licenses.get(name, None)
            if act_lic and act_lic.get_is_used():
                configured_lics.append(name)
                _total, used = (
                    int(cur_lic.attrib["issued"]),
                    int(cur_lic.attrib["used"]) - int(cur_lic.attrib.get("reserved", "0")))
                act_lic.clean_hosts()
                if act_lic.get_used_num() != used:
                    log_template.info(
                        "attribute %s: use_count changed from %d to %d" % (
                            act_lic.get_attribute(),
                            act_lic.get_used_num(),
                            used))
                    act_lic.set_used_num(int(used))
                    act_lic.set_changed()
    return configured_lics

def calculate_compound_licenses(log_template, actual_licenses, configured_lics):
    comp_keys = [key for key, value in actual_licenses.iteritems() if value.get_is_used() and value.get_license_type() == "compound"]
    for comp_key in sorted(comp_keys):
        configured_lics.append(comp_key)
        for log_line, log_level in actual_licenses[comp_key].handle_compound(actual_licenses):
            log_template.log(log_level, log_line)

def build_sge_report_lines(log_template, configured_lics, actual_lics):
    lines = ["start"]
    rep_dict = {"lics_in_use"   : [],
                "simple_lics"   : 0,
                "compound_lics" : 0}
    for configured_lic in configured_lics:
        act_lic = actual_lics[configured_lic]
        free_lics = act_lic.get_free_num()
        if act_lic.get_license_type() == "simple":
            rep_dict["simple_lics"] += 1
        else:
            rep_dict["compound_lics"] += 1
        if free_lics != act_lic.get_total_num():
            rep_dict["lics_in_use"].append(configured_lic)
        if act_lic.get_changed():
            log_template.info(
                "reporting %d free of %d for %s" % (free_lics,
                    act_lic.get_total_num(),
                    configured_lic))
        lines.append("global:%s:%d" % (configured_lic, free_lics))
    lines.append("end")
    return lines, rep_dict

def get_used(log_template, qstat_bin):
    act_dict = {}
    job_id_re = re.compile("\d+\.*\d*")
    act_com = "%s -ne -r" % (qstat_bin)
    c_stat, out = commands.getstatusoutput(act_com)
    if c_stat:
        log_template.error("Error calling %s (%d):" % (act_com, c_stat))
        for line in out.split("\n"):
            log_template.error(" - %s" % (line.rstrip()))
    else:
        act_job_mode = "?"
        for line_parts in [x.strip().split() for x in out.split("\n") if x.strip()]:
            job_id = line_parts[0]
            if job_id_re.match(job_id) and len(line_parts) >= 9:
                act_job_mode = line_parts[4]
            elif len(line_parts) >= 3:
                if ("%s %s" % (line_parts[0], line_parts[1])).lower() == "hard resources:":
                    res_name, res_value = line_parts[2].split("=")
                    if "r" in act_job_mode or "R" in act_job_mode or "t" in act_job_mode:
                        dict_name = "used"
                    else:
                        dict_name = "requested"
                    act_dict.setdefault(dict_name, {}).setdefault(res_name, 0)
                    try:
                        res_value = int(res_value)
                    except ValueError:
                        pass
                    else:
                        act_dict[dict_name][res_name] += res_value
    return act_dict

def write_ext_data(vector_socket, log_template, actual_licenses):
    drop_com = server_command.srv_command(command="set_vector")
    add_obj = drop_com.builder("values")
    cur_time = time.time()
    for lic_stuff in actual_licenses.itervalues():
        for cur_mve in lic_stuff.get_mvect_entries(hm_classes.mvect_entry):
            cur_mve.valid_until = cur_time + 120
            add_obj.append(cur_mve.build_xml(drop_com.builder))
    drop_com["vector_loadsensor"] = add_obj
    drop_com["vector_loadsensor"].attrib["type"] = "vector"
    send_str = unicode(drop_com)
    log_template.log("sending %d bytes to vector_socket" % (len(send_str)))
    vector_socket.send_unicode(send_str)

def main():
    # change IO-descriptors
    zmq_context = zmq.Context()
    log_template = logging_tools.get_logger(
        "loadsensor",
        "uds:/var/lib/logging-server/py_log",
        init_logger=True,
        zmq=True,
        context=zmq_context,
    )
    base_dir = "/etc/sysconfig/licenses"
    my_pid = os.getpid()
    log_template.info("starting for pid %d, base_dir is %s" % (my_pid, base_dir))
    if not os.environ.has_key("SGE_ROOT"):
        log_template.error("Error, no SGE_ROOT environment variable set")
        sys.exit(1)
    if not os.environ.has_key("SGE_CELL"):
        log_template.error("Error, no SGE_CELL environment variable set")
        sys.exit(1)
    sge_root, sge_cell = (os.environ["SGE_ROOT"],
                          os.environ["SGE_CELL"])
    arch_util = "%s/util/arch" % (sge_root)
    if not os.path.isfile(arch_util):
        log_template.error("No arch-utility found in %s/util" % (sge_root))
        sys.exit(1)
    sge_arch = commands.getoutput(arch_util)
    log_template.info("SGE_ROOT is %s, SGE_CELL is %s, SGE_ARCH is %s" % (sge_root, sge_cell, sge_arch))
    act_site = sge_license_tools.read_default_site_file(base_dir, sge_license_tools.ACT_SITE_NAME)
    if not act_site:
        log_template.error("Actual site not defined, exiting...")
        sys.exit(1)
    act_conf = sge_license_tools.DEFAULT_CONFIG
    sge_license_tools.parse_site_config_file(base_dir, act_site, act_conf)
    log_template.info("read config for actual site '%s'" % (act_site))
    for key, value in act_conf.iteritems():
        log_template.info(" - %-20s : %s" % (key, value))
    call_num = 0
    io_in_fd = sys.stdin.fileno()
    io_out_fd = sys.stdout.fileno()
    log_template.info("starting up, input handle is %d, output handle is %d" % (io_in_fd, io_out_fd))
    actual_licenses, lic_read_time = ([], time.time())
    # read node_grouping file
    ng_dict = sge_license_tools.read_ng_file(log_template)
    # license_check_dict
    lc_dict = {}
    # vector socket
    conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
    vector_socket = zmq_context.socket(zmq.PUSH)
    vector_socket.setsockopt(zmq.LINGER, 0)
    vector_socket.connect(conn_str)
    try:
        while True:
            in_lines = raw_read(io_in_fd)
            call_num += 1
            if in_lines == "quit":
                log_template.warning("call #%d, received '%s'" % (call_num, in_lines))
                break
            else:
                log_template.info("starting reporting load values (call #%d)" % (call_num))
                start_time = time.time()
                site_lic_file_name = sge_license_tools.get_site_license_file_name(base_dir, act_site)
                if os.path.isfile(site_lic_file_name):
                    file_time = os.stat(site_lic_file_name)[stat.ST_MTIME]
                    if not actual_licenses or file_time > lic_read_time:
                        log_template.info("reading license_file for site %s" % (act_site))
                        actual_licenses = sge_license_tools.parse_license_lines(sge_license_tools.read_site_license_file(base_dir, act_site), act_site, ng_dict=ng_dict)
                        lic_read_time = file_time
                        write_ext_ok = False
                    else:
                        write_ext_ok = True
                    configured_licenses = parse_actual_license_usage(log_template, actual_licenses, act_conf, lc_dict)
                    [cur_lic.handle_node_grouping() for cur_lic in actual_licenses.itervalues()]
                    calculate_compound_licenses(log_template, actual_licenses, configured_licenses)
                    sge_lines, rep_dict = build_sge_report_lines(log_template, configured_licenses, actual_licenses)
                    # report to SGE
                    print "\n".join(sge_lines)
                    if write_ext_ok:
                        write_ext_data(vector_socket, log_template, actual_licenses)
                    end_time = time.time()
                    log_template.info("%s defined, %d configured, %d in use%s, (%d simple, %d compound), took %s" % (
                        logging_tools.get_plural("license", len(actual_licenses.keys())),
                        len(configured_licenses),
                        len(rep_dict["lics_in_use"]),
                        rep_dict["lics_in_use"] and " (%s)" % (", ".join(rep_dict["lics_in_use"])) or "",
                        rep_dict["simple_lics"],
                        rep_dict["compound_lics"],
                        logging_tools.get_diff_time_str(end_time - start_time)))
                else:
                    log_template.warning("site_file for site %s not readable (base_dir is %s)" % (act_site, base_dir))
    except KeyboardInterrupt:
        log_template.warning("proc %d: got KeyboardInterrupt, exiting ..." % (my_pid))
    except term_error:
        log_template.warning("proc %d: got term-signal, exiting ..." % (my_pid))
    except stop_error:
        log_template.warning("proc %d: got stop-signal, exiting ..." % (my_pid))
    except int_error:
        log_template.warning("proc %d: got int-signal, exiting ..." % (my_pid))
    vector_socket.close()
    zmq_context.term()
    sys.exit(0)

if __name__ == "__main__":
    main()

