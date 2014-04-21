#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012,2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" classes for handling external command """

# import commands
import time
import subprocess
import logging_tools

class command_stream(object):
    def __init__(self, stream_id):
        self.stream_id = stream_id
        self.log("init stream")
        self.__commands = []
        self.__running = False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        simple_command.process.log("[cs {}] {}".format(self.stream_id, what), log_level)
    def new_command(self, new_sc):
        self.__commands.append(new_sc)
        new_sc.stream = self
        if not self.__running:
            self.__running = True
            self.__commands.pop(0).call()
    def done(self):
        if self.__commands:
            self.__commands.pop(0).call()
        else:
            self.__running = False
        
class simple_command(object):
    sc_idx = 0
    com_list = []
    stream_dict = {}
    def __init__(self, com_str, **kwargs):
        simple_command.sc_idx += 1
        self.idx = simple_command.sc_idx
        self.com_str = com_str
        # stream_id, None for unsorted
        # streams with the same id are processed strictly in order
        # (for example to feed the DHCP-server)
        self.stream_id, self.stream = (kwargs.get("stream_id", None), None)
        self.__log_com = kwargs.get("log_com", None)
        self.delay_time = kwargs.get("delay_time", 0)
        self.done_func = kwargs.get("done_func", None)
        self.start_time, self.popen = (None, None)
        self.info = kwargs.get("info", None)
        self.max_run_time = kwargs.get("max_run_time", 30)
        self.log("init command %s%s, delay is %s" % (
            "with %s" % (logging_tools.get_plural("line", len(self.com_str.split("\n")))) if kwargs.get("short_info", True) else "'%s'" % (self.com_str),
            " (%s)" % (kwargs.get("add_info", "")) if "add_info" in kwargs else "",
            logging_tools.get_plural("second", self.delay_time)))
        if self.delay_time:
            simple_command.process.register_timer(self.call, self.delay_time, oneshot=True)
        else:
            if self.stream_id:
                simple_command.feed_stream(self)
            else:
                self.call()
        simple_command.com_list.append(self)
    @staticmethod
    def feed_stream(cur_sc):
        if not cur_sc.stream_id in simple_command.stream_dict:
            simple_command.stream_dict[cur_sc.stream_id] = command_stream(cur_sc.stream_id)
        simple_command.stream_dict[cur_sc.stream_id].new_command(cur_sc)
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
            self.__log_com("[sc %d] %s" % (self.idx, what), log_level)
        else:
            simple_command.process.log("[sc %d] %s" % (self.idx, what), log_level)
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
