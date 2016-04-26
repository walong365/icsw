# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" node control related parts of mother """

import os
import re
import select
import shutil
import stat
import time

from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, macbootlog, mac_ignore, \
    log_source_lookup, LogSource, DeviceLogEntry, user
from initat.tools import config_tools, configfile, icmp_class, ipvx_tools, logging_tools, \
    process_tools, server_command, threading_tools
from .command_tools import simple_command
from .config import global_config
from .devicestate import DeviceState
from .dhcp import DHCPCommand, DHCPSyncer


class Host(object):
    # store important device-related settings
    def __init__(self, dev):
        self.device = dev
        self.name = dev.name
        self.full_name = dev.full_name
        self.pk = dev.pk
        self.__source_idx = global_config["LOG_SOURCE_IDX"]
        self.__log_template = logging_tools.get_logger(
            "{}.{}".format(
                global_config["LOG_NAME"],
                self.name.replace(".", r"\.")
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=Host.process.zmq_context,
            init_logger=True
        )
        self.log("added client, type is {}".format("META" if self.device.is_meta_device else "real"))
        self.additional_lut_keys = set()
        # clear ip_dict
        self.ip_dict = {}
        # clear maintenance ip/mac
        self.set_maint_ip()
        assert not self.device.uuid, "device {} has no uuid".format(unicode(self.device))
        Host.add_lut_key(self, "pk", self.device.pk)
        Host.add_lut_key(self, "uuid", self.device.uuid)
        Host.add_lut_key(self, "boot_uuid", self.device.get_boot_uuid())

    def init(self):
        pass

    def close(self):
        for add_key in self.additional_lut_keys:
            Host.del_lut_key(self, add_key)
        self.additional_lut_keys = set()
        self.__log_template.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, device_log=False):
        self.__log_template.log(log_level, what)

    @staticmethod
    def setup(c_process, dhcp_syncer, device_state):
        Host.process = c_process
        Host.dhcp_syncer = dhcp_syncer
        Host.device_state = device_state
        Host.debug = global_config["DEBUG"]
        Host.eb_dir = global_config["ETHERBOOT_DIR"]
        Host.iso_dir = global_config["ISO_DIR"]
        Host.g_log("init (etherboot_dir={}, isos in{})".format(Host.eb_dir, Host.iso_dir))
        Host.__lut = {}
        Host.__name_lut = {}
        # pks
        Host.__unique_keys = set()

    @staticmethod
    def name_keys(name):
        return Host.__name_lut.get(name, {}).keys()

    @staticmethod
    def shutdown():
        [
            Host.delete_device(_key, remove_from_unique_keys=False) for _key in Host.__unique_keys
        ]
        Host.__unique_keys = set()

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        Host.process.log("[mach] {}".format(what), log_level)

    @staticmethod
    def get_query(names=[], ips=[], pks=[], exclude_existing=True):
        query = device.all_real_enabled.filter(
            Q(bootserver=Host.process.sc.effective_device)
        )
        if exclude_existing:
            query = query.exclude(
                Q(pk__in=Host.name_keys("pk"))
            )
        query = query.prefetch_related(
            "domain_tree_node",
            "netdevice_set",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type",
        ).select_related(
            "bootnetdevice"
        )
        if names:
            query = query.filter(Q(name__in=names))
        if ips:
            query = query.filter(Q(netdevice__net_ip__ip__in=ips))
        if pks:
            query = query.filter(Q(pk__in=pks))
        return query

    def refresh_device(self):
        # fetch db-info, ignore when the device is already present
        found_devs = Host.get_query(names=[self.device.name], exclude_existing=False)
        if len(found_devs) == 1:
            self.device = found_devs[0]
        elif not len(found_devs):
            self.device = None
            self.log("device has vanished from database ...", logging_tools.LOG_LEVEL_ERROR)

    @staticmethod
    def sync(names=[], ips=[], pks=[]):
        s_time = time.time()
        query = Host.get_query(names=names, ips=ips, pks=pks)
        # from django.db import connection
        # import pprint
        # pprint.pprint(connection.queries)
        _added = len(query)
        if _added:
            Host.g_log(
                "found {}: {}".format(
                    logging_tools.get_plural("device", _added),
                    logging_tools.compress_list([cur_dev.name for cur_dev in query])
                )
            )
            for cur_dev in query:
                Host.set_device(cur_dev)
        else:
            Host.g_log(
                "found no hosts",
                logging_tools.LOG_LEVEL_WARN,
            )
        e_time = time.time()
        Host.g_log("sync took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))
        return _added
        # pprint.pprint(connection.queries)

    @staticmethod
    def add_lut_key(obj, key_name, key):
        if key in Host.__lut:
            Host.g_log(
                "key '{}' already set in Host.__lut ({} set, obj is {})".format(
                    key,
                    Host.__lut[key].name,
                    obj.name,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            Host.__lut[key] = obj
            Host.__name_lut.setdefault(key_name, {})[key] = obj
            obj.additional_lut_keys.add(key)

    @staticmethod
    def del_lut_key(obj, key):
        for _name_key in Host.__name_lut.keys():
            if key in Host.__name_lut[_name_key]:
                del Host.__name_lut[_name_key][key]
        del Host.__lut[key]

    @staticmethod
    def set_device(new_dev):
        new_mach = Host(new_dev)
        Host.__unique_keys.add(new_dev.pk)
        Host.device_state.add_device(new_dev)
        # check network settings
        new_mach.check_network_settings()

    @staticmethod
    def delete_device(dev_spec, remove_from_unique_keys=True):
        mach = Host.get_device(dev_spec)
        if mach:
            mach.close()
            Host.device_state.remove_device(mach.pk)
            if remove_from_unique_keys:
                Host.__unique_keys.remove(mach.pk)

    @staticmethod
    def get_device(dev_spec):
        if dev_spec in Host.__lut:
            return Host.__lut[dev_spec]
        else:
            if Host.sync(pks=[dev_spec]):
                return Host.__lut[dev_spec]
            else:
                Host.g_log(
                    "no device with spec '{}' found (not mother / bootserver ?)".format(
                        str(dev_spec),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                return None

    @staticmethod
    def iterate(com_name, *args, **kwargs):
        iter_keys = set(Host.__unique_keys)
        if "device_keys" in kwargs:
            iter_keys &= set(kwargs.pop("device_keys", Host.__unique_keys))
        if iter_keys:
            for u_key in iter_keys:
                cur_dev = Host.get_device(u_key)
                if hasattr(cur_dev, com_name):
                    cur_dev.log("call '{}'".format(com_name))
                    getattr(cur_dev, com_name)(*args, **kwargs)
                else:
                    cur_dev.log(
                        "call '{}' not defined".format(com_name),
                        logging_tools.LOG_LEVEL_WARN
                    )
            Host.dhcp_syncer.sync()
        else:
            Host.g_log("iterate for {} gave no result".format(com_name), logging_tools.LOG_LEVEL_ERROR)

    @staticmethod
    def ping(srv_com):
        if "user_id" in srv_com:
            log_user = user.objects.get(Q(pk=srv_com["user_id"].text))  # @UndefinedVariable
        else:
            log_user = None
        # send ping(s) to all valid IPs of then selected devices
        keys = set(map(lambda x: int(x), srv_com.xpath(".//ns:device/@pk"))) & set(Host.__unique_keys)
        master_dev_list = set(
            device.objects.filter(
                Q(parent_device__child__in=keys)
            ).select_related(
                "netdevice_set__net_ip_set"
            ).values_list(
                "pk",
                "netdevice__net_ip__ip",
                "netdevice__net_ip__network__network_type__identifier",
            )
        )
        # create dict for master / slave relations
        _master_dict = {
            key: value for key, value, nwt in master_dev_list if value and nwt not in ["l"]
        }
        # list of devices to ping (== require status)
        ping_keys, error_keys = ([], [])
        for dev_node in srv_com.xpath(".//ns:device[@pk]"):
            # print
            u_key = int(dev_node.attrib["pk"])
            cur_dev = Host.get_device(u_key)
            if cur_dev is None:
                DeviceLogEntry.new(
                    device=device.objects.get(Q(pk=u_key)),
                    source=Host.process.mother_src,
                    level=logging_tools.LOG_LEVEL_ERROR,
                    text="not a valid device",
                    user=log_user,
                )
                error_keys.append(u_key)
            else:
                ping_keys.append(u_key)
                command = dev_node.attrib.get("soft_command", "status")
                Host.device_state.get_device_state(u_key).modify_xml(dev_node)
                if command not in ["status"]:
                    Host.device_state.soft_control(dev_node, command)
                    if "soft_control_error" in dev_node.attrib:
                        cur_dev.log(
                            "error sending soft_control {}: {}".format(
                                command,
                                dev_node.attrib["soft_control_error"],
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        DeviceLogEntry.new(
                            device=cur_dev.device,
                            source=Host.process.mother_src,
                            level=logging_tools.LOG_LEVEL_WARN,
                            text="cannot send async soft control '{}': {}".format(
                                command,
                                dev_node.attrib["soft_control_error"],
                            ),
                            user=log_user,
                        )
                        dev_node.attrib["command_sent"] = "0"
                    else:
                        cur_dev.log("sent soft_control {}".format(command))
                        DeviceLogEntry.new(
                            device=cur_dev.device,
                            source=Host.process.mother_src,
                            text="async soft control '{}'".format(
                                command,
                            ),
                            user=log_user,
                        )
                        dev_node.attrib["command_sent"] = "1"
                # print dev_node.attrib
        Host.device_state.require_ping(ping_keys + _master_dict.keys())
        _bldr = srv_com.builder()
        cd_ping_list = _bldr.cd_ping_list()
        if _master_dict:
            for master_pk, master_ip in _master_dict.iteritems():
                cur_cd_ping = _bldr.cd_ping(pk="{:d}".format(master_pk))
                Host.device_state.get_device_state(master_pk).modify_xml(cur_cd_ping)
                cd_ping_list.append(cur_cd_ping)
            srv_com["cd_ping_list"] = cd_ping_list
        # result logging
        if error_keys:
            srv_com.set_result(
                "handled {} ({} unknown)".format(
                    logging_tools.get_plural("device", len(ping_keys)),
                    logging_tools.get_plural("device", len(error_keys)),
                ),
                server_command.SRV_REPLY_STATE_WARN
            )
        else:
            srv_com.set_result(
                "handled {}".format(
                    logging_tools.get_plural("device", len(ping_keys)),
                ),
            )
        # return False

    def set_maint_ip(self, ip=None):
        if ip:
            if self.maint_ip and (self.maint_ip.ip != ip.ip or self.maint_ip.netdevice.macaddr != ip.netdevice.macaddr):
                self.log(
                    "Changing maintenance IP and MAC from {} ({}) [{}] to {} ({}) [{}] and setting node-flag".format(
                        self.maint_ip.ip,
                        self.maint_ip.get_hex_ip(),
                        self.maint_ip.netdevice.macaddr,
                        ip.ip,
                        ip.get_hex_ip(),
                        ip.netdevice.macaddr
                    )
                )
            else:
                self.log(
                    "Setting maintenance IP and MAC to {} ({}) [{}] and setting node-flag".format(
                        ip.ip,
                        ip.get_hex_ip(),
                        ip.netdevice.macaddr
                    )
                )
            self.maint_ip = ip
        else:
            self.log("Clearing maintenance IP and MAC (and node-flag)")
            self.maint_ip = None
            self.dhcp_mac_written = None
            self.dhcp_ip_written = None

    @property
    def is_node(self):
        # check if device is a valid node
        if self.maint_ip and self.bootnetdevice is not None:
            return True
        else:
            return False

    def get_bnd(self):
        return self.__bnd

    def set_bnd(self, val):
        if val is None:
            self.log("clearing bootnetdevice")
            self.__bnd = val
        else:
            self.log(
                "changing bootnetdevice_name from '{}' to '{}'".format(
                    self.__bnd.devname if self.__bnd else "unset",
                    val
                )
            )
            self.__bnd = val
    bootnetdevice = property(get_bnd, set_bnd)

    def get_sip_d(self):
        return self.__srv_ip_dict

    def set_sip_d(self, val):
        self.__srv_ip_dict = val
        if val is not None:
            self.log("Found {}:".format(logging_tools.get_plural("valid device->server ip-mapping", len(val.keys()))))
            for my_ip, s_ip in val.iteritems():
                self.log(
                    "  {:<15s} -> {:<15s} [{}]".format(my_ip, s_ip["ip"], s_ip["identifier"])
                )
    server_ip_dict = property(get_sip_d, set_sip_d)

    def check_network_settings(self):
        if self.device is None:
            self.log("device is none in check_network_settings", logging_tools.LOG_LEVEL_WARN)
            return
        # bootnet device name
        self.bootnetdevice = None
        nd_list, nd_lut = (set(), {})
        # bootnetdevices via IP in boot net
        _possible_bnds = []
        # forced bnd via dhcp_device (force write DHCP)
        _forced_bnds = []
        for net_dev in self.device.netdevice_set.all():
            nd_list.add(net_dev.pk)
            nd_lut[net_dev.pk] = net_dev
            if any(
                [
                    _ip.network.network_type.identifier == "b" for _ip in net_dev.net_ip_set.all()
                ]
            ):
                _possible_bnds.append(net_dev)
            if net_dev.dhcp_device:
                _forced_bnds.append(net_dev)
            if self.device.bootnetdevice_id and net_dev.pk == self.device.bootnetdevice.pk:
                # set bootnetdevice_name
                self.bootnetdevice = net_dev
        if not len(_possible_bnds):
            if self.bootnetdevice is not None:
                self.log("removing bootnetdevice", logging_tools.LOG_LEVEL_WARN)
                self.bootnetdevice = None
                self.device.bootnetdevice = self.bootnetdevice
                self.device.save(update_fields=["bootnetdevice"])
        elif len(_possible_bnds) == 1:
            if _possible_bnds[0] == self.bootnetdevice:
                pass
            else:
                self.log("changing bootnetdevice to {}".format(_possible_bnds[0]))
                self.bootnetdevice = _possible_bnds[0]
                self.device.bootnetdevice = self.bootnetdevice
                self.device.save(update_fields=["bootnetdevice"])
        else:
            self.log("more than one possible bootnetdevice found ({:d})".format(len(_possible_bnds)), logging_tools.LOG_LEVEL_WARN)
        if self.bootnetdevice is None:
            if _forced_bnds:
                self.log(
                    "bootnetdevice is none in check_network_settings but forced_bnd list is set ({:d})".format(
                        len(_forced_bnds)
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                self._forced_bootnetdevice(_forced_bnds)
            else:
                self.log(
                    "bootnetdevice is none in check_network_settings and empty forced_bnd list",
                    logging_tools.LOG_LEVEL_WARN
                )
        else:
            self._valid_bootnetdevice(nd_list, nd_lut)

    def _forced_bootnetdevice(self, bnd_list):
        self.log("forced_bnd list has {}".format(logging_tools.get_plural("entry", len(bnd_list))))
        _ip_list = [
            b_ip for b_ip in sum(
                [list(bnd.net_ip_set.all()) for bnd in bnd_list], []
            ) if b_ip.network.identifier != "l"
        ]
        self.log("IP-list: {}".format(", ".join([_ip.ip for _ip in _ip_list])))
        self.server_ip_dict = {}
        if _ip_list:
            _boot_ip = _ip_list[0]
            self.bootnetdevice = _boot_ip.netdevice
            self.device.bootnetdevice = self.bootnetdevice
            self.maint_ip = _boot_ip
        else:
            self.maint_ip = None

    def _valid_bootnetdevice(self, nd_list, nd_lut):
        # dict: my net_ip -> dict [identifier, ip] server_net_ip
        server_ip_dict = {}
        # dict: ip -> identifier
        ip_dict = {}
        if nd_list:
            Host.process.update_router_object()
            all_paths = sorted(
                Host.process.router_obj.get_ndl_ndl_pathes(
                    Host.process.sc.netdevice_idx_list,
                    nd_list,
                    only_endpoints=True,
                    add_penalty=True,
                )
            )
            for _ in all_paths:
                srv_dev, mach_dev = (Host.process.sc.nd_lut[_[1]], nd_lut[_[2]])
                for cur_ip in mach_dev.net_ip_set.all():
                    cur_id = cur_ip.network.network_type.identifier
                    if cur_id == "l":
                        continue
                    srv_ips = list(
                        set(
                            [
                                srv_ip.ip for srv_ip in Host.process.sc.identifier_ip_lut.get(cur_id, []) if srv_ip.network_id == cur_ip.network_id
                            ]
                        ) & set(
                            [
                                x2.ip for x2 in Host.process.sc.netdevice_ip_lut[srv_dev.pk]
                            ]
                        )
                    )
                    if srv_ips and cur_ip.ip not in server_ip_dict:
                        if len(srv_ips) > 1:
                            self.log("more than on IP found: {}".format(", ".join(sorted(srv_ips))), logging_tools.LOG_LEVEL_WARN)
                        server_ip_dict[cur_ip.ip] = {
                            "identifier": cur_id,
                            "ip": srv_ips[0] if srv_ips else None
                        }
                    if cur_id == "b" and srv_ips:
                        self.set_maint_ip(cur_ip)
                    if cur_ip.ip not in ip_dict:
                        ip_dict[cur_ip.ip] = cur_ip
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("IP-address", len(ip_dict)),
                    ", ".join(sorted(ip_dict.keys()))
                )
            )
            link_array = []
            if self.etherboot_dir:
                link_array.extend(
                    [
                        ("d", self.etherboot_dir),
                        # ("d", self.pxelinux_dir),
                        ("l", (os.path.join(global_config["ETHERBOOT_DIR"], self.name), self.maint_ip.ip)),
                        # create a link in config dir, dangerous because cluster-config-server is running with restricted rights
                        ("l", (os.path.join(global_config["CONFIG_DIR"], self.maint_ip.ip), self.name)),
                    ]
                )
                self.device.etherboot_valid = True
            else:
                self.log("etherboot-directory (maint_ip) not defined", logging_tools.LOG_LEVEL_ERROR)
                self.device.etherboot_valid = False
            if self.maint_ip:
                self.show_boot_netdriver()
            self.process_link_array(link_array)
        else:
            self.log(
                "Cannot add device {} (empty ip_list -> cannot reach host)".format(self.name),
                logging_tools.LOG_LEVEL_WARN
            )
        master_dev_list = device.objects.filter(
            Q(parent_device__child__in=[self.device.pk])
        ).prefetch_related(
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network__network_type",
        )
        # ip_list fot controlling device
        for _cd in master_dev_list:
            if not Host.device_state.device_present(_cd.pk):
                Host.device_state.add_device(_cd, ping_only=True)
            cd_ip_dict = {}
            for _nd in _cd.netdevice_set.all():
                for _ip in _nd.net_ip_set.all():
                    cd_ip_dict[_ip.ip] = _ip
            Host.device_state.set_ip_dict(_cd.pk, cd_ip_dict)
        # cd_ip_list = [value for key, value, nwt in master_dev_list if nwt not in ["l"]]
        self.ip_dict = ip_dict
        Host.device_state.set_ip_dict(self.device.pk, ip_dict)
        self.server_ip_dict = server_ip_dict

    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    try:
                        self.log("pla(): Creating directory {}".format(ps))
                        os.mkdir(ps)
                    except:
                        self.log("  error creating {}: {}".format(ps, process_tools.get_except_info()))
            elif pt == "l":
                if isinstance(ps, basestring):
                    dest = self.name
                else:
                    ps, dest = ps
                create_link = False
                if not os.path.islink(ps):
                    create_link = True
                else:
                    if os.path.exists(ps):
                        old_dest = os.readlink(ps)
                        if old_dest != dest:
                            try:
                                os.unlink(ps)
                            except OSError:
                                self.log("  error unlinking {}: {}".format(ps, process_tools.get_except_info()))
                            else:
                                self.log(" removed wrong link ({} pointed to {} instead of {})".format(ps, old_dest, dest))
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink {}".format(ps))
                            os.unlink(ps)
                        except:
                            self.log("  error unlinking {}: {}".format(ps, process_tools.get_except_info()))
                        try:
                            self.log("pla(): rmtree {}".format(ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  error in rmtree {}: {}".format(ps, process_tools.get_except_info()))
                    try:
                        self.log("pla(): symlink from {} to {}".format(ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  error creating link from {} to {}: {}".format(ps, dest, process_tools.get_except_info()))

    def show_boot_netdriver(self):  # , driver="eepro100", ethtool_options=0, options=""):
        self.log("current boot_netdriver/ethtool_options/netdriver_options is '{}' / {:d} ({}) / '{}'".format(
            self.maint_ip.netdevice.driver,
            self.maint_ip.netdevice.ethtool_options,
            self.maint_ip.netdevice.ethtool_string(),
            self.maint_ip.netdevice.driver_options))

    @property
    def etherboot_dir(self):
        if self.maint_ip:
            return os.path.join(self.eb_dir, self.maint_ip.ip)
        else:
            return None

    @property
    def config_dir(self):
        if self.maint_ip:
            return os.path.join(global_config["CONFIG_DIR"], self.maint_ip.ip)
        else:
            return None

    @property
    def menu_file_name(self):
        return os.path.join(self.etherboot_dir, "menu")

    @property
    def ip_file_name(self):
        return os.path.join(self.eb_dir, "pxelinux.cfg", self.maint_ip.get_hex_ip())

    @property
    def ip_mac_file_base_name(self):
        return "01-{}".format(self.maint_ip.netdevice.macaddr.lower().replace(":", "-"))

    @property
    def ip_mac_file_name(self):
        return os.path.join(self.eb_dir, "pxelinux.cfg", self.ip_mac_file_base_name)

    def refresh_target_kernel(self, *args, **kwargs):
        if kwargs.get("refresh", True):
            self.refresh_device()
            self.check_network_settings()
        if self.is_node:
            # files to remove
            self._files_to_rm = set([self.ip_file_name, self.ip_mac_file_name, self.menu_file_name])
            if not self.device.stage1_flavour:
                self.device.stage1_flavour = "cpio"
                self.log("setting stage1_flavour to '{}'".format(self.device.stage1_flavour))
                self.device.save(update_fields=["stage1_flavour"])
            if not self.device.prod_link:
                self.log("no production link set", logging_tools.LOG_LEVEL_WARN)
                prod_net = None
            else:
                prod_net = self.device.prod_link
                self.log("production network is {}".format(unicode(prod_net)))
            if self.device.new_state:
                new_kernel = self.device.new_kernel
                new_state = self.device.new_state
                self.log(
                    "refresh for target_state {}, kernel {}, stage1_flavour {}".format(
                        unicode(self.device.new_state),
                        unicode(new_kernel),
                        self.device.stage1_flavour
                    )
                )
            else:
                self.log("no state set", logging_tools.LOG_LEVEL_WARN)
                self.clear_kernel_links()
                new_state, new_kernel = (None, None)
            if new_state:
                if new_kernel and new_state.prod_link:
                    # print self.server_ip_dict
                    if self.server_ip_dict:
                        self.write_kernel_config(new_kernel)
                    else:
                        self.log("no server_ip_dict set", logging_tools.LOG_LEVEL_ERROR)
                elif new_state.boot_local:
                    # boot local
                    self.write_localboot_config()
                elif new_state.memory_test:
                    # memory test
                    self.write_memtest_config()
                elif new_state.boot_iso:
                    self.write_isoboot_config()
                else:
                    self.log(
                        "cannot handle new_state '{}'".format(unicode(new_state)),
                        logging_tools.LOG_LEVEL_ERROR,
                    )
            self.remove_files()
        else:
            self.log("device is not node", logging_tools.LOG_LEVEL_WARN)

    def remove_files(self):
        for _f_name in self._files_to_rm:
            if os.path.exists(_f_name):
                try:
                    os.unlink(_f_name)
                except:
                    self.log(
                        "error removing file {}".format(
                            _f_name
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    self.log("removed file {}".format(_f_name))

    def clear_kernel_links(self):
        for link_name in ["i", "k"]:
            full_name = os.path.join(self.etherboot_dir, link_name)
            if os.path.islink(full_name):
                self.log("removing kernel link {}".format(full_name))
                os.unlink(full_name)

    def write_file(self, f_name, f_content, **kwargs):
        self._files_to_rm.remove(f_name)
        open(f_name, "w").write(f_content)

    def write_isoboot_config(self):
        if self.device.kernel_append:
            _iso = self.device.kernel_append
            self.log("using iso {} for booting".format(_iso))
            for name in [self.ip_file_name, self.ip_mac_file_name]:
                self.write_file(
                    name,
                    "\n".join(
                        [
                            "DEFAULT isoboot",
                            "LABEL isoboot",
                            "KERNEL memdisk",
                            "APPEND iso initrd=isos/{} raw".format(_iso),
                            "",
                        ]
                    )
                )
        else:
            self.log("no kernel_append (==iso filename) given", logging_tools.LOG_LEVEL_CRITICAL)

    def write_memtest_config(self):
        iso_files = [_entry for _entry in os.listdir(self.iso_dir) if _entry.startswith("memtest")]
        if iso_files:
            memtest_iso = iso_files[0]
            self.log("using iso {} for memtest".format(memtest_iso))
            for name in [self.ip_file_name, self.ip_mac_file_name]:
                self.write_file(
                    name,
                    "\n".join(
                        [
                            "DEFAULT memtest",
                            "LABEL memtest",
                            "KERNEL memdisk",
                            "APPEND iso initrd=isos/{} raw".format(memtest_iso),
                            "",
                        ]
                    )
                )
        else:
            self.log("no memtest iso found in {}".format(self.iso_dir), logging_tools.LOG_LEVEL_ERROR)

    def write_localboot_config(self):
        for name in [self.ip_file_name, self.ip_mac_file_name]:
            self.write_file(
                name,
                "\n".join(
                    [
                        "DEFAULT linux",
                        "LABEL linux",
                        "IMPLICIT 0",
                        "LOCALBOOT 0",
                        "",
                    ]
                )
            )

    def write_kernel_config(self, new_kernel):
        kern_dst_dir = self.etherboot_dir
        if kern_dst_dir:
            if os.path.isdir(kern_dst_dir):
                for file_name in ["i", "k", "x"]:
                    fname = os.path.join(kern_dst_dir, file_name)
                    if os.path.islink(fname):
                        os.unlink(fname)
                for stage_name in ["stage2", "stage3"]:
                    stage_source = "{}/lcs/{}".format(
                        global_config["CLUSTER_DIR"],
                        stage_name)
                    stage_dest = os.path.join(kern_dst_dir, stage_name)
                    if not os.path.isfile(stage_source):
                        self.log("Error, cannot find {}_source '{}'...".format(stage_name, stage_source))
                    elif not os.path.isfile(stage_dest) or (
                        os.path.isfile(stage_dest) and (
                            os.stat(stage_source)[stat.ST_MTIME] > os.stat(stage_dest)[stat.ST_MTIME]
                        ) or os.stat(stage_source)[stat.ST_SIZE] != os.stat(stage_dest)[stat.ST_SIZE]
                    ):
                        self.log("Copying {} from {} to {} ...".format(stage_name, stage_source, stage_dest))
                        open(stage_dest, "w").write(open(stage_source, "r").read())
                # print kernel_stuff
                kern_base_dir = "../../kernels/{}".format(new_kernel.display_name)
                kern_abs_base_dir = "{}/kernels/{}".format(global_config["TFTP_DIR"], new_kernel.display_name)
                unlink_field = [
                    "{}/k".format(kern_dst_dir),
                    "{}/i".format(kern_dst_dir),
                    "{}/x".format(kern_dst_dir)
                ]
                valid_links = []
                server_ip = self.server_ip_dict[self.maint_ip.ip]["ip"]
                if os.path.isdir(kern_abs_base_dir):
                    # check if requested flavour is ok
                    if not hasattr(new_kernel, "stage1_{}_present".format(self.device.stage1_flavour)):
                        self.log(
                            "requested stage1_flavour '{}' not known".format(
                                self.device.stage1_flavour
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    elif not getattr(new_kernel, "stage1_{}_present".format(self.device.stage1_flavour)):
                        self.log(
                            "requested stage1_flavour '{}' not present".format(
                                self.device.stage1_flavour
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        link_field = [
                            (
                                "{}/bzImage".format(kern_abs_base_dir),
                                "{}/bzImage".format(kern_base_dir),
                                "{}/k".format(kern_dst_dir)
                            ),
                            (
                                "{}/initrd_{}.gz".format(kern_abs_base_dir, self.device.stage1_flavour),
                                "{}/initrd_{}.gz".format(kern_base_dir, self.device.stage1_flavour),
                                "{}/i".format(kern_dst_dir)
                            )
                        ]
                        if new_kernel.xen_host_kernel:
                            link_field.append(
                                (
                                    "{}/xen.gz".format(kern_abs_base_dir),
                                    "{}/xen.gz".format(kern_base_dir),
                                    "{}/x".format(kern_dst_dir)
                                )
                            )
                        for abs_src, src, dst in link_field:
                            if new_kernel.name:
                                if os.path.isfile(abs_src):
                                    c_link = True
                                    if os.path.islink(dst):
                                        act_dst = os.readlink(dst)
                                        if src == act_dst:
                                            # self.log("Link %s is still valid (points to %s)" % (dst, act_dst))
                                            valid_links.append(dst)
                                            c_link = False
                                        else:
                                            os.unlink(dst)
                                    elif os.path.isfile(dst):
                                        os.unlink(dst)
                                    if c_link:
                                        self.log("Linking from {} to {}".format(dst, src))
                                        # print "symlink()", src, dst
                                        os.symlink(src, dst)
                                        valid_links.append(dst)
                                else:
                                    self.log(
                                        "source {} for symlink() does not exist".format(abs_src),
                                        logging_tools.LOG_LEVEL_ERROR
                                    )
                                    valid_links.append(dst)
                else:
                    self.log(
                        "source_kernel_dir {} does not exist".format(kern_abs_base_dir),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                if unlink_field:
                    unlink_field = [l_path for l_path in unlink_field if os.path.islink(l_path) and l_path not in valid_links]
                    if unlink_field:
                        self.log(
                            "Removing {}: {}".format(
                                logging_tools.get_plural("dead link", len(unlink_field)),
                                ", ".join(unlink_field)
                            )
                        )
                        for l_path in unlink_field:
                            try:
                                os.unlink(l_path)
                            except:
                                self.log(
                                    "error removing link {}: {}".format(
                                        l_path,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                if self.device.stage1_flavour == "cpio":
                    root_str = ""
                else:
                    root_str = "root=/dev/ram0"
                append_string = (
                    " ".join(
                        [
                            root_str,
                            "init=/linuxrc rw nbd={},{},{:d},{} uuid={} {}".format(
                                self.bootnetdevice.devname,
                                self.bootnetdevice.driver,
                                self.bootnetdevice.ethtool_options,
                                self.bootnetdevice.driver_options.replace(" ", ur"§"),
                                self.device.get_boot_uuid(),
                                self.device.kernel_append
                            )
                        ]
                    )
                ).strip().replace("  ", " ").replace("  ", " ")
                # self.clear_ip_mac_files([self.ip_mac_file_base_name])
                if new_kernel.xen_host_kernel:
                    append_field = [
                        "x dom0_mem=524288",
                        "k console=tty0 ip={}:{}::{} {}".format(
                            self.maint_ip.ip,
                            server_ip,
                            ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask),
                            append_string,
                        ),
                        "i"
                    ]
                else:
                    total_append_string = "initrd={}/i ip={}:{}::{} {}".format(
                        self.maint_ip.ip,
                        self.maint_ip.ip,
                        server_ip,
                        ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask),
                        append_string,
                    )
                pxe_lines = []
                if global_config["NODE_BOOT_DELAY"]:
                    pxe_lines.extend(
                        [
                            "TIMEOUT {:d}".format(global_config["NODE_BOOT_DELAY"]),
                            "PROMPT 1"
                        ]
                    )
                pxe_lines.extend(
                    [
                        "DISPLAY {}/menu".format(self.maint_ip.ip),
                        "DEFAULT linux auto"
                    ]
                )
                if new_kernel.name:
                    if new_kernel.xen_host_kernel:
                        pxe_lines.extend(
                            [
                                "LABEL linux",
                                "    KERNEL mboot.c32",
                                "    APPEND {}".format(" --- ".join(append_field))
                            ]
                        )
                    else:
                        pxe_lines.extend(
                            [
                                "LABEL linux",
                                "    KERNEL {}/k".format(self.maint_ip.ip),
                                "    APPEND {}".format(total_append_string)
                            ]
                        )
                pxe_lines.extend([""])
                if global_config["FANCY_PXE_INFO"]:
                    menu_lines = [
                        "\x0c\x0f20{}\x0f07".format(("init.at Bootinfo, {}{}".format(time.ctime(), 80 * " "))[0:79])
                    ]
                else:
                    menu_lines = [
                        "",
                        ("init.at Bootinfo, {}{}".format(time.ctime(), 80 * " "))[0:79]
                    ]
                menu_lines.extend(
                    [
                        "Nodename  , IP : {:<30s}, {}".format(self.device.name, self.maint_ip.ip),
                        "Servername, IP : {:<30s}, {}".format(global_config["SERVER_SHORT_NAME"], server_ip),
                        "Netmask        : {} ({})".format(self.maint_ip.network.netmask, ipvx_tools.get_network_name_from_mask(self.maint_ip.network.netmask)),
                        "MACAddress     : {}".format(self.bootnetdevice.macaddr.lower()),
                        "Stage1 flavour : {}".format(self.device.stage1_flavour),
                        "Kernel to boot : {}".format(
                            "{} (is a {})".format(
                                new_kernel.display_name,
                                new_kernel.name
                            ) or "<no kernel set>"
                        ),
                        "device UUID    : {}".format(self.device.get_boot_uuid()),
                        "Kernel options : {}".format(append_string or "<none set>"),
                        "target state   : {}".format(unicode(self.device.new_state) if self.device.new_state_id else "???"),
                        "will boot {}".format(
                            "in {}".format(
                                logging_tools.get_plural("second", int(global_config["NODE_BOOT_DELAY"] / 10))
                            ) if global_config["NODE_BOOT_DELAY"] else "immediately"
                        ),
                        "",
                        "",
                    ]
                )
                self.write_file(self.ip_file_name, "\n".join(pxe_lines))
                self.write_file(self.ip_mac_file_name, "\n".join(pxe_lines))
                self.write_file(self.menu_file_name, "\n".join(menu_lines))
                if new_kernel.xen_host_kernel:
                    open(self.mboot_file_name, "w").write(global_config["MBOOT.C32"])
            else:
                self.log("Error: directory {} does not exist".format(kern_dst_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("Error: etherboot-dir not defined", logging_tools.LOG_LEVEL_ERROR)

    def handle_mac_command(self, com_name, **kwargs):
        if kwargs.get("refresh", True):
            self.refresh_device()
            self.check_network_settings()
        if self.maint_ip:
            ip_to_write, ip_to_write_src = (self.maint_ip.ip, "maint_ip")
        elif self.bootnetdevice and self.bootnetdevice.dhcp_device:
            # FIXME, why do we take the first IP address ?
            if self.ip_dict:
                ip_to_write, ip_to_write_src = (self.ip_dict.keys()[0], "first ip of ip_dict.keys()")
            else:
                ip_to_write, ip_to_write_src = (None, "")
        else:
            ip_to_write, ip_to_write_src = (None, "")
        # flag to create IP from forced_bnds
        _force_write = False
        if ip_to_write:
            if self.server_ip_dict:
                mac_to_write = self.device.bootnetdevice.macaddr
                server_ip = self.server_ip_dict[self.maint_ip.ip]["ip"]
            else:
                server_ip = "0.0.0.0"
                mac_to_write = self.bootnetdevice.macaddr
                _force_write = True
        else:
            mac_to_write = None
            server_ip = None
        if com_name in ["alter", "write"]:
            if (_force_write or self.device.dhcp_write) and ip_to_write:
                om_shell_com = DHCPCommand(self.device.name, self.device.uuid, ip_to_write, mac_to_write, server_ip)
            else:
                om_shell_com = DHCPCommand(self.device.name, self.device.uuid)
        else:
            om_shell_com = DHCPCommand(self.device.name)
        self.log(
            "transformed dhcp_command {} to {} ({})".format(
                com_name,
                unicode(om_shell_com),
                ip_to_write and "ip {} from {}".format(ip_to_write, ip_to_write_src) or "no ip",
            )
        )
        Host.dhcp_syncer.feed_command(om_shell_com)

    def feed_dhcp(self, in_dict, in_line):
        self.refresh_device()
        if in_dict["key"] == "discover":
            if self.bootnetdevice is None:
                DeviceLogEntry.new(
                    device=self.device,
                    source=Host.process.node_src,
                    text="no valid bootnetdevice (mac: {})".format(in_dict["macaddr"]),
                    level=logging_tools.LOG_LEVEL_ERROR
                )
                self.log("no bootnetdevice set", logging_tools.LOG_LEVEL_ERROR)
                return
            # dhcp feed, in most cases discover
            self.log("set macaddress of bootnetdevice to '{}'".format(in_dict["macaddr"]))
            self.bootnetdevice.macaddr = in_dict["macaddr"]
            self.bootnetdevice.save(update_fields=["macaddr"])
            self.device.dhcp_mac = False
            self.device.save(update_fields=["dhcp_mac"])
            DeviceLogEntry.new(
                device=self.device,
                source=Host.process.node_src,
                text="set macaddr of {} to {}".format(self.bootnetdevice.devname, in_dict["macaddr"]),
            )
            macbootlog(
                device=self.device,
                macaddr=in_dict["macaddr"],
                entry_type=in_dict["key"],
                ip_action="SET"
            ).save()
            # no change to dhcp-server
            Host.iterate("handle_mac_command", "alter", device_keys=[self.device.pk])
        else:
            change_fields = set()
            if self.device.dhcp_mac:
                # clear dhcp_mac
                self.log("clearing dhcp_mac")
                self.device.dhcp_mac = False
                change_fields.add("dhcp_mac")
            DeviceLogEntry.new(
                device=self.device,
                source=Host.process.node_src,
                text="DHCP / {} ({})".format(in_dict["key"], in_dict["ip"],),
            )
            # self.set_recv_state("got IP-Address via DHCP")
            if change_fields:
                self.device.save(update_fields=list(change_fields))
            if self.device.new_state:
                self.refresh_target_kernel(refresh=False)

    def nodeinfo(self, in_text, instance):
        self.log("got info '{}' from {}".format(in_text, instance))
        DeviceLogEntry.new(
            device=self.device,
            source=Host.process.node_src,
            text=in_text,
        )
        return "ok got it"


class hm_icmp_protocol(icmp_class.icmp_protocol):
    def __init__(self, process, log_template, verbose):
        self.__log_template = log_template
        self.__verbose = verbose
        icmp_class.icmp_protocol.__init__(self)
        self.__work_dict, self.__seqno_dict = ({}, {})
        self.__process = process
        self.init_socket()
        self.__process.register_socket(self.socket, select.POLLIN, self.received)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, "[icmp] {}".format(what))

    def __setitem__(self, key, value):
        self.__work_dict[key] = value

    def __getitem__(self, key):
        return self.__work_dict[key]

    def __delitem__(self, key):
        for seq_key in self.__work_dict[key]["sent_list"].keys():
            if seq_key in self.__seqno_dict:
                del self.__seqno_dict[seq_key]
        del self.__work_dict[key]

    def ping(self, seq_str, target, num_pings, timeout, **kwargs):
        if self.__verbose:
            self.log("ping to {} ({:d}, {:.2f}) [{}]".format(target, num_pings, timeout, seq_str))
        cur_time = time.time()
        self[seq_str] = {
            "host": target,
            "num": num_pings,
            "timeout": timeout,
            "start": cur_time,
            "id": kwargs.get("id", seq_str),
            "return_queue": kwargs.get("ret_queue", None),
            # time between pings
            "slide_time": 0.1,
            "sent": 0,
            "recv_ok": 0,
            "recv_fail": 0,
            "error_list": [],
            "sent_list": {},
            "recv_list": {},
        }
        self._update()

    def _update(self):
        cur_time = time.time()
        del_keys = []
        # pprint.pprint(self.__work_dict)
        for key, value in self.__work_dict.iteritems():
            if value["sent"] < value["num"]:
                if value["sent_list"]:
                    # send if last send was at least slide_time ago
                    to_send = max(value["sent_list"].values()) + value["slide_time"] < cur_time or value["recv_ok"] == value["sent"]
                else:
                    # always send
                    to_send = True
                if to_send:
                    value["sent"] += 1
                    try:
                        self.send_echo(value["host"])
                    except:
                        value["error_list"].append(process_tools.get_except_info())
                        self.log(
                            "error sending to {}: {}".format(
                                value["host"],
                                ", ".join(value["error_list"])
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        value["sent_list"][self.echo_seqno] = cur_time
                        self.__seqno_dict[self.echo_seqno] = key
                        self.__process.register_timer(self._update, value["slide_time"] + 0.001, oneshot=True)
                        self.__process.register_timer(self._update, value["timeout"], oneshot=True)
            # check for timeout
            for seq_to in [
                s_key for s_key, s_value in value["sent_list"].iteritems() if abs(s_value - cur_time) > value["timeout"] and s_key not in value["recv_list"]
            ]:
                value["recv_fail"] += 1
                value["recv_list"][seq_to] = None
            # check for ping finish
            if value["error_list"] or (value["sent"] == value["num"] and value["recv_ok"] + value["recv_fail"] == value["num"]):
                self.__process.send_ping_result(key, value)  # ["sent"], value["recv_ok"], all_times, ", ".join(value["error_list"]))
                del_keys.append(key)
        for del_key in del_keys:
            del self[del_key]
        # pprint.pprint(self.__work_dict)

    def received(self, sock):
        dgram = self.parse_datagram(sock.recv(1024))
        if dgram and dgram.packet_type == 0 and dgram.ident == self.__process.pid & 0x7fff:
            seqno = dgram.seqno
            if seqno not in self.__seqno_dict:
                self.log(
                    "got result with unknown seqno {:d}".format(seqno),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                value = self[self.__seqno_dict[seqno]]
                if seqno not in value["recv_list"]:
                    value["recv_list"][seqno] = time.time()
                    value["recv_ok"] += 1
            self._update()


class ICMPProcess(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        self.__verbose = global_config["VERBOSE"]
        self.icmp_protocol = hm_icmp_protocol(self, self.__log_template, self.__verbose)
        # add private socket
        self.add_com_socket()
        self.bind_com_socket("control")
        self.register_func("ping", self._ping)

    def _ping(self, *args, **kwargs):
        self.icmp_protocol.ping(*args, **kwargs)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def send_ping_result(self, *args):
        # intermediate solution
        if args[1]["return_queue"]:
            self.send_pool_message("ds_ping_result", *args, target="control", target_process=args[1]["return_queue"])
        else:
            self.send_pool_message("ping_result", *args, target="control")

    def loop_post(self):
        self.__log_template.close()


class NodeControlProcess(threading_tools.process_obj):
    def process_init(self):
        # check log type (queue or direct)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        db_tools.close_connection()
        self.node_src = log_source_lookup("node", None)
        self.mother_src = LogSource.objects.get(Q(pk=global_config["LOG_SOURCE_IDX"]))
        # close database connection
        simple_command.setup(self)
        self.sc = config_tools.server_check(server_type="mother_server")
        if "b" in self.sc.identifier_ip_lut:
            _boot_ips = self.sc.identifier_ip_lut["b"]
            self.log(
                "{} in {}: {}".format(
                    logging_tools.get_plural("IP-address", len(_boot_ips)),
                    logging_tools.get_plural("boot-network", len(_boot_ips)),
                    ", ".join([_boot_ip.ip for _boot_ip in _boot_ips]),
                )
            )
        else:
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.router_obj = config_tools.router_object(self.log)
        self._setup_etherboot()
        self.dhcp_syncer = DHCPSyncer(self.log)
        self.device_state = DeviceState(self, self.log)
        Host.setup(self, self.dhcp_syncer, self.device_state)
        Host.sync()
        self.register_func("refresh", self._refresh)
        # self.register_func("alter_macaddr", self.alter_macaddr)
        self.register_func("nodestatus", self._status)
        self.register_func("soft_control", self._status)
        self.register_func("ds_ping_result", self.device_state.ping_result)
        self.register_timer(self._check_commands, 10)
        # self.kernel_dev = config_tools.server_check(server_type="kernel_server")
        self.register_func("syslog_line", self._syslog_line)
        self.register_func("node_status", self._node_status)
        # build dhcp res
        self.__dhcp_res = {
            "discover": re.compile("(?P<program>\S+): DHCPDISCOVER from (?P<macaddr>\S+) via .*$"),
            "offer": re.compile("^(?P<program>\S+): DHCPOFFER on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
            "request": re.compile("^(?P<program>\S+): DHCPREQUEST for (?P<ip>\S+) .*from (?P<macaddr>\S+) via .*$"),
            "answer": re.compile("^(?P<program>\S+): DHCPACK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
            "inform": re.compile("^(?P<program>\S+): DHCPINFORM from (?P<ip>\S+) via .*$"),
            "nak": re.compile("^(?P<program>\S+): DHCPNAK on (?P<ip>\S+) to (?P<macaddr>\S+) via .*$"),
        }

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _setup_etherboot(self):
        map_list = [
            ("pxelinux.0", "PXELINUX.0"),
            ("memdisk", "MEMDISK"),
            ("ldlinux.c32", "LDLINUX.C32"),
            ("ldlinux.e64", "LDLINUX.E64"),
            ("mboot.c32", "MBOOT.C32"),
            ("bootx64.efi", "BOOTX64.EFI"),
            ("bootia32.efi", "BOOTIA32.EFI"),
        ]
        file_names = set([f_name for f_name, _key in map_list])
        for _dir, _dir_list, _entry_list in os.walk(global_config["ETHERBOOT_DIR"], False):
            _del_dir = False
            if os.path.basename(_dir) == "pxelinux.cfg":
                del_files = _entry_list
                _del_dir = True
            else:
                del_files = set(_entry_list) & file_names
            if del_files:
                try:
                    [os.unlink(os.path.join(_dir, _file_name)) for _file_name in del_files]
                except:
                    pass
            if _del_dir:
                os.rmdir(_dir)
        for rel_name, key_name in map_list:
            t_file = os.path.join(global_config["ETHERBOOT_DIR"], rel_name)
            if key_name in global_config:
                try:
                    file(t_file, "wb").write(global_config[key_name])
                except:
                    self.log("cannot create {}: {}".format(t_file, process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    os.chmod(t_file, 0444)
                    self.log("created {} (mode 0444)".format(t_file))
            else:
                self.log("key {} not found in global_config".format(key_name), logging_tools.LOG_LEVEL_CRITICAL)
        # cleanup pxelinux.cfg
        _cfg_dir = os.path.join(global_config["ETHERBOOT_DIR"], "pxelinux.cfg")
        if os.path.isdir(_cfg_dir):
            for _entry in os.listdir(_cfg_dir):
                try:
                    os.unlink(os.path.join(_cfg_dir, _entry))
                except:
                    pass
        else:
            os.mkdir(_cfg_dir)
        # setup isos
        _iso_dir = os.path.join(global_config["ETHERBOOT_DIR"], "isos")
        global_config.add_config_entries(
            [
                ("ISO_DIR", configfile.str_c_var(_iso_dir)),
            ]
        )
        if not os.path.isdir(_iso_dir):
            os.mkdir(_iso_dir)
        for entry in os.listdir(global_config["SHARE_DIR"]):
            _path = os.path.join(global_config["SHARE_DIR"], entry)
            if entry.startswith("memtest"):
                t_path = os.path.join(_iso_dir, entry)
                self.log("copy from {} to {}".format(_path, t_path))
                file(t_path, "wb").write(file(_path, "rb").read())

    def update_router_object(self):
        cur_time = time.time()
        if abs(cur_time - self.router_obj.latest_update) > 5:
            self.router_obj.check_for_update()

    def _refresh(self, *args, **kwargs):
        if len(args):
            in_com = server_command.srv_command(source=args[0])
            dev_list = map(lambda x: int(x), in_com.xpath(".//ns:device/@pk", smart_strings=False))
            self.log(
                "got refresh for {}: {}".format(
                    logging_tools.get_plural("device", len(dev_list)),
                    ", ".join(["{:d}".format(_pk) for _pk in sorted(dev_list)]),
                )
            )
            Host.iterate("refresh_target_kernel", device_keys=dev_list, refresh=True)
            Host.iterate("handle_mac_command", "alter", device_keys=dev_list, refresh=True)
            in_com.set_result("ok refreshed", server_command.SRV_REPLY_STATE_OK)
            self.send_pool_message("remote_call_async_result", unicode(in_com))
        else:
            # full refresh
            # use kwargs to specify certain devices
            Host.iterate("refresh_target_kernel", refresh=kwargs.get("refresh", True))
            Host.iterate("handle_mac_command", "alter", refresh=kwargs.get("refresh", True))

    def _status(self, in_com, *args, **kwargs):
        in_com = server_command.srv_command(source=in_com)
        Host.ping(in_com)
        self.send_pool_message("remote_call_async_result", unicode(in_com))

    def _node_status(self, srv_com, **kwargs):  # id_str, node_text, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        # exytract node_status text
        for node_ct in ["nodeinfo", "nodestatus"]:
            if node_ct in srv_com:
                node_text = srv_com["*{}".format(node_ct)]
                break
        if node_ct == "nodestatus":
            self.device_state.feed_nodestatus(kwargs.get("src_id"), node_text)
            self.send_pool_message("remote_call_async_done", unicode(srv_com))
        else:
            self.device_state.feed_nodeinfo(kwargs.get("src_id"), node_text)
            node_id, instance = kwargs.get("src_id").split(":", 1)
            cur_dev = Host.get_device(node_id)
            if cur_dev:
                srv_com.set_result(cur_dev.nodeinfo(node_text, instance))
            else:
                srv_com.set_result(
                    "error no node with id '{}' found".format(node_id),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def loop_post(self):
        Host.shutdown()
        self.__log_template.close()

    def set_check_freq(self, cur_to):
        self.log("changing check_freq of check_commands to {:d} msecs".format(cur_to))
        self.change_timer(self._check_commands, cur_to)

    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.set_loop_timer(1000)

    def _syslog_line(self, *args, **kwargs):
        in_line = args[0]
        if "DHCP" not in in_line:
            self.log("got non-DHCP line {}, skip".format(in_line), logging_tools.LOG_LEVEL_WARN)
        else:
            for key, cur_re in self.__dhcp_res.iteritems():
                cur_m = cur_re.match(in_line)
                if cur_m:
                    break
            if not cur_m:
                self.log("cannot parse {}".format(in_line), logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_dict = cur_m.groupdict()
                cur_dict["key"] = key
                self._handle_syslog(cur_dict, in_line)

    def _handle_syslog(self, in_dict, in_line):
        if "ip" in in_dict:
            try:
                ip_dev = device.objects.select_related("bootnetdevice").get(Q(netdevice__net_ip__ip=in_dict["ip"]))
            except device.DoesNotExist:
                self.log(
                    "got {} for unknown ip {}".format(
                        in_dict["key"],
                        in_dict["ip"]
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                ip_dev = None
            except device.MultipleObjectsReturned:
                self.log(
                    "got {} for multiple ip {}".format(
                        in_dict["key"],
                        in_dict["ip"]
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                ip_dev = None
            else:
                if ip_dev.bootserver:
                    if ip_dev.bootserver.pk == self.sc.effective_device.pk:
                        boot_dev = Host.get_device(ip_dev.pk)
                        if boot_dev is None:
                            self.log(
                                "got no local device for '{}', not bootserver or disabled?".format(
                                    unicode(ip_dev),
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        else:
                            boot_dev.log(
                                "parsed: {}, send to boot_dev".format(
                                    ", ".join(
                                        [
                                            "{}={}".format(
                                                key,
                                                in_dict[key]
                                            ) for key in sorted(in_dict.keys())
                                        ]
                                    )
                                )
                            )
                            boot_dev.feed_dhcp(in_dict, in_line)
                    else:
                        self.log(
                            "got request {} for {}, not responsible".format(
                                in_dict["key"],
                                ip_dev.name
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                else:
                    self.log("no bootserver set for device {}, strange...".format(ip_dev.name), logging_tools.LOG_LEVEL_ERROR)
        if in_dict["key"] == "discover":
            self.log(
                "parsed: {}".format(
                    ", ".join(
                        [
                            "{}={}".format(key, in_dict[key]) for key in sorted(in_dict.keys())
                        ]
                    )
                )
            )
            if in_line.lower().count("no free leases"):
                # nothing found
                try:
                    _used_dev = device.objects.get(
                        Q(bootserver=self.sc.effective_device) & Q(netdevice__macaddr__iexact=in_dict["macaddr"].lower())
                    )
                except device.DoesNotExist:
                    greedy_devs = device.objects.filter(
                        Q(bootserver=self.sc.effective_device) & Q(dhcp_mac=True)
                    ).select_related("bootnetdevice").order_by("name")
                    if len(greedy_devs):
                        if mac_ignore.objects.filter(Q(macaddr__iexact=in_dict["macaddr"].lower())).count():
                            self.log("ignoring mac-address '{}' (in ignore_list)".format(in_dict["macaddr"]))
                            macbootlog(
                                entry_type=in_dict["key"],
                                ip_action="IGNORE",
                                macaddr=in_dict["macaddr"].lower()
                            ).save()
                        else:
                            # no feed to device
                            cur_mach = Host.get_device(greedy_devs[0].pk)
                            if cur_mach:
                                cur_mach.feed_dhcp(in_dict, in_line)
                            else:
                                # FIXME
                                self.log("no device found with name '{}', resync ?".format(greedy_devs[0].name), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        all_greedy_devs = device.objects.filter(Q(dhcp_mac=True)).select_related("bootnetdevice").order_by("name")
                        if all_greedy_devs:
                            self.log(
                                "found {} but none related to me".format(
                                    logging_tools.get_plural("greedy device", len(all_greedy_devs))
                                ),
                                logging_tools.LOG_LEVEL_WARN
                            )
                            macbootlog(
                                entry_type=in_dict["key"],
                                ip_action="NOLOCGREEDY",
                                macaddr=in_dict["macaddr"].lower()
                            ).save()
                        else:
                            self.log("no greedy devices found for MAC-address {} or not responsible".format(in_dict["macaddr"]))
                            macbootlog(
                                entry_type=in_dict["key"],
                                ip_action="NOGLOBGREEDY",
                                macaddr=in_dict["macaddr"].lower()
                            ).save()
                else:
                    # reject entry because we are unable to answer the DHCP-Request
                    macbootlog.objects.create(
                        entry_type=in_dict["key"],
                        ip_action="REJECT",
                        macaddr=in_dict["macaddr"].lower()
                    )
            else:
                # discover request got an answer
                macbootlog.objects.create(
                    entry_type=in_dict["key"],
                    ip_action="---",
                    macaddr=in_dict["macaddr"].lower()
                )
        else:
            # non-discover call, should have an ip-entry
            macbootlog.objects.create(
                entry_type=in_dict["key"],
                device=ip_dev,
                ip_action=in_dict["ip"],
                # macaddr is not set for certain dhcp actions
                macaddr=in_dict.get("macaddr", "N/A").lower(),
            )
