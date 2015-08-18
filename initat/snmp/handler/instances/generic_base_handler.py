# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
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
""" SNMP handler instances """

from ...functions import simplify_dict
from ...snmp_struct import ResultNode
from ..base import SNMPHandler
try:
    from initat.cluster.backbone.models import DeviceSNMPInfo
except:
    pass


class handler(SNMPHandler):
    class Meta:
        # oids = ["generic.base"]
        description = "basic SNMP info"
        vendor_name = "generic"
        name = "base"
        tl_oids = ["1.3.6.1.2.1.1"]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        try:
            _cur_info = dev.DeviceSNMPInfo
        except DeviceSNMPInfo.DoesNotExist:
            _cur_info = DeviceSNMPInfo(device=dev)
        _dict = simplify_dict(result_dict[list(oid_list)[0]], ())
        for _idx, attr, default in [
            (1, "description", "???"),
            (4, "contact", "???"),
            (5, "name", "???"),
            (6, "location", "???"),
            (8, "services", 0),
        ]:
            setattr(_cur_info, attr, _dict[0].get(_idx, default))
        _cur_info.save()
        return ResultNode(ok="set Infos")
