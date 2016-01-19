# Copyright (C) 2001-2008,2012-2016 Andreas Lang-Nevyjel, init.at
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
""" raid controller base structures and helper functions """

import commands
import os
import time

from initat.host_monitoring import hm_classes
from initat.tools import logging_tools, process_tools, server_command


class ctrl_type(object):
    _all_types = None
    all_struct = None

    def __init__(self, module_struct, all_struct, **kwargs):
        self.name = self.Meta.name
        self.kernel_modules = getattr(self.Meta, "kernel_modules", [])
        self._modules_loaded = False
        # allraidctrl struct
        ctrl_type.all_struct = all_struct
        # last scan date
        self.scanned = None
        # last check date
        self.checked = None
        self._dict = {}
        self._module = module_struct
        self._check_exec = None
        if not kwargs.get("quiet", False):
            self.log("init")

    def load_kernel_modules(self):
        if not self._modules_loaded:
            self._modules_loaded = True
            if self.kernel_modules:
                self.log(
                    "trying to load {}: {}".format(
                        logging_tools.get_plural("kernel module", len(self.kernel_modules)),
                        ", ".join(self.kernel_modules)
                    )
                )
                mp_command = process_tools.find_file("modprobe")
                for kern_mod in self.kernel_modules:
                    cmd = "{} {}".format(mp_command, kern_mod)
                    c_stat, c_out = commands.getstatusoutput(cmd)
                    self.log(
                        "calling '{}' gave ({:d}): {}".format(
                            cmd,
                            c_stat,
                            c_out
                        )
                    )

    # calls to all_raidctrl
    @staticmethod
    def update(name, ctrl_ids=[]):
        return ctrl_type.all_struct.update(name, ctrl_ids)

    @staticmethod
    def ctrl(key):
        if ctrl_type.all_struct is None:
            from initat.host_monitoring.modules.raidcontrollers.all import AllRAIDCtrl
            return AllRAIDCtrl.ctrl(key)
        else:
            return ctrl_type.all_struct.ctrl(key)

    @staticmethod
    def ctrl_class(key):
        if ctrl_type.all_struct is None:
            from initat.host_monitoring.modules.raidcontrollers.all import AllRAIDCtrl
            return AllRAIDCtrl.ctrl_class(key)
        else:
            return ctrl_type.all_struct.ctrl_class(key)

    def exec_command(self, com_line, **kwargs):
        if com_line.startswith(" "):
            com_line = "{}{}".format(self._check_exec, com_line)
        cur_stat, cur_out = commands.getstatusoutput(com_line)
        lines = cur_out.split("\n")
        if cur_stat:
            self.log("{} gave {:d}:".format(com_line, cur_stat), logging_tools.LOG_LEVEL_ERROR)
            for line_num, cur_line in enumerate(lines):
                self.log("  {:<3d} {}".format(line_num + 1, cur_line), logging_tools.LOG_LEVEL_ERROR)
        if "post" in kwargs:
            lines = [getattr(cur_line, kwargs["post"])() for cur_line in lines]
        if kwargs.get("super_strip", False):
            lines = [" ".join(line.strip().split()) for line in lines]
        if not kwargs.get("empty_ok", False):
            lines = [cur_line for cur_line in lines if cur_line.strip()]
        # print cur_stat, lines
        return cur_stat, lines

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._module.log("[ct {}] {}".format(self.name, what), log_level)

    def _scan(self):
        self.load_kernel_modules()
        self.scanned = time.time()
        self.log("scanning for {} controller".format(self.name))
        self.check_for_exec()
        if self._check_exec:
            self.log("scanning for {}".format(self.Meta.description))
            self.scan_ctrl()

    def _update(self, ctrl_ids):
        if not self.scanned:
            self._scan()
        self.update_ctrl(ctrl_ids)

    def get_exec_name(self):
        if type(self.Meta.exec_name) is list:
            return ", ".join(self.Meta.exec_name)
        else:
            return self.Meta.exec_name

    def check_for_exec(self):
        if self._check_exec is None:
            if type(self.Meta.exec_name) is list:
                _cns = self.Meta.exec_name
            else:
                _cns = [self.Meta.exec_name]
            # iterate over check_names
            for _cn in _cns:
                for s_path in ["/opt/cluster/sbin", "/sbin", "/usr/sbin", "/bin", "/usr/bin"]:
                    cur_path = os.path.join(s_path, _cn)
                    if os.path.islink(cur_path):
                        self._check_exec = os.path.normpath(os.path.join(cur_path, os.readlink(cur_path)))
                        break
                    elif os.path.isfile(cur_path):
                        self._check_exec = cur_path
                        break
                if self._check_exec is not None:
                    break
        if self._check_exec:
            self.log("found check binary for {} at '{}'".format(_cn, self._check_exec))
        else:
            self.log(
                "no check binary '{}' found".format(
                    self.get_exec_name(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def controller_list(self):
        return self._dict.keys()

    def scan_ctrl(self):
        # override to scan for controllers
        pass

    def update_ctrl(self, *args):
        # override to update controllers, args optional
        pass

    def update_ok(self, srv_com):
        # return True if update is OK, can be overridden to add more checks (maybe arguments)
        if self._check_exec:
            return True
        else:
            srv_com.set_result(
                "monitoring tool '{}' missing".format(self.get_exec_name()),
                server_command.SRV_REPLY_STATE_ERROR
            )
            return False


class ctrl_check_struct(hm_classes.subprocess_struct):
    class Meta:
        verbose = True
        id_str = "raid_ctrl"

    def __init__(self, log_com, srv_com, ct_struct, ctrl_list=[]):
        self.__log_com = log_com
        self.__ct_struct = ct_struct
        hm_classes.subprocess_struct.__init__(self, srv_com, ct_struct.get_exec_list(ctrl_list))

    def process(self):
        try:
            self.__ct_struct.process(self)
        except:
            exc_info = process_tools.exception_info()
            for _line in exc_info.log_lines:
                self.log(_line, logging_tools.LOG_LEVEL_ERROR)
            self.srv_com.set_result(
                "error in process() call: {}".format(
                    process_tools.get_except_info()
                ),
                server_command.SRV_REPLY_STATE_CRITICAL
            )

    def started(self):
        if hasattr(self.__ct_struct, "started"):
            self.__ct_struct.started(self)
            self.send_return()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[ccs] {}".format(what), level)
