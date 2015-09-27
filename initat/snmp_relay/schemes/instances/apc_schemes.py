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
from initat.tools import logging_tools

from ..base import SNMPRelayScheme


class apc_rpdu_load_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "apc_rpdu_load", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.4.1.318.1.1.12.2.3.1.1")

    def process_return(self):
        simple_dict = self._simplify_keys(self.snmp_dict.values()[0])
        p_idx = 1
        act_load = simple_dict[(2, p_idx)]
        act_state = simple_dict[(3, p_idx)]
        ret_state = {
            1: limits.nag_STATE_OK,
            2: limits.nag_STATE_OK,
            3: limits.nag_STATE_WARNING,
            4: limits.nag_STATE_CRITICAL
        }[act_state]
        return ret_state, "load is %.2f Ampere" % (float(act_load) / 10.)


class usv_apc_load_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "usv_apc_load", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2), cache=True)

    def process_return(self):
        WARN_LOAD, CRIT_LOAD = (70, 85)
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        try:
            act_load = use_dict[(3, 0)]
        except KeyError:
            return limits.nag_STATE_CRITICAL, "error getting load"
        else:
            ret_state, prob_f = (limits.nag_STATE_OK, [])
            if act_load > CRIT_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                prob_f.append("load is very high (> %d)" % (CRIT_LOAD))
            elif act_load > WARN_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
                prob_f.append("load is high (> %d)" % (WARN_LOAD))
            return ret_state, "load is %d %%%s" % (
                act_load,
                ": %s" % ("; ".join(prob_f)) if prob_f else "")


class usv_apc_output_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "usv_apc_output", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2), cache=True)

    def process_return(self):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (219, 235)
        out_dict = self._simplify_keys(self.snmp_dict.values()[0])
        out_freq, out_voltage = (
            out_dict[(2, 0)],
            out_dict[(1, 0)]
        )
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if out_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output frequency not ok [%d, %d]" % (
                MIN_HZ,
                MAX_HZ))
        if out_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output voltage is not in range [%d, %d]" % (
                MIN_VOLT,
                MAX_VOLT))
        return ret_state, "output is %d V at %d Hz%s" % (
            out_voltage,
            out_freq,
            ": %s" % ("; ".join(prob_f)) if prob_f else ""
        )


class usv_apc_input_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "usv_apc_input", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 3, 2), cache=True)

    def process_return(self):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (216, 235)
        in_dict = self._simplify_keys(self.snmp_dict.values()[0])
        in_freq, in_voltage = (int(in_dict[(4, 0)]),
                               int(in_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if in_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input frequency not ok [%d, %d]" % (
                MIN_HZ,
                MAX_HZ))
        if in_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input voltage is not in range [%d, %d]" % (
                MIN_VOLT,
                MAX_VOLT))
        return ret_state, "input is %d V at %d Hz%s" % (
            in_voltage,
            in_freq,
            ": %s" % ("; ".join(prob_f)) if prob_f else ""
        )


class usv_apc_battery_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "usv_apc_battery", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 2, 2), cache=True)
        self.parser.add_argument("-w", type=float, dest="warn", help="warning value [%(default)s]", default=35.0)
        self.parser.add_argument("-c", type=float, dest="crit", help="critical value [%(default)s]", default=40.0)
        self.parse_options(kwargs["options"])

    def process_return(self):
        warn_temp = int(self.opts.warn)
        crit_temp = int(self.opts.crit)
        warn_bat_load, crit_bat_load = (90, 50)
        bat_dict = self._simplify_keys(self.snmp_dict.values()[0])
        need_replacement, run_time, act_temp, act_bat_load = (
            int(bat_dict[(4, 0)]),
            int(bat_dict[(3, 0)]),
            int(bat_dict[(2, 0)]),
            int(bat_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if need_replacement > 1:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("battery needs replacing")
        if act_temp > crit_temp:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("temperature is very high (th %d)" % (crit_temp))
        elif act_temp > warn_temp:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("temperature is high (th %d)" % (warn_temp))
        if act_bat_load < crit_bat_load:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("very low load (th %d)" % (crit_bat_load))
        elif act_bat_load < warn_bat_load:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("not fully loaded (th %d)" % (warn_bat_load))
        # run time in seconds
        run_time = run_time / 100.
        if run_time < 5 * 60:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("run time below 5 minutes")
        elif run_time < 10 * 60:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("run time below 10 minutes")
        return ret_state, "bat temperature is %d C, bat load is %d %%, support time is %s %s%s" % (
            act_temp,
            act_bat_load,
            logging_tools.get_plural("min", int(run_time / 60)),
            logging_tools.get_plural("sec", int(run_time % 60)),
            ": %s" % ("; ".join(prob_f)) if prob_f else ""
        )
