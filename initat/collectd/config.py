#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

""" base constants and logging base """

import logging_tools

IPC_SOCK = "ipc:///var/log/cluster/sockets/collectd/com"
RECV_PORT = 8002
COMMAND_PORT = 8008
GRAPHER_PORT = 8003

LOG_NAME = "collectd"
LOG_DESTINATION = "ipc:///var/lib/logging-server/py_log_zmq"

class log_base(object):
    def __init__(self):
        self.__log_template = logging_tools.get_logger(
            LOG_NAME,
            LOG_DESTINATION,
            zmq=True,
            context=self.zmq_context)
    @property
    def log_template(self):
        return self.__log_template
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def close_log(self):
        self.__log_template.close()

