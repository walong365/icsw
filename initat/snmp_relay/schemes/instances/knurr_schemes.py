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
""" knurr schemes for SNMP relayer """

from initat.host_monitoring import limits
from initat.snmp.snmp_struct import snmp_oid

from ..base import SNMPRelayScheme


class temperature_knurr_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "temperature_knurr_scheme", **kwargs)
        self.parser.add_argument(
            "--type",
            type="choice",
            dest="sensor_type",
            choices=["outlet", "inlet"],
            help="temperature probe [%(default)s]",
            default="outlet"
        )
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        sensor_type = self.opts.sensor_type
        lut_id = {
            "outlet": 1,
            "inlet": 2
        }[sensor_type]
        new_dict = self._simplify_keys(
            {key[1]: float(value) / 10. for key, value in self.snmp_dict.values()[0].iteritems() if key[0] == lut_id}
        )
        warn_val, crit_val = (new_dict[5], new_dict[6])
        cur_val = new_dict[3]
        if cur_val > crit_val:
            cur_state = limits.nag_STATE_CRITICAL
        elif cur_val > warn_val:
            cur_state = limits.nag_STATE_WARNING
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "temperature %.2f C | temp=%.2f" % (
            cur_val,
            cur_val
        )


class humidity_knurr_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "humidity_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 1, 7), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(
            {key[0]: float(value) / 10. for key, value in self.snmp_dict.values()[0].iteritems()}
        )
        low_crit, high_crit = (new_dict[3], new_dict[4])
        cur_val = new_dict[2]
        if cur_val > high_crit or cur_val < low_crit:
            cur_state = limits.nag_STATE_CRITICAL
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "humidity %.2f %% [%.2f - %.2f] | humidity=%.2f" % (
            cur_val,
            low_crit,
            high_crit,
            cur_val)


class environment_knurr_base(object):
    def process_return(self):
        new_dict = self._simplify_keys(
            {
                key[0]: int(value) for key, value in self.snmp_dict.values()[0].iteritems()
            }
        )
        del new_dict[4]
        if max(new_dict.values()) == 0:
            cur_state = limits.nag_STATE_OK
        else:
            cur_state = limits.nag_STATE_CRITICAL
        info_dict = {
            1: "fan1",
            2: "fan2",
            3: "fan3",
            5: "water",
            6: "smoke",
            7: "PSA",
            8: "PSB",
        }
        return cur_state, ", ".join(
            [
                "{}: {}".format(
                    info_dict[key],
                    {
                        0: "OK",
                        1: "failed"
                    }[new_dict[key]]
                ) for key in sorted(new_dict.keys())
            ]
        )


class environment_knurr_scheme(SNMPRelayScheme, environment_knurr_base):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "environment_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 2, 4), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])


# new version of Emerson/Knuerr CoolCon rack (APP 1.15.10, HMI 1.15.10)
class environment2_knurr_scheme(SNMPRelayScheme, environment_knurr_base):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "environment2_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 9, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])
