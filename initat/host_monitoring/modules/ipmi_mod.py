#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010,2013 Andreas Lang-Nevyjel, init.at
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

""" IPMI sensor readings """

from initat.host_monitoring.config import global_config
from initat.host_monitoring import hm_classes, limits
import commands
import logging_tools
import os
import pprint
import process_tools
import re
import stat
import subprocess
import sys
import time

def parse_ipmi_type(name, sensor_type):
    key, info, unit, base = ("", "", "", 1)
    parts = name.strip().split()
    lparts = name.strip().lower().split()
    key_str = "_".join([_p.replace(".", ",") for _p in lparts])
    # print "parse", name, sensor_type, parts
    if sensor_type == "rpm":
        if lparts[-1] == "tach":
            lparts.pop(-1)
        key = "fan.%s" % (key_str)
        info = "rotation of fan %s" % (" ".join(parts))
        unit = "RPM"
        base = 1000
    elif sensor_type == "degrees c":
        key = "temp.%s" % (key_str)
        info = "Temperature of %s" % (" ".join(parts))
        unit = "C"
    elif sensor_type == "volts":
        key = "volts.%s" % (key_str)
        info = "Voltage of %s" % (" ".join(parts))
        unit = "V"
    elif sensor_type == "watts":
        key = "watts.%s" % (key_str)
        info = "Power usage of %s" % (" ".join(parts))
        unit = "W"
    return key, info, unit, base

def parse_ipmi(in_lines):
    result = {}
    for line in in_lines:
        parts = [_part.strip() for _part in line.split("|")]
        if len(parts) == 10:
            s_type = parts[2].lower()
            if s_type not in ["discrete"] and parts[1].lower() not in ["na"]:
                key, info, unit, base = parse_ipmi_type(parts[0], s_type)
                if key:
                    result[key] = (float(parts[1]), info, unit, base)
    return result

class _general(hm_classes.hm_module):
    def init_module(self):
        self.ipmi_result, self.ipmi_update = (None, None)
        self.it_command = False
        self.registered_mvs = set()
        if hasattr(self.process_pool, "register_vector_receiver") and global_config["TRACK_IPMI"]:
            self.check_ipmi_settings()
            self.popen = None
            self.process_pool.register_timer(self._update_ipmi, 20, instant=True)
        # print "*" * 20

    def _update_ipmi(self):
        if self.it_command:
            if self.popen:
                cur_res = self.popen.poll()
                if cur_res is not None:
                    self.ipmi_result = parse_ipmi(self.popen.stdout.read().split("\n"))
                    self.ipmi_update = time.time()
                    self.popen = None
            if not self.popen:
                self.popen = subprocess.Popen("%s sensor" % (self.it_command), shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    def check_ipmi_settings(self):
        cmd_name = "ipmitool"
        self.it_command = process_tools.find_file(cmd_name)
        # print self.it_command
        if self.it_command:
            mp_command = process_tools.find_file("modprobe")
            self.log(
                "found %s at %s" % (
                    cmd_name,
                    self.it_command))
            self.log("trying to load ipmi kernel modules")
            for kern_mod in ["ipmi_si", "ipmi_devintf"]:
                cmd = "%s %s" % (mp_command, kern_mod)
                c_stat, c_out = commands.getstatusoutput(cmd)
                self.log("calling '%s' gave (%d): %s" % (
                    cmd,
                    c_stat,
                    c_out
                    ))
            # c_suc, c_stat, c_out = self.call_ipmi_command("sensor list", self.log)
            # if c_suc:
            #    for line in c_out:
            #        new_sensor = ipmi_sensor(self, self.log, line)
            # new_sensor.update(logger)
            # ipmi_sensor.update_all(self, self.log, ["rpm", "degrees c"])
        else:
            self.log(
                "cmd %s not found" % (cmd_name),
                logging_tools.LOG_LEVEL_WARN)
    def update_machine_vector(self, mv):
        if self.ipmi_result:
            new_keys = set(self.ipmi_result) - self.registered_mvs
            del_keys = self.registered_mvs - set(self.ipmi_result)
            update_keys = set(self.ipmi_result) & self.registered_mvs
            for del_key in del_keys:
                mv.unregister_entry(del_key)
            for new_key in new_keys:
                _values = self.ipmi_result[new_key]
                self.registered_mvs.add(new_key)
                mv.register_entry(new_key, _values[0], _values[1], _values[2], _values[3])
            for upd_key in update_keys:
                mv[upd_key] = self.ipmi_result[upd_key][0]
            # pprint.pprint(self.ipmi_result)

class ipmi_bg(hm_classes.subprocess_struct):
    class Meta:
        verbose = False
        id_str = "ipmi"
    def __init__(self, log_com, srv_com, ipmi_com, it_command):
        self.__log_com = log_com
        self.__ipmi_com = ipmi_com
        hm_classes.subprocess_struct.__init__(self, srv_com, ["%s -s '%s'" % (
            it_command,
            ipmi_com.Meta.command,
            )])
    def process(self):
        self.__ipmi_com.process(self)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[ipmi] %s" % (what), level)

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
                val = float(stuff["d"]) + val * float(stuff["k"])
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

class _ipmi_sensor(object):
    class Meta:
        command = "sensor list"
    def process(self, bgp):
        for line in bgp.read().split("\n"):
            print line
            pass

class ipmi_sensor_command(hm_classes.hm_command):
    info_string = "IPMI sensor readout"
    def __call__(self, srv_com, cur_ns):
        # return self.module.sensor.handle_srv_com(srv_com, cur_ns)
        return ipmi_bg(self.log, srv_com, _ipmi_sensor(), self.module.it_command)
    def interpret(self, srv_com, cur_ns):
        return _ipmi_sensor().interpret(srv_com, cur_ns)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
