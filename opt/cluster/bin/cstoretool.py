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
frontend tool to config store
"""

import sys
import argparse


def quiet_log(_a, _b):
    pass


def main():
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--mode", default="getkey", choices=["getkey", "storeexists", "keyexists"], type=str, help="Operation mode [%(default)s]")
    _ap.add_argument("--store", default="client", type=str, help="ConfigStore name [%(default)s]")
    _ap.add_argument("--key", default="", type=str, help="Key to show [%(default)s]")
    opts = _ap.parse_args()
    if opts.mode == "storeexists":
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


if __name__ == "__main__":
    main()
