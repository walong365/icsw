# Copyright (C) 2008-2009,2012-2015 Andreas Lang-Nevyjel init.at
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

import commands
import re
import time

from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools, process_tools


class _general(hm_classes.hm_module):
    def init_module(self):
        self._find_ipsec_command()

    def _find_ipsec_command(self):
        self.__ipsec_command = process_tools.find_file("ipsec")

    def _exec_command(self, com):
        if com.startswith("."):
            if self.__ipsec_command:
                com = "{} {}".format(self.__ipsec_command, com[1:])
            else:
                self.log(
                    "no ipsec command found",
                    logging_tools.LOG_LEVEL_ERROR
                )
                com, out = (None, "")
        if com:
            c_stat, out = commands.getstatusoutput(com)
            if c_stat and out:
                self.log(
                    "cannot execute {} ({:d}): {}".format(
                        com, c_stat, out or "<NO OUTPUT>"
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                out = ""
        return out.split("\n")

    def _update_ipsec_status(self):
        # for strongswan
        act_out = self._exec_command(". statusall")
        con_dict = {}
        if act_out:
            first_line = act_out[0]
            if first_line.lower().count("strongswan 5"):
                con_dict["lines"] = act_out
            else:
                for line in act_out:
                    parts = line.strip().split()
                    if len(parts) > 1:
                        parts.pop(0)
                        first_key = parts.pop(0)
                        if first_key.startswith('"'):
                            # connection related
                            con_key = first_key[1:-2]
                            con_dict.setdefault(
                                con_key, {
                                    "flags": [],
                                    "keys": {},
                                    "sa_dict": {}
                                }
                            )
                            parts = [part.strip() for part in (" ".join(parts)).split(";") if part.strip()]
                            for part in parts:
                                if part.count(": "):
                                    key, value = part.split(": ", 1)
                                    if key.endswith(" proposal") and value.replace("N/A", "N_A").count("/") == 2:
                                        value = [sub_value.replace("N_A", "N/A") for sub_value in value.replace("N/A", "N_A").split("/")]
                                    elif key == "prio" and value.count(",") == 1:
                                        value = value.split(",")
                                    con_dict[con_key]["keys"][key] = value
                                else:
                                    con_dict[con_key]["flags"].append(part)
                        elif first_key.startswith("#"):
                            sa_key = int(first_key[1:-1])
                            con_key = parts.pop(0)
                            if con_key not in ["pending"]:
                                if con_key.count(":"):
                                    con_key, port_num = con_key.split(":")
                                else:
                                    port_num = "0"
                                con_key, port_num = (con_key[1:-1], int(port_num))
                                parts = [part.strip() for part in (" ".join(parts)).split(";") if part.strip()]
                                con_dict[con_key]["sa_dict"].setdefault(("con_{:d}.{:d}".format(sa_key, port_num)), []).extend(parts)
        return con_dict

    def init_machine_vector(self, mv):
        self.__ipsec_re = re.compile("^\s*(?P<conn_name>\S+){(?P<conn_id>\d+)}:\s+.*\s+(?P<bytes_in>\d+)\s+bytes_i.*\s+(?P<bytes_out>\d+)\s+bytes_o.*$")
        self.__ipsec_conns = {}

    def update_machine_vector(self, mv):
        if self.__ipsec_command:
            _lines = [(line, self.__ipsec_re.match(line)) for line in self._exec_command(". statusall") if line.count("bytes_i")]
            _found = set()
            for _line, _res in _lines:
                if _res:
                    _gd = _res.groupdict()
                    _cn = _gd["conn_name"]
                    _found.add(_cn)
                    if _cn not in self.__ipsec_conns:
                        self.log("registered IPSec connection {}".format(_cn))
                        self.__ipsec_conns[_cn] = ipsec_con(_cn, mv)
                    self.__ipsec_conns[_cn].feed(mv, int(_gd["bytes_in"]), int(_gd["bytes_out"]))
                else:
                    self.log("cannot parse line '{}'".format(line), logging_tools.LOG_LEVEL_WARN)
            _to_del = set(self.__ipsec_conns.keys()) - _found
            for _del in _to_del:
                self.log("unregistered IPSec connection {}".format(_del))
                self.__ipsec_conns[_del].close(mv)
                del self.__ipsec_conns[_del]


class ipsec_con(object):
    def __init__(self, name, mv):
        self.name = name
        mv.register_entry(self.key("in"), 0, "bytes received for connection {}".format(self.name), "Byte/s", 1024)
        mv.register_entry(self.key("out"), 0, "bytes transmitted for connection {}".format(self.name), "Byte/s", 1024)
        self.__in, self.__out = (0, 0)
        self.__last = None

    def feed(self, mv, _in, _out):
        cur_time = time.time()
        if self.__last:
            diff_time = max(1, cur_time - self.__last)
            mv[self.key("in")] = (max(0, _in - self.__in) / diff_time)
            mv[self.key("out")] = (max(0, _out - self.__out) / diff_time)
        self.__last = cur_time
        self.__in, self.__out = (_in, _out)

    def key(self, key):
        return "net.ipsec.{}.{}".format(self.name, key)

    def close(self, mv):
        mv.unregister_entry(self.key("in"))
        mv.unregister_entry(self.key("out"))


class ipsec_tunnel(object):
    def __init__(self, t_id):
        self.t_id = t_id
        self.__parts = []
        self.__installed = False
        self.__rekeying = False

    def feed(self, _parts):
        _line = " ".join(_parts)
        if _line.count("INSTALLED"):
            self.__installed = True
        if _line.count("REKEYING"):
            self.__rekeying = True
        self.__parts.append(_line)
        # print "*", self.t_id, self.__parts

    def is_ok(self):
        return self.__installed

    @property
    def rekeying(self):
        return self.__rekeying

    @property
    def installed(self):
        return self.__installed


class c_con(object):
    # ipsec client connection
    def __init__(self, name):
        self.name = name
        self.__master_connection = None
        self.__con_dict = {}
        self.__feedcount = 0
        self.__tunnels = {}

    @property
    def con_dict(self):
        return self.__con_dict

    def get_master(self):
        if self.__master_connection:
            return self.__master_connection.get_master()
        else:
            return self

    def feed(self, _parts, _prev_con):
        _mode = _parts[0][:-1]
        if _mode == "child" and self.__feedcount == 0:
            # this connection lives inside another connection
            self.__master_connection = _prev_con.get_master()
        self.__feedcount += 1
        if _mode in ["local", "remote"]:
            self.__con_dict[_mode] = _parts[1:]
        elif _mode in ["child"]:
            self.__con_dict.setdefault(_mode, []).append(_parts[1:])
        else:
            self.__con_dict.setdefault("info", []).append(_parts)

    def feed_tunnel(self, _id, _parts):
        if _id not in self.__tunnels:
            self.__tunnels[_id] = ipsec_tunnel(_id)
        self.__tunnels[_id].feed(_parts)

    def tunnel_installed(self):
        if self.__tunnels:
            return any([_tunnel.installed for _tunnel in self.__tunnels.itervalues()])
        else:
            # no tunnels
            return False

    def tunnel_rekeying(self):
        if self.__tunnels:
            return any([_tunnel.rekeying for _tunnel in self.__tunnels.itervalues()])
        else:
            # no tunnels
            return False


class ipsec_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        srv_com["ipsec_status"] = self.module._update_ipsec_status()

    def interpret(self, srv_com, cur_ns):
        con_dict = srv_com["ipsec_status"]
        return self._interpret(con_dict, cur_ns)

    def interpret_old(self, result, parsed_coms):
        con_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(con_dict, parsed_coms)

    def _interpret(self, con_dict, cur_ns):
        if cur_ns.arguments:
            first_arg = cur_ns.arguments[0]
        else:
            first_arg = None
        if "lines" in con_dict:
            _con_dict = {}
            # new version
            line_mode = "v"
            for line_num, line in enumerate(con_dict["lines"]):
                if line_num == 0:
                    line_mode = "v"
                elif line.startswith("Listening"):
                    line_mode = "l"
                elif line.startswith("Connections:"):
                    cur_con = None
                    line_mode = "c"
                elif line.startswith("Security Ass"):
                    cur_con = None
                    line_mode = "s"
                else:
                    if line_mode in ["c", "s"]:
                        _parts = line.strip().split()
                        if line_mode == "c":
                            conn_name = _parts.pop(0)[:-1]
                            if not cur_con:
                                prev_con = cur_con
                                cur_con = c_con(conn_name)
                                _con_dict[conn_name] = cur_con
                            elif cur_con.name != conn_name:
                                prev_con = cur_con
                                cur_con = c_con(conn_name)
                                _con_dict[conn_name] = cur_con
                            cur_con.feed(_parts, prev_con)
                        else:
                            if line.count("{"):
                                conn_id = _parts.pop(0)
                                conn_name = conn_id.split("{")[0]
                                tunnel_id = conn_id.split("{")[1].split("}")[0]
                                _con_dict[conn_name].feed_tunnel(tunnel_id, _parts)
            if not first_arg:
                if _con_dict:
                    ret_state, ret_list = (limits.nag_STATE_OK, [])
                    for con_name in sorted(_con_dict):
                        if _con_dict[con_name].tunnel_rekeying():
                            ret_list.append("{} is rekeying".format(con_name))
                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                        elif _con_dict[con_name].tunnel_installed():
                            ret_list.append("{} ok".format(con_name))
                        else:
                            ret_list.append("no installed tunnel for {}".format(con_name))
                            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    return ret_state, ", ".join(ret_list)
                else:
                    return limits.nag_STATE_WARNING, "no connections defined"
            else:
                if first_arg in _con_dict:
                    _conn = _con_dict[first_arg]
                    if _conn.tunnel_rekeying():
                        return limits.nag_STATE_WARNING, "connection {} is defined but tunnel is rekeying".format(_conn.name)
                    elif _conn.tunnel_installed():
                        return limits.nag_STATE_OK, "connection {} is defined and tunnel is installed".format(_conn.name)
                    else:
                        return limits.nag_STATE_CRITICAL, "connection {} is defined but no tunnel installed".format(_conn.name)
                else:
                    return limits.nag_STATE_CRITICAL, "connection '{}' not found (defined: {})".format(
                        first_arg,
                        ", ".join(sorted(_con_dict)) or "none"
                    )
        else:
            # old strongswans
            if not first_arg:
                # overview
                if con_dict:
                    ret_state, ret_list = (limits.nag_STATE_OK, [])
                    for con_name in sorted(con_dict):
                        if "erouted" in con_dict[con_name]["flags"]:
                            ret_list.append("{} ok".format(con_name))
                        else:
                            ret_list.append("{} is not erouted".format(con_name))
                            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    return ret_state, ", ".join(ret_list)
                else:
                    return limits.nag_STATE_WARNING, "no connections defined"
            elif first_arg in con_dict:
                con_stuff = con_dict[first_arg]
                ret_state, ret_list = (limits.nag_STATE_OK, [])
                if "erouted" in con_stuff["flags"]:
                    ret_list.append("is erouted")
                    for key in con_stuff["keys"]:
                        if key.endswith("proposal"):
                            ret_list.append("{}: {}".format(key, "/".join(con_stuff["keys"][key])))
                else:
                    ret_list.append("is not erouted")
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                return ret_state, "connection {}: {}".format(
                    first_arg,
                    ", ".join(ret_list)
                )
            else:
                return limits.nag_STATE_CRITICAL, "error connection '{}' not found (defined: {})".format(
                    first_arg,
                    ", ".join(sorted(con_dict)) or "none"
                )
