# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
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
from initat.md_config_server.config import global_config
from initat.host_monitoring import limits
import logging_tools
import server_command
import threading_tools
import pprint
from lxml import etree # @UnresolvedImport

class dynconfig_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        connection.close()
        self.register_func("monitoring_info", self._monitoring_info)
        # feed as test
        self._monitoring_info('<ns0:ics_batch xmlns:ns0="http://www.initat.org/lxml/ns" srvc_version="1"><ns0:source host="eddie" pid="19855"/><ns0:command>monitoring_info</ns0:command><ns0:identity>not set</ns0:identity><ns0:mon_info><monitor_info uuid="ee567638-581b-4154-9734-0e437db12ba0" name="kvm01-ipmi" time="1402922591"><value info="rotation of fan Fan 4B Tach" v_type="f" lc="468.000" m_type="ipmi" value="4140.000000" base="1000" unit="RPM" name="ipmi.fan.fan_4b_tach"/><value info="Power usage of Avg Power" v_type="f" name="ipmi.watts.avg_power" m_type="ipmi" value="190.000000" base="1" unit="W"/><value info="Voltage of Planar VBAT" v_type="f" lc="2.095" m_type="ipmi" value="3.226000" lw="2.248" base="1" unit="V" name="ipmi.volts.planar_vbat"/><value info="Temperature of Ambient Temp" v_type="f" name="ipmi.temp.ambient_temp" m_type="ipmi" uw="38.000" value="20.000000" un="45.000" uc="41.000" base="1" unit="C"/><value info="rotation of fan Fan 1B Tach" v_type="f" lc="468.000" m_type="ipmi" value="4176.000000" base="1000" unit="RPM" name="ipmi.fan.fan_1b_tach"/><value info="rotation of fan Fan 1A Tach" v_type="f" lc="492.000" m_type="ipmi" value="4018.000000" base="1000" unit="RPM" name="ipmi.fan.fan_1a_tach"/><value info="Voltage of Planar 3.3V" v_type="f" lc="3.039" m_type="ipmi" value="3.351000" base="1" uc="3.564" unit="V" name="ipmi.volts.planar_3,3v"/><value info="Voltage of Planar 5V" v_type="f" lc="4.475" m_type="ipmi" value="5.108000" base="1" uc="5.582" unit="V" name="ipmi.volts.planar_5v"/><value info="rotation of fan Fan 2A Tach" v_type="f" lc="492.000" m_type="ipmi" value="4018.000000" base="1000" unit="RPM" name="ipmi.fan.fan_2a_tach"/><value info="rotation of fan Fan 3A Tach" v_type="f" lc="492.000" m_type="ipmi" value="3977.000000" base="1000" unit="RPM" name="ipmi.fan.fan_3a_tach"/><value info="rotation of fan Fan 4A Tach" v_type="f" lc="492.000" m_type="ipmi" value="4018.000000" base="1000" unit="RPM" name="ipmi.fan.fan_4a_tach"/><value info="rotation of fan Fan 3B Tach" v_type="f" lc="468.000" m_type="ipmi" value="4176.000000" base="1000" unit="RPM" name="ipmi.fan.fan_3b_tach"/><value info="Voltage of Planar 12V" v_type="f" lc="10.692" m_type="ipmi" value="12.204000" base="1" uc="13.446" unit="V" name="ipmi.volts.planar_12v"/><value info="rotation of fan Fan 2B Tach" v_type="f" lc="468.000" m_type="ipmi" value="4176.000000" base="1000" unit="RPM" name="ipmi.fan.fan_2b_tach"/></monitor_info></ns0:mon_info></ns0:ics_batch>')
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
        cur_hints = {(cur_h.m_type, cur_h.key) : cur_h for cur_h in monitoring_hint.objects.filter(Q(device=cur_dev))}
        ocsp_lines = []
        # pprint.pprint(cur_hints)
        updated, created = (0, 0)
        for _val in mon_info:
            _key = (_val.get("m_type"), _val.get("name"))
            changed = False
            if _key in cur_hints:
                cur_hint = cur_hints[_key]
                # update
                for _sfn, _dfn in [("info", "info"), ]:
                    if _val.get(_sfn) != getattr(cur_hint, _dfn):
                        setattr(cur_hint, _dfn, _val.get(_sfn))
                        changed = True
                if changed:
                    updated += 1
            else:
                cur_hint = monitoring_hint(
                    device=cur_dev,
                    m_type=_val.get("m_type"),
                    key=_val.get("name"),
                    info=_val.get("info"),
                )
                changed = True
                created += 1
            if changed:
                cur_hint.save()
            # create passive check result
            ret_code, ret_str = self._check_status_ipmi(_val, cur_hint)
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
            self.log("for {}: created {:d}, updated {:d}".format(unicode(cur_dev), created, updated))
    def _check_status_ipmi(self, _xml, cur_hint):
        _ret = limits.nag_STATE_OK
        _val_str = _xml.get("value")
        if _xml.get("v_type") in ["f", "i"]:
            _is_int = _xml.get("v_type") == "i"
            if _is_int:
                _val = int(float(_val_str))
            else:
                _val = float(_val_str)
            if _is_int:
                _val_str = "{:d}".format(_val)
            else:
                _val_str = "{:.2f}".format(_val)
            for _ck, _rv, _ul, _add_str in [
                ("lw", limits.nag_STATE_WARNING, False, "["),
                ("uw", limits.nag_STATE_WARNING, True, "]"),
                ("lc", limits.nag_STATE_CRITICAL, False, "["),
                ("uc", limits.nag_STATE_CRITICAL, True, "]"),
                ]:
                if _ck in _xml.attrib:
                    _cval = float(_xml.get(_ck))
                    if _ul:
                        _val_str = "{} {:.2f}({}){}".format(_val_str, _cval, _ck[1], _add_str)
                    else:
                        _val_str = "{}{:.2f}({}) {}".format(_add_str, _cval, _ck[1], _val_str)
                    if (_ul and _val > _cval) or (not _ul and _val < _cval):
                        _ret = max(_ret, _rv)
        # print _val_str
        return _ret, _val_str

