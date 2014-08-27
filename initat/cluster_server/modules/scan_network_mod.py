# Copyright (C) 2014 Andreas Lang-Nevyjel
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
""" connects to remote device to scan its network device(s) """

from django.db.models import Q
from initat.cluster.backbone.models import device, netdevice, net_ip, netdevice_speed, get_related_models
import cs_base_class
import logging_tools
import net_tools
import process_tools
import server_command

IGNORE_LIST = ["tun", "tap", "vnet"]


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


class scan_network_info(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["pk", "scan_address", "strict_mode"]

    def _call(self, cur_inst):
        # print cur_inst.option_dict
        dev_pk = int(cur_inst.option_dict["pk"])
        strict_mode = True if int(cur_inst.option_dict["strict_mode"]) else False
        scan_address = cur_inst.option_dict["scan_address"]
        scan_dev = device.objects.get(Q(pk=dev_pk))
        cur_inst.log("scanning network for device '{}' ({:d}), scan_address is '{}', strict_mode is {}".format(
            unicode(scan_dev),
            scan_dev.pk,
            scan_address,
            "on" if strict_mode else "off",
            ))
        zmq_con = net_tools.zmq_connection(
            "server:{}".format(process_tools.get_machine_name()),
            context=self.process_pool.zmq_context)
        conn_str = "tcp://{}:{:d}".format(
            scan_address,
            2001)
        cur_inst.log(u"connection_str for {} is {}".format(unicode(scan_dev), conn_str))
        zmq_con.add_connection(
            conn_str,
            server_command.srv_command(command="network_info"),
            multi=True
        )
        res_list = zmq_con.loop()
        cur_inst.log("length of result list: {:d}".format(len(res_list)))
        num_errors, ret_f = (0, [])
        num_taken, num_ignored, num_warnings = (0, 0, 0)
        nds_list = netdevice_speed.objects.filter(Q(speed_bps__in=[1000000000, 100000000])).order_by("-speed_bps", "-full_duplex", "-check_via_ethtool")
        default_nds = nds_list[0]
        cur_inst.log("default nds is {}".format(unicode(default_nds)))
        for _idx, (result, target_dev) in enumerate(zip(res_list, [scan_dev])):
            cur_inst.log("device {} ...".format(unicode(target_dev)))
            # print idx, result, target_dev
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
                    cur_inst.log("removing current network devices")
                    target_dev.netdevice_set.all().delete()
                    all_ok = True
                    _all_devs = set(networks)
                    _br_devs = set(bridges)
                    nd_struct.setup(cur_inst, target_dev, default_nds)
                    for dev_name in sorted(list(_all_devs & _br_devs)) + sorted(list(_all_devs - _br_devs)):
                        if any([dev_name.startswith(_ignore_pf) for _ignore_pf in IGNORE_LIST]):
                            cur_inst.log("ignoring device {}".format(dev_name))
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
                                cur_inst.log("  {}".format(_log), logging_tools.LOG_LEVEL_CRITICAL)
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
            cur_inst.srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_ERROR)
        elif num_warnings:
            cur_inst.srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_WARN)
        else:
            cur_inst.srv_com.set_result(u"; ".join(ret_f), server_command.SRV_REPLY_STATE_OK)
