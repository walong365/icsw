#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009 Andreas Lang-Nevyjel, init.at
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

SENSFILE_NAME = "sensinfo"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "sensors",
                                        "interface to the i2c-sensor functionality to monitor important hardware-parameters",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__sfile_name = "%s/%s" % (basedir_name, SENSFILE_NAME)
            self.__sfile_checked = 0
            self.sens_dict = {}
            self.find_i2c_devices(logger)
    def find_i2c_devices(self, logger):
        targ_dict = {}
        start_path = "/sys/devices/platform"
        logger.log("Starting search for adapters in %s ..." % (start_path))
        sensor_found_list = []
        if os.path.isdir(start_path):
            # ipmi
            adapters = ["%s/%s" % (start_path, act_ent) for act_ent in os.listdir(start_path) if os.path.isdir("%s/%s" % (start_path, act_ent)) and os.path.exists("%s/%s/temp1_input" % (start_path, act_ent))]
            for adap in adapters:
                logger.log("Found ipmi-adapater with base-path '%s'" % (adap))
                for f_name in [y for y in os.listdir(adap) if y.endswith("_input")]:
                    sens_name = f_name.split("_")[0]
                    sensor_found_list.append((sens_name, "%s/%s" % (adap, f_name)))
            # coretemp
            coretemps = ["%s/%s" % (start_path, act_ent) for act_ent in os.listdir(start_path) if act_ent.startswith("coretemp")]
            for coretemp in coretemps:
                logger.log("Found coretemp sensor with base-path '%s'" % (coretemp))
                act_dict = {}
                for f_name in [y for y in os.listdir(coretemp) if [True for pf in ["input", "label"] if y.endswith(pf)]]:
                    act_dict[f_name] = file("%s/%s" % (coretemp, f_name), "r").read().strip().lower().replace(" ", "")
                if len(act_dict.keys()) == 2:
                    sens_name = act_dict["temp1_label"]
                    sensor_found_list.append((sens_name, "%s/%s" % (coretemp, "temp1_input")))
                else:
                    logger.warning("Dict not fully populated or over populated for %s (len is %d)" % (coretemp,
                                                                                                      len(act_dict.keys())))
        logger.info("Starting search for i2c-adapters in %s ..." % (start_path))
        start_path = "/sys/class/i2c-adapter"
        if os.path.isdir(start_path):
            adapters = ["%s/%s" % (start_path, act_ent) for act_ent in os.listdir(start_path)]
            for adap in adapters:
                logger.info("Found i2c-adapater with base-path '%s'" % (adap))
                for sub_dir in [cur_sub_dir for cur_sub_dir in ["%s" % (adap),
                                                                "%s/device" % (adap)] if os.path.isdir(cur_sub_dir)]:
                    for ad in ["%s/%s" % (sub_dir, act_ent) for act_ent in os.listdir(sub_dir) if re.match("^\w+-\w+$", act_ent)]:
                        logger.info("  now in dir %s ..." % (ad))
                        for f_name in [y for y in os.listdir(ad) if y.endswith("_input")]:
                            sens_name = f_name.split("_")[0]
                            sensor_found_list.append((sens_name, "%s/%s" % (ad, f_name)))
        if sensor_found_list:
            sensor_found_list.sort()
            logger.info("Found %s: %s" % (logging_tools.get_plural("senor", len(sensor_found_list)),
                                          ", ".join([a for a, b in sensor_found_list])))
            for sens_name, full_path in sensor_found_list:
                if targ_dict.has_key(sens_name):
                    sens_idx = 1
                    while 1:
                        sens_idx += 1
                        act_sens_name = "%s.%d" % (sens_name, sens_idx)
                        if not targ_dict.has_key(act_sens_name):
                            break
                else:
                    targ_dict[sens_name] = full_path
                    logger.info("   setting sensor %-10s to path %s" % (sens_name, targ_dict[sens_name]))
                    act_sens_name = "%s.1" % (sens_name)
                targ_dict[act_sens_name] = full_path
                logger.info("   setting sensor %-10s to path %s" % (act_sens_name, targ_dict[act_sens_name]))
        else:
            logger.info("Found no sensors in /sys")
        start_path = "/proc/sys/dev/sensors"
        logger.info("Starting search for i2c-adapters in %s ..." % (start_path))
        if os.path.isdir(start_path):
            adapters = [x for x in ["%s/%s" % (start_path, x) for x in os.listdir(start_path)] if os.path.isdir(x)]
            for adap in adapters:
                for sens_name in os.listdir(adap):
                    if targ_dict.has_key(sens_name):
                        logger.warning("+++ sensor %-10s already present in dict (%s)" % (sens_name, targ_dict[sens_name]))
                    else:
                        targ_dict[sens_name] = "%s/%s" % (adap, sens_name)
                        logger.info("   setting sensor %-10s to path %s" % (sens_name, targ_dict[sens_name]))
        logger.info("Saving targ_dict for sensors with %d entries" % (len(targ_dict.keys())))
        self.targ_dict = targ_dict
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
        self.check_for_sensfile(logger)
        return ok, why
    def check_for_sensfile(self, logger):
        self.__sfile_checked = time.time()
        if os.path.isfile(self.__sfile_name):
            self.sens_dict = {}
            logger.info("reading sensor_file %s" % (self.__sfile_name))
            arg = file(self.__sfile_name, "r").readline().strip()
            for sens in arg.split(":"):
                sss = sens.split(",")
                if len(sss) != 4:
                    ok, why = (0, "Error parsing SENSINFO %s: %d != %d" % (",".join(sss), len(sss), 4))
                    break
                name, port, mult, off = (sss[0], sss[1], sss[2], sss[3])
                if not mult:
                    mult = 1.0
                if not off:
                    off = 0.0
                if not name or not port:
                    ok, why = (0, "Error parsing SENSINFO %s: name or port missing" % (",".join(sss)))
                    break
                self.sens_dict[name.lower()] = {"port" : port,
                                                "k"    : mult,
                                                "d"    : off}
            parse_sensinfo(self, logger)
        else:
            logger.warning("no sensor_file %s found" % (self.__sfile_name))
    def init_m_vect(self, mv, logger):
        if os.path.isfile(self.__sfile_name):
            if os.stat(self.__sfile_name)[stat.ST_MTIME] > self.__sfile_checked:
                act_keys = [x["key"] for x in self.sens_dict.values()]
                self.check_for_sensfile(logger)
                new_keys = [x["key"] for x in self.sens_dict.values()]
                for del_key in [x for x in act_keys if x not in new_keys]:
                    mv.unreg_entry(del_key)
        for name, stuff in self.sens_dict.iteritems():
            if stuff.has_key("key") and not mv.has_key(stuff["key"]):
                #print "***", stuff
                mv.reg_entry(stuff["key"], 0., stuff["info"], stuff["unit"], stuff["base"])
    def update_m_vect(self, mv, logger):
        int_error = "IntError"
        self.init_m_vect(mv, logger)
        short_sinfo = [x.lower() for x in self.sens_dict.keys()]
        s_dict = {}
        for info in short_sinfo:
            s_dict[info] = 0.
        try:
            s_dict = sensor_int(self)
        except int_error:
            pass
        for info in short_sinfo:
            #print machvect_keys, s_dict, info
            if s_dict.has_key(info) and self.sens_dict[info].has_key("key"):
                mv.reg_update(logger, self.sens_dict[info]["key"], s_dict[info])

class sensor_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "sensor", **args)
        self.help_str = "returns the value of port NAME"
        self.short_client_info = "-w warn -c crit"
        self.long_client_info = "bla-bla"
        self.short_client_opts = "w:c:"
        self.short_server_info = SENSFILE_NAME
        self.long_server_info = "set sensor info, where SENSINFOS is a colon-separated list of SENSINFO sets " + \
                                "or a file with SENSINFO sets. a SENSINFO set is equal to name,port,mult,offset, mult and offset " + \
                                "have the default values 1.0 and 0.0. example: CPU-Temp,temp2,1.0,2.0"
    def server_call(self, cm):
        int_error = "IntError"
        if len(cm) != 1:
            return "invalid number of parameters (%d != 1)" % (len(cm))
        s_dict = dict([(k.lower(), 0.) for k in self.module_info.sens_dict.keys()])
        try:
            s_dict = sensor_int(self.module_info)
        except int_error:
            pass
        #print s_dict.keys(),cm
        what = cm[0].lower()
        if s_dict.has_key(what):
            return "ok %s" % (hm_classes.sys_to_net({"sensor" : cm[0], "value" : s_dict[what]}))
        else:
            return "invalid parameter %s not known (not one of %s)" % (str(what),
                                                                       ", ".join([str(x) for x in s_dict.keys()]) or "none set")
    def client_call(self, result, parsed_coms):
        lim = parsed_coms[0]
        result = hm_classes.net_to_sys(result[3:])
        val = result["value"]
        val_i = int(val)
        if re.match("^.*emp.*$", result["sensor"]):
            what = "C"
            if val_i == -1:
                ret_state = limits.nag_STATE_WARNING
                state = "Can't read"
            else:
                ret_state, state = lim.check_ceiling(val)
        else:
            what = "RPM"
            ret_state, state = lim.check_floor(val)
            if (val_i == -1) or (val_i == 0):
                ret_state = limits.nag_STATE_WARNING
                state = "Can't read"
            else:
                ret_state, state = lim.check_floor(val)
        return ret_state, "%s: %s has %s %s" % (state, result["sensor"], val, what)

def parse_sensinfo(mod_info, logger):
    devdict = {"mb"  : "mainboard",
               "cpu" : "CPU",
               "nb"  : "northbridge"}
    for name, stuff in mod_info.sens_dict.iteritems():
        temp_m = re.match("^([a-z]+)(\d*)-temp$", name)
        fan_m = re.match("^([a-z]+)(\d*)-fan$", name)
        if temp_m:
            device = temp_m.group(1)
            if temp_m.group(2):
                devset, devnum = (1, int(temp_m.group(2)))
            else:
                devset, devnum = (0, 0)
            mkey = "temp.%s%d" % (device, devnum)
            info = "temperature of the %s" % (devdict.get(device, device))
            if devset:
                info += " #%d" % (devnum)
            unit, base = ("C", 1)
        elif fan_m:
            device = fan_m.group(1)
            if fan_m.group(2):
                devnum = int(fan_m.group(2))
            else:
                devnum = 0
            mkey = "fan.%s%d" % (device, devnum)
            info = "rotation of the %s #%d-fan" % (devdict.get(device, device), devnum)
            unit, base = ("RPM", 1000)
        else:
            mkey = None
        if mkey:
            logger.info("Recognized as sensor '%s' (on port %s): %s (%s) [%s,%d]" % (name, stuff["port"], mkey, info, unit, base))
            mod_info.sens_dict[name]["key"] = mkey
            mod_info.sens_dict[name]["info"] = info
            mod_info.sens_dict[name]["unit"] = unit
            mod_info.sens_dict[name]["base"] = base
    #print "**", sens_dict

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

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
