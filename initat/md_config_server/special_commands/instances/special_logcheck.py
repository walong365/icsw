# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" special calls for logcheck-server related commands """

from initat.cluster.backbone.models import SpecialGroupsEnum, SyslogCheck
from initat.md_config_server.special_commands.base import SpecialBase
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.tools import logging_tools


class special_syslog_rate(SpecialBase):
    class Meta:
        server_contact = False
        info = "Syslog rate"
        group = SpecialGroupsEnum.system
        command_line = "$USER2$ -m $ARG1$ -p $ARG2$ syslog_rate_mon -w ${ARG3:DEVICE_SYSLOG_RATE_WARNING:1} " \
            "-c ${ARG4:DEVICE_SYSLOG_RATE_CRITICAL:2.0} --pk $ARG5$"
        description = "return the current syslog rate of the given device"

    def _call(self):
        sc_array = []
        SRV_TYPE = "logcheck-server"
        _router = self.build_cache.router
        if SRV_TYPE in _router:
            warn_value = float(self.host.dev_variables.get("DEVICE_SYSLOG_RATE_WARNING", "1.0"))
            crit_value = float(self.host.dev_variables.get("DEVICE_SYSLOG_RATE_CRITICAL", "2.0"))
            _srv_address = _router.get_server_address(SRV_TYPE)
            sc_array.append(
                self.get_arg_template(
                    "syslog rate",
                    arg1=_srv_address,
                    arg2=self.build_cache.instance_xml.get_port_dict(SRV_TYPE, ptype="command"),
                    arg3="{:.3f}".format(warn_value),
                    arg4="{:.3f}".format(crit_value),
                    arg5=self.host.pk,
                )
            )
        else:
            self.log("server_type {} not defined in routing".format(SRV_TYPE), logging_tools.LOG_LEVEL_ERROR)
        return sc_array


class special_syslog_general(SpecialBase):
    class Meta:
        info = "all configured Syslog checks"
        description = "Enable all syslog checks"
        command_line = "$USER2$ -m $ARG1$ -p $ARG2$ syslog_check_mon " \
            "--pk $ARG3$ --key $ARG4$ --checks $ARG5$"

    def _call(self, instance=None):
        _checks = SyslogCheck.all_enabled.all()
        sc_array = []
        SRV_TYPE = "logcheck-server"
        _router = self.build_cache.router
        if SRV_TYPE in _router:
            warn_value = float(self.host.dev_variables.get("DEVICE_SYSLOG_RATE_WARNING", "1.0"))
            crit_value = float(self.host.dev_variables.get("DEVICE_SYSLOG_RATE_CRITICAL", "2.0"))
            _srv_address = _router.get_server_address(SRV_TYPE)
            _srv_port = self.build_cache.instance_xml.get_port_dict(SRV_TYPE, ptype="command")
            _passive_check_prefix = host_service_id_util.create_host_service_description(self.host.pk, self.parent_check, "")
            check_sig = ",".join(["{:d}".format(_check.pk) for _check in _checks])
            sc_array.append(
                self.get_arg_template(
                    "syslog checks ({:d})".format(len(_checks)),
                    arg1=_srv_address,
                    arg2=_srv_port,
                    arg3=self.host.pk,
                    arg4=_passive_check_prefix,
                    arg5=check_sig,
                )
            )
            for _check in _checks:
                sc_array.append(
                    self.get_arg_template(
                        "syslog check {}".format(_check.name),
                        arg1=_srv_address,
                        arg2=_srv_port,
                        arg3=self.host.pk,
                        arg4=_passive_check_prefix,
                        arg5=check_sig,
                        check_active=False,
                    )
                )
        else:
            self.log("server_type {} not defined in routing".format(SRV_TYPE), logging_tools.LOG_LEVEL_ERROR)
        return sc_array
