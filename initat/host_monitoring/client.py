#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011,2012,2013 Andreas Lang-Nevyjel
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

import difflib
import net_tools
import os
import server_command

from initat.host_monitoring import limits
from initat.host_monitoring.config import global_config

def client_code():
    from initat.host_monitoring import modules
    # log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=)
    conn_str = "tcp://%s:%d" % (global_config["HOST"],
                                global_config["COM_PORT"])
    arg_stuff = global_config.get_argument_stuff()
    arg_list = arg_stuff["arg_list"]
    com_name = arg_list.pop(0)
    if com_name in modules.command_dict:
        srv_com = server_command.srv_command(command=com_name) # " ".join(arg_list))
        for src_key, dst_key in [("HOST"    , "host"),
                                 ("COM_PORT", "port")]:
            srv_com[dst_key] = global_config[src_key]
        com_struct = modules.command_dict[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError, what:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error parsing: %s" % (what[1]))
        else:
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg%d" % (arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            result = net_tools.zmq_connection(
                "%s:%d" % (global_config["IDENTITY_STRING"],
                           os.getpid()),
                timeout=global_config["TIMEOUT"]).add_connection(conn_str, srv_com)
            if result:
                error_result = result.xpath(None, ".//ns:result[@state != '0']")
                if error_result:
                    error_result = error_result[0]
                    ret_state, ret_str = (
                        int(error_result.attrib["state"]),
                        error_result.attrib["reply"])
                else:
                    ret_state, ret_str = com_struct.interpret(result, cur_ns)
            else:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "timeout")
    else:
        c_matches = difflib.get_close_matches(com_name, modules.command_dict.keys())
        if c_matches:
            cm_str = "close matches: %s" % (", ".join(c_matches))
        else:
            cm_str = "no matches found"
        ret_state, ret_str = (
            limits.nag_STATE_CRITICAL,
            "unknown command %s, %s" % (com_name, cm_str)
        )
    print ret_str
    return ret_state

