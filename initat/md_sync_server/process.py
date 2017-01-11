# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" interface to control icinga daemon for md-sync-server """

import codecs
import os
import time
import subprocess
import signal

from initat.tools import logging_tools, process_tools
from initat.md_sync_server.config import global_config
import psutil


class ExternalProcess(object):
    def __init__(self, log_com, name, command, create_files):
        self.__name = name
        self.__command = command
        self.__log_com = log_com
        self.__create_files = create_files

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(
            "[EP {}] {}".format(
                self.__name,
                what,
            ),
            log_level
        )

    def close(self):
        self.log("closed")

    def run(self):
        for _name, _cf in self.__create_files.items():
            if not os.path.isfile(_name):
                try:
                    open(_name, "w").close()
                except:
                    self.log(
                        "error creating file {}: {}".format(
                            _name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    self.log("created {}".format(_name))
            else:
                self.log("file {} already present".format(_name))
        self.start_time = time.time()
        self.log("starting command '{}'".format(self.__command))
        self.popen = subprocess.Popen(
            self.__command,
            bufsize=128,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
            cwd="/",
        )
        self.log("start with pid {} (detached)".format(self.popen.pid))

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except (OSError, ValueError):
                self.log("error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")

    def terminate(self):
        try:
            pid = self.popen.pid
            self.popen.terminate()
        except (OSError, ValueError):
            self.log("error in popen.terminate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("called terminate (pid={:d})".format(pid))

    def kill(self):
        try:
            pid = self.popen.pid
            self.popen.kill()
        except (OSError, ValueError):
            self.log("error in popen.kill: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("called kill (pid={:d})".format(pid))

    def wait(self):
        try:
            pid = self.popen.pid
            self.popen.wait()
        except (OSError, ValueError):
            self.log("error in popen.wait: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("called wait (pid={:d})".format(pid))

    @property
    def return_code(self):
        if self.popen:
            return self.popen.returncode
        else:
            return None


class ProcessControl(object):
    def __init__(self, proc, proc_name, pid_file_name):
        self.__process = proc
        self.__proc_name = proc_name
        self.__pid_file_name = pid_file_name
        self.log("init (pid_file_name={})".format(self.__pid_file_name))
        self.__ext_process = None
        self.__external_cmd_file = None
        self.check_state()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            "[PC {}] {}".format(self.__proc_name, what),
            log_level
        )

    def check_state(self):
        _proc = self._get_proc()
        if _proc is None:
            return False
        elif _proc is not None:
            return True

    def _get_pid_from_file(self):
        _pid_present = os.path.isfile(self.__pid_file_name)
        if _pid_present:
            try:
                _pid = open(self.__pid_file_name, "r").read().strip()
                if len(_pid):
                    _pid = int(_pid.split()[0])
                    try:
                        _proc = psutil.Process(_pid)
                    except:
                        self.log(
                            "cannot get process from pid {:d}: {}".format(
                                _pid,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        _pid = None
                    else:
                        if _proc.name() != self.__proc_name:
                            self.log(
                                "process name of pid {:d} does not match {}: {}".format(
                                    _pid,
                                    self.__proc_name,
                                    _proc.name()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            self.log("removing pid file {}".format(self.__pid_file_name))
                            os.unlink(self.__pid_file_name)
                            _pid = None
                else:
                    _pid = None
            except:
                self.log(
                    "error getting pid from {} :{}".format(
                        self.__pid_file_name,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                _pid = None
        else:
            _pid = None
        return _pid

    def write_external_cmd_file(self, lines):
        if self.check_state() and self.__external_cmd_file and os.path.exists(self.__external_cmd_file):
            if type(lines) != list:
                lines = [lines]
            try:
                codecs.open(self.__external_cmd_file, "w", "utf-8").write("\n".join(lines + [""]))
            except:
                self.log(
                    "error writing to {}: {}".format(
                        self.__external_cmd_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                raise
        else:
            self.log("process not running or external cmd file not present", logging_tools.LOG_LEVEL_ERROR)

    def kill_old_instances(self):
        self.log("checking for old instances")
        for _proc in psutil.process_iter():
            try:
                if _proc.name().count("icinga"):
                    _cmdline = _proc.cmdline()
                    _path = _cmdline[0]
                    if _path.startswith("/opt/") and _path.count("icinga"):
                        self.log("trying to kill process {} ({})".format(_proc.pid, _proc.name()))
                        _proc.send_signal(9)
            except:
                self.log("error in handing process entry: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        self.log("done")

    def _get_proc(self):
        _pid = self._get_pid_from_file()
        if _pid is not None:
            try:
                _proc = psutil.Process(_pid)
            except:
                self.log(
                    "error getting process from pid {:d}: {}".format(
                        _pid,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                _proc = None
            else:
                pass
        else:
            _proc = None
        return _proc

    def send_signal(self, signal_num):
        _pid = self._get_pid_from_file()
        if _pid is not None:
            self.log("sending signal {:d} to Process {:d}".format(signal_num, _pid))
            try:
                _proc = psutil.Process(pid=_pid)
                _proc.send_signal(signal_num)
            except:
                self.log("error sending signal: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                pass
        else:
            self.log("PID not defined or found", logging_tools.LOG_LEVEL_ERROR)

    def stop(self):
        self.log("stopping process")
        if self.__ext_process:
            self.__ext_process.communicate()
            self.__ext_process.terminate()
            self.__ext_process.kill()
            self.__ext_process = None
        # kill pids
        if os.path.isfile(self.__pid_file_name):
            _pid = self._get_pid_from_file()
            if _pid is not None:
                for _signal, _wait_time in [(signal.SIGTERM, 5), (signal.SIGKILL, 0)]:
                    try:
                        os.kill(_pid, _signal)
                    except:
                        self.log(
                            "error sending {:d} to {:d}: {}".format(
                                _signal,
                                _pid,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log("sent {:d} to {:d}".format(_signal, _pid))
                    _s_time = time.time()
                    while True:
                        try:
                            _cur_proc = psutil.Process(pid=_pid)
                        except:
                            break
                        else:
                            self.log("process still present, waiting...")
                            _c_time = time.time()
                            if _wait_time and abs(_c_time - _s_time) < _wait_time:
                                time.sleep(1)
                            else:
                                break
        # kill all icinga processes
        for _proc in psutil.process_iter():
            if _proc.name == self.__proc_name:
                print(_proc)

    def check_md_config(self):
        # checks the current config and returns True or False
        _valid = False
        _check_com = "{} -v -d {}".format(
            os.path.join(
                global_config["MD_BASEDIR"],
                "bin",
                self.__proc_name,
            ),
            os.path.join(
                global_config["MD_BASEDIR"],
                "etc",
                "icinga.cfg",
            ),
        )
        self.log("checking md-config")
        _check_proc = self._start_ext_proc(_check_com)
        _check_proc.close()
        return _valid

    def _start_ext_proc(self, com_str):
        # start external process with command string com_tr
        self.log("starting process (com_str {})".format(com_str))
        ext_proc = ExternalProcess(
            self.log,
            self.__proc_name,
            com_str,
            {
                os.path.join(
                    global_config["MD_BASEDIR"],
                    "var",
                    "icinga.log",
                ): True,
                os.path.join(
                    global_config["MD_BASEDIR"],
                    "var",
                    "retention.dat",
                ): True,
                os.path.join(
                    global_config["MD_BASEDIR"],
                    "var",
                    "icinga.lock",
                ): True,
            }
        )
        ext_proc.run()
        ext_proc.wait()
        self.log("returncode is {}".format(ext_proc.return_code))
        return ext_proc

    def start(self):
        self.stop()
        _com = "{} -d {}".format(
            os.path.join(
                global_config["MD_BASEDIR"],
                "bin",
                self.__proc_name,
            ),
            os.path.join(
                global_config["MD_BASEDIR"],
                "etc",
                "icinga.cfg",
            ),
        )

        self.__ext_process = self._start_ext_proc(_com)
        self.__external_cmd_file = os.path.join(
            global_config["MD_BASEDIR"],
            "var",
            "icinga.cmd"
        )
        if self.__ext_process.popen.returncode is not None:
            self.log(
                "returncode is {}, closing ext_process".format(
                    self.__ext_process.return_code
                ),
            )
            self.__ext_process.close()
            self.__ext_process = None
