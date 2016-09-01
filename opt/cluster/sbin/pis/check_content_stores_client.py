#!/usr/bin/python-init -Ot
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
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

""" check values in client content stores """

import os

from initat.constants import LOG_ROOT
from initat.tools import config_store

OLD_LOG_DIR = "/var/log/cluster/logging-server"
NEW_LOG_DIR = os.path.join(LOG_ROOT, "logging-server")


def main():
    c_store = config_store.ConfigStore("client")
    if c_store["log.logdir"] == OLD_LOG_DIR:
        c_store["log.logdir"] = NEW_LOG_DIR
        c_store.write()


if __name__ == "__main__":
    main()
