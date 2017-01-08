# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from __future__ import unicode_literals, print_function

from django.db.models import Q

from initat.cluster.backbone.models import device_variable, device

__all__ = [
    b"MonVarCache",
]


# used by md-config-server and collectd
class VarCache(dict):
    def __init__(self, prefill=False, def_dict=None):
        super(VarCache, self).__init__(self)
        self.__cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        self.__prefill = prefill
        self.__def_dict = def_dict or {}
        # for future configure options
        self.__new_var_type = "private"
        if self.__prefill:
            self._prefill()

    # key functions
    def _global_key(self):
        return "GLOBAL"

    def _device_group_key(self, dev):
        return "g__{:d}".format(dev.device_group_id)

    def _device_key(self, dev):
        return "d__{:d}".format(dev.pk)

    def _prefill(self):
        for _var in device_variable.objects.all().select_related("device"):
            if _var.device.is_meta_device:
                if _var.device.device_group_id == self.__cdg.pk:
                    _key = self._global_key()
                    if _key not in self:
                        self[_key] = {g_key: (g_value, True) for g_key, g_value in self.__def_dict.iteritems()}
                else:
                    _key = self._device_group_key(_var.device)
            else:
                _key = self._device_key(_var.device)
            self.setdefault(_key, {})[_var.name] = (_var.value, _var.inherit)

    def add_variable(self, new_var):
        self.setdefault(self._device_key(new_var.device), {})[new_var.name] = (new_var.value, new_var.inherit)

    def set_variable(self, dev, var_name, var_value):
        # update db
        _d_key = self._device_key(dev)
        if _d_key not in self or var_name not in self.get(_d_key, {}):
            if not self.__prefill:
                self.get_vars(dev)
        if _d_key not in self or var_name not in self.get(_d_key, {}):
            # set variable
            _new_var = device_variable.get_private_variable(
                name=var_name,
                device=dev,
            )
            _new_var.set_value(var_value)
            _new_var.save()
            self.setdefault(_d_key, {})[var_name] = (var_value, _new_var.inherit)
        else:
            if self[_d_key][var_name][0] != var_value:
                # update
                dev_variable = device_variable.objects.get(Q(name=var_name) & Q(device=dev))
                dev_variable.value = var_value
                dev_variable.save()
                # update dict
                self[_d_key][var_name] = (var_value, dev_variable.inherit)

    def _fetch_vars(self, key, ref_dev):
        self[key] = {
            cur_var.name: (cur_var.get_value(), cur_var.inherit) for cur_var in device_variable.objects.filter(Q(device=ref_dev))
        }

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            self._global_key(),
            self._device_group_key(cur_dev),
            self._device_key(cur_dev),
        )
        if global_key not in self:
            # read global configs
            self._fetch_vars(global_key, self.__cdg)
            # update with def_dict
            for key, value in self.__def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = (value, True)
        if not self.__prefill:
            # do not query the devices
            if dg_key not in self:
                # read device_group configs
                self._fetch_vars(dg_key, cur_dev.device_group.device)
            if dev_key not in self:
                # read device configs
                self._fetch_vars(dev_key, cur_dev)
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n, ignore_inh in [
            (dev_key, "d", True),
            (dg_key, "g", False),
            (global_key, "c", False),
        ]:
            info_dict[key_n] = 0
            for s_key, (s_value, inherit) in self.get(key, {}).iteritems():
                if (inherit or ignore_inh) and (s_key not in ret_dict):
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        # print cur_dev, ret_dict, info_dict
        return ret_dict, info_dict
