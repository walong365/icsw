#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009,2012-2015 Andreas Lang-Nevyjel
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
""" generates zonefiles for nsX.init.at """

import argparse
import os
import pwd


def parse_options(**kwargs):
    _mon_machs = kwargs.get("monitor_machines", [])
    machname = os.uname()[1]
    try:
        _named = pwd.getpwnam("named")
    except:
        _uid, _gid = (0, 0)
    else:
        _uid, _gid = (_named.pw_uid, _named.pw_gid)
    _parser = argparse.ArgumentParser()
    _parser.add_argument("--creator", type=str, default="lang.init.at.", help="set creator in SOA records [%(default)s]")
    _parser.add_argument("--tmpdir", type=str, default="", help="temporary directory, when not set create one (for testing) [%(default)s]")
    _parser.add_argument("--mode", type=str, default="multi", choices=["multi", "single"], help="set mode [%(default)s]")
    _parser.add_argument("--hostname", type=str, default=machname, help="set name of host [%(default)s]")
    _parser.add_argument("--uid", type=int, default=_uid, help="uid of named [%(default)d]")
    _parser.add_argument("--gid", type=int, default=_gid, help="gid of named [%(default)d]")
    _parser.add_argument("--nameddir", type=str, default="/var/lib/named/", help="run-directory of named [%(default)s]")
    _parser.add_argument("--named-run-dir", type=str, default="/var/lib/named/", help="run-directory of named [%(default)s]")
    _parser.add_argument("--named-conf-dir", type=str, default="/etc/named.d/", help="conf-directory of named [%(default)s]")
    _parser.add_argument("--key-dir", type=str, default=".dns_keys", help="location of dns_keys (local to homedir) [%(default)s]")
    _parser.add_argument(
        "--primary",
        type=str,
        default=kwargs.get("primary_ns", "xeon.init.at:192.168.1.50"),
        help="comma-separated list of primary nameserver(s) [%(default)s]"
    )
    _parser.add_argument(
        "--secondary",
        type=str,
        default=kwargs.get("secondary_ns", "im.init.at:192.168.1.60"),
        help="comma-separated list of secodary nameserver(s) [%(default)s]"
    )
    _parser.add_argument("--deploy", default=False, action="store_true", help="deploy config to configured nameservers [%(default)s]")
    _parser.add_argument("--restart", default=False, action="store_true", help="restart nameservers instead of simple reload [%(default)s]")
    _parser.add_argument("--profile", default=False, action="store_true", help="profile run [%(default)s]")
    _parser.add_argument("--dryrun", default=False, action="store_true", help="enable dryrun mode (for deploy) [%(default)s]")
    _parser.add_argument("--deploy-map", default="", type=str, help="deployment IP map [%(default)s]")
    _parser.add_argument(
        "--monitoring",
        default=False,
        action="store_true",
        help="update monitoring records [%(default)s], only possible on {}".format(
            ", ".join(_mon_machs),
        )
    )
    _parser.add_argument("--mon-config-name", type=str, default="gz_bind_auto", help="name of ns config [%(default)s]")
    _opts = _parser.parse_args()
    if machname not in _mon_machs:
        _opts.monitoring = False
    if _opts.monitoring and not _opts.tmpdir:
        raise ValueError("Monitoring update only for testing run")
    if _opts.mode == "single":
        _opts.type = "master"
    # show opts
    print("Options (after parsing and cleanup):")
    for _key in sorted(dir(_opts)):
        if not _key.startswith("_"):
            print("    {:<40s} : {}".format(_key, getattr(_opts, _key)))
    return _opts
