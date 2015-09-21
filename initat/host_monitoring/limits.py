# Copyright (C) 2001-2008,2010-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

from initat.tools import logging_tools

# nagios / icinga exit codes
nag_STATE_CRITICAL = 2
nag_STATE_WARNING = 1
nag_STATE_OK = 0
nag_STATE_UNKNOWN = -1
nag_STATE_DEPENDENT = -2


def get_state_str(in_state):
    return {
        nag_STATE_CRITICAL: "Critical",
        nag_STATE_WARNING: "Warning",
        nag_STATE_OK: "OK",
        nag_STATE_UNKNOWN: "Unknown",
        nag_STATE_DEPENDENT: "Dependent"
    }.get(in_state, "state {:d} not known".format(in_state))


def nag_state_to_log_level(in_state):
    return {
        nag_STATE_CRITICAL: logging_tools.LOG_LEVEL_CRITICAL,
        nag_STATE_WARNING: logging_tools.LOG_LEVEL_WARN,
        nag_STATE_OK: logging_tools.LOG_LEVEL_OK,
        nag_STATE_UNKNOWN: logging_tools.LOG_LEVEL_ERROR,
        nag_STATE_DEPENDENT: logging_tools.LOG_LEVEL_WARN
    }.get(in_state, logging_tools.LOG_LEVEL_ERROR)


def check_ceiling(value, warn, crit):
    if crit is not None and value >= crit:
        return nag_STATE_CRITICAL
    elif warn is not None and value >= warn:
        return nag_STATE_WARNING
    else:
        return nag_STATE_OK


def check_floor(value, warn, crit):
    if crit is not None and value <= crit:
        return nag_STATE_CRITICAL
    elif warn is not None and value <= warn:
        return nag_STATE_WARNING
    else:
        return nag_STATE_OK


class range_parameter(object):
    __slots__ = ["name", "lower_boundary", "upper_boundary"]

    def __init__(self, name):
        self.name = name
        self.set_lower_boundary()
        self.set_upper_boundary()

    def set_lower_boundary(self, lower=0):
        if lower is None:
            self.lower_boundary = lower
        else:
            self.lower_boundary = int(lower)

    def set_upper_boundary(self, upper=0):
        if upper is None:
            self.upper_boundary = upper
        else:
            self.upper_boundary = int(upper)

    def has_boundaries_set(self):
        return self.upper_boundary or self.lower_boundary

    def get_lower_boundary(self):
        return self.lower_boundary

    def get_upper_boundary(self):
        return self.upper_boundary

    def in_boundaries(self, value):
        b_ok = True
        if self.has_boundaries_set():
            if self.lower_boundary and value < self.lower_boundary:
                b_ok = False
            if self.upper_boundary and value > self.upper_boundary:
                b_ok = False
        return b_ok


class limits(object):
    __slots__ = ["warn_val", "crit_val", "warn_val_f", "crit_val_f", "add_flags", "add_vars"]

    def __init__(self, warn_val=None, crit_val=None, add_flags=None):
        self.warn_val, self.warn_val_f = (None, None)
        self.crit_val, self.crit_val_f = (None, None)
        self.add_flags, self.add_vars = ([], {})
        if warn_val is not None:
            self.set_warn_val(warn_val)
        if crit_val is not None:
            self.set_crit_val(crit_val)
        if add_flags is not None:
            self.set_add_flags(add_flags)

    def set_warn_val(self, val):
        try:
            self.warn_val_f = float(val)
            self.warn_val = int(self.warn_val_f)
        except:
            self.warn_val, self.warn_val_f = (None, None)
            retc = 0
        else:
            retc = 1
        return retc

    def set_crit_val(self, val):
        try:
            self.crit_val_f = float(val)
            self.crit_val = int(self.crit_val_f)
        except:
            self.crit_val, self.crit_val_f = (None, None)
            retc = 0
        else:
            retc = 1
        return retc

    def set_add_var(self, name, value):
        self.add_vars[name] = value
        return 1

    def get_add_var(self, name, default=0):
        return self.add_vars.get(name, default)

    def has_add_var(self, name):
        return name in self.add_vars

    def set_add_flags(self, flags):
        retc = 1
        for flag in flags:
            try:
                self.add_flags.append(flag)
            except:
                retc = 0
        return retc

    def get_add_flag(self, what):
        return what in self.add_flags

    def get_string(self):
        out_f = []
        if self.warn_val:
            out_f.append("warn={:d}".format(self.warn_val))
        if self.crit_val:
            out_f.append("crit={:d}".format(self.crit_val))
        for flag in self.add_flags:
            out_f.append(flag)
        return out_f and ",".join(out_f) or "-"

    def check_ceiling(self, val):
        # interpret values as upper limits (for example temperatures)
        ret_code, state = (nag_STATE_OK, "OK")
        if type(val) == float:
            if self.crit_val_f is not None:
                if val >= self.crit_val_f:
                    ret_code, state = (nag_STATE_CRITICAL, "Critical")
            if (self.warn_val_f is not None) and ret_code == nag_STATE_OK:
                if val >= self.warn_val_f:
                    ret_code, state = (nag_STATE_WARNING, "Warning")
        elif type(val) in [int, long]:
            if self.crit_val is not None:
                if val >= self.crit_val:
                    ret_code, state = (nag_STATE_CRITICAL, "Critical")
            if (self.warn_val is not None) and ret_code == nag_STATE_OK:
                if val >= self.warn_val:
                    ret_code, state = (nag_STATE_WARNING, "Warning")
        else:
            ret_code, state = (nag_STATE_CRITICAL, "TypeError")
        return ret_code, state

    def check_floor(self, val):
        # interpret values as lower limits (for example RPMs for fans)
        ret_code, state = (nag_STATE_OK, "OK")
        if type(val) == float:
            if self.crit_val_f is not None:
                if val <= self.crit_val_f:
                    ret_code, state = (nag_STATE_CRITICAL, "Critical")
            if (self.warn_val_f is not None) and ret_code == nag_STATE_OK:
                if val <= self.warn_val_f:
                    ret_code, state = (nag_STATE_WARNING, "Warning")
        elif type(val) in [int, long]:
            if self.crit_val is not None:
                if val <= self.crit_val:
                    ret_code, state = (nag_STATE_CRITICAL, "Critical")
            if (self.warn_val is not None) and ret_code == nag_STATE_OK:
                if val <= self.warn_val:
                    ret_code, state = (nag_STATE_WARNING, "Warning")
        else:
            ret_code, state = (nag_STATE_CRITICAL, "TypeError")
        return ret_code, state
