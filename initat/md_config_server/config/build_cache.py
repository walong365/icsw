# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
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
""" cache of various settings and luts for md-config-server """

import time
from collections import defaultdict

from django.db.models import Q
from lxml.builder import E

from initat.cluster.backbone import routing
from initat.cluster.backbone.models import device, device_group, mon_check_command, user, \
    mon_host_cluster, mon_service_cluster, MonHostTrace, mon_host_dependency, mon_service_dependency, \
    MonHostTraceGeneration, netdevice
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.backbone.var_cache import VarCache
from initat.icsw.service.instance import InstanceXML
from initat.snmp.sink import SNMPSink
from initat.tools import logging_tools, process_tools, server_mixins
from .global_config import global_config
from ..config import SimpleCounter, MonFileContainer, SpecialTypesEnum

__all__ = [
    "GlobalBuildCache",
    "HostBuildCache",
    "MonCheckEmitter",
]


class MonCheckEmitter(object):
    # holds the mon_checks to generate
    def __init__(
        self,
        master_build: bool,
        host_filter: object,
        monitor_server: int=0,
        single_build: bool=False,
    ):
        # filter for all configs, wider than the h_filter
        ac_filter = Q()
        if master_build:
            # need all devices for master
            pass
        else:
            host_filter &= Q(monitor_server=monitor_server)
            ac_filter &= Q(monitor_server=monitor_server)
        if not single_build:
            host_filter &= Q(enabled=True) & Q(device_group__enabled=True)
            ac_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        self.host_pk_list = device.objects.exclude(
            Q(is_meta_device=True)
        ).filter(
            host_filter
        ).values_list(
            "pk", flat=True
        )
        import pprint
        # dict of all check_commands per device
        cc_per_dev = defaultdict(set)
        _DEBUG = False
        if _DEBUG:
            # debug: eddie == 3
            # uptime (uptime), check command (uptime) == 3, 79
            # ac_filter &= Q(name="eddie")
            print("Hosts: ", list(self.host_pk_list))

        # Step 1: meta devices, check_commands via config, resolve devices via device_group

        for _entry in device.objects.filter(
            Q(
                is_meta_device=True,
                device_config__config__mcc_rel__isnull=False,
                device_config__config__mcc_rel__enabled=True,
                # device_group__device_group__name="eddie",
            )
        ).values_list(
            # tuple format:
            # - device idx (from meta device)
            "device_group__device_group",
            # - mcc index via config
            "device_config__config__mcc_rel",
        ).order_by(
            "device_group__device_group",
            "device_config__config__mcc_rel",
        ).distinct():
            # distinct beacuse a config check can be referenced multiple times
            cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s1")
            pprint.pprint(cc_per_dev)

        # Step 2: meta devices, check_commands via direct mon_check, resolve
        # devices via device_group
        for _entry in device.objects.filter(
            Q(
                is_meta_device=True,
                mcc_devices__isnull=False,
                mcc_devices__enabled=True,
            )
        ).values_list(
            # device idx
            "device_group__device_group",
            # direct devices
            "mcc_devices",
        ).distinct():
            if _entry[1] in cc_per_dev[_entry[0]]:
                # already set, interpret as exclusion
                cc_per_dev[_entry[0]].remove(_entry[1])
            else:
                cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s2")
            pprint.pprint(cc_per_dev)

        # Step 3: check commands per device via configs

        for _entry in device.objects.filter(
            ac_filter
        ).filter(
            Q(
                device_config__config__mcc_rel__isnull=False,
                device_config__config__mcc_rel__enabled=True,
            )
        ).values_list(
            # device idx
            "idx",
            # mcc via config
            "device_config__config__mcc_rel",
        ).distinct():
            cc_per_dev[_entry[0]].add(_entry[1])

        if _DEBUG:
            print("s3")
            pprint.pprint(cc_per_dev)

        # Step 4: check commands per device direct via mcc

        for _entry in device.objects.filter(
            ac_filter
        ).filter(
            Q(
                mcc_devices__isnull=False,
                mcc_devices__enabled=True,
            )
        ).values_list(
            "idx",
            "mcc_devices",
        ).distinct():
            if _entry[1] in cc_per_dev[_entry[0]]:
                # interpret as exlcusion
                cc_per_dev[_entry[0]].remove(_entry[1])
            else:
                cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s4")
            pprint.pprint(cc_per_dev)

        # final debug dump

        if _DEBUG:
            # dump result
            for _key, _values in cc_per_dev.items():
                _dev = device.objects.get(Q(idx=_key))
                if _values:
                    print(
                        "Checks for device {} ({:d}, count={:d})".format(
                            str(_dev),
                            _dev.idx,
                            len(_values)
                        )
                    )
                    for _val in _values:
                        print(
                            "   [{:d}] {}".format(
                                _val,
                                mon_check_command.objects.filter(Q(idx=_val))
                            )
                        )
        # result
        self._result = cc_per_dev

    def __getitem__(self, key):
        return self._result[key]


class HostBuildCache(object):
    # cache for building a single host
    def __init__(self, cur_dev):
        # print("init", unicode(cur_dev))
        # device object
        self.device = cur_dev
        # self.dynamic_checks = False
        # list of dynamic checks
        self.dynamic_checks = []
        # device config file
        self.device_file = None
        self.start_time = time.time()
        self.log_cache = []
        self.counter = SimpleCounter()
        self.num_checks = 0
        # contact groups for this host
        # self.contact_groups = None
        # dont set a default value (has to be set in build process)
        # self.host_is_actively_checked = None
        # host config list
        self.host_config_list = MonFileContainer(self.device.full_name)
        # pending fetches, for dyn_fetch call
        self.pending_fetch_calls = []

    def add_pending_fetch(self, s_instance):
        s_instance.hbc = self
        self.pending_fetch_calls.append(s_instance)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_cache.append((what, log_level))
        if log_level == logging_tools.LOG_LEVEL_WARN:
            self.counter.warning()
        elif log_level == logging_tools.LOG_LEVEL_OK:
            self.counter.ok()
        else:
            # everything else counts as error
            self.counter.error()

    def add_dynamic_check(self, s_check):
        self.dynamic_checks.append(s_check)

    def build_finished(self):
        self.end_time = time.time()

    def add_checks(self, num=1):
        self.num_checks += num

    @property
    def write_logs(self):
        # check for log emit
        return True if self.counter.num_error else False

    def flush_logs(self, logger):
        for what, level in self.log_cache:
            logger.log(level, what)

    def store_to_db(self):
        # check for changed flags / fields
        upd_fields = []
        _has_dyn_checks = True if len(self.dynamic_checks) else False
        if self.device.dynamic_checks != _has_dyn_checks:
            upd_fields.append("dynamic_checks")
            self.device.dynamic_checks = _has_dyn_checks
        if upd_fields:
            self.device.save(update_fields=upd_fields)
        # print(_has_dyn_checks, len(self.dynamic_checks))

    @property
    def info_str(self):
        _counter = self.counter
        # info string for logging
        info_str = "NC={:3d} / DC={:3d}, logs: {:3d} / {:3d} / {:3d} ({:3d} total) [{}] in {:>16s}".format(
            self.num_checks,
            len(self.dynamic_checks),
            _counter.num_ok,
            _counter.num_warning,
            _counter.num_error,
            len(self.log_cache),
            "l " if _counter.num_error == 0 else "lw",
            logging_tools.get_diff_time_str(self.end_time - self.start_time),
        )
        return info_str

    def get_result_xml(self):
        return E.device(
            pk="{:d}".format(self.device.idx),
            dynamic_checks="1" if self.device.dynamic_checks else "0",
        )

    # set device (== host config) file
    def set_device_file(self, d_file):
        self.device_file = d_file
        self.host_config_list.append(d_file)


class GlobalBuildCache(object):
    # cache for build (all hosts)
    def __init__(self, log_com, full_build, routing_fingerprint=None, router_obj=None):
        s_time = time.time()
        self.log_com = log_com
        self.router = routing.SrvTypeRouting(log_com=self.log_com)
        self.instance_xml = InstanceXML(log_com=self.log, quiet=True)
        # build cache to speed up config generation
        # stores various cached objects
        # routing handling
        if router_obj is None:
            # slave, no consumer
            self.consumer = None
            self.routing_fingerprint = routing_fingerprint
            # must exist
            self.__trace_gen = MonHostTraceGeneration.objects.get(Q(fingerprint=self.routing_fingerprint))
        else:
            # master, install the egg consumer
            self.consumer = server_mixins.EggConsumeObject(self)
            self.consumer.init({"SERVICE_ENUM_NAME": icswServiceEnum.monitor_server.name})
            self.routing_fingerprint = router_obj.fingerprint
            # get generation
            try:
                self.__trace_gen = MonHostTraceGeneration.objects.get(Q(fingerprint=self.routing_fingerprint))
            except MonHostTraceGeneration.DoesNotExist:
                self.log("creating new tracegeneration")
                self.__trace_gen = router_obj.create_trace_generation()
            # delete old ones
            MonHostTrace.objects.exclude(Q(generation=self.__trace_gen)).delete()

        # global luts
        # print("i0")
        self.mcc_lut_3 = {_check.pk: _check for _check in mon_check_command.objects.all()}
        # add dummy entries
        for _value in self.mcc_lut_3.values():
            # why ? FIXME
            # _value.mccs_id = None
            # _value.check_command_pk = _value.pk
            pass
        self.mcc_lut = {
            key: (v0, v1, v2) for key, v0, v1, v2 in mon_check_command.objects.all().values_list("pk", "name", "description", "config_rel__name")
        }
        # lookup table for config -> mon_check_commands
        self.mcc_lut_2 = {}
        for v_list in mon_check_command.objects.all().values_list("name", "config_rel__name"):
            self.mcc_lut_2.setdefault(v_list[1], []).append(v_list[0])
        # print("i1")
        # import pprint
        # pprint.pprint(self.mcc_lut)
        # host list, set from caller
        self.host_list = []
        self.dev_templates = None
        self.serv_templates = None
        self.single_build = False
        self.debug = False
        self.__var_cache = VarCache(
            prefill=full_build,
            def_dict={
                "SNMP_VERSION": 2,
                "SNMP_READ_COMMUNITY": "public",
                "SNMP_WRITE_COMMUNITY": "private",
            }
        )
        self.join_char = "_" if global_config["SAFE_NAMES"] else " "
        # device_group user access
        self.dg_user_access = {}
        mon_user_pks = list(
            user.objects.filter(Q(mon_contact__pk__gt=0)).values_list("pk", flat=True)
        )
        for _dg in device_group.objects.all().prefetch_related("user_set"):
            self.dg_user_access[_dg.pk] = list([_user for _user in _dg.user_set.all() if _user.pk in mon_user_pks])
        # all hosts dict
        self.all_hosts_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.objects.filter(
                Q(device_group__enabled=True) & Q(enabled=True)
            ).select_related(
                "domain_tree_node",
                "device_group"
            ).prefetch_related(
                "monhosttrace_set"
            )
        }
        for _host in self.all_hosts_dict.values():
            _host.reachable = True
        # print(_res)
        # traces in database
        self.log("traces found in database: {:d}".format(MonHostTrace.objects.all().count()))
        # read traces
        self.__host_traces = {}
        for _trace in MonHostTrace.objects.filter(Q(generation=self.__trace_gen)):
            self.__host_traces.setdefault(_trace.device_id, []).append(_trace)
        # import pprint
        # pprint.pprint(self.__host_traces)
        # host / service clusters
        clusters = {}
        for _obj, _name in [
            (
                mon_host_cluster, SpecialTypesEnum.mon_host_cluster
            ), (
                mon_service_cluster, SpecialTypesEnum.mon_service_cluster
            )
        ]:
            _lut = {}
            _query = _obj.objects.all()
            if _name == SpecialTypesEnum.mon_service_cluster:
                _query = _query.select_related("mon_check_command")
            for _co in _query:
                _lut[_co.pk] = _co.main_device_id
                _co.devices_list = []
                clusters.setdefault(_name, {}).setdefault(_co.main_device_id, []).append(_co)
            for _entry in _obj.devices.through.objects.all():
                if _name == SpecialTypesEnum.mon_host_cluster:
                    _pk = _entry.mon_host_cluster_id
                else:
                    _pk = _entry.mon_service_cluster_id
                _tco = [_co for _co in clusters[_name][_lut[_pk]] if _co.pk == _pk][0]
                _tco.devices_list.append(_entry.device_id)
                # clusters[_name][_entry.]
        self.__clusters = clusters
        # host / service dependencies
        deps = {}
        for _obj, _name in [
            (
                mon_host_dependency, SpecialTypesEnum.mon_host_dependency
            ), (
                mon_service_dependency, SpecialTypesEnum.mon_service_dependency
            )
        ]:
            _lut = {}
            _query = _obj.objects.all().prefetch_related("devices", "dependent_devices")
            if _name == SpecialTypesEnum.mon_host_dependency:
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
                if _name == SpecialTypesEnum.mon_host_dependency:
                    _pk = _entry.mon_host_dependency_id
                else:
                    _pk = _entry.mon_service_dependency_id
                for _devpk in _lut[_pk]:
                    _tdo = [_do for _do in deps[_name][_devpk] if _do.pk == _pk][0]
                    _tdo.devices_list.append(_entry.device_id)
            for _entry in _obj.dependent_devices.through.objects.all():
                if _name == SpecialTypesEnum.mon_host_dependency:
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
        self.log(
            "init build_cache in {}".format(
                logging_tools.get_diff_time_str(e_time - s_time)
            )
        )

    def close(self):
        if self.consumer:
            self.consumer.close()

    def set_global_config(self, gc, cur_dmap, hdep_from_topo):
        # set global config and other global values
        # global_config gc is an instance of MainConfig()
        self.global_config = gc
        # distance map
        self.cur_dmap = cur_dmap
        # host dependency from topology
        self.hdep_from_topo = hdep_from_topo
        # mon check special command lut (mccs_dict)
        # mccs_dict = {
        #     mccs.pk: mccs for mccs in mon_check_command_special.objects.all()
        #  }
        # for _value in list(mccs_dict.values()):
        #     mccs_dict[_value.name] = _value

        # for value in list(self.global_config["command"].values()):
        #     if value.mccs_id:
        #         # add links back to check_command_names
        #         mccs_dict[value.mccs_id].check_command_name = value.name
        # self.mccs_dict = mccs_dict
        # set settings for local monitor server (== master or slave)
        server_idxs = [self.global_config.monitor_server.pk]
        # get netip-idxs of own host
        self.server_net_idxs = set(
            netdevice.objects.filter(Q(device__in=server_idxs)).filter(Q(enabled=True)).values_list("pk", flat=True)
        )

    def feed_unreachable_pks(self, unreachable_pks):
        # set reachable flag
        for key, value in self.all_hosts_dict.items():
            value.reachable = value.pk not in unreachable_pks

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[bc] {}".format(what), log_level)

    def get_device_group_users(self, dg_pk):
        return [_user.login for _user in self.dg_user_access[dg_pk]]

    def get_host(self, pk):
        return self.all_hosts_dict[pk]

    def get_vars(self, host):
        return self.__var_cache.get_vars(host)

    def add_variable(self, new_var):
        self.__var_cache.add_variable(new_var)

    def set_variable(self, dev, var_name, var_value):
        self.__var_cache.set_variable(dev, var_name, var_value)

    def get_cluster(self, c_type: enumerate, main_device_id: int) -> list:
        if main_device_id in self.__clusters.get(c_type, {}):
            return self.__clusters[c_type][main_device_id]
        else:
            return []

    def get_dependencies(self, s_type, main_device_id):
        if main_device_id in self.__dependencies.get(s_type, {}):
            return self.__dependencies[s_type][main_device_id]
        else:
            return []

    def get_mon_host_trace(self, host, dev_net_idxs, srv_net_idxs) -> list:
        _traces = self.__host_traces.get(host.pk, [])
        if _traces:
            _dev_fp, _srv_fp = (
                MonHostTrace.get_fingerprint(dev_net_idxs),
                MonHostTrace.get_fingerprint(srv_net_idxs),
            )
            _traces = [_tr for _tr in _traces if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp]
            if _traces:
                return _traces[0].get_trace()
            else:
                return []
        else:
            return []

    def set_mon_host_trace(self, host, dev_net_idxs, srv_net_idxs, traces):
        _dev_fp, _srv_fp = (
            MonHostTrace.get_fingerprint(dev_net_idxs),
            MonHostTrace.get_fingerprint(srv_net_idxs),
        )
        # check for update
        _match_traces = [
            _tr for _tr in self.__host_traces.get(host.pk, []) if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp
        ]
        if _match_traces:
            _match_trace = _match_traces[0]
            if not _match_trace.match(traces):
                _match_trace.set_trace(traces)
                try:
                    _match_trace.save()
                except:
                    self.log(
                        "error saving trace {} for {}: {}".format(
                            str(traces),
                            str(_match_trace),
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            _new_trace = MonHostTrace.create_trace(self.__trace_gen, host, _dev_fp, _srv_fp, traces)
            self.__host_traces.setdefault(host.pk, []).append(_new_trace)

    def set_host_list(self, host_pks):
        self.host_pks = set(list(host_pks))
        for _pk in host_pks:
            self.all_hosts_dict[_pk].valid_ips = {}
            self.all_hosts_dict[_pk].invalid_ips = {}
        # print host_pks
