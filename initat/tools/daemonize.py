#!/usr/bin/python-init -Otu
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" daemonizes a given server """

from __future__ import unicode_literals, print_function

import argparse
import grp
import importlib
import os
import pwd
import setproctitle
import sys

import daemon


#  do NOT put initat imports here (otherwise path manipulations below will not work)


def get_gid_from_name(group):
    try:
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        from initat.tools import logging_tools
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
        from initat.tools import logging_tools
        new_uid, new_uid_name = (0, "root")
        logging_tools.my_syslog("Cannot find user '{}', using {} ({:d})".format(user, new_uid_name, new_uid))
    return new_uid, new_uid_name


def main():
    _parser = argparse.ArgumentParser()
    _parser.add_argument("-d", dest="daemonize", default=False, action="store_true", help="daemonize process [%(default)s]")
    _parser.add_argument("--progname", default="", type=str, help="programm name for sys.argv [%(default)s]")
    _parser.add_argument("--modname", default="", type=str, help="python module to load [%(default)s]")
    _parser.add_argument("--exename", default="", type=str, help="exe to start [%(default)s]")
    _parser.add_argument("--proctitle", default="", type=str, help="process title to set [%(default)s]")
    _parser.add_argument("--user", type=str, default="root", help="user to use for the process [%(default)s]")
    _parser.add_argument("--group", type=str, default="root", help="group to use for the process [%(default)s]")
    _parser.add_argument("--groups", type=str, default="", help="comma-separated list of groups for the process [%(default)s]")
    _parser.add_argument("--nice", type=int, default=0, help="set nice level of new process [%(default)d]")
    _parser.add_argument("--debug", default=False, action="store_true", help="enable debug mode (modify sys.path), [%(default)s]")
    _parser.add_argument("--debug-flag", default=False, action="store_true", help="enable debug flag via environment (modify sys.path), [%(default)s]")
    _parser.add_argument("extra_args", nargs="*", type=str, help="extra  arguments")
    opts = _parser.parse_args()
    if opts.exename:
        _mode = "exe"
        _args = [opts.exename]
    else:
        _mode = "python"
        _args = [opts.progname]
    if opts.user != "root":
        uid = get_uid_from_name(opts.user)[0]
    else:
        uid = 0
    if opts.group != "root":
        gid = get_gid_from_name(opts.group)[0]
    else:
        gid = 0
    if opts.groups.strip():
        gids = [get_gid_from_name(_gid)[0] for _gid in opts.groups.strip().split(",")]
    else:
        gids = []
    _daemon_context = daemon.DaemonContext(
        detach_process=True,
        uid=uid,
        gid=gid,
        gids=gids,
        # valid with python-daemonize-2.1.2
        # init_groups=False
    )
    if opts.nice:
        os.nice(opts.nice)
    if opts.daemonize:
        _daemon_context.open()
    else:
        if gids:
            os.setgroups(gids)
        if uid or gid:
            os.setgid(gid)
            os.setuid(uid)
    if _mode == "python":
        os.environ["LC_LANG"] = "en_us.UTF_8"
        os.environ["PYTHONIOENCODING"] = "utf_8"
        # python path
        if opts.debug:
            # set debug flag
            os.environ["ICSW_DEBUG_SOFTWARE"] = "1"
            abs_path = os.path.dirname(__file__)
            abs_path = os.path.split(os.path.split(abs_path)[0])[0]
            sys.path.insert(0, abs_path)
            _args.append("-d")
            if opts.debug_flag:
                os.environ["DEBUG_WEBFRONTEND"] = "yes"
        if opts.extra_args:
            _args.extend(opts.extra_args)
        sys.argv = _args
        setproctitle.setproctitle(opts.proctitle)
        main_module = importlib.import_module(opts.modname)
        if opts.daemonize:
            # redirect IO-streams
            from initat.tools.io_stream_helper import icswIOStream
            sys.stdout = icswIOStream("/var/lib/logging-server/py_log_zmq")
            sys.stderr = icswIOStream("/var/lib/logging-server/py_err_zmq")
        main_module.main()
    else:
        # path for standard exe (munge, redis)
        if opts.extra_args:
            _args.extend(opts.extra_args)
        setproctitle.setproctitle(opts.proctitle)
        # if opts.daemonize:
        #    # redirect IO-streams
        #    from initat.tools.io_stream_helper import icswIOStream
        #    sys.stdout = icswIOStream("/var/lib/logging-server/py_log_zmq")
        #    sys.stderr = icswIOStream("/var/lib/logging-server/py_err_zmq")
        os.execv(_args[0], _args)
        # print("*", _args, os.getuid(), os.getgid())
        # subprocess.call(_args)


if __name__ == "__main__":
    main()
