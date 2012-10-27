#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Andreas Lang-Nevyjel, init.at
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


import threading_tools
import logging_tools
from mother.config import global_config
import config_tools
import commands
import time
import subprocess
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, network
from mother.command_tools import simple_command
import re

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
        self.sc = config_tools.server_check(server_type="mother")
        if "b" in self.sc.identifier_ip_lut:
            self.__kernel_ip = self.sc.identifier_ip_lut["b"][0].ip
            self.log("IP address in boot-net is %s" % (self.__kernel_ip))
        else:
            self.__kernel_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.register_func("delay_command", self._delay_command)
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
    def sc_finished(self, sc_com):
        self.log("simple command done")
        print sc_com.read()
