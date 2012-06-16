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
""" frontend for SGE qstat """

import logging_tools
import sys
import optparse
import os
import os.path
import time
import datetime
import sge_tools
import pprint
# from NH
import urwid
from lxml import etree

SQL_ACCESS = "cluster_full_access"

def check_environment():
    # set environment variables SGE_ROOT / SGE_CELL if not already set
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"),
                          ("SGE_CELL", "/etc/sge_cell")]:
        if not os.environ.has_key(v_name):
            if os.path.isfile(v_src):
                os.environ[v_name] = open(v_src, "r").read().strip()
            else:
                print "error Cannot assign environment-variable '%s', exiting..." % (v_name)
                sys.exit(1)

def sjs(s_info, opt_dict):
    ret_list = [time.ctime()]
    s_info.build_luts()
    # running jobs
    r_job_ids = sorted(s_info["qstat"].xpath(".//job_list[@state='running' and master[text() = 'MASTER']]"), key=lambda x : x.findtext("JB_job_number"))
    w_job_ids = sorted(s_info["qstat"].findall(".//job_list[@state='pending']"), key=lambda x : x.findtext("JB_job_number"))
    if len(r_job_ids):
        r_out_list = logging_tools.new_form_list()
        job_host_lut, job_host_pe_lut = ({}, {})
        for cur_host in s_info["qhost"].findall("qhost/host"):
            #print etree.tostring(cur_host, pretty_print=True)
            for cur_job in cur_host.xpath("job"):
                job_host_lut.setdefault(cur_job.attrib["full_id"], []).append(cur_host.attrib["short_name"])
                job_host_pe_lut.setdefault(cur_job.attrib["full_id"], {}).setdefault(cur_job.findtext("jobvalue[@name='pe_master']"), []).append(cur_host.attrib["short_name"])
        host_loads = dict([(cur_host.attrib["short_name"], float(cur_host.findtext("hostvalue[@name='load_avg']"))) for cur_host in s_info["qhost"].findall(".//host") if cur_host.attrib["short_name"] != "global"])
        run_counted = 0
        for act_job in r_job_ids:
            show_job = True
            if opt_dict.users:
                if act_job.find("JB_owner").text not in opt_dict.users:
                    show_job = False
            i_reqs = set([])#act_job.get_init_requests(s_info["complexes"]))
            if opt_dict.complexes:
                pass
            if show_job:
                run_counted += 1
                act_line = [logging_tools.form_entry(act_job.findtext("JB_job_number"), header="id"),
                            logging_tools.form_entry(act_job.findtext("tasks") or "", header="task"),
                            logging_tools.form_entry_right(act_job.findtext("JB_name"), header="name"),
                            logging_tools.form_entry_right("%s(%s)" % (act_job.find("granted_pe").attrib["name"], act_job.findtext("granted_pe")) if len(act_job.findall("granted_pe")) else "-", header="pe"),
                            logging_tools.form_entry_right(act_job.find("JB_owner").text, header="user"),
                            logging_tools.form_entry_right(act_job.findtext("state_long" if opt_dict.long_status else "state"), header="state")]
                if opt_dict.show_memory:
                    # shows only memory of first host
                    master_h = s_info.get_host(act_job.findtext("queue_name").split("@")[-1].split(".")[0])
                    act_line.extend([logging_tools.form_entry_right(master_h.findtext("resourcevalue[@name='virtual_total']"), header="v_tot"),
                                     logging_tools.form_entry_right(master_h.findtext("resourcevalue[@name='virtual_free']"), header="v_free")])
                act_line.extend([logging_tools.form_entry_right(",".join(sorted(i_reqs)) or "---", header="complex"),
                                 logging_tools.form_entry_right(act_job.findtext("queue_name").split("@")[0], header="queue")])
                if not opt_dict.suppress_times:
                    start_time = datetime.datetime.fromtimestamp(int(act_job.attrib["start_time"]))
                    act_line.extend([logging_tools.form_entry_right(logging_tools.get_relative_dt(start_time), header="start time"),
                                     logging_tools.form_entry_right(s_info.get_run_time(start_time), header="run time"),
                                     logging_tools.form_entry_right(s_info.get_left_time(start_time, act_job.findtext("hard_request[@name='h_rt']")), header="left time")
                                     ])
                load_list = [host_loads[h_name] for h_name in job_host_lut[act_job.attrib["full_id"]]]
                mean_load = sum(load_list) / len(load_list)
                num_nodes = len(load_list)
                if num_nodes == 1:
                    eff = 100
                else:
                    max_load = max(load_list)
                    if max_load:
                        eff = int((num_nodes / (max_load * float(num_nodes - 1)) * mean_load + 1./float(1 - num_nodes)) * 100)
                    else:
                        eff = 0
                act_line.extend([logging_tools.form_entry_right("%.2f (%3d %%)" % (mean_load, eff), header="load (eff)")])
                if not opt_dict.suppress_nodelist:
                    jh_pe_lut = job_host_pe_lut[act_job.get("full_id")]
                    act_line.append(logging_tools.form_entry(",".join([sge_tools.compress_list(sorted(jh_pe_lut[key])) for key in ["MASTER", "SLAVE"] if key in jh_pe_lut]), header="nodes"))
                r_out_list.append(act_line)
        if len(r_job_ids) == run_counted:
            ret_list.append("%s" % (logging_tools.get_plural("running job", len(r_job_ids))))
        else:
            ret_list.append("%s, showing only %d (due to filter)" % (logging_tools.get_plural("running job", len(r_job_ids)),
                                                                     run_counted))
        if r_out_list:
            ret_list.append(str(r_out_list))
    if len(w_job_ids):
        w_out_list = logging_tools.new_form_list()
        show_ids = []
        for act_job in w_job_ids:
            show_job = True
            if opt_dict.only_valid_waiting:
                if "h" in act_job.findtext("state") or "E" in act_job.findtext("state"):
                    show_job = False
            if show_job:
                show_ids.append((float(act_job.findtext("JB_priority")), act_job.findtext("JB_job_number"), act_job))
        show_ids.sort()
        show_ids.reverse()
        wait_counted = 0
        for pri, w_job_id, act_job in show_ids:
            show_job = True
            if opt_dict.users and act_job.findtext("JB_owner") not in opt_dict.users:
                show_job = False
            i_reqs = set([])#act_job.get_init_requests(s_info["complexes"]))
            if opt_dict.complexes:
                pass
            if show_job:
                wait_counted += 1
                act_line = [logging_tools.form_entry(act_job.findtext("JB_job_number"), header="id"),
                            logging_tools.form_entry(act_job.findtext("tasks") or "", header="task"),
                            logging_tools.form_entry_right(act_job.findtext("JB_name"), header="name"),
                            logging_tools.form_entry_right("%s(%s)" % (act_job.find("requested_pe").attrib["name"], act_job.findtext("requested_pe")) if len(act_job.findall("requested_pe")) else "-", header="pe"),
                            logging_tools.form_entry_right(act_job.findtext("JB_owner"), header="user"),
                            logging_tools.form_entry_right(act_job.findtext("state_long" if opt_dict.long_status else "state"), header="state"),
                            logging_tools.form_entry_right(",".join(act_job.xpath("hard_request/@name")) or "---", header="complex"),
                            logging_tools.form_entry_right(act_job.findtext("hard_req_queue") or "---", header="queue")]
                if not opt_dict.suppress_times:
                    submit_time = datetime.datetime.fromtimestamp(int(act_job.attrib["submit_time"]))
                    act_line.extend([logging_tools.form_entry_right(logging_tools.get_relative_dt(submit_time), header="queue time"),
                                     logging_tools.form_entry_right(s_info.get_run_time(submit_time), header="wait time"),
                                     logging_tools.form_entry_right(s_info.get_h_rt_time(act_job.findtext("hard_request[@name='h_rt']")), header="req time")
                                     ])
                dep_list = sorted(act_job.xpath(".//predecessor_jobs_req/text()"))
                act_line.extend([logging_tools.form_entry_right(act_job.find("JAT_prio").text, header="priority"),
                                 logging_tools.form_entry("%d: %s" % (len(dep_list), ",".join(dep_list)) if dep_list else "", header="depends")])
                w_out_list.append(act_line)
        if len(show_ids) == wait_counted:
            ret_list.append("%s" % (logging_tools.get_plural("waiting job", len(show_ids))))
        else:
            ret_list.append("%s, showing only %d (due to filter)" % (logging_tools.get_plural("waiting job", len(show_ids)),
                                                                     wait_counted))
        if w_out_list:
            ret_list.append(str(w_out_list))
    if opt_dict.interactive:
        return "\n".join(ret_list)
    else:
        print "\n".join(ret_list)

def sns(s_info, opt_dict):
    # build list of queue / node tuples to display
    s_info.build_luts()
    job_host_lut, job_host_pe_lut = ({}, {})
    for cur_host in s_info["qhost"].findall("qhost/host"):
        for cur_job in cur_host.xpath("job"):
            job_host_lut.setdefault(cur_job.attrib["full_id"], []).append(cur_host.attrib["short_name"])
            job_host_pe_lut.setdefault(cur_host.attrib["short_name"], {}).setdefault(cur_job.findtext("jobvalue[@name='qinstance_name']").split("@")[0], {}).setdefault(cur_job.get("full_id"), []).append(cur_job.findtext("jobvalue[@name='pe_master']"))
    d_list = []
    for act_q in s_info["queueconf"].findall(".//queue"):
        d_list.extend([(act_q.attrib["name"], h_name.text) for h_name in act_q.findall(".//host")])
    d_list = sorted(d_list, key=lambda node: node[1 if opt_dict.node_sort else 0])
    #init_complexes = [key for key, value in s_info["complexes"].iteritems() if value.complex_type == "i"]
    out_list = logging_tools.new_form_list()
    for q_name, h_name in d_list:
        act_q, act_h = (s_info.get_queue(q_name), s_info.get_host(h_name))
        s_name = act_h.get("short_name")
        m_queue = act_h.find("queue[@name='%s']" % (act_q.attrib["name"]))
        show_queue = True
        if opt_dict.suppress_empty and int(m_queue.findtext("queuevalue[@name='slots_used']")) == 0:
            show_queue = False
        if opt_dict.show_nonstd:
            show_queue = False
            if m_queue.findtext("queuevalue[@name='state_string']") not in [""]:
                show_queue = True
                if m_queue.findtext("queuevalue[@name='state_string']") == "a" and opt_dict.show_nonstd > 1:
                    show_queue = False
        if show_queue:
            # check for user filters
            q_job_list = []#job_lut.get(q_name, {}).get(s_name, [])
            if opt_dict.users:
                q_job_owners = set([s_info["qstat"][job_id]["JB_owner"] for job_id, job_type in q_job_list])
                if not q_job_owners.intersection(opt_dict.users):
                    show_queue = False
        if show_queue:
            # check for complex filters
            if opt_dict.complexes:
                q_job_complexes = set(act_q.xpath("complex_values/conf_var[not(@node_name) or @node_name='%s']/@name" % (act_h.get("short_name"))))
                if not q_job_complexes & set(opt_dict.complexes):
                    show_queue = False
        if show_queue:
            act_line = [logging_tools.form_entry(q_name, header="queue"),
                        logging_tools.form_entry(s_name, header="host")]
            #out_list.append(act_line)
            #continue
            if opt_dict.show_seq:
                act_line.append(logging_tools.form_entry(int(act_q.xpath("seq_no/conf_var[not(@node_name) or @node_name='%s']/@name")[0]), header="seq"))
            if not opt_dict.suppress_status:
                act_line.append(logging_tools.form_entry(m_queue.findtext("queuevalue[@name='%sstate_string']" % (
                    "long_" if opt_dict.long_status else "")) or "-", header="state"))
            if opt_dict.show_type or opt_dict.show_long_type:
                act_line.append(logging_tools.form_entry(m_queue.findtext("queuevalue[@name='%sqtype_string']" % (
                    "long_" if opt_dict.show_long_type else "")), header="type"))
            if opt_dict.show_complexes:
                act_line.append(logging_tools.form_entry(",".join(sorted(set(act_q.xpath("complex_values/conf_var[not(@node_name) or @node_name='%s']/@name" % (act_h.get("short_name")))))), header="complex"))
            if opt_dict.show_pe:
                act_line.append(logging_tools.form_entry(",".join(sorted(set(act_q.xpath("pe_list/conf_var[not(@node_name) or @node_name='%s']/@name" % (act_h.get("short_name")))))), header="PE"))
            if opt_dict.show_memory:
                act_line.extend([logging_tools.form_entry_right(act_h.findtext("resourcevalue[@name='virtual_total']"), header="v_tot"),
                                 logging_tools.form_entry_right(act_h.findtext("resourcevalue[@name='virtual_free']"), header="v_free")])
            act_line.extend([logging_tools.form_entry_right("%.2f" % (float(act_h.findtext("resourcevalue[@name='load_avg']"))), header="load"),
                             logging_tools.form_entry_right(m_queue.findtext("queuevalue[@name='slots_used']"), header="su"),
                             logging_tools.form_entry_right(m_queue.findtext("queuevalue[@name='slots_resv']"), header="sr"),
                             logging_tools.form_entry_right(m_queue.findtext("queuevalue[@name='slots']"), header="st"),
                             ])
            if opt_dict.show_acl:
                for ref_name, header_name in [("user_list", "userlists"),
                                              ("project"  , "projects")]:
                    pos_list = " or ".join(act_q.xpath(".//%ss/conf_var[not(@node_name) or @node_name='%s']/@name" % (
                        ref_name,
                        act_h.get("short_name"))))
                    neg_list = " or ".join(act_q.xpath(".//x%ss/conf_var[not(@node_name) or @node_name='%s']/@name" % (
                        ref_name,
                        act_h.get("short_name"))))
                    if not pos_list and not neg_list:
                        acl_str = "all"
                    elif not neg_list:
                        acl_str = pos_list
                    elif not pos_list:
                        acl_str = "not (%s)" % (neg_list)
                    else:
                        acl_str = "%s and not (%s)" % (pos_list, neg_list)
                    act_line.append(logging_tools.form_entry(acl_str, header=header_name))
            type_dict = job_host_pe_lut.get(s_name, {}).get(q_name, {})
            cur_dict = dict([(job_id, s_info.get_job(job_id)) for job_id in sorted(type_dict.keys())])
            qstat_info = ", ".join(["%s%s %s (%d) %s%s" % (
                "[" if "s" in cur_dict[key].findtext("state").lower() else "",
                key,
                cur_dict[key].findtext("JB_owner"),
                int(cur_dict[key].findtext("granted_pe") or "1"),
                (", ".join([
                    "%s%s" % (
                        ("%d x " % (type_dict[key].count(s_key))).replace("1 x ", ""),
                        s_key) for
                    s_key in ["MASTER", "SLAVE"] if s_key in type_dict[key]]) + ".").replace("MASTER.", "SINGLE.")[:-1],
                "]" if "s" in cur_dict[key].findtext("state").lower() else "",
            ) for key in sorted(type_dict.keys())])
            act_line.append(logging_tools.form_entry(qstat_info, header="jobs"))
            out_list.append(act_line)
    if out_list:
        if opt_dict.interactive:
            return "%s\n%s" % (time.ctime(), out_list)
        else:
            print out_list

# following code from NH for interactive mode
    
class window(object):
    def __init__(self, **kwargs):
        self.start_time = time.time()
        self.callback = kwargs.get("callback", None)
        self.tree = kwargs.get("tree", None)
        self.cb_args = kwargs.get("args", [])
        self.top_text = urwid.Text(("banner", "Init cluster"), align="left")
        self.main_text = urwid.Text("Wait please...", align="left")
        self.bottom_text = urwid.Text("", align="left")
        if self.tree:
            self.set_question_text(self.tree.get_cur_text())
        else:
            self.set_question_text("q/Q - exit")
        palette = [
            ('banner', 'black', 'light gray', 'standout,underline'),
            ('streak', 'black', 'dark red', 'standout'),
            ('bg', 'white', 'dark blue'),
        ]
        urwid_map = urwid.AttrMap(
            urwid.Filler(
                urwid.Pile([
                    urwid.AttrMap(
                        self.top_text,
                        "streak"),
                    urwid.AttrMap(
                        self.main_text,
                        "banner"),
                    urwid.AttrMap(
                        self.bottom_text,
                        "streak")]),
                "top"),
            "banner")
        self.mainloop = urwid.MainLoop(urwid_map, palette, unhandled_input=self._handler_data)
        self._update_screen()
        self.mainloop.set_alarm_in(10, self._alarm_callback)
    def loop(self):
        self.mainloop.run()
    def _alarm_callback(self, main_loop, user_data):
        self._update_screen()
        self.mainloop.set_alarm_in(10, self._alarm_callback)
    # can be called from dt_tree
    def close(self):
        raise urwid.ExitMainLoop()
    def back_to_top(self):
        self.tree.back_to_top()
        self.set_question_text(self.tree.get_cur_text())
    def _handler_data(self, in_char):
        if self.tree:
            handled = self.tree.handle_input(in_char, self)
        else:
            if in_char.lower() == "q":
                self.close()
            else:
                handled = False
        if not handled:
            self._update_screen()
    def _update_screen(self):
        self.top_text.set_text(("streak", "time: %s" % (time.ctime())))
        self.main_text.set_text(("banner", str(self.get_data())))
    def set_question_text(self, in_text):
        self.bottom_text.set_text(("bg", in_text))
    def get_data(self):
        if self.callback:
            return unicode(self.callback(*self.cb_args))
        else:
            return "no data"
        
class dt_tree(object):
    def __init__(self, head_node):
        self.head_node = head_node
        self.head_node.set_tree(self)
        self.cur_node = self.head_node
    def back_to_top(self):
        self.cur_node = self.head_node
    def get_cur_text(self):
        return "%s (%s)" % (
            self.cur_node.question,
            "/".join(sorted(self.cur_node.get_triggers())))
    def handle_input(self, in_char, w_obj):
        cur_node = self.cur_node
        cur_triggers = cur_node.get_triggers()
        if in_char.lower() in cur_triggers:
            handled = True
            next_node = cur_node.follow_edge(in_char.lower())
            if next_node.action:
                getattr(w_obj, next_node.action)()
            else:
                self.cur_node = next_node
                w_obj.set_question_text(self.get_cur_text())
        else:
            handled = False
        return handled
        
class dt_node(object):
    def __init__(self, question, action=None, edges=[]):
        self.question = question
        self.edges = []
        self.__edge_dict = {}
        self.action = action
        for edge in edges:
            self.add_edge(edge)
    def add_edge(self, edge):
        edge.target.prev_node = self
        self.edges.append(edge)
        self.__edge_dict[edge.trigger.lower()] = edge
    def set_tree(self, tree):
        self.tree = tree
        for edge in self.edges:
            edge.target.set_tree(tree)
    def get_triggers(self):
        return [edge.trigger.lower() for edge in self.edges]
    def follow_edge(self, trigger):
        sub_edge = self.__edge_dict[trigger.lower()]
        return sub_edge.target

class dt_edge(object):
    def __init__(self, trigger, target=None):
        self.trigger = trigger
        self.target = target

class my_opt_parser(optparse.OptionParser):
    def __init__(self, run_mode):
        optparse.OptionParser.__init__(self)
        if run_mode in ["sjs", "sns"]:
            self.add_option("-m", dest="show_memory", help="show memory information [%default]", action="store_true", default=False)
            self.add_option("-s", dest="suppress_status", help="suppress status [%default]", action="store_true", default=False)
            self.add_option("-S", dest="long_status", help="show long status [%default]", action="store_true", default=False)
            self.add_option("-T", dest="show_long_type", help="show long queue type [%default]", action="store_true", default=False)
            self.add_option("-a", dest="show_acl", help="show access control info [%default]", action="store_true", default=False)
            self.add_option("-q", dest="show_seq", help="show sequence number [%default]", action="store_true", default=False)
            self.add_option("-u", dest="users", type="str", help="show only jobs of user [%default]", action="append", default=[])
            self.add_option("-c", dest="complexes", type="str", help="show only jobs with the given complexes [%default]", action="append", default=[])
            self.add_option("-e", dest="show_nonstd", help="show nonstandard queues, specifiy twice to suppress alarm queues [%default]", action="count", default=0)
            self.add_option("-i", dest="interactive", help="show info interactive", action="store_true", default=False)
        if run_mode == "sns":
            self.add_option("-t", dest="show_type", help="show queue type [%default]", action="store_true", default=False)
            self.add_option("-C", dest="show_complexes", help="show complexes [%default]", action="store_true", default=False)
            self.add_option("-n", dest="suppress_empty", help="show only nonempty queues [%default]", action="store_true", default=False)
            self.add_option("-N", dest="node_sort", help="sort according to the nodename [%default]", action="store_true", default=False)
            self.add_option("--pe", dest="show_pe", help="show pe information [%default]", action="store_true", default=False)
        elif run_mode == "sjs":
            #self.add_option("-s", dest="no_status", help="suppress status [%default]", action="store_true", default=False)
            self.add_option("--valid", dest="only_valid_waiting", help="show only valid waiting jobs [%default]", action="store_true", default=False)
            self.add_option("-n", dest="suppress_nodelist", help="suppress nodelist [%default]", action="store_true", default=False)
            self.add_option("-t", dest="suppress_times", help="suppress the display of start/run/left times [%default]", action="store_true", default=False)
        elif run_mode == "scs":
            self.add_option("-q", dest="show_queues", help="display according to the queuename [%default]", action="store_true", default=False)
            self.add_option("-s", dest="sort_queues", help="sort according to the queuename [%default]", action="store_true", default=False)
        elif run_mode == "sla":
            self.add_option("-n", dest="node", help="set nodename to add a logline to [%default]", type="str", default=None)
            self.add_option("-l", dest="log_level", help="set numeric log_level (0 ... ok, 5 ... warn, 10 ... error, 20 ... critical) [%default]", type="int", default=10)
            self.add_option("--warn", dest="log_level", help="set log_level to warn", action="store_const", const=5)
            self.add_option("--error", dest="log_level", help="set log_level to error", action="store_const", const=10)
            self.add_option("--critical", dest="log_level", help="set log_level to critical", action="store_const", const=20)
            self.add_option("-q", dest="queue_name", help="set queue_name for log_entry [%default]", type="str", default=None)
        self.add_option("-v", dest="verbose", help="set verbose mode [%default]", action="store_true", default=False)
        
def log_com(what, level):
    print "%s [%s] %s" % (time.ctime(),
                          logging_tools.get_log_level_str(level),
                          what)

def get_server():
    srv_name = "localhost"
    if os.environ.has_key("SGE_SERVER"):
        srv_name = os.environ["SGE_SERVER"]
    else:
        for f_name in ["/etc/sge_relayer", "/etc/sge_server"]:
            if os.path.isfile(f_name):
                srv_name = file(f_name, "r").read().split()[0]
                break
    return srv_name

def main():
    c_time = time.time()
    check_environment()
    run_mode = {
        "sgejobstat"     : "sjs",
        "sgenodestat"    : "sns",
        "sjs"            : "sjs",
        "sns"            : "sns",
        }.get(os.path.basename(sys.argv[0]), "sjs")
    options, args = my_opt_parser(run_mode).parse_args()
    if run_mode in ["sla"]:
        if args:
            add_args = " ".join(args)
        else:
            print "Need logentry text"
            sys.exit(-1)
    else:
        if args:
            print "Additional arguments found (%s), exiting" % (" ".join(args))
            sys.exit(-1)
    if run_mode not in ["sla"]:
        act_si = sge_tools.sge_info(update_pref={"qhost"     : [],
                                                 "complexes" : ["server"],
                                                 "hostgroup" : ["server"],
                                                 "qstat"     : [],
                                                 "queueconf" : ["server"]},
                                    verbose=options.verbose,
                                    log_command=log_com,
                                    server=get_server())
    s_time = time.time()
    if run_mode == "sjs":
        if options.interactive:
            window(callback=sjs,
                   args=(act_si, options),
                   tree=dt_tree(
                       dt_node(
                           "press p to print and q to exit",
                           edges=[
                               dt_edge(
                                   "p",
                                   dt_node(
                                       "Are you sure",
                                       edges=[
                                           dt_edge("y", dt_node(None, action="back_to_top")),
                                           dt_edge("n", dt_node(None, action="back_to_top"))])),
                               dt_edge(
                                   "q",
                                   dt_node(
                                       None,
                                       action="close"))])
                       )).loop()
        else:
            sjs(act_si, options)
    elif run_mode == "sns":
        if options.interactive:
            window(callback=sns, args=(act_si, options),
                   tree=dt_tree(
                       dt_node(
                           "press q to exit",
                           edges=[
                               dt_edge(
                                   "q",
                                   dt_node(
                                       None,
                                       action="close"))])
                       )).loop()
        else:
            sns(act_si, options)
    else:
        print "Unknown runmode %s" % (run_mode)
    e_time = time.time()
    if not options.interactive:
        print "took %s / %s" % (
            logging_tools.get_diff_time_str(s_time - c_time),
            logging_tools.get_diff_time_str(e_time - s_time))
    
if __name__ == "__main__":
    main()
