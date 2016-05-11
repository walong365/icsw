# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
Cisco stack handler instance
Not needed now, maybe we remove this later ?
"""

import pprint
from ..base import SNMPHandler
from ...snmp_struct import ResultNode
from ...functions import simplify_dict


STACK_BASE = "1.3.6.1.4.1.9.5.1.9.3.1"


class handler(SNMPHandler):
    class Meta:
        # oids = ["generic.netip"]
        description = "Cisco Stack Information"
        vendor_name = "cisco"
        name = "ciscostack"
        tl_oids = [STACK_BASE]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        pprint.pprint(result_dict)
        _info_dict = simplify_dict(result_dict[STACK_BASE])
        # not needed now
        # pprint.pprint(_info_dict)
        return ResultNode()
