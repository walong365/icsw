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
from initat.tools import logging_tools, process_tools


def quiet_log(_a, _b):
    pass


def main(opts):
    if opts.mode == "liststores":
        _names = ConfigStore.get_store_names()
        if opts.quiet:
            print(" ".join(_names))
        else:
            print("Found {}:".format(logging_tools.get_plural("CStore", len(_names))))
            for _name in _names:
                try:
                    _store = ConfigStore(_name, log_com=quiet_log)
                except:
                    print(
                        " ** corrupt store {}: {}".format(
                            _name,
                            process_tools.get_except_info(),
                        )
                    )
                else:
                    print("    {:<34s} ({})".format(_name, _store.info))
    elif opts.mode == "showstore":
        if ConfigStore.exists(opts.store):
            _store = ConfigStore(opts.store, log_com=quiet_log)
            print("Read store {} ({}):".format(opts.store, _store.info))
            _dict = _store.get_dict()
            if opts.sort_by_value:
                _keys = [_key for (_value, _key) in sorted([(str(_value), _key) for _key, _value in _dict.iteritems()])]
            else:
                _keys = sorted(_dict.keys())
            for _key in _keys:
                _value = _store[_key]
                print(
                    "    {:<30s} ({:<13s}): {}".format(
                        _key,
                        str(type(_value)),
                        str(_value),
                    )
                )
        else:
            print("unknown store {}".format(opts.store))
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
    elif opts.mode == "setkey":
        _store = ConfigStore(opts.store)
        print("setting key '{}' of store {} to '{}'".format(opts.key, opts.store, opts.value))
        _store[opts.key] = opts.value
        _store.write()
    elif opts.mode == "createstore":
        if ConfigStore.exists(opts.store):
            print("CStore {} already exists".format(opts.store))
        else:
            _new_c = ConfigStore(opts.store)
            _new_c.write()
            print("Createted CStore {}".format(opts.store))