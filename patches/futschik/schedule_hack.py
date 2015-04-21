#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang
#
# Send feedback to: <lang@init.at>
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

import sys
import commands
from initat.tools import logging_tools
import xml
import xml.dom.minidom
import xml.parsers.expat
import pprint
import time

def getText(nodelist):
    return "".join([node.data for node in nodelist if node.nodeType == node.TEXT_NODE])

class queue(object):
    def __init__(self, xml_ent):
        self.__full_queue_name = str(getText(xml_ent.getElementsByTagName("name")[0].childNodes))
        self.__queue_name = self.__full_queue_name.split("@")[0]
        self.__node_name = self.__full_queue_name.split("@")[1]
        state_elements = xml_ent.getElementsByTagName("state")
        if state_elements:
            self.__state = str(getText(state_elements[0].childNodes))
        else:
            self.__state = "-"
        self.__slots_used  = int(xml_ent.getElementsByTagName("slots_used")[0].childNodes[0].data)
        self.__slots_total = int(xml_ent.getElementsByTagName("slots_total")[0].childNodes[0].data)
    def get_queue_name(self):
        return self.__queue_name
    def get_free_slots(self):
        if self.__state in ["-", "a"]:
            return self.__slots_total - self.__slots_used
        else:
            return 0

class job(object):
    def __init__(self, xml_ent):
        self.__owner = str(getText(xml_ent.getElementsByTagName("JB_owner")[0].childNodes))
        self.__state = str(getText(xml_ent.getElementsByTagName("state")[0].childNodes))
        self.__job_id = str(getText(xml_ent.getElementsByTagName("JB_job_number")[0].childNodes))
        queue_el = xml_ent.getElementsByTagName("hard_req_queue")
        if queue_el:
            self.__queue_request = str(getText(queue_el[0].childNodes))
        else:
            self.__queue_request = ""
        task_el = xml_ent.getElementsByTagName("tasks")
        if task_el:
            self.__job_task_id = str(getText(task_el[0].childNodes))
        else:
            self.__job_task_id = ""
        self.__queue = None
        self.__group = "unknown"
        self.__action, self.__why = ("-", "")
    def get_state(self):
        return self.__state
    def get_owner_group_info(self):
        return "user %s, group %s" % (self.__owner, self.__group)
    def get_job_id(self):
        return self.__job_id
    def get_full_job_id(self):
        # return job_id with task_id
        if self.__job_task_id:
            return "%s.%s" % (self.__job_id, self.__job_task_id)
        else:
            return self.__job_id
    def get_queue_request(self):
        return self.__queue_request
    def set_action(self, what, why):
        if what == "h" and "h" in self.__state:
            pass
        else:
            self.__action, self.__why = (what, why)
    def get_action(self):
        return self.__action, self.__why
    def set_queue(self, q):
        self.__queue = q
    def set_group(self, u_dict):
        group_found = False
        for ul_name, ul_stuff in u_dict.iteritems():
            if self.__owner in ul_stuff["users"]:
                self.__group = ul_name
                group_found = True
                break
        if not group_found:
            # unknown is my group
            ul_stuff = u_dict[self.__group]
            if self.__owner not in ul_stuff["users"]:
                ul_stuff["users"].append(self.__owner)
    def get_group(self):
        return self.__group
    def get_owner(self):
        return self.__owner

def get_user_dict():
    user_dict = dict([(x.strip(), {"users" : []}) for x in commands.getstatusoutput("qconf -sul")[1].split("\n") + ["unknown"]])
    for ul_name in user_dict.keys():
        stat, out = commands.getstatusoutput("qconf -su %s" % (ul_name))
        if not stat:
            act_lines = out.split("\n")
            new_lines = []
            add_next_line = False
            for act_line in act_lines:
                anl = add_next_line
                if act_line.endswith("\\"):
                    add_next_line = True
                    act_line = act_line[:-1]
                else:
                    add_next_line = False
                if anl:
                    new_lines[-1] += act_line.strip()
                else:
                    new_lines.append(act_line)
            entry_line = dict([(x, y) for x, y in [line.split(None, 1) for line in new_lines]]).get("entries", "")
            if entry_line.lower() != "none":
                user_dict[ul_name]["users"] = [x.strip() for x in entry_line.split(",") if x.strip()]
    return user_dict

def main():
    inner_loop_time = 60
    check_user_dict_every = 5
    inner_loop_counter = check_user_dict_every
    while True:
        inner_loop_counter += 1
        if inner_loop_counter > check_user_dict_every:
            print "Checking user_dict"
            user_dict = get_user_dict()
        # add hold_list (queue -> groups to hold)
        hold_dict = {"pom"  : ["biostat", "seds", "unknown"],
                     "bssd" : ["pom", "unknown"]}
        stat, out = commands.getstatusoutput("qstat -xml -f -r")
        xml_doc = xml.dom.minidom.parseString(out)
        # find job_info entity
        sge_node = xml_doc.getElementsByTagName("job_info")[0]
        queue_info = sge_node.getElementsByTagName("queue_info")[0]
        queue_list = []
        job_run_list, job_wait_list = ([], [])
        for queue_info in queue_info.getElementsByTagName("Queue-List"):
            new_queue = queue(queue_info)
            queue_list.append(new_queue)
            for job_info in queue_info.getElementsByTagName("job_list"):
                run_job = job(job_info)
                run_job.set_queue(new_queue)
                job_run_list.append(run_job)
        wait_job_info = sge_node.getElementsByTagName("job_info")[0]
        for job_info in wait_job_info.getElementsByTagName("job_list"):
            wait_job = job(job_info)
            wait_job.set_group(user_dict)
            job_wait_list.append(wait_job)
        # build queue_dict (queue_name -> free_slots)
        q_dict = {}
        for q in queue_list:
            q_dict.setdefault(q.get_queue_name(), {"free_slots"               : 0,
                                                   "jobs_waiting_allowed"     : [],
                                                   "jobs_waiting_not_allowed" : []})
            q_dict[q.get_queue_name()]["free_slots"] += q.get_free_slots()
        # check pre-actions for waiting jobs
        for wait_job in job_wait_list:
            if not wait_job.get_queue_request():
                wait_job.set_action("h", "no default-queue set")
        for q_name, u_lists in hold_dict.iteritems():
            if hold_dict.has_key(q_name):
                hold_user_list = hold_dict[q_name]
                for wait_job in job_wait_list:
                    j_q_req, j_group = (wait_job.get_queue_request(), wait_job.get_group())
                    if q_name == j_q_req and q_dict.has_key(j_q_req):
                        q_stuff = q_dict[j_q_req]
                        #print "*", q_name, wait_job.get_job_id(), wait_job.get_owner_group_info(), j_group in hold_user_list
                        if j_group in hold_user_list:
                            q_stuff["jobs_waiting_not_allowed"].append(wait_job)
                        else:
                            q_stuff["jobs_waiting_allowed"].append(wait_job)
    ##                     if q_dict["free_slots"][q_name]:
    ##                         # only unhold jobs if no permitted users have pending jobs for this queue
    ##                         wait_job.set_action("u", "requested queue %s is not full" % (q_name))
    ##                     else:
    ##                         wait_job.set_action("h", "requested queue %s is full" % (q_name))
        # hold or unhold jobs
        for q_name, q_stuff in q_dict.iteritems():
            if q_stuff["free_slots"] and not q_stuff["jobs_waiting_allowed"]:
                # unhold all not_allowed jobs
                for wait_job in q_stuff["jobs_waiting_not_allowed"]:
                    wait_job.set_action("u", "queue %s is not full and no allowed jobs waiting" % (q_name))
                # unhold all allowed waiting jobs, hold all not_allowed jobs
                for wait_job in q_stuff["jobs_waiting_allowed"]:
                    wait_job.set_action("u", "job is allowed")
            else:
                for wait_job in q_stuff["jobs_waiting_not_allowed"]:
                    wait_job.set_action("h", "queue %s is full or allowed jobs waiting" % (q_name))
                for wait_job in q_stuff["jobs_waiting_allowed"]:
                    wait_job.set_action("u", "job is allowed")
        hold_dict, unhold_dict = ({}, {})
        for wait_job in job_wait_list:
            action, why = wait_job.get_action()
            #print wait_job.get_owner(), wait_job.get_full_job_id(), wait_job.get_group(), action, why
            if action == "h" and "h" not in wait_job.get_state():
                hold_dict[wait_job.get_full_job_id()] = (wait_job, why)
            elif action == "u" and "h" in wait_job.get_state():
                unhold_dict[wait_job.get_full_job_id()] = (wait_job, why)
        if hold_dict:
            hold_list = hold_dict.keys()
            hold_list.sort()
            print "%s to hold: %s" % (logging_tools.get_plural("Job", len(hold_list)),
                                      ", ".join(["%s (%s): %s" % (x, hold_dict[x][0].get_owner_group_info(), hold_dict[x][1]) for x in hold_list]))
            commands.getstatusoutput("qhold -h s %s" % (" ".join(hold_list)))
        if unhold_dict:
            unhold_list = unhold_dict.keys()
            unhold_list.sort()
            print "%s to unhold: %s" % (logging_tools.get_plural("Job", len(unhold_list)),
                                        ", ".join(["%s (%s): %s" % (x, unhold_dict[x][0].get_owner_group_info(), unhold_dict[x][1]) for x in unhold_list]))
            commands.getstatusoutput("qrls -h s %s" % (" ".join(unhold_list)))
        time.sleep(inner_loop_time)

if __name__ == "__main__":
    main()
