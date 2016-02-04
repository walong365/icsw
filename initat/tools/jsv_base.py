#!/usr/bin/python-init -Otu
#
# Copyright (c) 2012-2016 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" SGE Job submission verifier """

import os
import re
import sys

from initat.tools import logging_tools


class JSVBase(object):

    """
   Control the Job Submission Verification steps
   """

    _jsv_cli_params = (
        "a", "ar", "A", "b", "ckpt", "cwd", "C", "display",
        "dl", "e", "hard", "h", "hold_jid", "hold_jid_ad", "i",
        "inherit", "j", "js", "m", "M", "masterq", "notify",
        "now", "N", "noshell", "nostdin", "o", "ot", "P", "p",
        "pty", "R", "r", "shell", "sync", "S", "t", "tc",
        "terse", "u", "w", "wd"
    )
    _jsv_mod_params = (
        "ac", "l_hard", "l_soft", "q_hard", "q_soft", "pe_min",
        "pe_max", "pe_name", "binding_strategy", "binding_type",
        "binding_amount", "binding_socket", "binding_core",
        "binding_step", "binding_exp_n"
    )
    _jsv_add_params = (
        "CLIENT", "CONTEXT", "GROUP", "VERSION", "JOB_ID",
        "SCRIPT", "CMDARGS", "USER"
    )

    def __init__(self):
        self.__log_template = logging_tools.get_logger(
            "jsv_{:d}".format(os.getuid()),
            "uds:/var/lib/logging-server/py_log_zmq",
            zmq=True,
        )
        self.__state = "initialized"
        self.env = {}
        self.param = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def log_sge(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.send_command(
            "LOG {} {}".format(
                {
                    logging_tools.LOG_LEVEL_OK: "INFO",
                    logging_tools.LOG_LEVEL_WARN: "WARNING",
                    logging_tools.LOG_LEVEL_ERROR: "ERROR",
                }[log_level],
                what,
            )
        )

    def send_command(self, command):
        print(command)
        sys.stdout.flush()
        self.log("<<< {}".format(command))

    def main(self):
        _jsv_quit = False
        try:
            while not _jsv_quit:
                iput = sys.stdin.readline().strip('\n')
                if len(iput) == 0:
                    continue
                self.log(">>> {}".format(iput))
                jsv_line = re.split('\s*', iput, maxsplit=3)
                if jsv_line[0] == "QUIT":
                    _jsv_quit = True
                elif jsv_line[0] == "PARAM":
                    self.handle_param_command(jsv_line[1], jsv_line[2])
                elif jsv_line[0] == "ENV":
                    jsv_data = re.split('\s*', jsv_line[2], maxsplit=2)
                    self.handle_env_command(jsv_line[1], jsv_data[0], jsv_data[1])
                elif jsv_line[0] == "START":
                    self.handle_start_command()
                elif jsv_line[0] == "BEGIN":
                    self.handle_begin_command()
                elif jsv_line[0] == "SHOW":
                    self.show_params()
                    self.show_envs()
                else:
                    self.send_command("ERROR JSV script got unknown command " + jsv_line[0])
        except EOFError:
            pass
        self.log("end")
        self.__log_template.close()

    def handle_start_command(self):
        if self.__state == "initialized":
            self.on_start()
            self.send_command("STARTED")
            self.__state = "started"
        else:
            self.send_command("ERROR JSV script got START but is in state {}".format(self.__state))

    def handle_begin_command(self):
        if self.__state == "started":
            self.__state = "verifying"
            self.on_verify()
            self.clear_params()
            self.clear_envs()
        else:
            self.send_command("ERROR JSV script got BEGIN but is in state {}".format(self.__state))

    def handle_param_command(self, param, value):
        self.param[param] = {}
        if "," in value:
            _list = []
            for v in value.split(","):
                if "=" in v:
                    t = v.split("=", 1)
                    _list.append({t[0]: t[1]})
                else:
                    _list.append(v)
                self.param[param] = _list
        else:
            if "=" in value:
                t = value.split("=", 1)
                self.param[param][t[0]] = t[1]
            else:
                self.param[param] = value

    def handle_env_command(self, action, name, data):
        if action == "DEL":
            if name in self.env:
                del(self.env[name])
        else:
            self.env[name] = data

    def on_verify(self):
        self.accept()

    def on_start(self):
        pass

    def accept(self, reason="everything ok"):
        if self.__state == "verifying":
            self.send_command("RESULT STATE ACCEPT {}".format(reason))
            self.__state = "initialized"
        else:
            self.send_command("ERROR JSV script tried to send RESULT but was in state {}".format(self.__state))

    def correct(self, reason="something changed"):
        if self.__state == "verifying":
            self.send_command("RESULT STATE CORRECT {}".format(reason))
            self.__state = "initialized"
        else:
            self.send_command("ERROR JSV script tried to send RESULT but was in state {}".format(self.__state))

    def reject(self, reason="rejected"):
        if self.__state == "verifying":
            self.send_command("RESULT STATE REJECT {}".format(reason))
            self.__state = "initialized"
        else:
            self.send_command("ERROR JSV script tried to send RESULT but was in state {}".format(self.__state))

    def reject_wait(self, reason="rejected, wait"):
        if self.__state == "verifying":
            self.send_command("RESULT STATE REJECT_WAIT {}".format(reason))
            self.__state = "initialized"
        else:
            self.send_command("ERROR JSV script tried to send RESULT but was in state {}".format(self.__state))

    def clear_envs(self):
        self.env = {}

    def clear_params(self):
        self.param = {}

    def is_env(self, var):
        return var in self.env

    def get_env(self, var):
        if self.is_env(var):
            return self.env['var']
        else:
            return None

    def add_env(self, var, val):
        if not self.is_env(var):
            self.env[var] = val
            self.send_command('ENV ADD {} {}'.format(var, val))

    def mod_env(self, var, val):
        if self.is_env(var):
            self.env[var] = val
            self.send_command('ENV MOD {} {}'.format(var, val))

    def del_env(self, var):
        if self.is_env(var):
            del self.env[var]
            self.send_command('ENV DEL {}'.format(var))

    def show_params(self):
        for k, v in self.param.iteritems():
            self.log_sge("got param {}={}".format(k, v))

    def show_envs(self):
        for k, v in self.env.iteritems():
            self.log_sge("got env {}={}".format(k, v))

    def send_env(self):
        self.send_command("SEND ENV")

    def has_param(self, param):
        return param in self.param

    def get_param(self, param):
        return self.param.get(param, None)

    def set_param(self, param, val):
        self.param[param] = val
        self.send_command("PARAM {} {}".format(param, val))

    def del_param(self, param):
        if self.has_param(param):
            del(self.param[param])
            self.send_command("PARAM {}".format(param))

    # def sub_is_param(self, param, var):
    #    if self.has_param(param):
    #        _v = self.get_param(param)
    #        if type(_v) is dict:
    #            return var in _v
    #    return False

    # def sub_get_param(self, param, var):
    #    if self.sub_is_param(param, var):
    #        return self.get_param(param)[var]
    #    else:
    #        return None

    # def sub_add_param(self, param, var, val):
    #    if self.is_param(param):
    #        self.param[param][var] = val
    #    else:
    #        self.param[param] = {var: val}
    #    args = []
    #    for item in self.param[param].iteritems():
    #        if item[1] is None:
    #            args.append(item[0])
    #        else:
    #            args.append('='.join(item))
    #    args = ",".join(args)
    #    self.send_command("PARAM {} {}".format(param, args))

    # def sub_del_param(self, param, var):
    #    if self.is_param(param) and self.sub_is_param(param, var):
    #        del(self.param[param][var])
    #    args = []
    #    for item in self.param[param].iteritems():
    #        if item[1] is None:
    #            args.append(item[0])
    #        else:
    #            args.append('='.join(item))
    #    args = ",".join(args)
    #    self.send_command("PARAM {} {}".format(param, args))
