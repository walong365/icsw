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
import datetime
import re
import json
import time

from django.db.models import Q
from lxml.builder import E

from initat.cluster.backbone.models import SyslogCheck
from initat.host_monitoring import limits
from initat.tools import logging_tools, process_tools, server_command


class DeviceNotFoundException(BaseException):
    pass


class MonCommand(object):
    @staticmethod
    def setup(log_com, mach_class):
        MonCommand.machine_class = mach_class
        MonCommand.log_com = log_com
        MonCommand.commands = {}
        # add commands
        LogRateCommand()
        SyslogCheckCommand()

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
            MonCommand.commands[com_name].handle(srv_com)
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
                    raise DeviceNotFoundException("no device with pk {} defined".format(values))

        # add --pk <INT> for device parser
        self.parser.add_argument("--pk", type=int, help="pk of device to check", action=validate_pk)

    def handle(self, srv_com):
        try:
            p_args = self.parse(srv_com)
            self.run(srv_com, p_args)
        except DeviceNotFoundException:
            srv_com.set_result(
                "device not found",
                server_command.SRV_REPLY_STATE_CRITICAL,
            )
        except:
            exc_com = process_tools.exception_info()
            for _line in exc_com.log_lines:
                self.log(_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com.set_result(
                "an exception occured: {}".format(process_tools.get_except_info()),
                server_command.SRV_REPLY_STATE_CRITICAL,
            )

    def send_to_remote_server(self, srv_type, srv_com):
        MonCommand.machine_class.srv_proc.send_to_remote_server(srv_type, unicode(srv_com))

    def parse(self, srv_com):
        if "arg_list" in srv_com:
            args = srv_com["*arg_list"].strip().split()
        else:
            args = []
        self.log(
            "got {}: '{}'".format(
                logging_tools.get_plural("argument", len(args)),
                " ".join(args),
            )
        )
        return self.parser.parse_args(args)

    # base class for monitoring commands
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=self.Meta.description,
        )
        self.populate_parser()
        self.name = self.__class__.__name__
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


class CheckResult(object):
    def __init__(self):
        self.state = server_command.SRV_REPLY_STATE_OK
        self.rf = []

    def ok(self, what):
        self.rf.append(what)

    def warn(self, what):
        self.state = max(self.state, server_command.SRV_REPLY_STATE_WARN)
        self.rf.append(what)

    def error(self, what):
        self.state = max(self.state, server_command.SRV_REPLY_STATE_ERROR)
        self.rf.append(what)

    def set_result(self, srv_com):
        srv_com.set_result(
            ", ".join(self.rf) or "nothing set in CheckResult",
            self.state,
        )


class SyslogCheckCommand(MonCommand):
    class Meta:
        command = "syslog_check_mon"
        description = "Checks Syslogs for problems"

    def populate_parser(self):
        self.parser.add_argument("--key", type=str, help="passive check key")
        self.parser.add_argument("--checks", type=str, help="syslog check pks")
        self.add_pk_parser()

    def run(self, srv_com, args):
        _dev = args.device
        # get checks
        check_pks = sorted([int(_val) for _val in args.checks.strip().split(",")])
        checks = SyslogCheck.objects.filter(Q(pk__in=check_pks))
        found_pks = sorted([_check.pk for _check in checks])
        res = CheckResult()
        if check_pks != found_pks:
            res.warn(
                "Some checks are missing: {}".format(
                    ", ".join(
                        [
                            "{:d}".format(_mis) for _mis in set(check_pks) - set(found_pks)
                        ]
                    )
                )
            )
        if not check_pks:
            res.warn(
                "No checks defined"
            )
        else:
            max_minutes = max([_check.minutes_to_consider for _check in checks])
            _log = _dev.filewatcher.get_logs(minutes=max_minutes)
            mon_info = E.monitor_info(
                uuid=_dev.device.uuid,
                name=_dev.device.name,
                time="{:d}".format(int(time.time())),
            )
            if not _log:
                res.error("no logs found (max_minutes={:d})".format(max_minutes))
                _res_list = [
                    ("syslog check {}".format(_check.name), limits.nag_STATE_CRITICAL, "no logs found") for _check in checks
                ]
            else:
                res.ok("lines to scan: {:d}, checks: {:d}, minutes: {:d}".format(len(_log), len(checks), max_minutes))
                _res_list = []
                _now = datetime.datetime.now()
                for _check in checks:
                    expressions = [SyslogCheckExpression(_obj) for _obj in json.loads(_check.expressions)]
                    if expressions:
                        if _check.minutes_to_consider == max_minutes:
                            _check_lines = _log
                        else:
                            _td = datetime.timedelta(seconds=_check.minutes_to_consider * 60)
                            _check_lines = [_line for _line in _log if _now - _line.pd < _td]
                        _matches = []
                        for _expr in expressions:
                            _expr.feed(_check_lines)
                            if _expr.found:
                                _matches.append(_expr.match_str)
                        _res_list.append(
                            (
                                "slc {}".format(_check.name),
                                max(_expr.ret_state for _expr in expressions),
                                "{} / {} [{}], {}".format(
                                    logging_tools.get_plural("expression", len(expressions)),
                                    logging_tools.get_plural("line", len(_check_lines)),
                                    logging_tools.get_plural("minute", _check.minutes_to_consider),
                                    ", ".join(_matches) if _matches else "no expressions matched"
                                ),
                            )
                        )
                    else:
                        _res_list.append(
                            (
                                "slc {}".format(_check.name),
                                limits.nag_STATE_WARNING,
                                "no expressions defined",
                            )
                        )
            _result_chunk = {
                "source": "logcheck-server check",
                "prefix": args.key,
                "list": _res_list
            }
            self.send_to_remote_server(
                "md-config-server",
                server_command.srv_command(
                    command="passive_check_results_as_chunk",
                    ascii_chunk=process_tools.compress_struct(_result_chunk),
                )
            )
        # print srv_com, _dev, args
        res.set_result(srv_com)


class SyslogCheckExpression(object):
    def __init__(self, struct):
        self.text = struct["text"]
        self.level = struct["level"]
        self.format = struct["format"]
        try:
            self.regexp = re.compile(self.text, re.IGNORECASE)
        except:
            self.regexp = re.compile(".*")
        self.found = 0
        self.checked = 0
        self.ret_state = limits.nag_STATE_OK

    def __repr__(self):
        return "format {}, level {}, found {:d}".format(
            self.format,
            self.level,
            self.found,
        )

    def feed(self, lines):
        for line in lines:
            self.checked += 1
            if self.regexp.search(line.text):
                self.found += 1
                if self.level == "warn":
                    self.ret_state = max(self.ret_state, limits.nag_STATE_WARNING)
                elif self.level == "crit":
                    self.ret_state = max(self.ret_state, limits.nag_STATE_CRITICAL)

    @property
    def match_str(self):
        return "pattern '{}' found {} (level: {})".format(
            self.regexp.pattern,
            logging_tools.get_plural("time", self.found),
            self.level,
        )
