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
""" eonstor schemes for SNMP relayer """

from initat.host_monitoring import limits
from initat.snmp.snmp_struct import snmp_oid
from initat.tools import logging_tools, process_tools

from ..base import SNMPRelayScheme



# timeout of Eonstor
EONSTOR_TIMEOUT = 5 * 60


class eonstor_object(object):
    def __init__(self, type_str, in_dict, **kwargs):
        # print time.ctime(), "new eonstor_object"
        self.type_str = type_str
        self.name = in_dict[8]
        self.state = int(in_dict[kwargs.get("state_key", 13)])
        # default values
        self.nag_state, self.state_strs = (limits.nag_STATE_OK, [])
        self.out_string = ""
        self.long_string = ""

    def __del__(self):
        # print time.ctime(), "del eonstor_object"
        pass

    def set_error(self, err_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_CRITICAL)
        self.state_strs.append(err_str)

    def set_warn(self, warn_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_WARNING)
        self.state_strs.append(warn_str)

    def get_state_str(self):
        return ", ".join(self.state_strs) or "ok"

    def get_ret_str(self, **kwargs):
        out_str = self.long_string if (self.long_string and kwargs.get("long_format", False)) else self.out_string
        if self.nag_state == limits.nag_STATE_OK and out_str:
            return "%s: %s" % (
                self.name,
                out_str,
            )
        elif self.nag_state:
            return "%s: %s%s" % (
                self.name,
                self.get_state_str(),
                " (%s)" % (out_str) if out_str else "",
            )
        else:
            return ""


class eonstor_disc(eonstor_object):
    lu_dict = {
        0: ("New Drive", limits.nag_STATE_OK),
        1: ("On-Line Drive", limits.nag_STATE_OK),
        2: ("Used Drive", limits.nag_STATE_OK),
        3: ("Spare Drive", limits.nag_STATE_OK),
        4: ("Drive Initialization in Progress", limits.nag_STATE_WARNING),
        5: ("Drive Rebuild in Progress", limits.nag_STATE_WARNING),
        6: ("Add Drive to Logical Drive in Progress", limits.nag_STATE_WARNING),
        9: ("Global Spare Drive", limits.nag_STATE_OK),
        int("11", 16): ("Drive is in process of Cloning another Drive", limits.nag_STATE_WARNING),
        int("12", 16): ("Drive is a valid Clone of another Drive", limits.nag_STATE_OK),
        int("13", 16): ("Drive is in process of Copying from another Drive", limits.nag_STATE_WARNING),
        int("3f", 16): ("Drive Absent", limits.nag_STATE_OK),
        # int("8x", 16) : "SCSI Device (Type x)",
        int("fc", 16): ("Missing Global Spare Drive", limits.nag_STATE_CRITICAL),
        int("fd", 16): ("Missing Spare Drive", limits.nag_STATE_CRITICAL),
        int("fe", 16): ("Missing Drive", limits.nag_STATE_CRITICAL),
        int("ff", 16): ("Failed Drive", limits.nag_STATE_CRITICAL)
    }

    def __init__(self, in_dict):
        eonstor_object.__init__(self, "disc", in_dict, state_key=11)
        disk_num = int(in_dict[13])
        self.name = "Disc{:d}".format(disk_num)
        if self.state in self.lu_dict:
            state_str, state_val = self.lu_dict[self.state]
            if state_val == limits.nag_STATE_WARNING:
                self.set_warn(state_str)
            elif state_val == limits.nag_STATE_CRITICAL:
                self.set_error(state_str)
        elif self.state & int("80", 16) == int("80", 16):
            self.name = "SCSI Disc {:d}".format(self.state & ~int("80", 16))
        else:
            self.set_warn("unknown state {:d}".format(self.state))
        # generate long string
        # ignore SCSIid and SCSILun
        if 15 in in_dict:
            disk_size = (2 ** int(in_dict[8])) * int(in_dict[7])
            vers_str = "{} ({})".format(
                (" ".join(in_dict[15].split())).strip(),
                in_dict[16].strip()
            )
            self.long_string = "{}, LC {:d}, PC {:d}, {}".format(
                logging_tools.get_size_str(disk_size, divider=1000),
                int(in_dict[2]),
                int(in_dict[3]),
                vers_str
            )
        else:
            self.long_string = "no disk"

    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_ld(eonstor_object):
    lu_dict = {0: ("Good", limits.nag_STATE_OK),
               1: ("Rebuilding", limits.nag_STATE_WARNING),
               2: ("Initializing", limits.nag_STATE_WARNING),
               3: ("Degraded", limits.nag_STATE_CRITICAL),
               4: ("Dead", limits.nag_STATE_CRITICAL),
               5: ("Invalid", limits.nag_STATE_CRITICAL),
               6: ("Incomplete", limits.nag_STATE_CRITICAL),
               7: ("Drive missing", limits.nag_STATE_CRITICAL)}

    def __init__(self, in_dict):
        eonstor_object.__init__(self, "ld", in_dict, state_key=7)
        self.name = "LD"
        state_str, state_val = self.lu_dict[int(in_dict[6]) & 7]
        if state_val == limits.nag_STATE_WARNING:
            self.set_warn(state_str)
        elif state_val == limits.nag_STATE_CRITICAL:
            self.set_error(state_str)
        if self.state & 1:
            self.set_warn("rebuilding")
        if self.state & 2:
            self.set_warn("expanding")
        if self.state & 4:
            self.set_warn("adding drive(s)")
        if self.state & 64:
            self.set_warn("SCSI drives operation paused")
        # opmode
        op_mode = int(in_dict[5]) & 15
        op_mode_str = {0: "Single Drive",
                       1: "NON-RAID",
                       2: "RAID 0",
                       3: "RAID 1",
                       4: "RAID 3",
                       5: "RAID 4",
                       6: "RAID 5",
                       7: "RAID 6"}.get(op_mode, "NOT DEFINED")
        op_mode_extra_bits = int(in_dict[5]) - op_mode
        if type(in_dict[3]) == str and in_dict[3].lower().startswith("0x"):
            ld_size = int(in_dict[3][2:], 16) * 512
            vers_str = "id %s" % (in_dict[2])
        else:
            ld_size = (2 ** int(in_dict[4])) * (int(in_dict[3]))
            vers_str = "id %d" % (int(in_dict[2]))
        drv_total, drv_online, drv_spare, drv_failed = (int(in_dict[8]),
                                                        int(in_dict[9]),
                                                        int(in_dict[10]),
                                                        int(in_dict[11]))
        if drv_failed:
            self.set_error("%s failed" % (logging_tools.get_plural("drive", drv_failed)))
        drv_info = "%d total, %d online%s" % (drv_total,
                                              drv_online,
                                              ", %d spare" % (drv_spare) if drv_spare else "")
        self.long_string = "%s (0x%x) %s, %s, %s" % (op_mode_str,
                                                     op_mode_extra_bits,
                                                     logging_tools.get_size_str(ld_size, divider=1000),
                                                     drv_info,
                                                     vers_str)

    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_slot(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "slot", in_dict)
        if self.state & 1:
            self.set_error("Sense circuitry malfunction")
        if self.state & 2:
            self.set_error("marked BAD, waiting for replacement")
        if self.state & 4:
            self.set_warn("not activated")
        if self.state & 64:
            self.set_warn("ready for insertion / removal")
        if self.state & 128:
            self.set_warn("slot is empty")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "slot %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_psu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "PSU", in_dict)
        if self.state & 1:
            self.set_error("PSU malfunction")
        if self.state & 64:
            self.set_warn("PSU is OFF")
        if self.state & 128:
            self.set_warn("PSU not present")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "PSU %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_bbu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "BBU", in_dict)
        if self.state & 1:
            self.set_error("BBU malfunction")
        if self.state & 2:
            self.set_warn("BBU charging")
        if self.state & 64:
            self.set_warn("BBU disabled")
        if self.state & 128:
            self.set_warn("BBU not present")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "BBU %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_ups(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "UPS", in_dict)
        if self.state & 128:
            self.set_warn("UPS not present")
        else:
            if self.state & 1:
                self.set_error("UPS malfunction")
            if self.state & 2:
                self.set_error("AC Power not present")
            if self.state & 64:
                self.set_warn("UPS is off")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "UPS %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_fan(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Fan", in_dict)
        if self.state & 1:
            self.set_error("Fan malfunction")
        if self.state & 64:
            self.set_warn("Fan is OFF")
        if self.state & 128:
            self.set_warn("Fan not present")
        if not self.state:
            self.out_string = "%.2f RPM" % (float(in_dict[9]) / 1000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "fan %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_temperature(eonstor_object):
    def __init__(self, in_dict, net_obj):
        eonstor_object.__init__(self, "temp", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % (
                {
                    2: "cold",
                    3: "hot"
                }[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % (
                {
                    4: "cold",
                    5: "hot"
                }[sensor_th]))
        if not self.state and int(in_dict[9]):
            if net_obj.eonstor_version == 2:
                self.out_string = "%.2f C" % (float(in_dict[9]) * float(in_dict[10]) / 1000 - 273)
            else:
                self.out_string = "%.2f C" % (float(in_dict[9]) / 1000000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "temperature %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_voltage(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Voltage", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % (
                {
                    2: "low",
                    3: "high"
                }[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % (
                {
                    4: "low",
                    5: "high"
                }[sensor_th]))
        if not self.state:
            self.out_string = "%.2f V" % (float(in_dict[9]) / 1000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "voltage %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_info_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "eonstor_info", **kwargs)
        if "net_obj" in kwargs:
            net_obj = kwargs["net_obj"]
            if not hasattr(net_obj, "eonstor_version"):
                net_obj.eonstor_version = 2
            _vers = net_obj.eonstor_version
        else:
            _vers = 2
        if _vers == 1:
            self.__th_system = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
            self.__th_disc = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
        else:
            self.__th_system = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 1, 9, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
            self.__th_disc = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1),
                cache=True,
                cache_timeout=EONSTOR_TIMEOUT,
                max_oid=(1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1, 20)
            )
        self.requests = [
            self.__th_system,
            self.__th_disc
        ]

    def error(self):
        if len(self.get_missing_headers()) == 2:
            # change eonstor version
            self.net_obj.eonstor_version = 3 - self.net_obj.eonstor_version

    def process_return(self):
        # device dict (also for discs)
        dev_dict = {}
        for dev_idx, dev_stuff in self._reorder_dict(self.snmp_dict[tuple(self.__th_system)]).iteritems():
            if dev_stuff[6] == 17:
                # slot
                dev_dict[dev_idx] = eonstor_slot(dev_stuff)
            elif dev_stuff[6] == 2:
                # fan
                dev_dict[dev_idx] = eonstor_fan(dev_stuff)
            elif dev_stuff[6] == 3:
                # temperature
                dev_dict[dev_idx] = eonstor_temperature(dev_stuff, self.net_obj)
            elif dev_stuff[6] == 1:
                # power supply
                dev_dict[dev_idx] = eonstor_psu(dev_stuff)
            elif dev_stuff[6] == 11:
                # battery backup unit
                dev_dict[dev_idx] = eonstor_bbu(dev_stuff)
            elif dev_stuff[6] == 4:
                # UPS
                dev_dict[dev_idx] = eonstor_ups(dev_stuff)
            elif dev_stuff[6] == 5:
                # voltage
                dev_dict[dev_idx] = eonstor_voltage(dev_stuff)
        for disc_idx, disc_stuff in self._reorder_dict(self.snmp_dict[tuple(self.__th_disc)]).iteritems():
            dev_dict["d{:d}".format(disc_idx)] = eonstor_disc(disc_stuff)
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        for key in sorted(dev_dict.keys()):
            value = dev_dict[key]
            if value.nag_state:
                # only show errors and warnings
                ret_state = max(ret_state, value.nag_state)
                ret_field.append(value.get_ret_str())
        ret_field.sort()
        return ret_state, "; ".join(ret_field) or "no errors or warnings"


class eonstor_proto_scheme(SNMPRelayScheme):
    def __init__(self, name, **kwargs):
        SNMPRelayScheme.__init__(self, name, **kwargs)
        if "net_obj" in kwargs:
            net_obj = kwargs["net_obj"]
            if not hasattr(net_obj, "eonstor_version"):
                net_obj.eonstor_version = 1
            eonstor_version = getattr(net_obj, "eonstor_version", 1)
        else:
            eonstor_version = 2
        if eonstor_version == 1:
            self.sys_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1)
            self.disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1)
            self.max_disc_oid = None
            self.ld_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 2, 1)
        else:
            self.sys_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 9, 1)
            self.disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1)
            self.max_disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1, 20)
            self.ld_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 2, 1)
        if kwargs.get("ld_table", False):
            self.requests = snmp_oid(self.ld_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT)
        if kwargs.get("disc_table", False):
            self.requests = snmp_oid(self.disc_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT, max_oid=self.max_disc_oid)
        if kwargs.get("sys_table", False):
            self.requests = snmp_oid(self.sys_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT)

    def error(self):
        if len(self.get_missing_headers()) == len(self.requests):
            # change eonstor version
            self.net_obj.eonstor_version = 3 - self.net_obj.eonstor_version

    def process_return(self):
        # reorder the snmp-dict
        pre_dict = self._reorder_dict(self.snmp_dict[tuple(self.requests[0])])
        return self._generate_return(self.handle_dict(pre_dict))

    def _generate_return(self, dev_dict):
        if "iarg" in self.opts:
            dev_idx = self.opts.iarg
        else:
            dev_idx = 0
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        raw_dict = {}
        if dev_idx:
            if dev_idx in dev_dict:
                if self.xml_input:
                    raw_dict = {"state": dev_dict[dev_idx].state}
                else:
                    value = dev_dict[dev_idx]
                    ret_state = value.nag_state
                    ret_field.append(value.get_ret_str(long_format=True) or "%s is OK" % (value.name))
            else:
                ret_state = limits.nag_STATE_CRITICAL
                ret_field.append("idx %d not found in dict (possible values: %s)" % (
                    dev_idx,
                    ", ".join(["%d" % (key) for key in sorted(dev_dict.keys())])))
        else:
            for key in sorted(dev_dict.keys()):
                value = dev_dict[key]
                ret_state = max(ret_state, value.nag_state)
                act_ret_str = value.get_ret_str() or "%s is OK" % (value.name)
                ret_field.append(act_ret_str)
            ret_field.sort()
        if self.xml_input:
            self.srv_com["eonstor_info"] = raw_dict
            return limits.nag_STATE_OK, "ok got info"
        else:
            return ret_state, "; ".join(ret_field) or "no errors or warnings"


class eonstor_ld_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_ld_info", ld_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_ld(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems()}


class eonstor_fan_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_fan_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_fan(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 2}


class eonstor_temperature_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_temperature_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_temperature(dev_stuff, self.net_obj) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 3}


class eonstor_ups_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_ups_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_ups(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 4}


class eonstor_bbu_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_bbu_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_bbu(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 11}


class eonstor_voltage_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_voltage_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_voltage(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 5}


class eonstor_slot_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_slot_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_slot(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 17}


class eonstor_disc_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_disc_info", disc_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_disc(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems()}


class eonstor_psu_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_psu_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_psu(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 1}


class eonstor_get_counter_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_get_counter", sys_table=True, disc_table=True, ld_table=True, **kwargs)
        self.parse_options(kwargs["options"])

    def process_return(self):
        sys_dict, disc_dict = (
            self._reorder_dict(self.snmp_dict[self.sys_oid]),
            self._reorder_dict(self.snmp_dict[self.disc_oid])
        )
        # number of discs
        info_dict = {"disc_ids": disc_dict.keys()}
        for idx, value in sys_dict.iteritems():
            ent_name = {
                1: "psu",
                2: "fan",
                3: "temperature",
                4: "ups",
                5: "voltage",
                11: "bbu",
                17: "slot"
            }.get(value[6], None)
            if ent_name:
                info_dict.setdefault("ent_dict", {}).setdefault(ent_name, {})[idx] = value[8]
        info_dict["ld_ids"] = self._reorder_dict(self.snmp_dict[self.ld_oid]).keys()
        if self.xml_input:
            self.srv_com["eonstor_info"] = info_dict
            return limits.nag_STATE_OK, "ok got info"
        else:
            # FIXME
            return limits.nag_STATE_OK, process_tools.sys_to_net(info_dict)
