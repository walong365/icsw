#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import codecs
import commands
import config_tools
import logging_tools
import networkx
import operator
import process_tools
import server_command
import signal
import stat
import threading_tools
import time
from lxml.builder import E # @UnresolvedImport

from initat.md_config_server.config import global_config, main_config, var_cache, all_commands, \
    all_service_groups, time_periods, all_contacts, all_contact_groups, all_host_groups, all_hosts, \
    all_hosts_extinfo, all_services, config_dir, device_templates, service_templates, nag_config
from initat.md_config_server import special_commands
from initat.md_config_server import constants

from django.db.models import Q
from django.db import connection
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
     mon_ext_host, mon_check_command, mon_period, mon_contact, \
     mon_contactgroup, mon_service_templ, netdevice, network, network_type, net_ip, \
     user, mon_host_cluster, mon_service_cluster, config, md_check_data_store, category, \
     category_tree, TOP_MONITORING_CATEGORY, mon_notification, config_str, config_int, host_check_command

try:
    import mk_livestatus
except ImportError:
    mk_livestatus = None

class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.__hosts_pending, self.__hosts_waiting = (set(), set())
        self.__nagios_lock_file_name = "%s/var/%s" % (global_config["MD_BASEDIR"], global_config["MD_LOCK_FILE"])
        connection.close()
        self.__mach_loggers = {}
        self.version = int(time.time())
        self.log("initial config_version is %d" % (self.version))
        # slave configs
        slave_servers = device.objects.filter(Q(device_config__config__name="monitor_slave")).select_related("domain_tree_node")
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        self.router_obj = config_tools.router_object(self.log)
        self.__gen_config = main_config(self, master_server, distributed=True if len(slave_servers) else False)
        self.send_pool_message("external_cmd_file", self.__gen_config.get_command_name())
        self.__slave_configs, self.__slave_lut = ({}, {})
        if len(slave_servers):
            self.log("found %s: %s" % (logging_tools.get_plural("slave_server", len(slave_servers)),
                                       ", ".join(sorted([cur_dev.full_name for cur_dev in slave_servers]))))
            for cur_dev in slave_servers:
                self.__slave_configs[cur_dev.pk] = main_config(
                    self,
                    cur_dev,
                    slave_name=cur_dev.full_name,
                    master_server=master_server,
                )
                self.__slave_lut[cur_dev.full_name] = cur_dev.pk
        else:
            self.log("no slave-servers found")
        self.register_func("rebuild_config", self._rebuild_config)
        self.register_func("sync_http_users", self._sync_http_users)
        self.register_func("file_content_info", self._file_content_info)
        self.register_func("check_for_redistribute", self._check_for_redistribute)
        self.register_func("build_host_config", self._build_host_config)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        for mach_logger in self.__mach_loggers.itervalues():
            mach_logger.close()
        self.__log_template.close()
    def send_command(self, src_id, srv_com):
        self.send_pool_message("send_command", "urn:uuid:%s:relayer" % (src_id), srv_com)
    def mach_log(self, what, lev=logging_tools.LOG_LEVEL_OK, mach_name=None, **kwargs):
        if mach_name is None:
            mach_name = self.__cached_mach_name
        else:
            self.__cached_mach_name = mach_name
        if mach_name not in self.__mach_loggers:
            self.__mach_loggers[mach_name] = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           mach_name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=self.zmq_context,
                init_logger=True)
        self.__mach_loggers[mach_name].log(lev, what)
        if kwargs.get("global_flag", False):
            self.log(what, lev)
    def close_mach_log(self):
        if self.__cached_mach_name:
            mach_name = self.__cached_mach_name
            self.__mach_loggers[mach_name].close()
            del self.__mach_loggers[mach_name]
    def _check_nagios_config(self):
        c_stat, out = commands.getstatusoutput("%s/bin/%s -v %s/etc/%s.cfg" % (
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"],
            global_config["MD_BASEDIR"],
            global_config["MD_TYPE"]))
        if c_stat:
            self.log("Checking the %s-configuration resulted in an error (%d)" % (
                global_config["MD_TYPE"],
                c_stat),
                     logging_tools.LOG_LEVEL_ERROR)
            ret_stat = 0
        else:
            self.log("Checking the %s-configuration returned no error" % (global_config["MD_TYPE"]))
            ret_stat = 1
        return ret_stat, out
    def _reload_nagios(self):
        start_daemon, restart_daemon = (False, False)
        cs_stat, cs_out = self._check_nagios_config()
        if not cs_stat:
            self.log("Checking the %s-config resulted in an error, not trying to (re)start" % (global_config["MD_TYPE"]), logging_tools.LOG_LEVEL_ERROR)
            self.log("error_output has %s" % (logging_tools.get_plural("line", cs_out.split("\n"))),
                     logging_tools.LOG_LEVEL_ERROR)
            for line in cs_out.split("\n"):
                if line.strip().lower().startswith("error"):
                    self.log(" - %s" % (line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if os.path.isfile(self.__nagios_lock_file_name):
                try:
                    pid = file(self.__nagios_lock_file_name, "r").read().strip()
                except:
                    self.log("Cannot read %s LockFile named '%s', trying to start %s" % (
                        global_config["MD_TYPE"],
                        self.__nagios_lock_file_name,
                        global_config["MD_TYPE"]),
                             logging_tools.LOG_LEVEL_WARN)
                    start_daemon = True
                else:
                    pid = file(self.__nagios_lock_file_name).read().strip()
                    try:
                        pid = int(pid)
                    except:
                        self.log("PID read from '%s' is not an integer (%s, %s), trying to restart %s" % (
                            self.__nagios_lock_file_name,
                            str(pid),
                            process_tools.get_except_info(),
                            global_config["MD_TYPE"]),
                                 logging_tools.LOG_LEVEL_ERROR)
                        restart_daemon = True
                    else:
                        try:
                            os.kill(pid, signal.SIGHUP)
                        except OSError:
                            self.log("Error signaling pid %d with SIGHUP (%d), trying to restart %s (%s)" % (
                                pid,
                                signal.SIGHUP,
                                global_config["MD_TYPE"],
                                process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                            restart_daemon = True
                        else:
                            self.log("Successfully signaled pid %d with SIGHUP (%d)" % (pid, signal.SIGHUP))
            else:
                self.log(
                    "Nagios LockFile '%s' not found, trying to start %s" % (
                        self.__nagios_lock_file_name,
                        global_config["MD_TYPE"]),
                    logging_tools.LOG_LEVEL_WARN)
                start_daemon = True
        if start_daemon:
            self.log("Trying to start %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s start" % (global_config["MD_TYPE"]))
        elif restart_daemon:
            self.log("Trying to restart %s via at-command" % (global_config["MD_TYPE"]))
            sub_stat, log_lines = process_tools.submit_at_command("/etc/init.d/%s restart" % (global_config["MD_TYPE"]))
        else:
            log_lines = []
        if log_lines:
            for log_line in log_lines:
                self.log(log_line)
    def _check_for_redistribute(self, *args, **kwargs):
        for slave_config in self.__slave_configs.itervalues():
            slave_config.check_for_resend()
    def _file_content_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        slave_name = srv_com["slave_name"].text
        if slave_name in self.__slave_lut:
            self.__slave_configs[self.__slave_lut[slave_name]].file_content_info(srv_com)
        else:
            self.log("unknown slave_name '%s'" % (slave_name), logging_tools.LOG_LEVEL_ERROR)
    def _sync_http_users(self, *args, **kwargs):
        self.log("syncing http-users")
        self.__gen_config._create_access_entries()
    def _build_host_config(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = srv_com.xpath(None, ".//device_list/device/@pk")
        dev_names = [cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=dev_pks))]
        self.log("starting single build with %s: %s" % (
            logging_tools.get_plural("device", len(dev_names)),
            ", ".join(sorted(dev_names))))
        srv_com["result"] = self._rebuild_config(*dev_names)
        srv_com.set_result("rebuilt config for %s" % (", ".join(dev_names)), server_command.SRV_REPLY_STATE_OK)
        self.send_pool_message("send_command", src_id, unicode(srv_com))
    def _rebuild_config(self, *args, **kwargs):
        h_list = list(args)
        single_build = True if len(args) > 0 else False
        cache_mode = kwargs.get("cache_mode", "???")
        if cache_mode not in special_commands.CACHE_MODES:
            # take first cache mode
            cache_mode = special_commands.DEFAULT_CACHE_MODE
        self.log("rebuild_config called, single_build is %s, cache_mode is %s" % (
            str(single_build),
            cache_mode))
        if not single_build:
            self.version += 1
            self.log("config_version for full build is %d" % (self.version))
        if global_config["DEBUG"]:
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
                description="mon config rebuild on %s" % (self.__gen_config.monitor_server.full_name),
                var_type="i")
        # fetch SNMP-stuff of cluster and initialise var cache
        var_stack = var_cache(cdg)
        rebuild_gen_config = False
        if not h_list:
            self.log(
                "rebuilding complete config (for master and %s)" % (
                    logging_tools.get_plural("slave", len(self.__slave_configs))
                )
            )
            rebuild_gen_config = True
        else:
            # FIXME, handle host-related config for only specified slaves
            self.log(
                "rebuilding config for %s: %s" % (
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
                # clean device and service entries
                for key in constants.SINGLE_BUILD_MAPS:
                    self.__gen_config[key].refresh(self.__gen_config)
            self.router_obj.check_for_update()
            # build distance map
            cur_dmap = self._build_distance_map(self.__gen_config.monitor_server, show_unroutable=not single_build)
            total_hosts = sum([self._get_number_of_hosts(cur_gc, h_list) for cur_gc in [self.__gen_config] + self.__slave_configs.values()])
            if build_dv:
                self.log("init gauge with max=%d" % (total_hosts))
                build_dv.init_as_gauge(total_hosts)
            gc_list = [self.__gen_config]
            if not single_build:
                gc_list.extend(self.__slave_configs.values())
            for cur_gc in gc_list:
                cur_gc.cache_mode = cache_mode
                if cur_gc.master and not single_build:
                    # recreate access files
                    cur_gc._create_access_entries()
                self._create_host_config_files(build_dv, cur_gc, h_list, dev_templates, serv_templates, var_stack, cur_dmap, single_build)
                if not single_build:
                    # refresh implies _write_entries
                    cur_gc.refresh()
                    if not cur_gc.master:
                        cur_gc._write_entries()
                        cur_gc.distribute(self.version)
            if build_dv:
                build_dv.delete()
        if not single_build:
            cfgs_written = self.__gen_config._write_entries()
            if bc_valid and (cfgs_written or rebuild_gen_config):
                # send reload to remote instance ?
                self._reload_nagios()
        else:
            cur_gc = self.__gen_config
            res_node = E.config(
                *sum([cur_gc[key].get_xml() for key in constants.SINGLE_BUILD_MAPS], [])
            )
        if global_config["DEBUG"]:
            tot_query_count = len(connection.queries) - cur_query_count
            self.log("queries issued: %d" % (tot_query_count))
            # for q_idx, act_sql in enumerate(connection.queries[cur_query_count:], 1):
            #    self.log("%5d %s" % (q_idx, act_sql["sql"][:180]))
        if single_build:
            return res_node
    def _build_distance_map(self, root_node, show_unroutable=True):
        self.log("building distance map, root node is '%s'" % (root_node))
        # exclude all without attached netdevices
        dm_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.filter(Q(enabled=True)).exclude(netdevice=None).prefetch_related("netdevice_set")])
        nd_dict = {}
        for dev_pk, nd_pk in netdevice.objects.all().values_list("device", "pk"):
            nd_dict.setdefault(dev_pk, set()).add(nd_pk)
        nd_lut = dict([(value[0], value[1]) for value in netdevice.objects.all().values_list("pk", "device") if value[1] in dm_dict.keys()])
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
            self.log("dm_run %3d, %s, %s" % (
                cur_iter,
                logging_tools.get_plural("source node", len(src_nodes)),
                logging_tools.get_plural("dest node", len(dst_nodes))))
            src_nds = reduce(operator.ior, [nd_dict[key] for key in src_nodes], set())
            # dst_nds = reduce(operator.ior, [nd_dict[key] for key in dst_nodes], set())
            # build list of src_nd, dst_nd tuples
            nb_list = []
            for src_nd in src_nds:
                try:
                    for dst_nd in networkx.all_neighbors(self.router_obj.nx, src_nd):
                        if dst_nd not in src_nds:
                            nb_list.append((src_nd, dst_nd))
                except networkx.exception.NetworkXError:
                    self.log("netdevice %s is not in graph: %s" % (src_nd,
                                                                   process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            for src_nd, dst_nd, in nb_list:
                if src_nd in all_nd_pks and dst_nd in all_nd_pks:
                    src_dev, dst_dev = (dm_dict[nd_lut[src_nd]], dm_dict[nd_lut[dst_nd]])
                    new_level = src_dev.md_dist_level + 1
                    if dst_dev.md_dist_level >= 0 and new_level > dst_dev.md_dist_level:
                        self.log("pushing node %s farther away from root (%d => %d)" % (
                            unicode(dst_dev),
                            dst_dev.md_dist_level,
                            new_level))
                    dst_dev.md_dist_level = max(dst_dev.md_dist_level, new_level)
                    max_level = max(max_level, dst_dev.md_dist_level)
                    run_again = True
                else:
                    self.log("dropping link (%d, %d), devices disabled?" % (src_nd, dst_nd), logging_tools.LOG_LEVEL_WARN)
            if not run_again:
                break
        self.log("max distance level: %d" % (max_level))
        nodes_ur = [unicode(value) for value in dm_dict.itervalues() if value.md_dist_level < 0]
        if nodes_ur and show_unroutable:
            self.log("%s: %s" % (
                logging_tools.get_plural("unroutable node", len(nodes_ur)),
                ", ".join(sorted(nodes_ur))
            )
                     )
        for level in xrange(max_level + 1):
            self.log("nodes in level %d: %s" % (
                level,
                len([True for value in dm_dict.itervalues() if value.md_dist_level == level])
            )
                     )
        return dict([(key, value.md_dist_level) for key, value in dm_dict.iteritems()])
    def _create_general_config(self):
        start_time = time.time()
        self._check_image_maps()
        self._create_gen_config_files([self.__gen_config] + self.__slave_configs.values())
        end_time = time.time()
        self.log("creating the total general config took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
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
            # hosts_extinfo
            cur_gc.add_config(all_hosts_extinfo(cur_gc, self))
            # services
            cur_gc.add_config(all_services(cur_gc, self))
            # device dir
            cur_gc.add_config_dir(config_dir("device", cur_gc, self))
            end_time = time.time()
            cur_gc.log("created host_configs in %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _get_mon_ext_hosts(self):
        return dict([(cur_ext.pk, cur_ext) for cur_ext in mon_ext_host.objects.all()])
    def _check_image_maps(self):
        min_width, max_width, min_height, max_height = (16, 64, 16, 64)
        all_image_stuff = self._get_mon_ext_hosts()
        self.log("Found %s" % (logging_tools.get_plural("ext_host entry", len(all_image_stuff.keys()))))
        logos_dir = "%s/share/images/logos" % (global_config["MD_BASEDIR"])
        base_names = set()
        if os.path.isdir(logos_dir):
            logo_files = os.listdir(logos_dir)
            for log_line in [entry.split(".")[0] for entry in logo_files]:
                if log_line not in base_names:
                    if "%s.png" % (log_line) in logo_files and "%s.gd2" % (log_line) in logo_files:
                        base_names.add(log_line)
        name_case_lut = {}
        if base_names:
            stat, out = commands.getstatusoutput("file %s" % (" ".join([os.path.join(logos_dir, "%s.png" % (entry)) for entry in base_names])))
            if stat:
                self.log("error getting filetype of %s" % (logging_tools.get_plural("logo", len(base_names))), logging_tools.LOG_LEVEL_ERROR)
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
                            self.log("width or height (%d x %d) not in range ([%d - %d] x [%d - %d])" % (
                                width,
                                height,
                                min_width,
                                max_width,
                                min_height,
                                max_height))
        name_lut = dict([(eh.name.lower(), pk) for pk, eh in all_image_stuff.iteritems()])
        all_images_present = set([eh.name for eh in all_image_stuff.values()])
        all_images_present_lower = set([name.lower() for name in all_images_present])
        base_names_lower = set([name.lower() for name in base_names])
        new_images = base_names_lower - all_images_present_lower
        del_images = all_images_present_lower - base_names_lower
        present_images = base_names_lower & all_images_present_lower
        for new_image in new_images:
            mon_ext_host(name=new_image,
                         icon_image="%s.png" % (new_image),
                         statusmap_image="%s.gd2" % (new_image)).save()
        for p_i in present_images:
            img_stuff = all_image_stuff[name_lut[p_i]]
            # check for wrong case
            if img_stuff.icon_image != "%s.png" % (name_case_lut[img_stuff.name]):
                # correct case
                img_stuff.icon_image = "%s.png" % (name_case_lut[img_stuff.name])
                img_stuff.statusmap_image = "%s.gd2" % (name_case_lut[img_stuff.name])
                img_stuff.save()
        if del_images:
            mon_ext_host.objects.filter(Q(name__in=del_images)).delete()
        self.log("Inserted %s, deleted %s" % (
            logging_tools.get_plural("new ext_host_entry", len(new_images)),
            logging_tools.get_plural("ext_host_entry", len(del_images))))
    def _get_int_str(self, i_val, size=3):
        if i_val:
            return ("%%%dd" % (size)) % (i_val)
        else:
            return ("%%%ds" % (size)) % ("-")
    def _create_single_host_config(self,
                                   cur_gc,
                                   host,
                                   check_hosts,
                                   d_map,
                                   my_net_idxs,
                                   all_hosts_dict,
                                   dev_templates,
                                   serv_templates,
                                   var_stack,
                                   all_access,
                                   # not used right now
                                   # all_ms_connections,
                                   # all_ib_connections,
                                   # all_dev_relationships,
                                   contact_group_dict,
                                   ng_ext_hosts,
                                   all_configs,
                                   nagvis_maps,
                                   single_build,
                                   ):
        start_time = time.time()
        # set some vars
        host_nc = cur_gc["device.d"]
        if cur_gc.master:
            check_for_passive_checks = True
        else:
            check_for_passive_checks = False
        checks_are_active = True
        if check_for_passive_checks:
            if host.monitor_server_id and host.monitor_server_id != cur_gc.monitor_server.pk:
                checks_are_active = False
        # h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        self.__cached_mach_name = host.full_name
        self.mach_log("-------- %s ---------" % ("master" if cur_gc.master else "slave %s" % (cur_gc.slave_name)))
        glob_log_str = "Starting build of config for device %32s%s (%10s), distance level is %3d" % (
            host.full_name[:32],
            "*" if len(host.name) > 32 else " ",
            "active" if checks_are_active else "passive",
            d_map.get(host.pk, -1),
        )
        self.mach_log("Starting build of config", logging_tools.LOG_LEVEL_OK, host.full_name)
        num_ok, num_warning, num_error = (0, 0, 0)
        # print "%s : %s" % (host["name"], host["identifier"])
        if host.valid_ips:
            net_devices = host.valid_ips
        elif host.invalid_ips:
            self.mach_log("Device %s has no valid netdevices associated, using invalid ones..." % (host.full_name),
                          logging_tools.LOG_LEVEL_WARN)
            net_devices = host.invalid_ips
        else:
            self.mach_log("Device %s has no netdevices associated, skipping..." % (host.full_name),
                          logging_tools.LOG_LEVEL_ERROR)
            num_error += 1
            net_devices = {}
        if net_devices:
            # print mni_str_s, mni_str_d, dev_str_s, dev_str_d
            # get correct netdevice for host
            if host.name == global_config["SERVER_SHORT_NAME"]:
                valid_ips, traces = ([("127.0.0.1", "localdomain")], [(1, 0, [host.pk])])
            else:
                valid_ips, traces = self._get_target_ip_info(my_net_idxs, net_devices, all_hosts_dict[host.pk], check_hosts)
                if not valid_ips:
                    num_error += 1
            act_def_dev = dev_templates[host.mon_device_templ_id or 0]
            if not valid_ips and single_build:
                valid_ips = [("0.0.0.0", host.full_name), ]
                self.mach_log("no ips found using %s as dummy IP" % (str(valid_ips)))
            if valid_ips and act_def_dev:
                host.domain_names = [cur_ip[1] for cur_ip in valid_ips if cur_ip[1]]
                valid_ip = valid_ips[0][0]
                host.valid_ip = valid_ip
                self.mach_log("Found %s for host %s : %s, using %s" % (
                    logging_tools.get_plural("target ip", len(valid_ips)),
                    host.full_name,
                    ", ".join(["%s%s" % (cur_ip, " (.%s)" % (dom_name) if dom_name else "") for cur_ip, dom_name in valid_ips]),
                    host.valid_ip))
                if not serv_templates.has_key(act_def_dev.mon_service_templ_id):
                    self.log("Default service_template not found in service_templates", logging_tools.LOG_LEVEL_WARN)
                else:
                    act_def_serv = serv_templates[act_def_dev.mon_service_templ_id]
                    # tricky part: check the actual service_template for the various services
                    self.mach_log("Using default device_template '%s' and service_template '%s' for host %s" % (
                        act_def_dev.name,
                        act_def_serv.name,
                        host.full_name))
                    # get device variables
                    dev_variables, var_info = var_stack.get_vars(host)
                    host.dev_variables = dev_variables
                    self.mach_log("device has %s (%s)" % (
                        logging_tools.get_plural("device_variable", len(host.dev_variables.keys())),
                        ", ".join(["%s: %d" % (key, var_info[key]) for key in ["d", "g", "c"]])
                        ))
                    # now we have the device- and service template
                    host_config_list = []
                    act_host = nag_config("host", host.full_name)
                    host_config_list.append(act_host)
                    act_host["host_name"] = host.full_name
                    act_host["display_name"] = host.full_name
                    # action url
                    if global_config["ENABLE_PNP"] or global_config["ENABLE_COLLECTD"]:
                        act_host["process_perf_data"] = 1 if host.enable_perfdata else 0
                        if host.enable_perfdata:
                            act_host["action_url"] = "%s/index.php/graph?host=$HOSTNAME$&srv=_HOST_" % (global_config["PNP_URL"])
                    act_host["alias"] = ",".join(sorted(list(set([entry for entry in [host.alias, host.name, host.full_name] + ["%s.%s" % (host.name, dom_name) for dom_name in host.domain_names] if entry.strip()]))))
                    act_host["address"] = host.valid_ip
                    # check for parents
                    parents = []
                    # rule 1: APC Masterswitches have their bootserver set as parent
                    if host.device_type.identifier in ["AM", "IBC"] and host.bootserver_id:
                        parents.append(all_hosts_dict[host.bootserver_id].full_name)
                    # rule 2: Devices connected to an apc have this apc set as parent
                    # elif all_ms_connections.has_key(host.pk):
                        # for pd in all_ms_connections[host.pk]:
                            # if all_hosts_dict[pd]["name"] not in parents:
                                # # disable circular references
                                # if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                    # self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                # else:
                                    # parents.append(all_hosts_dict[pd]["name"])
                    # rule 3: Devices connected to an ibc have this ibc set as parent
                    # elif all_ib_connections.has_key(host.pk):
                        # for pd in all_ib_connections[host.pk]:
                            # if all_hosts_dict[pd]["name"] not in parents:
                                # # disable circular references
                                # if host["identifier"] == "H" and all_hosts_dict[pd]["bootserver"] == host["device_idx"]:
                                    # self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[pd]["name"]))
                                # else:
                                    # parents.append(all_hosts_dict[pd]["name"])
                    # rule 4: Devices have their xen/vmware-parent set as parent
                    # elif all_dev_relationships.has_key(host.pk) and all_hosts_dict.has_key(all_dev_relationships[host.pk]["host_device"]):
                        # act_rel = all_dev_relationships[host.pk]
                        # # disable circular references
                        # if host["identifier"] == "H" and host["name"] == global_config["SERVER_SHORT_NAME"]:
                            # self.mach_log("Disabling parent %s to prevent circular reference" % (all_hosts_dict[act_rel["host_device"]]["name"]))
                        # else:
                            # parents.append(all_hosts_dict[act_rel["host_device"]]["name"])
                    # rule 5: Check routing
                    else:
                        self.mach_log("No direct parent(s) found, registering trace")
                        if host.bootserver_id != host.pk and host.bootserver_id:
                            traces.append((1, 0, [host.pk]))
                        if traces and len(traces[0][2]) > 1:
                            act_host["possible_parents"] = traces
                            # print traces, host["name"], all_hosts_dict[traces[1]]["name"]
                            # parents += [all_hosts_dict[traces[1]]["name"]]
                        # print "No parent set for %s" % (host["name"])
                    if parents:
                        self.mach_log("settings %s: %s" % (
                            logging_tools.get_plural("parent", len(parents)),
                            ", ".join(sorted(parents))))
                        act_host["parents"] = ",".join(parents)
                    act_host["retain_status_information"] = global_config["RETAIN_HOST_STATUS"]
                    act_host["max_check_attempts"] = act_def_dev.max_attempts
                    act_host["notification_interval"] = act_def_dev.ninterval
                    act_host["notification_period"] = cur_gc["timeperiod"][act_def_dev.mon_period_id]["name"]
                    act_host["checks_enabled"] = 1
                    act_host["%s_checks_enabled" % ("active" if checks_are_active else "passive")] = 1
                    act_host["%s_checks_enabled" % ("passive" if checks_are_active else "active")] = 0
                    act_host["flap_detection_enabled"] = 1 if (host.flap_detection_enabled and act_def_dev.flap_detection_enabled) else 0
                    if host.flap_detection_enabled and act_def_dev.flap_detection_enabled:
                        # add flap fields
                        act_host["low_flap_threshold"] = act_def_dev.low_flap_threshold
                        act_host["high_flap_threshold"] = act_def_dev.high_flap_threshold
                        n_field = []
                        for short, f_name in [("o", "up"), ("d", "down"), ("u", "unreachable")]:
                            if getattr(act_def_dev, "flap_detect_%s" % (f_name)):
                                n_field.append(short)
                        if not n_field:
                            n_field.append("o")
                        act_host["flap_detection_options"] = ",".join(n_field)
                    if checks_are_active and not cur_gc.master:
                        # trace changes
                        act_host["obsess_over_host"] = 1
                    host_groups = set(contact_group_dict.get(host.full_name, []))
                    # print "*", host, set(contact_group_dict.get(host.full_name, []))
                    act_host["contact_groups"] = ",".join(host_groups) if host_groups else global_config["NONE_CONTACT_GROUP"]
                    # deep copy needed here
                    c_list = [entry for entry in all_access]
                    # set alias
                    if host.device_group.user_set.all():
                        c_list.extend([cur_u.login for cur_u in host.device_group.user_set.filter(Q(mon_contact__pk__gt=0))])
                    if c_list:
                        act_host["contacts"] = ",".join(c_list)
                    self.mach_log("contact groups for host: %s" % (
                        ", ".join(sorted(host_groups)) or "none"))
                    if host.monitor_checks or single_build:
                        if host.valid_ip == "0.0.0.0":
                            self.mach_log("IP address is '%s', host is assumed to be always up" % (unicode(host.valid_ip)))
                            act_host["check_command"] = "check-host-ok"
                        else:
                            if act_def_dev.host_check_command:
                                act_host["check_command"] = act_def_dev.host_check_command.name
                            else:
                                self.log("dev_template has no host_check_command set", logging_tools.LOG_LEVEL_ERROR)
                        # check for nagvis map
                        if host.automap_root_nagvis and cur_gc.master:
                            map_file = os.path.join(global_config["NAGVIS_DIR"], "etc", "maps", "%s.cfg" % (host.full_name.encode("ascii", errors="ignore")))
                            map_dict = {
                                "sources"      : "automap",
                                "alias"        : host.comment or host.full_name,
                                "parent_map"   : "",
                                "iconset"      : "std_big",
                                "child_layers" : 10,
                                "backend_id"   : "live_1",
                                "root"         : host.full_name,
                                "label_show"   : "1",
                                "label_border" : "transparent",
                                "render_mode"  : "directed",
                                "rankdir"      : "TB",
                                "width"        : 800,
                                "height"       : 600,
                                "header_menu"  : True,
                                "hover_menu"   : True,
                                "context_menu" : True,
                                # parent map
                                "parent_map"   : host.device_group.name.replace(" ", "_"),
                                # special flag for anovis
                                "use_childs_for_overview_icon" : False,
                            }
                            try:
                                map_h = codecs.open(map_file, "w", "utf-8")
                            except:
                                self.mach_log("cannot open %s: %s" % (map_file,
                                                                      process_tools.get_except_info()),
                                              logging_tools.LOG_LEVEL_CRITICAL)
                            else:
                                nagvis_maps.add(map_file)
                                map_h.write("define global {\n")
                                for key, value in map_dict.iteritems():
                                    if type(value) == bool:
                                        value = "1" if value else "0"
                                    elif type(value) in [int, long]:
                                        value = "%d" % (value)
                                    map_h.write(u"    %s=%s\n" % (key, value))
                                map_h.write("}\n")
                                map_h.close()
                        # check for notification options
                        not_a = []
                        for what, shortcut in [("nrecovery", "r"), ("ndown", "d"), ("nunreachable", "u"), ("nflapping", "f"), ("nplanned_downtime", "s")]:
                            if getattr(act_def_dev, what):
                                not_a.append(shortcut)
                        if not not_a:
                            not_a.append("n")
                        act_host["notification_options"] = ",".join(not_a)
                        # check for hostextinfo
                        if host.mon_ext_host_id and ng_ext_hosts.has_key(host.mon_ext_host_id):
                            if (global_config["MD_TYPE"] == "nagios" and global_config["MD_VERSION"] > 1) or (global_config["MD_TYPE"] == "icinga"):
                                # handle for nagios 2
                                act_hostext_info = nag_config("hostextinfo", host.full_name)
                                act_hostext_info["host_name"] = host.full_name
                                for key in ["icon_image", "statusmap_image"]:
                                    act_hostext_info[key] = getattr(ng_ext_hosts[host.mon_ext_host_id], key)
                                # FIXME, not working for nagios2
                                host_config_list.append(act_hostext_info)
                                # hostext_nc[host.full_name] = act_hostext_info
                            else:
                                self.log("don't know how to handle hostextinfo for %s_version %d" % (
                                    global_config["MD_TYPE"],
                                    global_config["MD_VERSION"]),
                                         logging_tools.LOG_LEVEL_ERROR)
                        # clear host from servicegroups
                        cur_gc["servicegroup"].clear_host(host.full_name)
                        # get check_commands and templates
                        conf_names = set(all_configs.get(host.full_name, []))
                        # cluster config names
                        cconf_names = set(host.devs_mon_service_cluster.all().values_list("mon_check_command__name", flat=True))
                        # build lut
                        conf_dict = dict([(
                            cur_c["command_name"], cur_c) for cur_c in cur_gc["command"].values() if
                                          (cur_c.get_config() in conf_names and (not(cur_c.get_device()) or cur_c.get_device() == host.pk)) or
                                          cur_c["command_name"] in cconf_names])
                        # old code, use only_ping config
                        # if host["identifier"] == "NB" or host["identifier"] == "AM" or host["identifier"] == "S":
                        #    # set config-dict for netbotzes, APC Masterswitches and switches to ping
                        #    conf_dict = dict([(x["command_name"], x) for x in self.__gen_config["checkcommand"]["struct"].values() if x["command_name"].startswith("check_ping")])
                        # print host["name"], conf_dict
                        # now conf_dict is a list of all service-checks defined for this host
                        # pprint.pprint(conf_dict)
                        # list of already used checks
                        used_checks = set()
                        conf_names = sorted(conf_dict.keys())
                        for conf_name in conf_names:
                            s_check = conf_dict[conf_name]
                            if s_check.name in used_checks:
                                self.mach_log("%s (%s) already used, ignoring .... (CHECK CONFIG !)" % (
                                    s_check.get_description(),
                                    s_check["command_name"]), logging_tools.LOG_LEVEL_WARN)
                                num_warning += 1
                            else:
                                used_checks.add(s_check.name)
                                special = s_check.get_special()
                                if special:
                                    sc_array = []
                                    try:
                                        cur_special = getattr(special_commands, "special_%s" % (special.lower()))(
                                            self,
                                            s_check,
                                            host, global_config, cache_mode=cur_gc.cache_mode)
                                    except:
                                        self.log("unable to initialize special '%s': %s" % (
                                            special,
                                            process_tools.get_except_info()),
                                                 logging_tools.LOG_LEVEL_CRITICAL)
                                    else:
                                        # calling handle to return a list of checks with format
                                        # [(description, [ARG1, ARG2, ARG3, ...]), (...)]
                                        try:
                                            sc_array = cur_special()
                                        except:
                                            exc_info = process_tools.exception_info()
                                            self.log("error calling special %s:" % (special),
                                                     logging_tools.LOG_LEVEL_CRITICAL)
                                            for line in exc_info.log_lines:
                                                self.log(" - %s" % (line), logging_tools.LOG_LEVEL_CRITICAL)
                                            sc_array = []
                                        finally:
                                            cur_special.cleanup()
                                else:
                                    sc_array = [special_commands.arg_template(s_check, s_check.get_description())]
                                    # contact_group is only written if contact_group is responsible for the host and the service_template
                                serv_temp = serv_templates[s_check.get_template(act_def_serv.name)]
                                serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                sc_list = self.get_service(host, act_host, s_check, sc_array, act_def_serv, serv_cgs, checks_are_active, serv_temp, cur_gc)
                                host_config_list.extend(sc_list)
                                num_ok += len(sc_list)
                        # add cluster checks
                        mhc_checks = host.main_mon_host_cluster.all().prefetch_related("devices")
                        if len(mhc_checks):
                            self.mach_log("adding %s" % (logging_tools.get_plural("host_cluster check", len(mhc_checks))))
                            for mhc_check in mhc_checks:
                                dev_names = ",".join(["$HOSTSTATEID:%s$" % (cur_dev.full_name) for cur_dev in mhc_check.devices.all()])
                                if dev_names.strip():
                                    s_check = cur_gc["command"]["check_host_cluster"]
                                    serv_temp = serv_templates[mhc_check.mon_service_templ_id]
                                    serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                    sub_list = self.get_service(
                                        host,
                                        act_host,
                                        s_check,
                                        [special_commands.arg_template(
                                            s_check,
                                            "%s %s" % (s_check.get_description(), mhc_check.description),
                                            arg1=mhc_check.description,
                                            arg2=mhc_check.warn_value,
                                            arg3=mhc_check.error_value,
                                            arg4=dev_names)
                                         ],
                                        act_def_serv,
                                        serv_cgs,
                                        checks_are_active,
                                        serv_temp,
                                        cur_gc)
                                    host_config_list.extend(sub_list)
                                    num_ok += len(sub_list)
                                else:
                                    self.mach_log("ignoring empty host_cluster", logging_tools.LOG_LEVEL_WARN)
                        # add service checks
                        msc_checks = host.main_mon_service_cluster.all().prefetch_related("devices")
                        if len(msc_checks):
                            self.mach_log("adding %s" % (logging_tools.get_plural("service_cluster check", len(msc_checks))))
                            for msc_check in msc_checks:
                                c_com = cur_gc["command"][msc_check.mon_check_command.name]
                                dev_names = ",".join(["$SERVICESTATEID:%s:%s$" % (cur_dev.full_name, c_com.get_description()) for cur_dev in msc_check.devices.all()])
                                if dev_names.strip():
                                    s_check = cur_gc["command"]["check_service_cluster"]
                                    serv_temp = serv_templates[msc_check.mon_service_templ_id]
                                    serv_cgs = set(serv_temp.contact_groups).intersection(host_groups)
                                    sub_list = self.get_service(
                                        host,
                                        act_host,
                                        s_check,
                                        [special_commands.arg_template(
                                            s_check,
                                            s_check.get_description(),
                                            arg1=msc_check.description,
                                            arg2=msc_check.warn_value,
                                            arg3=msc_check.error_value,
                                            arg4=dev_names)
                                         ],
                                        act_def_serv,
                                        serv_cgs,
                                        checks_are_active,
                                        serv_temp,
                                        cur_gc)
                                    host_config_list.extend(sub_list)
                                    num_ok += len(sub_list)
                                else:
                                    self.mach_log("ignoring empty service_cluster", logging_tools.LOG_LEVEL_WARN)
                        host_nc.add_device(host_config_list, host) # [act_host["name"]] = act_host
                    else:
                        self.mach_log("Host %s is disabled" % (host.full_name))
            else:
                self.mach_log("No valid IPs found or no default_device_template found", logging_tools.LOG_LEVEL_ERROR)
        info_str = "finished with %s warnings and %s errors (%3d ok) in %s" % (
            self._get_int_str(num_warning),
            self._get_int_str(num_error),
            num_ok,
            logging_tools.get_diff_time_str(time.time() - start_time))
        glob_log_str = "%s, %s" % (glob_log_str, info_str)
        self.log(glob_log_str)
        self.mach_log(info_str)
        self.close_mach_log()
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
        return device.objects.exclude(Q(device_type__identifier="MD")).filter(h_filter).count()
    def _create_host_config_files(self, build_dv, cur_gc, hosts, dev_templates, serv_templates, var_stack, d_map, single_build):
        """
        d_map : distance map
        """
        start_time = time.time()
        # get contacts with access to all devices
        all_access = list([cur_u.login for cur_u in user.objects.filter(Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)) if cur_u.has_perm("backbone.all_devices")])
        self.log("users with access to all devices: %s" % (", ".join(sorted(all_access))))
        server_idxs = [cur_gc.monitor_server.pk]
        # get netip-idxs of own host
        my_net_idxs = set(netdevice.objects.filter(Q(device__in=server_idxs)).values_list("pk", flat=True))
        # get ext_hosts stuff
        ng_ext_hosts = self._get_mon_ext_hosts()
        # all hosts
        all_hosts_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.filter(Q(enabled=True)).select_related("device_type", "domain_tree_node")])
        # check_hosts
        if hosts:
            # not beautiful but ok
            pk_list = []
            for full_h_name in hosts:
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
        # add master/slave related filters
        if cur_gc.master:
            pass
            # h_filter &= (Q(monitor_server=cur_gc.monitor_server) | Q(monitor_server=None))
        else:
            h_filter &= Q(monitor_server=cur_gc.monitor_server)
        if not single_build:
            h_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        # dictionary with all parent / slave relations
        ps_dict = {}
        for ps_config in config.objects.exclude(Q(parent_config=None)).select_related("parent_config"):
            ps_dict[ps_config.name] = ps_config.parent_config.name
        check_hosts = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.exclude(Q(device_type__identifier='MD')).filter(h_filter).select_related("domain_tree_node")])
        for cur_dev in check_hosts.itervalues():
            # set default values
            cur_dev.valid_ips = {}
            cur_dev.invalid_ips = {}
        meta_devices = dict([(md.device_group.pk, md) for md in device.objects.filter(Q(device_type__identifier='MD')).prefetch_related("device_config_set", "device_config_set__config").select_related("device_group")])
        all_configs = {}
        for cur_dev in device.objects.filter(h_filter).select_related("domain_tree_node").prefetch_related("device_config_set", "device_config_set__config"):
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
        first_contactgroup_name = cur_gc["contactgroup"][cur_gc["contactgroup"].keys()[0]]["name"]
        contact_group_dict = {}
        # get contact groups
        if hosts:
            host_info_str = logging_tools.get_plural("host", len(hosts))
            ct_groups = mon_contactgroup.objects.filter(Q(device_groups__device__name__in=hosts))
        else:
            host_info_str = "all"
            ct_groups = mon_contactgroup.objects.all()
        ct_group = ct_groups.prefetch_related("device_groups", "device_groups__device")
        for ct_group in ct_groups:
            if cur_gc["contactgroup"].has_key(ct_group.pk):
                cg_name = cur_gc["contactgroup"][ct_group.pk]["name"]
            else:
                self.log("contagroup_idx %s for device %s not found, using first from contactgroups (%s)" % (
                    unicode(ct_group),
                    ct_group.name,
                    first_contactgroup_name),
                         logging_tools.LOG_LEVEL_ERROR)
                cg_name = first_contactgroup_name
            for g_devg in ct_group.device_groups.all().prefetch_related("device_group", "device_group__domain_tree_node"):
                for g_dev in g_devg.device_group.all():
                    contact_group_dict.setdefault(g_dev.full_name, []).append(ct_group.name)
        # get valid and invalid network types
        valid_nwt_list = set(network_type.objects.filter(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        invalid_nwt_list = set(network_type.objects.exclude(Q(identifier__in=["p", "o"])).values_list("identifier", flat=True))
        # get all network devices (needed for relaying)
        for n_i, n_t, n_d, d_pk, dom_name in net_ip.objects.all().values_list("ip", "network__network_type__identifier", "netdevice__pk", "netdevice__device__pk", "domain_tree_node__full_name"):
            if d_pk in check_hosts:
                cur_host = check_hosts[d_pk]
                getattr(cur_host, "valid_ips" if n_t in valid_nwt_list else "invalid_ips").setdefault(n_d, []).append((n_i, dom_name))
        # get all masterswitch connections, FIXME
        # dc.execute("SELECT d.device_idx, ms.device FROM device d, msoutlet ms WHERE ms.slave_device = d.device_idx")
        # all_ms_connections = {}
        # for db_rec in dc.fetchall():
        #    all_ms_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        # get all device relationships
        # all_dev_relationships = {}
        # FIXME
        # dc.execute("SELECT * FROM device_relationship")
        # for db_rec in dc.fetchall():
        #    all_dev_relationships[db_rec["domain_device"]] = db_rec
        # get all ibm bladecenter connections
        # FIXME
        # dc.execute("SELECT d.device_idx, ib.device FROM device d, ibc_connection ib WHERE #ib.slave_device = d.device_idx")
        # all_ib_connections = {}
        # for db_rec in dc.fetchall():
        #    all_ib_connections.setdefault(db_rec["device_idx"], []).append(db_rec["device"])
        host_nc = cur_gc["device.d"]
        # delete host if already present in host_table
        for host_pk, host in check_hosts.iteritems():
            if host.full_name in host_nc:
                # now very simple
                del host_nc[host.full_name]
        # build lookup-table
        nagvis_maps = set()
        for host_name, host in sorted([(cur_dev.full_name, cur_dev) for cur_dev in check_hosts.itervalues()]):
            if build_dv:
                build_dv.count()
            self._create_single_host_config(
                cur_gc,
                host,
                check_hosts,
                d_map,
                my_net_idxs,
                all_hosts_dict,
                dev_templates,
                serv_templates,
                var_stack,
                all_access,
                # all_ms_connections,
                # all_ib_connections,
                # all_dev_relationships,
                contact_group_dict,
                ng_ext_hosts,
                all_configs,
                nagvis_maps,
                single_build,
            )
        host_names = host_nc.keys()
        # host_uuids = set([host_val.uuid for host_val in all_hosts_dict.itervalues() if host_val.full_name in host_names])
        for host_name in sorted(host_names):
            host = host_nc[host_name][0]
            if host.has_key("possible_parents"):
                parent_list = []
                p_parents = host["possible_parents"]
                # print "*", p_parents
                for _p_val, _nd_val, p_list in p_parents:
                    # skip first host (is self)
                    host_pk = p_list.pop(0)
                    for parent_idx in p_list:
                        if d_map[host_pk] > d_map[parent_idx]:
                            parent = all_hosts_dict[parent_idx].full_name
                            if parent in host_names and parent != host["name"]:
                                parent_list.append(parent)
                                # exit inner loop
                                break
                        else:
                            break
                del host["possible_parents"]
                if parent_list:
                    host["parents"] = ",".join(set(parent_list))
                    self.mach_log("Setting parent to %s" % (", ".join(parent_list)), logging_tools.LOG_LEVEL_OK, host["name"])
                    self.close_mach_log()
        # remove old nagvis maps
        if cur_gc.master and not single_build:
            self.log("created %s" % (logging_tools.get_plural("nagvis map", len(nagvis_maps))))
            nagvis_map_dir = os.path.join(global_config["NAGVIS_DIR"], "etc", "maps")
            if os.path.isdir(nagvis_map_dir):
                for entry in os.listdir(nagvis_map_dir):
                    full_name = os.path.join(nagvis_map_dir, entry)
                    if full_name not in nagvis_maps:
                        self.log("removing old nagvis mapfile %s" % (full_name))
                        try:
                            os.unlink(full_name)
                        except:
                            self.log("error removing %s: %s" % (full_name,
                                                                process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                # create group maps
                dev_groups = device_group.objects.filter(
                    Q(enabled=True) &
                    Q(device_group__name__in=[os.path.basename(entry).split(".")[0] for entry in nagvis_maps])).distinct()
                self.log("creating maps for %s" % (logging_tools.get_plural("device group", len(dev_groups))))
                for dev_group in dev_groups:
                    map_name = os.path.join(nagvis_map_dir, "%s.cfg" % (dev_group.name.replace(" ", "_")))
                    file(map_name, "w").write("\n".join([
                        "define global {",
                        "    alias=Group %s" % (dev_group.name),
                        "}",
                    ]))
            cache_dir = os.path.join(global_config["NAGVIS_DIR"], "var")
            if os.path.isdir(cache_dir):
                rem_ok, rem_failed = (0, 0)
                for entry in os.listdir(cache_dir):
                    try:
                        full_name = os.path.join(cache_dir, entry)
                    except:
                        self.log("error building full_name from entry '%s'" % (entry), logging_tools.LOG_LEVEL_CRITICAL)
                        rem_failed += 1
                    else:
                        if os.path.isfile(full_name):
                            try:
                                os.unlink(full_name)
                            except:
                                rem_failed += 1
                            else:
                                rem_ok += 1
                self.log("cleaned cache_dir %s (%d ok, %d failed)" % (
                    cache_dir,
                    rem_ok,
                    rem_failed), logging_tools.LOG_LEVEL_ERROR if rem_failed else logging_tools.LOG_LEVEL_OK)
        end_time = time.time()
        self.log("created configs for %s hosts in %s" % (
            host_info_str,
            logging_tools.get_diff_time_str(end_time - start_time)))
    def get_service(self, host, act_host, s_check, sc_array, act_def_serv, serv_cgs, checks_are_active, serv_temp, cur_gc):
        self.mach_log("  adding check %-30s (%2d p), template %s, %s" % (
            s_check["command_name"],
            len(sc_array),
            s_check.get_template(act_def_serv.name),
            "cg: %s" % (", ".join(sorted(serv_cgs))) if serv_cgs else "no cgs"))
        ret_field = []
        # for sc_name, sc in sc_array:
        for arg_temp in sc_array:
            act_serv = nag_config("service", arg_temp.info)
            act_serv["%s_checks_enabled" % ("active" if checks_are_active else "passive")] = 1
            act_serv["%s_checks_enabled" % ("passive" if checks_are_active else "active")] = 0
            act_serv["service_description"] = arg_temp.info.replace("(", "[").replace(")", "]")
            act_serv["host_name"] = host.full_name
            # volatile
            act_serv["is_volatile"] = "1" if serv_temp.volatile else "0"
            act_serv["check_period"] = cur_gc["timeperiod"][serv_temp.nsc_period_id]["name"]
            act_serv["max_check_attempts"] = serv_temp.max_attempts
            act_serv["normal_check_interval"] = serv_temp.check_interval
            act_serv["retry_check_interval"] = serv_temp.retry_interval
            act_serv["notification_interval"] = serv_temp.ninterval
            act_serv["notification_options"] = ",".join(serv_temp.notification_options)
            act_serv["notification_period"] = cur_gc["timeperiod"][serv_temp.nsn_period_id]["name"]
            if serv_cgs:
                act_serv["contact_groups"] = ",".join(serv_cgs)
            else:
                act_serv["contact_groups"] = global_config["NONE_CONTACT_GROUP"]
            if not checks_are_active:
                act_serv["check_freshness"] = 0
                act_serv["freshness_threshold"] = 3600
            if checks_are_active and not cur_gc.master:
                # trace
                act_serv["obsess_over_service"] = 1
            act_serv["flap_detection_enabled"] = 1 if (host.flap_detection_enabled and serv_temp.flap_detection_enabled) else 0
            if serv_temp.flap_detection_enabled and host.flap_detection_enabled:
                act_serv["low_flap_threshold"] = serv_temp.low_flap_threshold
                act_serv["high_flap_threshold"] = serv_temp.high_flap_threshold
                n_field = []
                for short, f_name in [("o", "ok"), ("w", "warn"), ("c", "critical"), ("u", "unknown")]:
                    if getattr(serv_temp, "flap_detect_%s" % (f_name)):
                        n_field.append(short)
                if not n_field:
                    n_field.append("o")
                act_serv["flap_detection_options"] = ",".join(n_field)
            if global_config["ENABLE_PNP"] or global_config["ENABLE_COLLECTD"]:
                act_serv["process_perf_data"] = 1 if (host.enable_perfdata and s_check.enable_perfdata) else 0
                if host.enable_perfdata and s_check.enable_perfdata:
                    act_serv["action_url"] = "%s/index.php/graph?host=$HOSTNAME$&srv=$SERVICEDESC$" % (global_config["PNP_URL"])
            if s_check.servicegroup_names:
                act_serv["servicegroups"] = ",".join(s_check.servicegroup_names)
                cur_gc["servicegroup"].add_host(host.name, act_serv["servicegroups"])
            act_serv["check_command"] = "!".join([s_check["command_name"]] + s_check.correct_argument_list(arg_temp, host.dev_variables))
            # if act_host["check_command"] == "check-host-alive-2" and s_check["command_name"].startswith("check_ping"):
            #    self.mach_log(
            #        "   removing command %s because of %s" % (
            #            s_check["command_name"],
            #            act_host["check_command"]))
            # else:
            ret_field.append(act_serv)
        return ret_field
    def _get_target_ip_info(self, my_net_idxs, net_devices, host, check_hosts):
        traces = []
        pathes = self.router_obj.get_ndl_ndl_pathes(my_net_idxs, net_devices.keys(), add_penalty=True)
        for penalty, cur_path in sorted(pathes):
            if net_devices.has_key(cur_path[-1]):
                dev_path = self.router_obj.map_path_to_device(cur_path)
                dev_path.reverse()
                traces.append((penalty, cur_path[-1], dev_path))
        traces = sorted(traces)
        if not traces:
            self.mach_log("Cannot reach host %s (check peer_information)" % (host.name),
                          logging_tools.LOG_LEVEL_ERROR)
            valid_ips = []
        else:
            valid_ips = sum([net_devices[nd_pk] for _val, nd_pk, _loc_trace in traces], [])
        return valid_ips, traces

