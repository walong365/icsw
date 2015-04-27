#!/usr/bin/python-init -Otu
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

""" daemonizes a given server """

import setproctitle
import sys
import importlib
import pwd
import grp

import daemon
from initat.tools.io_stream_helper import io_stream


def get_gid_from_name(group):
    try:
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '{}', using {} ({:d})".format(group, new_gid_name, new_gid))
    return new_gid, new_gid_name


def get_uid_from_name(user):
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        logging_tools.my_syslog("Cannot find user '{}', using {} ({:d})".format(user, new_uid_name, new_uid))
    return new_uid, new_uid_name


def get_gid_from_name(group):
    try:
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '{}', using {} ({:d})".format(group, new_gid_name, new_gid))
    return new_gid, new_gid_name


def main():
    prog_name, module_name, prog_title = sys.argv[1:4]
    if len(sys.argv) > 4:
        user_name, group_name = sys.argv[4:6]
        uid = get_uid_from_name(user_name)[0]
        gid = get_gid_from_name(group_name)[0]
        if len(sys.argv) > 6:
            gids = [get_gid_from_name(_gid)[0] for _gid in sys.argv[6].split(",")]
            _daemon_context = daemon.DaemonContext(detach_process=True, uid=uid, gid=gid, gids=gids)
        else:
            _daemon_context = daemon.DaemonContext(detach_process=True, uid=uid, gid=gid)
    else:
        _daemon_context = daemon.DaemonContext(detach_process=True)
    _daemon_context.open()
    sys.argv = [prog_name]
    setproctitle.setproctitle(prog_title)
    main_module = importlib.import_module(module_name)
    sys.stdout = io_stream("/var/lib/logging-server/py_log_zmq")
    sys.stderr = io_stream("/var/lib/logging-server/py_err_zmq")
    main_module.main()


if __name__ == "__main__":
    main()
