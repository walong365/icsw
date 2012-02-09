#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010 lang-nevyjel@init.at
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
from host_monitoring import limits
from host_monitoring import hm_classes
import os
import os.path
import logging_tools
import contextlib
import pprint
import process_tools
from lxml import etree
try:
    import libvirt_tools
except:
    libvirt_tools = None

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "libvirt",
                                        "provides a interface to check for libvirt (virsh)",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        pass
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
                    
class libvirt_status(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "libvirt_status", **args)
        self.help_str = "checks if libvirt is running"
    def server_call(self, cm):
        if libvirt_tools:
            cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
            ret_dict = cur_lvc.get_status()
            cur_lvc.close()
        else:
            ret_dict = {}
        return "ok %s" % (hm_classes.sys_to_net(ret_dict))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            r_dict = hm_classes.net_to_sys(result[3:])
            ret_state, out_f = (limits.nag_STATE_OK, [])
            if "info" in r_dict:
                out_f.append("type is %s, version is %d.%d on an %s" % (
                    r_dict["type"],
                    (r_dict["version"] / 1000),
                    r_dict["version"] % 1000,
                    r_dict["info"][0]))
            else:
                ret_state = limits.nag_STATE_CRITICAL
                out_f.append("libvirt is not running")
            return ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                          ", ".join(out_f))
        else:
            return limits.nag_STATE_CRITICAL, result

class domain_overview(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "domain_overview", **args)
        self.help_str = "get domain overview"
    def server_call(self, cm):
        if libvirt_tools:
            cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
            ret_dict = cur_lvc.domain_overview()
            cur_lvc.close()
        else:
            ret_dict = {}
        return "ok %s" % (hm_classes.sys_to_net(ret_dict))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            dom_dict = hm_classes.net_to_sys(result[3:])
            ret_state, out_f = (limits.nag_STATE_OK, [])
            if "running" in dom_dict and "defined" in dom_dict:
                pass
            else:
                # reorder old-style retunr
                dom_dict = {"running" : dom_dict,
                            "defined" : {}}
            r_dict = dom_dict["running"]
            d_dict = dom_dict["defined"]
            # generate name lookup
            name_lut = dict([(value["name"], key) for key, value in r_dict.iteritems()])
            all_names = sorted(name_lut.keys())
            for act_name in all_names:
                n_dict = r_dict[name_lut[act_name]]
                out_f.append("%s [#%d, %s]" % (act_name, name_lut[act_name],
                                               logging_tools.get_plural("CPU", n_dict["info"][3])))
            out_f.append("%s: %s" % (logging_tools.get_plural("defined", len(d_dict)),
                                     ", ".join(sorted(d_dict.keys())) or "none"))
            return ret_state, "%s running: %s; %s" % (limits.get_state_str(ret_state),
                                                      logging_tools.get_plural("domain", len(all_names)),
                                                      ", ".join(out_f))
        else:
            return limits.nag_STATE_CRITICAL, result

class domain_status(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "domain_status", **args)
        self.help_str = "get domain status"
    def server_call(self, cm):
        if libvirt_tools:
            cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
            ret_dict = cur_lvc.domain_status(cm)
            cur_lvc.close()
        else:
            ret_dict = {}
        return "ok %s" % (hm_classes.sys_to_net(ret_dict))
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            r_dict = hm_classes.net_to_sys(result[3:])
            ret_state, out_f = (limits.nag_STATE_OK, [])
            if r_dict["desc"]:
                xml_doc = etree.fromstring(r_dict["desc"])
                out_f.append("%s, memory %s, %s, %s, VNC port is %d" % (
                    xml_doc.find(".//name").text,
                    logging_tools.get_size_str(int(xml_doc.find(".//memory").text) * 1024),
                    logging_tools.get_plural("disk", len(xml_doc.findall(".//disk"))),
                    logging_tools.get_plural("iface", len(xml_doc.findall(".//interface"))),
                    int(xml_doc.find(".//graphics").attrib["port"]) - 5900
                ))
            else:
                if r_dict["cm"]:
                    ret_state = limits.nag_STATE_CRITICAL
                    out_f.append("domain '%s' not running" % (r_dict["cm"][0]))
                else:
                    ret_state = limits.nag_STATE_WARNING
                    out_f.append("no domain-name give")
            return ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                          ", ".join(out_f))
        else:
            return limits.nag_STATE_CRITICAL, result
        
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
