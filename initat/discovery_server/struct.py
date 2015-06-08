#
# this file is part of discovery-server
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel init.at
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

import subprocess
import time

from initat.tools import logging_tools, process_tools


class ExtCom(object):
    run_idx = 0

    def __init__(self, log_com, command, debug=False, name=None, detach=False):
        ExtCom.run_idx += 1
        self.__name = name
        self.__detach = detach
        self.idx = ExtCom.run_idx
        self.command = command
        self.popen = None
        self.debug = debug
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(
            u"[ec {:d}{}] {}".format(
                self.idx,
                ", {}".format(self.__name) if self.__name else "",
                what,
            ),
            log_level
        )

    def run(self):
        self.start_time = time.time()
        if self.__detach:
            self.popen = subprocess.Popen(
                self.command,
                bufsize=1,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True
            )
            self.log("start with pid {} (detached)".format(self.popen.pid))
        else:
            self.popen = subprocess.Popen(
                self.command,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            if self.debug:
                self.log("start with pid {}".format(self.popen.pid))

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except OSError:
                self.log(u"error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")

    def finished(self):
        self.result = self.popen.poll()
        if self.result is not None:
            self.end_time = time.time()
        return self.result

    def terminate(self):
        self.popen.kill()
