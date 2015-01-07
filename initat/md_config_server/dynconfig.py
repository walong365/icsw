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

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, monitoring_hint
from initat.host_monitoring import limits
from initat.md_config_server.config import global_config
from lxml import etree  # @UnresolvedImport @UnusedImport
import logging_tools
import pprint  # @UnusedImport
import server_command
import threading_tools


class dynconfig_process(threading_tools.process_obj):
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

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

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

    def _create_hints_ipmi(self, cur_dev, mon_info):
        cur_hints = {(cur_h.m_type, cur_h.key): cur_h for cur_h in monitoring_hint.objects.filter(Q(device=cur_dev))}
        ocsp_lines = []
        # pprint.pprint(cur_hints)
        n_updated, n_created = (0, 0)
        updated, created = (False, False)
        for _val in mon_info:
            _key = (_val.get("m_type"), _val.get("name"))
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
            limit_dict = {"{}_{}".format(
                {
                    "l": "lower",
                    "u": "upper"
                }[_key[0]], {
                    "w": "warn",
                    "c": "crit"
                }[_key[1]]): float(_val.attrib[_key]) for _key in ["lc", "uc", "lw", "uw"] if _key in _val.attrib
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
                _val.get("info"),
                ret_code,
                ret_str,
            )
            ocsp_lines.append(ocsp_line)
        # pprint.pprint(ocsp_lines)
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
        for s_key, c_val in cur_hint.get_limit_list():
            if s_key[1] == "w":
                _sn, _retc = (1, limits.nag_STATE_WARNING)
            else:
                _sn, _retc = (2, limits.nag_STATE_CRITICAL)
            if (s_key[0] == "l" and _val <= c_val) or (s_key[0] == "u" and _val >= c_val):
                _ret = max(_ret, _retc)
            if s_key[0] == "u":
                _val_str = "{} {}{}{}".format(_val_str, "<" * _sn, form_str.format(c_val), ">" * _sn)
            else:
                _val_str = "{}{}{} {}".format("<" * _sn, form_str.format(c_val), ">" * _sn, _val_str)
        # print _val_str
        return _ret, _val_str
