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

import sys
import commands
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import os
import os.path
import logging_tools

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "mpt_status",
                                        "provides a interface to check the status of MPT SCSI Controllers",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.scsi_ids = []

def check_for_scsi_ids(logger, exec_name):
    stat, out = commands.getstatusoutput("%s -p" % (exec_name))
    if stat:
        return False, "error calling %s (%d): %s" % (exec_name, stat, out)
    else:
        scsi_lines = [x.strip() for x in out.lower().split("\n") if x.startswith("found")]
        if scsi_lines:
            scsi_ids = [int(x.split(",")[0].split()[2].split("=")[1]) for x in scsi_lines]
        else:
            scsi_ids = []
        return True, scsi_ids
    
def get_size_str(int_size, size_pf):
    if size_pf == "TB":
        int_size *= 1000 * 1000 * 1000 * 1000
    elif size_pf == "GB":
        int_size *= 1000 * 1000 * 1000
    elif size_pf == "MB":
        int_size *= 1000 * 1000
    pf_list = ["k", "M", "G", "T"]
    int_size = float(int_size)
    while int_size > 1000.:
        int_size /= 1000.
        act_pf = pf_list.pop(0)
    return "%.2f %sB" % (int_size, act_pf)
    
class mpt_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "mpt_status", **args)
        self.help_str = "returns the status of the given controller"
        self.cache_timeout = 600
        self.is_immediate = False
    def server_call(self, cm):
        mpt_exec = "/usr/sbin/mpt-status"
        sg_dir = "/proc/scsi/sg"
        if os.path.isfile(mpt_exec):
            if not self.module_info.scsi_ids:
                ids_ok, id_list = check_for_scsi_ids(self.logger, mpt_exec)
                if not ids_ok:
                    # id_list is the error strings
                    return id_list
                else:
                    self.module_info.scsi_ids = id_list
            if self.module_info.scsi_ids:
                scsi_dict = {}
                for scsi_id in self.module_info.scsi_ids:
                    stat, out = commands.getstatusoutput("%s -i %d -n" % (mpt_exec, scsi_id))
                    if stat == 1:
                        # error
                        scsi_dict[scsi_id] = out
                    else:
                        scsi_dict[scsi_id] = {}
                        # parse
                        lines = [x.strip() for x in out.split("\n") if x.startswith("ioc")]
                        for line in lines:
                            line_parts = line.split()
                            var_list = []
                            for act_part in line_parts:
                                if act_part.count(":"):
                                    var_list.append(act_part)
                                else:
                                    var_list[-1] = "%s %s" % (var_list[-1], act_part)
                            var_dict = dict([(key, value.strip()) for key, value in [act_var.split(":") for act_var in var_list if not act_var.count("ASC/ASCQ")]])
                            var_keys = var_dict.keys()
                            for key in var_keys:
                                value = var_dict[key]
                                if value.isdigit():
                                    var_dict[key] = int(value)
                                if key.startswith("size"):
                                    var_dict["size"] = var_dict[key]
                                    var_dict["size_postfix"] = key[5:-1]
                            if not scsi_dict[scsi_id].has_key(var_dict["ioc"]):
                                scsi_dict[scsi_id][var_dict["ioc"]] = {"volumes"   : {},
                                                                       "physicals" : {}}
                            if var_dict.has_key("vol_id"):
                                scsi_dict[scsi_id][var_dict["ioc"]]["volumes"][var_dict["vol_id"]] = var_dict
                            else:
                                scsi_dict[scsi_id][var_dict["ioc"]]["physicals"][var_dict["phys_id"]] = var_dict
                return "ok %s" % (hm_classes.sys_to_net(scsi_dict))
            else:
                return "error no MPT scsi-ids found"
        elif os.path.isdir(sg_dir):
            # check for devices in /proc/scsi/sg
            sg_dict = {}
            for entry in os.listdir(sg_dir):
                if entry.startswith("device"):
                    try:
                        sg_dict[entry] = [y for y in [x.strip() for x in file("%s/%s" % (sg_dir, entry), "r").read().replace("\t", " ").split("\n")] if y]
                    except:
                        pass
            return "ok %s" % (hm_classes.sys_to_net(sg_dict))
        else:
            return "error no %s found" % (mpt_exec)
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            mpt_dict = hm_classes.net_to_sys(result[3:])
            num_warn, num_error = (0, 0)
            ret_list = []
            #pprint.pprint(mpt_dict)
            if mpt_dict:
                if mpt_dict.has_key("device_strs") and mpt_dict.has_key("devices") and mpt_dict.has_key("device_hdr"):
                    device_strs, devices, device_hdr = (mpt_dict["device_strs"],
                                                        mpt_dict["devices"],
                                                        mpt_dict["device_hdr"])
                    # generate dict
                    dict_headers = device_hdr[0].split()
                    dev_list = []
                    for dev_info, dev_name in zip(devices, device_strs):
                        dev_parts = [int(x) for x in dev_info.split()]
                        dev_name = " ".join(dev_name.split())
                        dev_dict = dict([(key, value) for key, value in zip(dict_headers, dev_parts)] + [("name", dev_name)])
                        dev_list.append(dev_dict)
                        if not dev_dict["online"]:
                            num_error += 1
                    ret_list = sorted(["%s: %s" % (dev_dict["name"], dev_dict["online"] and "online" or "not online") for dev_dict in dev_list])
                else:
                    for scsi_id, scsi_dict in mpt_dict.iteritems():
                        for ioc_id, ioc_dict in scsi_dict.iteritems():
                            if ioc_dict.has_key("volumes"):
                                for vol_id, vol_dict in ioc_dict["volumes"].iteritems():
                                    if vol_dict["state"] not in ["OPTIMAL"]:
                                        num_warn += 1
                                    if vol_dict.has_key("size") and vol_dict.has_key("size_postfix"):
                                        size_str = get_size_str(vol_dict["size"], vol_dict["size_postfix"])
                                    else:
                                        size_str = "unknown size"
                                    ret_list.append("%d:%d:%d %s on %s (%s, %s)" % (scsi_id,
                                                                                    ioc_id,
                                                                                    vol_id,
                                                                                    vol_dict["raidlevel"],
                                                                                    logging_tools.get_plural("disk", vol_dict["num_disks"]),
                                                                                    vol_dict["state"],
                                                                                    size_str))
                            if ioc_dict.has_key("physicals"):
                                for phys_id, phys_dict in ioc_dict["physicals"].iteritems():
                                    if phys_dict["state"] not in ["ONLINE"]:
                                        num_warn += 1
                                    if phys_dict.has_key("size") and phys_dict.has_key("size_postfix"):
                                        size_str = get_size_str(phys_dict["size"], phys_dict["size_postfix"])
                                    else:
                                        size_str = "unknown size"
                                    ret_list.append("%d:%d:%d %s (%s, %s%s%s)" % (scsi_id,
                                                                                  ioc_id,
                                                                                  phys_id,
                                                                                  phys_dict["vendor"],
                                                                                  phys_dict["state"],
                                                                                  size_str,
                                                                                  phys_dict["flags"] != "NONE" and ", %s" % (phys_dict["flags"]) or "",
                                                                                  phys_dict["sync_state"] != 100 and ", %d %%" % (phys_dict["sync_state"]) or ""))
            else:
                ret_list.append("no controller found")
                num_error = 1
            if num_error:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "ERROR")
            elif num_warn:
                ret_state, ret_str = (limits.nag_STATE_WARNING, "WARNING")
            else:
                ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            return ret_state, "%s: %s" % (ret_str, ", ".join(ret_list))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
