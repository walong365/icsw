# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2008,2012-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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
"""
module to operate with config and ip relationsships in the database. This
module gets included from configfile
"""

if __name__ == "__main__":
    # for testing
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")
    import django
    django.setup()

import array
import netifaces
import time
import hashlib

from django.db.models import Q, Count

from initat.cluster.backbone.models import config, device, net_ip, device_config, \
    netdevice, peer_information, config_int, config_blob, config_str, config_bool, \
    MonHostTraceGeneration, network_type
from initat.constants import VERSION_CS_NAME
from . import configfile, logging_tools, process_tools, config_store

try:
    from initat.cluster.backbone.models import ICSWVersion, VERSION_NAME_LIST
except ImportError:
    # when doing an update from an older ICSW-Version without ICSWVersion model
    pass


class RouterObject(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__cur_gen = 0
        self.nx = None
        self.fp = None
        self._update()

    def init_fingerprint(self):
        import networkx
        if self.nx:
            self.previous_fp = self.fp.hexdigest()
            del self.nx
            del self.fp
        else:
            self.previous_fp = "N/A"
        self.nx = networkx.Graph()
        self.fp = hashlib.new("sha256")

    def add_nodes(self):
        self.nx.add_nodes_from(list(self.nd_dict.keys()))
        for _key in sorted(self.nd_dict.keys()):
            self.fp.update("n{:d}".format(_key).encode("utf-8"))

    def create_trace_generation(self):
        # create new MonHostTrace Generation
        return MonHostTraceGeneration.objects.create(
            nodes=len(self.nd_dict),
            edges=len(self.simple_peer_dict),
            fingerprint=self.fingerprint
        )

    def add_edges(self):
        for node_pair, penalty in self.simple_peer_dict.items():
            src_node, dst_node = node_pair
            self.nx.add_edge(src_node, dst_node, weight=penalty)
            self.fp.update("e{:d},{:d},{:d}".format(src_node, dst_node, penalty).encode("utf-8"))

    @property
    def latest_update(self):
        return self.__latest_update

    @property
    def fingerprint_changed(self):
        return self.fingerprint != self.previous_fp

    @property
    def fingerprint(self):
        return self.fp.hexdigest()

    def check_for_update(self):
        self._update()

    def _update(self):
        self.__latest_update = time.time()
        # the concept of marking the current route setup dirty is flawed (too many dependencies)
        # and is therefore removed
        # latest_gen = route_generation.objects.all().order_by("-generation")
        # if latest_gen:
        #    latest_gen = latest_gen[0].generation
        # else:
        #    latest_gen = route_generation(generation=1)
        #    latest_gen.save()
        #    latest_gen = latest_gen.generation
        latest_gen = self.__cur_gen + 1
        if latest_gen != self.__cur_gen:
            s_time = time.time()
            self.all_nds = netdevice.objects.exclude(
                Q(device__is_meta_device=True)
            ).exclude(
                Q(enabled=False)
            ).filter(
                Q(device__enabled=True) & Q(device__device_group__enabled=True)
            ).values_list(
                "idx", "device", "routing", "penalty", "inter_device_routing"
            )
            self.dev_dict = {}
            for cur_nd in self.all_nds:
                if cur_nd[1] not in self.dev_dict:
                    self.dev_dict[cur_nd[1]] = []
                self.dev_dict[cur_nd[1]].append(cur_nd)
            self.nd_lut = {
                value[0]: value[1] for value in netdevice.objects.exclude(
                    Q(enabled=False)
                ).values_list(
                    "pk", "device"
                ) if value[1] in self.dev_dict
            }
            self.nd_dict = {cur_nd[0]: cur_nd for cur_nd in self.all_nds}
            self.log(
                "init router helper object, {} / {}".format(
                    logging_tools.get_plural("netdevice", len(self.all_nds)),
                    logging_tools.get_plural("peer information", peer_information.objects.count())
                )
            )
            # peer dict
            self.peer_dict, self.simple_peer_dict = ({}, {})
            all_peers = peer_information.objects.all().values_list(
                "s_netdevice_id", "d_netdevice_id", "penalty"
            )
            for s_nd_id, d_nd_id, penalty in all_peers:
                if s_nd_id in self.nd_lut and d_nd_id in self.nd_lut:
                    self.peer_dict[
                        (s_nd_id, d_nd_id)
                    ] = penalty + self.nd_dict[s_nd_id][3] + self.nd_dict[d_nd_id][3]
                    self.peer_dict[
                        (d_nd_id, s_nd_id)
                    ] = penalty + self.nd_dict[s_nd_id][3] + self.nd_dict[d_nd_id][3]
                    self.simple_peer_dict[
                        (s_nd_id, d_nd_id)
                    ] = penalty
            # add simple peers for device-internal networks
            for nd_list in self.dev_dict.values():
                route_nds = [cur_nd for cur_nd in nd_list if cur_nd[4]]
                if len(route_nds) > 1:
                    for s_idx in range(len(route_nds)):
                        for d_idx in range(s_idx + 1, len(route_nds)):
                            s_pk, d_pk = (route_nds[s_idx][0], route_nds[d_idx][0])
                            int_penalty = 1
                            self.peer_dict[(s_pk, d_pk)] = int_penalty
                            self.peer_dict[(d_pk, s_pk)] = int_penalty
                            self.simple_peer_dict[(s_pk, d_pk)] = int_penalty
            self.init_fingerprint()
            self.add_nodes()
            self.add_edges()
            if self.__cur_gen:
                self.log(
                    "update generation from {:d} ({}) to {:d} ({}) in {}".format(
                        self.__cur_gen,
                        self.previous_fp,
                        latest_gen,
                        self.fingerprint if self.fingerprint != self.previous_fp else "same",
                        logging_tools.get_diff_time_str(time.time() - s_time),
                    ),
                    logging_tools.LOG_LEVEL_WARN if self.fingerprint_changed else logging_tools.LOG_LEVEL_OK
                )
            else:
                self.log(
                    "init with generation {:d} ({}) in {}".format(
                        latest_gen,
                        self.fingerprint,
                        logging_tools.get_diff_time_str(time.time() - s_time),
                    )
                )
            self.__cur_gen = latest_gen

    def get_penalty(self, in_path):
        return sum(
            [
                self.peer_dict[
                    (
                        in_path[idx],
                        in_path[idx + 1]
                    )
                ] for idx in range(len(in_path) - 1)
            ]
        ) + sum(
            [
                self.nd_dict[entry][3] for entry in in_path
            ]
        )

    def add_penalty(self, in_path):
        return (self.get_penalty(in_path), in_path)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if hasattr(self.__log_com, "log"):
            self.__log_com.log(
                log_level,
                "[router] {}".format(what)
            )
        else:
            self.__log_com(
                "[router] {}".format(what),
                log_level
            )

    def get_ndl_ndl_pathes(self, s_list, d_list, **kwargs):
        import networkx
        """
        returns all pathes between s_list and d_list (:: net_device)
        """
        only_ep = kwargs.get("only_endpoints", False)
        all_paths = []
        for s_ndev in s_list:
            for d_ndev in d_list:
                try:
                    if only_ep:
                        all_paths.append(networkx.shortest_path(self.nx, s_ndev, d_ndev, weight="weight"))
                    else:
                        all_paths.extend(networkx.all_shortest_paths(self.nx, s_ndev, d_ndev, weight="weight"))
                except networkx.exception.NetworkXNoPath:
                    pass
        if kwargs.get("add_penalty", False):
            if only_ep:
                all_paths = [(self.get_penalty(cur_path), cur_path[0], cur_path[-1]) for cur_path in all_paths]
            else:
                all_paths = [(self.get_penalty(cur_path), cur_path) for cur_path in all_paths]
        elif only_ep:
            all_paths = [(cur_path[0], cur_path[-1]) for cur_path in all_paths]
        return all_paths

    def map_path_to_device(self, in_path):
        return [self.nd_lut[value] for value in in_path]

    def get_clusters(self):
        import networkx
        clusters = []
        for _cce in networkx.connected_components(self.nx):
            _num_nds = len(_cce)
            _dev_pks = set([self.nd_lut[_val] for _val in _cce])
            clusters.append(
                {
                    "with_netdevices": True,
                    "net_devices": _num_nds,
                    "devices": len(_dev_pks),
                    "device_pks": list(_dev_pks),
                }
            )
        # add devices withoutnetdevices
        for _wnd in device.all_real_enabled.filter(
            Q(netdevice=None)
        ).values_list("pk", flat=True):
            clusters.append(
                {
                    "with_netdevices": False,
                    "net_devices": 0,
                    "devices": 1,
                    "device_pks": [_wnd],
                }
            )
        # biggest clusters first
        return sorted(clusters, key=lambda _c: _c["devices"], reverse=True)


class TopologyObject(object):
    def __init__(self, log_com, graph_mode="all", **kwargs):
        self.__log_com = log_com
        self.nx = None
        # ignore device-internal links
        self.ignore_self = kwargs.get("ignore_self", True)
        self.__graph_mode = graph_mode
        if self.__graph_mode.startswith("sel"):
            self.__dev_pks = kwargs["dev_list"]
        self.__user = kwargs.get("user", None)
        if self.__user is not None:
            if self.__user.is_superuser:
                self.__only_allowed_device_groups = False
            else:
                self.__only_allowed_device_groups = kwargs.get("only_allowed_device_groups", False)
        else:
            self.__only_allowed_device_groups = False
        self._update()

    def add_nodes(self, pks):
        self.nx.add_nodes_from(pks)  # self.dev_dict.keys())

    def add_edges(self):
        # for node_pair, network_idx_list in self.simple_peer_dict.iteritems():
        for node_pair, penalty_list in self.simple_peer_dict.items():
            src_node, dst_node = node_pair
            if src_node == dst_node:
                pass
            else:
                # print src_node, dst_node, penalty_list
                # self.nx.add_edge(src_node, dst_node, networkidx=sum(network_idx_list))
                self.nx.add_edge(src_node, dst_node, min_penalty=min(penalty_list), num_connections=len(penalty_list))

    def _update(self):
        import networkx
        s_time = time.time()
        dev_sel = device.all_real_enabled.select_related("domain_tree_node")
        if self.__graph_mode.startswith("sel"):
            dev_sel = dev_sel.filter(Q(pk__in=self.__dev_pks))
        _dev_pks = set(dev_sel.values_list("pk", flat=True))
        if self.__graph_mode == "none":
            _dev_pks = set()
        else:
            if self.__graph_mode.startswith("selp"):
                # add further rings
                for _idx in range(int(self.__graph_mode[-1])):
                    new_dev_pks = set(
                        device.all_enabled.filter(
                            Q(netdevice__peer_s_netdevice__d_netdevice__device__in=_dev_pks)  # self.dev_dict.keys())
                        ).values_list("idx", flat=True)
                    ) | set(
                        device.all_enabled.filter(
                            Q(netdevice__peer_d_netdevice__s_netdevice__device__in=_dev_pks)  # self.dev_dict.keys())
                        ).values_list("idx", flat=True)
                    )
                    if new_dev_pks:
                        _dev_pks |= new_dev_pks
                    else:
                        break
            elif self.__graph_mode == "core":
                p_list = set(
                    sum(
                        [
                            [
                                (s_val, d_val), (d_val, s_val)
                            ] for s_val, d_val in peer_information.objects.all().values_list(
                                "s_netdevice_id", "d_netdevice_id"
                            ) if s_val != d_val
                        ],
                        []
                    )
                )
                nd_dict = {value[0]: value[1] for value in netdevice.objects.all().values_list("pk", "device")}
                # remove all devices which have only a single selection to the current dev_dict
                while True:
                    dev_list = [nd_dict[s_val] for s_val, d_val in p_list]
                    rem_devs = set([key for key in dev_list if dev_list.count(key) == 1])
                    rem_nds = set([key for key, value in nd_dict.items() if value in rem_devs])
                    p_list = [(s_val, d_val) for s_val, d_val in p_list if s_val not in rem_nds and d_val not in rem_nds]
                    _dev_pks -= rem_devs
                    # self.dev_dict = {key: value for key, value in self.dev_dict.iteritems() if key not in rem_devs}
                    if not rem_devs:
                        break
        if self.__only_allowed_device_groups:
            # print self.__user
            _allowed_dev_pks = device.all_enabled.filter(
                Q(device_group__in=self.__user.get_allowed_object_list("backbone.device.access_device_group"))
            ).values_list("pk", flat=True)
            _dev_pks &= _allowed_dev_pks
            # self.dev_dict = {_key: _value for _key, _value in self.dev_dict.iteritems() if _key in _allowed_dev_pks}
            # print self.dev_dict.keys()
        nd_dict = {
            value[0]: value[1] for value in netdevice.objects.all().values_list("pk", "device")
        }
        ip_dict = {
            value[0]: (value[1], value[2]) for value in net_ip.objects.all().values_list(
                "pk",
                "netdevice",
                "network",
            )
        }
        # reorder ip_dict
        nd_lut = {}
        for _net_ip_pk, (nd_pk, nw_pk) in ip_dict.items():
            nd_lut.setdefault(nd_pk, []).append(nw_pk)
        self.log(
            "init topology helper object, {} / {}, device_groups={}".format(
                logging_tools.get_plural("device", len(_dev_pks)),
                logging_tools.get_plural("peer information", peer_information.objects.count()),
                "only allowed" if self.__only_allowed_device_groups else "all",
            )
        )
        # peer dict
        self.peer_dict, self.simple_peer_dict = ({}, {})
        all_peers = peer_information.objects.all().values_list("s_netdevice_id", "d_netdevice_id", "penalty")
        # all devices which are connected to another device
        foreign_devs = set()
        for s_nd_id, d_nd_id, penalty in all_peers:
            if nd_dict[s_nd_id] in _dev_pks and nd_dict[d_nd_id] in _dev_pks:
                src_device_id = nd_dict[s_nd_id]
                dst_device_id = nd_dict[d_nd_id]
                src_device_id, dst_device_id = (
                    min(src_device_id, dst_device_id),
                    max(src_device_id, dst_device_id)
                )
                if src_device_id != dst_device_id:
                    foreign_devs.add(src_device_id)
                    foreign_devs.add(dst_device_id)
                self.simple_peer_dict.setdefault(
                    (src_device_id, dst_device_id),
                    []
                ).append(penalty)
        if self.nx:
            del self.nx
        self.nx = networkx.Graph()
        if self.ignore_self and not (self.__graph_mode.startswith("sel") or self.__graph_mode in ["all"]):
            # remove all devices which are not connected to another device
            # only ignore self-references when the graph_mode is not selected* (?)
            _dev_pks &= set(foreign_devs)
            # self.dev_dict = {key: value for key, value in self.dev_dict.iteritems() if key in foreign_devs}
        self.add_nodes(_dev_pks)
        self.add_edges()
        # add num_nds / num_peers (only nds)
        for _dev_pk, _num_nds in device.all_enabled.filter(
            Q(pk__in=_dev_pks)
        ).annotate(num_nds=Count("netdevice")).values_list("pk", "num_nds"):
            self.nx.node[_dev_pk]["num_nds"] = _num_nds
        e_time = time.time()
        self.log(
            "creation took {}".format(
                logging_tools.get_diff_time_str(e_time - s_time)
            )
        )

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[TopObj] {}".format(what), log_level)


_VAR_LUT = {
    "int": config_int,
    "str": config_str,
    "blob": config_blob,
    "bool": config_bool,
}


def get_config_var_list(config_obj, config_dev):
    r_dict = {}
    # dict of local vars without specified host
    # l_var_wo_host = {}
    for short in [
        "str",
        "int",
        "blob",
        "bool"
    ]:
        src_sql_obj = _VAR_LUT[short].objects
        for db_rec in src_sql_obj.filter(
            (
                Q(device=0) |
                Q(device=None) |
                Q(device=config_dev.pk)
            ) & (
                Q(config=config_obj)
            ) & (
                Q(config__device_config__device=config_dev)
            )
        ):
            if db_rec.name.count(":"):
                var_global = False
                _local_host_name, var_name = db_rec.name.split(":", 1)
            else:
                var_global = True
                _local_host_name, var_name = (config_dev.name, db_rec.name)
            if isinstance(db_rec.value, array.array):
                new_val = configfile.StringConfigVar(db_rec.value.tostring(), source="{}_table".format(short))
            elif short == "int":
                new_val = configfile.IntegerConfigVar(int(db_rec.value), source="{}_table".format(short))
            elif short == "bool":
                new_val = configfile.BoolConfigVar(bool(db_rec.value), source="{}_table".format(short))
            else:
                new_val = configfile.StringConfigVar(db_rec.value, source="{}_table".format(short))
            new_val.is_global = var_global
            r_dict[var_name.upper()] = new_val
    return r_dict


class icswServerCheckResult(object):
    def __init__(self, srv_check, service_type_enunm):
        # link to icswServerCheck
        self._srv_check = srv_check
        # device for which the config is set
        self.effective_device = None
        # config or None
        self.config = None
        # server origin, one of unknown,
        # ...... real (hostname matches and config set local)
        # ...... meta (hostname matches and config set to meta_device)
        # ...... virtual (hostname mismatch, ip match)
        # ...... virtual meta (hostname mismatch, ip match, config set to meta_device)
        self.server_origin = "unknown"
        # info string
        self.server_info_str = "not set"
        # set service type enum
        self.service_type_enum = service_type_enunm
        if self.service_type_enum is not None:
            self.real_server_name = self.service_type_enum.name
        else:
            self.real_server_name = ""
        # config variable dict
        self.__config_vars = {}

    def set_fields(self, **kwargs):
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise KeyError(
                    "key {} not defined in {}".format(
                        key,
                        self.__class__.__name__
                    )
                )
            else:
                setattr(self, key, value)

    def set_srv_info(self, sdsc, s_info_str):
        self.server_origin = sdsc
        self.set_result(
            "{} '{}'-server via service_type_enum {}".format(
                self.server_origin,
                self.service_type_enum.name,
                s_info_str
            )
        )

    def set_result(self, info_str):
        self.server_info_str = info_str

    def fetch_config_vars(self):
        self.__config_vars.update(get_config_var_list(self.config, self.effective_device))

    def has_key(self, var_name):
        return var_name in self.__config_vars

    def __contains__(self, var_name):
        return var_name in self.__config_vars

    def keys(self):
        return list(self.__config_vars.keys())

    def is_fixed(self, var_name):
        return self.__config_vars[var_name].fixed

    def copy_flag(self, var_name, new_var):
        self.__config_vars[var_name].set_is_global(new_var.is_global())

    def get_source(self, var_name):
        return self.__config_vars[var_name].source

    def __setitem__(self, var_name, var_value):
        self.__config_vars[var_name] = var_value

    def __getitem__(self, var_name):
        return self.__config_vars[var_name].value


class icswServerCheck(object):
    """
    is called icswServerCheck, but can also be used for nodes
    checks if the device specified via kwargs (or the local device)
    has one or more service_type_enum set
    """
    def __init__(
        self,
        service_type_enum: enumerate=None,
        service_type_enum_list: list=None,
        **kwargs
    ):
        # device from database or None
        self.device = None
        # important: may be the empty list
        if service_type_enum_list is not None:
            self.multiple = True
            self.__service_type_enum = service_type_enum_list
        else:
            self.multiple = False
            if service_type_enum is None:
                self.__service_type_enum = []
            else:
                self.__service_type_enum = [service_type_enum]
        if "db_version_dict" in kwargs:
            self.__db_version_dict = kwargs["db_version_dict"]
        else:
            self.__db_version_dict = ICSWVersion.get_latest_db_dict()
        if "sys_version_dict" in kwargs:
            self.__sys_version_dict = kwargs["sys_version_dict"]
        else:
            _cs = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
            self.__sys_version_dict = {
                _name: _cs[_name] for _name in VERSION_NAME_LIST
            }
        # print ICSWVersion.object
        if "host_name" in kwargs:
            self.host_name = kwargs["host_name"]
            self.short_host_name = self.host_name.split(".")[0]
            if not self.host_name.count("."):
                # host_name is a short_host_name, clear host_name
                self.host_name = None
        elif "short_host_name" in kwargs:
            # deprecated
            self.host_name = None
            self.short_host_name = kwargs["short_host_name"]
        else:
            self.host_name = None
            self.short_host_name = kwargs.get("short_host_name", process_tools.get_machine_name())
        # list of ip-addresses for server
        self.ip_list = []
        # list of netdevice-idxs for server
        self.netdevice_idx_list = []
        # lookup table netdevice_idx -> list of ips
        self.netdevice_ip_lut = {}
        # lookup table ip -> netdevice_idx
        self.ip_netdevice_lut = {}
        # lookup table ip -> network identifier
        self.ip_identifier_lut = {}
        # lookup table netdev_pk -> netdev
        self.nd_lut = {}
        # lookup table network_identifier -> ip_list
        self.identifier_ip_lut = {}
        self.__fetch_network_info = kwargs.get("fetch_network_info", True)
        self.__network_info_fetched = False
        # self.set_hopcount_cache()
        self._check(**kwargs)

    def get_result(self):
        if self.multiple:
            return self._result
        else:
            # return result node for singular calls
            return list(self._result.values())[0]

    def _check(self, **kwargs):
        if self.multiple:
            self._result = {
                _enum: icswServerCheckResult(self, _enum) for _enum in self.__service_type_enum
            }
        else:
            if self.__service_type_enum:
                _key = self.__service_type_enum[0]
            else:
                # special mode, no service_type_enum was specified, node mode
                _key = None
            self._result = {
                _key: icswServerCheckResult(self, _key)
            }
        if self._vers_check():
            self._db_check(**kwargs)

    def _vers_check(self):
        if not self.__db_version_dict:
            # no database version found, stop service
            return False
        else:
            if self.__db_version_dict["database"] == self.__sys_version_dict["database"]:
                return True
            else:
                res_str = "Database version mismatch"
                (value.set_result(res_str) for value in self._result.values())
                return False

    def _db_check(self, **kwargs):
        if "device" in kwargs:
            # got device, no need to query
            self.device = kwargs["device"]
            if self.multiple:
                raise SyntaxError(
                    "db_check with set device and config only works for single checks"
                )
            list(self._result.values())[0].set_fields(
                config=kwargs["config"],
                effective_device=kwargs.get(
                    "effective_device",
                    kwargs["device"]
                ),
            )
        else:
            # clear config
            self.clear_results()
            try:
                # resolve host
                if self.host_name:
                    # search with full host name
                    self.device = device.all_enabled.prefetch_related(
                        "netdevice_set__net_ip_set__network__network_type"
                    ).select_related(
                        "domain_tree_node"
                    ).get(
                        Q(name=self.short_host_name) & Q(domain_tree_node__full_name=self.host_name.split(".", 1)[1])
                    )
                else:
                    # search with short host name
                    self.device = device.all_enabled.prefetch_related(
                        "netdevice_set__net_ip_set__network__network_type"
                    ).select_related(
                        "domain_tree_node"
                    ).get(
                        Q(name=self.short_host_name)
                    )
            except device.DoesNotExist:
                self.device = None
            else:
                if self.device:
                    # get config
                    if self.__service_type_enum:
                        _enum_lut = {
                            _enum.name: _enum for _enum in self.__service_type_enum
                        }
                        _enum_names = _enum_lut.keys()
                        _queries = [
                            (
                                True,
                                Q(config_service_enum__enum_name__in=_enum_names) &
                                Q(device_config__device=self.device)
                            ),
                            (
                                False,
                                Q(config_service_enum__enum_name__in=_enum_names) &
                                Q(device_config__device__is_meta_device=True) &
                                Q(device_config__device__device_group=self.device.device_group_id)
                            ),
                        ]
                    else:
                        # no service type enum specifed, take device (for node selection)
                        _queries = []
                    if len(_queries):
                        for _direct_device, _query in _queries:
                            _configs = config.objects.filter(
                                _query
                            ).select_related(
                                "config_service_enum"
                            )
                            for _config in _configs:
                                _enum = _enum_lut[_config.config_service_enum.enum_name]
                                _result = self._result[_enum]
                                if _result.config is None:
                                    # config is not already set
                                    _result.set_fields(
                                        config=_config,
                                    )
                                    # found
                                    if _direct_device:
                                        # direct device
                                        _result.set_fields(
                                            effective_device=self.device
                                        )
                                    else:
                                        # via meta device
                                        _result.set_fields(
                                            effective_device=device.all_enabled.select_related(
                                                "domain_tree_node"
                                            ).get(
                                                Q(device_group=self.device.device_group_id) &
                                                Q(is_meta_device=True)
                                            )
                                        )
                            if self.all_configs_set:
                                # all configs set, exit loop
                                # print("BRK")
                                break
                    else:
                        for _result in self._result.values():
                            _result.set_fields(
                                effective_device=self.device
                            )

        if self.__fetch_network_info:
            # fetch ip_info only if needed
            self._fetch_network_info(kwargs.get("dn_cache", None))
        for _result in self._result.values():
            if _result.config is not None:
                _result.set_srv_info(
                    "real" if self.device.pk == _result.effective_device.pk else "meta",
                    "hostname '{}'".format(self.short_host_name)
                )
        if not self.all_configs_set and self.device:
            # no direct config found, check for matching IP
            # we need at least a device to check
            # fetch ip_info
            self._fetch_network_info(kwargs.get("dn_cache", None))
            if self.__service_type_enum:
                # hmm ... ? for node selection not necessary
                self._db_check_ip(kwargs.get("dn_cache", None))
            # for _result in self._result.values():
            #    _result.set_result(
            #        "device {}".format(
            #            str(self.device),
            #        )
            #    )

    @property
    def all_configs_set(self):
        any_unset = any([_result.config is None for _result in self._result.values()])
        return not any_unset

    def clear_results(self):
        # clear result structures (set config and effective_device to None)
        for _result in self._result.values():
            _result.set_fields(
                config=None,
                effective_device=None,
            )

    # utility funcitions

    @property
    def simple_ip_list(self):
        return [cur_ip.ip for cur_ip in self.ip_list]

    def _fetch_network_info(self, dn_cache):

        # commented force_flag, FIXME
        if self.device is not None:
            if not self.__network_info_fetched:
                if dn_cache is not None and self.device.idx in dn_cache:
                    # copy from dn_cache
                    # print("+", dn_cache[self.device.idx])
                    self._set_network_dict(dn_cache[self.device.idx])
                else:
                    nw_type_lut = {
                        nwt.idx: nwt for nwt in network_type.objects.all()
                    }
                    for net_dev in self.device.netdevice_set.filter(
                        Q(enabled=True)
                    ).prefetch_related(
                        "net_ip_set__network__network__network_type"
                    ):
                        self.netdevice_idx_list.append(net_dev.pk)
                        self.netdevice_ip_lut[net_dev.pk] = []
                        self.nd_lut[net_dev.pk] = net_dev
                        for net_ip in net_dev.net_ip_set.all():
                            self.ip_list.append(net_ip)
                            self.netdevice_ip_lut[net_dev.pk].append(net_ip)
                            self.ip_netdevice_lut[net_ip.ip] = net_dev
                            nwt_id = nw_type_lut[net_ip.network.network_type_id].identifier
                            self.ip_identifier_lut[net_ip.ip] = nwt_id
                            self.identifier_ip_lut.setdefault(nwt_id, []).append(net_ip)
                    if dn_cache is not None:
                        # set fetched network_info in dn_cache
                        dn_cache[self.device.idx] = self._get_network_dict()
                        # print("*", dn_cache)
                self.__network_info_fetched = True

    def _set_network_dict(self, in_dict):
        # print("*", in_dict)
        for attr_name in [
            "netdevice_idx_list",
            "netdevice_ip_lut",
            "nd_lut",
            "ip_list",
            "ip_netdevice_lut",
            "ip_identifier_lut",
        ]:
            setattr(self, attr_name, in_dict[attr_name])

    def _get_network_dict(self):
        return {
            key: getattr(self, key) for key in [
                "netdevice_idx_list",
                "netdevice_ip_lut",
                "nd_lut",
                "ip_list",
                "ip_netdevice_lut",
                "ip_identifier_lut",
            ]
        }

    def _db_check_ip(self, dn_cache):
        # get local ip-addresses
        # my_ips = set(net_ip.objects.exclude(
        #    Q(network__network_type__identifier='l')
        # ).filter(
        #    Q(netdevice__device=self.device)
        # ).select_related(
        #    "netdevice", "network", "network__network_type"
        # ).values_list("ip", flat=True))
        ipv4_dict = {
            cur_if_name: [
                ip_tuple["addr"] for ip_tuple in value[netifaces.AF_INET]
            ] for cur_if_name, value in [
                (
                    if_name,
                    netifaces.ifaddresses(if_name)
                ) for if_name in netifaces.interfaces()
            ] if netifaces.AF_INET in value
        }
        my_ips = set(sum(list(ipv4_dict.values()), []))
        # check for virtual-device
        # get all real devices with the requested config, no meta-device handling possible
        _enum_lut = {
            _enum.name: _enum for _enum in self.__service_type_enum
            }
        _enum_names = _enum_lut.keys()
        # get a unique list of devices for which the requested services are related
        dev_list = device.all_enabled.select_related("domain_tree_node").filter(
            Q(device_config__config__config_service_enum__enum_name__in=_enum_names)
        ).values_list(
            "idx",
            "device_config__config__config_service_enum__enum_name"
        ).distinct()
        if not dev_list.count():
            # no device(s) found with IP and requested config
            return
        # find matching IP-adresses
        # reorder, gather same dev_idxs
        dev_ip_enum_lut = {}
        for dev_idx, enum_name in dev_list:
            dev_ip_enum_lut.setdefault(dev_idx, []).append(enum_name)
        for dev_idx, enum_list in dev_ip_enum_lut.items():
            if dn_cache is not None and dev_idx in dn_cache:
                # take ips from dn_cache, to be implemented ...
                # print("*", dn_cache[dev_idx])
                pass
            dev_ips = set(
                net_ip.objects.exclude(
                    Q(network__network_type__identifier='l')
                ).filter(
                    Q(netdevice__device=dev_idx)
                ).values_list(
                    "ip",
                    flat=True
                )
            )
            match_ips = my_ips & dev_ips
            if match_ips:
                # we dont change the local device attribute
                # self.clear_results()
                _configs = config.objects.filter(
                    Q(config_service_enum__enum_name__in=enum_list)
                ).select_related(
                    "config_service_enum"
                )
                for _config in _configs:
                    _enum = _enum_lut[_config.config_service_enum.enum_name]
                    _result = self._result[_enum]
                    if _result.config is None:
                        _result.set_fields(
                            config=_config,
                            effective_device=device.all_enabled.get(Q(idx=dev_idx)),
                        )
                        _result.set_srv_info(
                            "virtual",
                            "IP address '{}'".format(list(match_ips)[0])
                        )
                # self.short_host_name = cur_dev.name

    def get_route_to_other_devices(self, router_obj, dev_list, **kwargs):
        # check routing from this node to other devices
        # dev_list
        self._fetch_network_info(None)
        ip_list = net_ip.objects.filter(
            Q(netdevice__enabled=True) &
            Q(netdevice__device__in=dev_list)
        ).select_related(
            "netdevice",
            "network"
        ).values_list(
            "ip",
            "netdevice__device__idx",
            "network",
            "netdevice__idx",
            "network__network_type__identifier"
        )
        # print ip_list
        dev_dict = {
            dev.idx: {
                "nd_list": set(),
                "raw": [entry for entry in ip_list if entry[1] == dev.idx],
            } for dev in dev_list
        }
        for _ip, _dev_idx, _nw_idx, _nd_idx, _nw_id in ip_list:
            dev_dict[_dev_idx]["nd_list"].add(_nd_idx)
        res_dict = {
            dev_idx: [] for dev_idx in dev_dict.keys()
        }
        for dev_idx, dev in dev_dict.items():
            if self.netdevice_idx_list and dev["nd_list"]:
                all_pathes = router_obj.get_ndl_ndl_pathes(self.netdevice_idx_list, list(dev["nd_list"]), add_penalty=True, only_endpoints=True)
                _raw = dev["raw"]
                nd_ip_lut = {}
                ip_id_lut = {}
                for _entry in _raw:
                    nd_ip_lut.setdefault(_entry[3], []).append(_entry[0])
                    ip_id_lut[_entry[0]] = _entry[4]
                # routing list, common network identifiers
                c_ret_list = []
                # routing list, non-common network identifier
                nc_ret_list = []
                for penalty, s_nd_pk, d_nd_pk in all_pathes:
                    # dicts identifier -> ips
                    source_ip_lut, dest_ip_lut = ({}, {})
                    for s_ip in self.netdevice_ip_lut[s_nd_pk]:
                        source_ip_lut.setdefault(self.ip_identifier_lut[str(s_ip)], []).append(str(s_ip))
                    for d_ip in nd_ip_lut[d_nd_pk]:
                        dest_ip_lut.setdefault(ip_id_lut[str(d_ip)], []).append(str(d_ip))
                    # print source_ip_lut, dest_ip_lut
                    # common identifiers, ignore localhost
                    common_identifiers = (
                        set(
                            source_ip_lut.keys()
                        ) & set(
                            dest_ip_lut.keys()
                        )
                    ) - set(["l"])
                    if common_identifiers:
                        for act_id in common_identifiers:
                            add_actual = True
                            if add_actual:
                                c_ret_list.append(
                                    (
                                        penalty,
                                        act_id,
                                        (s_nd_pk, source_ip_lut[act_id]),
                                        (d_nd_pk, dest_ip_lut[act_id])
                                    )
                                )
                    else:
                        if kwargs.get("allow_route_to_other_networks", False):
                            for src_id in set(source_ip_lut.keys()) & {"p", "o"}:
                                for dst_id in set(dest_ip_lut.keys()) & {"p", "o"}:
                                    add_actual = True
                                    if add_actual:
                                        nc_ret_list.append(
                                            (
                                                penalty,
                                                dst_id,
                                                (s_nd_pk, source_ip_lut[src_id]),
                                                (d_nd_pk, dest_ip_lut[dst_id])
                                            )
                                        )
                r_list = sorted(c_ret_list) + sorted(nc_ret_list)
                if kwargs.get("global_sort_results", False):
                    r_list = sorted(r_list)
                if kwargs.get("prefer_production_net", False):
                    r_list = self.prefer_production_net(r_list)
                res_dict[dev_idx] = r_list
        return res_dict

    def get_route_to_other_device(self, router_obj, other, **kwargs):
        if "cache" in kwargs and self.device is not None and other.device is not None and (self.device.pk, other.device.pk) in kwargs["cache"]:
            return kwargs["cache"][(self.device.pk, other.device.pk)]
        filter_ip = kwargs.get("filter_ip", None)
        # at first fetch the network info if necessary
        self._fetch_network_info(None)
        other._fetch_network_info(None)
        # format of return list: value, network_id, (self.netdevice_idx, [list of self.ips]), (other.netdevice_idx, [list of other.ips])
        # routing list, common network identifiers
        c_ret_list = []
        # routing list, non-common network identifier
        nc_ret_list = []
        if self.netdevice_idx_list and other.netdevice_idx_list:
            # skip if any of both netdevice_idx_lists are empty
            # get peer_information
            all_pathes = router_obj.get_ndl_ndl_pathes(
                self.netdevice_idx_list,
                other.netdevice_idx_list,
                add_penalty=True,
                only_endpoints=True,
            )
            for penalty, s_nd_pk, d_nd_pk in all_pathes:
                # dicts identifier -> ips
                source_ip_lut, dest_ip_lut = ({}, {})
                for s_ip in self.netdevice_ip_lut[s_nd_pk]:
                    source_ip_lut.setdefault(self.ip_identifier_lut[str(s_ip)], []).append(str(s_ip))
                for d_ip in other.netdevice_ip_lut[d_nd_pk]:
                    dest_ip_lut.setdefault(other.ip_identifier_lut[str(d_ip)], []).append(str(d_ip))
                # common identifiers, ignore localhost
                common_identifiers = (
                    set(
                        source_ip_lut.keys()
                    ) & set(
                        dest_ip_lut.keys()
                    )
                ) - set(["l"])
                if common_identifiers:
                    for act_id in common_identifiers:
                        add_actual = True
                        if filter_ip:
                            if filter_ip not in source_ip_lut[act_id] and filter_ip not in dest_ip_lut[act_id]:
                                add_actual = False
                        if add_actual:
                            c_ret_list.append(
                                (
                                    penalty,
                                    act_id,
                                    (s_nd_pk, source_ip_lut[act_id]),
                                    (d_nd_pk, dest_ip_lut[act_id])
                                )
                            )
                else:
                    if kwargs.get("allow_route_to_other_networks", False):
                        for src_id in set(source_ip_lut.keys()) & {"p", "o"}:
                            for dst_id in set(dest_ip_lut.keys()) & {"p", "o"}:
                                add_actual = True
                                if filter_ip:
                                    if filter_ip not in source_ip_lut[src_id] and filter_ip not in dest_ip_lut[dst_id]:
                                        add_actual = False
                                if add_actual:
                                    nc_ret_list.append(
                                        (
                                            penalty,
                                            dst_id,
                                            (s_nd_pk, source_ip_lut[src_id]),
                                            (d_nd_pk, dest_ip_lut[dst_id])
                                        )
                                    )
        r_list = sorted(c_ret_list) + sorted(nc_ret_list)
        if kwargs.get("global_sort_results", False):
            r_list = sorted(r_list)
        if kwargs.get("prefer_production_net", False):
            r_list = self.prefer_production_net(r_list)
        if "cache" in kwargs and self.device is not None and other.device is not None:
            kwargs["cache"][(self.device.pk, other.device.pk)] = r_list
        return r_list

    def prefer_production_net(self, r_list):
        # puts production routes in front of the rest
        return [
            entry for entry in r_list if entry[1] in ["p"]
        ] + [
            entry for entry in r_list if entry[1] not in ["p"]
        ]

    # commented out, move to Result ?
    # def report(self):
    #     # print self.effective_device
    #     if self.effective_device:
    #         return "short_host_name is %s (idx %d), server_origin is %s, effective_device_idx is %d, config_idx is %d, info_str is \"%s\"" % (
    #             self.short_host_name,
    #             self.device.pk,
    #             self.server_origin,
    #             self.effective_device.pk,
    #             self.config.pk,
    #             self.server_info_str
    #         )
    #     else:
    #         return "short_host_name is %s (idx %d), server_origin is %s, info_str is \"%s\"" % (
    #             self.short_host_name,
    #             self.device.pk,
    #             self.server_origin,
    #             self.server_info_str
    #         )


class icswDeviceWithConfig(dict):
    def __init__(self, service_type_enum=None, dn_cache=None):
        """
        this is somehow orthogonal to icswServerCheck
        the dictionary values are lists of icswServerChecks
        :param service_type_enum:
        """
        dict.__init__(self)
        # service_type_enum may be None to get all defined servers (like the old %server% call)
        self.__service_type_enum = service_type_enum
        if dn_cache is not None:
            # device -> network info cache for caching netdevice / netip lookups
            self._dn_cache = dn_cache
        else:
            self._dn_cache = {}
        self._check()

    def _check(self):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        # locates devices with the given config_name
        # right now we are fetching a little bit too much ...
        if self.__service_type_enum is None:
            direct_list = device_config.objects.filter(
                Q(
                    **{
                        "config__config_service_enum__isnull": False,
                        "device__enabled": True,
                        "device__device_group__enabled": True,
                    }
                )
            )
        else:
            direct_list = device_config.objects.filter(
                Q(
                    **{
                        "config__config_service_enum__enum_name": self.__service_type_enum.name,
                        "device__enabled": True,
                        "device__device_group__enabled": True,
                    }
                )
            )
        _value_list = [
            "config__config_service_enum__enum_name",
            "config",
            "device__name",
            "device",
            "device__device_group",
            "device__is_meta_device",
        ]
        direct_list = direct_list.select_related(
            "config__config_service_enum",
            "device__device_group",
        ).values_list(
            *_value_list
        )
        exp_group = set(
            [
                cur_entry[4] for cur_entry in direct_list if cur_entry[5]
            ]
        )
        conf_pks = set(
            [
                cur_entry[1] for cur_entry in direct_list
            ]
        )
        # expand device groups
        group_dict, md_set, group_md_lut = ({}, set(), {})
        if exp_group:
            for group_dev in device.all_enabled.select_related(
                "domain_tree_node"
            ).filter(
                Q(device_group__in=exp_group)
            ).values_list(
                "name", "pk", "device_group", "is_meta_device"
            ):
                if not group_dev[3]:
                    group_dict.setdefault(group_dev[2], []).append(group_dev)
                else:
                    # lut: device_group -> md_device
                    group_md_lut[group_dev[2]] = group_dev[1]
                    md_set.add(group_dev[1])
        all_list = []
        for cur_entry in direct_list:
            if cur_entry[5]:
                all_list.extend(
                    [
                        (
                            cur_entry[0],
                            cur_entry[1],
                            g_list[0],
                            g_list[1],
                            g_list[2],
                            g_list[3],
                            "MD"
                        ) for g_list in group_dict[cur_entry[4]]
                    ]
                )
            else:
                all_list.append(cur_entry)
        dev_conf_dict = {}
        for cur_entry in all_list:
            dev_conf_dict.setdefault(
                tuple(cur_entry[2:6]),
                []
            ).append(
                (
                    cur_entry[0],
                    cur_entry[1],
                    cur_entry[5],
                    cur_entry[5]
                )
            )
        # we dont use complex prefetching here because we rely on our clever dn_cache
        dev_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.all_enabled.select_related(
                "domain_tree_node"
            ).filter(
                Q(pk__in=[key[1] for key in dev_conf_dict.keys()] + list(md_set))
            )
        }
        conf_dict = {
            cur_conf.pk: cur_conf for cur_conf in config.objects.filter(
                Q(pk__in=conf_pks)
            )
        }
        # device -> network info cache
        for dev_key, conf_list in dev_conf_dict.items():
            dev_name, dev_pk, devg_pk, _dev_type = dev_key
            for srvc_name, conf_pk, m_type, src_type in conf_list:
                # print "%s (%s/%s), %s" % (conf_name, m_type, src_type, dev_key[0])
                cur_srv_type = icswServiceEnum[srvc_name]
                cur_struct = icswServerCheck(
                    short_host_name=dev_name,
                    service_type_enum=cur_srv_type,
                    config=conf_dict[conf_pk],
                    device=dev_dict[dev_pk],
                    effective_device=dev_dict[dev_pk] if m_type == src_type else dev_dict[group_md_lut[devg_pk]],
                    dn_cache=self._dn_cache,
                )
                self.setdefault(cur_srv_type, []).append(cur_struct)
        # print(self._dn_cache)


def close_db_connection():
    from initat.cluster.backbone import db_tools
    db_tools.close_connection()


def _log_com(what, log_level=logging_tools.LOG_LEVEL_OK):
    print("[{:2d}] {}".format(log_level, what))


if __name__ == "__main__":
    ro = RouterObject(_log_com)
    # pprint.pprint(ro.get_clusters())
    print(len(ro.get_clusters()))
