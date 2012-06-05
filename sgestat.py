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
try:
    import mysql_tools
except ImportError:
    mysql_tools = None

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
    show_users     = set(map(lambda fnc: fnc.strip(), opt_dict.user.split(",")))
    show_complexes = set(map(lambda fnc: fnc.strip(), opt_dict.complexes.split(",")))
    # running jobs
    r_job_ids = [key for key, value in s_info["qstat"].iteritems() if value.running]
    w_job_ids = [key for key, value in s_info["qstat"].iteritems() if not value.running]
    r_job_ids = sorted(r_job_ids)
    w_job_ids = sorted(w_job_ids)
    if r_job_ids:
        r_out_list = logging_tools.new_form_list()
        run_counted = 0
        for r_job_id in r_job_ids:
            act_job = s_info["qstat"][r_job_id]
            show_job = True
            if act_job["JB_owner"] in show_users or "ALL" in show_users:
                pass
            else:
                show_job = False
            i_reqs = set(act_job.get_init_requests(s_info["complexes"]))
            if "ALL" in show_complexes or i_reqs.intersection(show_complexes):
                pass
            else:
                show_job = False
            if show_job:
                run_counted += 1
                act_line = [logging_tools.form_entry(act_job.get_id(), header="id"),
                            logging_tools.form_entry(act_job.get("tasks", ""), header="task"),
                            logging_tools.form_entry_right(act_job["JB_name"], header="name"),
                            logging_tools.form_entry_right(act_job.get_pe_info("granted"), header="pe"),
                            logging_tools.form_entry_right(act_job["JB_owner"], header="user"),
                            logging_tools.form_entry_right(act_job.get_state(opt_dict.long_status), header="state")]
                if opt_dict.show_memory:
                    # shows only memory of first host
                    master_h = s_info["qhost"][act_job.get_master_node().split(".")[0]]
                    act_line.extend([logging_tools.form_entry_right(master_h.get_memory_info("virtual_total"), header="v_tot"),
                                     logging_tools.form_entry_right(master_h.get_memory_info("virtual_free"), header="v_free")])
                act_line.extend([logging_tools.form_entry_right(",".join(sorted(i_reqs)) or "---", header="complex"),
                                 logging_tools.form_entry_right(act_job.get_running_queue(), header="queue")])
                if not opt_dict.suppress_times:
                    act_line.extend([logging_tools.form_entry_right(act_job.get_start_time(), header="start time"),
                                     logging_tools.form_entry_right(act_job.get_run_time(), header="run time"),
                                     logging_tools.form_entry_right(act_job.get_left_time(), header="left time")])
                act_line.extend([logging_tools.form_entry_right(act_job.get_load_info(s_info["qhost"]), header="load (eff)")])
                if not opt_dict.suppress_nodelist:
                    act_line.append(logging_tools.form_entry(act_job.get_running_nodes(), header="nodes"))
                r_out_list.append(act_line)
        if len(r_job_ids) == run_counted:
            ret_list.append("%s" % (logging_tools.get_plural("running job", len(r_job_ids))))
        else:
            ret_list.append("%s, showing only %d (due to filter)" % (logging_tools.get_plural("running job", len(r_job_ids)),
                                                                     run_counted))
        if r_out_list:
            ret_list.append(str(r_out_list))
    if w_job_ids:
        w_out_list = logging_tools.new_form_list()
        show_ids = []
        for w_job_id in w_job_ids:
            act_job = s_info["qstat"][w_job_id]
            show_job = True
            if opt_dict.only_valid_waiting:
                if "h" in act_job.get_state() or "E" in act_job.get_state():
                    show_job = False
            if show_job:
                show_ids.append((float(act_job.get_priority()), w_job_id))
        show_ids.sort()
        show_ids.reverse()
        wait_counted = 0
        for pri, w_job_id in show_ids:
            act_job = s_info["qstat"][w_job_id]
            show_job = True
            if act_job["JB_owner"] in show_users or "ALL" in show_users:
                pass
            else:
                show_job = False
            i_reqs = set(act_job.get_init_requests(s_info["complexes"]))
            if "ALL" in show_complexes or i_reqs.intersection(show_complexes):
                pass
            else:
                show_job = False
            if show_job:
                wait_counted += 1
                act_line = [logging_tools.form_entry(act_job.get_id(), header="id"),
                            logging_tools.form_entry(act_job.get("tasks", ""), header="task"),
                            logging_tools.form_entry_right(act_job["JB_name"], header="name"),
                            logging_tools.form_entry_right(act_job.get_pe_info("requested"), header="pe"),
                            logging_tools.form_entry_right(act_job["JB_owner"], header="user"),
                            logging_tools.form_entry_right(act_job.get_state(opt_dict.long_status), header="state"),
                            logging_tools.form_entry_right(",".join(sorted(i_reqs)) or "---", header="complex"),
                            logging_tools.form_entry_right(act_job.get_requested_queue(), header="queue")]
                if not opt_dict.suppress_times:
                    act_line.extend([logging_tools.form_entry_right(act_job.get_queue_time(), header="queue time"),
                                     logging_tools.form_entry_right(act_job.get_wait_time(), header="wait time"),
                                     logging_tools.form_entry_right(act_job.get_h_rt_time(), header="req time")])
                act_line.extend([logging_tools.form_entry_right(act_job.get_priority(), header="priority"),
                                 logging_tools.form_entry(act_job.get_dependency_info(), header="depends")])
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
    #print time.ctime()
    show_users     = set(map(lambda fnc: fnc.strip(), opt_dict.user.split(",")))
    show_complexes = set(map(lambda fnc: fnc.strip(), opt_dict.complexes.split(",")))
    # builder helper dicts
    all_queues = sorted(s_info["queueconf"].keys())
    for q_name in all_queues:
        # expand various entries
        act_q = s_info["queueconf"][q_name]
        s_info.expand_host_list(q_name)
        #for exp_name, new_name in [("complex_values", "compl_values")]:
        for exp_name, with_values in [("complex_values", True ),
                                      ("pe_list"       , False),
                                      ("user_lists"    , False),
                                      ("xuser_lists"   , False),
                                      ("projects"      , False),
                                      ("xprojects"     , False),
                                      ("seq_no"        , False)]:
            act_q[exp_name] = s_info._parse_sge_values(act_q[exp_name], with_values)
    # make lut for jobs
    job_lut = {}
    for job_id, job_stuff in s_info["qstat"].iteritems():
        if job_stuff.running:
            for q_spec, job_type in zip(job_stuff["queue_name"], job_stuff["master"]):
                q_name, h_name = q_spec.split("@")
                h_name = h_name.split(".")[0]
                job_lut.setdefault(q_name, {}).setdefault(h_name, []).append((job_id, job_type))
    # build list of queue / node tuples to display
    d_list = []
    for q_name in sorted(all_queues):
        d_list.extend([(q_name, h_name) for h_name in s_info["queueconf"][q_name]["hostlist"]])
    init_complexes = [key for key, value in s_info["complexes"].iteritems() if value.complex_type == "i"]
    if opt_dict.node_sort:
        d_list = [(q_name, h_name) for h_name, q_name in sorted([(h_n, q_n) for q_n, h_n in d_list])]
    out_list = logging_tools.new_form_list()
    for q_name, h_name in d_list:
        s_name = h_name.split(".")[0]
        act_q, act_h = (s_info["queueconf"][q_name],
                        s_info["qhost"].get(s_name, None))
        if not act_h:
            continue
        show_queue = True
        if opt_dict.suppress_empty and act_h.get_slots_used(q_name) == 0:
            show_queue = False
        if opt_dict.show_nonstd:
            show_queue = False
            if act_h.get_queue_state(q_name) not in ["-"]:
                show_queue = True
                if act_h.get_queue_state(q_name) == "a" and opt_dict.show_nonstd > 1:
                    show_queue = False
        if show_queue:
            # check for user filters
            q_job_list = job_lut.get(q_name, {}).get(s_name, [])
            if "ALL" in show_users:
                # ok, show queue
                pass
            else:
                q_job_owners = set([s_info["qstat"][job_id]["JB_owner"] for job_id, job_type in q_job_list])
                if not q_job_owners.intersection(show_users):
                    show_queue = False
        if show_queue:
            # check for complex filters
            if "ALL" in show_complexes:
                pass
            else:
                q_job_complexes = set(sum([s_info["qstat"][job_id].get_init_requests(s_info["complexes"]) for job_id, job_type in q_job_list], []))
                if not q_job_complexes.intersection(show_complexes):
                    show_queue = False
        if show_queue:
            act_line = [logging_tools.form_entry(q_name, header="queue"),
                        logging_tools.form_entry(s_name, header="host")]
            if opt_dict.show_seq:
                act_line.append(logging_tools.form_entry(act_h.get_seq_no(act_q), header="seq"))
            if not opt_dict.suppress_status:
                act_line.append(logging_tools.form_entry(act_h.get_queue_state(q_name, opt_dict.long_status), header="state"))
            if opt_dict.show_type:
                act_line.append(logging_tools.form_entry(act_h.get_queue_type(q_name, False), header="type"))
            elif opt_dict.show_long_type:
                act_line.append(logging_tools.form_entry(act_h.get_queue_type(q_name, True), header="type"))
            if opt_dict.show_complexes:
                act_line.append(logging_tools.form_entry(act_h.get_complex_info(act_q), header="complex"))
            if opt_dict.show_pe:
                act_line.append(logging_tools.form_entry(act_h.get_pe_list(act_q), header="PE"))
            if opt_dict.show_memory:
                act_line.extend([logging_tools.form_entry_right(act_h.get_memory_info("virtual_total"), header="v_tot"),
                                 logging_tools.form_entry_right(act_h.get_memory_info("virtual_free"), header="v_free")])
            act_line.extend([logging_tools.form_entry_right(act_h.get_avg_load(q_name), header="load"),
                             logging_tools.form_entry_right(act_h.get_slots_used(q_name), header="su"),
                             logging_tools.form_entry(act_h.get_slots_total(q_name), header="st"),
                             logging_tools.form_entry(act_h.get_init_complexes(act_q, init_complexes), header="complexes")])
            if opt_dict.show_acl:
                act_line.extend([logging_tools.form_entry(act_h.get_user_lists(act_q), header="userlists"),
                                 logging_tools.form_entry(act_h.get_project_lists(act_q), header="projects")])
            act_line.append(logging_tools.form_entry(act_h.get_job_info(s_info["qstat"], q_job_list), header="jobs"))
            out_list.append(act_line)
    if out_list:
        if opt_dict.interactive:
            return "%s\n%s" % (time.ctime(), out_list)
        else:
            print out_list

def scs(s_info, opt_dict):
    print time.ctime()
    # init.at complexes
    init_complexes = sorted([key for key, value in s_info["complexes"].iteritems() if value.complex_type == "i"])
    # builder helper dicts
    all_queues = sorted(s_info["queueconf"].keys())
    for q_name in all_queues:
        # expand various entries
        act_q = s_info["queueconf"][q_name]
        s_info.expand_host_list(q_name)
        #for exp_name, new_name in [("complex_values", "compl_values")]:
        for exp_name, with_values in [("complex_values", True),
                                      ("pe_list"       , False)]:
            act_q[exp_name] = s_info._parse_sge_values(act_q[exp_name], with_values)
        for h_name, c_dict in act_q["complex_values"].iteritems():
            if h_name == "":
                # add all hosts
                h_name = [h_name.split(".")[0] for h_name in act_q["hostlist"]]
            for ic_name, add_it in c_dict.iteritems():
                if ic_name in init_complexes:
                    s_info["complexes"][ic_name].add_queue_host(q_name, h_name)
    out_list = logging_tools.new_form_list()
    if opt_dict.show_queues:
        d_list = sum([[(ic_name, q_name) for q_name in sorted(s_info["complexes"][ic_name]["queues"].keys())] for ic_name in init_complexes], [])
        if opt_dict.sort_queues:
            d_list = [(ic_name, q_name) for q_name, ic_name in sorted([(q_n, ic_n) for ic_n, q_n in d_list])]
    else:
        d_list = [(ic_name, "") for ic_name in init_complexes]
    for ic_name, q_name in d_list:
        act_ic = s_info["complexes"][ic_name]
        act_line = [logging_tools.form_entry(ic_name, header="complex")]
        if q_name:
            act_line.append(logging_tools.form_entry_right(q_name, header="queue"))
        act_line.extend([logging_tools.form_entry_right(act_ic["num_min"], header="minslots"),
                         logging_tools.form_entry_right(act_ic["num_max"], header="maxslots"),
                         logging_tools.form_entry_right(act_ic["mt_time"], header="time total"),
                         logging_tools.form_entry_right(act_ic["m_time"], header="time/node"),
                         logging_tools.form_entry_right(act_ic.get_waiting(s_info["qstat"], [q_name])),
                         logging_tools.form_entry_right(act_ic.get_running(s_info["qstat"], [q_name]))])
        hq_list = act_ic.get_hq_list(s_info["qhost"], [q_name])
        act_line.extend([logging_tools.form_entry_right(len(hq_list), header="total"),
                         logging_tools.form_entry_right(len([True for qs, su, st in hq_list if su < st and qs in ["a", "-"]]), header="avail"),
                         logging_tools.form_entry_right(len([True for qs, su, st in hq_list if "a" in qs]), header="alarm"),
                         logging_tools.form_entry_right(len([True for qs, su, st in hq_list if set("uAdDEsSC").intersection(set(qs))]), header="error"),
                         logging_tools.form_entry(act_ic.get_queues(q_name), header="queues")])
        out_list.append(act_line)
    print out_list

def sls(s_info, opt_dict):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(0, 0, 0, 0, 0, abs(opt_dict.hours))
    db_con = mysql_tools.dbcon_container()
    dc = db_con.get_connection(SQL_ACCESS)
    nodes = opt_dict.nodes
    dc.execute("SELECT * FROM sge_host")
    node_dict = dict([(db_rec["sge_host_idx"], db_rec["host_name"]) for db_rec in dc.fetchall()])
    if "ALL" in nodes:
        n_str = ""
    else:
        n_str = " AND (%s)" % (" OR ".join(["s.sge_host=%d" % (key) for key, value in node_dict.iteritems() if value in nodes]) or "0")
    sql_str = "SELECT * FROM sge_log s WHERE s.sge_host AND TIMEDIFF(NOW(), s.date) < %d AND s.log_level >= %d%s ORDER BY date" % (abs(opt_dict.hours),
                                                                                                                                   opt_dict.log_level,
                                                                                                                                   n_str)
    dc.execute(sql_str)
    log_records = dc.fetchall()
    dc.release()
    del db_con
    if log_records:
        print "Showing %s between %s and %s" % (logging_tools.get_plural("log entry", len(log_records)),
                                                start_date.ctime(),
                                                end_date.ctime())
        all_queues = set([db_rec["sge_queue"] for db_rec in log_records])
        all_jobs = set([db_rec["sge_job"] for db_rec in log_records])
        queue_dict = {0 : "---"}
        job_dict = {0 : {"job_uid" : "---"}}
        dc.execute("SELECT * FROM sge_queue WHERE %s" % (" OR ".join(["sge_queue_idx=%d" % (q_idx) for q_idx in all_queues])))
        queue_dict.update(dict([(db_rec["sge_queue_idx"], db_rec["queue_name"]) for db_rec in dc.fetchall()]))
        dc.execute("SELECT * FROM sge_job WHERE %s" % (" OR ".join(["sge_job_idx=%d" % (q_idx) for q_idx in all_jobs])))
        job_dict.update(dict([(db_rec["sge_job_idx"], db_rec) for db_rec in dc.fetchall()]))
        out_list = logging_tools.new_form_list()
        num_entries = 0
        if opt_dict.node_sort:
            display_list = sorted(node_dict.values())
        else:
            display_list = [""]
        for disp_host in display_list:
            for db_rec in log_records:
                if not disp_host or node_dict.get(db_rec["sge_host"], "---") == disp_host:
                    num_entries += 1
                    new_line = [logging_tools.form_entry(db_rec["date"].strftime("%a, %d. %b %Y %H:%M:%S"), header="date"),
                                logging_tools.form_entry_right(queue_dict[db_rec["sge_queue"]], header="queue"),
                                logging_tools.form_entry(node_dict[db_rec["sge_host"]], header="node"),
                                logging_tools.form_entry(job_dict[db_rec["sge_job"]]["job_uid"], header="job"),
                                logging_tools.form_entry(db_rec["log_level"] if opt_dict.log_numeric else logging_tools.get_log_level_str(db_rec["log_level"]), header="lev"),
                                logging_tools.form_entry(db_rec["log_str"], header="entry")
                                ]
                    out_list.append(new_line)
        print out_list
    else:
        print "No logs found between %s and %s" % (start_date.ctime(),
                                                   end_date.ctime())

def sla(opt_dict, add_args):
    db_con = mysql_tools.dbcon_container()
    dc = db_con.get_connection(SQL_ACCESS)
    host_record = None
    if opt_dict.node:
        dc.execute("SELECT * FROM sge_host WHERE host_name=%s", (opt_dict.node))
        if dc.rowcount:
            host_record = dc.fetchone()
        else:
            dc.execute("SELECT * FROM device WHERE name=%s", (opt_dict.node))
            if dc.rowcount:
                dc.execute("INSERT INTO sge_host SET host_name=%s, device=%s", (opt_dict.node,
                                                                                dc.fetchone()["device_idx"]))
                print "Created a new sge_host record for host '%s'" % (opt_dict.node)
                dc.execute("SELECT * FROM sge_host WHERE sge_host_idx=%s", (dc.insert_id()))
                host_record = dc.fetchone()
            else:
                print "Host '%s' not found" % (opt_dict.node)
    else:
        print "No Host given"
    if host_record:
        if opt_dict.queue_name:
            dc.execute("SELECT * FROM sge_queue WHERE queue_name=%s", (opt_dict.queue_name))
            if dc.rowcount:
                queue_idx = dc.fetchone()["sge_queue_idx"]
            else:
                print "No Queue named '%s' found" % (opt_dict.queue_name)
                queue_idx = 0
        else:
            queue_idx = 0
        sql_str, sql_tuple = ("INSERT INTO sge_log SET sge_job=%s, sge_queue=%s, sge_host=%s, log_level=%s, log_str=%s",
                              (0,
                               queue_idx,
                               host_record["sge_host_idx"],
                               opt_dict.log_level,
                               add_args))
        dc.execute(sql_str, sql_tuple)
        print "Created sge_log entry"
    dc.release()

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
##    def handle_graph(self, head_node):
##        cur_node = head_node
##        self.run_flag = True
##        while self.run_flag:
##            cur_triggers = cur_node.get_triggers()
##            print self.terminal.green + ("\n%s (%s)" % (cur_node.question, ", ".join(cur_triggers)))
##            while self.run_flag:
##                cur_c = raw_input()
##                if cur_c and cur_c not in ['\n',' ']:
##                    if (cur_c) in cur_triggers:
##                        next_node = cur_node.follow_edge(cur_c)
##                        if next_node.action is None:
##                            cur_node = next_node
##                            break
##                        elif type(next_node.action) in [unicode, str]:
##                            print self.terminal.green + (next_node.action)
##                            if next_node.question is None:
##                                self.handle_graph(self._parent_node(cur_node))
##                        else:
##                            target_node = next_node.action(next_node)
##                            if target_node is not None:
##                                cur_node = target_node
##                                break
##                    else:
##                        print self.terminal.green + "invalid keypress"
##        print self.terminal.normal
        
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
            self.add_option("-u", dest="user", type="str", help="show only jobs of user [%default]", default="ALL")
            self.add_option("-c", dest="complexes", type="str", help="show only jobs with the given complexes [%default]", default="ALL")
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
        elif run_mode == "sls":
            self.add_option("-n", dest="nodes", help="set comma-separated nodenames [%default]", type="str", default="ALL")
            self.add_option("-H", dest="hours", help="number of hours to go back [%default]", type="int", default=4)
            self.add_option("-s", dest="node_sort", help="sort according to the nodename [%default]", action="store_true", default=False)
            self.add_option("-l", dest="log_level", help="minimum log_level to be displayed [%default]", type="int", default=0)
            self.add_option("--numeric", dest="log_numeric", help="show log_level as numeric value [%default]", action="store_true", default=False)
        elif run_mode == "sla":
            self.add_option("-n", dest="node", help="set nodename to add a logline to [%default]", type="str", default=None)
            self.add_option("-l", dest="log_level", help="set numeric log_level (0 ... ok, 5 ... warn, 10 ... error, 20 ... critical) [%default]", type="int", default=10)
            self.add_option("--warn", dest="log_level", help="set log_level to warn", action="store_const", const=5)
            self.add_option("--error", dest="log_level", help="set log_level to error", action="store_const", const=10)
            self.add_option("--critical", dest="log_level", help="set log_level to critical", action="store_const", const=20)
            self.add_option("-q", dest="queue_name", help="set queue_name for log_entry [%default]", type="str", default=None)
        self.add_option("-v", dest="verbose", help="set verbose mode [%default]", action="store_true", default=False)
            #self.add_option("--max-devices", dest="max_devices", type="int", help="set maximum number of devices to scan, defaults to 0 (unlimited)", default=0)
        
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
    s_time = time.time()
    check_environment()
    run_mode = {"sgelogstat"     : "sls",
                "sls"            : "sls",
                "sgejobstat"     : "sjs",
                "sgenodestat"    : "sns",
                "sgecomplexstat" : "scs",
                "sgelogadd"      : "sla",
                "sla"            : "sla",
                "sjs"            : "sjs",
                "sns"            : "sns",
                "scs"            : "scs"}.get(os.path.basename(sys.argv[0]), "sjs")
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
    # check for right user
    if run_mode in ["sls", "sla"]:
        if os.getuid():
            print "Need to be root for %s" % (run_mode)
            return
    if run_mode not in ["sla"]:
        act_si = sge_tools.sge_info(update_pref={"qhost"     : [],
                                                 "complexes" : ["server"],
                                                 "hostgroup" : ["server"],
                                                 "qstat"     : [],
                                                 "queueconf" : ["server"]},
                                    verbose=options.verbose,
                                    log_command=log_com,
                                    server=get_server())
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
                                           dt_edge("y", dt_node(None, action="print")),
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
    elif run_mode == "scs":
        scs(act_si, options)
    elif run_mode == "sls":
        sls(act_si, options)
    elif run_mode == "sla":
        sla(options, add_args)
    else:
        print "Unknown runmode %s" % (run_mode)
    e_time = time.time()
    if not options.interactive:
        print "took %s" % (logging_tools.get_diff_time_str(e_time - s_time))
    
if __name__ == "__main__":
    main()
