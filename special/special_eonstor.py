#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2012 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
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
""" special task for configuring eonstor checks """

import sys
import pprint
import re
import logging_tools
import pyipc
import struct
import os
import process_tools
import server_command
from host_monitoring import ipc_comtools
try:
    import snmp_relay_schemes
except ImportError:
    snmp_relay_schemes = None

def handle(s_check, host, dc, build_proc, valid_ip, **kwargs):
    build_proc.mach_log("Starting special eonstor")
    sc_array = []
    if not snmp_relay_schemes:
        build_proc.mach_log("no snmp_relay_schemes found",
                            logging_tools.LOG_LEVEL_CRITICAL)
    else:
        try:
            srv_reply = ipc_comtools.send_and_receive_zmq(valid_ip,
                                                          "eonstor_get_counter",
                                                          server="snmp_relay",
                                                          zmq_context=build_proc.zmq_context,
                                                          #ipc_key="/var/run/snmp_relay_key.ipc",
                                                          snmp_version="1",
                                                          snmp_community="public")
        except:
            build_proc.mach_log("error getting eonstor_status from %s: %s" % (valid_ip,
                                                                              process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_CRITICAL)
        else:
            info_dict = server_command.srv_command.tree_to_dict(srv_reply.xpath(".//ns:eonstor_info")[0])
            # disks
            for disk_id in sorted(info_dict.get("disc_ids", [])):
                sc_array.append(("Disc %2d" % (disk_id), ["eonstor_disc_info", "%d" % (disk_id)]))
            # lds
            for ld_id in sorted(info_dict.get("ld_ids", [])):
                sc_array.append(("LD %2d" % (ld_id), ["eonstor_ld_info", "%d" % (ld_id)]))
            # env_dicts
            for env_dict_name in sorted(info_dict.get("ent_dict", {}).keys()):
                env_dict = info_dict["ent_dict"][env_dict_name]
                for idx in sorted(env_dict.keys()):
                    nag_name = env_dict[idx]
                    add_check = True
                    # get info for certain environment types
                    if env_dict_name in ["ups", "bbu"]:
                        act_com = "eonstor_%s_info" % (env_dict_name)
                        try:
                            srv_reply = ipc_comtools.send_and_receive_zmq(valid_ip,
                                                                          act_com,
                                                                          "%d" % (idx),
                                                                          server="snmp_relay",
                                                                          zmq_context=build_proc.zmq_context,
                                                                          #ipc_key="/var/run/snmp_relay_key.ipc",
                                                                          snmp_version="1",
                                                                          snmp_community="public")
                        except:
                            build_proc.mach_log("error sending command '%s': %s" % (act_com,
                                                                                    process_tools.get_except_info()),
                                                logging_tools.LOG_LEVEL_CRITICAL)
                        else:
                            print unicode(srv_reply)
                            if act_state:
                                build_proc.mach_log("error command %s gave (%d): %s" % (act_com,
                                                                                        act_state,
                                                                                        state_obj),
                                             logging_tools.LOG_LEVEL_ERROR)
                            else:
                                if env_dict_name == "ups":
                                    # check for inactive psus
                                    if state_obj.state & 128:
                                        build_proc.mach_log("disabling psu with idx %d because not present" % (idx),
                                                     logging_tools.LOG_LEVEL_ERROR)
                                        add_check = False
                                elif env_dict_name == "bbu":
                                    if state_obj.state & 128:
                                        build_proc.mach_log("disabling bbu with idx %d because not present" % (idx),
                                                     logging_tools.LOG_LEVEL_ERROR)
                                        add_check = False
                    if add_check:
                        if not nag_name.lower().startswith(env_dict_name):
                            nag_name = "%s %s" % (env_dict_name, nag_name)
                        sc_array.append((nag_name,
                                         ["eonstor_%s_info" % (env_dict_name), "%d" % (idx)]))
        # rewrite sc_array to include community and version
        sc_array = [(name, ["", ""] + var_list) for name, var_list in sc_array]
    build_proc.mach_log("sc_array has %s" % (logging_tools.get_plural("entry", len(sc_array))))
    return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    
