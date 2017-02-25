# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" host-monitoring client """

import os

from initat.host_monitoring import limits
from initat.host_monitoring.client_enums import icswServiceEnum
from initat.host_monitoring.host_monitoring_struct import ExtReturn
from initat.icsw.service.instance import InstanceXML
from initat.tools import net_tools, server_command, logging_tools


def ClientCode(global_config):
    from initat.host_monitoring.modules import local_mc
    from initat.debug import ICSW_DEBUG_MODE
    if ICSW_DEBUG_MODE:
        # dummy logger of module loader
        def dummy_log(what, log_level=logging_tools.LOG_LEVEL_OK):
            print("{} {}".format(logging_tools.get_log_level_str(log_level), what))

        local_mc.set_log_command(dummy_log)
    local_mc.build_structure(None, None)
    conn_str = "tcp://{}:{:d}".format(
        global_config["HOST"],
        global_config["COMMAND_PORT"]
    )
    arg_list = global_config["ARGUMENTS"]
    com_name = arg_list.pop(0)
    if com_name in local_mc:
        srv_com = server_command.srv_command(command=com_name)
        for src_key, dst_key in [
            ("HOST", "host"),
            ("COMMAND_PORT", "port")
        ]:
            srv_com[dst_key] = global_config[src_key]
        com_struct = local_mc[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError as what:
            ret = ExtReturn(limits.mon_STATE_CRITICAL, "error parsing: {}".format(what.args[1]))
        else:
            # see also struct.py in collrelay
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg{:d}".format(arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            for key, value in vars(cur_ns).items():
                srv_com["namespace:{}".format(key)] = value
            result = net_tools.ZMQConnection(
                "{}:{:d}".format(
                    global_config["IDENTITY_STRING"],
                    os.getpid()
                ),
                timeout=global_config["TIMEOUT"],
            ).add_connection(
                conn_str,
                srv_com,
                immediate=True,
            )
            if result:
                if global_config["COMMAND_PORT"] == InstanceXML(quiet=True).get_port_dict(
                    icswServiceEnum.host_monitoring,
                    command=True
                ):
                    error_result = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
                    if error_result:
                        error_result = error_result[0]
                        ret = ExtReturn(
                            int(error_result.attrib["state"]),
                            error_result.attrib["reply"]
                        )
                    else:
                        if hasattr(com_struct, "interpret"):
                            ret = ExtReturn.get_ext_return(com_struct.interpret(result, cur_ns))
                        else:
                            _result = result.xpath(".//ns:result", smart_strings=False)[0]
                            ret = ExtReturn(
                                server_command.srv_reply_to_nag_state(int(_result.attrib["state"])),
                                result.attrib["reply"]
                            )
                else:
                    ret_str, ret_state = result.get_log_tuple()
                    ret = ExtReturn(server_command.srv_reply_to_nag_state(ret_state), ret_str)
            else:
                ret = ExtReturn(limits.mon_STATE_CRITICAL, "timeout")
    else:
        import difflib
        c_matches = difflib.get_close_matches(com_name, list(local_mc.keys()))
        if c_matches:
            cm_str = "close matches: {}".format(", ".join(c_matches))
        else:
            cm_str = "no matches found"
        ret = ExtReturn(
            limits.mon_STATE_CRITICAL,
            "unknown command {}, {}".format(com_name, cm_str)
        )
    if ret.ascii_chunk:
        print(
            "Ignoring ascii_chunk with {:d} bytes".format(
                len(ret.ascii_chunk)
            )
        )
    # output
    print(ret.ret_str)
    return ret.ret_state
