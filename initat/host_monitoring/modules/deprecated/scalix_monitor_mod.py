#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel, init.at
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
import os
import os.path
import time
from initat.host_monitoring import limits
from initat.tools import logging_tools
import commands
from initat.host_monitoring import hm_classes
from initat.tools import process_tools
import pprint

SCALIX_QUEUES = ["BB",
                 "DIRSYNC",
                 "DMM",
                 "DUMP",
                 "ERRMGR",
                 "ERROR",
                 "LICENSE",
                 "LOCAL",
                 "PRINT",
                 "REQ",
                 "RESOLVE",
                 "ROUTER",
                 "SMERR",
                 "SMINTFC",
                 "TEST",
                 "UNIX"]


class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(
            self,
            "scalix_monitor",
            "monitors scalix servers",
            **args
        )

    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__exe_dict = {}
            exe_search = [("omstat", ["/opt/scalix/bin/omstat"]),
                          ("omshowu", ["/opt/scalix/bin/omshowu"]),
                          ("sxdu", ["/opt/scalix/bin/sxdu"]),
                          ("omsetsvc", ["/opt/scalix/bin/omsetsvc"]),
                          ("omshowlvl", ["/opt/scalix/bin/omshowlvl"]),
                          ("omlimit", ["/opt/scalix/bin/omlimit"])]
            for stat_name, search_list in exe_search:
                self.__exe_dict[stat_name] = None
                for name in search_list:
                    if os.path.exists(name):
                        self.__exe_dict[stat_name] = name
                        logger.info("Found %s at %s" % (stat_name, name))
                        break
            self.__services = {}
            act_service = None
            for line in commands.getoutput("%s -e" % (self.__exe_dict["omsetsvc"])).split("\n"):
                if line.startswith("Details"):
                    if act_service:
                        self.__services[act_service["full_name"]] = act_service
                    full_name = " ".join(line.split()[3:])[:-1]
                    act_service = {"full_name": full_name,
                                   "abbrevs": []}
                else:
                    if line.startswith("PID"):
                        act_service["pids"] = [int(pid.strip()) for pid in (" ".join(line.strip().split(":")[1:])).split() if pid.strip()]
                    elif line.count("\t= ") or line.count("\t-."):
                        if line.count("\t= "):
                            key, value = line.split("=", 1)
                        else:
                            key, value = line.split("-", 1)
                        if value.isdigit():
                            value = int(value)
                        act_service[key.strip()] = value.strip()
                        # print full_name, full_name in self.__services.keys()
            if act_service:
                self.__services[act_service["full_name"]] = act_service
            act_name = ""
            for line in commands.getoutput("%s -l" % (self.__exe_dict["omshowlvl"])).split("\n"):
                if line.strip():
                    if not line.startswith("\t"):
                        act_name = line.strip()
                    else:
                        if act_name in self.__services:
                            self.__services[act_name]["abbrevs"].append(line.strip())
            # build lookup-dict
            self.__service_lut = {}
            for full_name, service in self.__services.iteritems():
                self.__service_lut[full_name] = service
                for abbr in service["abbrevs"]:
                    self.__service_lut[abbr] = service
                    # pprint.pprint(self.__services.keys())

    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            if hmb.name in ["mailq"]:
                if opt == "-w":
                    if my_lim.set_warn_val(arg) == 0:
                        ok, why = (0, "Can't parse warning value !")
                if opt == "-c":
                    if my_lim.set_crit_val(arg) == 0:
                        ok, why = (0, "Can't parse critical value !")
        return ok, why, [my_lim]

    def get_queue_stat(self, queue_names):
        com_name = "omstat"
        if self.__exe_dict[com_name]:
            res_dict = {}
            for queue_name in queue_names or SCALIX_QUEUES:
                try:
                    cstat, result = commands.getstatusoutput("%s -q %s" % (self.__exe_dict[com_name], queue_name))
                    if cstat:
                        res_dict[queue_name] = "error %s gave (%d) %s" % (com_name, cstat, result)
                    else:
                        res_dict[queue_name] = "ok %s" % (result)
                except:
                    res_dict[queue_name] = "error calling %s: %s" % (self.__exe_dict[com_name],
                                                                     process_tools.get_except_info())
            return "ok %s" % (hm_classes.sys_to_net(res_dict))
        else:
            return "error %s command not found" % (com_name)

    def get_user_list(self):
        com_name = "omshowu"
        if self.__exe_dict[com_name]:
            try:
                cstat, result = commands.getstatusoutput("%s -m all" % (self.__exe_dict[com_name]))
                if cstat:
                    return "error %s gave (%d) %s" % (com_name, cstat, result)
                else:
                    u_list = [line.split("/")[0].strip() for line in result.split("\n")]
                    return "ok %s" % (hm_classes.sys_to_net(u_list))
            except:
                return "error calling %s: %s" % (self.__exe_dict[com_name],
                                                 process_tools.get_except_info())
        else:
            return "error %s command not found" % (com_name)

    def get_user_info(self, user_name):
        com_name = "omshowu"
        if self.__exe_dict[com_name]:
            try:
                cstat, result = commands.getstatusoutput("%s -n '%s' -f" % (self.__exe_dict[com_name],
                                                                            user_name))
                if cstat:
                    return "error %s gave (%d) %s" % (com_name, cstat, result)
                else:
                    u_dict = dict([(key.lower().strip().replace(" ", "_"), value.strip()) for key, value in
                                   [line.split(":", 1) for line in result.split("\n") if line.count(":")]])
                    total_size = 0
                    if self.__exe_dict["sxdu"]:
                        try:
                            cstat, result = commands.getstatusoutput("%s -a '%s'" % (self.__exe_dict["sxdu"],
                                                                                     user_name))
                        except:
                            pass
                        else:
                            total_size = int(result.split()[0]) * 1024
                    if self.__exe_dict["omlimit"]:
                        try:
                            cstat, result = commands.getstatusoutput("%s -u '%s' -r" % (self.__exe_dict["omlimit"],
                                                                                        user_name))
                        except:
                            pass
                        else:
                            if not cstat:
                                for key, value in [line.strip().split(":", 1) for line in result.split("\n") if line.count(":")]:
                                    key = key.strip()
                                    value = value.strip()
                                    if key.lower() == "message store size limit":
                                        if value.lower().endswith("kb"):
                                            u_dict["max_size"] = int(value[:-2]) * 1024
                    u_dict["total_size"] = total_size
                    return "ok %s" % (hm_classes.sys_to_net(u_dict))
            except:
                return "error calling %s: %s" % (com_name,
                                                 process_tools.get_except_info())
        else:
            return "error %s command not found" % (com_name)

    def get_service_info(self, service_name):
        com_name = "omstat"
        if self.__exe_dict[com_name]:
            try:
                cstat, result = commands.getstatusoutput("%s -s ; %s -a" % (self.__exe_dict[com_name],
                                                                            self.__exe_dict[com_name]))
                if cstat:
                    return "error %s gave (%d) %s" % (com_name, cstat, result)
                else:
                    act_dict = {}
                    for l_p in [line.strip().split() for line in result.split("\n")]:
                        if l_p[-1].isdigit():
                            num_subs = int(l_p.pop(-1))
                        else:
                            num_subs = -1
                        start_date = l_p.pop(-1)
                        act_state = l_p.pop(-1)
                        act_name = " ".join(l_p)
                        act_dict[act_name] = {"name": act_name,
                                              "num_sub": num_subs,
                                              "start_date": start_date,
                                              "act_state": act_state}
                    if service_name:
                        act_dict = act_dict.get(service_name, {})
                    return "ok %s" % (hm_classes.sys_to_net(act_dict))
            except:
                return "error calling %s: %s" % (self.__exe_dict[com_name],
                                                 process_tools.get_except_info())


class scalix_queue_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "scalix_queue", **args)
        self.help_str = "checks the number of entries in a given queue"
        self.short_client_info = "-w N1, -c N2"
        self.long_client_info = "sets the warning and critical values for the mailsystem"
        self.short_client_opts = "w:c:"

    def server_call(self, cm):
        return self.module_info.get_queue_stat(cm)

    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        result = hm_classes.net_to_sys(result[3:])
        return limits.nag_STATE_OK, "OK: %s: %s" % (logging_tools.get_plural("queue", len(result)),
                                                    ", ".join(["%s: %s" % (q_name, result[q_name]) for q_name in sorted(result.keys())]))


class scalix_users_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "scalix_users", **args)
        self.help_str = "returns the scalix userlist"

    def server_call(self, cm):
        return self.module_info.get_user_list()

    def client_call(self, result, parsed_coms):
        u_list = hm_classes.net_to_sys(result[3:])
        return limits.nag_STATE_OK, "OK: %s" % (logging_tools.get_plural("user", len(u_list)))


class scalix_userlist_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "scalix_userlist", **args)
        self.help_str = "returns the detailed scalix userlist"

    def server_call(self, cm):
        return self.module_info.get_user_list()

    def client_call(self, result, parsed_coms):
        u_list = sorted(hm_classes.net_to_sys(result[3:]))
        return limits.nag_STATE_OK, "OK: %s\n%s" % (logging_tools.get_plural("user", len(u_list)),
                                                    "\n".join(u_list))


class scalix_userinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "scalix_userinfo", **args)
        self.help_str = "returns scalix userinfo"

    def server_call(self, cm):
        return self.module_info.get_user_info(" ".join(cm))

    def client_call(self, result, parsed_coms):
        u_dict = hm_classes.net_to_sys(result[3:])
        # pprint.pprint(u_dict)
        ret_state = limits.nag_STATE_OK
        used = u_dict["total_size"]
        if "max_size" in u_dict:
            max_size = u_dict["max_size"]
            perc_used = 100. * float(used) / float(max_size)
            quota_perc = "%.2f %%" % (perc_used)
            quota_info = "%s of %s" % (quota_perc, logging_tools.get_size_str(max_size, long_version=True).strip())
            if perc_used > 100:
                ret_state = limits.nag_STATE_CRITICAL
                used_info = "over quota (%s)" % (quota_info)
            elif perc_used > 80:
                ret_state = limits.nag_STATE_WARNING
                used_info = "reaching quota (%s)" % (quota_info)
            else:
                used_info = "quota ok (%s)" % (quota_info)
        else:
            used_info = "no quota info"
        account_stat = u_dict.get("mail_account", "unknown")
        if account_stat.lower() != "unlocked":
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
        return ret_state, "%s %s (%s), used size is %s, %s" % (limits.get_state_str(ret_state),
                                                               (u_dict.get("user_name", "name not set").split("/")[0]).strip(),
                                                               account_stat,
                                                               used and logging_tools.get_size_str(used, long_version=True).strip() or "not known",
                                                               used_info)


class scalix_serviceinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "scalix_serviceinfo", **args)
        self.help_str = "returns scalix serviceinfo"

    def server_call(self, cm):
        return self.module_info.get_service_info(" ".join(cm))

    def client_call(self, result, parsed_coms):
        s_dict = hm_classes.net_to_sys(result[3:])
        # pprint.pprint(s_dict)
        if s_dict:
            ret_state = limits.nag_STATE_OK
            if s_dict["act_state"].lower() not in ["enabled", "started"]:
                ret_state = limits.nag_STATE_CRITICAL
            ret_str = "%s: %s %s" % (limits.get_state_str(ret_state),
                                     s_dict["name"],
                                     s_dict["act_state"])
        else:
            ret_state, ret_str = limits.nag_STATE_CRITICAL, "Error no info found"
        return ret_state, ret_str


if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
