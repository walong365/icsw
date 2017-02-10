# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

import subprocess
import tempfile
import time

from django.db import transaction
from django.db.models import Q
from lxml import etree

from initat.cluster.backbone.exceptions import NoMatchingNetworkDeviceTypeFoundError, \
    NoMatchingNetworkFoundError
from initat.cluster.backbone.models import net_ip, netdevice, \
    netdevice_speed, peer_information, DeviceLogEntry, DeviceInventory
from initat.icsw.service.instance import InstanceXML
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, net_tools, process_tools, server_command, dmi_tools, pci_database
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
    def setup(cur_inst, device, default_nds, bond_dict):
        NDStruct.cur_inst = cur_inst
        NDStruct.device = device
        NDStruct.default_nds = default_nds
        NDStruct.bond_dict = bond_dict
        NDStruct.dict = {}

    @staticmethod
    def handle_bonds():
        for _master_name, _struct in NDStruct.bond_dict.items():
            _master = NDStruct.dict[_master_name]
            _master.nd.is_bond = True
            _master.nd.save(update_fields=["is_bond"])
            for _slave_name in _struct["slaves"]:
                _slave = NDStruct.dict[_slave_name]
                _slave.nd.bond_master = _master.nd
                _slave.nd.save(update_fields=["bond_master"])

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
            self.log("added IP {} (network {})".format(new_ip.ip, str(new_ip.network)))

    def link_bridge_slaves(self):
        for _slave_name in self.br_dict.get("interfaces", []):
            if _slave_name in NDStruct.dict:
                _slave_nd = NDStruct.dict[_slave_name].nd
                if _slave_nd is not None:
                    _slave_nd.bridge_device = self.nd
                    self.log("enslaving {}".format(_slave_name))
                    _slave_nd.save()


class HostMonitoringMixin(object):
    def _interpret_lstopo(self, lstopo_dump):
        return etree.fromstring(lstopo_dump)

    def _interpret_dmiinfo(self, dmi_dump):
        with tempfile.NamedTemporaryFile() as tmp_file:
            open(tmp_file.name, "w").write(dmi_dump)
            _dmi_stat, dmi_result = subprocess.getstatusoutput(
                "{} --from-dump {}".format(
                    process_tools.find_file("dmidecode"),
                    tmp_file.name,
                )
            )
        _dict = dmi_tools.parse_dmi_output(dmi_result.split("\n"))
        _xml = dmi_tools.dmi_struct_to_xml(_dict)
        return _xml

    def _interpret_pciinfo(self, pci_dump):
        _xml = pci_database.pci_struct_to_xml(pci_dump)
        return _xml

    def scan_system_info(self, dev_com, scan_dev):
        hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        res_node = ResultNode()
        s_time = time.time()
        self.get_route_to_devices([scan_dev])
        self.log(
            "scanning system for device '{}' ({:d}), scan_address is '{}'".format(
                str(scan_dev),
                scan_dev.pk,
                scan_dev.target_ip,
            )
        )
        zmq_con = net_tools.ZMQConnection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.zmq_context
        )
        conn_str = "tcp://{}:{:d}".format(
            scan_dev.target_ip,
            hm_port,
        )
        self.log("connection_str for {} is {}".format(str(scan_dev), conn_str))
        zmq_con.add_connection(
            conn_str,
            server_command.srv_command(command="sysinfo"),
            multi=True,
        )
        res_list = zmq_con.loop()
        e_time = time.time()
        for _idx, (_dev, _res) in enumerate(zip([scan_dev], res_list)):
            if _res:
                _to_save = []
                for _dt, _kwargs, _cbf in [
                    ("lstopo_dump", {}, self._interpret_lstopo),
                    ("dmi_dump", {}, self._interpret_dmiinfo),
                    ("pci_dump", {"marshal": True}, self._interpret_pciinfo),
                ]:
                    if _dt in _res:
                        _data = _cbf(server_command.decompress(_res["*{}".format(_dt)], **_kwargs))
                        if _data is not None:
                            _to_save.append((_dt.split("_")[0], _data))
                    else:
                        self.log("missing {} in result".format(_dt), logging_tools.LOG_LEVEL_WARN)
                if _to_save:
                    _highest_run = _dev.deviceinventory_set.all().order_by("-idx")
                    if _highest_run.count():
                        _highest_run = _highest_run[0].run_idx
                    else:
                        _highest_run = 0
                    _highest_run += 1
                    self.log(
                        "{} trees to save ({}), run_idx is {:d}".format(
                            logging_tools.get_plural("inventory tree", len(_to_save)),
                            ", ".join(sorted([_tuple[0] for _tuple in _to_save])),
                            _highest_run,
                        )
                    )
                    for _name, _tree in _to_save:
                        inv = DeviceInventory(
                            device=_dev,
                            inventory_type=_name,
                            run_idx=_highest_run,
                            value=etree.tostring(_tree)
                        )
                        inv.save()
                else:
                    self.log("no trees to save", logging_tools.LOG_LEVEL_WARN)
                DeviceLogEntry.new(
                    device=_dev,
                    source=global_config["LOG_SOURCE_IDX"],
                    level=logging_tools.LOG_LEVEL_OK,
                    text="system scan took {}, {:d} trees".format(
                        logging_tools.get_diff_time_str(
                            e_time - s_time,
                        ),
                        len(_to_save),
                    ),
                )
            else:
                DeviceLogEntry.new(
                    device=_dev,
                    source=global_config["LOG_SOURCE_IDX"],
                    level=logging_tools.LOG_LEVEL_ERROR,
                    text="error scanning system (took {})".format(
                        logging_tools.get_diff_time_str(
                            e_time - s_time,
                        )
                    ),
                )

        res_node.ok("system scanned")
        return res_node

    def scan_network_info(self, dev_com, scan_dev):
        hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        res_node = ResultNode()
        strict_mode = True if int(dev_com.get("strict_mode")) else False
        modify_peering = True if int(dev_com.get("modify_peering")) else False
        scan_address = dev_com.get("scan_address")
        self.log(
            "scanning network for device '{}' ({:d}), scan_address is '{}', strict_mode is {}".format(
                str(scan_dev),
                scan_dev.pk,
                scan_address,
                "on" if strict_mode else "off",
            )
        )
        zmq_con = net_tools.ZMQConnection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.zmq_context
        )
        conn_str = "tcp://{}:{:d}".format(
            scan_address,
            hm_port,
        )
        self.log("connection_str for {} is {}".format(str(scan_dev), conn_str))
        zmq_con.add_connection(
            conn_str,
            server_command.srv_command(command="network_info"),
            multi=True
        )
        res_list = zmq_con.loop()
        self.log("length of result list: {:d}".format(len(res_list)))
        num_taken, num_ignored = (0, 0)
        nds_list = netdevice_speed.objects.filter(
            Q(speed_bps__in=[1000000000, 100000000])
        ).order_by("-speed_bps", "-full_duplex", "-check_via_ethtool")
        default_nds = nds_list[0]
        self.log("default nds is {}".format(str(default_nds)))

        for _idx, (result, target_dev) in enumerate(zip(res_list, [scan_dev])):
            self.log("device {} ...".format(str(target_dev)))
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                # num_errors += 1
                if res_state == -1:
                    res_node.error("{}: no result".format(str(target_dev)))
                else:
                    res_node.error(
                        "{}: error {:d}: {}".format(
                            str(target_dev),
                            int(result["result"].attrib["state"]),
                            result["result"].attrib["reply"]
                        )
                    )
            else:
                try:
                    bridges = result["bridges"]
                    networks = result["networks"]
                except:
                    res_node.error("{}: error missing keys in dict".format(target_dev))
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
                        self.log("removing current network devices")
                        target_dev.netdevice_set.all().delete()
                        all_ok = True
                        exc_dict = {}
                        _all_devs = set(networks)
                        _br_devs = set(bridges)
                        # build bond dict
                        bond_dict = {}
                        for dev_name in _all_devs:
                            _struct = networks[dev_name]
                            if "MASTER" in _struct["flags"]:
                                bond_dict[dev_name] = {"slaves": []}
                        for dev_name in _all_devs:
                            _struct = networks[dev_name]
                            if "SLAVE" in _struct["flags"]:
                                master_name = _struct["features"]["master"]
                                bond_dict[master_name]["slaves"].append(dev_name)
                        NDStruct.setup(self, target_dev, default_nds, bond_dict)
                        for dev_name in sorted(list(_all_devs & _br_devs)) + sorted(list(_all_devs - _br_devs)):
                            if any([dev_name.startswith(_ignore_pf) for _ignore_pf in IGNORE_LIST]):
                                self.log("ignoring device {}".format(dev_name))
                                num_ignored += 1
                                continue
                            _struct = networks[dev_name]
                            cur_nd = NDStruct(dev_name, _struct, bridges.get(dev_name, None))
                            try:
                                cur_nd.create()
                            except (NoMatchingNetworkDeviceTypeFoundError, NoMatchingNetworkFoundError) as exc:
                                _name = exc.__class__.__name__
                                self.log("caught {} for {}".format(_name, dev_name), logging_tools.LOG_LEVEL_ERROR)
                                exc_dict.setdefault(_name, []).append(dev_name)
                                all_ok = False
                            except:
                                err_str = "error creating netdevice {}: {}".format(
                                    dev_name,
                                    process_tools.get_except_info()
                                )
                                if strict_mode:
                                    res_node.error(err_str)
                                for _log in process_tools.icswExceptionInfo().log_lines:
                                    self.log("  {}".format(_log), logging_tools.LOG_LEVEL_CRITICAL)
                                all_ok = False
                            else:
                                num_taken += 1
                            if cur_nd.nd is not None and cur_nd.nd.devname in _old_peer_dict:
                                #  relink peers
                                for _peer in _old_peer_dict[cur_nd.nd.devname]:
                                    _new_peer = peer_information.create_from_store(_peer, cur_nd.nd)
                                del _old_peer_dict[cur_nd.nd.devname]
                        if all_ok:
                            NDStruct.handle_bonds()
                        if exc_dict:
                            for key in sorted(exc_dict.keys()):
                                res_node.error(
                                    "{} for {}: {}".format(
                                        key,
                                        logging_tools.get_plural("netdevice", len(exc_dict[key])),
                                        ", ".join(sorted(exc_dict[key]))
                                    )
                                )
                        if list(_old_peer_dict.keys()):
                            _err_str = "not all peers migrated: {}".format(", ".join(list(_old_peer_dict.keys())))
                            if strict_mode:
                                res_node.error(_err_str)
                                all_ok = False
                            else:
                                res_node.warn(_err_str)
                        [
                            NDStruct.dict[_bridge_name].link_bridge_slaves() for _bridge_name in _br_devs & set(NDStruct.dict.keys())
                        ]
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
        return res_node
