#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang-Nevyjel
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
""" create cluster functionality, deprecated """

import sys
import cs_base_class
import os
import re
import logging_tools

try:
    import xml_tools
    import xml
    import xml.dom.expatbuilder
    import xml.dom.minidom
except ImportError:
    xml_tools, xml = (None, None)

class create_cluster_functionality_xml_file(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_public_via_net(False)
    def call_it(self, opt_dict, call_params):
        if not xml:
            ret_str = "error no xml-module present"
        cf_sfile = "/etc/sysconfig/cluster/cluster_functionalities"
        cf_dfile = "%s.xml" % (cf_sfile)
        if os.path.isfile(cf_sfile):
            try:
                lines = [(z[0],
                          [s.strip() for s in z[1].split(":")],
                          [s.strip() for s in z[2].split(":")]) for z in [y.split(";") for y in [x.strip() for x in file(cf_sfile, "r").read().split("\n")] if not y.startswith("#")] if len(z) == 3]
            except:
                ret_str = "error reading file '%s': %s (%s)" % (cf_sfile,
                                                                str(sys.exc_info()[0]),
                                                                str(sys.exc_info()[1]))
            else:
                # read new_config names
                call_params.dc.execute("SELECT nc.name FROM new_config nc")
                all_conf_names = [x["name"] for x in call_params.dc.fetchall()]
                xml_doc = xml.dom.minidom.Document()
                func_level = xml_doc.appendChild(xml_doc.createElement("functionalities"))
                for func_name, conf_names, level_names in lines:
                    print "parsing function %s, %s and %s" % (func_name,
                                                              logging_tools.get_plural("config_name", len(conf_names)),
                                                              logging_tools.get_plural("level_name", len(level_names)))
                    act_func = func_level.appendChild(xml_doc.createElement("functionality"))
                    act_func.setAttribute("name", func_name)
                    conf_el = act_func.appendChild(xml_doc.createElement("configs"))
                    act_conf_names = []
                    for conf_name in conf_names:
                        act_conf_names.extend([x for x in all_conf_names if re.match(conf_name, x) if x not in act_conf_names])
                    for act_conf_name in act_conf_names:
                        act_conf = conf_el.appendChild(xml_doc.createElement("config"))
                        act_conf.setAttribute("name", act_conf_name)
                        
                    level_el = act_func.appendChild(xml_doc.createElement("scripts"))
                    for level_name in level_names:
                        act_level = level_el.appendChild(xml_doc.createElement("script"))
                        act_level.setAttribute("name", level_name)
                try:
                    file(cf_dfile, "w").write(xml_doc.toprettyxml("   "))
                except:
                    ret_str = "error creating file '%s': %s (%s)" % (cf_dfile,
                                                                     str(sys.exc_info()[0]),
                                                                     str(sys.exc_info()[1]))
                else:
                    ret_str = "ok write %s" % (cf_dfile)
        else:
            ret_str = "error file '%s' not found" % (cf_sfile)
        return ret_str
        #if call_params.nss_queue:
        #    call_params.nss_queue.put(server_broadcast_message(("write_etc_hosts")))

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
