# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, host monitoring functions """

from django.db import transaction
from django.db.models import Q
from initat.cluster.backbone.models import device, partition, partition_disc, \
    partition_table, partition_fs, lvm_lv, lvm_vg, sys_partition, net_ip, netdevice, \
    netdevice_speed, peer_information
from initat.snmp.struct import ResultNode
from initat.tools import config_tools
from initat.tools import logging_tools
from initat.tools import net_tools
from initat.tools import partition_tools
from initat.tools import process_tools
from initat.tools import server_command

from .config import global_config

# removed tun from list to enable adding of FWs from Madar, move to option?
IGNORE_LIST = ["tap", "vnet"]


class NDStruct(object):
    def __init__(self, dev_name, in_dict, br_dict):
        self.dev_name = dev_name
        self.in_dict = in_dict
        self.br_dict = br_dict
        self.nd = None
        NDStruct.dict[self.dev_name] = self

    @staticmethod
    def setup(cur_inst, device, default_nds):
        NDStruct.cur_inst = cur_inst
        NDStruct.device = device
        NDStruct.default_nds = default_nds
        NDStruct.dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        NDStruct.cur_inst.log("[nd {}] {}".format(self.dev_name, what), log_level)

    def create(self):
        cur_nd = netdevice(
            device=NDStruct.device,
            devname=self.dev_name,
            netdevice_speed=NDStruct.default_nds,
            routing=False,
            penalty=1,
            dhcp_device=False,
            is_bridge=True if self.br_dict else False,
        )
        cur_nd.save()
        self.nd = cur_nd
        self.log("created netdevice")
        if self.br_dict:
            self.dev_name, self.br_dict.get("interfaces", [])
        if "ether" in self.in_dict.get("links", {}):
            _ether = self.in_dict["links"]["ether"]
            _mac = _ether[0].split()[0]
            cur_nd.macaddr = _mac
            cur_nd.save()
            self.log("set macaddr to '{}'".format(cur_nd.macaddr))
        for _inet in self.in_dict.get("inet", []):
            cur_ip_nw = _inet.split()[0]
            cur_ip = cur_ip_nw.split("/")[0]
            new_ip = net_ip(
                netdevice=cur_nd,
                ip=cur_ip,
                domain_tree_node=self.device.domain_tree_node,
                )
            new_ip.save()
            self.log("added IP {} (network {})".format(new_ip.ip, unicode(new_ip.network)))

    def link_bridge_slaves(self):
        for _slave_name in self.br_dict.get("interfaces", []):
            if _slave_name in NDStruct.dict:
                _slave_nd = NDStruct.dict[_slave_name].nd
                if _slave_nd is not None:
                    _slave_nd.bridge_device = self.nd
                    self.log("enslaving {}".format(_slave_name))
                    _slave_nd.save()


class HostMonitoringMixin(object):
    def fetch_partition_info(self, dev_com, scan_dev):
        # target_pks = srv_com["device_pk"].text.split(",")
        # self.log("got %s: %s" % (
        #    logging_tools.get_plural("pk", len(target_pks)),
        #    ", ".join(target_pks))
        # )
        self.get_route_to_devices([scan_dev])
        zmq_con = net_tools.zmq_connection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.zmq_context
        )
        result_devs = []
        for target_dev in target_devs:
            if target_dev.target_ip:
                result_devs.append(target_dev)
                conn_str = "tcp://{}:{:d}".format(
                    cur_dev.target_ip,
                    2001
                )
                self.log(u"connection_str for {} is {}".format(unicode(target_dev), conn_str))
                zmq_con.add_connection(
                    conn_str,
                    server_command.srv_command(command="partinfo"),
                    multi=True
                )
        res_list = zmq_con.loop()
        self.log("length of result list: {:d}".format(len(res_list)))
        res_node = ResultNode()
        for _idx, (result, target_dev) in enumerate(zip(res_list, result_devs)):
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                if res_state == -1:
                    res_node.error(u"%s: no result" % (unicode(target_dev)))
                else:
                    res_node.error(
                        u"%s: error %d: %s" % (
                            unicode(target_dev),
                            int(result["result"].attrib["state"]),
                            result["result"].attrib["reply"]
                        )
                    )
            else:
                try:
                    dev_dict, sys_dict, lvm_dict = (
                        result["dev_dict"],
                        result["sys_dict"],
                        result["lvm_dict"],
                    )
                except KeyError:
                    res_node.error(u"%s: error missing keys in dict" % (target_dev))
                else:
                    try:
                        _old_stuff = server_command.decompress(lvm_dict.text)
                    except:
                        lvm_info = partition_tools.lvm_struct("xml", xml=lvm_dict)
                    else:
                        raise ValueError("it seems the client is using pickled transfers")
                    partition_name, partition_info = (
                        "{}_part".format(target_dev.full_name),
                        "generated partition_setup from device '%s'" % (target_dev.full_name))
                    prev_th_dict = {}
                    try:
                        cur_pt = partition_table.objects.get(Q(name=partition_name))
                    except partition_table.DoesNotExist:
                        pass
                    else:
                        # read previous settings
                        for entry in cur_pt.partition_disc_set.all().values_list(
                            "partition__mountpoint", "partition__warn_threshold", "partition__crit_threshold"
                        ):
                            prev_th_dict[entry[0]] = (entry[1], entry[2])
                        for entry in cur_pt.lvm_vg_set.all().values_list("lvm_lv__mountpoint", "lvm_lv__warn_threshold", "lvm_lv__crit_threshold"):
                            prev_th_dict[entry[0]] = (entry[1], entry[2])
                        if cur_pt.user_created:
                            self.log(
                                "prevision partition_table '%s' was user created, not deleting" % (unicode(cur_pt)),
                                logging_tools.LOG_LEVEL_WARN)
                        else:
                            self.log("deleting previous partition_table %s" % (unicode(cur_pt)))
                            for rel_obj in cur_pt._meta.get_all_related_objects():
                                if rel_obj.name in [
                                    "backbone:partition_disc",
                                    "backbone:lvm_lv",
                                    "backbone:lvm_vg",
                                    "backbone:sys_partition"
                                ]:
                                    pass
                                elif rel_obj.name == "backbone:device":
                                    for ref_obj in rel_obj.model.objects.filter(Q(**{rel_obj.field.name: cur_pt})):
                                        self.log("cleaning %s of %s" % (rel_obj.field.name, unicode(ref_obj)))
                                        setattr(ref_obj, rel_obj.field.name, None)
                                        ref_obj.save()
                                else:
                                    raise ValueError("unknown related object %s for partition_info" % (rel_obj.name))
                            cur_pt.delete()
                        target_dev.act_partition_table = None
                    # fetch partition_fs
                    fs_dict = {}
                    for db_rec in partition_fs.objects.all():
                        fs_dict.setdefault(("{:02x}".format(int(db_rec.hexid, 16))).lower(), {})[db_rec.name] = db_rec
                        fs_dict[db_rec.name] = db_rec
                    new_part_table = partition_table(
                        name=partition_name,
                        description=partition_info,
                        user_created=False,
                    )
                    new_part_table.save()
                    for dev, dev_stuff in dev_dict.iteritems():
                        if dev.startswith("/dev/sr"):
                            self.log("skipping device {}".format(dev), logging_tools.LOG_LEVEL_WARN)
                            continue
                        self.log("handling device %s" % (dev))
                        new_disc = partition_disc(partition_table=new_part_table,
                                                  disc=dev)
                        new_disc.save()
                        for part in sorted(dev_stuff):
                            part_stuff = dev_stuff[part]
                            self.log("   handling partition %s" % (part))
                            if "multipath" in part_stuff:
                                # see machinfo_mod.py, lines 1570 (partinfo_command:interpret)
                                real_disk = [entry for entry in part_stuff["multipath"]["list"] if entry["status"] == "active"]
                                if real_disk:
                                    mp_id = part_stuff["multipath"]["id"]
                                    real_disk = real_disk[0]
                                    if part is None:
                                        real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part)
                                    else:
                                        real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part[4:])
                                    if real_disk in dev_dict:
                                        # LVM between
                                        real_part = dev_dict[real_disk][real_part]
                                        for key in ["hextype", "info", "size"]:
                                            part_stuff[key] = real_part[key]
                                    else:
                                        # no LVM between
                                        real_part = dev_dict["/dev/mapper/%s" % (mp_id)]
                                        part_stuff["hextype"] = "0x00"
                                        part_stuff["info"] = "multipath w/o LVM"
                                        part_stuff["size"] = int(logging_tools.interpret_size_str(part_stuff["multipath"]["size"]) / (1024 * 1024))
                            hex_type = part_stuff["hextype"]
                            if hex_type is None:
                                self.log("ignoring partition because hex_type = None", logging_tools.LOG_LEVEL_WARN)
                            else:
                                hex_type = hex_type[2:].lower()
                                if part is None:
                                    # special multipath without partition
                                    part = "0"
                                elif part.startswith("part"):
                                    # multipath
                                    part = part[4:]
                                elif part.startswith("p"):
                                    # compaq array
                                    part = part[1:]
                                if "mountpoint" in part_stuff:
                                    fs_stuff = fs_dict.get(hex_type, {}).get(part_stuff["fstype"].lower(), None)
                                    if fs_stuff is None and "fstype" in part_stuff and part_stuff["fstype"] in fs_dict:
                                        fs_stuff = fs_dict[part_stuff["fstype"]]
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
                                            disk_by_info=",".join(part_stuff.get("lut", [])),
                                        )
                                    else:
                                        self.log("skipping partition {} because fs_stuff is None".format(part), logging_tools.LOG_LEVEL_WARN)
                                        new_part = None
                                else:
                                    if hex_type in fs_dict:
                                        if hex_type == "82":
                                            new_part = partition(
                                                partition_disc=new_disc,
                                                partition_hex=hex_type,
                                                size=part_stuff["size"],
                                                pnum=part,
                                                partition_fs=fs_dict[hex_type].values()[0],
                                                mount_options="defaults",
                                            )
                                        else:
                                            self.log(
                                                "skipping partition {} because no mountpoint and no matching fs_dict (hex_type {})".format(
                                                    part,
                                                    hex_type
                                                ),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                            new_part = None
                                    else:
                                        new_part = partition(
                                            partition_disc=new_disc,
                                            partition_hex=hex_type,
                                            size=part_stuff["size"],
                                            pnum=part,
                                        )
                                        new_part = None
                                        self.log("no mountpoint defined", logging_tools.LOG_LEVEL_ERROR)
                                if new_part is not None:
                                    if new_part.mountpoint in prev_th_dict:
                                        new_part.warn_threshold, new_part.crit_threshold = prev_th_dict[new_part.mountpoint]
                                    new_part.save()
                                _part_name = "%s%s" % (dev, part)
                    for part, part_stuff in sys_dict.iteritems():
                        self.log("handling part %s (sys)" % (part))
                        if type(part_stuff) == dict:
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
                                    "dump": 0,
                                    "fsck": 0,
                                    "mountpoint": "",
                                    "options": "",
                                    "fstype": "",
                                }
                            )
                            mount_options["fstype_idx"] = None
                            if mount_options["fstype"]:
                                mount_options["fstype_idx"] = fs_dict.get("83", {}).get(mount_options["fstype"].lower(), None)
                                if mount_options["fstype_idx"]:
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
                                    if new_lv.mountpoint in prev_th_dict:
                                        new_lv.warn_threshold, new_lv.crit_threshold = prev_th_dict[new_lv.mountpoint]
                                    new_lv.save()
                                    lv_stuff["db"] = new_lv
                                else:
                                    self.log(
                                        "no fstype found for LV %s (fstype %s)" % (
                                            lv_stuff["name"],
                                            mount_options["fstype"],
                                            ),
                                        logging_tools.LOG_LEVEL_ERROR)
                            else:
                                self.log("no fstype found for LV %s" % (lv_stuff["name"]),
                                         logging_tools.LOG_LEVEL_ERROR)
                    # set partition table
                    self.log(u"set partition_table for '%s'" % (unicode(target_dev)))
                    target_dev.act_partition_table = new_part_table
                    target_dev.partdev = ""
                    target_dev.save(update_fields=["act_partition_table", "partdev"])
                res_node.ok(
                    u"%s: %s, %s, %s and %s" % (
                        target_dev,
                        logging_tools.get_plural("disc", len(dev_dict.keys())),
                        logging_tools.get_plural("sys_partition", len(sys_dict.keys())),
                        logging_tools.get_plural("volumegroup", len(lvm_info.lv_dict.get("vg", {}).keys())),
                        logging_tools.get_plural("logical volume", len(lvm_info.lv_dict.get("lv", {}).keys()))
                    )
                )
        self.clear_scan(scan_dev)
        return res_node

    def scan_network_info(self, dev_com, scan_dev):
        res_node = ResultNode()
        strict_mode = True if int(dev_com.get("strict_mode")) else False
        scan_address = dev_com.get("scan_address")
        self.log(
            "scanning network for device '{}' ({:d}), scan_address is '{}', strict_mode is {}".format(
                unicode(scan_dev),
                scan_dev.pk,
                scan_address,
                "on" if strict_mode else "off",
            )
        )
        zmq_con = net_tools.zmq_connection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.zmq_context
        )
        conn_str = "tcp://{}:{:d}".format(
            scan_address,
            2001,
        )
        self.log(u"connection_str for {} is {}".format(unicode(scan_dev), conn_str))
        zmq_con.add_connection(
            conn_str,
            server_command.srv_command(command="network_info"),
            multi=True
        )
        res_list = zmq_con.loop()
        self.log("length of result list: {:d}".format(len(res_list)))
        num_taken, num_ignored = (0, 0)
        nds_list = netdevice_speed.objects.filter(Q(speed_bps__in=[1000000000, 100000000])).order_by("-speed_bps", "-full_duplex", "-check_via_ethtool")
        default_nds = nds_list[0]
        self.log("default nds is {}".format(unicode(default_nds)))

        for _idx, (result, target_dev) in enumerate(zip(res_list, [scan_dev])):
            self.log("device {} ...".format(unicode(target_dev)))
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                # num_errors += 1
                if res_state == -1:
                    res_node.error(u"{}: no result".format(unicode(target_dev)))
                else:
                    res_node.error(
                        u"{}: error {:d}: {}".format(
                            unicode(target_dev),
                            int(result["result"].attrib["state"]),
                            result["result"].attrib["reply"]
                        )
                    )
            else:
                try:
                    bridges = result["bridges"]
                    networks = result["networks"]
                except:
                    res_node.error(u"{}: error missing keys in dict".format(target_dev))
                else:
                    # clear current network
                    with transaction.atomic():
                        sid = transaction.savepoint()
                        # store current peers
                        _peers = [
                            _obj.store_before_delete(target_dev) for _obj in peer_information.objects.filter(
                                Q(s_netdevice__in=target_dev.netdevice_set.all()) |
                                Q(d_netdevice__in=target_dev.netdevice_set.all())
                            )
                        ]
                        _old_peer_dict = {}
                        for _old_peer in _peers:
                            _old_peer_dict.setdefault(_old_peer["my_name"], []).append(_old_peer)
                        # pprint.pprint(_old_peer_dict)
                        self.log("removing current network devices")
                        target_dev.netdevice_set.all().delete()
                        all_ok = True
                        _all_devs = set(networks)
                        _br_devs = set(bridges)
                        NDStruct.setup(self, target_dev, default_nds)
                        for dev_name in sorted(list(_all_devs & _br_devs)) + sorted(list(_all_devs - _br_devs)):
                            if any([dev_name.startswith(_ignore_pf) for _ignore_pf in IGNORE_LIST]):
                                self.log("ignoring device {}".format(dev_name))
                                num_ignored += 1
                                continue
                            _struct = networks[dev_name]
                            cur_nd = NDStruct(dev_name, _struct, bridges.get(dev_name, None))
                            try:
                                cur_nd.create()
                            except:
                                err_str = "error creating netdevice {}: {}".format(
                                    dev_name,
                                    process_tools.get_except_info())
                                if strict_mode:
                                    res_node.error(err_str)
                                for _log in process_tools.exception_info().log_lines:
                                    self.log("  {}".format(_log), logging_tools.LOG_LEVEL_CRITICAL)
                                all_ok = False
                            else:
                                num_taken += 1
                            if cur_nd.nd is not None and cur_nd.nd.devname in _old_peer_dict:
                                #  relink peers
                                for _peer in _old_peer_dict[cur_nd.nd.devname]:
                                    _new_peer = peer_information.create_from_store(_peer, cur_nd.nd)
                                del _old_peer_dict[cur_nd.nd.devname]
                        if _old_peer_dict.keys():
                            _err_str = "not all peers migrated: {}".format(", ".join(_old_peer_dict.keys()))
                            if strict_mode:
                                res_node.error(_err_str)
                                all_ok = False
                            else:
                                res_node.warn(_err_str)
                        [NDStruct.dict[_bridge_name].link_bridge_slaves() for _bridge_name in _br_devs & set(NDStruct.dict.keys())]
                        if not all_ok and strict_mode:
                            self.log("rolling back to savepoint because strict_mode is enabled", logging_tools.LOG_LEVEL_WARN)
                            num_taken -= target_dev.netdevice_set.all().count()
                            transaction.savepoint_rollback(sid)
                        else:
                            transaction.savepoint_commit(sid)
        if num_taken:
            res_node.ok("{} taken".format(logging_tools.get_plural("netdevice", num_taken)))
        if num_ignored:
            res_node.ok("{} ignored".format(logging_tools.get_plural("netdevice", num_ignored)))
        self.clear_scan(scan_dev)
        return res_node
