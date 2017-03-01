# Copyright (C) 2014,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server
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
""" SNMP result functions """


def oid_to_str(oid):
    if isinstance(oid, tuple):
        oid = ".".join(["{:d}".format(_p) for _p in oid])
    return oid


def simplify_dict(in_dict, start_tuple, sub_key_filter=[]):
    # check in_dict for all keys starting with start_tuple and return a reordered dict for faster
    # processing
    _slist = list(start_tuple)
    # get all valid keys
    _ref_keys = set([_key for _key in in_dict.keys() if list(_key)[:len(start_tuple)] == _slist])
    # the last entry is the reference idx
    _result = {}
    if sub_key_filter:
        for _key in _ref_keys:
            _s_key = _key[len(start_tuple):]
            if _s_key[0] in sub_key_filter:
                if len(_s_key) == 2:
                    # integer as key
                    _result.setdefault(_s_key[1], {})[_s_key[0]] = in_dict[_key]
                elif _s_key:
                    # tuple as key
                    _result.setdefault(tuple(list(_s_key[1:])), {})[_s_key[0]] = in_dict[_key]
    else:
        for _key in _ref_keys:
            _s_key = _key[len(start_tuple):]
            if len(_s_key) == 2:
                # integer as key
                _result.setdefault(_s_key[1], {})[_s_key[0]] = in_dict[_key]
            elif _s_key:
                # tuple as key
                _result.setdefault(tuple(list(_s_key[1:])), {})[_s_key[0]] = in_dict[_key]
            else:
                _result[None] = in_dict[_key]
    return _result


def reorder_dict(in_dict):
    # take in dict an reorder it using the following method:
    # in_dict: {key:value} where key has the form (idx, key[::])
    r_dict = {}
    for key, value in in_dict.items():
        r_dict.setdefault(key[1:], {})[key[0]] = value
    return r_dict


def flatten_dict(in_dict):
    _changed = True
    while _changed:
        _changed = False
        if len(in_dict) == 1:
            in_dict = list(in_dict.values())[0]
        _r_dict = {}
        for _key, _value in in_dict.items():
            if isinstance(_value, dict):
                _changed = True
                if isinstance(_key, int):
                    _key = [_key]
                else:
                    _key = list(_key)
                for _s_key, _s_value in _value.items():
                    if isinstance(_s_key, int):
                        _s_key = _key + [_s_key]
                    else:
                        _s_key = _key + list(_s_key)
                    _r_dict[tuple(_s_key)] = _s_value
            else:
                _r_dict[_key] = _value
        in_dict = _r_dict
    return _r_dict
