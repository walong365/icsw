#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel, init.at
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
""" tools for the SGE """

import commands
import sys
import re
import time
import os.path
import datetime
import pprint
import logging_tools
import server_command
import process_tools
import zmq
import copy
from lxml import etree
from lxml.builder import E

def compress_list(ql, queues = None):
    # node prefix, postfix, start_string, end_string
    # not exactly the same as the version in logging_tools
    def add_p(np, ap, s_str, e_str):
        if s_str == e_str:
            return "%s%s%s" % (np, s_str, ap)
        elif int(s_str) + 1 == int(e_str):
            return "%s%s%s/%s%s" % (np, s_str, ap, e_str, ap)
        else:
            return "%s%s%s-%s%s" % (np, s_str, ap, e_str, ap)
    if not queues or queues == "-":
        q_list = []
    else:
        q_list = [x.strip() for x in queues.split(",")]
    pf_re = re.compile("^(?P<pef>\D+)(?P<num>\d*)(?P<pof>.*)$")
    pf_q_re = re.compile("^(?P<pef>.+@\D+)(?P<num>\d*)(?P<pof>.*)$")
    ql.sort()
    nc_dict = {}
    for q_name in ql:
        if q_name.count("@"):
            pf_m = pf_q_re.match(q_name)
        else:
            pf_m = pf_re.match(q_name)
        pef = pf_m.group("pef")
        if len(q_list) == 1 and pef.startswith("%s@" % (q_list[0])):
            pef = pef[len(q_list[0])+1:]
        idx = pf_m.group("num")
        pof = pf_m.group("pof").split(".")[0]
        if idx:
            i_idx = int(idx)
        else:
            i_idx = 0
        nc_dict.setdefault(pef, {}).setdefault(pof, {})[i_idx] = idx
    nc_a = []
    for pef in nc_dict.keys():
        for pof, act_l in nc_dict[pef].iteritems():
            s_idx = None
            for e_idx in sorted(act_l.keys()):
                e_num = act_l[e_idx]
                if s_idx is None:
                    s_idx, s_num = (e_idx, e_num)
                    l_num, l_idx = (s_num, s_idx)
                else:
                    if e_idx == l_idx+1:
                        pass
                    else:
                        nc_a.append(add_p(pef, pof, s_num, l_num))
                        s_num, s_idx = (e_num, e_idx)
                    l_num, l_idx = (e_num, e_idx)
            if pef:
                nc_a.append(add_p(pef, pof, s_num, l_num))
    return ",".join(nc_a)

def str_to_sec(in_str):
    if in_str == "---":
        sec = in_str
    else:
        is_f = [int(x) for x in in_str.split()[0].split(":")]
        sec, mult = (0, 0)
        while len(is_f):
            sec = sec * mult + is_f.pop(0)
            if len(is_f) > 2:
                mult = 24
            else:
                mult = 60
    return sec

def sec_to_str(in_sec):
    if in_sec == "---":
        out_f = "---"
    else:
        if in_sec >= 0:
            diff_d = int(in_sec / (3600 * 24))
            dt = in_sec - 3600 * 24 * diff_d
            diff_h = int(dt / 3600)
            dt -= 3600 * diff_h
            diff_m = int(dt / 60)
            dt -= diff_m * 60
            #if diff_d:
            out_f = "%s%02d:%02d:%02d" % (diff_d and "%2d:" % (diff_d) or "", diff_h, diff_m, dt)
            #else:
            #    out_f = "%2d:%02d:%02d" % (diff_h, diff_m, dt)
        else:
            out_f = "????"
    return out_f

class sge_info(object):
    def __init__(self, **kwargs):
        """ arguments :
        verbose            : enables verbose messages
        sge_dict           : env_dict for accessing the SGE direct
        log_command        : how to handle log events (defaults to syslog)
        is_active          : flag, if set to false no direct calls to the SGE will be made
        thread_safe        : flag, if set locks update calls againts concurrent threads
        run_initial_update : flag, if set to false no initial update_call will be made
        init_dicts         : default values for the various dicts (for webfrontend)
        update_pref        : dict where the update preferences are stored (direct, server)
        ignore_dicts       : dicts to ignore
        server             : name of server to connect, defaults to localhost
        """
        self.__verbose = kwargs.get("verbose", 0)
        self.__sge_dict = kwargs.get("sge_dict", {})
        self.__log_com = kwargs.get("log_command", kwargs.get("log_com", None))
        # active: has sge_dict and can make calls to the system
        self.__is_active = kwargs.get("is_active", True)
        self.__server = kwargs.get("server", "localhost")
        # key : (relevance, call)
        setup_dict = {"hostgroup" : (0, self._check_hostgroup_dict),
                      "queueconf" : (1, self._check_queueconf_dict),
                      "complexes" : (2, self._check_complexes_dict),
                      "qhost"     : (3, self._check_qhost_dict),
                      "qstat"     : (4, self._check_qstat_dict)}
        self.__valid_dicts = [v_key for bla, v_key in sorted([(rel, key) for key, (rel, s_call) in setup_dict.iteritems()]) if v_key not in kwargs.get("ignore_dicts", [])]
        self.__update_call_dict = dict([(key, s_call) for key, (rel, s_call) in setup_dict.iteritems()])
        self.__update_pref_dict = dict([(key, kwargs.get("update_pref", {}).get(key, ["direct", "server"])) for key in self.__valid_dicts])
        self.__timeout_dicts = dict([(key, {"hostgroup" : 300,
                                            "qstat"     : 2}.get(key, 120)) for key in self.__valid_dicts])
        if self.__is_active:
            self._sanitize_sge_dict()
        self._init_update(kwargs.get("init_dicts", {}))
        if kwargs.get("run_initial_update", True) and self.__is_active:
            self.update()
    def __del__(self):
        pass
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[si] %s" % (what), log_level)
        else:
            logging_tools.my_syslog("[si] %s" % (what), log_level)
    def __getitem__(self, key):
        #return self.__act_dicts[key]
        #print etree.tostring(self.__tree, pretty_print=True)
        return self.__tree.find(key)
    def get_tree(self):
        return self.__tree
    def get(self, key, def_value):
        return self.__act_dicts.get(key, def_value)
    def get_run_time(self, cur_time):
        # returns time running
        run_time = abs(datetime.datetime.now() - cur_time)
        days = run_time.days
        secs = run_time.seconds
        return sec_to_str(24 * 3600 * days + secs)
    def get_left_time(self, start_time, h_rt):
        if h_rt:
            run_time = abs(datetime.datetime.now() - start_time)
            left_time = abs(run_time - datetime.timedelta(0, int(h_rt)))
            return sec_to_str(left_time.days * 24 * 3600 + left_time.seconds)
        else:
            return "???"
    def get_h_rt_time(self, h_rt):
        if h_rt:
            h_rt = datetime.timedelta(0, int(h_rt))
            return sec_to_str(h_rt.days * 24 * 3600 + h_rt.seconds)
        else:
            return "???"
    def _init_update(self, start_dict):
        self.__tree = E.rms_info()
        for key in self.__valid_dicts:
            self.__tree.append(getattr(E, key)())
    def get_updated_dict(self, dict_name, **kwargs):
        if self._check_for_update(dict_name):
            self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
        return self.__act_dicts[dict_name]
    def update(self, **kwargs):
        upd_dicts = kwargs.get("update_list", self.__valid_dicts)
        # determine which dicts to update
        dicts_to_update = [dict_name for dict_name in upd_dicts if self._check_for_update(dict_name, kwargs.get("force_update", False))]
        #print "to update: ", dicts_to_update
        server_update = [dict_name for dict_name in dicts_to_update if (self.__update_pref_dict[dict_name] + ["not set"])[0] == "server"]
        if server_update:
            srv_name = self.__server
            s_time = time.time()
            # try server_update
            # new fancy 0MQ code
            zmq_context = zmq.Context(1)
            client = zmq_context.socket(zmq.DEALER)
            client.setsockopt(zmq.IDENTITY, "sge_tools:%d" % (os.getpid()))
            client.setsockopt(zmq.LINGER, 100)
            client.connect("tcp://%s:8009" % (srv_name))
            srv_com = server_command.srv_command(command="get_config")
            my_poller = zmq.Poller()
            my_poller.register(client, zmq.POLLIN)
            client.send_unicode(unicode(srv_com))
            timeout_secs = kwargs.get("timeout", 5)
            poll_result = my_poller.poll(timeout=timeout_secs * 1000)
            if poll_result:
                recv = client.recv_unicode()
            else:
                print "timeout after %d seconds" % (timeout_secs)
                recv = None
            client.close()
            zmq_context.term()
            try:
                srv_reply = server_command.srv_command(source=recv)
            except:
                pass
            else:
                if "sge" in srv_reply:
                    self.__tree = srv_reply["sge"][0]
                    dicts_to_update = []
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (server %s) took %s" % (", ".join(server_update),
                                                     srv_name,
                                                     logging_tools.get_diff_time_str(e_time - s_time)))
        for dict_name in dicts_to_update:
            s_time = time.time()
            new_el = getattr(E, dict_name)(last_update="%d" % (time.time()))
            self.__tree.append(new_el)
            new_el.append(self.__update_call_dict[dict_name]())
            #self.__act_dicts[dict_name] = self.__update_call_dict[dict_name]()
            e_time = time.time()
            if self.__verbose > 0:
                self.log("%s (direct) took %s" % (dict_name,
                                                  logging_tools.get_diff_time_str(e_time - s_time)))
    def _sanitize_sge_dict(self):
        if not self.__sge_dict.has_key("SGE_ROOT"):
            if os.environ.has_key("SGE_ROOT"):
                # use SGE_ROOT from environment
                self.__sge_dict["SGE_ROOT"] = os.environ["SGE_ROOT"]
            else:
                try:
                    self.__sge_dict["SGE_ROOT"] = file("/etc/sge_root", "r").read().split()[0]
                except:
                    self.log("cannot read sge_root: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__sge_dict["SGE_ROOT"] = "NO_SGE_ROOT_SET"
        if not self.__sge_dict.has_key("SGE_CELL"):
            if os.environ.has_key("SGE_CELL"):
                # use SGE_CELL from environment
                self.__sge_dict["SGE_CELL"] = os.environ["SGE_CELL"]
            else:
                try:
                    self.__sge_dict["SGE_CELL"] = file("/etc/sge_cell", "r").read().split()[0]
                except:
                    self.log("cannot read sge_cell: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    self.__sge_dict["SGE_CELL"] = "NO_SGE_CELL_SET"
        if not self.__sge_dict.has_key("SGE_ARCH"):
            c_stat, c_out = self._execute_command("/%s/util/arch" % (self.__sge_dict["SGE_ROOT"]))
            if c_stat:
                self.__sge_dict["SGE_ARCH"] = "NO_SGE_ARCH_SET"
            else:
                self.__sge_dict["SGE_ARCH"] = c_out
    def _check_for_update(self, d_name, force=False):
        act_time = time.time()
        cur_el = self.__tree.find(d_name)
        last_time = int(cur_el.get("last_update", "0"))
        do_upd = abs(last_time - act_time) > self.__timeout_dicts[d_name] or force
        if do_upd:
            # remove previous xml subtree
            cur_el.getparent().remove(cur_el)
        return do_upd
    def _get_com_name(self, c_name):
        return "/%s/bin/%s/%s" % (self.__sge_dict["SGE_ROOT"],
                                  self.__sge_dict["SGE_ARCH"],
                                  c_name)
    def _execute_command(self, command, **kwargs):
        # fancy, fancy
        os.environ["SGE_CELL"] = self.__sge_dict["SGE_CELL"]
        os.environ["SGE_SINGLE_LINE"] = "1"
        s_time = time.time()
        c_stat, c_out = commands.getstatusoutput(command)
        e_time = time.time()
        if c_stat:
            self.log("command '%s' gave (%d) in %s: %s" % (command,
                                                           c_stat,
                                                           logging_tools.get_diff_time_str(e_time - s_time),
                                                           c_out))
        if kwargs.get("simple_split", False) and not c_stat:
            c_out = [line.split(None, 1) for line in c_out.split("\n") if len(line.split(None, 1)) == 2]
        return c_stat, c_out
    def _check_queueconf_dict(self):
        all_queues = E.queues()
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -sq \*" % (qconf_com),
                                              simple_split=True)
        if not c_stat:
            cur_q = None
            for key, value in c_out:
                if key == "qname":
                    if cur_q is not None:
                        all_queues.append(cur_q)
                    cur_q = E.queue(name=value)
                else:
                    cur_q.append(getattr(E, key)(value))
            all_queues.append(cur_q)
        return all_queues
    def _check_hostgroup_dict(self):
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -shgrpl" % (qconf_com))
        cur_hgroups = E.hostgroups()
        if not c_stat:
            for hgrp_name in c_out.split("\n"):
                c_stat, c_out = self._execute_command("%s -shgrp %s" % (qconf_com,
                                                                        hgrp_name),
                                                      simple_split=True)
                if not c_stat:
                    new_hg = E.hostgroup(name=c_out.pop(0)[1])
                    for host in c_out.pop(0)[1].split():
                        new_hg.append(E.host(host))
                    cur_hgroups.append(new_hg)
        return cur_hgroups
    def _check_complexes_dict(self):
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("%s -sc" % (qconf_com))
        all_complexes = E.complexes()
        if not c_stat:
            for line_parts in [s_line.strip().split() for s_line in c_out.split("\n") if not s_line.strip().startswith("#")]:
                all_complexes.append(E.complex(line_parts[0], short=line_parts[1]))
        return all_complexes
    def _check_qhost_dict(self):
        qstat_com = self._get_com_name("qhost")
        c_stat, c_out = self._execute_command("%s -F -q -xml -j" % (qstat_com))
        all_qhosts = etree.fromstring(c_out)
        for cur_host in all_qhosts.xpath(".//host"):#[not(@name='global')]"):
            cur_host.attrib["short_name"] = cur_host.attrib["name"].split(".")[0]
        for cur_job in all_qhosts.xpath(".//job"):
            task_node = cur_job.find("jobvalue[@name='taskid']")
            if task_node is not None:
                cur_job.attrib["full_id"] = "%s.%s" % (cur_job.attrib["name"], task_node.text)
            else:
                cur_job.attrib["full_id"] = cur_job.attrib["name"]
        for state_el in all_qhosts.xpath(".//queue/queuevalue[@name='state_string']"):
            state_el.addnext(E.queuevalue(",".join(["(%s)%s" % (
                cur_state,
                {"-" : "-",
                 "u" : "unknown",
                 "a" : "alarm",
                 "A" : "alarm",
                 "C" : "calendar suspended",
                 "s" : "suspended",
                 "S" : "subordinate",
                 "d" : "disabled",
                 "D" : "disabled",
                 "E" : "error"}[cur_state][1:]) for cur_state in state_el.text or "-"]),
                                          name="long_state_string"))
        for qtype_el in all_qhosts.xpath(".//queue/queuevalue[@name='qtype_string']"):
            qtype_el.addnext(E.queuevalue(",".join(["(%s)%s" % (
                cur_qtype,
                {"B" : "Batch",
                 "I" : "Interactive",
                 "C" : "Checkpointing",
                 "P" : "Parallel",
                 "T" : "Transfer"}[cur_qtype][1:]) for cur_qtype in qtype_el.text or "-"]),
                                          name="long_qtype_string"))
        return all_qhosts
    def _check_qstat_dict(self):
        qstat_com = self._get_com_name("qstat")
        # -u * is important to get all jobs
        c_stat, c_out = self._execute_command("%s -u \* -r -t -ext -urg -pri -xml" % (qstat_com))
        all_jobs = etree.fromstring(c_out)
        # modify job_ids
        for cur_job in all_jobs.findall(".//job_list"):
            cur_job.attrib["full_id"] = "%s%s" % (
                cur_job.findtext("JB_job_number"),
                ".%s"  % (cur_job.findtext("tasks")) if cur_job.find("tasks") is not None else "")
        for state_el in all_jobs.xpath(".//job_list/state"):
            state_el.addnext(E.state_long(",".join(["(%s)%s" % (
                cur_state,
                {"q" : "queued",
                 "d" : "deleted",
                 "h" : "hold",
                 "r" : "running",
                 "R" : "Restarted",
                 "s" : "suspended",
                 "S" : "Subordinated",
                 "t" : "transfering",
                 "T" : "Threshold",
                 "w" : "waiting",
                 "o" : "orphaned"}[cur_state][1:]) for cur_state in state_el.text or "-"])))
        for node_name, attr_name in [("JAT_start_time", "start_time"),
                                     ("JB_submission_time", "submit_time")]:
            for time_el in all_jobs.findall(".//%s" % (node_name)):
                time_el.getparent().attrib[attr_name] = datetime.datetime.strptime(time_el.text, "%Y-%m-%dT%H:%M:%S").strftime("%s")
        return all_jobs
    def _parse_sge_values(self, q_el, key_name, has_values):
        cur_el = q_el.find(key_name)
        if "parsed" in cur_el.attrib:
            # already transformed
            return
        cur_el.attrib["parsed"] = "1"
        #print "*", q_el, key_name, has_values, cur_el, "parsed" in cur_el.attrib
        #old_dict = q_el[key_name]
        # parse values of form GLOBAL,[node_spec=LOCAL],...
        c_split = cur_el.text.split(",[", 1)
        global_part = c_split.pop(0)
        if has_values:
            if global_part != "NONE":
                cur_el.extend([E.conf_var(name=s_part.split("=", 1)[0], value=s_part.split("=", 1)[1]) for s_part in global_part.split(",")])
        else:
            if global_part != "NONE":
                cur_el.extend([E.conf_var(name=s_part) for s_part in global_part.split()])
        if c_split:
            c_split = c_split[0][:-1].split("],[")
            for node_spec in c_split:
                node_part, local_part = node_spec.split("=", 1)
                s_node = node_part.split(".")[0]
                if has_values:
                    cur_el.extend([E.conf_var(host=s_node, name=s_part.split("=", 1)[0], value=s_part.split("=", 1)[1]) for s_part in local_part.split(",")])
                else:
                    cur_el.extend([E.conf_var(host=s_node, name=s_part) for s_part in local_part.split(",")])
        # remove text
        cur_el.text = None
    def get_queue(self, q_id, default=None):
        return self.__queue_lut.get(q_id, default)
    def get_host(self, h_id, default=None):
        return self.__host_lut.get(h_id, default)
    def get_job(self, j_id, default=None):
        return self.__job_lut.get(j_id, default)
    def build_luts(self):
        self.__job_lut = dict([(cur_job.get("full_id"), cur_job) for cur_job in self["qstat"].findall(".//job_list")])
        self.__queue_lut = {}
        for queue in self["queueconf"].findall(".//queue"):
            self.__queue_lut[queue.get("name")] = queue
            for exp_name, with_values in [("complex_values", True ),
                                          ("pe_list"       , False),
                                          ("user_lists"    , False),
                                          ("xuser_lists"   , False),
                                          ("projects"      , False),
                                          ("xprojects"     , False),
                                          ("seq_no"        , False)]:
                self._parse_sge_values(queue, exp_name, with_values)
        self.__host_lut = {}
        for cur_host in self["qhost"].findall("qhost/host"):
            self.__host_lut[cur_host.get("short_name")] = cur_host
            self.__host_lut[cur_host.get("name")] = cur_host
        # expand host_list of queue q_name if not already expanded
        hg_lut = dict([(cur_hg.get("name"), cur_hg) for cur_hg in self["hostgroup"].findall(".//hostgroup")])
        for queue in self.__queue_lut.itervalues():
            if not(queue.findall("hosts")):
                hosts_el = E.hosts()
                queue.append(hosts_el)
                for cur_hlist in queue.findall("hostlist"):
                    for hg_name in cur_hlist.text.split():
                        hosts_el.extend([E.host(str(name)) for name in hg_lut[hg_name].xpath(".//host/text()")] if hg_name.startswith("@") else [E.host(hg_name)])

if __name__ == "__main__":
    print "This is a loadable module, exiting..."
    sys.exit(0)
