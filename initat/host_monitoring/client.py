# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, with 0MQ and twisted support """

from initat.host_monitoring import limits
import difflib
import net_tools
import os
import server_command

def client_code(global_config):
    from initat.host_monitoring import modules
    if global_config["VERBOSE"] > 1:
        print "{:d} import errors:".format(len(modules.IMPORT_ERRORS))
        for mod, com, _str in modules.IMPORT_ERRORS:
            print "{:<30s} {:<20s} {}".format(com, mod.split(".")[-1], _str)
    conn_str = "tcp://{}:{:d}".format(
        global_config["HOST"],
        global_config["COM_PORT"])
    arg_stuff = global_config.get_argument_stuff()
    arg_list = arg_stuff["arg_list"]
    com_name = arg_list.pop(0)
    if com_name in modules.command_dict:
        srv_com = server_command.srv_command(command=com_name)
        for src_key, dst_key in [("HOST"    , "host"),
                                 ("COM_PORT", "port")]:
            srv_com[dst_key] = global_config[src_key]
        com_struct = modules.command_dict[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError, what:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error parsing: {}".format(what[1]))
        else:
            # see also struct.py in collrelay
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg{:d}".format(arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            for key, value in vars(cur_ns).iteritems():
                srv_com["namespace:{}".format(key)] = value
            result = net_tools.zmq_connection(
                "{}:{:d}".format(
                    global_config["IDENTITY_STRING"],
                    os.getpid()),
                timeout=global_config["TIMEOUT"]).add_connection(conn_str, srv_com)
            if result:
                if global_config["COM_PORT"] == 2001:
                    error_result = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
                    if error_result:
                        error_result = error_result[0]
                        ret_state, ret_str = (
                            int(error_result.attrib["state"]),
                            error_result.attrib["reply"])
                    else:
                        if hasattr(com_struct, "interpret"):
                            ret_state, ret_str = com_struct.interpret(result, cur_ns)
                        else:
                            _result = result.xpath(".//ns:result", smart_strings=False)[0]
                            ret_str = _result.attrib["reply"]
                            ret_state = server_command.srv_reply_to_nag_state(int(_result.attrib["state"]))
                else:
                    ret_str, ret_state = result.get_log_tuple()
                    if ret_state in [server_command.SRV_REPLY_STATE_CRITICAL, server_command.SRV_REPLY_STATE_ERROR, server_command.SRV_REPLY_STATE_UNSET]:
                        ret_state = limits.nag_STATE_CRITICAL
                    elif ret_state in [server_command.SRV_REPLY_STATE_WARN]:
                        ret_state = limits.nag_STATE_WARNING
                    else:
                        ret_state = limits.nag_STATE_OK
            else:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "timeout")
    else:
        c_matches = difflib.get_close_matches(com_name, modules.command_dict.keys())
        if c_matches:
            cm_str = "close matches: {}".format(", ".join(c_matches))
        else:
            cm_str = "no matches found"
        ret_state, ret_str = (
            limits.nag_STATE_CRITICAL,
            "unknown command {}, {}".format(com_name, cm_str)
        )
    print ret_str
    return ret_state

