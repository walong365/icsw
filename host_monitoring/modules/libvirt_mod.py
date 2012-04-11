#!/usr/bin/python-init -Ot
#
# Copyright (C) 2010,2012 Andreas Lang-Nevyjel init.at
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
from host_monitoring import limits, hm_classes
import os
import os.path
import logging_tools
import pprint
import server_command
import process_tools
from lxml import etree
try:
    import libvirt_tools
except:
    libvirt_tools = None

class _general(hm_classes.hm_module):
    def _exec_command(self, com, logger):
        stat, out = commands.getstatusoutput(com)
        if stat:
            logger.warning("cannot execute %s (%d): %s" % (com, stat, out))
            out = ""
        return out.split("\n")
                    
class libvirt_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        if libvirt_tools:
            cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
            ret_dict = cur_lvc.get_status()
            cur_lvc.close()
        else:
            ret_dict = {}
        srv_com["libvirt"] = ret_dict
    def interpret(self, srv_com, cur_ns):
        r_dict = srv_com["libvirt"]
        return self._interpret(r_dict, cur_ns)
    def interpret_old(self, result, parsed_coms):
        r_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(r_dict, parsed_coms)
    def _interpret(self, r_dict, cur_ns):
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
        return ret_state, ", ".join(out_f)

class domain_overview_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        if libvirt_tools:
            cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
            ret_dict = cur_lvc.domain_overview()
            cur_lvc.close()
        else:
            ret_dict = {}
        srv_com["domain_overview"] = ret_dict
    def interpret(self, srv_com, cur_ns):
        r_dict = srv_com["domain_overview"]
        return self._interpret(r_dict, cur_ns)
    def interpret_old(self, result, parsed_coms):
        r_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(r_dict, parsed_coms)
    def _interpret(self, dom_dict, cur_ns):
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
        return ret_state, "running: %s; %s" % (logging_tools.get_plural("domain", len(all_names)),
                                               ", ".join(out_f))

class domain_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({"reply"  : "missing argument",
                                              "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            if libvirt_tools:
                cur_lvc = libvirt_tools.libvirt_connection(log_com=self.log)
                ret_dict = cur_lvc.domain_status(srv_com["arguments:arg0"].text)
                cur_lvc.close()
            else:
                ret_dict = {}
            srv_com["domain_status"] = ret_dict
    def interpret(self, srv_com, cur_ns):
        r_dict = srv_com["domain_status"]
        return self._interpret(r_dict, cur_ns)
    def interpret_old(self, result, parsed_coms):
        r_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(r_dict, parsed_coms)
    def _interpret(self, dom_dict, cur_ns):
        ret_state, out_f = (limits.nag_STATE_OK, [])
        if dom_dict["desc"]:
            xml_doc = etree.fromstring(dom_dict["desc"])
            out_f.append("%s, memory %s, %s, %s, VNC port is %d" % (
                xml_doc.find(".//name").text,
                logging_tools.get_size_str(int(xml_doc.find(".//memory").text) * 1024),
                logging_tools.get_plural("disk", len(xml_doc.findall(".//disk"))),
                logging_tools.get_plural("iface", len(xml_doc.findall(".//interface"))),
                int(xml_doc.find(".//graphics").attrib["port"]) - 5900
            ))
        else:
            if dom_dict["cm"]:
                ret_state = limits.nag_STATE_CRITICAL
                out_f.append("domain '%s' not running" % (dom_dict["cm"]))
            else:
                ret_state = limits.nag_STATE_WARNING
                out_f.append("no domain-name give")
        return ret_state, ", ".join(out_f)
        
if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
