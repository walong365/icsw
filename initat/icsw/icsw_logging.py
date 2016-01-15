#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" loggers for commandline usage """

import datetime
import time
import os
import sys

from initat.tools import logging_tools
from initat.constants import LOG_ROOT

__all__ = [
    "get_logger",
    "install_global_logger",
]


def _get_logger(log_all):
    def logger(what, log_level=logging_tools.LOG_LEVEL_OK):
        if log_all or log_level > logging_tools.LOG_LEVEL_OK:
            print(
                u"{} [{}] {}".format(
                    str(datetime.datetime.now()),
                    logging_tools.get_log_level_str(log_level),
                    what
                )
            )
    return logger


def get_logger(name, options, **kwargs):
    log_type = options.logger
    log_all = options.logall
    if log_type == "stdout":
        if log_all or kwargs.get("all", False):
            return _get_logger(True)
        else:
            return _get_logger(False)
    else:
        return logging_tools.get_logger(
            "icsw_{}".format(name),
            "uds:/var/lib/logging-server/py_log_zmq",
            zmq=True,
            init_logger=True,
        ).log


class Redirect(object):
    def __init__(self, glog, io_type):
        self.glog = glog
        self.io_type = io_type

    def write(self, what):
        self.glog.write(self.io_type, what)

    def flush(self):
        pass


class GLog(object):
    def __init__(self):

        self._log_dir = os.path.join(LOG_ROOT, "setup", "{:d}".format(int(time.time())))
        try:
            os.makedirs(self._log_dir)
        except:
            self._log_dir = os.path.join("/tmp", "icsw_setup", "{:d}".format(int(time.time())))
            os.makedirs(self._log_dir)
        self._prev = {
            "stdout": sys.stdout,
            "stderr": sys.stderr,
        }
        self._names = {
            key: os.path.join(self._log_dir, key) for key in {"stdout", "stderr", "unified"}
        }
        self._ends_with_cr = {key: True for key in self._names.iterkeys()}
        self._last_was_debug = {key: False for key in self._names.iterkeys()}
        print("Logs are in {}".format(self._log_dir))
        sys.stdout = Redirect(self, "stdout")
        sys.stderr = Redirect(self, "stderr")

    def transform(self, io_type, what):
        _pf = "[{}] ".format(time.ctime())
        if self._ends_with_cr[io_type]:
            what = "{}{}".format(_pf, what)
        _ends_with_cr = what.endswith("\n")
        self._ends_with_cr[io_type] = _ends_with_cr
        if _ends_with_cr:
            what = what[:-1].replace("\n", "\n{}".format(_pf)) + "\n"
        else:
            what = what.replace("\n", "\n{}".format(_pf))
        return what

    def write(self, io_type, what):
        # is a debug line ?
        if what.startswith("<DBG>"):
            _debug = True
            what = what[5:]
        else:
            _debug = False
        file(self._names[io_type], "a").write(self.transform(io_type, what))
        file(self._names["unified"], "a").write(self.transform("unified", what))
        if not _debug:
            if self._last_was_debug[io_type] and what in ["\n"]:
                pass
            else:
                self._prev[io_type].write(what)
        self._last_was_debug[io_type] = _debug


def install_global_logger():
    GLog()
