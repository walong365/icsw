# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
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
""" discovery-server, discovery part """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, partition, partition_disc, partition_table, \
    partition_fs, lvm_lv, lvm_vg, sys_partition, net_ip, netdevice, netdevice_speed, snmp_network_type, \
    network, network_type, snmp_schemes, domain_tree_node, DeviceSNMPInfo, peer_information
from initat.discovery_server.config import global_config
from initat.snmp_relay.snmp_process import simple_snmp_oid, simplify_dict
import base64
import bz2
import config_tools
import inspect
import ipvx_tools
import logging_tools
import net_tools
import partition_tools
import pprint  # @UnusedImport
import process_tools
import server_command
import threading_tools
import time

IGNORE_LIST = ["tun", "tap", "vnet"]


class snmp_if_counter(object):
    def __init__(self, octets, ucast_pkts, nucast_pkts, discards, errors):
        self.octets = octets
        self.ucast_pkts = ucast_pkts
        self.nucast_pkts = nucast_pkts
        self.discards = discards
        self.errors = errors


class snmp_if(object):
    def __init__(self, in_dict):
        self.idx = in_dict[1]
        self.name = in_dict[2]
        self.if_type = in_dict[3]
        self.mtu = in_dict[4]
        self.speed = in_dict[5]
        self.macaddr = ":".join(["{:02x}".format(ord(_val)) for _val in in_dict[6]])
        self.admin_status = in_dict[7]
        self.oper_status = in_dict[8]
        self.last_change = in_dict[9]
        self.in_counter = snmp_if_counter(in_dict[10], in_dict[11], in_dict[12], in_dict[13], in_dict[14])
        self.out_counter = snmp_if_counter(in_dict[16], in_dict[17], in_dict[18], in_dict[19], in_dict[20])
        self.in_unknown_protos = in_dict[15]

    def __repr__(self):
        return "if {} ({:d}), MTU is {:d}, type is {:d}".format(
            self.name,
            self.idx,
            self.mtu,
            self.if_type
        )


class snmp_ip(object):
    def __init__(self, in_dict):
        self.address = ".".join(["{:d}".format(ord(_val)) for _val in in_dict[1]])
        self.netmask = ".".join(["{:d}".format(ord(_val)) for _val in in_dict[3]])
        self.address_ipv4 = ipvx_tools.ipv4(self.address)
        self.netmask_ipv4 = ipvx_tools.ipv4(self.netmask)
        self.if_idx = in_dict[2]

    def __repr__(self):
        return "{}/{}".format(self.address, self.netmask)


class snmp_batch(object):
    def __init__(self, src_uid, srv_com):
        self.src_uid = src_uid
        self.srv_com = srv_com
        self.id = snmp_batch.next_snmp_batch_id()
        snmp_batch.add_batch(self)
        self.init_run(self.srv_com["*command"])
        self.batch_valid = True
        try:
            _dev = self.srv_com.xpath(".//ns:devices/ns:device")[0]
            self.device = device.objects.get(Q(pk=_dev.attrib["pk"]))
            self.log("device is {}".format(unicode(self.device)))
            self.set_snmp_props(
                int(_dev.attrib["snmp_version"]),
                _dev.attrib["snmp_address"],
                _dev.attrib["snmp_community"],
            )
            self.flags = {
                "strict": True if int(_dev.attrib.get("strict", "0")) else False,
            }
        except:
            _err_str = "error setting device node: {}".format(process_tools.get_except_info())
            self.log(_err_str, logging_tools.LOG_LEVEL_ERROR, result=True)
            self.batch_valid = False
            self.finish()
        else:
            self.start_run()

    def init_run(self, command):
        self.command = command
        self.__snmp_results = {}
        # (optional) mapping from run_id to snmp_scheme pk
        self.__start_time = time.time()
        self.log("init new batch with command {}".format(self.command))

    def start_run(self):
        if self.command == "snmp_basic_scan":
            _all_schemes = snmp_schemes()
            self.new_run(
                True,
                20,
                *[
                    ("T*", [simple_snmp_oid(_tl_oid.oid)]) for _tl_oid in _all_schemes.all_tl_oids()
                ]
            )
        else:
            self.log("unknown command '{}'".format(self.command), logging_tools.LOG_LEVEL_ERROR, result=True)
            self.finish()

    def set_snmp_props(self, version, address, com):
        self.snmp_version = version
        self.snmp_address = address
        self.snmp_community = com
        self.log("set snmp props to {}@{} (v{:d})".format(self.snmp_community, self.snmp_address, self.snmp_version))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, result=False):
        snmp_batch.process.log("[batch {:d}] {}".format(self.id, what), log_level)
        if result:
            self.srv_com.set_result(
                what,
                server_command.log_level_to_srv_reply(log_level)
            )

    def new_run(self, flag, timeout, *oid_list, **kwargs):
        if self.batch_valid:
            _run_id = snmp_batch.next_snmp_run_id(self.id)
            self.__snmp_results[_run_id] = None
            snmp_batch.process.send_pool_message(
                "snmp_run",
                self.snmp_version,
                self.snmp_address,
                self.snmp_community,
                _run_id,
                flag,
                timeout,
                *oid_list,
                **kwargs
            )
        else:
            self.log("cannot start run, batch is marked invalid", logging_tools.LOG_LEVEL_ERROR)

    def __del__(self):
        # print("delete batch {:d}".format(self.id))
        pass

    def feed_snmp(self, run_id, error, src, results):
        _res_dict = simplify_dict(results, (2, 1))
        self.__snmp_results[run_id] = (error, src, results)
        self.check_for_result()

    def check_for_result(self):
        if all(self.__snmp_results.values()):
            self.__end_time = time.time()
            # unify results
            # pprint.pprint(self.__snmp_results)
            # unify dict
            _errors, _found, _res_dict = ([], set(), {})
            for _key, _value in self.__snmp_results.iteritems():
                _errors.extend(_value[0])
                _found |= _value[1]
                _res_dict.update(_value[2])
            self.log(
                "finished batch in {} ({}, {})".format(
                    logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
                    logging_tools.get_plural("run", len(self.__snmp_results)),
                    logging_tools.get_plural("error", len(_errors)),
                )
            )
            attr_name = "handle_{}".format(self.command)
            if hasattr(self, attr_name):
                getattr(self, attr_name)(_errors, _found, _res_dict)
            else:
                self.log("dont know how to handle {}".format(self.command), logging_tools.LOG_LEVEL_ERROR, result=True)
                self.finish()

    def handle_snmp_initial_scan(self, errors, found, res_dict):
        _all_schemes = snmp_schemes()
        _found_struct = {}
        # reorganize oids to dict with scheme -> {..., oid_list, ...}
        for _oid in found:
            _found_scheme = _all_schemes.get_scheme_by_oid(_oid)
            if _found_scheme:
                _key = (_found_scheme.priority, _found_scheme.pk)
                if _key not in _found_struct:
                    _found_struct[_key] = {
                        "scheme": _found_scheme,
                        "oids": set(),
                        "full_name": _found_scheme.full_name,
                    }
                _found_struct[_key]["oids"].add(_all_schemes.oid_to_str(_oid))
        _handler = SNMPSink(self.log)
        result = ResultNode(error=errors)
        for _key in sorted(_found_struct, reverse=True):
            _struct = _found_struct[_key]
            result.merge(
                _handler.update(
                    self.device,
                    _struct["scheme"],
                    _all_schemes.filter_results(res_dict, _struct["oids"]),
                    _struct["oids"],
                    self.flags,
                )
            )
        self.srv_com.set_result(*result.get_srv_com_result())
        self.finish()

    def handle_snmp_basic_scan(self, errors, found, res_dict):
        _all_schemes = snmp_schemes()
        if found:
            # any found, delete all present schemes
            self.device.snmp_schemes.clear()
        _added_pks = set()
        for _oid in found:
            _add_scheme = _all_schemes.get_scheme_by_oid(_oid)
            if _add_scheme is not None and _add_scheme.pk not in _added_pks:
                _added_pks.add(_add_scheme.pk)
                self.device.snmp_schemes.add(_add_scheme)
        if _added_pks:
            _scan_schemes = [_all_schemes.get_scheme(_pk) for _pk in _added_pks if _all_schemes.get_scheme(_pk).initial]
            if _scan_schemes:
                self.init_run("snmp_initial_scan")
                for _scheme in _scan_schemes:
                    self.new_run(
                        True,
                        20,
                        *[
                            ("T", [simple_snmp_oid(_tl_oid.oid)]) for _tl_oid in _scheme.snmp_scheme_tl_oid_set.all()
                        ]
                    )
            else:
                self.log("found {}".format(logging_tools.get_plural("scheme", len(_added_pks))), result=True)
                self.finish()
        else:
            if errors:
                self.log(", ".join(errors), logging_tools.LOG_LEVEL_ERROR, result=True)
            else:
                self.log("initial scan was ok, but no schemes found", logging_tools.LOG_LEVEL_WARN, result=True)
            self.finish()

    def finish(self):
        self.send_return()
        snmp_batch.remove_batch(self)

    def send_return(self):
        self.process.send_pool_message("discovery_result", self.src_uid, unicode(self.srv_com))

    @staticmethod
    def glob_feed_snmp(_run_id, error, src, results):
        snmp_batch.batch_dict[snmp_batch.run_batch_lut[_run_id]].feed_snmp(_run_id, error, src, results)
        del snmp_batch.run_batch_lut[_run_id]

    @staticmethod
    def setup(proc):
        snmp_batch.process = proc
        snmp_batch.snmp_batch_id = 0
        snmp_batch.snmp_run_id = 0
        snmp_batch.pending = {}
        snmp_batch.run_batch_lut = {}
        snmp_batch.batch_dict = {}

    @staticmethod
    def next_snmp_run_id(batch_id):
        snmp_batch.snmp_run_id += 1
        snmp_batch.run_batch_lut[snmp_batch.snmp_run_id] = batch_id
        return snmp_batch.snmp_run_id

    @staticmethod
    def next_snmp_batch_id():
        snmp_batch.snmp_batch_id += 1
        return snmp_batch.snmp_batch_id

    @staticmethod
    def add_batch(batch):
        snmp_batch.batch_dict[batch.id] = batch

    @staticmethod
    def remove_batch(batch):
        del snmp_batch.batch_dict[batch.id]
        del batch


class nd_struct(object):
    def __init__(self, dev_name, in_dict, br_dict):
        self.dev_name = dev_name
        self.in_dict = in_dict
        self.br_dict = br_dict
        self.nd = None
        nd_struct.dict[self.dev_name] = self

    @staticmethod
    def setup(cur_inst, device, default_nds):
        nd_struct.cur_inst = cur_inst
        nd_struct.device = device
        nd_struct.default_nds = default_nds
        nd_struct.dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        nd_struct.cur_inst.log("[nd {}] {}".format(self.dev_name, what), log_level)

    def create(self):
        cur_nd = netdevice(
            device=nd_struct.device,
            devname=self.dev_name,
            netdevice_speed=nd_struct.default_nds,
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
            if _slave_name in nd_struct.dict:
                _slave_nd = nd_struct.dict[_slave_name].nd
                if _slave_nd is not None:
                    _slave_nd.bridge_device = self.nd
                    self.log("enslaving {}".format(_slave_name))
                    _slave_nd.save()


class discovery_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # self.add_process(build_process("build"), start=True)
        connection.close()
        self.register_func("fetch_partition_info", self._fetch_partition_info)
        self.register_func("scan_network_info", self._scan_network_info)
        self.register_func("snmp_basic_scan", self._snmp_basic_scan)
        self.register_func("snmp_result", self._snmp_result)
        self.__run_idx = 0
        self.__pending_commands = {}
        self._init_snmp()

    def _fetch_partition_info(self, *args, **kwargs):
        src_uid, srv_com = args[0:2]
        srv_com = server_command.srv_command(source=srv_com)
        self.fetch_partition_info(srv_com)
        self.send_pool_message("discovery_result", src_uid, unicode(srv_com))

    def _scan_network_info(self, *args, **kwargs):
        src_uid, srv_com = args[0:2]
        srv_com = server_command.srv_command(source=srv_com)
        self.scan_network_info(srv_com)
        self.send_pool_message("discovery_result", src_uid, unicode(srv_com))

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def fetch_partition_info(self, srv_com):
        target_pks = srv_com["device_pk"].text.split(",")
        self.log("got %s: %s" % (
            logging_tools.get_plural("pk", len(target_pks)),
            ", ".join(target_pks))
        )
        src_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        src_nds = src_dev.netdevice_set.all().values_list("pk", flat=True)
        target_devs = device.objects.filter(Q(pk__in=target_pks)).prefetch_related("netdevice_set")
        self.log("device list: %s" % (", ".join([unicode(cur_dev) for cur_dev in target_devs])))
        router_obj = config_tools.router_object(self.log)
        for cur_dev in target_devs:
            routes = router_obj.get_ndl_ndl_pathes(
                src_nds,
                cur_dev.netdevice_set.all().values_list("pk", flat=True),
                only_endpoints=True,
                add_penalty=True)
            cur_dev.target_ip = None
            if routes:
                for route in sorted(routes):
                    found_ips = net_ip.objects.filter(Q(netdevice=route[2]))
                    if found_ips:
                        cur_dev.target_ip = found_ips[0].ip
                        break
            if cur_dev.target_ip:
                self.log(
                    "contact device %s via %s" % (
                        unicode(cur_dev),
                        cur_dev.target_ip
                    )
                )
            else:
                self.log(
                    u"no route to device {} found".format(unicode(cur_dev)),
                    logging_tools.LOG_LEVEL_ERROR
                )
        del router_obj
        zmq_con = net_tools.zmq_connection(
            "server:%s" % (process_tools.get_machine_name()),
            context=self.zmq_context)
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
        num_errors, num_warnings, ret_f = (0, 0, [])
        for _idx, (result, target_dev) in enumerate(zip(res_list, result_devs)):
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                num_errors += 1
                if res_state == -1:
                    ret_f.append(u"%s: no result" % (unicode(target_dev)))
                else:
                    ret_f.append(u"%s: error %d: %s" % (
                        unicode(target_dev),
                        int(result["result"].attrib["state"]),
                        result["result"].attrib["reply"]))
            else:
                try:
                    dev_dict, sys_dict, lvm_dict = (
                        result["dev_dict"],
                        result["sys_dict"],
                        result["lvm_dict"],
                    )
                except KeyError:
                    num_errors += 1
                    ret_f.append(u"%s: error missing keys in dict" % (target_dev))
                else:
                    try:
                        _old_stuff = bz2.decompress(base64.b64decode(lvm_dict.text))
                    except:
                        lvm_info = partition_tools.lvm_struct("xml", xml=lvm_dict)
                    else:
                        raise ValueError("it seems the client is using pickled transfers")
                    partition_name, partition_info = (
                        "%s_part" % (target_dev.full_name),
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
                ret_f.append(u"%s: %s, %s, %s and %s" % (
                    target_dev,
                    logging_tools.get_plural("disc", len(dev_dict.keys())),
                    logging_tools.get_plural("sys_partition", len(sys_dict.keys())),
                    logging_tools.get_plural("volumegroup", len(lvm_info.lv_dict.get("vg", {}).keys())),
                    logging_tools.get_plural("logical volume", len(lvm_info.lv_dict.get("lv", {}).keys()))))
        if num_errors:
            srv_com.set_result(u"error %s" % ("; ".join(ret_f)), server_command.SRV_REPLY_STATE_ERROR)
        elif num_warnings:
            srv_com.set_result(u"warning %s" % ("; ".join(ret_f)), server_command.SRV_REPLY_STATE_WARN)
        else:
            srv_com.set_result(u"ok %s" % ("; ".join(ret_f)), server_command.SRV_REPLY_STATE_OK)

    def scan_network_info(self, srv_com):
        dev_pk = int(srv_com["*pk"])
        strict_mode = True if int(srv_com["*strict_mode"]) else False
        scan_address = srv_com["*scan_address"]
        scan_dev = device.objects.get(Q(pk=dev_pk))
        self.log("scanning network for device '{}' ({:d}), scan_address is '{}', strict_mode is {}".format(
            unicode(scan_dev),
            scan_dev.pk,
            scan_address,
            "on" if strict_mode else "off",
            ))
        zmq_con = net_tools.zmq_connection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.zmq_context)
        conn_str = "tcp://{}:{:d}".format(
            scan_address,
            2001)
        self.log(u"connection_str for {} is {}".format(unicode(scan_dev), conn_str))
        zmq_con.add_connection(
            conn_str,
            server_command.srv_command(command="network_info"),
            multi=True
        )
        res_list = zmq_con.loop()
        self.log("length of result list: {:d}".format(len(res_list)))
        num_errors, ret_f = (0, [])
        num_taken, num_ignored, num_warnings = (0, 0, 0)
        nds_list = netdevice_speed.objects.filter(Q(speed_bps__in=[1000000000, 100000000])).order_by("-speed_bps", "-full_duplex", "-check_via_ethtool")
        default_nds = nds_list[0]
        self.log("default nds is {}".format(unicode(default_nds)))
        for _idx, (result, target_dev) in enumerate(zip(res_list, [scan_dev])):
            self.log("device {} ...".format(unicode(target_dev)))
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                num_errors += 1
                if res_state == -1:
                    ret_f.append(u"{}: no result".format(unicode(target_dev)))
                else:
                    ret_f.append(u"{}: error {:d}: {}".format(
                        unicode(target_dev),
                        int(result["result"].attrib["state"]),
                        result["result"].attrib["reply"]))
            else:
                try:
                    bridges = result["bridges"]
                    networks = result["networks"]
                except:
                    num_errors += 1
                    ret_f.append(u"{}: error missing keys in dict".format(target_dev))
                else:
                    # clear current network
                    self.log("removing current network devices")
                    target_dev.netdevice_set.all().delete()
                    all_ok = True
                    _all_devs = set(networks)
                    _br_devs = set(bridges)
                    nd_struct.setup(self, target_dev, default_nds)
                    for dev_name in sorted(list(_all_devs & _br_devs)) + sorted(list(_all_devs - _br_devs)):
                        if any([dev_name.startswith(_ignore_pf) for _ignore_pf in IGNORE_LIST]):
                            self.log("ignoring device {}".format(dev_name))
                            num_ignored += 1
                            continue
                        _struct = networks[dev_name]
                        cur_nd = nd_struct(dev_name, _struct, bridges.get(dev_name, None))
                        try:
                            cur_nd.create()
                        except:
                            err_str = "error creating netdevice {}: {}".format(
                                dev_name,
                                process_tools.get_except_info())
                            ret_f.append(err_str)
                            for _log in process_tools.exception_info().log_lines:
                                self.log("  {}".format(_log), logging_tools.LOG_LEVEL_CRITICAL)
                            all_ok = False
                            num_errors += 1
                        else:
                            num_taken += 1
                    [nd_struct.dict[_bridge_name].link_bridge_slaves() for _bridge_name in _br_devs & set(nd_struct.dict.keys())]
                    if not all_ok and strict_mode:
                        self.log("removing netdevices because strict_mode is enabled", logging_tools.LOG_LEVEL_WARN)
                        num_taken -= target_dev.netdevice_set.all().count()
                        target_dev.netdevice_set.all().delete()
        if num_taken:
            ret_f.append("{} taken".format(logging_tools.get_plural("netdevice", num_taken)))
        if num_ignored:
            ret_f.append("{} ignored".format(logging_tools.get_plural("netdevice", num_ignored)))
        if not ret_f:
            ret_f = ["nothing to log"]
        if num_errors:
            srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_ERROR)
        elif num_warnings:
            srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_WARN)
        else:
            srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_OK)

    def _init_snmp(self):
        snmp_batch.setup(self)

    def _snmp_basic_scan(self, *args, **kwargs):
        src_uid, srv_com = args[0:2]
        snmp_batch(src_uid, server_command.srv_command(source=srv_com))

    def _snmp_result(self, *args, **kwargs):
        _batch_id, _error, _src, _results = args
        snmp_batch.glob_feed_snmp(_batch_id, _error, _src, _results)


class ResultNode(object):
    def __init__(self, **kwargs):
        for inst_name in ["ok", "warn", "error"]:
            _target = "{}_list".format(inst_name)
            _val = kwargs.get(inst_name, [])
            if _val is None:
                _val = []
            elif type(_val) != list:
                _val = [_val]
            setattr(self, _target, _val)

    def merge(self, other_node):
        self.ok_list.extend(other_node.ok_list)
        self.warn_list.extend(other_node.warn_list)
        self.error_list.extend(other_node.error_list)

    def __repr__(self):
        return "; ".join(
            [
                "{:d} {}: {}".format(
                    len(_val),
                    _val_name,
                    ", ".join(_val)
                ) for _val, _val_name in [
                    (self.ok_list, "ok"),
                    (self.warn_list, "warn"),
                    (self.error_list, "error"),
                ] if _val
            ]
        ) or "empty ResultNode"

    def get_srv_com_result(self):
        if self.error_list:
            _state = server_command.SRV_REPLY_STATE_ERROR
        elif self.warn_list:
            _state = server_command.SRV_REPLY_STATE_WARN
        else:
            _state = server_command.SRV_REPLY_STATE_OK
        return unicode(self), _state


class SNMPHandler(object):
    def __init__(self, log_com):
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[SH] {}".format(what), log_level)


class generic_base_handler(SNMPHandler):
    class Meta:
        oids = ["generic.base"]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        try:
            _cur_info = dev.DeviceSNMPInfo
        except DeviceSNMPInfo.DoesNotExist:
            _cur_info = DeviceSNMPInfo(device=dev)
        _dict = simplify_dict(result_dict[list(oid_list)[0]], ())
        for _idx, attr, default in [
            (1, "description", "???"),
            (4, "contact", "???"),
            (5, "name", "???"),
            (6, "location", "???"),
            (8, "services", 0),
        ]:
            setattr(_cur_info, attr, _dict[0].get(_idx, default))
        _cur_info.save()
        return ResultNode(ok="set Infos")


class generic_net_handler(SNMPHandler):
    class Meta:
        oids = ["generic.net"]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        _if_dict = {key: snmp_if(value) for key, value in simplify_dict(result_dict["1.3.6.1.2.1.2"], (2, 1)).iteritems()}
        snmp_type_dict = {_value.if_type: _value for _value in snmp_network_type.objects.all()}
        speed_dict = {}
        for _entry in netdevice_speed.objects.all().order_by("-check_via_ethtool", "-full_duplex"):
            if _entry.speed_bps not in speed_dict:
                speed_dict[_entry.speed_bps] = _entry
        _added, _updated, _removed = (0, 0, 0)
        # found and used database ids (for deletion)
        _found_nd_ids = set()
        # lookup dict for snmp_if -> dev_nd
        for if_idx, if_struct in _if_dict.iteritems():
            _created = False
            try:
                # try to get interface with matching idx
                _dev_nd = netdevice.objects.get(Q(device=dev) & Q(snmp_idx=if_idx))
            except netdevice.DoesNotExist:
                try:
                    # try to get interface with matching name
                    _dev_nd = netdevice.objects.get(Q(device=dev) & Q(devname=if_struct.name))
                except:
                    _created = True
                    _added += 1
                    # create new entry, will be updated later with more values
                    _dev_nd = netdevice(
                        device=dev,
                        snmp_idx=if_idx,
                        force_network_device_type_match=False,
                    )
            if _dev_nd is not None:
                if not _created:
                    _updated += 1
                _dev_nd.devname = if_struct.name
                _dev_nd.netdevice_speed = speed_dict.get(if_struct.speed, speed_dict[0])
                _dev_nd.snmp_network_type = snmp_type_dict[if_struct.if_type]
                _dev_nd.mtu = if_struct.mtu
                _dev_nd.macaddr = if_struct.macaddr
                _dev_nd.snmp_admin_status = if_struct.admin_status
                _dev_nd.snmp_oper_status = if_struct.oper_status
                _dev_nd.save()
                _found_nd_ids.add(_dev_nd.idx)
        if flags["strict"]:
            stale_nds = netdevice.objects.exclude(Q(pk__in=_found_nd_ids)).filter(Q(device=dev))
            if stale_nds.count():
                _remove = True
                _stale_ids = [_nd.idx for _nd in stale_nds]
                # check peers
                stale_peers = peer_information.objects.filter(Q(s_netdevice__in=_stale_ids) | Q(d_netdevice__in=_stale_ids))
                if stale_peers.count():
                    # relink stale peers to first new netdevice
                    if _found_nd_ids:
                        relink_nd = netdevice.objects.get(Q(pk=list(_found_nd_ids)[0]))
                        for stale_peer in stale_peers:
                            if stale_peer.s_netdevice_id in _stale_ids and stale_peer.d_netdevice_id in _stale_ids:
                                # source and dest will be delete, delete this peer
                                pass
                            elif stale_peer.s_netdevice_id in _stale_ids:
                                stale_peer.s_netdevice = relink_nd
                                stale_peer.save()
                            else:
                                stale_peer.d_netdevice = relink_nd
                                stale_peer.save()
                    else:
                        # no netdevices found, skip removing stale nds
                        _remove = False
                if _remove:
                    _removed += stale_nds.count()
                    stale_nds.delete()
        return ResultNode(
            ok="updated interfaces (added {:d}, updated {:d}, removed {:d})".format(
                _added,
                _updated,
                _removed,
            )
        )


class generic_netip_handler(SNMPHandler):
    class Meta:
        oids = ["generic.netip"]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # ip dict
        _ip_dict = {key: snmp_ip(value) for key, value in simplify_dict(result_dict["1.3.6.1.2.1.4.20"], (1,)).iteritems()}
        if dev.domain_tree_node_id:
            _tln = dev.domain_tree_node
        else:
            _tln = domain_tree_node.objects.get(Q(depth=0))
        if_lut = {_dev_nd.snmp_idx: _dev_nd for _dev_nd in netdevice.objects.filter(Q(snmp_idx__gt=0) & Q(device=dev))}
        # handle IPs
        _found_ip_ids = set()
        _added = 0
        for ip_struct in _ip_dict.itervalues():
            if ip_struct.if_idx in if_lut:
                _dev_nd = if_lut[ip_struct.if_idx]
                # check for network
                _network_addr = ip_struct.address_ipv4 & ip_struct.netmask_ipv4
                try:
                    cur_nw = network.objects.get(Q(network=str(_network_addr)) & Q(netmask=ip_struct.netmask))  # @UndefinedVariable
                except network.DoesNotExist:  # @UndefinedVariable
                    # create new network
                    cur_nw = network(
                        network_type=network_type.objects.get(Q(identifier='o')),
                        short_names=False,
                        identifier=network.get_unique_identifier(),  # @UndefinedVariable
                        name="autogenerated",
                        info="autogenerated",
                        network=str(_network_addr),
                        netmask=ip_struct.netmask,
                        gateway=str(_network_addr + ipvx_tools.ipv4("0.0.0.1")),
                        broadcast=str(~ip_struct.netmask_ipv4 | (_network_addr & ip_struct.netmask_ipv4)),
                    )
                    cur_nw.save()
                # check for existing IP
                try:
                    _ip = net_ip.objects.get(Q(netdevice__device=dev) & Q(ip=ip_struct.address))
                except net_ip.DoesNotExist:
                    _added += 1
                    _ip = net_ip(
                        ip=ip_struct.address,
                    )
                _ip.domain_tree_node = _tln
                _ip.network = cur_nw
                _ip.netdevice = _dev_nd
                _ip.save()
                _found_ip_ids.add(_ip.idx)
        if flags["strict"]:
            stale_ips = net_ip.objects.exclude(Q(pk__in=_found_ip_ids)).filter(Q(netdevice__device=dev))
            if stale_ips.count():
                stale_ips.delete()
        if _added:
            return ResultNode(ok="updated IPs (added: {:d})".format(_added))
        else:
            return ResultNode()


class SNMPSink(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        # possible handlers
        self.__handlers = [
            _value for _key, _value in globals().iteritems() if inspect.isclass(
                _value
            ) and issubclass(
                _value, SNMPHandler
            ) and _value != SNMPHandler
        ]
        # registered handlers
        self.__reg_handlers = {}
        self.log("init ({} found)".format(logging_tools.get_plural("handler", len(self.__handlers))))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[SS] {}".format(what), log_level)

    def get_handler(self, scheme):
        full_name, full_name_version = (scheme.full_name, scheme.full_name_version)
        if full_name_version not in self.__reg_handlers:
            # search for full name with version
            _v_found, _found = ([], [])
            for _handler in self.__handlers:
                if full_name_version in _handler.Meta.oids:
                    _v_found.append(_handler)
                if full_name in _handler.Meta.oids:
                    _found.append(_handler)
            if _v_found:
                self.__reg_handlers[full_name_version] = _v_found[0](self.__log_com)
            elif _found:
                self.__reg_handlers[full_name_version] = _found[0](self.__log_com)
            else:
                self.log("no handlers found for {} or {}".format(full_name_version, full_name), logging_tools.LOG_LEVEL_ERROR)
                self.__reg_handlers[full_name_version] = None
        return self.__reg_handlers[full_name_version]

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # update dev with results from given snmp_scheme
        # valid oid_list is oid_list
        # results are in result_dict
        _handler = self.get_handler(scheme)
        if _handler:
            try:
                return _handler.update(dev, scheme, result_dict, oid_list, flags)
            except:
                exc_info = process_tools.exception_info()
                _err_str = "unable to process results: {}".format(process_tools.get_except_info())
                self.log(_err_str, logging_tools.LOG_LEVEL_ERROR)
                for _line in exc_info.log_lines:
                    self.log("  {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
                return ResultNode(error=_err_str)
        else:
            return ResultNode(error="no handler found for {}".format(scheme.full_name_version))
