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
from initat.cluster.backbone.models import device, device_group, mon_check_command, \
    mon_host_cluster, mon_service_cluster, mon_trace, mon_host_dependency, mon_service_dependency
from initat.md_config_server.config.var_cache import var_cache
from initat.snmp.sink import SNMPSink
import configfile
import json
import logging_tools
import process_tools
import time


__all__ = [
    "build_cache",
]


global_config = configfile.get_global_config(process_tools.get_programm_name())


class build_cache(object):
    def __init__(self, log_com, cdg, full_build, unreachable_pks=[]):
        self.log_com = log_com
        # build cache to speed up config generation
        # stores various cached objects
        # global luts
        # lookup table for host_check_commands
        self.unreachable_pks = set(unreachable_pks or [])
        s_time = time.time()
        self.mcc_lut = {key: (v0, v1, v2) for key, v0, v1, v2 in mon_check_command.objects.all().values_list("pk", "name", "description", "config__name")}
        # lookup table for config -> mon_check_commands
        self.mcc_lut_2 = {}
        for v_list in mon_check_command.objects.all().values_list("name", "config__name"):
            self.mcc_lut_2.setdefault(v_list[1], []).append(v_list[0])
        # host list, set from caller
        self.host_list = []
        self.dev_templates = None
        self.serv_templates = None
        self.cache_mode = "???"
        self.single_build = False
        self.debug = False
        self.__var_cache = var_cache(cdg, prefill=full_build)
        self.join_char = "_" if global_config["SAFE_NAMES"] else " "
        # device_group user access
        self.dg_user_access = {}
        mon_user_pks = list(user.objects.filter(Q(mon_contact__pk__gt=0)).values_list("pk", flat=True))  # @UndefinedVariable
        for _dg in device_group.objects.all().prefetch_related("user_set"):
            self.dg_user_access[_dg.pk] = list([_user for _user in _dg.user_set.all() if _user.pk in mon_user_pks])
        # all hosts dict
        self.all_hosts_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.objects.filter(
                Q(device_group__enabled=True) & Q(enabled=True)
            ).select_related(
                "device_type",
                "domain_tree_node",
                "device_group"
            ).prefetch_related("mon_trace_set")
        }
        # set reachable flag
        for key, value in self.all_hosts_dict.iteritems():
            value.reachable = value.pk not in self.unreachable_pks
        # traces
        self.__host_traces = {host.pk: list(host.mon_trace_set.all()) for host in self.all_hosts_dict.itervalues()}
        # host / service clusters
        clusters = {}
        for _obj, _name in [(mon_host_cluster, "hc"), (mon_service_cluster, "sc")]:
            _lut = {}
            _query = _obj.objects.all()
            if _name == "sc":
                _query = _query.select_related("mon_check_command")
            for _co in _query:
                _lut[_co.pk] = _co.main_device_id
                _co.devices_list = []
                clusters.setdefault(_name, {}).setdefault(_co.main_device_id, []).append(_co)
            for _entry in _obj.devices.through.objects.all():
                if _name == "hc":
                    _pk = _entry.mon_host_cluster_id
                else:
                    _pk = _entry.mon_service_cluster_id
                _tco = [_co for _co in clusters[_name][_lut[_pk]] if _co.pk == _pk][0]
                _tco.devices_list.append(_entry.device_id)
                # clusters[_name][_entry.]
        self.__clusters = clusters
        # host / service dependencies
        deps = {}
        for _obj, _name in [(mon_host_dependency, "hd"), (mon_service_dependency, "sd")]:
            _lut = {}
            _query = _obj.objects.all().prefetch_related("devices", "dependent_devices")
            if _name == "hd":
                _query = _query.select_related(
                    "mon_host_dependency_templ",
                    "mon_host_dependency_templ__dependency_period",
                )
            else:
                _query = _query.select_related(
                    "mon_service_cluster",
                    "mon_check_command",
                    "dependent_mon_check_command",
                    "mon_service_dependency_templ",
                    "mon_service_dependency_templ__dependency_period",
                )
            for _do in _query:
                # == slaves
                _do.devices_list = []
                # == dependent devices
                _do.master_list = []
                _lut[_do.pk] = []
                for _dd in _do.dependent_devices.all():
                    _lut[_do.pk].append(_dd.pk)
                    deps.setdefault(_name, {}).setdefault(_dd.pk, []).append(_do)
            for _entry in _obj.devices.through.objects.all():
                if _name == "hd":
                    _pk = _entry.mon_host_dependency_id
                else:
                    _pk = _entry.mon_service_dependency_id
                for _devpk in _lut[_pk]:
                    _tdo = [_do for _do in deps[_name][_devpk] if _do.pk == _pk][0]
                    _tdo.devices_list.append(_entry.device_id)
            for _entry in _obj.dependent_devices.through.objects.all():
                if _name == "hd":
                    _pk = _entry.mon_host_dependency_id
                else:
                    _pk = _entry.mon_service_dependency_id
                for _devpk in _lut[_pk]:
                    _tdo = [_do for _do in deps[_name][_devpk] if _do.pk == _pk][0]
                    _tdo.master_list.append(_entry.device_id)
        self.__dependencies = deps
        # init snmp sink
        self.snmp_sink = SNMPSink(log_com)
        e_time = time.time()
        self.log("init build_cache in {}".format(logging_tools.get_diff_time_str(e_time - s_time)))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[bc] {}".format(what), log_level)

    def get_device_group_users(self, dg_pk):
        return [_user.login for _user in self.dg_user_access[dg_pk]]

    def get_host(self, pk):
        return self.all_hosts_dict[pk]

    def get_vars(self, host):
        return self.__var_cache.get_vars(host)

    def get_cluster(self, c_type, main_device_id):
        if main_device_id in self.__clusters.get(c_type, {}):
            return self.__clusters[c_type][main_device_id]
        else:
            return []

    def get_dependencies(self, s_type, main_device_id):
        if main_device_id in self.__dependencies.get(s_type, {}):
            return self.__dependencies[s_type][main_device_id]
        else:
            return []

    def get_mon_trace(self, host, dev_net_idxs, srv_net_idxs):
        _traces = self.__host_traces.get(host.pk, [])
        if _traces:
            _dev_fp, _srv_fp = (
                mon_trace.get_fp(dev_net_idxs),
                mon_trace.get_fp(srv_net_idxs),
            )
            _traces = [_tr for _tr in _traces if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp]
            if _traces:
                return _traces[0].get_trace()
            else:
                return []
        else:
            return []

    def set_mon_trace(self, host, dev_net_idxs, srv_net_idxs, traces):
        _dev_fp, _srv_fp = (
            mon_trace.get_fp(dev_net_idxs),
            mon_trace.get_fp(srv_net_idxs),
        )
        # check for update
        _match_traces = [_tr for _tr in self.__host_traces.get(host.pk, []) if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp]
        if _match_traces:
            _match_trace = _match_traces[0]
            if json.loads(_match_trace.traces) != traces:
                _match_trace.set_trace(traces)
                try:
                    _match_trace.save()
                except:
                    self.log(
                        "error saving trace {}: {}".format(
                            str(traces),
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            _new_trace = mon_trace.create_trace(host, _dev_fp, _srv_fp, json.dumps(traces))
            self.__host_traces.setdefault(host.pk, []).append(_new_trace)

    def set_host_list(self, host_pks):
        self.host_pks = set(list(host_pks))
        for _pk in host_pks:
            self.all_hosts_dict[_pk].valid_ips = {}
            self.all_hosts_dict[_pk].invalid_ips = {}
        # print host_pks
