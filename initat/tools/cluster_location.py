# Copyright (C) 2012-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone
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

import array
import datetime
import netifaces

from django.db.models import Q

from initat.cluster.backbone.models import device_variable, device, config_blob, \
    config_bool, config_int, config_str, net_ip
from initat.tools import configfile, process_tools

_VAR_LUT = {
    "int": config_int,
    "str": config_str,
    "blob": config_blob,
    "bool": config_bool,
}


def read_config_from_db(g_config, sql_info, init_list=[]):
    g_config.add_config_entries(init_list, database=True)
    if sql_info.effective_device:
        # dict of local vars without specified host
        l_var_wo_host = {}
        for short in [
            "str",
            "int",
            "blob",
            "bool",
        ]:
            # very similiar code appears in config_tools.py
            src_sql_obj = _VAR_LUT[short].objects
            if init_list:
                src_sql_obj = src_sql_obj.filter(
                    Q(name__in=[var_name for var_name, _var_value in init_list])
                )
            for db_rec in src_sql_obj.filter(
                Q(config=sql_info.config) &
                Q(config__device_config__device=sql_info.effective_device)
            ).order_by("name"):
                if db_rec.name.count(":"):
                    var_global = False
                    local_host_name, var_name = db_rec.name.split(":", 1)
                else:
                    var_global = True
                    local_host_name, var_name = (sql_info.short_host_name, db_rec.name)
                source = "{}_table::{}".format(short, db_rec.pk)
                if isinstance(db_rec.value, array.array):
                    new_val = configfile.str_c_var(db_rec.value.tostring(), source=source)
                elif short == "int":
                    new_val = configfile.int_c_var(int(db_rec.value), source=source)
                elif short == "bool":
                    new_val = configfile.bool_c_var(bool(db_rec.value), source=source)
                else:
                    new_val = configfile.str_c_var(db_rec.value, source=source)
                new_val.is_global = var_global
                present_in_config = var_name in g_config
                if present_in_config:
                    # copy settings from config
                    new_val.database = g_config.database(var_name)
                    new_val.is_global = var_global
                    new_val._help_string = g_config.help_string(var_name)
                if local_host_name == sql_info.short_host_name:
                    if var_name.upper() in g_config and g_config.fixed(var_name.upper()):
                        # present value is fixed, keep value, only copy global / local status
                        g_config.set_global(var_name.upper(), new_val.is_global)
                    else:
                        g_config.add_config_entries([(var_name.upper(), new_val)])
                elif local_host_name == "":
                    l_var_wo_host[var_name.upper()] = new_val
        # check for vars to insert
        for wo_var_name, wo_var in l_var_wo_host.items():
            if wo_var_name not in g_config or g_config.get_source(wo_var_name) == "default":
                g_config.add_config_entries([(wo_var_name, wo_var)])


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
            act_dv = device_variable.objects.get(Q(name=var_name) & Q(device=self.__device))
        except device_variable.DoesNotExist:
            self.__act_dv = None
            self.__var_value = None
        else:
            self.__act_dv = act_dv
            self.set_stuff(
                var_type=act_dv.var_type,
                description=act_dv.description,
            )
            self.set_value(getattr(act_dv, "val_%s" % (self.__var_type_name)), type_ok=True)
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
            setattr(self.__act_dv, "val_{}".format(self.__var_type_name), self.__var_value)
        else:
            self.__act_dv = device_variable(
                description=self.__description,
                var_type=self.__var_type,
                name=self.__var_name,
                device=self.__device
            )
            setattr(self.__act_dv, "val_{}".format(self.__var_type_name), self.__var_value)
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


def write_config_to_db(g_config, sql_info):
    def strip_description(descr):
        if descr:
            descr = " ".join(
                [
                    entry for entry in descr.strip().split() if not entry.count("(default)")
                    ]
            )
        return descr

    log_lines = []
    type_dict = {
        "i": config_int,
        "s": config_str,
        "b": config_bool,
        "B": config_blob,
    }
    if sql_info.effective_device and sql_info.config:
        for key in sorted(g_config.keys()):
            # print k,config.get_source(k)
            # print "write", k, config.get_source(k)
            # if config.get_source(k) == "default":
            # only deal with int and str-variables
            var_obj = type_dict.get(g_config.get_type(key), None)
            # print key, var_obj, g_config.database(key)
            if var_obj is not None and g_config.database(key):
                other_types = set([value for _key, value in list(type_dict.items()) if _key != g_config.get_type(key)])
                # var global / local
                var_range_name = g_config.is_global(key) and "global" or "local"
                # build real var name
                real_k_name = g_config.is_global(key) and key or "{}:{}".format(sql_info.short_host_name, key)
                try:
                    cur_var = var_obj.objects.get(
                        Q(name=real_k_name) &
                        Q(config=sql_info.config) &
                        (Q(device=0) | Q(device=None) | Q(device=sql_info.effective_device.pk))
                        # removed config via meta_device, AL 20121125
                        # Q(config__device_config__device__device_group__device_group=srv_info.effective_device.pk)
                    )
                except var_obj.DoesNotExist:
                    # check other types
                    other_var = None
                    for other_var_obj in other_types:
                        try:
                            other_var = other_var_obj.objects.get(
                                Q(name=real_k_name) & Q(config=sql_info.config) & (
                                    Q(device=0) | Q(device=None) | Q(device=sql_info.effective_device.pk)
                                )
                            )
                        except other_var_obj.DoesNotExist:
                            pass
                        else:
                            break
                    if other_var is not None:
                        # other var found, delete
                        other_var.delete()
                        # print(other_var, other_type)
                    # description
                    if g_config.help_string(key):
                        description = strip_description(g_config.help_string(key))
                    else:
                        description = "{} default value from {} on {}".format(
                            var_range_name,
                            sql_info.config_name,
                            sql_info.short_host_name,
                        )
                    _new_var = var_obj(
                        name=real_k_name,
                        description=description,
                        config=sql_info.config,
                        device=None,
                        value=g_config[key],
                    )
                    _new_var.save()
                else:
                    # print key, cur_var.value, g_config.help_string(key), g_config.get_type(key)
                    if g_config[key] != cur_var.value:
                        cur_var.value = g_config[key]
                        cur_var.save()
                    _cur_descr = cur_var.description or ""
                    new_descr = strip_description(g_config.help_string(key))
                    if new_descr and _cur_descr and _cur_descr.count("default value from") and _cur_descr.strip().split()[0] in ["global", "local"]:
                        cur_var.description = new_descr
                        cur_var.save()
            else:
                # print "X", key
                pass
    return log_lines


class DeviceRecognition(object):
    def __init__(self, **kwargs):
        self.short_host_name = kwargs.get("short_host_name", process_tools.get_machine_name())
        try:
            self.device = device.objects.get(Q(name=self.short_host_name))
        except device.DoesNotExist:
            self.device = None
        # get IP-adresses (from IP)
        self.local_ips = list(net_ip.objects.filter(Q(netdevice__device__name=self.short_host_name)).values_list("ip", flat=True))
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
        self_ips = [_ip for _ip in sum(list(ipv4_dict.values()), []) if not _ip.startswith("127.")]
        self.ip_lut = {}
        self.ip_r_lut = {}
        if self_ips:
            _do = device.objects  # @UndefinedVariable
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
                _dev_ips = sum([list(_ndev.net_ip_set.all()) for _ndev in _dev.netdevice_set.all()], [])
                # filter for valid ips (no loopback addresses)
                _dev_ips = [_ip.ip for _ip in _dev_ips if _ip.network.network_type.identifier != "l" and not _ip.ip.startswith("127.")]
                for _dev_ip in _dev_ips:
                    self.ip_lut[_dev_ip] = _dev
                self.ip_r_lut[_dev] = _dev_ips
        else:
            self.device_dict = {}
