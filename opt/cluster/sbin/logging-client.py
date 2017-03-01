#!/usr/bin/python3-init -Ot
#
# Copyright (c) 2006-2011,2015,2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
""" client for logging-server """


import argparse

from initat.tools import io_stream_helper, logging_tools, threading_tools
from initat.logging_server.constants import ICSW_LOG_BASE, icswLogHandleTypes, get_log_path


class MyOptions(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        self.add_argument("-L", default=False, dest="use_log_com", action="store_true", help="use log_command instead of io_stream [%(default)s]")
        self.add_argument(
            "-d",
            type=str,
            dest="handle",
            choices=[_entry.value for _entry in icswLogHandleTypes],
            default=icswLogHandleTypes.log.value,
            help="set destination [%(default)s]"
        )
        self.add_argument("-t", default=10, type=int, dest="timeout", help="set timeout in seconds [%(default)d]")
        self.add_argument("-m", default=1, type=int, dest="mult", help="set multiplicator for loggstr to stress logging-client [%(default)d]")
        self.add_argument("-n", default=1, type=int, dest="processes", help="set number of concurrent processes to stress logging-client [%(default)d]")
        self.add_argument("-r", default=1, type=int, dest="repeat", help="set number of log repeat to stress logging-client [%(default)d]")
        self.add_argument("--log-name", default="logging_client", type=str, dest="log_name", help="name of logging instance [%(default)s]")
        self.add_argument("args", nargs="+")


class MyLogProcess(threading_tools.icswProcessObj):
    def __init__(self, t_name, options, log_template):
        self.__options = options
        threading_tools.icswProcessObj.__init__(self, t_name)

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            self.__options.log_name,
            get_log_path(icswLogHandleTypes(self.__options.handle)),
            context=self.zmq_context
        )
        self.__log_template.log_command("set_max_line_length {:d}".format(256))
        self.__log_str = self.__options.mult * (" ".join(self.__options.args))
        self.log("log_str has {}".format(logging_tools.get_plural("byte", len(self.__log_str))))
        self.register_func("start_logging", self._start_logging)

    def log(self, what, log_lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_lev, what)

    def _start_logging(self, **kwargs):
        self.log("start logging")
        emitted = 0
        for rep_num in range(self.__options.repeat):
            self.log("{:d}/{:d}: {}".format(rep_num + 1, self.__options.repeat, self.__log_str))
            emitted += len(self.__log_str)
        self.log("bytes emitted: {}".format(logging_tools.get_size_str(emitted)))
        self.send_pool_message("stop_logging", emitted)

    def loop_post(self):
        self.__log_template.close()


class MyProcessPool(threading_tools.icswProcessPool):
    def __init__(self, options):
        self.__options = options
        self.__log_template, self.__log_cache = (None, [])
        threading_tools.icswProcessPool.__init__(self, self.__options.log_name)
        self.__log_template = logging_tools.get_logger(
            options.log_name,
            get_log_path(icswLogHandleTypes(options.handle)),
            context=self.zmq_context
        )
        self.__log_template.log_command("set_max_line_length {:d}".format(256))
        self.register_func("stop_logging", self._stop_logging)
        self.__process_names = []
        # init processes
        for t_num in range(self.__options.processes):
            cur_name = "process_{:d}".format(t_num + 1)
            self.add_process(MyLogProcess(cur_name, self.__options, self.__log_template), start=True)
            self.__process_names.append(cur_name)
        self.__processes_running = len(self.__process_names)
        self.__bytes_total = 0
        [self.send_to_process(t_name, "start_logging") for t_name in self.__process_names]

    def log(self, what, log_lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            if self.__log_cache:
                for c_log_lev, c_what in self.__log_cache:
                    self.__log_template.log(c_log_lev, c_what)
                self.__log_cache = []
            self.__log_template.log(log_lev, what)
        else:
            self.__log_cache.append((log_lev, what))

    def _stop_logging(self, p_name, p_pid, num_bytes, **kwargs):
        self.__bytes_total += num_bytes
        self.__processes_running -= 1
        if self.__processes_running:
            self.log("{} still logging".format(logging_tools.get_plural("process", self.__processes_running)))
        else:
            self.log("bytes emitted: {}".format(logging_tools.get_size_str(self.__bytes_total)))
            self["exit_requested"] = True

    def loop_post(self):
        self.__log_template.close()


def main():
    options = MyOptions().parse_args()
    if options.use_log_com:
        MyProcessPool(options).loop()
    else:
        io_stream_helper.icswIOStream(icswLogHandleTypes(options.handle)).write(" ".join(options.args))


if __name__ == "__main__":
    main()
