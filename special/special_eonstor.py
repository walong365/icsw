#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009 Andreas Lang-Nevyjel, init.at
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
try:
    import ipc_comtools
except ImportError:
    ipc_comtools = None
try:
    import snmp_relay_schemes
except ImportError:
    snmp_relay_schemes = None

def handle(s_check, host, dc, mach_log_com, valid_ip, **args):
    mach_log_com("Starting special eonstor")
    sc_array = []
    if not ipc_comtools:
        mach_log_com("no ipc_comtools found",
                     logging_tools.LOG_LEVEL_CRITICAL)
    elif not snmp_relay_schemes:
        mach_log_com("no snmp_relay_schemes found",
                     logging_tools.LOG_LEVEL_CRITICAL)
    else:
        try:
            act_state, info_dict = ipc_comtools.send_and_receive(valid_ip,
                                                                 "eonstor_get_counter",
                                                                 decode=True,
                                                                 ipc_key="/var/run/snmp_relay_key.ipc",
                                                                 snmp_community="public",
                                                                 mode="snmp-relay")
        except:
            mach_log_com("error getting eonstor_status from %s: %s" % (valid_ip,
                                                                       process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
        else:
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
                        act_com = "eonstor_%s_info --raw %d" % (env_dict_name,
                                                                idx)
                        try:
                            act_state, state_obj = ipc_comtools.send_and_receive(valid_ip,
                                                                                 act_com,
                                                                                 decode=True,
                                                                                 ipc_key="/var/run/snmp_relay_key.ipc",
                                                                                 mode="snmp-relay")
                        except:
                            mach_log_com("error sending command '%s': %s" % (act_com,
                                                                             process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_CRITICAL)
                        else:
                            if act_state:
                                mach_log_com("error command %s gave (%d): %s" % (act_com,
                                                                                 act_state,
                                                                                 state_obj),
                                             logging_tools.LOG_LEVEL_ERROR)
                            else:
                                if env_dict_name == "ups":
                                    # check for inactive psus
                                    if state_obj.state & 128:
                                        mach_log_com("disabling psu with idx %d because not present" % (idx),
                                                     logging_tools.LOG_LEVEL_ERROR)
                                        add_check = False
                                elif env_dict_name == "bbu":
                                    if state_obj.state & 128:
                                        mach_log_com("disabling bbu with idx %d because not present" % (idx),
                                                     logging_tools.LOG_LEVEL_ERROR)
                                        add_check = False
                    if add_check:
                        if not nag_name.lower().startswith(env_dict_name):
                            nag_name = "%s %s" % (env_dict_name, nag_name)
                        sc_array.append((nag_name,
                                         ["eonstor_%s_info" % (env_dict_name), "%d" % (idx)]))
        # rewrite sc_array to include community and version
        sc_array = [(name, ["", ""] + var_list) for name, var_list in sc_array]
    mach_log_com("sc_array has %s" % (logging_tools.get_plural("entry", len(sc_array))))
    return sc_array

if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    