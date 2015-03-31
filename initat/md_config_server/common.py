# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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
import csv

import os.path
import socket
from initat.md_config_server.config import global_config


class live_query(object):
    def __init__(self, conn, resource):
        self._conn = conn
        self._resource = resource
        self._columns = []
        self._filters = []

    def call(self):
        if self._columns:
            return self._conn.call(str(self), self._columns)
        else:
            return self._conn.call(str(self))

    def __str__(self):
        r_field = ["GET {}".format(self._resource)]
        if self._columns:
            r_field.append("Columns: {}".format(" ".join(self._columns)))
        r_field.extend(self._filters)
        return "\n".join(r_field + ["", ""])

    def columns(self, *args):
        self._columns = args
        return self

    def filter(self, key, op, value):
        if type(value) == list:
            for entry in value:
                self._filters.append("Filter: {} {} {}".format(key, op, entry))
            if len(value) > 1:
                self._filters.append("Or: {:d}".format(len(value)))
        else:
            self._filters.append("Filter: {} {} {}".format(key, op, value))
        return self


class live_socket(object):
    def __init__(self, peer_name):
        self.peer = peer_name

    def __getattr__(self, name):
        return live_query(self, name)

    def call(self, request, columns=None):
        s = None
        try:
            if len(self.peer) == 2:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.peer)
            s.send(request)
            s.shutdown(socket.SHUT_WR)
            csv_lines = csv.DictReader(s.makefile(), columns, delimiter=';')
            _result = list(csv_lines)
        except:
            _result = []
        finally:
            if s is not None:
                s.close()
        return _result

    @classmethod
    def get_icinga_live_socket(cls):
        sock_name = "/opt/{}/var/live".format(global_config["MD_TYPE"])
        if os.path.exists(sock_name):
            return live_socket(sock_name)
        else:
            raise IOError("socket '{}' does not exist".format(sock_name))