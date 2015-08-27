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
"""
functions for config store
"""

import sys

from initat.tools.config_store import ConfigStore


def quiet_log(_a, _b):
    pass


def main(opts):
    if opts.mode == "liststores":
        print("not implemented")
    elif opts.mode == "storeexists":
        if ConfigStore.exists(opts.store):
            sys.exit(0)
        else:
            sys.exit(1)
    elif opts.mode == "getkey":
        _store = ConfigStore(opts.store, log_com=quiet_log)
        if opts.key in _store:
            print(_store[opts.key])
            sys.exit(0)
        else:
            raise KeyError("unknown key '{}'".format(opts.key))
