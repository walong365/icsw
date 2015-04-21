#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2007,2008 Andreas Lang-Nevyjel, init.at
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
import re
import os
import os.path
from initat.tools import logging_tools
import pprint
from initat.tools import process_tools

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "smartctl",
                                        "provides a interface to check the smart-status of harddisks",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.disk_list = []
    def needs_hourly_wakeup_call(self):
        return True
    def hourly_wakeup_call(self, logger):
        self.log("clearing disk_list to check for new disks")
        self.disk_list = []
        self._check_for_disks()
    def _check_for_disks(self):
        if not self.disk_list:
            unit_match = re.compile("^\s+Unit\s*(?P<num>\d+):\s*(?P<raid>.*)\s+(?P<size>\S+\s+\S+)\s+\(\s*(?P<blocks>\d+)\s+\S+\):\s*(?P<status>.*)$")
            port_match = re.compile("^\s+Port\s*(?P<num>\d+):\s*(?P<info>[^:]+):\s*(?P<status>.*)\(unit\s*(?P<unit>\d+)\)$")
            p2_match   = re.compile("^p(?P<num>\d+)\s+(?P<status>\S+)\s+u(?P<unit>\d+)\s+(?P<size>\S+\s+\S+)\s+(?P<blocks>\d+)\s+.*$")
            tw_exec = "/sbin/tw_cli"
            disk_list = []
            check_threeware = False
            block_dir = "/sys/block"
            if os.path.isdir(block_dir):
                ide_devices = [x for x in os.listdir(block_dir) if x.startswith("hd") or x.startswith("sd")]
                for ide_dev in ide_devices:
                    try:
                        removeable = file("%s/%s/removable" % (block_dir, ide_dev), "r").read().lower().strip()
                    except:
                        pass
                    else:
                        if removeable == "0":
                            # check vendor
                            try:
                                vendor = file("/%s/%s/device/vendor" % (block_dir, ide_dev), "r").read().lower().strip()
                            except:
                                vendor = "ATA"
                            if vendor in ["3ware", "amcc"]:
                                check_threeware = True
                            elif vendor == "ift":
                                # eonstor box
                                pass
                            elif vendor == "promise":
                                # promise shitty-raid
                                pass
                            else:
                                disk_list.append({"raw_device" : "/dev/%s" % (ide_dev),
                                                  "device"     : ide_dev,
                                                  "type"       : ide_dev.startswith("sd") and "sat" or "ata",
                                                  "vendor"     : vendor})
            if check_threeware:
                # check threeware disks
                if os.path.isfile(tw_exec):
                    stat, out = commands.getstatusoutput("%s info" % (tw_exec))
                    if stat:
                        return "error calling %s (%d): %s" % (tw_exec, stat, str(out))
                    else:
                        ctrl_list = []
                        mode = None
                        for line in [y for y in [x.strip() for x in out.split("\n")] if y]:
                            line_p = line.split()
                            if mode is None:
                                if line_p[0].lower() == "list":
                                    # old mode
                                    mode = 1
                                elif line_p[0].lower() == "ctl":
                                    # new mode
                                    mode = 2
                            elif mode:
                                if line_p[0].lower().startswith("controller") and mode == 1:
                                    ctrl_list.append("c%d" % (int(line_p[1][:-1])))
                                elif line_p[0].startswith("c") and mode == 2:
                                    ctrl_list.append(line_p[0])
                        for ctrl in ctrl_list:
                            loc_ctrl_dict = {"ports" : []}
                            stat, out = commands.getstatusoutput("%s info %s" % (tw_exec, ctrl))
                            if stat:
                                loc_ctrl_dict["info"] = "error calling %s (%d): %s" % (tw_exec, stat, str(out))
                            else:
                                loc_ctrl_dict["info"] = "ok"
                                lines = [y for y in [x.rstrip() for x in out.strip().split("\n")] if y]
                                if lines:
                                    if lines[0].lower().strip().startswith("unit"):
                                        # new format
                                        for line in lines:
                                            pm = p2_match.match(line)
                                            if pm:
                                                loc_ctrl_dict["ports"].append((int(pm.group("num")), pm.group("unit")))
                            self.log("Found 3ware-controller with %s" % (logging_tools.get_plural("port", len(loc_ctrl_dict["ports"]))))
                            # find 3ware-device name
                            char_dict, block_dict = process_tools.get_char_block_device_dict()
                            dev_nums = file("/proc/devices", "r").read().split("\n")
                            for port_num, unit_name in loc_ctrl_dict["ports"]:
                                disk_list.append({"raw_device" : "/dev/%s0" % (char_dict.get(254, "twe")),
                                                  "type"       : "3ware,%d" % (port_num),
                                                  "vendor"     : vendor,
                                                  "device"     : "u%s" % (unit_name)})
                else:
                    self.log("No tw_cli %s found, ignoring threeware disks" % (tw_exec),
                             logging_tools.LOG_LEVEL_ERROR)
                
            self.disk_list = disk_list

SMARTCTL_BIN = "smartctl"

class smart_stat_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "smart_stat", **args)
    def server_call(self, cm):
        sm_paths = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
        sm_exec = None
        for sm_path in sm_paths:
            if os.path.isfile("%s/%s" % (sm_path, SMARTCTL_BIN)):
                sm_exec = "%s/%s" % (sm_path, SMARTCTL_BIN)
                break
        if sm_exec:
            self.module_info._check_for_disks()
            parts = [y[3] for y in [x.strip().split() for x in file("/proc/partitions", "r").read().split("\n")] if len(y) > 3 and (y[3].startswith("hd") or y[3].startswith("sd"))]
            check_list = self.module_info.disk_list
            disk_dict = dict([("%s:%s" % (value["device"], value["type"]), {"partitions" : 0,
                                                                            "device"     : value["device"],
                                                                            "type"       : value["type"],
                                                                            "raw_device" : value["raw_device"]}) for value in check_list])
            for part in [x for x in parts if not x in [value["raw_device"] for value in check_list]]:
                disk = part[0:3]
                if disk_dict.has_key(disk):
                    disk_dict[disk]["partitions"] += 1
            for disk in disk_dict.keys():
                disk_stuff = disk_dict[disk]
                disk_target = "-A %s -d %s" % (disk_stuff["raw_device"],
                                               disk_stuff["type"])
                stat, out = commands.getstatusoutput("%s %s" % (sm_exec, disk_target))
                if stat:
                    disk_dict[disk]["info"] = "error getting smart-info: %s" % (out)
                else:
                    out_lines = [y for y in [x.strip() for x in out.split("\n")] if y]
                    if out_lines[-1].lower().startswith("smart disabled"):
                        stat, out = commands.getstatusoutput("%s -s on %s" % (sm_exec, disk_target))
                        if stat:
                            disk_dict[disk]["info"] = "error getting smart-info: %s" % (out)
                        else:
                            out_lines = [y for y in [x.strip() for x in out.split("\n")] if y]
                            disk_dict[disk]["info"] = "ok getting smart-info"
                    else:
                        disk_dict[disk]["info"] = "ok getting smart-info"
                    if disk_dict[disk]["info"].startswith("ok"):
                        out_lines = [y for y in [x.split(None, 9) for x in out_lines] if len(y) == 10 and (y[0].isdigit() or y[0].lower().startswith("id"))]
                        if out_lines:
                            head = [x.lower() for x in out_lines.pop(0)]
                            int_fields = [head[0], head[3], head[4], head[5], head[9]]
                            hex_fields = [head[2]]
                            out_dict = dict([(int(x[0]), dict([(a, b.split()[0]) for a, b in zip(head, x)])) for x in out_lines])
                            full_dict = {}
                            for key_id, loc_dict in out_dict.iteritems():
                                for key, value in loc_dict.iteritems():
                                    if key in int_fields:
                                        # check for xh+ym field
                                        if value.count("+"):
                                            r_v = 0
                                            for u_v in [x.strip() for x in value.strip().split("+") if x.strip()]:
                                                if u_v.endswith("h"):
                                                    r_v += 3600 * int(u_v[:-1])
                                                else:
                                                    r_v += 60 * int(u_v[:-1])
                                            loc_dict[key] = r_v
                                        else:
                                            loc_dict[key] = int(value)
                                    elif key in hex_fields:
                                        loc_dict[key] = int(value, 16)
                                    else:
                                        loc_dict[key] = value.lower()
                                full_dict[loc_dict["id#"]] = loc_dict
                            disk_dict[disk]["full"] = full_dict
                        else:
                            disk_dict[disk]["info"] = "error no smart-readable values found"
            #print disk_dict
            return "ok %s" % (hm_classes.sys_to_net(disk_dict))
        else:
            return "error no %s found in %s" % (SMARTCTL_BIN, ", ".join(sm_paths))
    def client_call(self, cm, crs):
        def get_disk_info_str(d_name, d_field):
            if d_field:
                return "%s (%s)" % (d_name,
                                    ", ".join(d_field))
            else:
                return d_name
        if cm.startswith("ok "):
            sm_dict = hm_classes.net_to_sys(cm[3:])
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            disk_strs = []
            for disk, disk_info in sm_dict.iteritems():
                disk_info_field = []
                if disk_info["partitions"]:
                    disk_info_field.append(logging_tools.get_plural("part", disk_info["partitions"]))
                if disk_info["info"].startswith("ok"):
                    full_dict = disk_info.get("full", {})
                    disk_temp = 0
                    if full_dict:
                        # new format, read temperature
                        temp_ids = [key for key, value in full_dict.iteritems() if value["attribute_name"].lower().count("temperature")]
                        for temp_id in temp_ids:
                            act_temp = full_dict[temp_id]["raw_value"]
                            if act_temp > 0 and act_temp < 100:
                                disk_temp = act_temp
                        fail_dict = {"-" : 0}
                        for smart_id, smart_stuff in full_dict.iteritems():
                            if smart_stuff["when_failed"] != "-":
                                fail_dict["%s (%d)" % (smart_stuff["attribute_name"],
                                                       smart_id)] = "failed"
                    else:
                        fail_dict = disk_info["fail"]
                    if disk_temp:
                        if disk_temp > 45:
                            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error")
                        disk_info_field.append("%d Celsius" % (disk_temp))
                    if fail_dict.keys() != ["-"]:
                        ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error")
                        if full_dict:
                            # new format
                            disk_strs.append("%s: %s" % (get_disk_info_str(disk, disk_info_field),
                                                         ", ".join(["%s: %s" %(k, fail_dict[k]) for k in fail_dict.keys() if k != "-"])))
                        else:
                            # old format
                            disk_strs.append("%s: %s" % (get_disk_info_str(disk, disk_info_field),
                                                         ", ".join(["%s: %d" %(k, fail_dict[k]) for k in fail_dict.keys() if k != "-"])))
                    else:
                        disk_strs.append("%s: ok" % (get_disk_info_str(disk, disk_info_field)))
                else:
                    disk_strs.append("%s: %s" % (get_disk_info_str(disk, disk_info_field),
                                                 disk_info["info"]))
            disk_strs.sort()
            return ret_state, "%s:%s: %s" % (ret_str,
                                             logging_tools.get_plural("disk", len(disk_strs)),
                                             disk_strs and ", ".join(disk_strs) or "no disks found")
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (cm)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

