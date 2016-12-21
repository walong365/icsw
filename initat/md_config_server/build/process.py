# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
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
""" build process for md-config-server """

from __future__ import unicode_literals, print_function

import os
import time

from django.db.models import Q
from lxml.builder import E

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, mon_contactgroup, network_type, user, \
    config, config_catalog, mon_host_dependency_templ, mon_host_dependency, mon_service_dependency, net_ip, \
    mon_check_command_special, mon_check_command, BackgroundJobState
from initat.md_config_server import special_commands, constants
from initat.md_config_server.config import global_config, MainConfig, MonAllCommands, \
    MonAllServiceGroups, MonAllTimePeriods, MonAllContacts, MonAllContactGroups, MonAllHostGroups, MonDirContainer, \
    MonDeviceTemplates, MonServiceTemplates, MonAllHostDependencies, build_safe_name, StructuredMonBaseConfig, \
    MON_VAR_IP_NAME
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.md_sync_server.mixins import VersionCheckMixin
from initat.tools import config_tools, logging_tools, server_mixins, server_command
from initat.tools.bgnotify import create_bg_job
from .ipc_comtool import IPCClientHandler
from ..config.build_cache import BuildCache, HostBuildCache
from ..constants import BuildModesEnum
from ..mixins import ImageMapMixin, DistanceMapMixin, NagVisMixin
from ..special_commands.struct import DynamicCheckMode


class BuildProcess(
    server_mixins.ICSWBaseProcess,
    VersionCheckMixin,
    ImageMapMixin,
    DistanceMapMixin,
    NagVisMixin,
):
    def process_init(self):
        # init CC, also re-init global-config
        self.CC.init(None, global_config)
        db_tools.close_connection()
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
        self.register_func("start_build", self._start_build)
        self.register_func("fetch_dyn_config", self._fetch_dyn_config)
        self.register_func("routing_fingerprint", self._routing_fingerprint)
        special_commands.dynamic_checks.link(self)

    def loop_post(self):
        self.log("build {} process exiting".format(self.name))
        self.CC.close()

    def get_mach_logger(self, mach_name):
        return logging_tools.get_logger(
            "{}.{}".format(
                global_config["LOG_NAME"],
                mach_name.replace(".", r"\."),
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True,
        )

    def _cleanup_db(self):
        # cleanup tasks for the database
        num_empty_mhd = mon_host_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None))
        num_empty_msd = mon_service_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None))
        if num_empty_mhd.count():
            self.log(
                "removing {}".format(
                    logging_tools.get_plural("empty mon_host_dependency", num_empty_mhd),
                )
            )
            mon_host_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).delete()
        if num_empty_msd:
            self.log(
                "removing {}".format(
                    logging_tools.get_plural("empty mon_service_dependency", num_empty_msd),
                )
            )
            mon_service_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).delete()

    def _check_for_snmp_container(self):
        try:
            _container = config.objects.get(Q(name="SNMP container"))
        except config.DoesNotExist:
            self.log("created SNMP container class")
            _container = config.objects.create(
                name="SNMP container",
                # system_config=True,
                server_config=True,
                config_catalog=config_catalog.objects.get(Q(system_catalog=True)),
                enabled=False,
                description="container for all SNMP checks",
            )
        _present_coms = set(_container.mon_check_command_set.all().values_list("name", flat=True))
        _specials = {
            "snmp {}".format(_special.name): _special for _special in mon_check_command_special.objects.all()
        }
        _new = set(
            [
                "snmp {}".format(_com.Meta.name) for _com in special_commands.special_snmp_general.SpecialSnmpGeneral(
                    self.log
                ).get_commands()
            ]
        )
        _to_create = set(_specials.keys()) & (_new - _present_coms)
        for _name in _to_create:
            _new_mcc = mon_check_command.objects.create(
                name=_name,
                description="auto created SNMP check entry",
                config=_container,
                mon_check_command_special=_specials[_name],
                command_line="/bin/true",
            )

    def _routing_fingerprint(self, *args, **kwargs):
        # called when process is a slave after the main process has determined the current routing generation
        self.router_obj = config_tools.RouterObject(self.log)
        self.routing_fingerprint = args[0]
        if self.routing_fingerprint == self.router_obj.fingerprint:
            self.log("routing_fingerprint is {}".format(self.routing_fingerprint))
        else:
            self.log(
                "routing_fingerprint {} doesn not match local fingerprint {}".format(
                    self.routing_fingerprint,
                    self.router_obj.fingerprint
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        build_cache = BuildCache(
            self.log,
            full_build=not self.single_build,
            routing_fingerprint=self.routing_fingerprint,
        )
        self.fingerprint_set(build_cache)

    def _fetch_dyn_config(self, *args, **kwargs):
        args = list(args)
        self.build_mode = args.pop(0)
        self.__gen_config = MainConfig(self, args.pop(0))
        self.srv_com = server_command.srv_command(source=args.pop(0))
        # print(self.srv_com.pretty_print())
        self.log("received fetch_dyn_config")
        self.single_build = True if len(args) > 0 else False
        # print("*", self.single_build, args)
        self.router_obj = config_tools.RouterObject(self.log)
        build_cache = BuildCache(
            self.log,
            full_build=True,
            router_obj=self.router_obj,
        )
        self.gc = global_config
        _bgj = create_bg_job(
            global_config["SERVER_IDX"],
            None,
            "fetch dynamic config",
            "manual start",
            None,
            state=BackgroundJobState.pending,
            # set timeout to 30 minutes for big installs
            timeout=30 * 60
        )

        gbc = build_cache
        gbc.background_job = _bgj
        self.fetch_dyn_configs(gbc, args)
        _bgj.set_state(BackgroundJobState.done)
        if self.single_build:
            self.srv_com.set_result(
                "run DynConfig on {}".format(
                    logging_tools.get_plural("host", len(args)),
                )
            )
            self.send_pool_message("remote_call_async_result", unicode(self.srv_com))
        self._exit_process()

    def fetch_dyn_configs(self, gbc, pk_list):
        start_time = time.time()
        cur_gc = self.__gen_config
        cur_gc.add_config(MonAllCommands(cur_gc))
        gbc.set_global_config(cur_gc, {}, False)
        ac_filter = Q(dynamic_checks=True) & Q(enabled=True) & Q(device_group__enabled=True)
        if pk_list:
            ac_filter &= Q(pk__in=pk_list)
        gbc.set_host_list(device.objects.exclude(Q(is_meta_device=True)).filter(
            ac_filter
        ).values_list(
            "pk", flat=True)
        )
        all_configs = self.get_all_configs(ac_filter)
        # import pprint
        # pprint.pprint(all_configs)
        fetch_list = []
        for host_pk in gbc.host_pks:
            host = gbc.get_host(host_pk)
            dev_variables, var_info = gbc.get_vars(host)
            # store
            host.dev_variables = dev_variables
            hbc = None
            if MON_VAR_IP_NAME not in dev_variables:
                self.log("No IP found for dyn reconfig of {}".format(unicode(host)), logging_tools.LOG_LEVEL_ERROR)
            else:
                # get config names
                conf_names = set(all_configs.get(host.full_name, []))
                # cluster config names
                cconf_names = set([_sc.mon_check_command.name for _sc in gbc.get_cluster("sc", host.pk)])
                # build lut
                conf_names = sorted(
                    [
                        cur_c["command_name"] for cur_c in cur_gc["command"].values() if not cur_c.is_event_handler and (
                            (
                                (cur_c.get_config() in conf_names) and (host.pk not in cur_c.exclude_devices)
                            ) or cur_c["command_name"] in cconf_names
                        )
                    ]
                )
                _added = False
                for conf_name in conf_names:
                    s_check = cur_gc["command"][conf_name]
                    if s_check.mccs_id:
                        if hbc is None:
                            # init
                            hbc = HostBuildCache(host)
                            # set IP for updates
                            hbc.ip = dev_variables[MON_VAR_IP_NAME]
                        _res = special_commands.dynamic_checks.handle(
                            gbc,
                            hbc,
                            cur_gc,
                            s_check,
                            DynamicCheckMode.fetch,
                        )
                        if _res.r_type == "fetch":
                            if not _added:
                                fetch_list.append(hbc)
                                _added = True
                            hbc.add_pending_fetch(_res.special_instance)
                            # print(unicode(_res))
            if hbc and not hbc.pending_fetch_calls:
                hbc.build_finished()
                glob_log_str = "df, device {:<48s}{}".format(
                    host.full_name[:48],
                    "*" if len(host.name) > 48 else " ",
                )
                self.flush_hbc_logs(hbc, glob_log_str)
            # print("*", host, dev_variables)
        if fetch_list:
            self.log(
                "{} in fetch_list for dynamic checks".format(
                    logging_tools.get_plural("device", len(fetch_list))
                )
            )
            client = IPCClientHandler(self)
            client.add_server(special_commands.DynamicCheckServer.collrelay)
            client.add_server(special_commands.DynamicCheckServer.snmp_relay)
            for hbc in fetch_list:
                client.register_hbc(hbc)
            client.loop()
            client.close()
            for hbc in fetch_list:
                hbc.build_finished()
                host = hbc.device
                glob_log_str = "df, device {:<48s}{}".format(
                    host.full_name[:48],
                    "*" if len(host.name) > 48 else " ",
                )
                self.flush_hbc_logs(hbc, glob_log_str)
        end_time = time.time()
        self.log("dyn_config run took {}".format(logging_tools.get_diff_time_str(end_time - start_time)))

    def _start_build(self, *args, **kwargs):
        args = list(args)
        self.build_mode = getattr(BuildModesEnum, args.pop(0))
        self.__gen_config = MainConfig(self, args.pop(0))
        self.version = args.pop(0)
        self.srv_com = server_command.srv_command(source=args.pop(0))
        self.single_build = True if len(args) > 0 else False
        self.host_list = list(args)
        if self.__gen_config.master:
            self.router_obj = config_tools.RouterObject(self.log)
            self.send_pool_message("build_step", "routing_ok", self.router_obj.fingerprint)
            self.routing_fingerprint = self.router_obj.fingerprint
            build_cache = BuildCache(
                self.log,
                full_build=not self.single_build,
                router_obj=self.router_obj,
            )
            if self.build_mode == BuildModesEnum.all_master:
                # from mixin
                # todo, remove, move to syncer
                self.VCM_check_md_version()
                self._cleanup_db()
                # check for SNMP container config
                self._check_for_snmp_container()
            self.fingerprint_set(build_cache)

    def fingerprint_set(self, build_cache):
        # fingerprint valid (either called directly or via routing_fingerprint command from control)
        # copy global_config
        self.gc = global_config
        hdep_from_topo = self.gc["USE_HOST_DEPENDENCIES"] and self.gc["HOST_DEPENDENCIES_FROM_TOPOLOGY"]
        if hdep_from_topo:
            host_deps = mon_host_dependency_templ.objects.all().order_by("-priority")
            if len(host_deps):
                self.mon_host_dep = host_deps[0]
            else:
                self.log("no mon_host_dependencies found", logging_tools.LOG_LEVEL_ERROR)
                hdep_from_topo = False
        self.log(
            "rebuild_config called, version is {:d}, mode is {}, hdep_from_topo is {}".format(
                self.version,
                self.build_mode,
                "enabled" if hdep_from_topo else "disabled",
            )
        )
        if self.build_mode in [BuildModesEnum.all_master, BuildModesEnum.some_master]:
            _bgj = create_bg_job(
                global_config["SERVER_IDX"],
                None,
                "build config",
                "config rebuild",
                None,
                state=BackgroundJobState.pending,
                # set timeout to 30 minutes for big installs
                timeout=30 * 60
            )
            # the version is controlled by control.py (to keep all slaves in sync)
            # print("*", self.version, int(time.time()))
            # if int(time.time()) > self.version:
            #     self.version = int(time.time())
            # else:
            #     self.version += 1
            self.log("config_version for full build is {:d}".format(self.version))
            self.send_pool_message("build_info", "start_build", self.version, self.build_mode.name, target="syncer")
        elif self.build_mode in [BuildModesEnum.sync_users_master]:
            self.send_pool_message("build_info", "start_build", self.version, self.build_mode.name, target="syncer")
            _bgj = None
        else:
            _bgj = None

        # fetch SNMP-stuff from cluster and initialise var cache
        self._create_general_config(self.build_mode, write_entries=self.build_mode not in [BuildModesEnum.some_check])
        bc_valid = self.__gen_config.is_valid
        if bc_valid:
            # get device templates
            dev_templates = MonDeviceTemplates(self)
            # get serivce templates
            serv_templates = MonServiceTemplates(self)
            if dev_templates.is_valid and serv_templates.is_valid:
                pass
            else:
                if not dev_templates.is_valid:
                    self.log("device templates are not valid", logging_tools.LOG_LEVEL_ERROR)
                if not serv_templates.is_valid:
                    self.log("service templates are not valid", logging_tools.LOG_LEVEL_ERROR)
                bc_valid = False
        if bc_valid:
            if self.build_mode == BuildModesEnum.some_check:
                # clean device and service entries
                for key in constants.SINGLE_BUILD_MAPS:
                    if key in self.__gen_config:
                        self.__gen_config[key].refresh(self.__gen_config)
            # hosts to build, not needed ?
            # total_hosts = self._get_number_of_hosts()
            if self.build_mode in [BuildModesEnum.all_master, BuildModesEnum.all_slave]:
                # build distance map
                cur_dmap, unreachable_pks, unreachable_names = self.DM_build_distance_map(
                    self.__gen_config.monitor_server,
                    self.router_obj
                )
                if unreachable_pks and not self.single_build:
                    self.log(
                        u"{}: {}".format(
                            logging_tools.get_plural("unroutable node", len(unreachable_names)),
                            u", ".join(sorted(unreachable_names)),
                        )
                    )
                self.send_pool_message("build_info", "unreachable_devices", len(unreachable_pks), target="syncer")
                if unreachable_pks:
                    for _urd in device.objects.filter(Q(pk__in=unreachable_pks)).select_related("domain_tree_node"):
                        self.send_pool_message("build_info", "unreachable_device", _urd.pk, unicode(_urd), unicode(_urd.device_group), target="syncer")
                    build_cache.feed_unreachable_pks(unreachable_pks)
            else:
                cur_dmap = {}
            cur_gc = self.__gen_config
            if self.build_mode in [BuildModesEnum.all_master, BuildModesEnum.sync_users_master, BuildModesEnum.sync_users_slave]:
                # recreate access files
                cur_gc.create_access_entries()

            if self.build_mode in [BuildModesEnum.sync_users_master, BuildModesEnum.sync_users_slave]:
                cur_gc.write_entries()
                # start syncing
                self.send_pool_message("build_info", "sync_slave", cur_gc.monitor_server.full_name, cur_gc.access_entry_files, target="syncer")
            else:
                # global build cache
                gbc = build_cache
                gbc.background_job = _bgj
                gbc.host_list = self.host_list
                gbc.dev_templates = dev_templates
                gbc.serv_templates = serv_templates
                gbc.single_build = self.single_build
                gbc.debug = self.gc["DEBUG"]
                # set global config and other global values
                gbc.set_global_config(cur_gc, cur_dmap, hdep_from_topo)
                self.send_pool_message("build_info", "start_config_build", cur_gc.monitor_server.full_name, target="syncer")
                self.create_all_host_configs(gbc)
                self.send_pool_message("build_info", "end_config_build", cur_gc.monitor_server.full_name, target="syncer")
                if self.build_mode in [BuildModesEnum.all_master, BuildModesEnum.all_slave, BuildModesEnum.some_master, BuildModesEnum.some_slave]:
                    # refresh implies _write_entries
                    cur_gc.refresh()
                    # write config to disk
                    cur_gc.write_entries()
                    # start syncing
                    self.send_pool_message("build_info", "sync_slave", cur_gc.monitor_server.full_name, target="syncer")
                del gbc
            if _bgj:
                _bgj.set_state(BackgroundJobState.done)
        if self.build_mode in [BuildModesEnum.all_master, BuildModesEnum.sync_users_master]:
            self.send_pool_message("build_info", "end_build", self.version, self.build_mode.name, target="syncer")
        if self.build_mode in [BuildModesEnum.some_check, BuildModesEnum.some_master]:
            cur_gc = self.__gen_config
            res_node = E.config(
                *sum(
                    [
                        cur_gc[key].get_xml() for key in constants.SINGLE_BUILD_MAPS
                    ],
                    []
                )
            )
            self.srv_com["result"] = res_node
            self.send_pool_message("remote_call_async_result", unicode(self.srv_com))
        self._exit_process()

    def _create_general_config(self, mode, write_entries=None):
        if write_entries is not None:
            prev_awc = self.__gen_config.allow_write_entries
            # set actual value
            self.__gen_config.allow_write_entries = write_entries
        start_time = time.time()
        self.IM_check_image_maps()
        self._create_gen_config_files(mode)
        end_time = time.time()
        if write_entries is not None:
            # restore to previous value
            self.__gen_config.allow_write_entries = prev_awc
        self.log(
            "creating the total general config took {}".format(
                logging_tools.get_diff_time_str(end_time - start_time)
            )
        )

    def _create_gen_config_files(self, mode):
        cur_gc = self.__gen_config
        # misc commands (sending of mails)
        cur_gc.add_config(MonAllCommands(cur_gc))
        # servicegroups
        cur_gc.add_config(MonAllServiceGroups(cur_gc))
        # timeperiods
        cur_gc.add_config(MonAllTimePeriods(cur_gc))
        # contacts
        cur_gc.add_config(MonAllContacts(cur_gc))
        # contactgroups
        cur_gc.add_config(MonAllContactGroups(cur_gc))
        # hostgroups
        cur_gc.add_config(MonAllHostGroups(cur_gc))
        # device dir
        cur_gc.add_config(MonDirContainer("device", full_build=mode in [BuildModesEnum.all_master, BuildModesEnum.all_slave]))
        # host_dependencies
        cur_gc.add_config(MonAllHostDependencies(cur_gc))
        cur_gc.dump_logs()

    def create_all_host_configs(self, gbc):
        start_time = time.time()
        # get contacts with access to all devices
        _uo = user.objects
        all_access = list(
            [
                cur_u.login for cur_u in _uo.filter(
                    Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)
                ) if cur_u.has_perm("backbone.device.all_devices")
            ]
        )
        self.log("users with access to all devices: {}".format(", ".join(sorted(all_access))))
        cur_gc = gbc.global_config
        # get ext_hosts stuff
        gbc.ng_ext_hosts = self.IM_get_mon_ext_hosts()
        # check_hosts
        if gbc.host_list:
            # not beautiful but working
            pk_list = []
            for full_h_name in gbc.host_list:
                try:
                    if full_h_name.count("."):
                        found_dev = device.objects.get(Q(name=full_h_name.split(".")[0]) & Q(domain_tree_node__full_name=full_h_name.split(".", 1)[1]))
                    else:
                        found_dev = device.objects.get(Q(name=full_h_name))
                except device.DoesNotExist:
                    pass
                except device.MultipleObjectsReturned:
                    self.log("multiple objects returned for host_name '{}'".format(full_h_name), logging_tools.LOG_LEVEL_ERROR)
                else:
                    pk_list.append(found_dev.pk)
            h_filter = Q(pk__in=pk_list)
        else:
            h_filter = Q()
        # filter for all configs, wider than the h_filter
        ac_filter = Q()
        # add master/slave related filters
        if cur_gc.master:
            # need all devices for master
            pass
        else:
            h_filter &= Q(monitor_server=cur_gc.monitor_server)
            ac_filter &= Q(monitor_server=cur_gc.monitor_server)
        if not gbc.single_build:
            h_filter &= Q(enabled=True) & Q(device_group__enabled=True)
            ac_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        gbc.set_host_list(device.objects.exclude(Q(is_meta_device=True)).filter(
            h_filter
        ).values_list(
            "pk", flat=True)
        )
        all_configs = self.get_all_configs(ac_filter)
        # get config variables
        if not cur_gc["contactgroup"].keys():
            self.log(
                "no contact group defined",
                logging_tools.LOG_LEVEL_ERROR
            )
            return
        first_contactgroup_name = cur_gc["contactgroup"][cur_gc["contactgroup"].keys()[0]].name
        contact_group_dict = {}
        # get contact groups
        if gbc.host_list:
            host_info_str = logging_tools.get_plural("host", len(gbc.host_list))
            ct_groups = mon_contactgroup.objects.filter(Q(device_groups__device__name__in=gbc.host_list))
        else:
            host_info_str = "all"
            ct_groups = mon_contactgroup.objects.all()
        for ct_group in ct_groups.prefetch_related("device_groups", "device_groups__device"):
            if ct_group.pk in cur_gc["contactgroup"]:
                pass  # cg_name = cur_gc["contactgroup"][ct_group.pk].name
            else:
                self.log(
                    "contagroup_idx {} for device {} not found, using first from contactgroups ({})".format(
                        unicode(ct_group),
                        ct_group.name,
                        first_contactgroup_name,
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                # cg_name = first_contactgroup_name
            for g_devg in ct_group.device_groups.all().prefetch_related("device_group", "device_group__domain_tree_node"):
                for g_dev in g_devg.device_group.all():
                    contact_group_dict.setdefault(g_dev.full_name, []).append(ct_group.name)
        # get valid and invalid network types
        valid_nwt_list = set(network_type.objects.filter(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        _invalid_nwt_list = set(network_type.objects.exclude(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        for n_i in net_ip.objects.all().select_related("network__network_type", "netdevice", "domain_tree_node"):
            n_t = n_i.network.network_type.identifier
            n_d = n_i.netdevice.pk
            d_pk = n_i.netdevice.device_id
            if n_i.domain_tree_node_id:
                dom_name = n_i.domain_tree_node.full_name
            else:
                dom_name = ""
            # print n_i, n_t, n_d, d_pk, dom_name
            if d_pk in gbc.host_pks:
                cur_host = gbc.get_host(d_pk)
                # populate valid_ips and invalid_ips
                getattr(cur_host, "valid_ips" if n_t in valid_nwt_list else "invalid_ips").setdefault(n_d, []).append((n_i, dom_name))
        host_nc = cur_gc["device"]
        # delete host if already present in host_table
        host_names = []
        for host_pk in gbc.host_pks:
            host = gbc.get_host(host_pk)
            host_names.append((host.full_name, host))
            if host.full_name in host_nc:
                # now very simple
                del host_nc[host.full_name]
        # caching object
        # build lookup-table
        self.send_pool_message("build_info", "device_count", cur_gc.monitor_server.full_name, len(host_names), target="syncer")
        nagvis_maps = set()
        for host_name, host in sorted(host_names):
            self.create_single_host_config(
                gbc,
                host,
                all_access,
                contact_group_dict,
                all_configs,
                nagvis_maps,
            )
        p_dict = self.parenting_run(gbc)
        if cur_gc.master and not gbc.single_build:
            if gbc.hdep_from_topo:
                # import pprint
                # pprint.pprint(p_dict)
                for parent, clients in p_dict.iteritems():
                    new_hd = StructuredMonBaseConfig("hostdependency", "")
                    new_hd["dependent_host_name"] = clients
                    new_hd["host_name"] = parent
                    new_hd["dependency_period"] = self.mon_host_dep.dependency_period.name
                    new_hd["execution_failure_criteria"] = self.mon_host_dep.execution_failure_criteria
                    new_hd["notification_failure_criteria"] = self.mon_host_dep.notification_failure_criteria
                    new_hd["inherits_parent"] = "1" if self.mon_host_dep.inherits_parent else "0"
                    cur_gc["hostdependency"].add_object(new_hd)
            self.log("created {}".format(logging_tools.get_plural("nagvis map", len(nagvis_maps))))
            # nagvis handling
            nagvis_map_dir = os.path.join(self.gc["NAGVIS_DIR"], "etc", "maps")
            if os.path.isdir(nagvis_map_dir):
                self.NV_store_nagvis_maps(nagvis_map_dir, nagvis_maps)
            cache_dir = os.path.join(self.gc["NAGVIS_DIR"], "var")
            if os.path.isdir(cache_dir):
                self.NV_clear_cache_dirs(cache_dir)
        end_time = time.time()
        self.log(
            "created configs for {} hosts in {}".format(
                host_info_str,
                logging_tools.get_diff_time_str(end_time - start_time),
            )
        )

    def get_all_configs(self, ac_filter):
        meta_devices = {
            md.device_group.pk: md for md in device.objects.filter(
                Q(is_meta_device=True)
            ).prefetch_related(
                "device_config_set",
                "device_config_set__config"
            ).select_related("device_group")
        }
        all_configs = {}
        for cur_dev in device.objects.filter(
            ac_filter
        ).select_related(
            "domain_tree_node"
        ).prefetch_related(
            "device_config_set",
            "device_config_set__config"
        ):
            loc_config = [cur_dc.config.name for cur_dc in cur_dev.device_config_set.all()]
            if cur_dev.device_group_id in meta_devices:
                loc_config.extend([cur_dc.config.name for cur_dc in meta_devices[cur_dev.device_group_id].device_config_set.all()])
            all_configs[cur_dev.full_name] = loc_config
        return all_configs

    def parenting_run(self, gbc):
        s_time = time.time()
        cur_gc = gbc.global_config
        self.log("start parenting run")
        host_nc = cur_gc["device"]
        p_dict = {}
        # host_uuids = set([host_val.uuid for host_val in all_hosts_dict.itervalues() if host_val.full_name in host_names])
        _p_ok, _p_failed = (0, 0)
        d_map = gbc.cur_dmap
        host_names = host_nc.keys()
        for host_name in sorted(host_names):
            host = host_nc[host_name].object_list[0]
            if "possible_parents" in host and not gbc.single_build:
                # parent list
                parent_list = set()
                # check for nagvis_maps
                local_nagvis_maps = []
                p_parents = host["possible_parents"]
                for _p_val, _nd_val, p_list in p_parents:
                    # skip first host (is self)
                    host_pk = p_list[0]
                    for parent_idx in p_list[1:]:
                        if parent_idx in d_map:
                            if d_map[host_pk] > d_map[parent_idx]:
                                parent = gbc.get_host(parent_idx).full_name
                                if parent in host_names and parent != host.name:
                                    parent_list.add(parent)
                                    # exit inner loop
                                    break
                            else:
                                # exit inner loop
                                break
                        else:
                            self.log("parent_idx {:d} not in distance map, routing cache too old?".format(parent_idx), logging_tools.LOG_LEVEL_ERROR)
                    if "_nagvis_map" not in host:
                        # loop again to scan for nagvis_map
                        for parent_idx in p_list[1:]:
                            if parent_idx in d_map:
                                if d_map[host_pk] > d_map[parent_idx]:
                                    parent = gbc.get_host(parent_idx).full_name
                                    if parent in host_names and parent != host.name:
                                        if "_nagvis_map" in host_nc[parent].object_list[0]:
                                            local_nagvis_maps.append(host_nc[parent].object_list[0]["_nagvis_map"])
                            else:
                                self.log("parent_idx {:d} not in distance map, routing cache too old?".format(parent_idx), logging_tools.LOG_LEVEL_ERROR)
                if "_nagvis_map" not in host and local_nagvis_maps:
                    host["_nagvis_map"] = local_nagvis_maps[0]
                if parent_list:
                    host["parents"] = list(parent_list)
                    for cur_parent in parent_list:
                        p_dict.setdefault(cur_parent, []).append(host_name)
                    _p_ok += 1
                    if gbc.debug:
                        self.log("Setting parent of '{}' to {}".format(host_name, ", ".join(parent_list)), logging_tools.LOG_LEVEL_OK)
                else:
                    _p_failed += 1
                    self.log("Parenting problem for '{}', {:d} traces found".format(host_name, len(p_parents)), logging_tools.LOG_LEVEL_WARN)
                    if gbc.debug:
                        p_parents = host["possible_parents"]
                        for t_num, (_p_val, _nd_val, p_list) in enumerate(p_parents):
                            host_pk = p_list[0]
                            self.log(
                                "  trace {:3d}, distance is {:3d}, {}".format(
                                    t_num + 1,
                                    d_map[host_pk],
                                    logging_tools.get_plural("entry", len(p_list) - 1),
                                )
                            )
                            for parent_idx in p_list[1:]:
                                parent = gbc.get_host(parent_idx).full_name
                                self.log(
                                    "    {:>30s} (distance is {:3d}, in config: {})".format(
                                        unicode(parent),
                                        d_map[parent_idx],
                                        parent in host_names,
                                    )
                                )
            if "possible_parents" in host:
                del host["possible_parents"]
        e_time = time.time()
        self.log(
            "end parenting run in {}, {:d} ok, {:d} failed".format(
                logging_tools.get_diff_time_str(e_time - s_time),
                _p_ok,
                _p_failed,
            )
        )
        return p_dict

    def create_single_host_config(
        self,
        gbc,
        host,
        all_access,
        contact_group_dict,
        all_configs,
        nagvis_maps,
    ):
        hbc = HostBuildCache(host)
        cur_gc = gbc.global_config
        # build safe names
        self.__safe_cc_name = global_config["SAFE_CC_NAME"]
        # set some vars
        if cur_gc.master:
            if host.monitor_server_id and host.monitor_server_id != cur_gc.monitor_server.pk:
                hbc.host_is_actively_checked = False
            else:
                hbc.host_is_actively_checked = True
        else:
            hbc.host_is_actively_checked = True
        hbc.log(
            "-------- {} ---------".format(
                "master" if cur_gc.master else "slave {}".format(cur_gc.slave_name)
            ),
        )
        hbc.log("Starting build of config", logging_tools.LOG_LEVEL_OK)
        if host.valid_ips:
            net_devices = host.valid_ips
        elif host.invalid_ips:
            hbc.log(
                "Device {} has no valid netdevices associated, using invalid ones...".format(
                    host.full_name
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            net_devices = host.invalid_ips
        else:
            hbc.log(
                "Device {} has no netdevices associated, skipping...".format(
                    host.full_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            net_devices = {}
        use_host_deps, use_service_deps = (
            self.gc["USE_HOST_DEPENDENCIES"],
            self.gc["USE_SERVICE_DEPENDENCIES"],
        )
        if net_devices:
            # print mni_str_s, mni_str_d, dev_str_s, dev_str_d
            # get correct netdevice for host
            valid_ips, traces = self._get_target_ip_info(gbc, hbc, net_devices)
            act_def_dev = gbc.dev_templates[host.mon_device_templ_id or 0]
            if gbc.single_build:
                if not valid_ips:
                    valid_ips = [(net_ip(ip="0.0.0.0"), host.full_name)]
                    hbc.log("no ips found using {} as dummy IP".format(str(valid_ips)))
            else:
                if (len(valid_ips) > 0) != host.reachable:
                    hbc.log(
                        "reachable flag {} for host {} differs from valid_ips {}".format(
                            str(host.reachable),
                            unicode(host),
                            str(valid_ips),
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL,
                    )
            if valid_ips and act_def_dev:
                host.domain_names = [cur_ip[1] for cur_ip in valid_ips if cur_ip[1]]
                valid_ip = valid_ips[0][0]
                host.valid_ip = valid_ip
                if cur_gc.master:
                    # only store IP on master (needed for dyn reconfig)
                    gbc.set_variable(hbc.device, MON_VAR_IP_NAME, host.valid_ip.ip)
                hbc.log(
                    "Found {} for host {} : {}, mon_resolve_name is {}, using {}".format(
                        logging_tools.get_plural("target ip", len(valid_ips)),
                        host.full_name,
                        ", ".join(["{}{}".format(cur_ip, " (.{})".format(dom_name) if dom_name else "") for cur_ip, dom_name in valid_ips]),
                        str(host.mon_resolve_name),
                        unicode(host.valid_ip)
                    )
                )
                if act_def_dev.mon_service_templ_id not in gbc.serv_templates:
                    self.log("Default service_template not found in service_templates", logging_tools.LOG_LEVEL_WARN)
                else:
                    act_def_serv = gbc.serv_templates[act_def_dev.mon_service_templ_id]
                    # tricky part: check the actual service_template for the various services
                    hbc.log(
                        "Using default device_template '{}' and service_template '{}' for host {}".format(
                            act_def_dev.name,
                            act_def_serv.name,
                            host.full_name,
                        )
                    )
                    # get device variables
                    dev_variables, var_info = gbc.get_vars(host)
                    # store
                    host.dev_variables = dev_variables
                    hbc.log(
                        "device has {} ({})".format(
                            logging_tools.get_plural("device_variable", len(host.dev_variables.keys())),
                            ", ".join(
                                [
                                    "{}: {:d}".format(key, var_info[key]) for key in ["d", "g", "c"]
                                ]
                            ),
                        )
                    )
                    # now we have the device- and service template
                    # list of all MonBaseConfigs for given host, first one is always the host part
                    # host_config_list = MonFileContainer(host.full_name)
                    act_host = StructuredMonBaseConfig("host", host.full_name)
                    hbc.set_device_file(act_host)
                    act_host["host_name"] = host.full_name
                    act_host["display_name"] = host.full_name
                    # action url
                    if self.gc["ENABLE_COLLECTD"]:
                        act_host["process_perf_data"] = 1 if host.enable_perfdata else 0
                    # always set action_url, to be fixed, FIXME, TODO
                    # act_host["action_url"] = reverse("device:device_info", kwargs={"device_pk": host.pk, "mode": "rrd"})
                    act_host["_device_pk"] = host.pk
                    if global_config["USE_ONLY_ALIAS_FOR_ALIAS"]:
                        act_host["alias"] = host.alias or host.name
                    else:
                        act_host["alias"] = sorted(
                            list(
                                set(
                                    [
                                        entry for entry in [
                                            host.alias, host.name, host.full_name
                                        ] + [
                                            u"{}.{}".format(
                                                host.name, dom_name
                                            ) for dom_name in host.domain_names
                                        ] if entry.strip()
                                    ]
                                )
                            )
                        )
                    if host.mon_resolve_name:
                        act_host["address"] = host.valid_ip.ip
                    else:
                        v_ip = host.valid_ip
                        if v_ip.alias and v_ip.alias_excl:
                            act_host["address"] = "{}.{}".format(v_ip.alias, v_ip.domain_tree_node.full_name)
                        else:
                            act_host["address"] = host.full_name
                    if traces and len(traces[0][2]) > 1:
                        act_host["possible_parents"] = traces
                    act_host["retain_status_information"] = 1 if self.gc["RETAIN_HOST_STATUS"] else 0
                    act_host["max_check_attempts"] = act_def_dev.max_attempts
                    act_host["retry_interval"] = act_def_dev.retry_interval
                    act_host["check_interval"] = act_def_dev.check_interval
                    act_host["notification_interval"] = act_def_dev.ninterval
                    act_host["_uuid"] = host.uuid
                    act_host["check_period"] = cur_gc["timeperiod"][act_def_dev.mon_period_id].name
                    act_host["notification_period"] = cur_gc["timeperiod"][act_def_dev.not_period_id].name
                    # removed because this line screws active / passive checks
                    # act_host["checks_enabled"] = 1
                    # only allow active checks if this the active monitor master, very important for anovis
                    act_host["active_checks_enabled"] = 1 if hbc.host_is_actively_checked else 0
                    # we always allow passive checks
                    act_host["passive_checks_enabled"] = 1
                    # act_host["{}_checks_enabled".format("active" if checks_are_active else "passive")] = 1
                    # act_host["{}_checks_enabled".format("passive" if checks_are_active else "active")] = 0
                    act_host["flap_detection_enabled"] = 1 if (host.flap_detection_enabled and act_def_dev.flap_detection_enabled) else 0
                    if host.flap_detection_enabled and act_def_dev.flap_detection_enabled:
                        # add flap fields
                        act_host["low_flap_threshold"] = act_def_dev.low_flap_threshold
                        act_host["high_flap_threshold"] = act_def_dev.high_flap_threshold
                        n_field = []
                        for short, f_name in [("o", "up"), ("d", "down"), ("u", "unreachable")]:
                            if getattr(act_def_dev, "flap_detect_{}".format(f_name)):
                                n_field.append(short)
                        if not n_field:
                            n_field.append("o")
                        act_host["flap_detection_options"] = n_field
                    # if checks_are_active and not cur_gc.master:
                    #    # trace changes
                    act_host["obsess_over_host"] = 1
                    hbc.contact_groups = set(contact_group_dict.get(host.full_name, []))
                    act_host["contact_groups"] = list(hbc.contact_groups) if hbc.contact_groups else self.gc["NONE_CONTACT_GROUP"]
                    c_list = [entry for entry in all_access] + gbc.get_device_group_users(host.device_group_id)
                    if c_list:
                        act_host["contacts"] = c_list
                    hbc.log(
                        "contact groups for host: {}".format(
                            ", ".join(sorted(hbc.contact_groups)) or "none"
                        )
                    )
                    if host.monitor_checks or gbc.single_build:
                        if host.valid_ip.ip == "0.0.0.0":
                            hbc.log(
                                "IP address is '{}', host is assumed to be always up".format(unicode(host.valid_ip))
                            )
                            act_host["check_command"] = "check-host-ok"
                        else:
                            if act_def_dev.host_check_command:
                                if hbc.host_is_actively_checked:
                                    act_host["check_command"] = act_def_dev.host_check_command.name
                                else:
                                    hbc.log("disabling host check_command (passive)")
                            else:
                                self.log("dev_template has no host_check_command set", logging_tools.LOG_LEVEL_ERROR)
                        # check for nagvis map
                        if host.automap_root_nagvis and cur_gc.master:
                            # with or without .cfg ? full path ?
                            self.NV_add_nagvis_info(act_host, host, nagvis_maps)
                        # check for notification options
                        not_a = []
                        for what, shortcut in [
                            ("nrecovery", "r"),
                            ("ndown", "d"),
                            ("nunreachable", "u"),
                            ("nflapping", "f"),
                            ("nplanned_downtime", "s")
                        ]:
                            if getattr(act_def_dev, what):
                                not_a.append(shortcut)
                        if not not_a:
                            not_a.append("n")
                        act_host["notification_options"] = not_a
                        # check for hostextinfo
                        if host.mon_ext_host_id and host.mon_ext_host_id in gbc.ng_ext_hosts:
                            for key in ["icon_image", "statusmap_image"]:
                                act_host[key] = getattr(gbc.ng_ext_hosts[host.mon_ext_host_id], key)
                        # clear host from servicegroups
                        cur_gc["servicegroup"].clear_host(host.full_name)
                        # get check_commands and templates
                        conf_names = set(all_configs.get(host.full_name, []))
                        # cluster config names
                        cconf_names = set([_sc.mon_check_command.name for _sc in gbc.get_cluster("sc", host.pk)])
                        # build lut
                        conf_names = sorted(
                            [
                                cur_c["command_name"] for cur_c in cur_gc["command"].values() if not cur_c.is_event_handler and (
                                    (
                                        (cur_c.get_config() in conf_names) and (host.pk not in cur_c.exclude_devices)
                                    ) or cur_c["command_name"] in cconf_names
                                )
                            ]
                        )
                        # list of already used checks
                        used_checks = set()
                        # print "*", conf_names
                        # print gbc.get_vars(host)
                        for conf_name in conf_names:
                            self.add_host_config(
                                gbc, hbc,
                                conf_name, used_checks,
                                act_def_serv,
                            )
                        # add cluster checks
                        mhc_checks = gbc.get_cluster("hc", host.pk)
                        if len(mhc_checks):
                            hbc.host_config_list.extend(self.add_host_cluster_checks(gbc, hbc, mhc_checks, act_def_serv))
                        # add cluster service checks
                        msc_checks = gbc.get_cluster("sc", host.pk)
                        if len(msc_checks):
                            hbc.host_config_list.extend(self.add_service_cluster_checks(gbc, hbc, msc_checks, act_def_serv))
                        # add host dependencies
                        if use_host_deps:
                            for h_dep in gbc.get_dependencies("hd", host.pk):
                                # check reachability
                                _unreachable = [
                                    gbc.get_host(_dev_pk) for _dev_pk in h_dep.devices_list + h_dep.master_list if not gbc.get_host(_dev_pk).reachable
                                ]
                                if _unreachable:
                                    hbc.log(
                                        "cannot create host dependency, {} unreachable: {}".format(
                                            logging_tools.get_plural("device", len(_unreachable)),
                                            ", ".join(sorted([unicode(_dev) for _dev in _unreachable])),
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR,
                                    )
                                else:
                                    act_host_dep = StructuredMonBaseConfig("hostdependency", "")
                                    _list = [gbc.get_host(dev_pk).full_name for dev_pk in h_dep.devices_list]
                                    _dep_list = [gbc.get_host(dev_pk).full_name for dev_pk in h_dep.master_list]
                                    if _list and _dep_list:
                                        if set(_list) & set(_dep_list):
                                            hbc.log(
                                                "host_name and dependent_host_name share some hosts: {}".format(
                                                    ", ".join(sorted(list(set(_list) & set(_dep_list))))
                                                ),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                        else:
                                            act_host_dep["host_name"] = _list
                                            act_host_dep["dependent_host_name"] = _dep_list
                                            h_dep.feed_config(act_host_dep)
                                            hbc.host_config_list.append(act_host_dep)
                                    else:
                                        hbc.log(
                                            "empty list or dependency_list for hostdependency.(host_name|dependency_name)",
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
                        # add service dependencies
                        if use_service_deps:
                            for s_dep in gbc.get_dependencies("sd", host.pk):
                                act_service_dep = StructuredMonBaseConfig("servicedependency", "")
                                if s_dep.mon_service_cluster_id:
                                    # check reachability
                                    _unreachable = [gbc.get_host(_dev_pk) for _dev_pk in s_dep.master_list if not gbc.get_host(_dev_pk).reachable]
                                    if _unreachable:
                                        hbc.log(
                                            "cannot create host dependency, {} unreachable: {}".format(
                                                logging_tools.get_plural("device", len(_unreachable)),
                                                ", ".join(sorted([unicode(_dev) for _dev in _unreachable])),
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR,
                                        )
                                    else:
                                        all_ok = True
                                        for d_host in s_dep.master_list:
                                            all_ok &= self._check_for_config(
                                                hbc,
                                                "child",
                                                all_configs,
                                                gbc.mcc_lut,
                                                gbc.mcc_lut_2,
                                                gbc.get_host(d_host),
                                                s_dep.dependent_mon_check_command_id
                                            )
                                        if all_ok:
                                            act_service_dep["dependent_service_description"] = host_service_id_util.create_host_service_description(
                                                dev_pk,
                                                gbc.mcc_lut_3[s_dep.dependent_mon_check_command_id],
                                                gbc.mcc_lut[s_dep.dependent_mon_check_command_id][1],
                                            )
                                            sc_check = cur_gc["command"]["check_service_cluster"]
                                            # FIXME, my_co.mcc_lut[...][1] should be mapped to check_command().get_description()
                                            act_service_dep["service_description"] = "{} / {}".format(
                                                sc_check.get_description(),
                                                gbc.mcc_lut[s_dep.mon_service_cluster.mon_check_command_id][1]
                                            )
                                            act_service_dep["host_name"] = gbc.get_host(s_dep.mon_service_cluster.main_device_id).full_name
                                            act_service_dep["dependent_host_name"] = [gbc.get_host(dev_pk).full_name for cur_dev in s_dep.master_list]
                                            s_dep.feed_config(act_service_dep)
                                            hbc.host_config_list.append(act_service_dep)
                                        else:
                                            hbc.log("cannot add cluster_service_dependency", logging_tools.LOG_LEVEL_ERROR)
                                else:
                                    # check reachability
                                    _unreachable = [
                                        gbc.get_host(_dev_pk) for _dev_pk in s_dep.master_list + s_dep.devices_list if not gbc.get_host(_dev_pk).reachable
                                    ]
                                    if _unreachable:
                                        hbc.log(
                                            "cannot create host dependency, {} unrechable: {}".format(
                                                logging_tools.get_plural("device", len(_unreachable)),
                                                ", ".join(sorted([unicode(_dev) for _dev in _unreachable])),
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR,
                                        )
                                    else:
                                        all_ok = True
                                        for p_host in s_dep.devices_list:
                                            all_ok &= self._check_for_config(
                                                hbc,
                                                "parent",
                                                all_configs,
                                                gbc.mcc_lut,
                                                gbc.mcc_lut_2,
                                                gbc.get_host(p_host),
                                                s_dep.mon_check_command_id
                                            )
                                        for d_host in s_dep.master_list:
                                            all_ok &= self._check_for_config(
                                                hbc,
                                                "child",
                                                all_configs,
                                                gbc.mcc_lut,
                                                gbc.mcc_lut_2,
                                                gbc.get_host(d_host),
                                                s_dep.dependent_mon_check_command_id
                                            )
                                        if all_ok:
                                            # FIXME, TODO, must unroll loops
                                            # act_service_dep["dependent_service_description"] = gbc.mcc_lut[s_dep.dependent_mon_check_command_id][1]
                                            act_service_dep["dependent_service_description"] = [
                                                host_service_id_util.create_host_service_description(
                                                    dev_pk,
                                                    gbc.mcc_lut_3[s_dep.dependent_mon_check_command_id],
                                                    gbc.mcc_lut[s_dep.dependent_mon_check_command_id][1],
                                                ) for dev_pk in s_dep.master_list
                                            ]
                                            # act_service_dep["service_description"] = gbc.mcc_lut[s_dep.mon_check_command_id][1]
                                            act_service_dep["service_description"] = [
                                                host_service_id_util.create_host_service_description(
                                                    dev_pk,
                                                    gbc.mcc_lut_3[s_dep.mon_check_command_id],
                                                    gbc.mcc_lut[s_dep.mon_check_command_id][1],
                                                ) for dev_pk in s_dep.devices_list
                                            ]
                                            act_service_dep["host_name"] = [gbc.get_host(dev_pk).full_name for dev_pk in s_dep.devices_list]
                                            act_service_dep["dependent_host_name"] = [gbc.get_host(dev_pk).full_name for dev_pk in s_dep.master_list]
                                            s_dep.feed_config(act_service_dep)
                                            hbc.host_config_list.append(act_service_dep)
                                        else:
                                            hbc.log("cannot add service_dependency", logging_tools.LOG_LEVEL_ERROR)
                        cur_gc["device"].add_entry(hbc.host_config_list, host)
                    else:
                        hbc.log("Host {} is disabled".format(host.full_name))
            else:
                hbc.log(
                    "No valid IPs found or no default_device_template found",
                    logging_tools.LOG_LEVEL_ERROR
                )

        hbc.build_finished()
        glob_log_str = "cb, device {:<48s}{} ({}), d={:>3s}".format(
            host.full_name[:48],
            "*" if len(host.name) > 48 else " ",
            "a" if hbc.host_is_actively_checked else "p",
            "{:3d}".format(gbc.cur_dmap[host.pk]) if gbc.cur_dmap.get(host.pk) >= 0 else "---",
        )
        self.flush_hbc_logs(hbc, glob_log_str)
        hbc.store_to_db()

    def flush_hbc_logs(self, hbc, glob_log_str):
        info_str = hbc.info_str
        hbc.log(info_str)
        self.log("{}, {}".format(glob_log_str, info_str))
        if hbc.write_logs or self.gc["DEBUG"]:
            _mach_logger = self.get_mach_logger(hbc.device.full_name)
            hbc.flush_logs(_mach_logger)
            _mach_logger.close()
            del _mach_logger

    def add_host_cluster_checks(self, gbc, hbc, mhc_checks, act_def_serv):
        cur_gc = gbc.global_config
        ret_list = []
        hbc.log(
            "adding {}".format(
                logging_tools.get_plural("host_cluster check", len(mhc_checks))
            )
        )
        for mhc_check in mhc_checks:
            dev_names = [gbc.get_host(cur_dev).full_name for cur_dev in mhc_check.devices_list]
            if len(dev_names):
                s_check = cur_gc["command"]["check_host_cluster"]
                serv_temp = gbc.serv_templates[mhc_check.mon_service_templ_id]
                serv_cgs = list(set(serv_temp.contact_groups).intersection(hbc.contact_groups))
                sub_list = self.get_service(
                    gbc,
                    hbc,
                    s_check,
                    [
                        special_commands.ArgTemplate(
                            s_check,
                            self._get_cc_name("{}{}{}".format(s_check.get_description(), gbc.join_char, mhc_check.description)),
                            arg1=mhc_check.description,
                            arg2=mhc_check.warn_value,
                            arg3=mhc_check.error_value,
                            arg4=",".join(["$HOSTSTATEID:{}$".format(_dev_name) for _dev_name in dev_names]),
                            arg5=",".join(dev_names),
                        )
                    ],
                    act_def_serv,
                    serv_cgs,
                    serv_temp,
                )
                ret_list.extend(sub_list)
                hbc.add_checks(len(sub_list))
            else:
                hbc.log("ignoring empty host_cluster", logging_tools.LOG_LEVEL_WARN)
        return ret_list

    def add_service_cluster_checks(self, gbc, hbc, msc_checks, act_def_serv):
        cur_gc = gbc.global_config
        hbc.log(
            "adding {}".format(
                logging_tools.get_plural("service_cluster check", len(msc_checks))
            )
        )
        ret_list = []
        for msc_check in msc_checks:
            if msc_check.mon_check_command.name in cur_gc["command"]:
                c_com = cur_gc["command"][msc_check.mon_check_command.name]
                dev_names = [(gbc.get_host(cur_dev).full_name, c_com.get_description()) for cur_dev in msc_check.devices_list]
                if len(dev_names):
                    s_check = cur_gc["command"]["check_service_cluster"]
                    serv_temp = gbc.serv_templates[msc_check.mon_service_templ_id]
                    serv_cgs = list(set(serv_temp.contact_groups).intersection(hbc.contact_groups))
                    sub_list = self.get_service(
                        gbc,
                        hbc,
                        s_check,
                        [
                            special_commands.ArgTemplate(
                                s_check,
                                self._get_cc_name("{} / {}".format(s_check.get_description(), c_com.get_description())),
                                arg1=msc_check.description,
                                # arg2="@{:d}:".format(msc_check.warn_value),
                                # arg3="@{:d}:".format(msc_check.error_value),
                                arg2=msc_check.warn_value,
                                arg3=msc_check.error_value,
                                arg4=",".join(
                                    [
                                        "$SERVICESTATEID:{}:{}$".format(
                                            _dev_name, _srv_name
                                        ) for _dev_name, _srv_name in dev_names
                                        ]
                                ),
                                arg5=",".join(
                                    [
                                        "{}{}{}".format(
                                            _dev_name, gbc.join_char, _srv_name
                                        ).replace(",", " ") for _dev_name, _srv_name in dev_names
                                    ]
                                ),
                            )
                        ],
                        act_def_serv,
                        serv_cgs,
                        serv_temp,
                    )
                    ret_list.extend(sub_list)
                    hbc.add_checks(len(sub_list))
                else:
                    hbc.log("ignoring empty service_cluster", logging_tools.LOG_LEVEL_WARN)
            else:
                hbc.log(
                    "check command '{}' not present in list of commands {}".format(
                        msc_check.mon_check_command.name,
                        ", ".join(sorted(cur_gc["command"].keys()))
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
        return ret_list

    def add_host_config(
        self, gbc, hbc, conf_name, used_checks,
        act_def_serv,
    ):
        cur_gc = gbc.global_config
        s_check = cur_gc["command"][conf_name]
        if s_check.name in used_checks:
            hbc.log(
                "{} ({}) already used, ignoring .... (CHECK CONFIG !)".format(
                    s_check.get_description(),
                    s_check["command_name"],
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        else:
            used_checks.add(s_check.name)
            # s_check: instance of check_command
            if s_check.mccs_id:
                hbc.add_dynamic_check(s_check)
                dc_rv = special_commands.dynamic_checks.handle(
                    gbc,
                    hbc,
                    cur_gc,
                    s_check,
                    DynamicCheckMode.create,
                )
                dc_rv.dump_errors(self.log)
                if dc_rv.r_type == "none":
                    # an error occured, do nothing
                    sc_array = []
                elif dc_rv.r_type == "config":
                    # iterate into add_host_config again
                    for _com_name in dc_rv.config_list:
                        self.add_host_config(
                            gbc, hbc,
                            _com_name, used_checks,
                            act_def_serv,
                        )
                    sc_array = []
                else:
                    # we got a valid list of sc_array
                    sc_array = dc_rv.check_list
                _rewrite_lut = dc_rv.rewrite_lut
            else:
                # no special command, empty rewrite_lut, simple templating
                _rewrite_lut = {}
                sc_array = [
                    special_commands.ArgTemplate(s_check, s_check.get_description(), check_active=False if not s_check.is_active else None)
                ]
                # contact_group is only written if contact_group is responsible for the host and the service_template
            if sc_array:
                serv_temp = gbc.serv_templates[s_check.get_template(act_def_serv.name)]
                serv_cgs = list(set(serv_temp.contact_groups).intersection(hbc.contact_groups))
                sc_list = self.get_service(
                    gbc, hbc, s_check, sc_array, act_def_serv, serv_cgs, serv_temp, **_rewrite_lut
                )
                hbc.host_config_list.extend(sc_list)
                hbc.add_checks(len(sc_list))

    def _get_cc_name(self, in_str):
        if self.__safe_cc_name:
            return build_safe_name(in_str)
        else:
            return in_str

    def _check_for_config(self, hbc, c_type, all_configs, mcc_lut, mcc_lut_2, device, moncc_id):
        # configure mon check commands
        # import pprint
        # pprint.pprint(all_configs.get(device.full_name, []))
        ccoms = sum([mcc_lut_2.get(key, []) for key in all_configs.get(device.full_name, [])], [])
        # needed checkcommand
        nccom = mcc_lut[moncc_id]
        if nccom[0] in ccoms:
            return True
        else:
            hbc.log(
                "Checkcommand '{}' config ({}) not found in configs ({}) for {} '{}'".format(
                    nccom[0],
                    nccom[2],
                    ", ".join(sorted(ccoms)) or "none defined",
                    c_type,
                    unicode(device),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            return False

    def _get_number_of_hosts(self):
        _q = device.objects.exclude(Q(is_meta_device=True)).filter(Q(enabled=True) & Q(device_group__enabled=True))
        if self.host_list:
            _q = _q.filter(Q(name__in=self.host_list))
        # add master/slave related filters
        if not self.__gen_config.master:
            _q = _q.filter(Q(monitor_server=self.__gen_config.monitor_server))
        return _q.count()

    def get_service(self, gbc, hbc, s_check, sc_array, act_def_serv, serv_cgs, serv_temp, **kwargs):
        host = hbc.device
        ev_defined = True if s_check.event_handler else False
        hbc.log(
            "  adding check {:<30s} ({:2d} p), template {}, {}, {}".format(
                s_check["command_name"],
                len(sc_array),
                s_check.get_template(act_def_serv.name),
                "cg: {}".format(", ".join(sorted(serv_cgs))) if serv_cgs else "no cgs",
                "no evh" if not ev_defined else "evh is {} ({})".format(
                    s_check.event_handler.name,
                    "enabled" if (s_check.event_handler_enabled and hbc.host_is_actively_checked) else "disabled",
                ),
            )
        )
        ret_field = []

        # for sc_name, sc in sc_array:
        for arg_temp in sc_array:
            act_serv = StructuredMonBaseConfig("service", arg_temp.info)
            # event handlers
            if s_check.event_handler:
                act_serv["event_handler"] = s_check.event_handler.name
                act_serv["event_handler_enabled"] = "1" if (s_check.event_handler_enabled and hbc.host_is_actively_checked) else "0"
            if arg_temp.check_active is not None:
                # check flag overrides device specific setting
                act_serv["{}_checks_enabled".format("active" if arg_temp.check_active else "passive")] = 1
                act_serv["{}_checks_enabled".format("passive" if arg_temp.check_active else "active")] = 0
            else:
                if arg_temp.is_active:
                    act_serv["{}_checks_enabled".format("active" if hbc.host_is_actively_checked else "passive")] = 1
                    act_serv["{}_checks_enabled".format("passive" if hbc.host_is_actively_checked else "active")] = 0
                else:
                    act_serv["passive_checks_enabled"] = 1
                    act_serv["active_checks_enabled"] = 0
            # display this in icinga webfrontend
            info = arg_temp.info.replace("(", "[").replace(")", "]")
            act_serv["display_name"] = info
            # create identifying string for log
            # print "::", s_check.check_command_pk, s_check.special_command_pk, s_check.mccs_id
            act_serv["service_description"] = host_service_id_util.create_host_service_description(host.pk, s_check, info)
            act_serv["host_name"] = host.full_name
            # volatile
            act_serv["is_volatile"] = "1" if serv_temp.volatile else "0"
            cur_gc = gbc.global_config
            act_serv["check_period"] = cur_gc["timeperiod"][serv_temp.nsc_period_id].name
            act_serv["max_check_attempts"] = serv_temp.max_attempts
            act_serv["check_interval"] = serv_temp.check_interval
            act_serv["retry_interval"] = serv_temp.retry_interval
            act_serv["notification_interval"] = serv_temp.ninterval
            act_serv["notification_options"] = serv_temp.notification_options
            act_serv["notification_period"] = cur_gc["timeperiod"][serv_temp.nsn_period_id].name
            if serv_cgs:
                act_serv["contact_groups"] = serv_cgs
            else:
                act_serv["contact_groups"] = self.gc["NONE_CONTACT_GROUP"]
            if not hbc.host_is_actively_checked:
                act_serv["check_freshness"] = 0
                act_serv["freshness_threshold"] = 3600
            if hbc.host_is_actively_checked and not cur_gc.master:
                # trace
                act_serv["obsess_over_service"] = 1
            act_serv["flap_detection_enabled"] = 1 if (host.flap_detection_enabled and serv_temp.flap_detection_enabled) else 0
            if serv_temp.flap_detection_enabled and host.flap_detection_enabled:
                act_serv["low_flap_threshold"] = serv_temp.low_flap_threshold
                act_serv["high_flap_threshold"] = serv_temp.high_flap_threshold
                n_field = []
                for short, f_name in [("o", "ok"), ("w", "warn"), ("c", "critical"), ("u", "unknown")]:
                    if getattr(serv_temp, "flap_detect_{}".format(f_name)):
                        n_field.append(short)
                if not n_field:
                    n_field.append("o")
                act_serv["flap_detection_options"] = n_field
            if self.gc["ENABLE_COLLECTD"]:
                act_serv["process_perf_data"] = 1 if (host.enable_perfdata and s_check.enable_perfdata) else 0
            # TODO: POSSIBLY remove this in favor of service_description
            act_serv["_device_pk"] = host.pk
            if s_check.servicegroup_names:
                act_serv["_cat_pks"] = s_check.servicegroup_pks
                act_serv["servicegroups"] = s_check.servicegroup_names
                cur_gc["servicegroup"].add_host(host.name, act_serv["servicegroups"])
            # command_name may be altered when using a special-command
            _com_parts = [
                kwargs.get("command_name", s_check["command_name"])
            ] + s_check.correct_argument_list(arg_temp, host.dev_variables)
            if any([_part is None for _part in _com_parts]) and self.gc["DEBUG"]:
                self.log("none found: {}".format(str(_com_parts)), logging_tools.LOG_LEVEL_CRITICAL)
            else:
                act_serv["check_command"] = "!".join(_com_parts)
            # add addon vars
            for key, value in arg_temp.addon_dict.iteritems():
                act_serv[key] = value
            ret_field.append(act_serv)
        return ret_field

    def _get_target_ip_info(self, gbc, hbc, net_devices):
        srv_net_idxs = gbc.server_net_idxs
        host = hbc.device
        traces = gbc.get_mon_host_trace(host, net_devices, srv_net_idxs)
        if not traces:
            pathes = self.router_obj.get_ndl_ndl_pathes(srv_net_idxs, net_devices.keys(), add_penalty=True)
            traces = []
            for penalty, cur_path in sorted(pathes):
                if cur_path[-1] in net_devices:
                    dev_path = self.router_obj.map_path_to_device(cur_path)
                    dev_path.reverse()
                    traces.append((penalty, cur_path[-1], dev_path))
            traces = sorted(traces)
            gbc.set_mon_host_trace(host, net_devices, srv_net_idxs, traces)
        if not traces:
            hbc.log(
                "Cannot reach device {} (check peer_information)".format(
                    host.full_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            valid_ips = []
        else:
            valid_ips = []
            _nd_added = set()
            for _val, nd_pk, _loc_trace in traces:
                if nd_pk not in _nd_added:
                    _nd_added.add(nd_pk)
                    valid_ips.extend(net_devices[nd_pk])
            # old code, produces a lot of dups
            # valid_ips = sum([net_devices[nd_pk] for _val, nd_pk, _loc_trace in traces], [])
        return valid_ips, traces
