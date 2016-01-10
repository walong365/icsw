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

from initat.tools import logging_tools

__all__ = [
    "get_logger",
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
