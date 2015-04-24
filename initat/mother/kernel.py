# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" kernel related parts of mother """

from django.db import connection
from initat.cluster.backbone.models import kernel
from initat.mother.config import global_config
from kernel_sync_tools import kernel_helper
from initat.tools import config_tools
from initat.tools import logging_tools
import os
import pprint  # @UnusedImport
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools
import time


class kernel_sync_process(threading_tools.process_obj):
    def process_init(self):
        # , config, db_con, **args):
        # needed keys in config:
        # TMP_DIR ....................... directory to create temporary files
        # SET_DEFAULT_BUILD_MACHINE ..... flag, if true sets the build_machine to local machine name
        # IGNORE_KERNEL_BUILD_MACHINE ... flag, if true discards kernel if build_machine != local machine name
        # KERNEL_DIR .................... kernel directory, usually /tftpboot/kernels
        # TFTP_DIR ...................... tftpboot directory (optional)
        # SQL_ACCESS .................... access string for database
        # SERVER_SHORT_NAME ............. short name of device
        # SYNCER_ROLE ................... syncer role, mother or xen
        # check log type (queue or direct)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        self.register_func("srv_command", self._srv_command)
        self.register_func("rescan_kernels", self._rescan_kernels)
        self.kernel_dev = config_tools.server_check(server_type="kernel_server")

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _rescan_kernels(self, *args, **kwargs):
        src_id, srv_com_str = args[0:2]
        srv_com = server_command.srv_command(source=srv_com_str)
        self._check_kernel_dir(srv_com)
        self.send_pool_message("send_return", src_id, unicode(srv_com))

    def _srv_command(self, srv_com, **kwargs):
        srv_com = server_command.srv_command(source=srv_com)
        if srv_com["command"].text == "check_kernel_dir":
            self._check_kernel_dir(srv_com)

    def _check_kernel_dir(self, srv_com):
        self.log("checking kernel dir")
        # build option dict
        opt_dict = {}
        for key, def_value in {
            "ignore_kernel_build_machine": False,
            "kernels_to_insert": [],
            "check_list": [],
            "insert_all_found": False,
            "kernels_to_sync": {}
        }.iteritems():
            if key in srv_com:
                cur_val = srv_com[key].text
                if type(def_value) == bool:
                    cur_val = True if int(cur_val) else False
            else:
                cur_val = def_value
            opt_dict[key] = cur_val
        # self.__ks_check._check(dc)
        self.log(
            "option_dict has {}: {}".format(
                logging_tools.get_plural("key", len(opt_dict.keys())),
                ", ".join(["%s (%s, %s)" % (key, str(type(value)), str(value)) for key, value in opt_dict.iteritems()])
            )
        )
        # kernels_found, problems = ({}, [])
        srv_com.update_source()
        # send reply now or do we need more data ?
        reply_now = (opt_dict["insert_all_found"] is True)
        # problems are global problems, not kernel local
        kernels_found = []
        problems = []
        # print srv_com.pretty_print()
        # srv_reply.set_option_dict({"problems"      : problems,
        #                           "kernels_found" : kernels_found})
        if reply_now:
            srv_com.set_result("starting check of kernel_dir '%s'" % (global_config["KERNEL_DIR"]))
            # send return, FIXME
        # print srv_com.pretty_print()
        # if reply_now:
        #    srv_reply.set_ok_result("starting check of kernel_dir")
        #    if srv_com.get_queue():
        #        srv_com.get_queue().put(("result_ready", (srv_com, srv_reply)))
        if not self.kernel_dev.effective_device:
            self.log("no kernel_server, skipping check ...",
                     logging_tools.LOG_LEVEL_ERROR)
            srv_com.set_result("no kernel server", server_command.SRV_REPLY_STATE_ERROR)
        else:
            all_k_servers = config_tools.device_with_config("kernel_server")
            def_k_servers = all_k_servers.get("kernel_server", [])
            self.log("found %s: %s" % (logging_tools.get_plural("kernel_server", len(def_k_servers)),
                                       ", ".join(sorted([unicode(s_struct.effective_device) for s_struct in def_k_servers]))))
            all_kernels = dict([(cur_kern.name, cur_kern) for cur_kern in kernel.objects.all()])
            any_found_in_database = len(all_kernels) > 0
            if any_found_in_database:
                self.log("some kernels already present in database, not inserting all found", logging_tools.LOG_LEVEL_WARN)
                opt_dict["insert_all_found"] = False
            kct_start = time.time()
            self.log("Checking for kernels (%d already in database) ..." % (len(all_kernels.keys())))
            if opt_dict["kernels_to_insert"]:
                self.log(" - only %s to insert: %s" % (
                    logging_tools.get_plural("kernels", len(opt_dict["kernels_to_insert"])),
                    ", ".join(opt_dict["kernels_to_insert"])))
            if "TFTP_DIR" in global_config:
                if not os.path.isdir(global_config["TFTP_DIR"]):
                    self.log("TFTP_DIR '%s' is not a directory" % (global_config["TFTP_DIR"]), logging_tools.LOG_LEVEL_ERROR)
                    problems.append("TFTP_DIR '%s' is not a directory" % (global_config["TFTP_DIR"]))
            kern_dir = global_config["KERNEL_DIR"]
            if not os.path.isdir(kern_dir):
                self.log("kernel_dir '%s' is not a directory" % (kern_dir), logging_tools.LOG_LEVEL_ERROR)
                problems.append("kernel_dir '%s' is not a directory" % (kern_dir))
            else:
                for entry in os.listdir(kern_dir):
                    if not opt_dict["check_list"] or entry in opt_dict["check_list"]:
                        try:
                            act_kernel = kernel_helper(entry, kern_dir, self.log, global_config, master_server=self.kernel_dev.effective_device)
                        except IOError, what:
                            self.log(
                                "error %s: %s" % (
                                    process_tools.get_except_info(),
                                    unicode(what)),
                                logging_tools.LOG_LEVEL_ERROR)
                            problems.append(unicode(what))
                        else:
                            # handle initrd generated by old populate_ramdisk.py
                            act_kernel.move_old_initrd()
                            if act_kernel.name in all_kernels.keys():
                                act_kernel.db_kernel = all_kernels[act_kernel.name]
                                act_kernel.check_md5_sums()
                                act_kernel.check_kernel_dir()
# #                                act_kernel.check_initrd()
# #                                # always check comment
# #                                act_kernel.check_comment()
# #                                # always check for xen
# #                                act_kernel.check_xen()
# #                                # check config
# #                                act_kernel.check_config()
                            else:
                                act_kernel.check_md5_sums()
                                act_kernel.check_kernel_dir()
                            act_kernel.set_option_dict_values()
                            # determine if we should insert the kernel into the database
                            if act_kernel.check_for_db_insert(opt_dict):
                                act_kernel.insert_into_database()
                                act_kernel.check_initrd()
                            act_kernel.store_option_dict()
                            kernels_found.append(act_kernel.name)
                            act_kernel.log_statistics()
                            del act_kernel
            kct_end = time.time()
            self.log("checking of kernel_dir took %s" % (logging_tools.get_diff_time_str(kct_end - kct_start)))
            srv_com.set_result("check of kernel_dir took %s" % (logging_tools.get_diff_time_str(kct_end - kct_start)))
        # send reply after term-message
        # if srv_com.get_queue() and not reply_now:
        #    srv_com.get_queue().put(("result_ready", (srv_com, srv_reply)))
        # print srv_com.pretty_print()

    def thread_running(self):
        self.log("my role is %s" % (self.__config["SYNCER_ROLE"]))
        # dicts for sync info
        # for bookkeeping
        self.__pending_syncs = {}
        # information
        self.__sync_dict = {}

    def _kernel_sync_data(self, srv_com):
        dc = self.__db_con.get_connection(self.__config["SQL_ACCESS"])
        sync_dict = srv_com.get_option_dict()
        srv_reply = server_command.server_reply()  # @UndefinedVariable
        self.log("got kernel_sync_data for kernel %s" % (sync_dict["name"]))
        self.__ks_check._check(dc)
        start_copy = False
        if not self.__ks_check.server_device_idx:
            self.log("no kernel_server, skipping sync ...",
                     logging_tools.LOG_LEVEL_ERROR)
            srv_reply.set_error_result("no kernel server")
        elif not self.__net_server:
            self.log("no net_server set", logging_tools.LOG_LEVEL_ERROR)
            srv_reply.set_error_result("no net_server set")
        else:
            # check if kernel is not in own pending_sync dict
            if sync_dict["name"] in self.__pending_syncs.keys():
                log_str = "kernel %s in own pending_sync dict" % (sync_dict["name"])
                self.log(log_str, logging_tools.LOG_LEVEL_ERROR)
                srv_reply.set_error_result(log_str)
            else:
                dc.execute("SELECT k.* FROM kernel k WHERE k.name=%s", (sync_dict["name"]))
                if not dc.rowcount:
                    srv_reply.set_error_result("kernel not found in database")
                else:
                    db_rec = dc.fetchone()
                    start_copy = True
                    srv_reply.set_ok_result("started sync")
        srv_com.get_queue().put(("result_ready", (srv_com, srv_reply)))
        if start_copy:
            self.log("starting sync for kernel %s" % (sync_dict["name"]))
            kern_dir = self.__config["KERNEL_DIR"]
            if not os.path.isdir(kern_dir):
                try:
                    os.makedirs(kern_dir)
                except:
                    self.log("cannot create kernel_dir %s: %s" % (kern_dir,
                                                                  process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            if os.path.isdir(kern_dir):
                try:
                    act_kernel = kernel(
                        sync_dict["name"],
                        kern_dir,
                        self.log,
                        dc,
                        self.__config,
                        master_server=self.__ks_check.server_device_idx,
                        sync_kernel=True,
                        sync_dict=sync_dict
                    )
                except:
                    self.log("error initialising kernel %s: %s" % (sync_dict["name"],
                                                                   process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    act_kernel.db_kernel = db_rec
                    act_kernel.check_md5_sums()
                    act_kernel.set_option_dict_values()
                    act_kernel.store_option_dict()
                    self.log("synced kernel")
                    del act_kernel
        dc.release()

    def _sync_kernels(self, srv_com):
        dc = self.__db_con.get_connection(self.__config["SQL_ACCESS"])
        sync_dict = srv_com.get_option_dict()
        srv_reply = server_command.server_reply()  # @UndefinedVariable
        self.log("got sync_kernels request for %s: %s" % (
            logging_tools.get_plural("kernel", len(sync_dict.keys())),
            ", ".join(["%s (to %s)" % (key, ",".join(["%s:%s" % (s_name, s_role) for s_name, s_role in sync_dict[key]])) for key in sorted(sync_dict.keys())])))
        self.__ks_check._check(dc)
        start_sync = False
        if not self.__ks_check.server_device_idx:
            self.log("no kernel_server, skipping sync ...",
                     logging_tools.LOG_LEVEL_ERROR)
            srv_reply.set_error_result("no kernel server")
        elif not self.__net_server:
            self.log("no net_server set", logging_tools.LOG_LEVEL_ERROR)
            srv_reply.set_error_result("no net_server set")
        elif self.__pending_syncs:
            self.log("some syncs still pending", logging_tools.LOG_LEVEL_ERROR)
            srv_reply.set_error_result("some syncs still pending")
        else:
            start_sync = True
            srv_reply.set_ok_result("started sync")
        srv_com.get_queue().put(("result_ready", (srv_com, srv_reply)))
        if start_sync:
            all_k_servers = config_tools.device_with_config("kernel_server", dc)
            all_k_servers.set_key_type("config")
            def_k_servers = all_k_servers.get("kernel_server", [])
            self.log("found %s: %s" % (logging_tools.get_plural("kernel_server", len(def_k_servers)),
                                       ", ".join(sorted([s_struct.short_host_name for s_struct in def_k_servers]))))
            # build target dict
            k_target_dict = {}
            for ks_struct in def_k_servers:
                ks_name = ks_struct.short_host_name
                k_target_dict[ks_name] = None
                t_list = ks_struct.get_route_to_other_device(dc, self.__ks_check)
                if t_list:
                    k_target_dict[ks_name] = t_list[0][2][1][0]
            # pprint.pprint(k_target_dict)
            dc.execute("SELECT k.* FROM kernel k WHERE %s" % (" OR ".join(["k.name='%s'" % (k_name) for k_name in sync_dict.iterkeys()])))
            kern_dir = self.__config["KERNEL_DIR"]
            for db_rec in dc.fetchall():
                try:
                    act_kernel = kernel(db_rec["name"], kern_dir, self.log, dc, self.__config, master_server=self.__ks_check.server_device_idx)
                except:
                    self.log("error initialising kernel %s: %s" % (db_rec["name"],
                                                                   process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    act_kernel.db_kernel = db_rec
                    act_kernel.check_md5_sums()
                    send_com = server_command.server_command(command="kernel_sync_data",  # @UndefinedVariable
                                                             option_dict=act_kernel.get_sync_dict())
                    self.log("send_com for %s has %s" % (act_kernel.name,
                                                         logging_tools.get_size_str(len(str(send_com)), long_format=True)))
                    unreach_list, reach_list = ([], [])
                    self.__sync_dict[db_rec["name"]] = {"start_time": time.time()}
                    # build reach_list
                    for targ_srv, targ_role in sync_dict[db_rec["name"]]:
                        if k_target_dict[targ_srv]:
                            reach_list.append((targ_srv, targ_role))
                        else:
                            unreach_list.append((targ_srv, targ_role))
                    act_kernel.log("starting sync to %s: %s" % (logging_tools.get_plural("target server", len(reach_list)),
                                                                ", ".join(sorted(["%s:%s" % (s_name, s_role) for s_name, s_role in reach_list])) or "NONE"),
                                   db_write=True)
                    if unreach_list:
                        act_kernel.log("%s unreachable: %s" % (logging_tools.get_plural("target server", len(unreach_list)),
                                                               ", ".join(sorted(["%s:%s" % (s_name, s_role) for s_name, s_role in unreach_list]))),
                                       logging_tools.LOG_LEVEL_ERROR,
                                       db_write=True)
                    for targ_srv, targ_role in sync_dict[db_rec["name"]]:
                        if k_target_dict[targ_srv]:
                            self.__pending_syncs.setdefault(act_kernel.name, []).append((targ_srv, targ_role))
                            self.log("  syncing kernel %s to %s (role %s, IP %s)" % (act_kernel.name,
                                                                                     targ_srv,
                                                                                     targ_role,
                                                                                     k_target_dict[targ_srv]))
                            self.__net_server.add_object(
                                net_tools.tcp_con_object(# @UndefinedVariable
                                    self._new_tcp_con,
                                    connect_state_call=self._connect_state_call,
                                    connect_timeout_call=self._connect_timeout,
                                    target_host=k_target_dict[targ_srv],
                                    target_port=(8001 if targ_role == "mother" else 8019),
                                    timeout=20,
                                    bind_retries=1,
                                    rebind_wait_time=1, add_data={
                                        "server_name": targ_srv,
                                        "server_role": targ_role,
                                        "kernel": act_kernel,
                                        "send_com": send_com
                                    }
                                )
                            )
                    del act_kernel
        dc.release()

    def _remove_pending_sync(self, act_kernel, s_name, s_role):
        k_name = act_kernel.name
        self.__pending_syncs[k_name].remove((s_name, s_role))
        if not self.__pending_syncs[k_name]:
            self.log("removing kernel %s from pending_dict" % (k_name))
            k_dict = self.__sync_dict[k_name]
            k_dict["end_time"] = time.time()
            act_kernel.log("syncing done in %s" % (logging_tools.get_diff_time_str(k_dict["end_time"] - k_dict["start_time"])),
                           db_write=True)
            del act_kernel
            del self.__pending_syncs[k_name]
            if not self.__pending_syncs:
                self.log("no syncs pending")

    def _srv_ok(self, (in_dict, recv_str)):
        try:
            srv_reply = server_command.server_reply(recv_str)  # @UndefinedVariable
        except:
            in_dict["kernel"].log("error reconstructing srv_reply for %s:%s" % (in_dict["server_name"],
                                                                                in_dict["server_role"]),
                                  logging_tools.LOG_LEVEL_ERROR,
                                  db_write=True)
            self.log("cannot reconstruct server_reply from recv_str", logging_tools.LOG_LEVEL_ERROR)
        else:
            in_dict["kernel"].log("got '%s' from %s:%s" % (srv_reply.get_result(),
                                                           in_dict["server_name"],
                                                           in_dict["server_role"]),
                                  logging_tools.LOG_LEVEL_OK if srv_reply.get_state() == server_command.SRV_REPLY_STATE_OK else logging_tools.LOG_LEVEL_ERROR,
                                  db_write=True)
        self._remove_pending_sync(in_dict["kernel"], in_dict["server_name"], in_dict["server_role"])

    def _srv_error(self, (in_dict, cause)):
        self.log("got error %s" % (cause),
                 logging_tools.LOG_LEVEL_ERROR)
        in_dict["kernel"].log("got error '%s' for %s:%s" % (cause,
                                                            in_dict["server_name"],
                                                            in_dict["server_role"]),
                              logging_tools.LOG_LEVEL_ERROR,
                              db_write=True)
        self._remove_pending_sync(in_dict["kernel"], in_dict["server_name"], in_dict["server_role"])

    def _connect_timeout(self, sock):
        self.log("error connecting to %s" % (sock.get_target_host()),
                 logging_tools.LOG_LEVEL_ERROR)
        # remove references to command_class
        sock.delete()
        sock.close()

    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.log("connect error to %s" % (args["host"]),
                     logging_tools.LOG_LEVEL_ERROR)
            # self._result_error(args["socket"].get_add_data()[1], args["host"], "connect error")
            # remove references to command_class
            in_dict = args["socket"].get_add_data()
            in_dict["kernel"].log("cannot connect to %s:%s" % (in_dict["server_name"],
                                                               in_dict["server_role"]),
                                  logging_tools.LOG_LEVEL_ERROR,
                                  db_write=True)
            self._remove_pending_sync(in_dict["kernel"], in_dict["server_name"], in_dict["server_role"])
            args["socket"].delete()
