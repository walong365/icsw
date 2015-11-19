# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" checks for ips (AAC) RAID controller """

import base64
import bz2
import marshal

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct
from initat.tools import logging_tools, server_command


def _split_config_line(line):
    key, val = line.split(":", 1)
    key = key.lower().strip().replace(" ", "_")
    val = val.strip()
    if val.isdigit():
        val = int(val)
    elif val.lower() == "enabled":
        val = True
    elif val.lower() == "disabled":
        val = False
    return key, val


class ctrl_type_ips(ctrl_type):
    class Meta:
        name = "ips"
        exec_name = "arcconf"
        description = "Adapatec AAC RAID Controller"

    def get_exec_list(self, ctrl_ids=[]):
        ctrl_ids = ctrl_ids or self._dict.keys()
        return [("{} getconfig {:d} AL".format(self._check_exec, ctrl_id),
                 "config", ctrl_id) for ctrl_id in ctrl_ids] + \
               [("{} getstatus {:d}".format(self._check_exec, ctrl_id),
                 "status", ctrl_id) for ctrl_id in ctrl_ids]

    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" getversion", post="strip")
        if not cur_stat:
            num_ctrl = len([True for line in cur_lines if line.lower().count("controller #")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    ctrl_stuff = {"last_al_lines": []}
                    # get config for every controller
                    _c_stat, c_result = self.exec_command(" getconfig %d AD" % (ctrl_num))
                    ctrl_stuff["config"] = {}
                    for key, val in [_split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self._dict[ctrl_num] = ctrl_stuff

    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com.set_result(
                "no controller found",
                server_command.SRV_REPLY_STATE_ERROR
            )
            return False

    def process(self, ccs):
        _com_line, com_type, ctrl_num = ccs.run_info["command"]
        if com_type == "config":
            ctrl_config = {
                "logical": {},
                "array": {},
                "channel": {},
                "physical": [],
                "controller": {}
            }
            act_part, prev_line = ("", "")
            for line in ccs.read().split("\n"):
                ls = line.strip()
                lsl = ls.lower()
                # get key and value, space is important here
                if lsl.count(" :"):
                    key, value = [entry.strip() for entry in lsl.split(" :", 1)]
                else:
                    key, value = (None, None)
                if prev_line.startswith("-" * 10) and line.endswith("information"):
                    act_part = " ".join(line.split()[0:2]).lower().replace(" ", "_").replace("drive", "device")
                elif line.lower().startswith("command complet") or line.startswith("-" * 10):
                    pass
                else:
                    if act_part == "logical_device":
                        if line.lower().count("logical device number") or line.lower().count("logical drive number"):
                            act_log_drv_num = int(line.split()[-1])
                            ctrl_config["logical"][act_log_drv_num] = {}
                        elif line.lower().strip().startswith("logical device name"):
                            array_name = ls.split()[1]
                            ctrl_config["array"][array_name] = " ".join(line.lower().strip().split()[2:])
                        elif line.count(":"):
                            key, val = _split_config_line(line)
                            ctrl_config["logical"][act_log_drv_num][key] = val
                    elif act_part == "physical_device":
                        if lsl.startswith("channel #"):
                            act_channel_num = int(lsl[-2])
                            ctrl_config["channel"][act_channel_num] = {}
                            act_scsi_stuff = None
                        elif lsl.startswith("device #"):
                            act_scsi_id = int(lsl[-1])
                            act_channel_num = -1
                            act_scsi_stuff = {}
                        elif lsl.startswith("reported channel,device"):
                            # key should be set here
                            if key.endswith(")"):
                                key, value = (key.split("(", 1)[0],
                                              value.split("(", 1)[0])
                            act_scsi_id = int(value.split(",")[-1])
                            if act_channel_num == -1:
                                act_channel_num = int(value.split(",")[-2].split()[-1])
                                ctrl_config["channel"][act_channel_num] = {}
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = key
                            act_scsi_stuff["channel"] = act_channel_num
                            act_scsi_stuff["scsi_id"] = act_scsi_id
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = act_scsi_stuff
                            ctrl_config["physical"].append(act_scsi_stuff)
                        elif line.count(":"):
                            if act_scsi_stuff is not None:
                                key, val = _split_config_line(line)
                                act_scsi_stuff[key] = val
                    elif act_part == "controller_information":
                        if key:
                            ctrl_config["controller"][key] = value
                    # print act_part, linea
                prev_line = line
            self._dict[ctrl_num].update(ctrl_config)
        elif com_type == "status":
            task_list = []
            act_task = None
            for line in ccs.read().split("\n"):
                lline = line.lower()
                if lline.startswith("logical device task"):
                    act_task = {"header": lline}
                elif act_task:
                    if lline.count(":"):
                        key, value = [part.strip().lower() for part in lline.split(":", 1)]
                        act_task[key] = value
                if not lline.strip():
                    if act_task:
                        task_list.append(act_task)
                        act_task = None
            self._dict[ctrl_num]["config"]["task_list"] = task_list
        if ctrl_num == max(self._dict.keys()) and com_type == "status":
            ccs.srv_com["ips_dict_base64"] = base64.b64encode(bz2.compress(marshal.dumps(self._dict)))

    def _interpret(self, aac_dict, cur_ns):
        num_warn, num_error = (0, 0)
        ret_f = []
        for c_num, c_stuff in aac_dict.iteritems():
            # pprint.pprint(c_stuff)
            act_field = []
            if c_stuff["logical"]:
                log_field = []
                for l_num, l_stuff in c_stuff["logical"].iteritems():
                    sold_name = "status_of_logical_device" if "status_of_logical_device" in l_stuff else "status_of_logical_drive"
                    log_field.append(
                        "ld%d: %s (%s, %s)" % (
                            l_num,
                            logging_tools.get_size_str(int(l_stuff["size"].split()[0]) * 1000000, divider=1000).strip(),
                            "RAID%s" % (l_stuff["raid_level"]) if "raid_level" in l_stuff else "RAID?",
                            l_stuff[sold_name].lower()
                        )
                    )
                    if l_stuff[sold_name].lower() in ["degraded"]:
                        num_error += 1
                    elif l_stuff[sold_name].lower() not in ["optimal", "okay"]:
                        num_warn += 1
                act_field.extend(log_field)
            if c_stuff["physical"]:
                phys_dict = {}
                for phys in c_stuff["physical"]:
                    if "size" in phys:
                        s_state = phys["state"].lower()
                        if s_state == "sby":
                            # ignore empty standby bays
                            pass
                        else:
                            if s_state not in ["onl", "hsp", "optimal", "online"]:
                                num_error += 1
                            con_info = ""
                            if "reported_location" in phys:
                                cd_info = phys["reported_location"].split(",")
                                if len(cd_info) == 2:
                                    try:
                                        con_info = "c%d.%d" % (int(cd_info[0].split()[-1]),
                                                               int(cd_info[1].split()[-1]))
                                    except:
                                        con_info = "error parsing con_info %s" % (phys["reported_location"])
                            phys_dict.setdefault(
                                s_state, []
                            ).append(
                                "c%d/id%d%s" % (
                                    phys["channel"],
                                    phys["scsi_id"],
                                    " (%s)" % (con_info) if con_info else ""
                                )
                            )
                act_field.extend(["%s: %s" % (key, ",".join(phys_dict[key])) for key in sorted(phys_dict.keys())])
            if "task_list" in c_stuff:
                for act_task in c_stuff["task_list"]:
                    act_field.append(
                        "%s on logical device %s: %s, %d %%" % (
                            act_task.get("header", "unknown task"),
                            act_task.get("logical device", "?"),
                            act_task.get("current operation", "unknown op"),
                            int(act_task.get("percentage complete", "0"))
                        )
                    )
            # check controller warnings
            ctrl_field = []
            if c_stuff["controller"]:
                ctrl_dict = c_stuff["controller"]
                c_stat = ctrl_dict.get("controller status", "")
                if c_stat:
                    ctrl_field.append("status %s" % (c_stat))
                    if c_stat.lower() not in ["optimal", "okay"]:
                        num_error += 1
                ov_temp = ctrl_dict.get("over temperature", "")
                if ov_temp:
                    if ov_temp == "yes":
                        num_error += 1
                        ctrl_field.append("over temperature")
            ret_f.append(
                "c%d (%s): %s" % (
                    c_num,
                    ", ".join(ctrl_field) or "---",
                    ", ".join(act_field)
                )
            )
            if num_error:
                ret_state = limits.nag_STATE_CRITICAL
            elif num_warn:
                ret_state = limits.nag_STATE_WARNING
            else:
                ret_state = limits.nag_STATE_OK
        if not ret_f:
            return limits.nag_STATE_WARNING, "no controller information found"
        else:
            return ret_state, "; ".join(ret_f)


class aac_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)

    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("ips")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("ips").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("ips"), ctrl_list)

    def interpret(self, srv_com, cur_ns):
        return self._interpret(marshal.loads(bz2.decompress(base64.b64decode(srv_com["ips_dict_base64"].text))), cur_ns)

    def interpret_old(self, result, cur_ns):
        aac_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(aac_dict, cur_ns)

    def _interpret(self, aac_dict, cur_ns):
        return ctrl_type.ctrl("ips")._interpret(aac_dict, cur_ns)
