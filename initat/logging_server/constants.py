# -*- coding: utf-8 -*-
#
# Copyright (C) 2009-2017 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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

""" logging server, constatns for streams """

from enum import Enum


class icswLogHandleTypes(Enum):
    log = "log"
    log_py = "log_py"
    err_py = "err_py"

ICSW_LOG_BASE = "/var/lib/logging-server"


def get_log_path(log_type):
    return "ipc://{}/{}_zmq".format(
        ICSW_LOG_BASE,
        log_type.value,
    )
