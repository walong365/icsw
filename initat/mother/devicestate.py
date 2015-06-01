# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" pinger support code """

import re
import pprint
import time

from django.db.models import Q
from initat.tools import logging_tools, process_tools
from .command_tools import simple_command
from .config import global_config
from initat.cluster.backbone.models import device


class ResultStream(object):
    def __init__(self, max_length=10):
        self.results = []
        self.max_length = max_length

    def feed(self, element):
        self.results.insert(0, element)
        self.results = self.results[:self.max_length]

    def __repr__(self):
        return "{}, {}".format(
            logging_tools.get_plural("element", len(self.results)),
            ", ".join([unicode(_val) for _val in self.results]),
        )

    def __getitem__(self, idx):
        return self.results[idx]

    def __len__(self):
        return len(self.results)


class HostStatusInfo(object):
    def __init__(self, instance, text, source):
        self.instance = instance
        self.text = text
        # info or status
        self.source = source
        self.when = time.time()

    def __unicode__(self):
        return "{} from {}[{}] at {:d}".format(
            self.text,
            self.instance,
            self.source,
            int(self.when),
        )

    def __repr__(self):
        return unicode(self)


class PingInfo(object):
    def __init__(self, result):
        self.when = time.time()
        self.success = True if result["recv_ok"] else False
        self.ip = result["host"]
        self.network = result["network"]

    def __repr__(self):
        return "PI {}@{} ({})".format(
            self.ip,
            self.network,
            "up" if self.success else "down",
        )


class DSDevice(object):
    ping_id = 0

    def __init__(self, log_com, dev, ping_only):
        # True for controlling devices
        self.__log_com = log_com
        self.ping_only = ping_only
        self.pk = dev.pk
        self.uuid = dev.uuid
        self.boot_uuid = dev.get_boot_uuid()
        self.full_name = unicode(dev)
        self.uuids = [self.pk, self.uuid, self.boot_uuid]
        # dict of IPs
        self.ip_dict = None
        # latest 10 hoststatus infos
        self.ping_info = ResultStream()
        if not self.ping_only:
            self.hoststatus_info = ResultStream()
        # pinger helper
        self.last_required = None
        # last ping(s) sent
        self.last_sent = None
        # pings pending
        self.pending = 0
        self.wait_list = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[{}] {}".format(self.full_name, what), log_level)

    def set_ip_dict(self, ip_dict):
        prev_dict = self.ip_dict
        self.ip_dict = {
            key: (
                value.network.network_type.identifier,
                value.network.identifier
            ) for key, value in ip_dict.iteritems() if value.network.network_type.identifier not in ["s", "l"]
        }
        if prev_dict is None:
            _prev_id_str = ""
        else:
            _prev_id_str = ", ".join(
                [
                    "{}[{}]".format(_key, prev_dict[_key][0]) for _key in sorted(prev_dict)
                ]
            )
        _new_id_str = ", ".join(
            [
                "{}[{}]".format(_key, self.ip_dict[_key][0]) for _key in sorted(self.ip_dict)
            ]
        )
        if _prev_id_str != _new_id_str:
            self.log(
                "set ip_dict to {}".format(_new_id_str)
            )

    def get_ip_list(self):
        return self.ip_dict.keys()

    def get_hoststatus_uuid(self, ip):
        if ip in self.ip_dict:
            if self.ip_dict[ip] == "b":
                return self.boot_uuid
            else:
                return self.uuid
        else:
            return self.uuid

    def feed_hoststatus(self, instance, text, source):
        self.hoststatus_info.feed(HostStatusInfo(instance, text, source))
        # print self.hoststatus_info

    def require(self):
        self.last_required = time.time()

    def do_ping(self, cur_time):
        return self._required(cur_time) and self._ping_allowed(cur_time) and self._non_pending(cur_time)

    def _ping_allowed(self, cur_time):
        # return True if last_sent is at least 5 seconds ago
        if self.last_sent:
            return abs(self.last_sent - cur_time) > 5
        else:
            return True

    def _required(self, cur_time):
        # return True if last required is at most 30 seconds ago
        if self.last_required:
            return abs(cur_time - self.last_required) < 30
        else:
            return False

    def start_ping(self):
        self.last_sent = time.time()

    def _non_pending(self, cur_time):
        # return True if no pings are pending
        return True if self.pending == 0 else False

    def emit_ping(self, ip):
        if not self.pending:
            # wait for first ping
            self.await_result = True
        self.pending += 1
        DSDevice.ping_id += 1
        DSDevice.ping_id %= 40000
        _cur_id = "icsw_MI_{:05d}@{:05d}".format(DSDevice.ping_id, self.pk)
        self.wait_list.append(_cur_id)
        return _cur_id

    def feed_result(self, _key, _result):
        # return value, is the IP-address of the hostatus to connect to or None
        _rvalue = None
        # self.wait_list.remove(_key)g
        self.pending -= 1
        self.wait_list.remove(_key)
        if self.await_result:
            # take first result
            self.await_result = False
            _result["network"] = self.ip_dict[_result["host"]][1]
            self.ping_info.feed(PingInfo(_result))
        if _result["recv_ok"]:
            _rvalue = _result["host"]
        if not self.pending:
            # pprint.pprint(self.wait_dict)
            # print "***", time.ctime(time.time())
            pass
        return _rvalue

    def get_state(self):
        cur_time = time.time()
        _cs = CurrentState(self.pk)
        if self.ping_info:
            _latest = self.ping_info[0]
            if abs(_latest.when - cur_time) < 15:
                _cs.feed_ping_info(_latest)
            # print self.ping_info
            if not self.ping_only:
                if self.hoststatus_info:
                    _latest = self.hoststatus_info[0]
                    if abs(_latest.when - cur_time) < 15:
                        _cs.feed_hoststatus(_latest)
        return _cs


class CurrentState(object):
    # stores current state info
    def __init__(self, pk):
        # reachable network
        self.network = None
        # state (True is up, False is down, None is unknown)
        self.state = None
        # reachable ip
        self.ip = None
        self.hoststatus = None
        self.hoststatus_source = None
        self.pk = pk

    def __repr__(self):
        return "CS@{:d}, {} ({}), {}".format(
            self.pk or 0,
            self._get_ip_state(),
            self.ip or "???",
            "hoststatus is '{}' ({})".format(
                self.hoststatus,
                self.hoststatus_source,
            ) if self.hoststatus else "no hoststatus",
        )

    def _get_ip_state(self):
        return {
            None: "unknown",
            True: "up",
            False: "down",
        }[self.state]

    def feed_hoststatus(self, hi):
        self.hoststatus = hi.text
        self.hoststatus_source = hi.source

    def feed_ping_info(self, pi):
        self.network = pi.network
        self.ip = pi.ip
        self.state = pi.success

    def modify_xml(self, xml_el):
        # stores state info in XML element
        xml_el.attrib.update(
            {
                "ip_state": self._get_ip_state(),
                "network": self.network or "",
                "ip": self.ip or "",
                "hoststatus": self.hoststatus or "",
                "hoststatus_source": self.hoststatus_source or "",
            }
        )


class DeviceState(object):
    def __init__(self, process, log_com):
        self.process = process
        self.__log_com = log_com
        self.log("init")
        # uuid, boot_uuid, pk -> dev
        self.__dev_pks = set()
        self.__unique_keys = set()
        self.__devices = {}
        # add private communication socket
        self.process.add_com_socket()
        self.process.bind_com_socket("icmp")
        self.process.register_timer(self.ping, 2)

    def add_device(self, dev, ping_only=False):
        # dev ... device object
        if dev.pk not in self.__dev_pks:
            _new_dsd = DSDevice(self.log, dev, ping_only)
            self.__dev_pks.add(dev.pk)
            for _new_id in _new_dsd.uuids:
                self.__unique_keys.add(_new_id)
                self.__devices[_new_id] = _new_dsd
            self.log(
                "added new device {} ({})".format(
                    unicode(dev),
                    ", ".join([str(_val) for _val in _new_dsd.uuids]),
                )
            )

    def require_ping(self, pk_list):
        for _pk in pk_list:
            if _pk in self.__devices:
                _dev = self.__devices[_pk]
                _dev.require()
            else:
                self.log("unknown device with pk {:d} (require_ping)".format(_pk), logging_tools.LOG_LEVEL_ERROR)
        # start pinging
        self.ping()

    def remove_device(self, pk):
        _dsd = self.__devices[pk]
        self.log("removing device {} with pk {}".format(_dsd.full_name, pk))
        self.__dev_pks.remove(_dsd.pk)
        for _id in _dsd.uuids:
            self.__unique_keys.remove(_id)
            del self.__devices[_id]

    def device_present(self, pk):
        return pk in self.__devices

    def set_ip_dict(self, pk, ip_dict):
        self.__devices[pk].set_ip_dict(ip_dict)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[DS] {}".format(what), log_level)

    def _get_non_idle_devices(self):
        cur_time = time.time()
        return [
            self.__devices[_pk] for _pk in self.__dev_pks if self.__devices[_pk].do_ping(cur_time)
        ]

    def ping(self):
        _non_idle = self._get_non_idle_devices()
        for _dev in _non_idle:
            _dev.start_ping()
            # print("ping to {}".format(_dev.full_name))
            for _ip in _dev.get_ip_list():
                _id_str = _dev.emit_ping(_ip)
                self.process.send_pool_message(
                    "ping",
                    _id_str,
                    _ip,
                    4,
                    3.0,
                    target_process="icmp",
                    ret_queue="control",
                )

    def ping_result(self, *args, **kwargs):
        # key is also in result
        _key, _result = args[0:2]
        try:
            _dev_pk = int(_key.split("@")[1])
        except ValueError, IndexError:
            self.log("error parsing key '{}': {}".format(_key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            if _dev_pk in self.__devices:
                _dev = self.__devices[_dev_pk]
                _hoststatus_ip = _dev.feed_result(_key, _result)
                if _hoststatus_ip:
                    self.process.send_pool_message(
                        "contact_hoststatus",
                        _dev.get_hoststatus_uuid(_hoststatus_ip),
                        "status",
                        _hoststatus_ip,
                    )
            else:
                self.log("pk {:d} not present in devices, discarding".format(_dev_pk), logging_tools.LOG_LEVEL_ERROR)

    def soft_control(self, dev_node, command):
        # send soft_control command to device in XML-element dev_node idx==pk
        _pk = int(dev_node.attrib["pk"])
        if _pk in self.__devices:
            _dev = self.__devices[_pk]
            if dev_node.get("ip", ""):
                if dev_node.get("hoststatus", ""):
                    self.process.send_pool_message(
                        "contact_hoststatus",
                        _dev.get_hoststatus_uuid(dev_node.attrib["ip"]),
                        command,
                        dev_node.attrib["ip"],
                    )
                else:
                    dev_node.attrib["soft_control_error"] = "hoststatus not set"
            else:
                dev_node.attrib["soft_control_error"] = "IP-address not set"
        else:
            dev_node.attrib["soft_control_error"] = "device not known to DeviceState"

    # feeds from hoststatus
    def feed_nodestatus(self, src_id, text):
        # required from mother
        node_id, instance = src_id.split(":", 1)
        self._feed_hoststatus(node_id, instance, text, "req")

    def feed_nodeinfo(self, src_id, text):
        # actively sent from node
        node_id, instance = src_id.split(":", 1)
        self._feed_hoststatus(node_id, instance, text, "recv")

    def _feed_hoststatus(self, node_id, instance, text, source):
        if node_id in self.__devices:
            self.__devices[node_id].feed_hoststatus(instance, text, source)
        else:
            self.log("unknown device {}".format(node_id))

    def get_device_state(self, pk):
        # return a devicestate record
        if pk in self.__devices:
            return self.__devices[pk].get_state()
        else:
            return CurrentState()
