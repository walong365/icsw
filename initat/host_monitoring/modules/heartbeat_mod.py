#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010,2012 Andreas Lang-Nevyjel, init.at
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

import sys
import commands
from initat.host_monitoring import limits, hm_classes
import os
import os.path
import logging_tools
import contextlib
import pprint
import process_tools
import server_command
from lxml import etree

class _general(hm_classes.hm_module):
    def _exec_command(self, com, **kwargs):
        c_stat, c_out = commands.getstatusoutput(com)
        if kwargs.get("full_output", False):
            return c_out, c_stat
        else:
            if c_stat:
                self.log("cannot execute %s (%d): %s" % (com, c_stat, c_out), logging_tools.LOG_LEVEL_WARN)
                c_out = ""
            return c_out.split("\n")
                    
class corosync_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        # not beautifull, FIXME ...
        c_out, c_stat = self.module._exec_command("/usr/sbin/corosync-cfgtool -s", full_output=True)
        srv_com["corosync_status"] = c_out
        srv_com["corosync_status"].attrib["status"] = "%d" % (c_stat)
    def interpret(self, srv_com, cur_ns): 
        coro_node = srv_com["corosync_status"]
        coro_stat = int(coro_node.attrib.get("status", "0"))
        lines = (coro_node.text or "").split("\n")
        return self._interpret(lines, cur_ns, status=coro_stat)
    def interpret_old(self, result, cur_ns):
        return self._interpret(hm_classes.net_to_sys(result[3:]), cur_ns)
    def _parse_lines(self, lines):
        r_dict = {"node_id" : "???",
                  "rings"   : {}}
        for line in lines:
            line = line.rstrip()
            if line:
                if line.lower().startswith("local node"):
                    r_dict["node_id"] = line.split()[-1]
                elif line.lower().startswith("ring id"):
                    ring_id = int(line.lower().split()[-1])
                    r_dict["rings"][ring_id] = {"id"     : "...",
                                                "status" : "unknown"}
                    cur_ring_id = ring_id
                elif ord(line[0]) == 9:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key in r_dict["rings"][cur_ring_id]:
                        r_dict["rings"][cur_ring_id][key] = value.strip()
        return r_dict
    def _interpret(self, r_lines, parsed_coms, **kwargs):
        coro_stat = kwargs.get("status", 0)
        if coro_stat:
            ret_state, out_f = (limits.nag_STATE_CRITICAL, r_lines)
        else:
            hb_dict = self._parse_lines(r_lines)
            ret_state, out_f = (limits.nag_STATE_OK, ["node_id is %s" % (hb_dict["node_id"])])
            ring_keys = sorted(hb_dict["rings"].keys())
            if ring_keys:
                for ring_key in ring_keys:
                    ring_dict = hb_dict["rings"][ring_key]
                    ring_stat = ring_dict["status"]
                    match_str = "ring %d" % (ring_key)
                    if ring_stat.lower().startswith(match_str):
                        ring_stat = ring_stat[len(match_str) : ].strip()
                    out_f.append("ring %d: id %s, %s" % (ring_key,
                                                         ring_dict["id"],
                                                         ring_stat))
                    if not ring_stat.lower().count("no faults"):
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            else:
                out_f.append("no rings defined")
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
        return ret_state, ", ".join(out_f)

class heartbeat_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["heartbeat_info"] = {"host"   : process_tools.get_machine_name(),
                                     "output" : self.module._exec_command("/usr/sbin/crm_mon -1")}
    def interpret(self, srv_com, cur_ns): 
        return self._interpret(srv_com["heartbeat_info"], cur_ns)
    def interpret_old(self, result, parsed_coms):
        return self._interpret(hm_classes.net_to_sys(result[3:]), parsed_coms)
    def _interpret(self, r_dict, parsed_coms):
        if type(r_dict) == type([]):
            r_dict = {"output" : r_dict,
                      "host"   : ""}
        hb_dict = self._parse_lines(r_dict)
        ret_state, out_f = (limits.nag_STATE_OK, [])
        out_f.append("stack is %s (%s), DC is %s" % (hb_dict["stack"],
                                                     hb_dict["version"],
                                                     hb_dict["current_dc"]))
        for online in [False, True]:
            nodes = [name for name, stuff in hb_dict["nodes"].iteritems() if stuff["online"] == online]
            if nodes:
                out_f.append("%s(%d): [%s]" % ("online" if online else "offline",
                                               len(nodes),
                                               logging_tools.compress_list(nodes)))
                if not online:
                    ret_state = max(ret_state, limits.nag_STATE_WARNING)
        for res_name in sorted(hb_dict["resources"]):
            stuff = hb_dict["resources"][res_name]
            if "node" in stuff:
                out_f.append("%s on %s" % (res_name,
                                           stuff["node"]))
            else:
                out_f.append(res_name)
        return ret_state, ", ".join(out_f)
    def _parse_lines(self, in_dict, **kwargs):
        only_local_resources = kwargs.get("only_local_resources", True)
        local_node = in_dict["host"]
        r_dict = {"stack"      : "unknown",
                  "current_dc" : "unknown",
                  "version"    : "unknown",
                  "nodes"      : {},
                  "resources"  : {}}
        act_mode = "???"
        for line in in_dict["output"]:
            line = line.strip()
            if line:
                first_word = line.split()[0].lower()
                if line.startswith("====="):
                    act_mode = {"???"  : "head",
                                "head" : "main"}[act_mode]
                else:
                    if act_mode == "head":
                        if line.count(":"):
                            key, value = line.split(":", 1)
                            key = key.lower().strip().replace(" ", "_")
                            if key in ["stack"]:
                                r_dict[key] = value.strip()
                            elif key in ["current_dc"]:
                                r_dict[key] = value.split()[0].strip()
                            elif key in ["version"]:
                                r_dict[key] = value.split("-")[0].strip()
                    elif act_mode == "main":
                        if first_word.startswith("online") or first_word.startswith("offline"):
                            node_list = line.split("[")[1].split("]")[0].strip().split()
                            online = first_word.startswith("online")
                            for node in node_list:
                                r_dict["nodes"][node] = {"online" : online}
                        else:
                            line_split = line.lower().split()
                            if len(line_split) == 4:
                                res_name, res_type, res_status, res_node = line_split
                                res_node = res_node.split(".")[0]
                                if (res_node == local_node and only_local_resources):
                                    r_dict["resources"][res_name] = {"type"   : res_type,
                                                                     "status" : res_status}
                                elif (not only_local_resources) or (not local_node):
                                    r_dict["resources"][res_name] = {"type"   : res_type,
                                                                     "status" : res_status,
                                                                     "node"   : res_node}
        return r_dict

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
