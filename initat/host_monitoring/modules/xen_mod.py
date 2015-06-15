#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2012 Andreas Lang-Nevyjel init.at
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

import sys
import commands
import os
import os.path

from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools

try:
    import xen_tools
except:
    xen_tools = None

HOST_KEY = "/tool/host"


class _general(hm_classes.hm_module):
    def read_host_name(self, ret_dict, logger):
        xsr_bins = ["/usr/bin/xenstore-read", "/bin/xenstore-read"]
        # search xenstore-read binary
        any_found = False
        for xsr_bin in xsr_bins:
            if os.path.isfile(xsr_bin):
                any_found = True
                host_name = self._exec_command("%s %s" % (xsr_bin, HOST_KEY), logger)
                if host_name[0]:
                    ret_dict["xen_host"] = host_name[0]
                else:
                    ret_dict["errors"].append("xenstore key %s not accessible" % (HOST_KEY))
                break
        if not any_found:
            ret_dict["errors"].append("no xenstore-read cmd found")

    def get_host_info(self, ret_dict, logger):
        if xen_tools:
            xen_info = xen_tools.xen_info_object(self.log)
            ret_dict["running_domains"] = [x_obj["name"] for x_obj in xen_info.get_running_domains()]
        else:
            ret_dict["errors"].append("xen_tools not found")

    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
                    

class xen_type_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ret_dict = {"xen_bus_found": False,
                    "xen_type": "",
                    "errors": []}
        if os.path.isdir("/sys/bus/xen"):
            # hack
            ret_dict["xen_bus_found"] = True
            if os.path.isdir("/var/lib/xenstored"):
                ret_dict["xen_type"] = "host"
                try:
                    self.module_info.get_host_info(ret_dict, self.logger)
                except:
                    # maybe we are a monitoring host with xen fully installed but not running
                    ret_dict["xen_type"] = "guest"
                    # read host name
                    self.module_info.read_host_name(ret_dict, self.logger)
            else:
                ret_dict["xen_type"] = "guest"
                # read host name
                self.module_info.read_host_name(ret_dict, self.logger)
        srv_com["xen_type"] = ret_dict

    def interpret(self, srv_com, cur_ns):
        return self._interpret(srv_com["xen_type"], cur_ns)

    def interpret_old(self, result, cur_ns):
        r_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(r_dict, cur_ns)

    def _interpret(self, r_dict, cur_ns):
        ret_state, out_f = (limits.nag_STATE_OK, [])
        if r_dict["xen_type"]:
            out_f.append("is a xen-%s" % (r_dict["xen_type"]))
            if r_dict["xen_type"] == "host":
                if "running_domains" in r_dict:
                    out_f.append(logging_tools.get_plural("running domain", len(r_dict["running_domains"])))
            elif r_dict["xen_type"] == "guest":
                if "xen_host" in r_dict:
                    out_f.append("host is %s" % (r_dict["xen_host"]))
        else:
            out_f.append("host is neither a xen-guest nor a xen-host")
        if r_dict["errors"]:
            out_f.extend(r_dict["errors"])
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        return ret_state, ", ".join(out_f)
