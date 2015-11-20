# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
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
""" build process for md-config-server """

import codecs
import commands
import operator
import json
import os
import os.path
import signal
import time

from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, device_group, device_variable, mon_ext_host, \
    mon_contactgroup, netdevice, network_type, user, config, config_catalog, \
    mon_host_dependency_templ, mon_host_dependency, mon_service_dependency, net_ip, \
    mon_check_command_special, mon_check_command
from initat.md_config_server import special_commands, constants
from initat.md_config_server.config import global_config, main_config, all_commands, \
    all_service_groups, time_periods, all_contacts, all_contact_groups, all_host_groups, all_hosts, \
    all_services, config_dir, device_templates, service_templates, mon_config, \
    all_host_dependencies, build_cache, build_safe_name, SimpleCounter
from initat.md_config_server.constants import CACHE_MODES, DEFAULT_CACHE_MODE
from initat.md_config_server.mixins import version_check_mixin
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from lxml.builder import E  # @UnresolvedImport
import networkx
from initat.tools import config_tools, configfile, logging_tools, net_tools, process_tools, \
    server_command, threading_tools
from initat.icsw.service.instance import InstanceXML


class build_process(threading_tools.process_obj, version_check_mixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
        self.__icinga_lock_file_name = os.path.join(global_config["MD_BASEDIR"], "var", global_config["MD_LOCK_FILE"])
        connection.close()
        self.__mach_loggers = {}
        self.__num_mach_logs = {}
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        self.version = int(time.time())
        self.log("initial config_version is %d" % (self.version))
        self.router_obj = config_tools.router_object(self.log)
        self.register_func("check_for_slaves", self._check_for_slaves)

        self.register_func("build_host_config", self._check_call)
        self.register_func("sync_http_users", self._check_call)
        self.register_func("rebuild_config", self._check_call)
        self.register_func("reload_md_daemon", self._check_call)
        # store pending commands
        self.__pending_commands = []
        # ready (check_for_slaves called)
        self.__ready = False

        # self.__host_service_map = host_service_map(self.log)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        for mach_logger in self.__mach_loggers.itervalues():
            mach_logger.close()
        self.__log_template.close()

    def _check_for_slaves(self, **kwargs):
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        slave_servers = device.objects.filter(Q(device_config__config__name="monitor_slave")).select_related("domain_tree_node")
        # slave configs
        self.__gen_config = main_config(self, master_server, distributed=True if len(slave_servers) else False)
        self.send_pool_message("external_cmd_file", self.__gen_config.get_command_name())
        self.__gen_config_built = False
        self.__slave_configs, self.__slave_lut = ({}, {})
        if len(slave_servers):
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("slave_server", len(slave_servers)),
                    ", ".join(sorted([cur_dev.full_name for cur_dev in slave_servers]))))
            for cur_dev in slave_servers:
                _slave_c = main_config(
                    self,
                    cur_dev,
                    slave_name=cur_dev.full_name,
                    master_server=master_server,
                )
                self.__slave_configs[cur_dev.pk] = _slave_c
                self.__slave_lut[cur_dev.full_name] = cur_dev.pk
        else:
            self.log("no slave-servers found")
        self.__ready = True
        if self.__pending_commands:
            self.log("processing {}".format(logging_tools.get_plural("pending command", len(self.__pending_commands))))
            while self.__pending_commands:
                _pc = self.__pending_commands.pop(0)
                self._check_call(*_pc["args"], **_pc["kwargs"])

    def send_command(self, src_id, srv_com):
        self.send_pool_message("send_command", "urn:uuid:{}:relayer".format(src_id), srv_com)

    def mach_log(self, what, lev=logging_tools.LOG_LEVEL_OK, mach_name=None, **kwargs):
        if "single_build" in kwargs:
            self.__write_logs = kwargs["single_build"]
        if mach_name is None:
            mach_name = self.__cached_mach_name
        else:
            self.__cached_mach_name = mach_name
        if mach_name not in self.__mach_loggers:
            self.__num_mach_logs[mach_name] = 0
            if self.__write_logs:
                self.__mach_loggers[mach_name] = self._get_mach_logger(mach_name)
            else:
                self.__mach_loggers[mach_name] = []
        self.__num_mach_logs[mach_name] += 1
        if self.__write_logs:
            self.__mach_loggers[mach_name].log(lev, what)
        else:
            self.__mach_loggers[mach_name].append((lev, what))
        if kwargs.get("global_flag", False):
            self.log(what, lev)

    def get_num_mach_logs(self):
        return self.__num_mach_logs.get(self.__cached_mach_name, 0)

    def _get_mach_logger(self, mach_name):
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

    def close_mach_log(self, mach_name=None, **kwargs):
        if mach_name is not None:
            self.__cached_mach_name = mach_name
        if self.__cached_mach_name:
            mach_name = self.__cached_mach_name
            del self.__num_mach_logs[mach_name]
            if self.__write_logs:
                self.__mach_loggers[mach_name].close()
            else:
                if kwargs.get("write_logs", False):
                    # write logs because of flag (errors ?)
                    _logger = self._get_mach_logger(mach_name)
                    for _lev, _what in self.__mach_loggers[mach_name]:
                        _logger.log(_lev, _what)
                    _logger.close()
                    del _logger
            del self.__mach_loggers[mach_name]

    def _check_md_config(self):
        c_stat, out = commands.getstatusoutput("{}/bin/{} -v {}/etc/{}.cfg".format(
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"],
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"]))
        if c_stat:
            self.log(
                "Checking the {}-configuration resulted in an error ({:d})".format(
                    global_config["MD_TYPE"],
                    c_stat,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            ret_stat = False
        else:
            self.log("Checking the {}-configuration returned no error".format(global_config["MD_TYPE"]))
            ret_stat = True
        return ret_stat, out

    def _check_call(self, *args, **kwargs):
        if self.__ready:
            getattr(self, "_{}".format(kwargs["func_name"]))(*args, **kwargs)
        else:
            self.__pending_commands.append(
                {
                    "args": args,
                    "kwargs": kwargs,
                }
            )

    def _reload_md_daemon(self, **kwargs):
        start_daemon, restart_daemon = (False, False)
        cs_stat, cs_out = self._check_md_config()
        if not cs_stat:
            self.log("Checking the {}-config resulted in an error, not trying to (re)start".format(global_config["MD_TYPE"]), logging_tools.LOG_LEVEL_ERROR)
            self.log("error_output has {}".format(logging_tools.get_plural("line", cs_out.split("\n"))),
                     logging_tools.LOG_LEVEL_ERROR)
            for line in cs_out.split("\n"):
                if line.strip().lower().startswith("error"):
                    self.log(" - {}".format(line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if os.path.isfile(self.__icinga_lock_file_name):
                try:
                    pid = file(self.__icinga_lock_file_name, "r").read().strip()
                except:
                    self.log(
                        "Cannot read {} LockFile named '{}', trying to start {}".format(
                            global_config["MD_TYPE"],
                            self.__icinga_lock_file_name,
                            global_config["MD_TYPE"],
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                    start_daemon = True
                else:
                    pid = file(self.__icinga_lock_file_name).read().strip()
                    try:
                        pid = int(pid)
                    except:
                        self.log(
                            "PID read from '{}' is not an integer ({}, {}), trying to restart {}".format(
                                self.__icinga_lock_file_name,
                                str(pid),
                                process_tools.get_except_info(),
                                global_config["MD_TYPE"],
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        restart_daemon = True
                    else:
                        try:
                            os.kill(pid, signal.SIGHUP)
                        except OSError:
                            self.log(
                                "Error signaling pid {:d} with SIGHUP ({:d}), trying to restart {} ({})".format(
                                    pid,
                                    signal.SIGHUP,
                                    global_config["MD_TYPE"],
                                    process_tools.get_except_info(),
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            restart_daemon = True
                        else:
                            self.log("Successfully signaled pid {:d} with SIGHUP ({:d})".format(pid, signal.SIGHUP))
            else:
                self.log(
                    "{} LockFile '{}' not found, trying to start {}".format(
                        global_config["MD_TYPE"],
                        self.__icinga_lock_file_name,
                        global_config["MD_TYPE"]),
                    logging_tools.LOG_LEVEL_WARN)
                start_daemon = True
        if start_daemon:
            _cmd = "start"
        elif restart_daemon:
            _cmd = "restart"
        else:
            _cmd = None
        if _cmd:
            self.log("Trying to {} {} via collserver-call_script".format(_cmd, global_config["MD_TYPE"]))
            reply = net_tools.zmq_connection("md_config_server", timeout=10).add_connection(
                "tcp://localhost:{:d}".format(self.__hm_port),
                server_command.srv_command(
                    command="call_script",
                    **{
                        "arguments:arg0": "/etc/init.d/{}".format(global_config["MD_TYPE"]),
                        "arguments:arg1": _cmd,
                    }
                )
            )
            if reply is None:
                self.log("got no reply", logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log(*reply.get_log_tuple())

    def _sync_http_users(self, *args, **kwargs):
        self.log("syncing http-users")
        self.__gen_config._create_access_entries()

    def _build_host_config(self, srv_com_str, *args, **kwargs):
        srv_com = server_command.srv_command(source=srv_com_str)
        dev_pks = srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
        dev_cache_modes = list(set(srv_com.xpath(".//device_list/device/@mode", smart_strings=False)))
        if dev_cache_modes:
            dev_cache_mode = dev_cache_modes[0]
            dev_names = [cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=dev_pks)).select_related("domain_tree_node")]
            self.log(
                "starting single build with {}, cache mode is {}: {}".format(
                    logging_tools.get_plural("device", len(dev_names)),
                    dev_cache_mode,
                    ", ".join(sorted(dev_names))
                )
            )
            srv_com["result"] = self._rebuild_config(*dev_names, cache_mode=dev_cache_mode)
            srv_com.set_result("rebuilt config for {}".format(", ".join(dev_names)), server_command.SRV_REPLY_STATE_OK)
        else:
            srv_com.set_result("no devices given", server_command.SRV_REPLY_STATE_ERROR)
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _cleanup_db(self):
        # cleanup tasks for the database
        num_empty_mhd = mon_host_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).count()
        num_empty_msd = mon_service_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).count()
        if num_empty_mhd:
            self.log("removing {} empty mon_host_dependencies".format(num_empty_mhd))
            mon_host_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).delete()
        if num_empty_msd:
            self.log("removing {} empty mon_service_dependencies".format(num_empty_msd))
            mon_service_dependency.objects.filter(Q(devices=None) & Q(dependent_devices=None)).delete()

    def _check_for_snmp_container(self):
        try:
            _container = config.objects.get(Q(name="SNMP container"))
        except config.DoesNotExist:
            self.log("created SNMP container class")
            _container = config.objects.create(
                name="SNMP container",
                system_config=True,
                server_config=True,
                config_catalog=config_catalog.objects.get(Q(system_catalog=True)),
                enabled=False,
                description="container for all SNMP checks",
            )
        _present_coms = set(_container.mon_check_command_set.all().values_list("name", flat=True))
        _specials = {"snmp {}".format(_special.name): _special for _special in mon_check_command_special.objects.all()}
        _new = set(["snmp {}".format(_com.Meta.name) for _com in special_commands.special_snmp_general.special_snmp_general(self.log).get_commands()])
        _to_create = set(_specials.keys()) & (_new - _present_coms)
        for _name in _to_create:
            _new_mcc = mon_check_command.objects.create(
                name=_name,
                description="auto created SNMP check entry",
                config=_container,
                mon_check_command_special=_specials[_name],
                command_line="/bin/true",
            )

    def _rebuild_config(self, *args, **kwargs):
        # self.__host_service_map.start_collecting()

        single_build = True if len(args) > 0 else False
        if not single_build:
            # from mixin
            self._check_md_version()
            self._check_relay_version()
            self._cleanup_db()
            # check for SNMP container config
            self._check_for_snmp_container()
        # copy from global_config (speedup)
        self.gc = configfile.gc_proxy(global_config)
        hdep_from_topo = self.gc["USE_HOST_DEPENDENCIES"] and self.gc["HOST_DEPENDENCIES_FROM_TOPOLOGY"]
        if hdep_from_topo:
            host_deps = mon_host_dependency_templ.objects.all().order_by("-priority")
            if len(host_deps):
                self.mon_host_dep = host_deps[0]
            else:
                self.log("no mon_host_dependencies found", logging_tools.LOG_LEVEL_ERROR)
                hdep_from_topo = False
        h_list = list(args)
        cache_mode = kwargs.get("cache_mode", "???")
        if cache_mode not in CACHE_MODES:
            # take first cache mode
            cache_mode = DEFAULT_CACHE_MODE
        self.log(
            "rebuild_config called, single_build is {}, cache_mode is {}, hdep_from_topo is {}".format(
                str(single_build),
                cache_mode,
                str(hdep_from_topo),
            )
        )
        if self.gc["DEBUG"]:
            cur_query_count = len(connection.queries)
        cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        if single_build:
            build_dv = None
        else:
            # delete old gauge variables
            device_variable.objects.filter(Q(name="_SYS_GAUGE_") & Q(is_public=False) & Q(device=cdg)).delete()
            # init build variable
            build_dv = device_variable(
                device=cdg,
                is_public=False,
                name="_SYS_GAUGE_",
                description="mon config rebuild on {}".format(
                    self.__gen_config.monitor_server.full_name if self.__gen_config else "unknown"
                ),
                var_type="i"
            )
            # bump version
            if int(time.time()) > self.version:
                self.version = int(time.time())
            else:
                self.version += 1
            self.log("config_version for full build is {:d}".format(self.version))
            self.send_pool_message("build_info", "start_build", self.version, target="syncer")
        # fetch SNMP-stuff from cluster and initialise var cache
        rebuild_gen_config = False
        if not h_list:
            self.log(
                "rebuilding complete config (for master and {})".format(
                    logging_tools.get_plural("slave", len(self.__slave_configs))
                )
            )
            rebuild_gen_config = True
        else:
            # FIXME, handle host-related config for only specified slaves
            self.log(
                "rebuilding config for {}: {}".format(
                    logging_tools.get_plural("host", len(h_list)),
                    logging_tools.compress_list(h_list)
                )
            )
        if not self.__gen_config:
            rebuild_gen_config = True
        if rebuild_gen_config:
            self._create_general_config()
            # h_list = []
        bc_valid = self.__gen_config.is_valid()
        if bc_valid:
            # get device templates
            dev_templates = device_templates(self)
            # get serivce templates
            serv_templates = service_templates(self)
            if dev_templates.is_valid() and serv_templates.is_valid():
                pass
            else:
                if not dev_templates.is_valid():
                    self.log("device templates are not valid", logging_tools.LOG_LEVEL_ERROR)
                if not serv_templates.is_valid():
                    self.log("service templates are not valid", logging_tools.LOG_LEVEL_ERROR)
                bc_valid = False
        if bc_valid:
            if single_build:
                if not self.__gen_config_built:
                    self._create_general_config(write_entries=False)
                # clean device and service entries
                for key in constants.SINGLE_BUILD_MAPS:
                    if key in self.__gen_config:
                        self.__gen_config[key].refresh(self.__gen_config)
            self.router_obj.check_for_update()
            total_hosts = sum([self._get_number_of_hosts(cur_gc, h_list) for cur_gc in [self.__gen_config] + self.__slave_configs.values()])
            if build_dv:
                self.log("init gauge with max={:d}".format(total_hosts))
                build_dv.init_as_gauge(total_hosts)
            if not single_build:
                # build distance map
                cur_dmap, unreachable_pks = self._build_distance_map(self.__gen_config.monitor_server, show_unroutable=not single_build)
                self.send_pool_message("build_info", "unreachable_devices", len(unreachable_pks), target="syncer")
                if unreachable_pks:
                    for _urd in device.objects.filter(Q(pk__in=unreachable_pks)).select_related("domain_tree_node"):
                        self.send_pool_message("build_info", "unreachable_device", _urd.pk, unicode(_urd), unicode(_urd.device_group), target="syncer")
            else:
                cur_dmap = {}
                unreachable_pks = []
            # todo, move to separate processes
            gc_list = [self.__gen_config]
            if not single_build:
                gc_list.extend(self.__slave_configs.values())
            for cur_gc in gc_list:
                cur_gc.cache_mode = cache_mode
                if cur_gc.master and not single_build:
                    # recreate access files
                    cur_gc._create_access_entries()

                _bc = build_cache(self.log, cdg, full_build=not single_build, unreachable_pks=unreachable_pks)
                _bc.cache_mode = cache_mode
                _bc.build_dv = build_dv
                _bc.host_list = h_list
                _bc.dev_templates = dev_templates
                _bc.serv_templates = serv_templates
                _bc.single_build = single_build
                _bc.debug = self.gc["DEBUG"]
                self.send_pool_message("build_info", "start_config_build", cur_gc.monitor_server.full_name, target="syncer")
                self._create_host_config_files(_bc, cur_gc, cur_dmap, hdep_from_topo)
                self.send_pool_message("build_info", "end_config_build", cur_gc.monitor_server.full_name, target="syncer")
                if not single_build:
                    # refresh implies _write_entries
                    cur_gc.refresh()
                    if not cur_gc.master:
                        # write config to disk
                        cur_gc._write_entries()
                        # start syncing
                        self.send_pool_message("build_info", "sync_slave", cur_gc.monitor_server.full_name, target="syncer")
                del _bc
            if build_dv:
                build_dv.delete()
        if not single_build:
            cfgs_written = self.__gen_config._write_entries()
            if bc_valid and (cfgs_written or rebuild_gen_config):
                # send reload to remote instance ?
                self._reload_md_daemon()
            self.send_pool_message("build_info", "end_build", self.version, target="syncer")
        else:
            cur_gc = self.__gen_config
            res_node = E.config(
                *sum([cur_gc[key].get_xml() for key in constants.SINGLE_BUILD_MAPS], [])
            )
        if self.gc["DEBUG"]:
            tot_query_count = len(connection.queries) - cur_query_count
            self.log("queries issued: {:d}".format(tot_query_count))
            for q_idx, act_sql in enumerate(connection.queries[cur_query_count:], 1):
                self.log("{:5d} {}".format(q_idx, act_sql["sql"][:180]))
        # self.__host_service_map.end_collecting()
        del self.gc
        if single_build:
            return res_node

    def _build_distance_map(self, root_node, show_unroutable=True):
        self.log("building distance map, root node is '{}'".format(root_node))
        # exclude all without attached netdevices
        dm_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.objects.filter(
                Q(enabled=True) & Q(device_group__enabled=True)
            ).exclude(netdevice=None).select_related("domain_tree_node").prefetch_related("netdevice_set")
        }
        nd_dict = {}
        for dev_pk, nd_pk in netdevice.objects.filter(Q(enabled=True)).values_list("device", "pk"):
            nd_dict.setdefault(dev_pk, set()).add(nd_pk)
        nd_lut = {
            value[0]: value[1] for value in netdevice.objects.filter(
                Q(enabled=True)
            ).values_list("pk", "device") if value[1] in dm_dict.keys()
        }
        for cur_dev in dm_dict.itervalues():
            # set 0 for root_node, -1 for all other devices
            cur_dev.md_dist_level = 0 if cur_dev.pk == root_node.pk else -1
        all_pks = set(dm_dict.keys())
        all_nd_pks = set(nd_lut.keys())
        max_level = 0
        # limit for loop
        for cur_iter in xrange(128):
            run_again = False
            # iterate until all nodes have a valid dist_level set
            src_nodes = set([key for key, value in dm_dict.iteritems() if value.md_dist_level >= 0])
            dst_nodes = all_pks - src_nodes
            self.log(
                "dm_run {:3d}, {}, {}".format(
                    cur_iter,
                    logging_tools.get_plural("source node", len(src_nodes)),
                    logging_tools.get_plural("dest node", len(dst_nodes))
                )
            )
            src_nds = reduce(operator.ior, [nd_dict[key] for key in src_nodes if key in nd_dict], set())
            # dst_nds = reduce(operator.ior, [nd_dict[key] for key in dst_nodes], set())
            # build list of src_nd, dst_nd tuples
            nb_list = []
            for src_nd in src_nds:
                try:
                    for dst_nd in networkx.all_neighbors(self.router_obj.nx, src_nd):
                        if dst_nd not in src_nds:
                            nb_list.append((src_nd, dst_nd))
                except networkx.exception.NetworkXError:
                    self.log(
                        "netdevice {} is not in graph: {}".format(
                            src_nd,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            for src_nd, dst_nd, in nb_list:
                if src_nd in all_nd_pks and dst_nd in all_nd_pks:
                    src_dev, dst_dev = (dm_dict[nd_lut[src_nd]], dm_dict[nd_lut[dst_nd]])
                    new_level = src_dev.md_dist_level + 1
                    if dst_dev.md_dist_level >= 0 and new_level > dst_dev.md_dist_level:
                        self.log(
                            "pushing node {} farther away from root ({:d} => {:d})".format(
                                unicode(dst_dev),
                                dst_dev.md_dist_level,
                                new_level,
                            )
                        )
                    dst_dev.md_dist_level = max(dst_dev.md_dist_level, new_level)
                    max_level = max(max_level, dst_dev.md_dist_level)
                    run_again = True
                else:
                    self.log(
                        "dropping link ({:d}, {:d}), devices disabled?".format(
                            src_nd,
                            dst_nd
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
            if not run_again:
                break
        self.log("max distance level: {:d}".format(max_level))
        nodes_ur = [unicode(value) for value in dm_dict.itervalues() if value.md_dist_level < 0]
        ur_pks = [_entry.pk for _entry in dm_dict.itervalues() if _entry.md_dist_level < 0]
        if nodes_ur and show_unroutable:
            self.log(
                u"{}: {}".format(
                    logging_tools.get_plural("unroutable node", len(nodes_ur)),
                    u", ".join(sorted(nodes_ur)),
                )
            )
        for level in xrange(max_level + 1):
            self.log(
                "nodes in level {:d}: {}".format(
                    level,
                    len([True for value in dm_dict.itervalues() if value.md_dist_level == level]),
                )
            )
        return {
            key: value.md_dist_level for key, value in dm_dict.iteritems()
        }, ur_pks

    def _create_general_config(self, write_entries=None):
        self.__gen_config_built = True
        config_list = [self.__gen_config] + self.__slave_configs.values()
        if write_entries is not None:
            prev_awc = self.__gen_config.allow_write_entries
            for cur_conf in config_list:
                # set actual value
                cur_conf.allow_write_entries = write_entries
        start_time = time.time()
        self._check_image_maps()
        self._create_gen_config_files(config_list)
        end_time = time.time()
        if write_entries is not None:
            for cur_conf in config_list:
                # restore to previous value
                cur_conf.allow_write_entries = prev_awc
        self.log(
            "creating the total general config took {}".format(
                logging_tools.get_diff_time_str(end_time - start_time)
            )
        )

    def _create_gen_config_files(self, gc_list):
        for cur_gc in gc_list:
            start_time = time.time()
            # misc commands (sending of mails)
            cur_gc.add_config(all_commands(cur_gc, self))
            # servicegroups
            cur_gc.add_config(all_service_groups(cur_gc, self))
            # timeperiods
            cur_gc.add_config(time_periods(cur_gc, self))
            # contacts
            cur_gc.add_config(all_contacts(cur_gc, self))
            # contactgroups
            cur_gc.add_config(all_contact_groups(cur_gc, self))
            # hostgroups
            cur_gc.add_config(all_host_groups(cur_gc, self))
            # hosts
            cur_gc.add_config(all_hosts(cur_gc, self))
            # services
            cur_gc.add_config(all_services(cur_gc, self))
            # device dir
            cur_gc.add_config_dir(config_dir("device", cur_gc, self))
            # host_dependencies
            cur_gc.add_config(all_host_dependencies(cur_gc, self))
            end_time = time.time()
            cur_gc.log("created host_configs in {}".format(logging_tools.get_diff_time_str(end_time - start_time)))

    def _get_mon_ext_hosts(self):
        return {cur_ext.pk: cur_ext for cur_ext in mon_ext_host.objects.all()}

    def _check_image_maps(self):
        min_width, max_width, min_height, max_height = (16, 64, 16, 64)
        all_image_stuff = self._get_mon_ext_hosts()
        self.log("Found {}".format(logging_tools.get_plural("ext_host entry", len(all_image_stuff.keys()))))
        logos_dir = "{}/share/images/logos".format(self.gc["MD_BASEDIR"])
        base_names = set()
        if os.path.isdir(logos_dir):
            logo_files = os.listdir(logos_dir)
            for log_line in [entry.split(".")[0] for entry in logo_files]:
                if log_line not in base_names:
                    if "{}.png".format(log_line) in logo_files and "{}.gd2".format(log_line) in logo_files:
                        base_names.add(log_line)
        name_case_lut = {}
        if base_names:
            stat, out = commands.getstatusoutput("file {}".format(" ".join([os.path.join(logos_dir, "{}.png".format(entry)) for entry in base_names])))
            if stat:
                self.log(
                    "error getting filetype of {}".format(
                        logging_tools.get_plural("logo", len(base_names))
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                base_names = set()
                for logo_name, logo_data in [
                    (os.path.basename(y[0].strip()), [z.strip() for z in y[1].split(",") if z.strip()]) for y in [
                        line.strip().split(":", 1) for line in out.split("\n")] if len(y) == 2]:
                    if len(logo_data) == 4:
                        width, height = [int(value.strip()) for value in logo_data[1].split("x")]
                        if min_width <= width and width <= max_width and min_height <= height and height <= max_height:
                            base_name = logo_name[:-4]
                            base_names.add(base_name)
                            name_case_lut[base_name.lower()] = base_name
                        else:
                            self.log(
                                "width or height ({:d} x {:d}) not in range ([{:d} - {:d}] x [{:d} - {:d}])".format(
                                    width,
                                    height,
                                    min_width,
                                    max_width,
                                    min_height,
                                    max_height,
                                )
                            )
        name_lut = {eh.name.lower(): pk for pk, eh in all_image_stuff.iteritems()}
        all_images_present = set([eh.name for eh in all_image_stuff.values()])
        all_images_present_lower = set([name.lower() for name in all_images_present])
        base_names_lower = set([name.lower() for name in base_names])
        new_images = base_names_lower - all_images_present_lower
        del_images = all_images_present_lower - base_names_lower
        present_images = base_names_lower & all_images_present_lower
        for new_image in new_images:
            mon_ext_host(
                name=new_image,
                icon_image="{}.png".format(new_image),
                statusmap_image="%s.gd2" % (new_image)
            ).save()
        for p_i in present_images:
            img_stuff = all_image_stuff[name_lut[p_i]]
            # check for wrong case
            if img_stuff.icon_image != "{}.png".format(name_case_lut[img_stuff.name]):
                # correct case
                img_stuff.icon_image = "{}.png".format(name_case_lut[img_stuff.name])
                img_stuff.statusmap_image = "{}.gd2".format(name_case_lut[img_stuff.name])
                img_stuff.save()
        if del_images:
            mon_ext_host.objects.filter(Q(name__in=del_images)).delete()
        self.log("Inserted {}, deleted {}".format(
            logging_tools.get_plural("new ext_host_entry", len(new_images)),
            logging_tools.get_plural("ext_host_entry", len(del_images))))

    def _create_single_host_config(
        self,
        _bc,
        cur_gc,
        host,
        d_map,
        my_net_idxs,
        all_access,
        contact_group_dict,
        ng_ext_hosts,
        all_configs,
        nagvis_maps,
        mccs_dict,
    ):
        # optimize
        self.__safe_cc_name = global_config["SAFE_CC_NAME"]
        start_time = time.time()
        # set some vars
        host_nc = cur_gc["device.d"]
        # we always check for passive checks
        # if cur_gc.master:
        #    check_for_passive_checks = True
        # else:
        #    check_for_passive_checks = False
        # checks_are_active = True
        # if check_for_passive_checks:
        #    if host.monitor_server_id and host.monitor_server_id != cur_gc.monitor_server.pk:
        #        checks_are_active = False
        # check if host is actively checked via current server
        if cur_gc.master:
            if host.monitor_server_id and host.monitor_server_id != cur_gc.monitor_server.pk:
                host_is_actively_checked = False
            else:
                host_is_actively_checked = True
        else:
            host_is_actively_checked = True
        # h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        self.__cached_mach_name = host.full_name
        # cache logs
        _write_logs = False
        self.mach_log(
            "-------- {} ---------".format(
                "master" if cur_gc.master else "slave {}".format(cur_gc.slave_name)
            ),
            single_build=_bc.single_build
        )
        glob_log_str = "device {:<48s}{} ({}), d={:>3s}".format(
            host.full_name[:48],
            "*" if len(host.name) > 48 else " ",
            "a" if host_is_actively_checked else "p",
            "{:3d}".format(d_map[host.pk]) if d_map.get(host.pk) >= 0 else "---",
        )
        self.mach_log("Starting build of config", logging_tools.LOG_LEVEL_OK, host.full_name)
        _counter = SimpleCounter()
        if host.valid_ips:
            net_devices = host.valid_ips
        elif host.invalid_ips:
            self.mach_log(
                "Device {} has no valid netdevices associated, using invalid ones...".format(
                    host.full_name
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            net_devices = host.invalid_ips
        else:
            self.mach_log(
                "Device {} has no netdevices associated, skipping...".format(
                    host.full_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _counter.error()
            net_devices = {}
        use_host_deps, use_service_deps = (
            self.gc["USE_HOST_DEPENDENCIES"],
            self.gc["USE_SERVICE_DEPENDENCIES"],
        )
        if net_devices:
            # print mni_str_s, mni_str_d, dev_str_s, dev_str_d
            # get correct netdevice for host
            valid_ips, traces = self._get_target_ip_info(_bc, my_net_idxs, net_devices, _bc.get_host(host.pk))
            if not valid_ips:
                _counter.error()
            act_def_dev = _bc.dev_templates[host.mon_device_templ_id or 0]
            if _bc.single_build:
                if not valid_ips:
                    valid_ips = [(net_ip(ip="0.0.0.0"), host.full_name)]
                    self.mach_log("no ips found using {} as dummy IP".format(str(valid_ips)))
            else:
                if (len(valid_ips) > 0) != host.reachable:
                    self.log(
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
                self.mach_log(
                    "Found {} for host {} : {}, mon_resolve_name is {}, using {}".format(
                        logging_tools.get_plural("target ip", len(valid_ips)),
                        host.full_name,
                        ", ".join(["{}{}".format(cur_ip, " (.{})".format(dom_name) if dom_name else "") for cur_ip, dom_name in valid_ips]),
                        str(host.mon_resolve_name),
                        unicode(host.valid_ip)
                    )
                )
                if act_def_dev.mon_service_templ_id not in _bc.serv_templates:
                    self.log("Default service_template not found in service_templates", logging_tools.LOG_LEVEL_WARN)
                else:
                    act_def_serv = _bc.serv_templates[act_def_dev.mon_service_templ_id]
                    # tricky part: check the actual service_template for the various services
                    self.mach_log(
                        "Using default device_template '{}' and service_template '{}' for host {}".format(
                            act_def_dev.name,
                            act_def_serv.name,
                            host.full_name,
                        )
                    )
                    # get device variables
                    dev_variables, var_info = _bc.get_vars(host)
                    # store
                    host.dev_variables = dev_variables
                    self.mach_log(
                        "device has {} ({})".format(
                            logging_tools.get_plural("device_variable", len(host.dev_variables.keys())),
                            ", ".join(["{}: {:d}".format(key, var_info[key]) for key in ["d", "g", "c"]]),
                        )
                    )
                    # now we have the device- and service template
                    host_config_list = []
                    act_host = mon_config("host", host.full_name)
                    host_config_list.append(act_host)
                    act_host["host_name"] = host.full_name
                    act_host["display_name"] = host.full_name
                    # action url
                    if self.gc["ENABLE_COLLECTD"]:
                        act_host["process_perf_data"] = 1 if host.enable_perfdata else 0
                    # always set action_url
                    act_host["action_url"] = reverse("device:device_info", kwargs={"device_pk": host.pk, "mode": "rrd"})
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
                    act_host["active_checks_enabled"] = 1 if host_is_actively_checked else 0
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
                    # always enable obsess_over_host
                    if True:
                        act_host["obsess_over_host"] = 1
                    host_groups = set(contact_group_dict.get(host.full_name, []))
                    act_host["contact_groups"] = list(host_groups) if host_groups else self.gc["NONE_CONTACT_GROUP"]
                    c_list = [entry for entry in all_access] + _bc.get_device_group_users(host.device_group_id)
                    if c_list:
                        act_host["contacts"] = c_list
                    self.mach_log("contact groups for host: {}".format(
                        ", ".join(sorted(host_groups)) or "none"))
                    if host.monitor_checks or _bc.single_build:
                        if host.valid_ip.ip == "0.0.0.0":
                            self.mach_log("IP address is '{}', host is assumed to be always up".format(unicode(host.valid_ip)))
                            act_host["check_command"] = "check-host-ok"
                        else:
                            if act_def_dev.host_check_command:
                                if host_is_actively_checked:
                                    act_host["check_command"] = act_def_dev.host_check_command.name
                                else:
                                    self.mach_log("disabling host check_command (passive)")
                            else:
                                self.log("dev_template has no host_check_command set", logging_tools.LOG_LEVEL_ERROR)
                        # check for nagvis map
                        if host.automap_root_nagvis and cur_gc.master:
                            # with or without .cfg ? full path ?
                            act_host["_nagvis_map"] = "{}".format(host.full_name.encode("ascii", errors="ignore"))
                            map_file = os.path.join(
                                self.gc["NAGVIS_DIR"],
                                "etc",
                                "maps",
                                "{}.cfg".format(
                                    host.full_name.encode("ascii", errors="ignore")
                                )
                            )
                            map_dict = {
                                "sources": "automap",
                                "alias": host.comment or host.full_name,
                                "iconset": "std_big",
                                "child_layers": 10,
                                "backend_id": "live_1",
                                "root": host.full_name,
                                "label_show": "1",
                                "label_border": "transparent",
                                "render_mode": "directed",
                                "rankdir": "TB",
                                "width": 800,
                                "height": 600,
                                "header_menu": True,
                                "hover_menu": True,
                                "context_menu": True,
                                # parent map
                                "parent_map": host.device_group.name.replace(" ", "_"),
                                # special flag for anovis
                                "use_childs_for_overview_icon": False,
                            }
                            try:
                                map_h = codecs.open(map_file, "w", "utf-8")
                            except:
                                self.mach_log(
                                    u"cannot open {}: {}".format(
                                        map_file,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_CRITICAL
                                )
                            else:
                                nagvis_maps.add(map_file)
                                map_h.write("define global {\n")
                                for key in sorted(map_dict.iterkeys()):
                                    value = map_dict[key]
                                    if type(value) == bool:
                                        value = "1" if value else "0"
                                    elif type(value) in [int, long]:
                                        value = "%d" % (value)
                                    map_h.write(u"    {}={}\n".format(key, value))
                                map_h.write("}\n")
                                map_h.close()
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
                        if host.mon_ext_host_id and host.mon_ext_host_id in ng_ext_hosts:
                            if self.gc["MD_TYPE"] == "icinga":
                                # handle for nagios 2, icinga
                                # act_hostext_info = mon_config("hostextinfo", host.full_name)
                                # act_hostext_info["host_name"] = host.full_name
                                for key in ["icon_image", "statusmap_image"]:
                                    act_host[key] = getattr(ng_ext_hosts[host.mon_ext_host_id], key)
                                # FIXME, not working for nagios2
                                # host_config_list.append(act_hostext_info)
                                # hostext_nc[host.full_name] = act_hostext_info
                            else:
                                self.log(
                                    "don't know how to handle hostextinfo for {}_version {:d}".format(
                                        self.gc["MD_TYPE"],
                                        self.gc["MD_VERSION"]
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                        # clear host from servicegroups
                        cur_gc["servicegroup"].clear_host(host.full_name)
                        # get check_commands and templates
                        conf_names = set(all_configs.get(host.full_name, []))
                        # cluster config names
                        cconf_names = set([_sc.mon_check_command.name for _sc in _bc.get_cluster("sc", host.pk)])
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
                        # print _bc.get_vars(host)
                        for conf_name in conf_names:
                            self._add_config(
                                host, act_host, conf_name, used_checks, _counter, _bc,
                                mccs_dict, cur_gc, act_def_serv, host_groups, host_is_actively_checked, host_config_list
                            )
                        # add cluster checks
                        mhc_checks = _bc.get_cluster("hc", host.pk)
                        if len(mhc_checks):
                            self.mach_log("adding {}".format(logging_tools.get_plural("host_cluster check", len(mhc_checks))))
                            for mhc_check in mhc_checks:
                                dev_names = [_bc.get_host(cur_dev).full_name for cur_dev in mhc_check.devices_list]
                                if len(dev_names):
                                    s_check = cur_gc["command"]["check_host_cluster"]
                                    serv_temp = _bc.serv_templates[mhc_check.mon_service_templ_id]
                                    serv_cgs = list(set(serv_temp.contact_groups).intersection(host_groups))
                                    sub_list = self.get_service(
                                        host,
                                        act_host,
                                        s_check,
                                        [
                                            special_commands.ArgTemplate(
                                                s_check,
                                                self._get_cc_name("{}{}{}".format(s_check.get_description(), _bc.join_char, mhc_check.description)),
                                                arg1=mhc_check.description,
                                                # arg2="@{:d}:".format(mhc_check.warn_value),
                                                # arg3="@{:d}:".format(mhc_check.error_value),
                                                arg2=mhc_check.warn_value,
                                                arg3=mhc_check.error_value,
                                                arg4=",".join(["$HOSTSTATEID:{}$".format(_dev_name) for _dev_name in dev_names]),
                                                arg5=",".join(dev_names),
                                            )
                                        ],
                                        act_def_serv,
                                        serv_cgs,
                                        host_is_actively_checked,
                                        serv_temp,
                                        cur_gc
                                    )
                                    host_config_list.extend(sub_list)
                                    _counter.ok(len(sub_list))
                                else:
                                    self.mach_log("ignoring empty host_cluster", logging_tools.LOG_LEVEL_WARN)
                        # add cluster service checks
                        msc_checks = _bc.get_cluster("sc", host.pk)
                        if len(msc_checks):
                            self.mach_log("adding {}".format(logging_tools.get_plural("service_cluster check", len(msc_checks))))
                            for msc_check in msc_checks:
                                if msc_check.mon_check_command.name in cur_gc["command"]:
                                    c_com = cur_gc["command"][msc_check.mon_check_command.name]
                                    dev_names = [(_bc.get_host(cur_dev).full_name, c_com.get_description()) for cur_dev in msc_check.devices_list]
                                    if len(dev_names):
                                        s_check = cur_gc["command"]["check_service_cluster"]
                                        serv_temp = _bc.serv_templates[msc_check.mon_service_templ_id]
                                        serv_cgs = list(set(serv_temp.contact_groups).intersection(host_groups))
                                        sub_list = self.get_service(
                                            host,
                                            act_host,
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
                                                                _dev_name, _bc.join_char, _srv_name
                                                            ).replace(",", " ") for _dev_name, _srv_name in dev_names
                                                        ]
                                                    ),
                                                )
                                            ],
                                            act_def_serv,
                                            serv_cgs,
                                            host_is_actively_checked,
                                            serv_temp,
                                            cur_gc,
                                        )
                                        host_config_list.extend(sub_list)
                                        _counter.ok(len(sub_list))
                                    else:
                                        self.mach_log("ignoring empty service_cluster", logging_tools.LOG_LEVEL_WARN)
                                else:
                                    self.mach_log(
                                        "check command '{}' not present in list of commands {}".format(
                                            msc_check.mon_check_command.name,
                                            ", ".join(sorted(cur_gc["command"].keys()))
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR,
                                    )
                        # add host dependencies
                        if use_host_deps:
                            for h_dep in _bc.get_dependencies("hd", host.pk):
                                # check reachability
                                _unreachable = [
                                    _bc.get_host(_dev_pk) for _dev_pk in h_dep.devices_list + h_dep.master_list if not _bc.get_host(_dev_pk).reachable
                                ]
                                if _unreachable:
                                    self.mach_log(
                                        "cannot create host dependency, {} unreachable: {}".format(
                                            logging_tools.get_plural("device", len(_unreachable)),
                                            ", ".join(sorted([unicode(_dev) for _dev in _unreachable])),
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR,
                                    )
                                else:
                                    act_host_dep = mon_config("hostdependency", "")
                                    _list = [_bc.get_host(dev_pk).full_name for dev_pk in h_dep.devices_list]
                                    _dep_list = [_bc.get_host(dev_pk).full_name for dev_pk in h_dep.master_list]
                                    if _list and _dep_list:
                                        if set(_list) & set(_dep_list):
                                            self.mach_log(
                                                "host_name and dependent_host_name share some hosts: {}".format(
                                                    ", ".join(sorted(list(set(_list) & set(_dep_list))))
                                                ),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                        else:
                                            act_host_dep["host_name"] = _list
                                            act_host_dep["dependent_host_name"] = _dep_list
                                            h_dep.feed_config(act_host_dep)
                                            host_config_list.append(act_host_dep)
                                    else:
                                        self.mach_log(
                                            "empty list or dependency_list for hostdependency.(host_name|dependency_name)",
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
                        # add service dependencies
                        if use_service_deps:
                            for s_dep in _bc.get_dependencies("sd", host.pk):
                                act_service_dep = mon_config("servicedependency", "")
                                if s_dep.mon_service_cluster_id:
                                    # check reachability
                                    _unreachable = [_bc.get_host(_dev_pk) for _dev_pk in s_dep.master_list if not _bc.get_host(_dev_pk).reachable]
                                    if _unreachable:
                                        self.mach_log(
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
                                                "child",
                                                all_configs,
                                                _bc.mcc_lut,
                                                _bc.mcc_lut_2,
                                                _bc.get_host(d_host),
                                                s_dep.dependent_mon_check_command_id
                                            )
                                        if all_ok:
                                            act_service_dep["dependent_service_description"] = host_service_id_util.create_host_service_description(
                                                dev_pk,
                                                _bc.mcc_lut_3[s_dep.dependent_mon_check_command_id],
                                                _bc.mcc_lut[s_dep.dependent_mon_check_command_id][1],
                                            )
                                            sc_check = cur_gc["command"]["check_service_cluster"]
                                            # FIXME, my_co.mcc_lut[...][1] should be mapped to check_command().get_description()
                                            act_service_dep["service_description"] = "{} / {}".format(
                                                sc_check.get_description(),
                                                _bc.mcc_lut[s_dep.mon_service_cluster.mon_check_command_id][1]
                                            )
                                            act_service_dep["host_name"] = _bc.get_host(s_dep.mon_service_cluster.main_device_id).full_name
                                            act_service_dep["dependent_host_name"] = [_bc.get_host(dev_pk).full_name for cur_dev in s_dep.master_list]
                                            s_dep.feed_config(act_service_dep)
                                            host_config_list.append(act_service_dep)
                                        else:
                                            self.mach_log("cannot add cluster_service_dependency", logging_tools.LOG_LEVEL_ERROR)
                                else:
                                    # check reachability
                                    _unreachable = [
                                        _bc.get_host(_dev_pk) for _dev_pk in s_dep.master_list + s_dep.devices_list if not _bc.get_host(_dev_pk).reachable
                                    ]
                                    if _unreachable:
                                        self.mach_log(
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
                                                "parent",
                                                all_configs,
                                                _bc.mcc_lut,
                                                _bc.mcc_lut_2,
                                                _bc.get_host(p_host),
                                                s_dep.mon_check_command_id
                                            )
                                        for d_host in s_dep.master_list:
                                            all_ok &= self._check_for_config(
                                                "child",
                                                all_configs,
                                                _bc.mcc_lut,
                                                _bc.mcc_lut_2,
                                                _bc.get_host(d_host),
                                                s_dep.dependent_mon_check_command_id
                                            )
                                        if all_ok:
                                            # FIXME, TODO, must unroll loops
                                            # act_service_dep["dependent_service_description"] = _bc.mcc_lut[s_dep.dependent_mon_check_command_id][1]
                                            act_service_dep["dependent_service_description"] = [
                                                host_service_id_util.create_host_service_description(
                                                    dev_pk,
                                                    _bc.mcc_lut_3[s_dep.dependent_mon_check_command_id],
                                                    _bc.mcc_lut[s_dep.dependent_mon_check_command_id][1],
                                                ) for dev_pk in s_dep.master_list
                                            ]
                                            # act_service_dep["service_description"] = _bc.mcc_lut[s_dep.mon_check_command_id][1]
                                            act_service_dep["service_description"] = [
                                                host_service_id_util.create_host_service_description(
                                                    dev_pk,
                                                    _bc.mcc_lut_3[s_dep.mon_check_command_id],
                                                    _bc.mcc_lut[s_dep.mon_check_command_id][1],
                                                ) for dev_pk in s_dep.devices_list
                                            ]
                                            act_service_dep["host_name"] = [_bc.get_host(dev_pk).full_name for dev_pk in s_dep.devices_list]
                                            act_service_dep["dependent_host_name"] = [_bc.get_host(dev_pk).full_name for dev_pk in s_dep.master_list]
                                            s_dep.feed_config(act_service_dep)
                                            host_config_list.append(act_service_dep)
                                        else:
                                            self.mach_log("cannot add service_dependency", logging_tools.LOG_LEVEL_ERROR)
                        host_nc.add_device(host_config_list, host)
                    else:
                        self.mach_log("Host {} is disabled".format(host.full_name))
            else:
                self.mach_log(
                    "No valid IPs found or no default_device_template found",
                    logging_tools.LOG_LEVEL_ERROR
                )
        info_str = "{:3d} ok, {:3d} w, {:3d} e ({:3d} {}) in {}".format(
            _counter.num_ok,
            _counter.num_warning,
            _counter.num_error,
            self.get_num_mach_logs(),
            "l " if _counter.num_error == 0 else "lw",
            logging_tools.get_diff_time_str(time.time() - start_time)
        )
        glob_log_str = "{}, {}".format(glob_log_str, info_str)
        self.log(glob_log_str)
        self.mach_log(info_str)
        if _counter.num_error > 0 or self.gc["DEBUG"]:
            _write_logs = True
        self.close_mach_log(write_logs=_write_logs)

    def _add_config(
        self, host, act_host, conf_name, used_checks, _counter, _bc, mccs_dict, cur_gc,
        act_def_serv, host_groups, host_is_actively_checked, host_config_list
    ):
        s_check = cur_gc["command"][conf_name]
        if s_check.name in used_checks:
            self.mach_log(
                "{} ({}) already used, ignoring .... (CHECK CONFIG !)".format(
                    s_check.get_description(),
                    s_check["command_name"],
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            _counter.warning()
        else:
            used_checks.add(s_check.name)
            # s_check: instance of check_command
            if s_check.mccs_id:
                # map to mccs (mon_check_command_special instance from backbone)
                mccs = mccs_dict[s_check.mccs_id]  #
                # store name of mccs (for parenting)
                mccs_name = mccs.name
                if mccs.parent_id:
                    # to get the correct command_line
                    com_mccs = mccs
                    # link to parent
                    mccs = mccs_dict[mccs.parent_id]
                else:
                    com_mccs = mccs
                # create lut entry to rewrite command name to mccs
                _rewrite_lut = {"check_command": mccs.md_name}
                sc_array = []
                try:
                    cur_special = special_commands.SPECIAL_DICT["special_{}".format(mccs.name)](
                        self.mach_log,
                        self,
                        # get mon_check_command (we need arg_ll)
                        s_check=cur_gc["command"][com_mccs.md_name],
                        parent_check=s_check,
                        host=host,
                        global_config=self.gc,
                        build_cache=_bc,
                        cache_mode=cur_gc.cache_mode,
                    )
                except:
                    self.log(
                        "unable to initialize special '{}': {}".format(
                            mccs.name,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                else:
                    # calling handle to return a list of checks with format
                    # [(description, [ARG1, ARG2, ARG3, ...]), (...)]
                    try:
                        if mccs_name != mccs.name:
                            # for meta specials
                            sc_array = cur_special(instance=mccs_name)
                        else:
                            sc_array = cur_special()
                    except:
                        exc_info = process_tools.exception_info()
                        self.log("error calling special {}:".format(mccs.name),
                                 logging_tools.LOG_LEVEL_CRITICAL)
                        for line in exc_info.log_lines:
                            self.log(" - {}".format(line), logging_tools.LOG_LEVEL_CRITICAL)
                        sc_array = []
                    finally:
                        cur_special.cleanup()
                    if cur_special.Meta.meta and sc_array and mccs_name == mccs.name:
                        # dive in subcommands, for instance 'all SNMP checks'
                        # check for configs not really configured
                        _dead_coms = [_entry for _entry in sc_array if not hasattr(mccs_dict[_entry], "check_command_name")]
                        if _dead_coms:
                            self.log("unconfigured checks: {}".format(", ".join(sorted(_dead_coms))), logging_tools.LOG_LEVEL_CRITICAL)
                        _com_names = [mccs_dict[_entry].check_command_name for _entry in sc_array if _entry not in _dead_coms]
                        for _com_name in _com_names:
                            self._add_config(
                                host, act_host, _com_name, used_checks, _counter, _bc,
                                mccs_dict, cur_gc, act_def_serv, host_groups, host_is_actively_checked, host_config_list
                            )
                        sc_array = []
            else:
                # no special command, empty rewrite_lut, simple templating
                _rewrite_lut = {}
                sc_array = [special_commands.ArgTemplate(s_check, s_check.get_description(), check_active=False if not s_check.is_active else None)]
                # contact_group is only written if contact_group is responsible for the host and the service_template
            if sc_array:
                serv_temp = _bc.serv_templates[s_check.get_template(act_def_serv.name)]
                serv_cgs = list(set(serv_temp.contact_groups).intersection(host_groups))
                sc_list = self.get_service(
                    host, act_host, s_check, sc_array, act_def_serv, serv_cgs, host_is_actively_checked, serv_temp, cur_gc, **_rewrite_lut
                )
                host_config_list.extend(sc_list)
                _counter.ok(len(sc_list))

    def _get_cc_name(self, in_str):
        if self.__safe_cc_name:
            return build_safe_name(in_str)
        else:
            return in_str

    def _check_for_config(self, c_type, all_configs, mcc_lut, mcc_lut_2, device, moncc_id):
        # configure mon check commands
        # import pprint
        # pprint.pprint(all_configs.get(device.full_name, []))
        ccoms = sum([mcc_lut_2.get(key, []) for key in all_configs.get(device.full_name, [])], [])
        # needed checkcommand
        nccom = mcc_lut[moncc_id]
        if nccom[0] in ccoms:
            return True
        else:
            self.mach_log(
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

    def _get_number_of_hosts(self, cur_gc, hosts):
        if hosts:
            h_filter = Q(name__in=hosts)
        else:
            h_filter = Q()
        # add master/slave related filters
        if cur_gc.master:
            pass
            # h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        else:
            h_filter &= Q(monitor_server=cur_gc.monitor_server)
        h_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        return device.objects.exclude(Q(is_meta_device=True)).filter(h_filter).count()

    def _create_host_config_files(self, _bc, cur_gc, d_map, hdep_from_topo):
        """
        d_map : distance map
        """
        start_time = time.time()
        # get contacts with access to all devices
        _uo = user.objects  # @UndefinedVariable
        all_access = list(
            [
                cur_u.login for cur_u in _uo.filter(
                    Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)
                ) if cur_u.has_perm("backbone.device.all_devices")
            ]
        )
        self.log("users with access to all devices: {}".format(", ".join(sorted(all_access))))
        server_idxs = [cur_gc.monitor_server.pk]
        # get netip-idxs of own host
        my_net_idxs = set(netdevice.objects.filter(Q(device__in=server_idxs)).filter(Q(enabled=True)).values_list("pk", flat=True))
        # get ext_hosts stuff
        ng_ext_hosts = self._get_mon_ext_hosts()
        # check_hosts
        if _bc.host_list:
            # not beautiful but working
            pk_list = []
            for full_h_name in _bc.host_list:
                try:
                    if full_h_name.count("."):
                        found_dev = device.objects.get(Q(name=full_h_name.split(".")[0]) & Q(domain_tree_node__full_name=full_h_name.split(".", 1)[1]))
                    else:
                        found_dev = device.objects.get(Q(name=full_h_name))
                except device.DoesNotExist:
                    pass
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
        if not _bc.single_build:
            h_filter &= Q(enabled=True) & Q(device_group__enabled=True)
            ac_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        # dictionary with all parent / slave relations
        ps_dict = {}
        _bc.set_host_list(device.objects.exclude(Q(is_meta_device=True)).filter(h_filter).values_list("pk", flat=True))
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
            # expand with parent
            while True:
                new_confs = set([ps_dict[cur_name] for cur_name in loc_config if cur_name in ps_dict]) - set(loc_config)
                if new_confs:
                    loc_config.extend(list(new_confs))
                else:
                    break
            all_configs[cur_dev.full_name] = loc_config
        # get config variables
        first_contactgroup_name = cur_gc["contactgroup"][cur_gc["contactgroup"].keys()[0]].name
        contact_group_dict = {}
        # get contact groups
        if _bc.host_list:
            host_info_str = logging_tools.get_plural("host", len(_bc.host_list))
            ct_groups = mon_contactgroup.objects.filter(Q(device_groups__device__name__in=_bc.host_list))
        else:
            host_info_str = "all"
            ct_groups = mon_contactgroup.objects.all()
        ct_group = ct_groups.prefetch_related("device_groups", "device_groups__device")
        for ct_group in ct_groups:
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
            if d_pk in _bc.host_pks:
                cur_host = _bc.get_host(d_pk)
                # populate valid_ips and invalid_ips
                getattr(cur_host, "valid_ips" if n_t in valid_nwt_list else "invalid_ips").setdefault(n_d, []).append((n_i, dom_name))
        host_nc = cur_gc["device.d"]
        # delete host if already present in host_table
        host_names = []
        for host_pk in _bc.host_pks:
            host = _bc.get_host(host_pk)  # , host in check_hosts.iteritems():
            host_names.append((host.full_name, host))
            if host.full_name in host_nc:
                # now very simple
                del host_nc[host.full_name]
        # mccs dict
        mccs_dict = {mccs.pk: mccs for mccs in mon_check_command_special.objects.all()}
        for _value in list(mccs_dict.values()):
            mccs_dict[_value.name] = _value
        for value in cur_gc["command"].values():
            if value.mccs_id:
                # add links back to check_command_names
                mccs_dict[value.mccs_id].check_command_name = value.name
        # caching object
        # build lookup-table
        self.send_pool_message("build_info", "device_count", cur_gc.monitor_server.full_name, len(host_names), target="syncer")
        nagvis_maps = set()
        for host_name, host in sorted(host_names):
            if _bc.build_dv:
                _bc.build_dv.count()
            self._create_single_host_config(
                _bc,
                cur_gc,
                host,
                d_map,
                my_net_idxs,
                all_access,
                # all_ms_connections,
                # all_ib_connections,
                # all_dev_relationships,
                contact_group_dict,
                ng_ext_hosts,
                all_configs,
                nagvis_maps,
                mccs_dict,
            )
        host_names = host_nc.keys()
        self.log("start parenting run")
        p_dict = {}
        # host_uuids = set([host_val.uuid for host_val in all_hosts_dict.itervalues() if host_val.full_name in host_names])
        _p_ok, _p_failed = (0, 0)
        for host_name in sorted(host_names):
            host = host_nc[host_name][0]
            if "possible_parents" in host and not _bc.single_build:
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
                                parent = _bc.get_host(parent_idx).full_name
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
                                    parent = _bc.get_host(parent_idx).full_name
                                    if parent in host_names and parent != host.name:
                                        if "_nagvis_map" in host_nc[parent][0]:
                                            local_nagvis_maps.append(host_nc[parent][0]["_nagvis_map"])
                            else:
                                self.log("parent_idx {:d} not in distance map, routing cache too old?".format(parent_idx), logging_tools.LOG_LEVEL_ERROR)
                if "_nagvis_map" not in host and local_nagvis_maps:
                    host["_nagvis_map"] = local_nagvis_maps[0]
                if parent_list:
                    host["parents"] = list(parent_list)
                    for cur_parent in parent_list:
                        p_dict.setdefault(cur_parent, []).append(host_name)
                    _p_ok += 1
                    if _bc.debug:
                        self.log("Setting parent of '{}' to {}".format(host_name, ", ".join(parent_list)), logging_tools.LOG_LEVEL_OK)
                else:
                    _p_failed += 1
                    self.log("Parenting problem for '{}', {:d} traces found".format(host_name, len(p_parents)), logging_tools.LOG_LEVEL_WARN)
                    if _bc.debug:
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
                                parent = _bc.get_host(parent_idx).full_name
                                self.log(
                                    "    {:>30s} (distance is {:3d}, in config: {})".format(
                                        unicode(parent),
                                        d_map[parent_idx],
                                        parent in host_names,
                                    )
                                )
            if "possible_parents" in host:
                del host["possible_parents"]
        self.log("end parenting run, {:d} ok, {:d} failed".format(_p_ok, _p_failed))
        if cur_gc.master and not _bc.single_build:
            if hdep_from_topo:
                # import pprint
                # pprint.pprint(p_dict)
                for parent, clients in p_dict.iteritems():
                    new_hd = mon_config("hostdependency", "")
                    new_hd["dependent_host_name"] = clients
                    new_hd["host_name"] = parent
                    new_hd["dependency_period"] = self.mon_host_dep.dependency_period.name
                    new_hd["execution_failure_criteria"] = self.mon_host_dep.execution_failure_criteria
                    new_hd["notification_failure_criteria"] = self.mon_host_dep.notification_failure_criteria
                    new_hd["inherits_parent"] = "1" if self.mon_host_dep.inherits_parent else "0"
                    cur_gc["hostdependency"].add_host_dependency(new_hd)
            self.log("created {}".format(logging_tools.get_plural("nagvis map", len(nagvis_maps))))
            # remove old nagvis maps
            nagvis_map_dir = os.path.join(self.gc["NAGVIS_DIR"], "etc", "maps")
            if os.path.isdir(nagvis_map_dir):
                skipped_customs = 0
                for entry in os.listdir(nagvis_map_dir):
                    if entry.startswith("custom_"):
                        skipped_customs += 1
                    else:
                        full_name = os.path.join(nagvis_map_dir, entry)
                        if full_name not in nagvis_maps:
                            self.log("removing old nagvis mapfile {}".format(full_name))
                            try:
                                os.unlink(full_name)
                            except:
                                self.log(
                                    "error removing {}: {}".format(
                                        full_name,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                if skipped_customs:
                    self.log("skipped removing of {}".format(logging_tools.get_plural("custom map", skipped_customs)))
                # create group maps
                dev_groups = device_group.objects.filter(
                    Q(enabled=True) &
                    Q(device_group__name__in=[os.path.basename(entry).split(".")[0] for entry in nagvis_maps])).distinct()
                self.log("creating maps for {}".format(logging_tools.get_plural("device group", len(dev_groups))))
                for dev_group in dev_groups:
                    map_name = os.path.join(nagvis_map_dir, "{}.cfg".format(dev_group.name.replace(" ", "_")))
                    file(map_name, "w").write(
                        "\n".join(
                            [
                                "define global {",
                                "    alias=Group {}".format(dev_group.name),
                                "}",
                            ]
                        )
                    )
            cache_dir = os.path.join(self.gc["NAGVIS_DIR"], "var")
            if os.path.isdir(cache_dir):
                rem_ok, rem_failed = (0, 0)
                for entry in os.listdir(cache_dir):
                    try:
                        full_name = os.path.join(cache_dir, entry)
                    except:
                        self.log("error building full_name from entry '{}'".format(entry), logging_tools.LOG_LEVEL_CRITICAL)
                        rem_failed += 1
                    else:
                        if os.path.isfile(full_name):
                            try:
                                os.unlink(full_name)
                            except:
                                rem_failed += 1
                            else:
                                rem_ok += 1
                self.log(
                    "cleaned cache_dir {} ({:d} ok, {:d} failed)".format(
                        cache_dir,
                        rem_ok,
                        rem_failed,
                    ),
                    logging_tools.LOG_LEVEL_ERROR if rem_failed else logging_tools.LOG_LEVEL_OK
                )
        end_time = time.time()
        self.log(
            "created configs for {} hosts in {}".format(
                host_info_str,
                logging_tools.get_diff_time_str(end_time - start_time),
            )
        )

    def get_service(self, host, act_host, s_check, sc_array, act_def_serv, serv_cgs, host_is_actively_checked, serv_temp, cur_gc, **kwargs):
        ev_defined = True if s_check.event_handler else False
        self.mach_log(
            "  adding check {:<30s} ({:2d} p), template {}, {}, {}".format(
                s_check["command_name"],
                len(sc_array),
                s_check.get_template(act_def_serv.name),
                "cg: {}".format(", ".join(sorted(serv_cgs))) if serv_cgs else "no cgs",
                "no evh" if not ev_defined else "evh is {} ({})".format(
                    s_check.event_handler.name,
                    "enabled" if (s_check.event_handler_enabled and host_is_actively_checked) else "disabled",
                ),
            )
        )
        ret_field = []

        # self.__host_service_map.add_host(host.full_name, host.pk)

        # for sc_name, sc in sc_array:
        for arg_temp in sc_array:
            # self.__host_service_map.add_service(arg_temp.info, s_check.check_command_pk)
            act_serv = mon_config("service", arg_temp.info)
            # event handlers
            if s_check.event_handler:
                act_serv["event_handler"] = s_check.event_handler.name
                act_serv["event_handler_enabled"] = "1" if (s_check.event_handler_enabled and host_is_actively_checked) else "0"
            if arg_temp.check_active is not None:
                # check flag overrides device specific setting
                act_serv["{}_checks_enabled".format("active" if arg_temp.check_active else "passive")] = 1
                act_serv["{}_checks_enabled".format("passive" if arg_temp.check_active else "active")] = 0
            else:
                if arg_temp.is_active:
                    act_serv["{}_checks_enabled".format("active" if host_is_actively_checked else "passive")] = 1
                    act_serv["{}_checks_enabled".format("passive" if host_is_actively_checked else "active")] = 0
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
            if not host_is_actively_checked:
                act_serv["check_freshness"] = 0
                act_serv["freshness_threshold"] = 3600
            if host_is_actively_checked and not cur_gc.master:
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
            # if act_host["check_command"] == "check-host-alive-2" and s_check["command_name"].startswith("check_ping"):
            #    self.mach_log(
            #        "   removing command %s because of %s" % (
            #            s_check["command_name"],
            #            act_host["check_command"]))
            # else:
            ret_field.append(act_serv)
        return ret_field

    def _get_target_ip_info(self, _bc, srv_net_idxs, net_devices, host):
        if _bc.cache_mode in ["ALWAYS"]:
            # use stored traces in mode ALWAYS
            traces = _bc.get_mon_trace(host, net_devices, srv_net_idxs)
        else:
            traces = []
        if not traces:
            pathes = self.router_obj.get_ndl_ndl_pathes(srv_net_idxs, net_devices.keys(), add_penalty=True)
            traces = []
            for penalty, cur_path in sorted(pathes):
                if cur_path[-1] in net_devices:
                    dev_path = self.router_obj.map_path_to_device(cur_path)
                    dev_path.reverse()
                    traces.append((penalty, cur_path[-1], dev_path))
            traces = sorted(traces)
            _bc.set_mon_trace(host, net_devices, srv_net_idxs, traces)
        if not traces:
            self.mach_log(
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


class host_service_map(object):
    """
    UNUSED

    here, we save the host and services we tell icinga
    then we can later resolve it when parsing the logs
    """
    class host_service_data(object):
        def __init__(self, hosts, services, timestamp):
            self.hosts = hosts
            self.services = services
            self.timestamp = timestamp

    @classmethod
    def get_mapping(cls, log):
        '''
        :return host_service_map.host_service_data:
        '''
        retval = None
        try:
            data = json.load(open(host_service_map._get_filepath()))
            retval = cls.host_service_data(data['hosts'], data['services'], data['timestamp'])
        except Exception as e:
            log("no host service map available: {}".format(e), logging_tools.LOG_LEVEL_WARN)
        return retval

    def __init__(self, log):
        self.clear()
        self.log = log
        self._collecting = False

    def clear(self):
        self._services = {}
        self._hosts = {}

    def start_collecting(self):
        self.clear()
        self._collecting = True

    def end_collecting(self):
        self._collecting = False

        data = {
            'hosts': self._hosts,
            'services': self._services,
            'timestamp': int(time.time())
        }

        self.log("writing host service mapping to {}".format(self._get_filepath()))
        with open(self._get_filepath(), "w") as mapping_file:
            json.dump(data, mapping_file)
            mapping_file.flush()

    def add_service(self, service, pk):
        if not self._collecting:
            self.log("collecting service mapping for {} outside of rebuild".format(service), logging_tools.LOG_LEVEL_WARN)

        if service in self._services and self._services[service] != pk:
            self.log("multiple definitions of service {}: {} and {}".format(service, self._services[service], pk), logging_tools.LOG_LEVEL_WARN)
        else:
            self._services[service] = pk

    def add_host(self, host, pk):
        if not self._collecting:
            self.log("collecting host mapping for {} outside of rebuild".format(host), logging_tools.LOG_LEVEL_WARN)

        if host in self._hosts and self._hosts[host] != pk:
            self.log("multiple definitions of host {}: {} and {}".format(host, self._hosts[host], pk), logging_tools.LOG_LEVEL_WARN)
        else:
            self._hosts[host] = pk

    @staticmethod
    def _get_filepath():
        return os.path.join(global_config['MD_BASEDIR'], 'var', 'host_service_map')
