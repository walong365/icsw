# Copyright (C) 2009-2016 Andreas Lang-Nevyjel
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
""" SNMP general schemes for SNMP relayer """

from .base import SNMPRelayScheme


class SNMPGeneralScheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        self.handler = kwargs.pop("handler")
        SNMPRelayScheme.__init__(self, self.handler.Meta.name, **kwargs)
        self.handler.parser_setup(self.parser)
        self.parse_options(kwargs["options"])
        if not self.get_errors():
            self.requests = self.handler.mon_start(self)

    def process_return(self):
        return self.handler.mon_result(self)
