#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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

from initat.host_monitoring import limits, hm_classes
import commands
import logging_tools
import re
import sys

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "lmstat",
                                        "provides a interface to check the status of flexlm License-Servers",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        pass

class lmstat_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "lmstat", **args)
        self.cache_timeout = 600
        self.is_immediate = False
        self.help_str = "returns the status of a given lmstat-command"
        self.short_client_info = "lmstat_bin [LIC_FILE]"
        self.long_client_info = "location of the lmstat or lmutil binary and optional license-file location"
    def server_call(self, cm):
        if len(cm) >= 1:
            lmstat_bin = cm[0]
            if len(cm) >= 2:
                lic_file_loc = " -c %s" % (cm[1])
            else:
                lic_file_loc = ""
            if lmstat_bin.endswith("util"):
                lm_call = "%s lmstat -a%s" % (lmstat_bin, lic_file_loc)
            else:
                lm_call = "%s -a%s" % (lmstat_bin, lic_file_loc)
            stat, out = commands.getstatusoutput(lm_call)
            if stat:
                return "error calling %s (%d): %s" % (lmstat_bin, stat, out)
            else:
                s_dict = parse_lmstat_out(out)
                return "ok %s" % (hm_classes.sys_to_net(s_dict))
        else:
            return "error no lmstat or lmutil binary given"
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            l_dict = hm_classes.net_to_sys(result[3:])
            feat_list = parse_features(l_dict["attributes"])
            if l_dict.has_key("server_port") and l_dict.has_key("server_name"):
                # old version
                s_port, s_name = (l_dict["server_port"],
                                  l_dict["server_name"])
                return limits.nag_STATE_OK, "ok %s (port %d); %s: %s" % (s_name,
                                                                         s_port,
                                                                         logging_tools.get_plural("feature", len(feat_list)),
                                                                         ", ".join(feat_list))
            elif l_dict.has_key("servers") and l_dict.has_key("server_status"):
                # num servers
                num_servers = len(l_dict["servers"])
                servers_up   = sorted([k for k, v in l_dict["server_status"].iteritems() if v.lower().count("server up")])
                servers_down = sorted([k for k, v in l_dict["server_status"].iteritems() if k not in servers_up])
                if servers_down:
                    return limits.nag_STATE_CRITICAL, "error %s down: %s, %s up: %s; %s: %s" % (
                        logging_tools.get_plural("server", len(servers_down)),
                        ", ".join(servers_down),
                        logging_tools.get_plural("server", len(servers_up)),
                        ", ".join(servers_up),
                        logging_tools.get_plural("feature", len(feat_list)),
                        ", ".join(feat_list))
                else:
                    num_features = len(feat_list)
                    if num_features:
                        ret_state, ret_str = (limits.nag_STATE_OK, "ok")
                    else:
                        ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error")
                    return ret_state, "%s %s up: %s; %s%s" % (
                        ret_str,
                        logging_tools.get_plural("server", len(servers_up)),
                        ", ".join(servers_up),
                        logging_tools.get_plural("feature", len(feat_list)),
                        feat_list and ": %s" % (", ".join(feat_list)) or "")
            else:
                return limits.nag_STATE_CRITICAL, "error no server_port or server_name key in response"
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

def parse_lmstat_out(out):
    stat_re = re.compile("^License server status: (?P<lic_info>\S+).*$")
    users_re = re.compile("^Users of (?P<attribute>\S+): .* of (?P<total>\d+) .* of (?P<used>\d+).*$")
    r_dict = {"attributes" : {}}
    act_mode = "not set"
    for line in [y for y in [x.strip() for x in out.split("\n")] if y]:
        if act_mode == "not set":
            stat_mo = stat_re.match(line)
            if stat_mo:
                r_dict["servers"] = [tuple(server_part.split("@")) for server_part in stat_mo.group("lic_info").split(",")]
                r_dict["server_status"] = dict([(y, "not set") for x, y in r_dict["servers"]])
                act_mode = "server stuff"
        elif act_mode == "server stuff":
            srv_name = line.split(":")[0]
            if srv_name in r_dict["server_status"].keys():
                r_dict["server_status"][srv_name] = line.split(":", 1)[1]
            if line.lower().startswith("feature usage info"):
                act_mode = "feature stuff"
        elif act_mode == "feature stuff":
            users_mo = users_re.match(line)
            if users_mo:
                attribute, total, used = (users_mo.group("attribute"),
                                          int(users_mo.group("total")),
                                          int(users_mo.group("used")))
                r_dict["attributes"][attribute] = (total, used)
    return r_dict

def parse_features(in_dict):
    a_names = sorted(in_dict.keys())
    a_list = []
    for a_name in a_names:
        total, used = in_dict[a_name]
        if total == used:
            if total == 1:
                a_info = "in use"
            else:
                a_info = "all %d in use" % (total)
        else:
            if used:
                a_info = "%d of %d" % (used, total)
            else:
                if total == 1:
                    a_info = "is free"
                else:
                    a_info = "all %d free" % (total)
        a_list.append("%s (%s)" % (a_name, a_info))
    return a_list
    
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
