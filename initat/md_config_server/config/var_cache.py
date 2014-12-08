# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from django.db.models import Q
from initat.cluster.backbone.models import device_variable


__all__ = [
    "var_cache",
]


# a similiar structure is used in the server process of rrd-grapher
class var_cache(dict):
    def __init__(self, cdg, prefill=False):
        super(var_cache, self).__init__(self)
        self.__cdg = cdg
        self.__prefill = prefill
        if prefill:
            self._prefill()

    def get_global_def_dict(self):
        return {
            "SNMP_VERSION": 2,
            "SNMP_READ_COMMUNITY": "public",
            "SNMP_WRITE_COMMUNITY": "private",
        }

    def _prefill(self):
        for _var in device_variable.objects.all().select_related("device__device_type"):
            if _var.device.device_type.identifier == "MD":
                if _var.device.device_group_id == self.__cdg.pk:
                    _key = "GLOBAL"
                    if _key not in self:
                        self[_key] = {g_key: g_value for g_key, g_value in self.get_global_def_dict().iteritems()}
                else:
                    _key = "dg__{:d}".format(_var.device.device_group_id)
            else:
                _key = "dev__{:d}".format(_var.device_id)
            self.setdefault(_key, {})[_var.name] = _var.value

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__{:d}".format(cur_dev.device_group_id),
            "dev__{:d}".format(cur_dev.pk))
        if global_key not in self:
            def_dict = self.get_global_def_dict()
            # read global configs
            self[global_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=self.__cdg))])
            # update with def_dict
            for key, value in def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = value
        if not self.__prefill:
            # do not query the devices
            if dg_key not in self:
                # read device_group configs
                self[dg_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device))])
            if dev_key not in self:
                # read device configs
                self[dev_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev))])
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n in [(dev_key, "d"), (dg_key, "g"), (global_key, "c")]:
            info_dict[key_n] = 0
            for s_key, s_value in self.get(key, {}).iteritems():
                if s_key not in ret_dict:
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        # print cur_dev, ret_dict, info_dict
        return ret_dict, info_dict
