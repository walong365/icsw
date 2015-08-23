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
""" DHCP support code """

import re
import pprint

from django.db.models import Q
from initat.tools import logging_tools
from .command_tools import simple_command
from .config import global_config
from initat.cluster.backbone.models import device


class DHCPCommand(object):
    def __init__(self, name, uuid=None, ip=None, mac=None, server_ip=None):
        self.name = name
        self.uuid = uuid
        self.ip = ip
        self.mac = mac
        self.server_ip = server_ip

    def __repr__(self):
        if self.ip:
            return "set device {}[{}] ({}@{} from {})".format(
                self.name,
                self.uuid,
                self.ip,
                self.mac,
                self.server_ip,
            )
        else:
            return "delete device {}".format(
                self.name,
            )

    def __unicode__(self):
        return repr(self)


class DHCPState(object):
    def __init__(self, syncer, name):
        self.syncer = syncer
        self.name = name
        # present in DHCP config
        self.set_result({})

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.syncer.log(
            "[State {}] {}".format(
                self.name,
                what
            )
        )

    def set_result(self, in_dict):
        _uuid = in_dict.get("uuid", None)
        if _uuid:
            try:
                cur_dev = device.objects.get(Q(uuid=_uuid))
            except device.DoesNotExist:
                cur_dev = None
        else:
            cur_dev = None
        if "ip-address" in in_dict and "error" not in in_dict:
            _action = "write"
            self.present = True
            self.ip = ".".join(["{:d}".format(int(_part, 16)) for _part in in_dict["ip-address"].split(":")])
            self.mac = in_dict["hardware-address"]
            if cur_dev:
                cur_dev.dhcp_written = True
                cur_dev.dhcp_error = ""
            self.log("present in leases")
        else:
            _action = "delete"
            self.present = False
            self.ip = None
            self.mac = None
            if cur_dev:
                cur_dev.dhcp_written = False
                cur_dev.dhcp_error = in_dict.get("error", "")
            self.log("not present in leases")
        if cur_dev is not None:
            if cur_dev.dhcp_error:
                cur_dev.add_log_entry(
                    source=global_config["LOG_SOURCE_IDX"],
                    level=logging_tools.LOG_LEVEL_ERROR,
                    text="DHCP: {}".format(cur_dev.dhcp_error),
                )
            else:
                cur_dev.add_log_entry(
                    source=global_config["LOG_SOURCE_IDX"],
                    text="DHCP: {} is ok".format(_action),
                )
            cur_dev.save(update_fields=["dhcp_written", "dhcp_error"])

    def __unicode__(self):
        return "DHCPState for {}, is {}{}".format(
            self.name,
            "present" if self.present else "not present",
            " ({}@{})".format(self.ip, self.mac) if self.present else "",
        )

    def __repr__(self):
        return unicode(self)


class DHCPSyncer(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init")
        # raw input queue
        self.__raw_input = []
        # waiting queue, waiting for base info from DHCP
        self.__waiting_queue = []
        # pending queue, waiting for action info from DHCP
        self.__pending_queue = []
        # statedict, name -> entry
        self.__state = {}
        # number of pending commands
        self.__pending = 0
        # name -> uuid dict
        self.__uuid_lut = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[DHCP] {}".format(what), log_level)

    def feed_command(self, dhcp_com):
        # inject new DHCPCommand
        self.__raw_input.append(dhcp_com)

    def sync(self):
        if self.__raw_input:
            self.log(
                "input queue has {}".format(
                    logging_tools.get_plural("entry", len(self.__raw_input))
                )
            )
            _input_names = set([_com.name for _com in self.__raw_input])
            _new_names = set(_input_names) - set(self.__state)
            uuid_lut = {
                _com.name: _com.uuid for _com in self.__raw_input if _com.name in _new_names
            }
            if _new_names:
                self.log(
                    "querying DHCP-server for {}{}".format(
                        logging_tools.get_plural("device", len(_new_names)),
                        ": {}".format(", ".join(sorted(list(_new_names)))) if len(_new_names) < 10 else "",
                    )
                )
                self.__uuid_lut.update(uuid_lut)
                self._query_devices(_new_names)
                self.__waiting_queue.extend(
                    [
                        _com for _com in self.__raw_input if _com.name in _new_names
                    ]
                )
                # remove from raw input queue
                self.__raw_input = [
                    _com for _com in self.__raw_input if _com.name not in _new_names
                ]
            if self.__raw_input:
                self._enqueue(self.__raw_input)
                self.__raw_input = []

    def _check_waiting_queue(self):
        _wlen = len(self.__waiting_queue)
        _transfer = [_com for _com in self.__waiting_queue if _com.name in self.__state]
        self.__waiting_queue = [_com for _com in self.__waiting_queue if _com.name not in self.__state]
        self.log(
            "transferred {} from waiting to pending queue".format(
                logging_tools.get_plural("entry", len(_transfer))
            )
        )
        if _transfer:
            self._enqueue(_transfer)

    def _enqueue(self, in_list):
        # max length is 4096, reduce a little
        _MAX_LEN = 3500
        # process commands in in_list
        _actions, _create, _delete = (0, 0, 0)
        _cur_com = self._omshell_base()
        _coms = [_cur_com]
        for _com in in_list:
            if len("\"n".join(_cur_com)) > _MAX_LEN:
                _cur_com = self._omshell_base()
                _coms.append(_cur_com)
            _state = self.__state[_com.name]
            if _state.present:
                if _com.ip:
                    if (_com.ip, _com.mac) == (_state.ip, _state.mac):
                        # no change
                        pass
                    else:
                        # alter
                        _cur_com.extend(
                            self._delete_record(_com)
                        )
                        _cur_com.extend(
                            self._create_record(_com)
                        )
                        _delete += 1
                        _create += 1
                        _actions += 1
                else:
                    # delete
                    _cur_com.extend(
                        self._delete_record(_com)
                    )
                    _delete += 1
                    _actions += 1
            else:
                if _com.ip:
                    _cur_com.extend(
                        self._create_record(_com)
                    )
                    _create += 1
                    _actions += 1
                else:
                    # not present and not to write ignore
                    pass
        if _actions:
            self.log(
                "{} resulted in {} ({}, {}), {}".format(
                    logging_tools.get_plural("input command", len(in_list)),
                    logging_tools.get_plural("action", _actions),
                    logging_tools.get_plural("create record", _create),
                    logging_tools.get_plural("delete record", _delete),
                    logging_tools.get_plural("DHCP batch", len(_coms)),
                )
            )
            for _com in _coms:
                self._do_omshell("write", _com)

    def _create_record(self, dhcp_com):
        om_array = []
        om_array.extend(
            [
                "new host",
                "set name = \"{}\"".format(dhcp_com.name),
                'set hardware-address = {}'.format(dhcp_com.mac),
                'set hardware-type = 1',
                'set ip-address={}'.format(dhcp_com.ip),
            ]
        )
        # the continuation lines are important here
        om_array.extend(
            [
                'set statements = "' +
                'supersede host-name = \\"{}\\" ;'.format(dhcp_com.name) +
                'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { ' +
                "next-server {} ; ".format(dhcp_com.server_ip) +
                'if option arch = 00:06 { ' +
                'filename = \\"etherboot/pxelinux.0\\" ; ' +
                "} else if option arch = 00:07 { " +
                'filename = \\"etherboot/bootx64.efi\\" ; ' +
                "} else { " +
                'filename = \\"etherboot/pxelinux.0\\" ; ' +
                '} ' +
                '}"'
            ]
        )
        om_array.extend(
            [
                "create",
                "",
            ]
        )
        return om_array

    def _delete_record(self, dhcp_com):
        om_array = []
        om_array.extend(
            [
                "new host",
                "set name = \"{}\"".format(dhcp_com.name),
                "open",
                "remove",
                "",
                "new host",
                "set name = \"{}\"".format(dhcp_com.name),
                "open",
                "",
            ]
        )
        return om_array

    def _omshell_base(self):
        return [
            'server 127.0.0.1',
            'port 7911',
            'connect',
        ]

    def _query_devices(self, name_list):
        _MAX_LEN = 3500
        # process commands in in_list
        _cur_com = self._omshell_base()
        _coms = [_cur_com]
        for _dev in name_list:
            if len("\"n".join(_cur_com)) > _MAX_LEN:
                _cur_com.append("")
                _cur_com = self._omshell_base()
                _coms.append(_cur_com)
            _cur_com.extend(
                [
                    "new host",
                    "set name = \"{}\"".format(_dev),
                    "open",
                ]
            )
        _cur_com.append("")
        self.log("query result in {}".format(logging_tools.get_plural("DHCP batch", len(_coms))))
        for _com in _coms:
            self._do_omshell("query", _com)

    def _do_omshell(self, com_name, com_lines):
        if not self.__pending:
            simple_command.process.set_check_freq(200)  # @UndefinedVariable
        self.__pending += 1
        simple_command(
            "echo -e '{}' | /usr/bin/omshell".format(
                "\n".join(com_lines),
            ),
            done_func=self.omshell_done,
            stream_id="mac",
            short_info=True,
            add_info="DHCP {}".format(com_name),
            log_com=self.log,
            # info=om_shell_com
        )

    def omshell_done(self, om_sc):
        cur_out = om_sc.read()
        error_re = re.compile("^.*can't (?P<what>.*) object: (?P<why>.*)$")
        key_value_re = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)$")
        lines = cur_out.split("\n")
        self.log(
            "omshell finished with state {:d} ({}, {})".format(
                om_sc.result,
                logging_tools.get_plural("byte", len(cur_out)),
                logging_tools.get_plural("line", len(lines)),
            )

        )
        # print "xxx", "\n".join(lines)
        self.__pending -= 1
        if not self.__pending:
            simple_command.process.set_check_freq(1000)  # @UndefinedVariable
        cur_dict = {}
        # extra error dict
        _error_dict = {}
        _result_dict = {}
        for line in lines:
            if line.lower().count("connection refused") or line.lower().count("dhcpctl_connect: no more"):
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
            else:
                err_m, key_value_m = (
                    error_re.match(line),
                    key_value_re.match(line),
                )
                if err_m:
                    if cur_dict["name"]:
                        _error_dict[cur_dict["name"]] = err_m.group("why")
                elif key_value_m:
                    _key, _value = (
                        key_value_m.group("key").lower().strip(),
                        key_value_m.group("value").lower().strip(),
                    )
                    if _value[0] in ["'", '"']:
                        _value = _value[1:-1]
                    cur_dict[_key] = _value
                if line.startswith(">"):
                    if "name" in cur_dict:
                        if cur_dict["name"] in _result_dict and cur_dict["name"] in _error_dict:
                            # do not replace because we already have a record with an (important)
                            # error message
                            pass
                        else:
                            _result_dict[cur_dict["name"]] = {
                                _k: _v for _k, _v in cur_dict.iteritems()
                            }
                    cur_dict = {}
        for _key, _dict in _result_dict.iteritems():
            if _key in _error_dict:
                _dict["error"] = _error_dict[_key]
                self.log("device {}: {}".format(_key, _dict["error"]), logging_tools.LOG_LEVEL_ERROR)
            if _key not in self.__state:
                self.__state[_key] = DHCPState(self, _key)
            _dict["uuid"] = self.__uuid_lut[_key]
            self.__state[_key].set_result(_dict)
        self._check_waiting_queue()
