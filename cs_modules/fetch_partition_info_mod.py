#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel
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
import cs_base_class
import logging_tools
import server_command
import net_tools
import pprint
import partition_tools

class fetch_partition_info(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_needed_option_keys(["devname"])
        self.set_public_via_net(False)
    def call_it(self, opt_dict, call_params):
        target_devs = opt_dict["devname"].split(",")
        res_dict = net_tools.multiple_connections(log_hook=call_params.log, target_list=[{"host"    : target_dev,
                                                                                          "port"    : 2001,
                                                                                          "command" : "partinfo"} for target_dev in target_devs]).iterate()
        num_errors, ret_f = (0, [])
        for idx, target_dev in zip(range(len(target_devs)), target_devs):
            t_stuff = res_dict[idx]
            was_error = t_stuff["errnum"]
            if was_error:
                num_errors += 1
                ret_f.append("%s: network error %d: %s" % (target_dev,
                                                           t_stuff["errnum"],
                                                           t_stuff["ret_str"]))
            elif not t_stuff["ret_str"].startswith("ok "):
                num_errors += 1
                if t_stuff["ret_str"].startswith("error"):
                    ret_f.append("%s: error for partinfo: %s" % (target_dev,
                                                                 t_stuff["ret_str"]))
                else:
                    ret_f.append("%s: error got garbled data (starting with %s)" % (target_dev,
                                                                                    t_stuff["ret_str"][0:5]))
            else:
                cmr = server_command.net_to_sys(t_stuff["ret_str"][3:])
                try:
                    dev_dict, sys_dict, lvm_dict = (cmr["dev_dict"],
                                                    cmr["sys_dict"],
                                                    cmr["lvm_dict"])
                except KeyError:
                    num_errors += 1
                    ret_f.append("%s: error missing keys in dict" % (target_dev))
                else:
                    #pprint.pprint(dev_dict)
                    #pprint.pprint(sys_dict)
                    #pprint.pprint(lvm_dict)
                    lvm_info = partition_tools.lvm_struct("dict", source_dict=lvm_dict)
                    partition_name, partition_info = ("%s_part" % (target_dev),
                                                      "generated partition_setup from device '%s'" % (target_dev))
                    # any old partitions?
                    call_params.dc.execute("SELECT * FROM partition_table WHERE name=%s", partition_name)
                    if call_params.dc.rowcount:
                        old_parts = [x["partition_table_idx"] for x in call_params.dc.fetchall()]
                        call_params.dc.execute("SELECT * FROM partition_disc WHERE %s" % (" OR ".join(["partition_table=%d" % (x) for x in old_parts])))
                        if call_params.dc.rowcount:
                            old_discs = [x["partition_disc_idx"] for x in call_params.dc.fetchall()]
                            call_params.dc.execute("DELETE FROM partition WHERE %s" % (" OR ".join(["partition_disc=%d" % (x) for x in old_discs])))
                            call_params.dc.execute("DELETE FROM partition_disc WHERE %s" % (" OR ".join(["partition_disc_idx=%d" % (x) for x in old_discs])))
                            call_params.dc.execute("DELETE FROM sys_partition WHERE %s" % (" OR ".join(["partition_table=%d" % (x) for x in old_parts])))
                        call_params.dc.execute("DELETE FROM partition_table WHERE %s" % (" OR ".join(["partition_table_idx=%d" % (x) for x in old_parts])))
                        call_params.dc.execute("DELETE FROM lvm_lv WHERE %s" % (" OR ".join(["partition_table=%d" % (x) for x in old_parts])))
                        call_params.dc.execute("DELETE FROM lvm_vg WHERE %s" % (" OR ".join(["partition_table=%d" % (x) for x in old_parts])))
                    # fetch partition_fs
                    call_params.dc.execute("SELECT * FROM partition_fs")
                    fs_dict = {}
                    for db_rec in call_params.dc.fetchall():
                        fs_dict.setdefault(("%02x" % (int(db_rec["hexid"], 16))).lower(), []).append(db_rec)
                    call_params.dc.execute("INSERT INTO partition_table SET name=%s, description=%s", (partition_name,
                                                                                                       partition_info))
                    partition_idx = call_params.dc.insert_id()
                    for dev, dev_stuff in dev_dict.iteritems():
                        call_params.dc.execute("INSERT INTO partition_disc SET partition_table=%s, disc=%s", (partition_idx,
                                                                                                              dev))
                        disc_idx = call_params.dc.insert_id()
                        for part, part_stuff in dev_stuff.iteritems():
                            hextype = part_stuff["hextype"][2:].lower()
                            if part.startswith("p"):
                                part = part[1:]
                            if part_stuff.has_key("mountpoint"):
                                fs_idx = 0
                                if hextype in fs_dict.keys():
                                    for fs_stuff in fs_dict[hextype]:
                                        if part_stuff["fstype"].lower() == fs_stuff["name"].lower():
                                            fs_idx = fs_stuff["partition_fs_idx"]
                                call_params.dc.execute("INSERT INTO partition SET partition_disc=%s, mountpoint=%s, partition_hex=%s, size=%s, pnum=%s, mount_options=%s, fs_freq=%s, fs_passno=%s, partition_fs=%s, lut_blob=%s", (disc_idx,
                                                                                                                                                                                                                                    part_stuff["mountpoint"],
                                                                                                                                                                                                                                    hextype,
                                                                                                                                                                                                                                    part_stuff["size"],
                                                                                                                                                                                                                                    part,
                                                                                                                                                                                                                                    part_stuff["options"] or "defaults",
                                                                                                                                                                                                                                    part_stuff["dump"],
                                                                                                                                                                                                                                    part_stuff["fsck"],
                                                                                                                                                                                                                                    fs_idx,
                                                                                                                                                                                                                                    server_command.sys_to_net(part_stuff.get("lut", None))
                                                                                                                                                                                                                                    ))
                            else:
                                if fs_dict.has_key(hextype):
                                    call_params.dc.execute("INSERT INTO partition SET partition_disc=%s, partition_hex=%s, size=%s, pnum=%s, partition_fs=%s, mount_options=%s", (disc_idx,
                                                                                                                                                                                  hextype,
                                                                                                                                                                                  part_stuff["size"],
                                                                                                                                                                                  part,
                                                                                                                                                                                  fs_dict[hextype][0]["partition_fs_idx"],
                                                                                                                                                                                  "defaults"
                                                                                                                                                                                  ))
                                else:
                                    call_params.dc.execute("INSERT INTO partition SET partition_disc=%s, partition_hex=%s, size=%s, pnum=%s", (disc_idx,
                                                                                                                                               hextype,
                                                                                                                                               part_stuff["size"],
                                                                                                                                               part
                                                                                                                                               ))
                            part_name = "%s%s" % (dev, part)
                    for part, part_stuff in sys_dict.iteritems():
                        if type(part_stuff) == type({}):
                            part_stuff = [part_stuff]
                        for p_stuff in part_stuff:
                            # ignore tmpfs mounts
                            if p_stuff["fstype"] in ["tmpfs"]:
                                pass
                            else:
                                call_params.dc.execute("INSERT INTO sys_partition SET partition_table=%s, name=%s, mountpoint=%s, mount_options=%s", (partition_idx,
                                                                                                                                                      part == "none" and p_stuff["fstype"] or part,
                                                                                                                                                      p_stuff["mountpoint"],
                                                                                                                                                      p_stuff["options"]))
                    if lvm_info.lvm_present:
                        # lvm save
                        for vg_name, v_group in lvm_info.lv_dict.get("vg", {}).iteritems():
                            call_params.dc.execute("INSERT INTO lvm_vg SET partition_table=%s, name=%s", (partition_idx,
                                                                                                          v_group["name"]))
                            v_group["db_idx"] = call_params.dc.insert_id()
                        for lv_name, lv_stuff in lvm_info.lv_dict.get("lv", {}).iteritems():
                            mount_options = lv_stuff.get("mount_options", {"dump"       : 0,
                                                                           "fsck"       : 0,
                                                                           "mountpoint" : "",
                                                                           "options"    : "",
                                                                           "fstype"     : ""})
                            mount_options["fstype_idx"] = 0
                            if mount_options["fstype"]:
                                for fs_stuff in fs_dict["83"]:
                                    if fs_stuff["name"].lower() == mount_options["fstype"].lower():
                                        mount_options["fstype_idx"] = fs_stuff["partition_fs_idx"]
                            call_params.dc.execute("INSERT INTO lvm_lv SET partition_table=%s, lvm_vg=%s, name=%s, size=%s, mountpoint=%s, mount_options=%s, fs_freq=%s, fs_passno=%s, partition_fs=%s", (partition_idx,
                                                                                                                                                                                                          lvm_info.lv_dict.get("vg", {})[lv_stuff["vg_name"]]["db_idx"],
                                                                                                                                                                                                          lv_stuff["name"],
                                                                                                                                                                                                          lv_stuff["size"],
                                                                                                                                                                                                          mount_options["mountpoint"],
                                                                                                                                                                                                          mount_options["options"],
                                                                                                                                                                                                          mount_options["dump"],
                                                                                                                                                                                                          mount_options["fsck"],
                                                                                                                                                                                                          mount_options["fstype_idx"]))
                            lv_stuff["db_idx"] = call_params.dc.insert_id()
                    # set partition table
                    call_params.dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (target_dev))
                    if call_params.dc.rowcount:
                        device_idx = call_params.dc.fetchone()["device_idx"]
                        call_params.log("found device '%s' in device_table (idx %d), setting partition_table to %d" % (target_dev, device_idx, partition_idx))
                        call_params.dc.execute("UPDATE device SET act_partition_table=%d, partdev='' WHERE device_idx=%d" % (partition_idx, device_idx))
                    else:
                        call_params.log("cannot find device '%s' in device_table" % (target_dev),
                                        logging_tools.LOG_LEVEL_WARN)
                ret_f.append("%s: %s, %s, %s and %s" % (target_dev,
                                                        logging_tools.get_plural("disc", len(dev_dict.keys())),
                                                        logging_tools.get_plural("sys_partition", len(sys_dict.keys())),
                                                        logging_tools.get_plural("volumegroup", len(lvm_info.lv_dict.get("vg", {}).keys())),
                                                        logging_tools.get_plural("logical volume", len(lvm_info.lv_dict.get("lv", {}).keys()))))
        if num_errors:
            return "error %s" % (";".join(ret_f))
        else:
            return "ok %s" % (";".join(ret_f))
        # show flag
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
