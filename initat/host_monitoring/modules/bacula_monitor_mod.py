#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008,2012 Andreas Lang-Nevyjel, init.at
# (C) 2010 SK, IMS Nanofabrication AG
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
from initat.host_monitoring import limits, hm_classes
import logging_tools
import commands
import process_tools
import pprint

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "bacula_monitor",
                                        "monitors bacula jobs",
                                        **args)
    def init(self, mode, log_template, basedir_name, **args):
        if mode == "i":
            self.__exe_dict = {}
            exe_search = [("checklastjob", ["/etc/bacula/check_last_job.pl"]),
	        	    ("checkbacula", ["/etc/bacula/check_bacula.pl"]),
			    ("bconsole", ["/usr/sbin/bconsole"])]
            for stat_name, search_list in exe_search:
                self.__exe_dict[stat_name] = None
                for name in search_list:
                    if os.path.exists(name):
                        self.__exe_dict[stat_name] = name
                        log_template.log("Found %s at %s" % (stat_name, name))
                        break
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            if hmb.name in ["jobinfo"]:
                if opt == "-w":
                    if my_lim.set_warn_val(arg) == 0:
                        ok, why = (0, "Can't parse warning value !")
                if opt == "-c":
                    if my_lim.set_crit_val(arg) == 0:
                        ok, why = (0, "Can't parse critical value !")
        return ok, why, [my_lim]
    def get_job_stat(self, jobargs):
        com_name = "checklastjob"
        if self.__exe_dict[com_name]:
            res_dict = {}
        try:
#            print "command= %s -client %s -warningAge=0" % (self.__exe_dict[com_name], jobargs[0])
            cmd = "%s -client %s" % (self.__exe_dict[com_name], jobargs[0])
            if len(jobargs) > 1:
                print "got 2nd arg"
                cmd+=" -warningAge=%s" % (jobargs[1])
            if len(jobargs) > 2:
                print "got 3rd arg"
                cmd+=" -criticalAge=%s" % (jobargs[2])
#            print "command= %s" % (cmd)
            cstat, result = commands.getstatusoutput( cmd )
#            print "result:", cstat, result
            j_dict=dict([("status",0),("message",result)])
            if cstat==256: #got warning message
                j_dict["status"]=cstat
                cstat=0
            if cstat==512: #got critical message
                j_dict["status"]=cstat
                cstat=0				
            if cstat:
                return "error %s gave (%d) %s" % (com_name, cstat, result)
            else:
                return "ok %s" % (hm_classes.sys_to_net(j_dict))
        except:
            return "error calling %s: %s" % (self.__exe_dict[com_name], process_tools.get_except_info())
        else:
            return "error %s command not found" % (com_name)
#dummy
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
#dummy
    def get_user_info(self, user_name):
        com_name = "omshowu"
        if self.__exe_dict[com_name]:
            try:
                cstat, result = commands.getstatusoutput("%s -n '%s' -f" % (self.__exe_dict[com_name],
                                                                            user_name))
                if cstat:
                    return "error %s gave (%d) %s" % (com_name, cstat, result)
                else:
                    u_dict = dict([(key.lower().strip().replace(" ", "_"), value.strip()) for key, value in [line.split(":", 1) for line in result.split("\n") if line.count(":")]])
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
#dummy
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
                        act_dict[act_name] = {"name"       : act_name,
                                              "num_sub"    : num_subs,
                                              "start_date" : start_date,
                                              "act_state"  : act_state}
                    if service_name:
                        act_dict = act_dict.get(service_name, {})
                    return "ok %s" % (hm_classes.sys_to_net(act_dict))
            except:
                return "error calling %s: %s" % (self.__exe_dict[com_name],
                                                 process_tools.get_except_info())

#get job status and info using perl script and bconsole
class bacula_jobinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bacula_jobinfo", **args)
        self.help_str = "checks the status of the last bacula job for given job name"
        self.short_client_info = "-w N1, -c N2 -t jobtype"
        self.long_client_info = "sets the warning and critical values for job age in hours and job type (F|D|I)"
        self.short_client_opts = "w:c:t:"
    def server_call(self, cm):
        return self.module_info.get_job_stat(cm)
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
#        pprint.pprint(result)
        j_dict = hm_classes.net_to_sys(result[3:])
        ret_state=limits.nag_STATE_OK
        if j_dict["status"]==256:
            ret_state=limits.nag_STATE_WARNING
        if j_dict["status"]==512:
            ret_state=limits.nag_STATE_CRITICAL
		
        return ret_state, "%s" % (j_dict["message"]) 

#dummy
class bacula_media_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bacula_media", **args)
        self.help_str = "returns the bacula media list"
    def server_call(self, cm):
        return self.module_info.get_user_list()
    def client_call(self, result, parsed_coms):
        u_list = hm_classes.net_to_sys(result[3:])
        return limits.nag_STATE_OK, "OK: %s" % (logging_tools.get_plural("user", len(u_list)))

#dummy
class bacula_userlist_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bacula_userlist", **args)
        self.help_str = "returns the detailed bacula userlist"
    def server_call(self, cm):
        return self.module_info.get_user_list()
    def client_call(self, result, parsed_coms):
        u_list = sorted(hm_classes.net_to_sys(result[3:]))
        return limits.nag_STATE_OK, "OK: %s\n%s" % (logging_tools.get_plural("user", len(u_list)),
                                                    "\n".join(u_list))
#dummy
class bacula_userinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bacula_userinfo", **args)
        self.help_str = "returns bacula userinfo"
    def server_call(self, cm):
        return self.module_info.get_user_info(" ".join(cm))
    def client_call(self, result, parsed_coms):
        u_dict = hm_classes.net_to_sys(result[3:])
        #pprint.pprint(u_dict)
        ret_state = limits.nag_STATE_OK
        used = u_dict["total_size"]
        if u_dict.has_key("max_size"):
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
#dummy
class bacula_serviceinfo_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "bacula_serviceinfo", **args)
        self.help_str = "returns bacula serviceinfo"
    def server_call(self, cm):
        return self.module_info.get_service_info(" ".join(cm))
    def client_call(self, result, parsed_coms):
        s_dict = hm_classes.net_to_sys(result[3:])
        #pprint.pprint(s_dict)
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

