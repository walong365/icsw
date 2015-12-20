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
functions for relay cstore handling
"""

import pprint
import sys
import re

from initat.tools.config_store import ConfigStore
from initat.host_monitoring.discovery import CS_NAME
from initat.tools import logging_tools


ADDR_RE = re.compile("^(?P<proto>\S+)@(?P<addr>[^:]+):(?P<port>\d+)$")


def quiet_log(_a, _b):
    pass


class HRSink(dict):
    def __init__(self, opts):
        self.opts = opts
        dict.__init__(self)

    def feed(self, key, value):
        if not value.startswith("urn:uuid:"):
            print("correcting value '{}' by adding urn:uuid: prefix".format(value))
            value = "urn:uuid:{}".format(value)
        # check for service postfix
        if value.count(":") > 2:
            _parts = value.split(":", 3)
            service = _parts.pop(-1)
            value = ":".join(_parts)
        else:
            service = None
        _proto, _addr, _port = parse_key(key)
        if self.opts.port and self.opts.port != _port:
            pass
        else:
            self.setdefault(value, {}).setdefault(_port, []).append((key, service))

    def filter(self):
        if self.opts.remove_unique:
            _del = []
            for _uuid, _struct in self.iteritems():
                if len(_struct.keys()) == 1:
                    if len(_struct.values()[0]) == 1:
                        _del.append(_uuid)
            for _dk in _del:
                del self[_dk]

    def dump(self):
        _keys = sorted(self.keys())
        print("Found {}:".format(logging_tools.get_plural("unique UUID", len(_keys))))
        for _key in _keys:
            _struct = self[_key]
            _ports = sorted(_struct.keys())
            _single = len(_ports) == 1 and len(_struct[_ports[0]]) == 1
            print(
                "{} with {:s}: {}{}".format(
                    _key,
                    logging_tools.get_plural("port", len(_ports)),
                    ", ".join(["{:d}".format(_port) for _port in _ports]),
                    ", {}".format(port_info(_struct[_ports[0]][0])) if _single else "",
                )
            )
            if not _single:
                for _port in _ports:
                    print(
                        "    port {:5d}: {}".format(
                            _port,
                            logging_tools.get_plural("entry", len(_struct[_port])),
                        )
                    )
                    for _entry in _struct[_port]:
                        print(
                            "        {}".format(
                                port_info(_entry),
                            )
                        )


def parse_key(in_key):
    km = ADDR_RE.match(in_key)
    if km:
        _gd = km.groupdict()
        return (_gd["proto"], _gd["addr"], int(_gd["port"]))
    else:
        print("unable to parse address '{}'".format(in_key))
        return None


def port_info(in_tuple):
    _srv = in_tuple[1]
    if _srv:
        if _srv.endswith(":"):
            _srv = _srv[:-1]
    else:
        _srv = "hm"
    return "{} via {}".format(_srv, in_tuple[0])


def log_com(a, b):
    print "[{:>6s}] {}".format(logging_tools.get_log_level_str(b), a)


def reload_relay():
    print("reloading relayer")
    from initat.icsw.service import transition, container, instance
    cur_c = container.ServiceContainer(log_com)
    cur_t = transition.ServiceTransition(
        "reload",
        ["host-relay"],
        cur_c,
        instance.InstanceXML(log_com),
        log_com,
    )
    while True:
        _left = cur_t.step(cur_c)
        if _left:
            time.sleep(1)
        else:
            break
    print("done")


def main(opts):
    store = ConfigStore(CS_NAME)
    sink = HRSink(opts)
    for _key, _value in store.get_dict().iteritems():
        sink.feed(_key, _value)
    sink.filter()
    _changed = False
    if opts.mode == "dump":
        sink.dump()
    elif opts.mode == "remove":
        _addr_list = [_entry.strip().lower() for _entry in opts.address.split(",") if _entry.strip()]
        if not _addr_list:
            print("no addresses given to remove")
            sys.exit(-1)
        print(
            "{}: {}".format(
                logging_tools.get_plural("remove address", len(_addr_list)),
                ", ".join(_addr_list),
            )
        )
        _del_keys = []
        for _key in store.keys():
            _proto, _addr, _port = parse_key(_key)
            if opts.port and _port != opts.port:
                continue
            if _addr.lower() in _addr_list:
                print(
                    "removing {} [UUID: {}]".format(
                        _key,
                        store[_key]
                    )
                )
                _del_keys.append(_key)
        if _del_keys:
            _changed = True
            print("{} to delete".format(logging_tools.get_plural("entry", len(_del_keys))))
            for _key in _del_keys:
                del store[_key]
            store.write()
        else:
            print("nothing changed")
    if _changed:
        reload_relay()
