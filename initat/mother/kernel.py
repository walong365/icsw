# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at
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

import os
import time

from django.db import connection
from initat.cluster.backbone.models import kernel
from initat.mother.config import global_config
from initat.tools import config_tools
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools

from kernel_sync_tools import kernel_helper


class kernel_sync_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
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
            self.log("checking of kernel_dir took {}".format(logging_tools.get_diff_time_str(kct_end - kct_start)))
            srv_com.set_result("check of kernel_dir took {}".format(logging_tools.get_diff_time_str(kct_end - kct_start)))
