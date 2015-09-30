# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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

dynamic config process for md-config-server
dynamically creates config entries for devices (for devices queried via IPMI or SNMP)

"""

import bz2
import time
import base64
import json

from django.db import connection
from django.db.models import Q

from initat.cluster.backbone.models import device, monitoring_hint, mon_check_command_special, \
    mon_check_command
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.host_monitoring import limits
from initat.md_config_server.config import global_config
from initat.tools import logging_tools, server_command, process_tools, threading_tools


class DynConfigProcess(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self.register_func("monitoring_info", self._monitoring_info)
        self.register_func("passive_check_result", self._pcr)
        self.register_func("passive_check_results_as_chunk", self._pcrs_as_chunk)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _pcr(self, *args, **kwargs):
        in_com = server_command.srv_command(source=args[0])
        _device_name = in_com["*device"]
        _check_name = in_com["*check"]
        _dev = device.get_device(_device_name)
        if _dev:
            try:
                _check = mon_check_command.objects.get(Q(name=_check_name))
            except:
                self.log("no valid mon_check_command with name '{}' found".format(_check_name), logging_tools.LOG_LEVEL_ERROR)
            else:
                if _check.is_active:
                    self.log("mon_check_command {} is active".format(unicode(_check)), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _check.check_command_pk = _check.pk
                    _check.mccs_id = None
                    # print _check, _dev
                    _ocsp_prefix = host_service_id_util.create_host_service_description(_dev.pk, _check, "")
                    ocsp_line = "[{:d}] PROCESS_SERVICE_CHECK_RESULT;{};{};{:d};{}".format(
                        int(time.time()),
                        _dev.full_name,
                        "{}{}".format(_ocsp_prefix, _check.description),
                        {
                            "OK": 0,
                            "WARN": 1,
                            "CRITICAL": 2
                        }.get(in_com["*state"], 2),
                        in_com["*output"],
                    )
                    self.log("translated passive_check_result to '{}'".format(ocsp_line))
                    self.send_pool_message("ocsp_results", [ocsp_line])
        else:
            self.log("no valid device with name '{}' found".format(_device_name), logging_tools.LOG_LEVEL_ERROR)

    def _pcrs_as_chunk(self, *args, **kwargs):
        in_com = server_command.srv_command(source=args[0])
        _chunk = json.loads(bz2.decompress(base64.b64decode(in_com["*ascii_chunk"])))
        _source = _chunk.get("source", "unknown")
        _prefix = _chunk["prefix"]
        try:
            cur_dev = device.objects.get(Q(pk=_prefix.split(":")[1]))
        except:
            self.log(
                "error getting device from prefix '{}' (source {}): {}".format(
                    _prefix,
                    _source,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            ocsp_lines = []
            for _line in _chunk["list"]:
                if len(_line) != 3:
                    self.log(
                        "pcr line has wrong format (len {:d} != 3): '{}'".format(
                            len(_line),
                            unicode(_line),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    _info, _ret_state, _result = _line
                    try:
                        _srv_info = "{}{}".format(_prefix, _info)
                        ocsp_line = "[{:d}] PROCESS_SERVICE_CHECK_RESULT;{};{};{:d};{}".format(
                            int(time.time()),
                            cur_dev.full_name,
                            _srv_info,
                            _ret_state,
                            _result,
                        )
                    except:
                        self.log(
                            "error generating ocsp_result from '{}': {}".format(
                                unicode(_line),
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        ocsp_lines.append(ocsp_line)
            if ocsp_lines:
                self.send_pool_message("ocsp_results", ocsp_lines)
            self.log(
                "generated {} (source: {})".format(
                    logging_tools.get_plural("passive check result", len(ocsp_lines)),
                    _source,
                )
            )

    def _monitoring_info(self, *args, **kwargs):
        in_com = server_command.srv_command(source=args[0])
        mon_info = in_com.xpath(".//monitor_info")
        if len(mon_info):
            mon_info = mon_info[0]
            try:
                cur_dev = device.objects.get(Q(uuid=mon_info.get("uuid")))
            except device.DoesNotExist:
                self.log("no device with uuid {} found".format(mon_info.get("uuid")), logging_tools.LOG_LEVEL_ERROR)
            else:
                self._create_hints(cur_dev, mon_info)
        else:
            self.log("no monitor_info found", logging_tools.LOG_LEVEL_ERROR)

    def _create_hints(self, cur_dev, mon_info):
        self._create_hints_ipmi(cur_dev, mon_info)

    def _get_ipmi_service_prefix(self, cur_dev):
        _prefix = None
        # better cache this info ?
        # special check command
        try:
            _mcs = mon_check_command_special.objects.get(
                Q(identifier="ipmi_passive_checks")
            )
        except mon_check_command_special.DoesNotExist:
            pass
        else:
            # mon command for current device
            try:
                _mc = mon_check_command.objects.get(
                    Q(config__device_config__device=cur_dev) &
                    Q(mon_check_command_special=_mcs)
                )
            except mon_check_command.DoesNotExist:
                try:
                    _mc = mon_check_command.objects.get(
                        Q(config__device_config__device=cur_dev.device_group.device_id) &
                        Q(mon_check_command_special=_mcs)
                    )
                except mon_check_command.DoesNotExist:
                    # mon check command not found
                    self.log(
                        "no mcc for mccs {} / device [or device_group] {} found".format(
                            unicode(_mcs),
                            unicode(cur_dev),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    _mc.check_command_pk = _mc.pk
                    _mc.mccs_id = _mcs.pk
                    _prefix = host_service_id_util.create_host_service_description(cur_dev.pk, _mc, "")
            except mon_check_command.MultipleObjectsReturned:
                # more than one check command found
                self.log(
                    "more than one mcc for mccs {} / device {} found".format(
                        unicode(_mcs),
                        unicode(cur_dev),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                _mc.check_command_pk = _mc.pk
                _mc.mccs_id = _mcs.pk
                _prefix = host_service_id_util.create_host_service_description(cur_dev.pk, _mc, "")
        return _prefix

    def _create_hints_ipmi(self, cur_dev, mon_info):
        cur_hints = {(cur_h.m_type, cur_h.key): cur_h for cur_h in monitoring_hint.objects.filter(Q(device=cur_dev))}
        _ocsp_prefix = self._get_ipmi_service_prefix(cur_dev)
        if not _ocsp_prefix:
            self.log("cannot get prefix for IPMI service results for device {}".format(unicode(cur_dev)))
        ocsp_lines = []
        # pprint.pprint(cur_hints)
        n_updated, n_created, n_deleted = (0, 0, 0)
        updated, created = (False, False)
        _used_types, _present_keys = (set(), set())
        for _val in mon_info:
            _key = (_val.get("m_type"), _val.get("name"))
            _present_keys.add(_key)
            _used_types.add(_val.get("m_type"))
            updated, created = (False, False)
            if _key in cur_hints:
                cur_hint = cur_hints[_key]
                # update
                for _sfn, _dfn in [("info", "info"), ("v_type", "v_type")]:
                    if _val.get(_sfn) != getattr(cur_hint, _dfn):
                        setattr(cur_hint, _dfn, _val.get(_sfn))
                        updated = True
            else:
                cur_hint = monitoring_hint(
                    device=cur_dev,
                    m_type=_val.get("m_type"),
                    v_type=_val.get("v_type"),
                    key=_val.get("name"),
                    info=_val.get("info"),
                )
                created = True
            limit_dict = {
                "{}_{}".format(
                    {
                        "l": "lower",
                        "u": "upper"
                    }[_key[0]], {
                        "w": "warn",
                        "c": "crit"
                    }[_key[1]]
                ): float(_val.attrib[_key]) for _key in ["lc", "uc", "lw", "uw"] if _key in _val.attrib
            }
            _value = _val.get("value")
            if _val.get("v_type") == "f":
                _value = float(_val.get("value"))
            else:
                _value = int(_val.get("value"))
            if cur_hint.update_limits(_value, limit_dict):
                updated = True
            if created or updated:
                if created:
                    n_created += 1
                if updated:
                    n_updated += 1
                cur_hint.save()
            # create passive check result
            cur_hint.set_value(_value)
            ret_code, ret_str = self._check_status_ipmi(_value, cur_hint)
            ocsp_line = "[{}] PROCESS_SERVICE_CHECK_RESULT;{};{};{:d};{}".format(
                mon_info.get("time"),
                cur_dev.full_name,
                "{}{}".format(_ocsp_prefix, _val.get("info")),
                ret_code,
                ret_str,
            )
            ocsp_lines.append(ocsp_line)
        # experimental: delete all hints with correct m_type
        if len(mon_info) and _used_types:
            _del_keys = [key for key, value in cur_hints.iteritems() if key not in _present_keys and key[0] in _used_types and not value.persistent]
            if _del_keys:
                self.log(
                    "{} / {}: {} to delete".format(
                        unicode(cur_dev),
                        ", ".join(sorted(list(_used_types))),
                        logging_tools.get_plural("key", len(_del_keys))
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                for _key in _del_keys:
                    cur_hints[_key].delete()
        # pprint.pprint(ocsp_lines)
        if _ocsp_prefix:
            self.send_pool_message("ocsp_results", ocsp_lines)
        if updated or created:
            self.log("for {}: created {:d}, updated {:d}".format(unicode(cur_dev), n_created, n_updated))

    def _check_status_ipmi(self, _val, cur_hint):
        _ret = limits.nag_STATE_OK
        if type(_val) in [int, long]:
            form_str = "{:d}"
        else:
            form_str = "{:.2f}"
        _val_str = form_str.format(_val)
        _errors = []
        for s_key, c_val in cur_hint.get_limit_list():
            if s_key[1] == "w":
                _sn, _retc = (1, limits.nag_STATE_WARNING)
            else:
                _sn, _retc = (2, limits.nag_STATE_CRITICAL)
            _lower = s_key[0] == "l"
            if (_lower and _val <= c_val) or (not _lower and _val >= c_val):
                _ret = max(_ret, _retc)
                _errors.append(
                    "{} {} threshold {}".format(
                        "below lower" if _lower else "above upper",
                        {"w": "warning", "c": "critical"}[s_key[1]],
                        form_str.format(c_val),
                    )
                )
            if _lower:
                _val_str = "{}{} {}".format(form_str.format(c_val), "<" * _sn, _val_str)
            else:
                _val_str = "{} {}{}".format(_val_str, "<" * _sn, form_str.format(c_val))
        if _errors:
            _val_str = "{}, value is {}".format(
                _val_str,
                ", ".join(_errors),
            )
        # print _val_str
        return _ret, _val_str
