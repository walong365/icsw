#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" handle service reload / restarts """

import re
from initat.tools import logging_tools, process_tools


class ServiceHelper(object):
    def __init__(self, log_com):
        self.log_com = log_com
        self.__services = {}
        self._check_for_systemd()

    def _check_for_systemd(self):
        if file("/proc/1/cmdline", "r").read().count("system"):
            self._method = "s"
            self._service_command = self._service_command_s
            self._systemctl = process_tools.find_file("systemctl")
            self.log("systemd detected, systemctl at {}".format(self._systemctl))
            self._get_systemd_services()
        else:
            self._method = "i"
            self._service_command = self._service_command_i
            self._chkconfig = process_tools.find_file("chkconfig")
            self._service = process_tools.find_file("service")
            self.log("classic init detected, chkconfig at {}, service at {}".format(self._chkconfig, self._service))
            self._get_init_services()
        self.log("found {}".format(logging_tools.get_plural("service", len(self.__services))))

    def _get_systemd_services(self):
        _stat, _out, _err = self._call_command("{} list-units -a --type=service".format(self._systemctl))
        for _line in _out.strip().split("\n")[1:-1]:
            try:
                _key, _value = _line.strip().split(None, 1)
            except:
                pass
            else:
                self.__services[_key] = _value

    def _get_init_services(self):
        _stat, _out, _err = self._call_command("{} -A".format(self._chkconfig))
        if _err:
            # -A switch not known (centos 6), use full output and parse
            _stat, _out, _err = self._call_command("{}".format(self._chkconfig))
            for _line in _out.strip().split("\n"):
                if not _line.strip():
                    break
                _key, _rest = _line.strip().split(None, 1)
                self.__services[_key] = None
        else:
            for _line in _out.strip().split("\n")[1:-1]:
                try:
                    _key, _value = _line.strip().split(None, 1)
                except:
                    pass
                else:
                    self.__services[_key] = _value

    def _call_command(self, com_str):
        return process_tools.call_command(com_str, self.log, close_fds=True, log_stdout=False)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[SH{}] {}".format(self._method, what), log_level)

    def _get_real_service_name(self, name):
        if self._method == "i":
            if name in self.__services:
                return name
            else:
                self.log("service {} not known to chkconfig".format(name), logging_tools.LOG_LEVEL_ERROR)
                return None
        else:
            if name in self.__services:
                return name
            elif "{}.service" in self.__services:
                return "{}.service".format(name)
            else:
                self.log("service {} not known to systemd".format(name), logging_tools.LOG_LEVEL_ERROR)
                return None

    def find_services(self, name_re_str):
        name_re = re.compile(name_re_str)
        _result = [_key for _key in self.__services.iterkeys() if name_re.match(_key)]
        if not _result:
            self.log("found no services with name_re '{}'".format(name_re_str), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log(
                "search for {} gave {}: {}".format(
                    name_re_str,
                    logging_tools.get_plural("result", len(_result)),
                    ", ".join(_result),
                )
            )
        return _result

    def service_command(self, name, cmd):
        _ALLOWED_CMDS = ["restart", "reload", "start", "stop"]
        if cmd not in _ALLOWED_CMDS:
            self.log("unknown command '{}' (must be one of {})".format(_cmd, ", ".join(_ALLOWED_CMDS)), logging_tools.LOG_LEVEL_ERROR)
            return None
        else:
            real_name = self._get_real_service_name(name)
            if real_name:
                self._service_command(real_name, cmd)

    def _service_command_s(self, name, cmd):
        return process_tools.call_command(
            "{} {} {}".format(self._systemctl, cmd, name),
            self.log,
            close_fds=True,
            log_stdout=False,
        )

    def _service_command_i(self, name, cmd):
        return process_tools.call_command(
            "{} {} {}".format(self._service, name, cmd),
            self.log,
            close_fds=True,
            log_stdout=False,
        )
