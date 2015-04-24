#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2007,2008 Andreas Lang-Nevyjel, init.at
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
""" commandline client to check status of jobs """

import sys
import optparse
import os
import os.path
from initat.tools import logging_tools
from initat.tools import net_tools
from initat.tools import server_command
from initat.tools import process_tools
import re
import pprint
sys.path.append("/usr/local/sbin")
import hm_classes
import re

MEAN_HOST_NAME = "mean"

def get_sge_server():
    if os.environ.has_key("SGE_SERVER"):
        sge_server = os.environ["SGE_SERVER"]
    elif os.path.isfile("/etc/sge_server"):
        try:
            sge_server = file("/etc/sge_server", "r").read().split("\n")[0].strip()
        except:
            sge_server = "localhost"
    else:
        sge_server = "localhost"
    return sge_server

def connect(server, port, com_str, timeout=30.0):
    errnum, data = net_tools.single_connection(host=server,
                                               port=port,
                                               command=com_str,
                                               timeout=timeout).iterate()
    if errnum:
        ret_str = "error Socket error: %s (%d)" % (data, errnum)
    else:
        try:
            j_info = job_info(data)
        except:
            ret_str = "error interpreting server-reply (%s): '%s'" % (process_tools.get_except_info(),
                                                                      data[0:100])
        else:
            ret_str = j_info
    return ret_str

class host_info(object):
    def __init__(self, in_data):
        self.__vector, self.__proc_dict = ({}, {})
        self.__mvector_ok, self.__proc_dict_ok = (False, False)
        if type(in_data) == type(""):
            print "Error for host: %s" % (in_data)
        else:
            for key, value in in_data.iteritems():
                if key == "get_mvector":
                    if type(value) != type(""):
                        self.__mvector_ok = True
                        self.__vector = dict([(s_key, s_value) for s_key, s_value in value[1]])
                    else:
                        self.__mvector_error = value
                elif key == "proclist":
                    if type(value) == type(""):
                        self.__proc_dict_error = value
                    else:
                        self.__proc_dict_ok = True
                        self.__proc_dict = value
                else:
                    print "Unknown key in host_info object: '%s'" % (key)
    def mvector_ok(self):
        return self.__mvector_ok
    def get_mvector_error(self):
        return self.__mvector_error
    def __getitem__(self, key):
        return self.__vector[key]
    def has_key(self, key):
        return self.__vector.has_key(key)
    def keys(self):
        return self.__vector.keys()
    def get_core_info(self, job_id, options, core_num=None):
        name_re = re.compile(options.prog_match)
        used_cores = {}
        if self.__proc_dict_ok:
            shep_pid = 0
            for pid, p_stuff in self.__proc_dict.iteritems():
                cmd_line = p_stuff.get("cmdline", [])
                if cmd_line and cmd_line[0] == "sge_shepherd-%s" % (job_id):
                    # find shepherd
                    shep_pid = pid
                    break
            if shep_pid:
                # find childs
                act_pids = [shep_pid]
                changed = True
                while changed:
                    changed = False
                    for pid, p_stuff in self.__proc_dict.iteritems():
                        if pid not in act_pids and p_stuff.get("ppid", 0) in act_pids:
                            act_pids.append(pid)
                            changed = True
                for p_stuff in [self.__proc_dict[pid] for pid in act_pids]:
                    if p_stuff.has_key("last_cpu"):
                        if name_re.match(p_stuff["name"]):
                            stat_info = p_stuff.get("stat_info", {})
                            # user time in seconds
                            user_time = stat_info.get("utime", 9999999) / 1000.
                            p_stuff["user_time"] = user_time
                            if user_time > options.user_threshold:
                                used_cores.setdefault(p_stuff["last_cpu"], []).append(p_stuff)
        if used_cores:
            if core_num is not None:
                c_info = ",".join(sorted([", ".join(["%s [%d, rt %s]" % (os.path.basename(p_stuff["cmdline"][0]),
                                                                         p_stuff["pid"],
                                                                         logging_tools.get_diff_time_str(p_stuff["user_time"])) for p_stuff in used_cores[core_num]])])) or "---"
            else:
                c_info = ",".join(sorted(["%d (%s)" % (core,
                                                       ", ".join(["%s [%d, %d]" % (p_stuff["name"],
                                                                                   p_stuff["pid"],
                                                                                   p_stuff["user_time"]) for p_stuff in used_cores[core]])) for core in sorted(used_cores.keys())]))
        else:
            c_info = "---"
        return used_cores, c_info

class job_info(object):
    def __init__(self, net_data):
        self.__srv_reply = server_command.server_reply(net_data)
        self.__job_dict, host_dict = (self.__srv_reply.get_option_dict()["jobs"],
                                      self.__srv_reply.get_option_dict()["hosts"])
        self.__host_dict = {}
        for h_name, h_stuff in host_dict.iteritems():
            self.__host_dict[h_name] = host_info(h_stuff["result"])
        self.__option_dict = {}
    def set_options(self, options):
        self.__options = options
    def show_info(self):
        ret_state, ret_str = self.__srv_reply.get_state_and_result()
        if ret_state:
            print " e Got non-ok result from sge-server"
            print " e %d %s" % (ret_state, ret_str)
        else:
            print "Got from server: %s" % (ret_str)
            self._show_job_details()
    def _show_job_details(self):
        j_ids = sorted(self.__job_dict.keys())
        for j_id in j_ids:
            j_stuff = self.__job_dict[j_id]
            print "\nId %s: %s%s" % (j_id,
                                      j_stuff["result"],
                                      " (%s):" % (", ".join(sorted(j_stuff["hosts"]))) if j_stuff["hosts"] else "")
            if j_stuff["hosts"]:
                out_keys = self._get_output_keys(j_id, j_stuff)
                ov_keys = [(e_type, e_header) for e_type, e_header in out_keys if e_type != "core"]
                if ov_keys:
                    h_out = logging_tools.new_form_list()
                    for h_name in sorted(j_stuff["hosts"]):
                        h_out.append(self._get_host_detail(j_id, h_name, ov_keys))
                    print h_out
                if ("core", "cores") in out_keys:
                    # get core keys
                    core_keys = set()
                    for h_name in sorted(j_stuff["hosts"]):
                        core_keys.update(self._get_core_keys(j_id, h_name))
                    h_out = logging_tools.new_form_list()
                    for h_name in sorted(j_stuff["hosts"]):
                        for add_line in self._get_host_core_detail(j_id, core_keys, h_name):
                            h_out.append(add_line)
                    print h_out
    def _get_output_keys(self, j_id, j_stuff):
        h_list = j_stuff["hosts"]
        out_keys = []
        for h_name in h_list:
            h_stuff = self.__host_dict[h_name]
            if self.__options.load:
                out_keys.extend([("load", key) for key in h_stuff.keys() if key.startswith("load.")])
            if self.__options.net:
                out_keys.extend([("net", key) for key in h_stuff.keys() if re.match("^net\.(eth|myr|ib).*\.[tr]x$", key)])
            if self.__options.mem:
                out_keys.extend([("mem", key) for key in h_stuff.keys() if re.match("^mem\..*$", key)])
            if self.__options.core:
                out_keys.extend([("core", "cores")])
        return sorted(list(set(out_keys)))
    def _format_load(self, in_val):
        return "%.2f" % (in_val)
    def _format_net(self, in_val):
        t_array = ["", "k", "M", "G", "T"]
        act_pfix = t_array.pop(0)
        while in_val > 1024.:
            act_pfix = t_array.pop(0)
            in_val /= 1024.
        return "%.2f %sB/s" % (in_val, act_pfix)
    def _format_mem(self, in_val):
        t_array = ["", "k", "M", "G", "T"]
        act_pfix = t_array.pop(0)
        while in_val > 1024.:
            act_pfix = t_array.pop(0)
            in_val /= 1024.
        return "%.2f %sB" % (in_val, act_pfix)
    def _format_vms(self, in_val):
        return "%.1f %%" % (in_val)
    def _get_host_detail(self, j_id, h_name, out_keys):
        h_dict = self.__host_dict[h_name]
        act_line = [logging_tools.form_entry(h_name, header="host")]
        if not h_dict.mvector_ok():
            act_line.append(h_dict.get_mvector_error(), header="info")
        else:
            for out_type, key in out_keys:
                if h_dict.has_key(key):
                    act_line.append(logging_tools.form_entry_right({"load" : self._format_load,
                                                                    "net"  : self._format_net,
                                                                    "mem"  : self._format_mem}[out_type](h_dict[key].value), header=key))
                else:
                    act_line.append(logging_tools.form_entry_right("---"))
            #if self.__option_dict["load"]:
            #    act_line.extend(logging_tools.form_entry_right(h_str(type(h_dict["result"][1]))))
            #print self.__option_dict
        return act_line
    def _get_core_keys(self, j_id, h_name):
        # returns vms keys where value is above vms_threshold
        h_dict = self.__host_dict[h_name]
        act_keys = set()
        if h_dict.mvector_ok():
            used_cores, c_info = h_dict.get_core_info(j_id, self.__options)
            core_list = set(used_cores.keys())
            for core_num in sorted(core_list):
                act_keys.update([key.split(".")[1] for key in h_dict.keys() if key.startswith("vms") and key.endswith(".p%d" % (core_num)) and h_dict[key].value > self.__options.vms_threshold])
        return act_keys
    def _get_host_core_detail(self, j_id, core_keys, h_name):
        h_dict = self.__host_dict[h_name]
        act_lines = []
        if not h_dict.mvector_ok():
            ret_lines = [[logging_tools.form_entry(h_name, header="host"),
                          logging_tools.form_entry(h_dict.get_mvector_error(), header="info")]]
        else:
            ret_lines = []
            used_cores, c_info = h_dict.get_core_info(j_id, self.__options)
            core_list = set(used_cores.keys())
            for core_num in sorted(core_list):
                act_line = [logging_tools.form_entry(h_name, header="host"),
                            logging_tools.form_entry(core_num, header="core"),
                            logging_tools.form_entry_right(h_dict.get_core_info(j_id, self.__options, core_num)[1], header="coreinfo")]
                act_keys = [key for key in h_dict.keys() if key.startswith("vms") and key.split(".")[1] in core_keys and key.endswith(".p%d" % (core_num))]
                for key in sorted(act_keys):
                    act_line.append(logging_tools.form_entry_right(self._format_vms(h_dict[key].value), header=key.split(".")[1]))
                ret_lines.append(act_line)
            #if self.__option_dict["load"]:
            #    act_line.extend(logging_tools.form_entry_right(h_str(type(h_dict["result"][1]))))
            #print self.__option_dict
        return ret_lines

class my_opt_parser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        self.add_option("-l", dest="load", help="show load info [%default]", action="store_true", default=False)
        self.add_option("-n", dest="net", help="show net info [%default]", action="store_true", default=False)
        self.add_option("-m", dest="mem", help="show memory info [%default]", action="store_true", default=False)
        self.add_option("-c", dest="core", help="show core info [%default]", action="store_true", default=False)
        self.add_option("-T", dest="timeout", type="int", help="set timeout in seconds [%default]", default=15)
        self.add_option("--vms-th", dest="vms_threshold", type="float", help="set minimal threshold for vms-display [%default]", default=0.5)
        self.add_option("--runtime-th", dest="user_threshold", type="float", help="set minimal usertime used in seconds for processes [%default]", default=60)
        self.add_option("--prog", dest="prog_match", type="str", help="regular expression for matching program names [%default]", type="str", default=".*")
    def parse(self):
        return self.parse_args()

def main():
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"), ("SGE_CELL", "/etc/sge_cell")]:
        if not os.environ.has_key(v_name):
            if os.path.isfile(v_src):
                os.environ[v_name] = file(v_src, "r").read().strip()
            else:
                print "error Cannot assign environment-variable '%s', exiting..." % (v_name)
                sys.exit(1)
    options, args = my_opt_parser().parse()
    if not args:
        print "Need some job-ids to check"
        sys.exit(2)
    jobs = sum([arg.split(",") for arg in args], [])
    print "Checking the status of the following jobs: %s" % (", ".join(jobs))
    j_info = connect(get_sge_server(),
                     8009,
                     server_command.server_command(command = "check_job",
                                                   option_dict={"job" : jobs}),
                     options.timeout)
    exit_state = -1
    if type(j_info) == type(""):
        print " e %s" % (j_info)
    else:
        j_info.set_options(options)
        j_info.show_info()
        exit_stat = 0
    sys.exit(exit_state)

if __name__ == "__main__":
    main()
