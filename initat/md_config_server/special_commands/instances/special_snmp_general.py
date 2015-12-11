# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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
""" snmp check """

from django.db.models import Q
from initat.snmp.sink import SNMPSink
from initat.md_config_server.special_commands.base import SpecialBase


class special_snmp_general(SpecialBase):
    class Meta:
        info = "all configured SNMP checks"
        description = "Enable all checks related to found SNMP schemes"
        meta = True

    def _call(self, instance=None):
        if not instance:
            _retf = []
            for _scheme in self.host.snmp_schemes.filter(Q(mon_check=True)):
                _handler = self.build_cache.snmp_sink.get_handler(_scheme)
                if _handler:
                    _retf.extend([_com.Meta.name for _com in _handler.config_mon_check()])
            return _retf
        else:
            return self.build_cache.snmp_sink.get_handler_from_mon(instance).config_call(self)

    def get_commands(self):
        snmp_sink = SNMPSink(self.log)
        return sum(
            [
                _handler.config_mon_check() for _handler in snmp_sink.handlers if _handler.Meta.mon_check
            ],
            []
        )
