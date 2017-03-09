# Copyright (C) 2012-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" module for checking current server status and extracting routes to other server """

import datetime
import netifaces

from django.db.models import Q

from initat.cluster.backbone.models import device_variable, device, net_ip
from initat.tools import process_tools


class db_device_variable(object):
    def __init__(self, cur_dev, var_name, **kwargs):
        if isinstance(cur_dev, int):
            try:
                self.__device = device.objects.get(Q(pk=cur_dev))
            except device.DoesNotExist:
                self.__device = None
        else:
            self.__device = cur_dev
        self.__var_name = var_name
        self.__var_type, self.__description = (None, kwargs.get("description", "not set"))
        try:
            act_dv = device_variable.objects.get(
                Q(name=var_name) & Q(device=self.__device)
            )
        except device_variable.DoesNotExist:
            self.__act_dv = None
            self.__var_value = None
        else:
            self.__act_dv = act_dv
            self.set_stuff(
                var_type=act_dv.var_type,
                description=act_dv.description,
            )
            self.set_value(
                getattr(
                    act_dv,
                    "val_{}".format(self.__var_type_name)
                ),
                type_ok=True
            )
        self.set_stuff(**kwargs)
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if (not self.__act_dv and "value" in kwargs) or kwargs.get("force_update", False):
            # update if device_variable not found and kwargs[value] is set
            self.update()

    def update(self):
        if self.__act_dv:
            self.__act_dv.description = self.__description
            self.__act_dv.var_type = self.__var_type
            setattr(
                self.__act_dv,
                "val_{}".format(self.__var_type_name),
                self.__var_value
            )
        else:
            self.__act_dv = device_variable(
                description=self.__description,
                var_type=self.__var_type,
                name=self.__var_name,
                device=self.__device
            )
            setattr(
                self.__act_dv,
                "val_{}".format(self.__var_type_name),
                self.__var_value
            )
        self.__act_dv.save()

    def is_set(self):
        return True if self.__act_dv else False

    def set_stuff(self, **kwargs):
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if "var_type" in kwargs:
            self.__var_type = kwargs["var_type"]
            self.__var_type_name = {
                "s": "str",
                "i": "int",
                "b": "blob",
                "t": "time",
                "d": "date"
            }[self.__var_type]
        if "description" in kwargs:
            self.__description = kwargs["description"]

    def set_value(self, value, type_ok=False):
        if not type_ok:
            if isinstance(value, str):
                v_type = "s"
            elif isinstance(value, int):
                v_type = "i"
            elif isinstance(value, datetime.datetime):
                v_type = "d"
            elif isinstance(value, datetime.time):
                v_type = "t"
            else:
                v_type = "b"
            self.set_stuff(var_type=v_type)
        self.__var_value = value

    def get_value(self):
        return self.__var_value


class DeviceRecognition(object):
    def __init__(self, **kwargs):
        self.short_host_name = kwargs.get("short_host_name", process_tools.get_machine_name())
        try:
            self.device = device.all_enabled.get(Q(name=self.short_host_name))
        except device.DoesNotExist:
            self.device = None
        # get IP-adresses (from IP)
        self.local_ips = list(
            net_ip.objects.filter(
                Q(netdevice__device__name=self.short_host_name) &
                Q(netdevice__device__enabled=True) &
                Q(netdevice__device__device_group__enabled=True)
            ).values_list("ip", flat=True)
        )
        # get configured IP-Adresses
        ipv4_dict = {
            cur_if_name: [
                ip_tuple["addr"] for ip_tuple in value[2]
            ] for cur_if_name, value in [
                (
                    if_name, netifaces.ifaddresses(if_name)
                ) for if_name in netifaces.interfaces()
            ] if 2 in value
        }
        # remove loopback addresses
        self_ips = [
            _ip for _ip in sum(list(ipv4_dict.values()), []) if not _ip.startswith("127.")
        ]
        self.ip_lut = {}
        self.ip_r_lut = {}
        if self_ips:
            _do = device.all_enabled
            # get IPs
            self.device_dict = {
                cur_dev.pk: cur_dev for cur_dev in _do.filter(
                    Q(netdevice__net_ip__ip__in=self_ips)
                ).prefetch_related(
                    "netdevice_set__net_ip_set__network__network_type"
                )
            }
            for _ip in self.local_ips:
                self.ip_lut[_ip] = self.device
            self.ip_r_lut[self.device] = self.local_ips
            # build lut
            for _dev in self.device_dict.values():
                # gather all ips
                _dev_ips = sum(
                    [
                        list(
                            _ndev.net_ip_set.all()
                        ) for _ndev in _dev.netdevice_set.all()
                    ],
                    []
                )
                # filter for valid ips (no loopback addresses)
                _dev_ips = [
                    _ip.ip for _ip in _dev_ips if _ip.network.network_type.identifier != "l" and not _ip.ip.startswith("127.")
                ]
                for _dev_ip in _dev_ips:
                    self.ip_lut[_dev_ip] = _dev
                self.ip_r_lut[_dev] = _dev_ips
        else:
            self.device_dict = {}
