#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010 Andreas Lang-Nevyjel, init.at
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

import sys
import os
import os.path
import re
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import stat
import time
import logging_tools
import process_tools
import commands
import pprint

class ipmi_sensor(object):
    sensor_dict = {}
    main_keys = {}
    sensors_with_readings = set()
    def __init__(self, mod_class, logger, line):
        l_parts = [part.strip() for part in line.split("|")]
        if len(l_parts) in [10] and not l_parts[0].startswith("-"):
            self.mod_class = mod_class
            name = l_parts[0]
            self.name = name
            self.sensor_type = l_parts[2].lower()
            if l_parts[1].lower() == "na":
                # sensor is not available, change sensor type
                self.sensor_type = "%s_%s" % (self.sensor_type, l_parts[1].lower())
            for loc_name in [name, name.lower(), name.replace(" ", "_"), name.replace(" ", "_").lower()]:
                ipmi_sensor.sensor_dict[loc_name] = self
            # main key
            ipmi_sensor.main_keys.setdefault(self.sensor_type, []).append(self.name)
            ipmi_sensor.main_keys.setdefault("all", []).append(self.name)
            self.parts = l_parts
            self._map_to_mv_key()
            self.value = None
            logger.log("added sensor %-30s (type %-20s)" % ("'%s'" % (self.name),
                                                            self.sensor_type))
        else:
            # discard it
            pass
    def _map_to_mv_key(self):
        # key for machvector, None if not mappable
        self.key = None
        parts = self.name.strip().lower().split()
        if self.sensor_type == "rpm":
            if len(parts) > 1 and parts[1].isdigit():
                self.key = "fan.fan%d" % (int(parts[1]))
                self.info = "rotation of FAN %d" % (int(parts[1]))
            elif parts[0].startswith("fan") and parts[0][3:].isdigit():
                self.key = "fan.%s" % (parts[0])
                self.info = "rotation of %s" % (parts[0])
            self.unit = "RPM"
            self.base = 1000
        elif self.sensor_type == "degrees c":
            if len(parts) > 1 and parts[1].isdigit():
                self.key = "temp.%s%d" % (parts[0].lower(),
                                          int(parts[1]))
                self.info = "Temperature of %s%d" % (parts[0].lower(),
                                                     int(parts[1]))
            elif parts[0].startswith("cpu") and parts[0][3:].isdigit():
                self.key = "temp.%s" % (parts[0])
                self.info = "Temperature of %s" % (parts[0])
            elif parts[0] in ["system", "ambient"]:
                self.key = "temp.%s" % (parts[0])
                self.info = "Temperature of %s" % (parts[0])
            self.unit = "C"
            self.base = 1000
    @classmethod
    def update_all(self, mod_class, logger, keys=[]):
        if mod_class.it_command:
            if not keys:
                keys = ["all"]
            if keys:
                s_keys = sorted(sum([ipmi_sensor.main_keys.get(key, []) for key in keys], []))
                r_keys = [part.replace(" ", r"\ ") for part in s_keys]
                c_suc, c_stat, c_out = mod_class.call_ipmi_command("sensor get %s" % (" ".join(r_keys)), logger)
                if c_suc:
                    for key in s_keys:
                        ipmi_sensor.sensor_dict[key].feed_output(c_out, logger)
    def __getitem__(self, key):
        return self.__sens_dict[key]
    def get(self, key, default):
        return self.__sens_dict.get(key, default)
    def __in__(self, key):
        return key in self.__sens_dict
    def feed_output(self, lines, logger):
        found = False
        sens_dict = {}
        for line in lines:
            if line.lower().startswith("sensor id") and line.split(":")[1].strip().startswith(self.name):
                found = True
            elif not line.strip():
                if found:
                    break
            if found and line.count(":"):
                l_parts = line.split(":")
                try:
                    key, value = line.split(":")
                except:
                    logger.log("cannot parse line '%s' : %s" % (line, process_tools.get_except_info()),
                               logging_tools.LOG_LEVEL_ERROR)
                else:
                    key = key.strip().lower().replace(" ", "_")
                    sens_dict[key] = value.lower()
        self.__sens_dict = sens_dict
        if found:
            if self.sensor_type in ["rpm", "degrees c", "volts"]:
                try:
                    cur_value = float(sens_dict["sensor_reading"].split()[0])
                except:
                    pass
                else:
                    ipmi_sensor.sensors_with_readings.add(self.name)
                    self.value = cur_value
    def __repr__(self):
        return "%s: %s %s" % (self.name,
                              "%.2f" % (self.value) if self.value is not None else "None",
                              self.sensor_type)

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "ipmi",
                                        "interface to the impitool functionality",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.check_ipmi_settings(logger)
    def check_ipmi_settings(self, logger):
        cmd_name = "ipmitool"
        self.it_command = process_tools.find_file(cmd_name)
        if self.it_command:
            logger.log("found %s at %s" % (cmd_name,
                                           self.it_command))
            c_suc, c_stat, c_out = self.call_ipmi_command("sensor list", logger)
            if c_suc:
                for line in c_out:
                    new_sensor = ipmi_sensor(self, logger, line)
            #new_sensor.update(logger)
            ipmi_sensor.update_all(self, logger, ["rpm", "degrees c"])
        else:
            logger.log("cmd %s not found" % (cmd_name),
                       logging_tools.LOG_LEVEL_WARN)
    def call_ipmi_command(self, cmd, logger):
        return self.call_command("%s %s" % (self.it_command, cmd), logger, ok_values=[0, 1, 256])
    def call_command(self, cmd, logger, **kwargs):
        ok_vals = kwargs.get("ok_values", [0])
        c_stat, c_out = commands.getstatusoutput(cmd)
        if c_stat not in ok_vals:
            logger.log("cmd '%s' gave (%d):" % (cmd,
                                                c_stat),
                       logging_tools.LOG_LEVEL_ERROR)
            for line in c_out.split("\n"):
                logger.log(" - %s" % (line), logging_tools.LOG_LEVEL_ERROR)
            return False, c_stat, c_out.split("\n")
        else:
            return True, c_stat, c_out.split("\n")
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        for opt, arg in opts:
            #print opt, arg
            if opt == "-w":
                if my_lim.set_warn_val(arg) == 0:
                    ok = 0
                    why = "Can't parse warning value !"
            if opt == "-c":
                if my_lim.set_crit_val(arg) == 0:
                    ok = 0
                    why = "Can't parse critical value !"
        return ok, why, [my_lim]
    def process_server_args(self, glob_config, logger):
        #print "Processing ", opts
        ok, why = (1, "")
        return ok, why
    def init_m_vect(self, mv, logger):
        #v_keys = ipmi_sensor.main_keys["all"]
        for key in sorted(ipmi_sensor.sensors_with_readings):
            cur_sensor = ipmi_sensor.sensor_dict[key]
            if cur_sensor.key:
                mv.reg_entry(cur_sensor.key,
                             0.,
                             cur_sensor.info,
                             cur_sensor.unit,
                             cur_sensor.base
                             )
    def update_m_vect(self, mv, logger):
        ipmi_sensor.update_all(self, logger, ["rpm", "degrees c"])
        for key in sorted(ipmi_sensor.sensors_with_readings):
            cur_sensor = ipmi_sensor.sensor_dict[key]
            if cur_sensor.key:
                mv.reg_update(logger, cur_sensor.key, cur_sensor.value)

def sensor_int(mod_info):
    ret_dict = {}
    int_error = "IntError"
    for name, stuff in mod_info.sens_dict.iteritems():
        if mod_info.targ_dict.has_key(stuff["port"]):
            try:
                src = mod_info.targ_dict[stuff["port"]]
                slc = file(src, "r").read().split()
                if src.startswith("/proc"):
                    val = float(slc[-1])
                else:
                    val = float(slc[0])
                    if [True for ms in ["temp", "core"] if stuff["port"].startswith(ms)]:
                        val /= 1000.
                val = float(stuff["d"])+val*float(stuff["k"])
                if stuff["port"].startswith("temp") and stuff.has_key("latest") and val > 100.:
                    val = stuff["latest"]
                else:
                    stuff["latest"] = val
                ret_dict[name] = val
            except:
                raise int_error
    else:
        pass
    return ret_dict

class ipmi_sensor_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "ipmi_sensor", **args)
        self.help_str = "returns the value of sensor NAME"
        self.short_client_info = "-w warn -c crit"
        self.long_client_info = "bla-bla"
        self.short_client_opts = "w:c:"
        self.long_server_info = "returns the setting of an ipmi sesor"

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
