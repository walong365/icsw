#
# this file is part of collectd-init
#
# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
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

""" background job for collectd-init """

from initat.collectd.collectd_structs import host_info
from initat.collectd.collectd_types import * # @UnusedWildImport
from initat.collectd.config import IPC_SOCK, log_base
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import logging_tools
import multiprocessing
import process_tools
import threading
import signal
import re
import server_command
import time
import uuid_tools
import zmq

class background(multiprocessing.Process, log_base):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="collectd_background")
    def _init(self):
        threading.currentThread().name = "background"
        # init zmq_context and logging
        self.zmq_context = zmq.Context()
        log_base.__init__(self)
        self.log("background started")
        # ignore signals
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        self._init_sockets()
    def _init_sockets(self):
        self.com = self.zmq_context.socket(zmq.ROUTER)
        self.com.setsockopt(zmq.IDENTITY, "bg")
        self.com.connect(IPC_SOCK)
    def _close(self):
        self._close_sockets()
    def _close_sockets(self):
        self.com.close()
        self.log("background finished")
        self.close_log()
        self.zmq_context.term()
    def _code(self):
        self._init()
        self.__run = True
        while self.__run:
            try:
                src_id = self.com.recv_unicode()
            except:
                self.log("exception raised in recv:", logging_tools.LOG_LEVEL_ERROR)
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    self.log(line, logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("got data from {}".format(src_id))
                data = self.com.recv_pyobj()
                if data == "exit":
                    self.__run = False
        self._close()
