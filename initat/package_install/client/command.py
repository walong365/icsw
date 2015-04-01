# Copyright (C) 2001-2009,2012-2014 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" package install, simple command structure """

import logging_tools
import subprocess
import time

# copy from command_tools.py (package mother)
class simple_command(object):
    sc_idx = 0
    com_list = []
    stream_dict = {}
    def __init__(self, com_str, **kwargs):
        simple_command.sc_idx += 1
        self.idx = simple_command.sc_idx
        self.com_str = com_str
        self.command_stage = kwargs["command_stage"]
        # stream_id, None for unsorted
        # streams with the same id are processed strictly in order
        # (for example to feed the DHCP-server)
        self.stream_id, self.stream = (kwargs.get("stream_id", None), None)
        self.__log_com = kwargs.get("log_com", None)
        self.delay_time = kwargs.get("delay_time", 0)
        self.done_func = kwargs.get("done_func", None)
        self.start_time, self.popen = (None, None)
        self.info = kwargs.get("info", None)
        self.max_run_time = kwargs.get("max_run_time", 600)
        self.log(
            "init {}-command {}{}, {}".format(
                self.command_stage,
                "with {}".format(
                    logging_tools.get_plural(
                        "line",
                        len(self.com_str.split("\n")))) if kwargs.get("short_info", True) else "'{}'".format(self.com_str),
                " ({})".format(
                    kwargs.get("add_info", "")) if "add_info" in kwargs else "",
                "delay is {}".format(
                    logging_tools.get_plural("second", self.delay_time)
                ) if self.delay_time else "no delay"
            )
        )
        if self.delay_time:
            simple_command.process.register_timer(self.call, self.delay_time, oneshot=True)
        else:
            self.call()
        if "data" in kwargs:
            self.data = kwargs["data"]
        simple_command.com_list.append(self)
        # print "add", len(simple_command.com_list)
    @staticmethod
    def setup(process):
        simple_command.process = process
        simple_command.process.log("init simple_command metastructure")
    @staticmethod
    def check():
        cur_time = time.time()
        new_list = []
        for com in simple_command.com_list:
            keep = True
            if com.start_time:
                if com.finished():
                    com.done()
                    keep = False
                elif abs(cur_time - com.start_time) > com.max_run_time:
                    com.log("maximum runtime exceeded, killing", logging_tools.LOG_LEVEL_ERROR)
                    keep = False
                    com.terminate()
            if keep:
                new_list.append(com)
        simple_command.com_list = new_list
    @staticmethod
    def idle():
        return True if not simple_command.com_list else False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[sc {:d}] {}".format(self.idx, what), log_level)
        else:
            simple_command.process.log("[sc {:d}] {}".format(self.idx, what), log_level)
    def terminate(self):
        if self.popen:
            del self.popen
    def finished(self):
        self.result = self.popen.poll()
        return self.result != None
    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None
    def done(self):
        self.end_time = time.time()
        if self.done_func:
            self.done_func(self)
        else:
            simple_command.process.sc_finished(self)
        if self.stream:
            self.stream.done()
    def call(self):
        self.start_time = time.time()
        self.popen = subprocess.Popen(self.com_str, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
