# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-client
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
"""
functions for config store
"""

import sys

from initat.tools import logging_tools, process_tools
from initat.tools.config_store import ConfigStore


def quiet_log(_a, _b):
    pass


def _show_store(opts, store):
    print("Read store {} ({}):".format(opts.store, store.info))
    _dict_store = True if store.prefix else False
    if _dict_store:
        _dict_keys = store.keys(only_dict=True)
    else:
        _dict_keys = []
    # all keys
    _all_keys = list(store.keys())
    # flat (== non-dict) keys
    _flat_keys = set(_all_keys) - set(_dict_keys)
    _dict = store.get_dict()
    if opts.sort_by_value:
        _keys = [
            _key for (_value, _key) in sorted(
                [
                    (_dict[_key], _key) for _key in _flat_keys
                    ]
            )
            ]
    else:
        _keys = sorted(_flat_keys)
    if _flat_keys:
        print("Flat keys ({:d}):".format(len(_flat_keys)))
        for _key in _keys:
            _value = store[_key]
            print(
                "    {:<30s} ({:<13s}): {}".format(
                    _key,
                    str(type(_value)),
                    str(_value),
                )
            )
    if _dict_keys:
        print("Dict keys ({:d}):".format(len(_dict_keys)))
        for _key in sorted(_dict_keys):
            _value = store[_key]
            print(
                "    dict index {} ({})".format(
                    _key,
                    logging_tools.get_plural("value", len(list(_value.keys()))),
                )
            )
            for _dkey in sorted(_value.keys()):
                _dvalue = _value[_dkey]
                print(
                    "        {:<30s} ({:<13s}): {}".format(
                        _dkey,
                        str(type(_dvalue)),
                        str(_dvalue),
                    )
                )


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
            store = ConfigStore(opts.store, log_com=quiet_log, fix_prefix_on_read=False)
            _show_store(opts, store)
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
        if not opts.key:
            print("Need valid key")
            sys.exit(4)
        print("setting key '{}' of store {} to '{}'".format(opts.key, opts.store, opts.value))
        _store[opts.key] = opts.value
        _store.write()
    elif opts.mode == "addprefix":
        if not ConfigStore.exists(opts.store):
            print("CStore {} does not exist".format(opts.store))
        else:
            _store = ConfigStore(opts.store, fix_prefix_on_read=False)
            if _store.prefix:
                print("CStore {} already has a prefix: {}".format(opts.store, _store.info))
            elif not opts.prefix:
                print("Need prefix")
            else:
                print("Adding prefix {} to cstore ({})".format(opts.prefix, _store.info))
                print("Moving all current keys to index {}".format(opts.index))
                _store.set_prefix(opts.prefix, opts.index)
                _show_store(opts, _store)
                _store.write()
    elif opts.mode == "createstore":
        if ConfigStore.exists(opts.store):
            print("CStore {} already exists".format(opts.store))
        else:
            _new_c = ConfigStore(opts.store)
            _new_c.write()
            print("Createted CStore {}".format(opts.store))
