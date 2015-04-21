# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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

from initat.host_monitoring import hm_classes, limits
from initat.tools import logging_tools
from initat.tools import server_command
import json
try:
    from initat.tools import drbd_tools
except ImportError:
    drbd_tools = None


class _general(hm_classes.hm_module):
    def init_module(self):
        self.__last_drbd_check = (-1, -1)
        if drbd_tools:
            self.drbd_config = drbd_tools.drbd_config()
        else:
            self.drbd_config = None


class drbd_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        if drbd_tools:
            self.module.drbd_config._parse_all()
            srv_com["drbd_status_format"] = "json"
            srv_com["drbd_status"] = json.dumps(self.module.drbd_config.get_config_dict())
        else:
            srv_com.set_result(
                "no drbd_tools found",
                server_command.SRV_REPLY_STATE_ERROR
            )

    def interpret(self, srv_com, cur_ns):
        if "drbd_status_format" in srv_com:
            return self._interpret(json.loads(srv_com["*drbd_status"]), cur_ns)
        else:
            return self._interpret(srv_com["drbd_status"], cur_ns)

    def interpret_old(self, result, cur_ns):
        drbd_conf = hm_classes.net_to_sys(result[3:])
        return self._interpret(drbd_conf, cur_ns)

    def _interpret(self, drbd_conf, cur_ns):
        if drbd_conf:
            if drbd_conf["status_present"] and drbd_conf["config_present"]:
                res_dict = drbd_conf["resources"]
                res_keys = sorted(res_dict.keys())
                state_dict = {
                    "total": res_keys
                }
                dev_states, ret_strs = ([], [])
                for key in res_keys:
                    loc_dict = res_dict[key]["localhost"]
                    # check connection_state
                    c_state = loc_dict["connection_state"].lower()
                    if c_state in ["connected"]:
                        dev_state = limits.nag_STATE_OK
                    elif c_state in [
                        "unconfigured", "syncsource", "synctarget", "wfconnection", "wfreportparams",
                        "pausedsyncs", "pausedsynct", "wfbitmaps", "wfbitmapt"
                    ]:
                        dev_state = limits.nag_STATE_WARNING
                    else:
                        dev_state = limits.nag_STATE_CRITICAL
                    # check states
                    if "state" in loc_dict:
                        state_dict.setdefault(loc_dict["state"][0], []).append(key)
                        for state in loc_dict["state"]:
                            if state not in ["primary", "secondary"]:
                                dev_state = max(dev_state, limits.nag_STATE_CRITICAL)
                    else:
                        dev_state = limits.nag_STATE_CRITICAL
                    if dev_state != limits.nag_STATE_OK:
                        # pprint.pprint(loc_dict)
                        ret_strs.append(
                            "{} ({}, protocol '{}'{}): cs {}, {}, ds {}".format(
                                key,
                                loc_dict["device"],
                                loc_dict.get("protocol", "???"),
                                ", {}%".format(loc_dict["resync_percentage"]) if "resync_percentage" in loc_dict else "",
                                c_state,
                                "/".join(loc_dict.get("state", ["???"])),
                                "/".join(loc_dict.get("data_state", ["???"]))
                            )
                        )
                    dev_states.append(dev_state)
                    # pprint.pprint(res_dict[key]["localhost"])
                # pprint.pprint(state_dict)
                ret_state = max(dev_states)
                return ret_state, "{}; {}".format(
                    ", ".join([logging_tools.get_plural(key, len(value)) for key, value in state_dict.iteritems()]),
                    ", ".join(ret_strs) if ret_strs else "everything ok"
                )
            else:
                ret_strs = []
                if not drbd_conf["status_present"]:
                    ret_state = limits.nag_STATE_WARNING
                    ret_strs.append("drbd status not present, module not loaded ?")
                elif not drbd_conf["config_present"]:
                    ret_state = limits.nag_STATE_CRITICAL
                    ret_strs.append("drbd config not present")
                return ret_state, ", ".join(ret_strs)
        else:
            return limits.nag_STATE_WARNING, "empty dbrd_config"
