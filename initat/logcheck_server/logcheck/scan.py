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
""" keeps syslog check commands from FS in sync with database """

import os

from initat.constants import USER_EXTENSION_ROOT
from initat.tools import logging_tools


class LogcheckScanner(object):
    def __init__(self, proc):
        self.proc = proc
        self.root_dir = os.path.join(USER_EXTENSION_ROOT, "logcheck_server.d")
        self.log("init LogCheckScanner")
        self.rescan()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[LCS] {}".format(what), log_level)

    def rescan(self):
        if not os.path.isdir(self.root_dir):
            self.log("dir {} does not exist, skipping scan", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("scanning {} for new / updated SyslogCheck(s)".format(self.root_dir))
