# Copyright (C) 2010,2013-2014 Andreas Lang-Nevyjel, init.at
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

from initat.host_monitoring import hm_classes, limits
from initat.host_monitoring.config import global_config
import commands
import logging_tools
import process_tools
import server_command
import subprocess
import time

IPMI_LIMITS = ["ln", "lc", "lw", "uw", "uc", "un"]
IPMI_LONG_LIMITS = ["{}{}".format({"l": "lower", "u": "upper"}[key[0]], key[1:]) for key in IPMI_LIMITS]


def parse_ipmi_type(name, sensor_type):
    key, info, unit, base = ("", "", "", 1)
    parts = name.strip().split()
    lparts = name.strip().lower().split()
    key_str = "_".join([_p.replace(".", ",") for _p in lparts])
    # print "parse", name, sensor_type, parts
    if sensor_type == "rpm":
        if lparts[-1] == "tach":
            lparts.pop(-1)
        key = "fan.{}".format(key_str)
        info = "rotation of fan {}".format(" ".join(parts))
        unit = "RPM"
        base = 1000
    elif sensor_type == "degrees c":
        key = "temp.{}".format(key_str)
        info = "Temperature of {}".format(" ".join(parts))
        unit = "C"
    elif sensor_type == "volts":
        key = "volts.{}".format(key_str)
        info = "Voltage of {}".format(" ".join(parts))
        unit = "V"
    elif sensor_type == "watts":
        key = "watts.{}".format(key_str)
        info = "Power usage of {}".format(" ".join(parts))
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
                    # limit dict,
                    limits = {key: l_val for key, l_val in zip(IPMI_LIMITS, [{"na": ""}.get(value, value) for value in parts[4:10]])}
                    result[key] = (float(parts[1]), info, unit, base, limits)
    return result


class _general(hm_classes.hm_module):
    def init_module(self):
        self.ipmi_result, self.ipmi_update = (None, None)
        self.it_command = False
        self.registered_mvs = set()
        if hasattr(self.main_proc, "register_vector_receiver") and global_config["TRACK_IPMI"]:
            self.check_ipmi_settings()
            self.popen = None
            self.main_proc.register_timer(self._update_ipmi, 20, instant=True)

    def _update_ipmi(self):
        if self.it_command:
            if self.popen:
                cur_res = self.popen.poll()
                if cur_res is not None:
                    self.ipmi_result = parse_ipmi(self.popen.stdout.read().split("\n"))
                    self.ipmi_update = time.time()
                    self.popen = None
            if not self.popen:
                self.popen = subprocess.Popen("{} sensor".format(self.it_command), shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

    def check_ipmi_settings(self):
        cmd_name = "ipmitool"
        self.it_command = process_tools.find_file(cmd_name)
        # print self.it_command
        if self.it_command:
            mp_command = process_tools.find_file("modprobe")
            self.log(
                "found {} at {}".format(
                    cmd_name,
                    self.it_command))
            self.log("trying to load ipmi kernel modules")
            for kern_mod in ["ipmi_si", "ipmi_devintf"]:
                cmd = "{} {}".format(mp_command, kern_mod)
                c_stat, c_out = commands.getstatusoutput(cmd)
                self.log(
                    "calling '{}' gave ({:d}): {}".format(
                        cmd,
                        c_stat,
                        c_out
                    )
                )
        else:
            self.log(
                "cmd {} not found".format(cmd_name),
                logging_tools.LOG_LEVEL_WARN)

    def init_machine_vector(self, mv):
        self.ipmi_result = False

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
        hm_classes.subprocess_struct.__init__(self, srv_com, ["{} -s '{}'".format(
            it_command,
            ipmi_com.Meta.command,
            )])

    def process(self):
        self.__ipmi_com.process(self)

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[ipmi] {}".format(what), level)


class _ipmi_sensor(object):
    class Meta:
        command = "sensor list"

    def process(self, bgp):
        for line in bgp.read().split("\n"):
            print line
            pass


class ipmi_sensor_command(hm_classes.hm_command):
    info_string = "get all IPMI sensors"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        for limit in IPMI_LONG_LIMITS:
            self.parser.add_argument("--{}".format(limit), dest=limit, type=str, default="na")

    def __call__(self, srv_com, cur_ns):
        if self.module.ipmi_result:
            key_list = sorted(self.module.ipmi_result.keys())
            if cur_ns.arguments:
                key = cur_ns.arguments[0]
                if key in key_list:
                    key_list = [key]
                else:
                    srv_com.set_result("IPMI sensor '{}' not found".format(key), server_command.SRV_REPLY_STATE_ERROR)
            if key_list:
                _b = srv_com.builder("sensor_list")
                for key in key_list:
                    value = self.module.ipmi_result[key]
                    _s = srv_com.builder("sensor")
                    _b.append(_s)
                    _s.attrib["key"] = key
                    _s.attrib["value"] = "{:.2f}".format(float(value[0]))
                    _s.attrib["info"] = "{}".format(value[1])
                    _s.attrib["unit"] = "{}".format(value[2])
                    _s.attrib["base"] = "{:d}".format(int(value[3]))
                    for key in IPMI_LIMITS:
                        if value[4].get(key, ""):
                            _s.attrib["limit_{}".format(key)] = value[4][key]
                srv_com["list"] = _b
        else:
            srv_com.set_result("no IPMI sensors found", server_command.SRV_REPLY_STATE_ERROR)

    def interpret(self, srv_com, cur_ns):
        l_dict = {}
        for key in IPMI_LONG_LIMITS:
            try:
                l_dict[key] = float(getattr(cur_ns, key))
            except:
                l_dict[key] = None
        s_list = srv_com.xpath(".//ns:sensor_list", smart_strings=False)
        if s_list:
            s_list = s_list[0]
            if cur_ns.arguments:
                el = s_list[0]
                cur_value = float(el.attrib["value"])
                ret_state = limits.nag_STATE_OK
                for t_name, log, t_state in [
                    ("lowern", False, limits.nag_STATE_CRITICAL),
                    ("lowerc", False, limits.nag_STATE_CRITICAL),
                    ("lowerw", False, limits.nag_STATE_WARNING),
                    ("upperw", True, limits.nag_STATE_WARNING),
                    ("upperc", True, limits.nag_STATE_CRITICAL),
                    ("uppern", True, limits.nag_STATE_CRITICAL),
                ]:
                    if l_dict[t_name] is not None:
                        if (log and cur_value >= l_dict[t_name]) or (not log and cur_value <= l_dict[t_name]):
                            ret_state = max(ret_state, t_state)
                return ret_state, "{}: {} is {:.2f} {}".format(
                    el.attrib["key"],
                    el.attrib["info"],
                    cur_value,
                    el.attrib["unit"],
                )
            else:
                # list mode
                keys = s_list.xpath(".//@key", smart_strings=False)
                out_list = logging_tools.new_form_list()
                for key in keys:
                    el = s_list.xpath("*[@key='{}']".format(key), smart_strings=False)[0]
                    v_list = [
                        logging_tools.form_entry(key, header="key"),
                        logging_tools.form_entry_right(el.attrib["value"], header="value"),
                        logging_tools.form_entry_right(el.attrib["base"], header="base"),
                        logging_tools.form_entry(el.attrib["unit"], header="unit"),
                        logging_tools.form_entry(el.attrib["info"], header="info"),
                    ]
                    for l_key in IPMI_LIMITS:
                        x_key = "limit_{}".format(l_key)
                        v_list.append(logging_tools.form_entry(el.attrib.get(x_key, "-"), header=x_key))
                    out_list.append(v_list)
                return limits.nag_STATE_OK, "found {}:\n{}".format(
                    logging_tools.get_plural("IPMI sensor", len(keys)),
                    unicode(out_list)
                )
        else:
            return limits.nag_STATE_WARNING, "no IPMI sensors found"
