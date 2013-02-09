#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2012,2013 Andreas Lang-Nevyjel
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
import process_tools
from django.db.models import Q
from initat.cluster.backbone.models import device, partition, partition_disc, partition_table, \
     partition_fs, lvm_lv, lvm_vg, sys_partition, get_related_models

class fetch_partition_info(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["devname"]
    def _call(self, cur_inst):
        target_devs = self.option_dict["devname"].split(",")
        zmq_con = net_tools.zmq_connection(
            "server:%s" % (process_tools.get_machine_name()),
            context=self.process_pool.zmq_context)
        for target_dev in target_devs:
            zmq_con.add_connection(
                "tcp://%s:%d" % (target_dev,
                                 2001),
                server_command.srv_command(command="partinfo"),
                multi=True
            )
        res_dict = zmq_con.loop()
##        res_dict = net_tools.multiple_connections(log_hook=self.log, target_list=[{"host"    : target_dev,
##                                                                                   "port"    : 2001,
##                                                                                   "command" : "partinfo"} for target_dev in target_devs]).iterate()
        num_errors, ret_f = (0, [])
        for idx, target_dev in zip(range(len(target_devs)), target_devs):
            t_stuff = res_dict[idx]
            if t_stuff is None:
                was_error = -1
            else:
                was_error = int(t_stuff["result"].attrib["state"])
            if was_error:
                num_errors += 1
                if t_stuff is None:
                    ret_f.append("%s: no result" % (target_dev))
                else:
                    ret_f.append("%s: network error %d: %s" % (target_dev,
                                                               int(t_stuff["result"].attrib["state"]),
                                                               t_stuff["result"].attrib["reply"]))
##            elif not t_stuff["ret_str"].startswith("ok "):
##                num_errors += 1
##                if t_stuff["ret_str"].startswith("error"):
##                    ret_f.append("%s: error for partinfo: %s" % (target_dev,
##                                                                 t_stuff["ret_str"]))
##                else:
##                    ret_f.append("%s: error got garbled data (starting with %s)" % (target_dev,
##                                                                                    t_stuff["ret_str"][0:5]))
            else:
                try:
##                    dev_dict, sys_dict, lvm_dict = (server_command.decompress(t_stuff["dev_dict"].text, marshal=True),
##                                                    server_command.decompress(t_stuff["sys_dict"].text, marshal=True),
##                                                    server_command.decompress(t_stuff["lvm_dict"].text, pickle=True))
                    dev_dict, sys_dict, lvm_dict = (
                        t_stuff["dev_dict"],
                        t_stuff["sys_dict"],
                        t_stuff["lvm_dict"])
                except KeyError:
                    num_errors += 1
                    ret_f.append("%s: error missing keys in dict" % (target_dev))
                else:
                    #pprint.pprint(dev_dict)
                    #pprint.pprint(sys_dict)
                    #pprint.pprint(lvm_dict)
                    lvm_info = partition_tools.lvm_struct("xml", xml=lvm_dict)
                    partition_name, partition_info = ("%s_part" % (target_dev),
                                                      "generated partition_setup from device '%s'" % (target_dev))
                    # any old partitions?
                    try:
                        cur_pt = partition_table.objects.get(Q(name=partition_name))
                    except partition_table.DoesNotExist:
                        pass
                    else:
                        for rel_obj in cur_pt._meta.get_all_related_objects():
                            if rel_obj.name in [
                                "backbone:partition_disc",
                                "backbone:lvm_lv",
                                "backbone:lvm_vg",
                                "backbone:sys_partition"]:
                                pass
                            elif rel_obj.name == "backbone:device":
                                for ref_obj in  rel_obj.model.objects.filter(Q(**{rel_obj.field.name : cur_pt})):
                                    self.log("cleaning %s of %s" % (rel_obj.field.name, unicode(ref_obj)))
                                    setattr(ref_obj, rel_obj.field.name, None)
                                    ref_obj.save()
                            else:
                                raise ValueError, "unknown related object %s for partition_info" % (rel_obj.name)
                        cur_pt.delete()
                    # fetch partition_fs
                    fs_dict = {}
                    for db_rec in partition_fs.objects.all():
                        fs_dict.setdefault(("%02x" % (int(db_rec.hexid, 16))).lower(), {})[db_rec.name] = db_rec
##                    self.dc.execute("SELECT * FROM partition_fs")
##                    fs_dict = {}
##                    for db_rec in self.dc.fetchall():
##                        fs_dict.setdefault(("%02x" % (int(db_rec["hexid"], 16))).lower(), []).append(db_rec)
                    new_part_table = partition_table(name=partition_name,
                                                     description=partition_info)
                    new_part_table.save()
##                    self.dc.execute("INSERT INTO partition_table SET name=%s, description=%s", (partition_name,
##                                                                                                       partition_info))
##                    partition_idx = self.dc.insert_id()
                    for dev, dev_stuff in dev_dict.iteritems():
                        self.log("handling device %s" % (dev))
                        new_disc = partition_disc(partition_table=new_part_table,
                                                  disc=dev)
                        new_disc.save()
##                        self.dc.execute("INSERT INTO partition_disc SET partition_table=%s, disc=%s", (partition_idx,
##                                                                                                              dev))
##                        disc_idx = self.dc.insert_id()
                        for part in sorted(dev_stuff):
                            part_stuff = dev_stuff[part]
                            self.log("   handling partition %s" % (part))
                            hex_type = part_stuff["hextype"][2:].lower()
                            if part.startswith("p"):
                                part = part[1:]
                            if part_stuff.has_key("mountpoint"):
                                fs_stuff = fs_dict.get(hex_type, {}).get(part_stuff["fstype"].lower(), None)
##                                fs_idx = 0
##                                if hextype in fs_dict.keys():
##                                    for fs_stuff in fs_dict[hextype]:
##                                        if part_stuff["fstype"].lower() == fs_stuff["name"].lower():
##                                            fs_idx = fs_stuff["partition_fs_idx"]
##                                if fs_idx:
##                                    fs_stuff = fs_dict[fs_idx]
##                                else:
##                                    fs_stuff = None
                                if fs_stuff is not None:
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        mountpoint=part_stuff["mountpoint"],
                                        size=part_stuff["size"],
                                        pnum=part,
                                        mount_options=part_stuff["options"] or "defaults",
                                        fs_freq=part_stuff["dump"],
                                        fs_passno=part_stuff["fsck"],
                                        partition_fs=fs_stuff,
                                        lut_blob=server_command.sys_to_net(part_stuff.get("lut", None))
                                    )
                                else:
                                    self.log("skipping partition because fs_stuff is None", logging_tools.LOG_LEVEL_WARN)
                                    new_part = None
                            else:
                                if fs_dict.has_key(hex_type):
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        partition_hex=hex_type,
                                        size=part_stuff["size"],
                                        pnum=part,
                                        #partition_fs=fs_dict[hex_type],
                                        mount_options="defaults",
                                    )
                                    self.log("skipping partition because no mountpoint and no matching fs_dict (hex_type %s)" % (hex_type), logging_tools.LOG_LEVEL_ERROR)
                                    new_part = None
                                else:
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        partition_hex=hex_type,
                                        size=part_stuff["size"],
                                        pnum=part,
                                    )
                            if new_part is not None:
                                new_part.save()
                            part_name = "%s%s" % (dev, part)
                    for part, part_stuff in sys_dict.iteritems():
                        self.log("handling part %s (sys)" % (part))
                        if type(part_stuff) == type({}):
                            part_stuff = [part_stuff]
                        for p_stuff in part_stuff:
                            # ignore tmpfs mounts
                            if p_stuff["fstype"] in ["tmpfs"]:
                                pass
                            else:
                                new_sys = sys_partition(
                                    partition_table=new_part_table,
                                    name=p_stuff["fstype"] if part == "none" else part,
                                    mountpoint=p_stuff["mountpoint"],
                                    mount_options=p_stuff["options"],
                                )
                                new_sys.save()
                    if lvm_info.lvm_present:
                        self.log("LVM info is present")
                        # lvm save
                        for vg_name, v_group in lvm_info.lv_dict.get("vg", {}).iteritems():
                            self.log("handling VG %s" % (vg_name))
                            new_vg = lvm_vg(
                                partition_table=new_part_table,
                                name=v_group["name"])
                            new_vg.save()
                            v_group["db"] = new_vg
                        for lv_name, lv_stuff in lvm_info.lv_dict.get("lv", {}).iteritems():
                            self.log("handling LV %s" % (lv_name))
                            mount_options = lv_stuff.get(
                                "mount_options", {
                                    "dump"       : 0,
                                    "fsck"       : 0,
                                    "mountpoint" : "",
                                    "options"    : "",
                                    "fstype"     : ""})
                            mount_options["fstype_idx"] = None
                            if mount_options["fstype"]:
                                mount_options["fstype_idx"] = fs_dict.get("83", {}).get(mount_options["fstype"].lower(), None)
                                ##                                for fs_stuff in fs_dict["83"]:
                                ##                                    if fs_stuff["name"].lower() == mount_options["fstype"].lower():
                                ##                                        mount_options["fstype_idx"] = fs_stuff["partition_fs_idx"]
                            new_lv = lvm_lv(
                                partition_table=new_part_table,
                                lvm_vg=lvm_info.lv_dict.get("vg", {})[lv_stuff["vg_name"]]["db"],
                                name=lv_stuff["name"],
                                size=lv_stuff["size"],
                                mountpoint=mount_options["mountpoint"],
                                mount_options=mount_options["options"],
                                fs_freq=mount_options["dump"],
                                fs_passno=mount_options["fsck"],
                                partition_fs=mount_options["fstype_idx"],
                            )
##                            self.dc.execute("INSERT INTO lvm_lv SET partition_table=%s, lvm_vg=%s, name=%s, size=%s, mountpoint=%s, mount_options=%s, fs_freq=%s, fs_passno=%s, partition_fs=%s", (
##                                partition_idx,
##                                lvm_info.lv_dict.get("vg", {})[lv_stuff["vg_name"]]["db_idx"],
##                                lv_stuff["name"],
##                                lv_stuff["size"],
##                                mount_options["mountpoint"],
##                                mount_options["options"],
##                                mount_options["dump"],
##                                mount_options["fsck"],
##                                mount_options["fstype_idx"]))
                            new_lv.save()
                            lv_stuff["db"] = new_lv
                    # set partition table
                    try:
                        t_dev = device.objects.get(Q(name=target_dev))
                    except device.DoesNotExist:
                        self.log("cannot find device '%s' in device_table" % (target_dev),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("found device '%s' in device_table (idx %d), setting partition_table to %d" % (target_dev, t_dev.pk, new_part_table.pk))
                        t_dev.act_partition_table = new_part_table
                        t_dev.partdev = ""
                        t_dev.save()
##                    self.dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (target_dev))
##                    if self.dc.rowcount:
##                        device_idx = self.dc.fetchone()["device_idx"]
##                        self.dc.execute("UPDATE device SET act_partition_table=%d, partdev='' WHERE device_idx=%d" % (partition_idx, device_idx))
                ret_f.append("%s: %s, %s, %s and %s" % (
                    target_dev,
                    logging_tools.get_plural("disc", len(dev_dict.keys())),
                    logging_tools.get_plural("sys_partition", len(sys_dict.keys())),
                    logging_tools.get_plural("volumegroup", len(lvm_info.lv_dict.get("vg", {}).keys())),
                    logging_tools.get_plural("logical volume", len(lvm_info.lv_dict.get("lv", {}).keys()))))
        if num_errors:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "ok %s" % (";".join(ret_f)),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "ok %s" % (";".join(ret_f)),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
