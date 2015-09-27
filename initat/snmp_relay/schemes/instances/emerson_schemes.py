# Copyright (C) 2009-2015 Andreas Lang-Nevyjel
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
""" SNMP schemes for SNMP relayer """

from initat.host_monitoring import limits
from initat.snmp.snmp_struct import snmp_oid

from ..base import SNMPRelayScheme


class current_pdu_emerson_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "current_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 30, 40, 1, 22, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1",
            2: "L2",
            3: "L3",
        }
        return cur_state, ", ".join(
            [
                "%s: %sA" % (info_dict[key], float(new_dict[key]) * 0.01) for key in sorted(info_dict.keys())
            ]
        )


class currentLLG_pdu_emerson_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "currentLLG_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 40, 20, 1, 130, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1-L2",
            2: "L1-L2",
            3: "L2-L3",
            4: "L2-L3",
            5: "L3-L1",
            6: "L3-L1",
        }
        return cur_state, ", ".join(
            [
                "%s: %sA" % (info_dict[key], float(new_dict[key]) * 0.01) for key in sorted(info_dict.keys())
            ]
        )


class voltageLL_pdu_emerson_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "voltageLL_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 30, 40, 1, 61, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1-L2",
            2: "L2-L3",
            3: "L3-L1",
        }
        return cur_state, ", ".join(
            [
                "%s: %sV" % (info_dict[key], float(new_dict[key]) * 0.1) for key in sorted(info_dict.keys())
            ]
        )
