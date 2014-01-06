#!/usr/bin/python-init -Otu
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
""" external commands (dhcp, ipmi) parts of mother """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, network, cd_connection, device_variable, netdevice
from initat.mother.command_tools import simple_command
from initat.mother.config import global_config
from lxml import etree # @UnresolvedImports
import commands
import config_tools
import logging_tools
import process_tools
import re
import server_command
import subprocess
import threading_tools
import time

class hc_command(object):
    def __init__(self, xml_struct, router_obj):
        cur_cd = cd_connection.objects.select_related("child", "parent").prefetch_related("parent__device_variable_set").get(Q(pk=xml_struct.get("cd_con")))
        self.cd_obj = cur_cd
        command = xml_struct.get("command")
        self.curl_base = self.cd_obj.parent.curl.split(":")[0]
        self.log("got command %s for %s (curl is '%s', target: %s)" % (
            command,
            unicode(cur_cd.parent),
            cur_cd.parent.curl,
            unicode(cur_cd.child)))
        # better use subclasses, FIXME
        var_list = {
            "ipmi" : [
                ("IPMI_USERNAME", "admin"),
                ("IPMI_PASSWORD", "admin"),
                ("IPMI_INTERFACE", ""),
                ],
            "ilo4" : [
                ("ILO_USERNAME", "Administrator"),
                ("ILO_PASSWORD", "passwd"),
                ]
            }.get(self.curl_base, [])
        var_dict = dict([(key, self.get_var(key, def_val)) for key, def_val in var_list])
        for key in sorted(var_dict):
            self.log(" var %-20s : %s" % (
                key,
                str(var_dict[key])))
        com_ip = self.get_ip_to_host(self.cd_obj.parent, router_obj)
        if not com_ip:
            self.log("cannot reach device %s" % (unicode(self.cd_obj.parent)),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            com_str = self._build_com_str(var_dict, com_ip, command)
            if com_str:
                self.log("com_str is '%s'" % (com_str))
                simple_command(com_str,
                               short_info="True",
                               done_func=self.hc_done,
                               log_com=self.log,
                               info="hard_control")
            else:
                self.log("com_str is None, strange...", logging_tools.LOG_LEVEL_ERROR)
    def _build_com_str(self, var_dict, com_ip, command):
        if self.curl_base == "ipmi":
            com_str = "%s %s -H %s -U %s -P %s chassis power %s" % (
                process_tools.find_file("ipmitool"),
                # add ipmi interface if defined
                "-I %s" % (var_dict["IPMI_INTERFACE"]) if var_dict.get("IPMI_INTERFACE", "") else "",
                com_ip,
                var_dict["IPMI_USERNAME"],
                var_dict["IPMI_PASSWORD"],
                {"on"    : "on",
                 "off"   : "off",
                 "cycle" : "cycle"}.get(command, "status")
            )
        elif self.curl_base == "ilo4":
            com_str = "%s -I lanplus -H %s -U %s -P %s chassis power %s" % (
                process_tools.find_file("ipmitool"),
                com_ip,
                var_dict["ILO_USERNAME"],
                var_dict["ILO_PASSWORD"],
                {"on"    : "on",
                 "off"   : "off",
                 "cycle" : "cycle"}.get(command, "status")
            )
        else:
            self.log("cannot handle curl_base '%s'" % (self.curl_base), logging_tools.LOG_LEVEL_CRITICAL)
            com_str = None
        return com_str
    def hc_done(self, hc_sc):
        cur_out = hc_sc.read()
        self.log("hc_com finished with stat %d (%d bytes)" % (
            hc_sc.result,
            len(cur_out)))
        for line_num, line in enumerate(cur_out.split("\n")):
            self.log(" %3d %s" % (line_num + 1, line))
        hc_sc.terminate()
    def get_var(self, var_name, default_val=None):
        try:
            cur_var = self.cd_obj.parent.device_variable_set.get(Q(name=var_name))
        except device_variable.DoesNotExist:
            try:
                cur_var = self.cd_obj.parent.device_group.device.device_variable_set.get(Q(name=var_name))
            except device_variable.DoesNotExist:
                try:
                    cur_var = device_variable.objects.get(Q(device__device_group__cluster_device_group=True) & Q(name=var_name))
                except device_variable.DoesNotExist:
                    var_value = default_val
                    cur_var = None
        if cur_var:
            var_value = cur_var.value
        return var_value
    def get_ip_to_host(self, dev_struct, router_obj):
        all_paths = sorted(
            router_obj.get_ndl_ndl_pathes(
                hc_command.process.sc.netdevice_idx_list,
                list(dev_struct.netdevice_set.all().values_list("pk", flat=True)),
                only_endpoints=True,
                add_penalty=True,
            )
        )
        com_ip = None
        if all_paths:
            ip_list = netdevice.objects.get(Q(pk=all_paths[0][2])).net_ip_set.all().values_list("ip", flat=True)
            if ip_list:
                com_ip = ip_list[0]
        return com_ip
    @staticmethod
    def setup(proc):
        hc_command.process = proc
        hc_command.process.log("init hc_command")
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        hc_command.process.log("[hc] %s" % (what), log_level)

class external_command_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        simple_command.setup(self)
        self.router_obj = config_tools.router_object(self.log)
        self.sc = config_tools.server_check(server_type="mother")
        if "b" in self.sc.identifier_ip_lut:
            self.__kernel_ip = self.sc.identifier_ip_lut["b"][0].ip
            self.log("IP address in boot-net is %s" % (self.__kernel_ip))
        else:
            self.__kernel_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.register_func("delay_command", self._delay_command)
        self.register_func("hard_control", self._hard_control)
        self.register_timer(self._check_commands, 10)
        hc_command.setup(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _delay_command(self, *args, **kwargs):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        new_sc = simple_command(args[0], delay_time=kwargs.get("delay_time", 0))
    def _server_com(self, s_com):
        dst_call = {"alter_macadr"  : self._adw_macaddr,
                    "delete_macadr" : self._adw_macaddr,
                    "write_macadr"  : self._adw_macaddr,
                    "syslog_line"   : self._syslog_line}.get(s_com.get_command(), None)
        if dst_call:
            dst_call(s_com.get_command(), s_com)
        else:
            self.log("Unknown server_message_command: %s" % (s_com.get_command()), logging_tools.LOG_LEVEL_ERROR)
        if s_com.get_option_dict().has_key("SIGNAL_MAIN_THREAD"):
            self.send_pool_message(s_com.get_option_dict()["SIGNAL_MAIN_THREAD"])
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.unregister_timer(self._check_commands)
    def _hard_control(self, zmq_id, in_com, *args, **kwargs):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        in_com = server_command.srv_command(source=in_com)
        self.router_obj.check_for_update()
        for cur_dev in in_com.xpath(".//ns:device"):
            hc_command(cur_dev, self.router_obj)
    def sc_finished(self, sc_com):
        self.log("simple command done")
        print sc_com.read()
