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

from initat.tools import logging_tools


def stdout_logger(what, log_level=logging_tools.LOG_LEVEL_OK):
    if log_level > logging_tools.LOG_LEVEL_OK:
        print(u"[{}] {}".format(logging_tools.get_log_level_str(log_level), what))


def stdout_all_logger(what, log_level=logging_tools.LOG_LEVEL_OK):
    print(u"[{}] {}".format(logging_tools.get_log_level_str(log_level), what))


def get_logger(name, options, **kwargs):
    log_type = options.logger
    log_all = options.logall
    if log_type == "stdout":
        if log_all or kwargs.get("all", False):
            return stdout_all_logger
        else:
            return stdout_logger
    else:
        return logging_tools.get_logger(
            "icsw_{}".format(name),
            "uds:/var/lib/logging-server/py_log_zmq",
            zmq=True,
            init_logger=True,
        ).log
