#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" implement commands for logcheck-server """

import argparse

from initat.tools import logging_tools, process_tools, server_command
from initat.host_monitoring import limits


class MonCommand(object):
    @staticmethod
    def setup(log_com, mach_class):
        MonCommand.machine_class = mach_class
        MonCommand.log_com = log_com
        MonCommand.commands = {}

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        MonCommand.log_com("[MC] {}".format(what), log_level)

    @staticmethod
    def register_command(com):
        MonCommand.commands[com.Meta.command] = com

    @staticmethod
    def g_run(srv_com):
        com_name = srv_com["*command"]
        if com_name in MonCommand.commands:
            try:
                MonCommand.commands[com_name].parse(srv_com)
            except:
                exc_com = process_tools.exception_info()
                for _line in exc_com.log_lines:
                    MonCommand.g_log(_line, logging_tools.LOG_LEVEL_ERROR)
                srv_com.set_result(
                    "an exception occured: {}".format(process_tools.get_except_info()),
                    server_command.SRV_REPLY_STATE_CRITICAL,
                )
        else:
            MonCommand.g_log("undefined command '{}'".format(com_name), logging_tools.LOG_LEVEL_ERROR)
            srv_com.set_result(
                "unknown command '{}'".format(com_name),
                server_command.SRV_REPLY_STATE_ERROR,
            )

    def add_pk_parser(self):
        class validate_pk(argparse.Action):
            def __call__(self, parser, namespace, values, option_string=None):
                if MonCommand.machine_class.has_device(values):
                    setattr(namespace, "device", MonCommand.machine_class.get_device(values))
                else:
                    raise ValueError("no device with pk {} defined".format(values))

        # add --pk <INT> for device parser
        self.parser.add_argument("--pk", type=int, help="pk of device to check", action=validate_pk)

    def parse(self, srv_com):
        if "arg_list" in srv_com:
            args = srv_com["*arg_list"].strip().split()
        else:
            args = []
        p_args = self.parser.parse_args(args)
        self.run(srv_com, p_args)

    # base class for monitoring commands
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=self.Meta.description,
        )
        self.populate_parser()
        # monkey patch parsers
        self.parser.exit = self._parser_exit
        self.parser.error = self._parser_error
        MonCommand.register_command(self)

    def populate_parser(self):
        pass

    def _parser_exit(self, status=0, message=None):
        raise ValueError("ParserExit", status, message)

    def _parser_error(self, message):
        raise ValueError("ParserError", message)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        MonCommand.log_com("[MC {}] {}".format(self.name, what), log_level)


class LogRateCommand(MonCommand):
    class Meta:
        command = "syslog_rate_mon"
        description = "Show Rate of syslog messages"

    def populate_parser(self):
        self.parser.add_argument("-w", dest="warn", type=float, help="warn value in lines per second [%(default)f]", default=0.5)
        self.parser.add_argument("-c", dest="crit", type=float, help="critical value in lines per second [%(default)f]", default=2.0)
        self.add_pk_parser()

    def run(self, srv_com, args):
        _dev = args.device
        _rates = _dev.filewatcher.get_rates()
        if _rates:
            _res = {
                _key: server_command.nag_state_to_srv_reply(
                    limits.check_ceiling(_rates[_key], args.warn, args.crit)
                ) for _key in _rates.keys()
            }
            ret_state = max(_res.values())
            _warn = {key for key, value in _res.iteritems() if value == server_command.SRV_REPLY_STATE_WARN}
            _crit = {key for key, value in _res.iteritems() if value == server_command.SRV_REPLY_STATE_ERROR}
            _rf = [
                "rates: {}{}{}".format(
                    _dev.filewatcher.get_rate_info(_rates),
                    ", warning: {}".format(
                        ", ".join([logging_tools.get_diff_time_str(_val, long=False) for _val in sorted(_warn)])
                    ) if _warn else "",
                    ", critical: {}".format(
                        ", ".join([logging_tools.get_diff_time_str(_val, long=False) for _val in sorted(_crit)])
                    ) if _crit else "",
                )
            ]
            srv_com.set_result(
                ", ".join(_rf),
                ret_state
            )
        else:
            srv_com.set_result(
                "no rates found for {}".format(unicode(_dev.device)),
                server_command.SRV_REPLY_STATE_WARN,
            )
