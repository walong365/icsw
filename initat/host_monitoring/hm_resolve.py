# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" caching resolver """

import socket
import time

from initat.tools import logging_tools, process_tools, threading_tools, logging_functions, config_store

CACHE_TIMEOUT = 20


class CacheEntry(object):
    def __init__(self, source, result):
        self.source = source
        self.result = result
        self.init_time = time.time()

    def check_for_timeout(self, cur_time):
        if abs(cur_time - self.init_time) > CACHE_TIMEOUT:
            return True
        else:
            return False


class ResolveProcess(threading_tools.icswProcessObj):
    def process_init(self):
        self.__log_template = logging_functions.get_logger(
            config_store.ConfigStore("client", quiet=True),
            "{}/{}".format(
                process_tools.get_machine_name(),
                self.global_config["LOG_NAME"],
            ),
            process_name=self.name,
        )
        # log.startLoggingWithObserver(my_observer, setStdout=False)
        self.__debug = self.global_config["DEBUG"]
        self.register_func("resolve", self._resolve, greedy=True)
        # clear flag for extra twisted thread
        self.__cache = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _resolve_addr(self, addr, overload=False):
        cur_time = time.time()
        _renew = True
        if addr in self.__cache:
            _ce = self.__cache[addr]
            if _ce.check_for_timeout(cur_time):
                del self.__cache[addr]
            else:
                _renew = False
                result = _ce.result
        if _renew:
            try:
                if overload:
                    # overload mode, do not ask the nameservers
                    result = None
                else:
                    result = socket.gethostbyname(addr)
            except:
                self.log("cannot resolve {}: {}".format(addr, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                result = None
            self.__cache[addr] = CacheEntry(addr, result)
        return result

    def _resolve(self, r_list):
        overload = len(r_list) > 4
        if len(r_list) > 1:
            self.log(
                "resolve_list has {:d} entries{}".format(
                    len(r_list),
                    ", overload" if overload else ""
                ),
                logging_tools.LOG_LEVEL_ERROR if overload else logging_tools.LOG_LEVEL_WARN
            )
        for _src_proc, _cur_mes in r_list:
            _id, _addr_list = _cur_mes["args"][:2]
            self.send_pool_message("resolved", _id, [self._resolve_addr(_addr, overload=overload) for _addr in _addr_list], target="socket")
