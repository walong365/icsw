#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cbc_tools
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
""" parses and improves VASP xml files """

from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import os

outcar_name = "OUTCAR"
vasprun_name = "vasprun.xml"


class target_file(object):
    def get_file_name(self, base_name):
        if "JOB_ID" in os.environ:
            f_name = "%s.%s.%s" % (base_name, os.environ["JOB_ID"], os.environ["SGE_TASK_ID"])
        else:
            f_name = "%s.%d" % (base_name, os.getpid())
        add_iter = 0
        while True:
            c_file = "%s.xml" % (f_name if not add_iter else "%s.%d" % (f_name, add_iter))
            if not os.path.isfile(c_file):
                break
            add_iter += 1
        return c_file


class outcar(target_file):
    def __init__(self, f_name):
        res = E.vasp_info(E.timing())
        res.append(E.incar(file("INCAR", "r").read()))
        loop_nodes = E.loop()
        loopp_nodes = E.loopplus()
        res.find("timing").extend([loop_nodes, loopp_nodes])
        for line_num, line in enumerate(file(f_name, "r").read().split("\n")):
            s_line = line.strip()
            s_parts = s_line.split()
            if not line_num:
                res.append(E.info(line.strip()))
            elif s_line.startswith("running on"):
                res.append(E.nodes(s_parts[2]))
            elif s_parts:
                if s_parts[0] == "distr:":
                    res.append(E.distribution(nodes=s_parts[4], groups=s_parts[6]))
                elif s_parts[0] == "LOOP:":
                    loop_nodes.append(E.timing(cpu=s_parts[3][:-1], real=s_parts[6]))
                elif s_parts[0] == "LOOP+:":
                    loopp_nodes.append(E.timing(cpu=line[21:29].strip(), real=line[40:].strip()))
        t_name = self.get_file_name("vasp_info")
        print "saving to %s" % (t_name)
        file(t_name, "w").write(etree.tostring(res, pretty_print=True))


class VASPRun(target_file):
    def __init__(self, f_name):
        src_xml = etree.fromstring(file(f_name, "r").read())
        self._transform(src_xml)
        t_name = self.get_file_name("vasp_run")
        print("saving to {}".format(t_name))
        file(t_name, "w").write(etree.tostring(src_xml, pretty_print=True))

    def _transform(self, in_xml):
        split_to_xyz = {"v", "r"}
        for node in in_xml.xpath(".//*"):
            if node.text is not None:
                node.text = node.text.strip()
                if node.tag in split_to_xyz:
                    if len(node.text.split()) == 3:
                        for val_name, val in zip(["x", "y", "z"], node.text.split()):
                            node.append(getattr(E, val_name)(val))
                    else:
                        for val in node.text.split():
                            node.append(E.val(val))
                    node.text = ""


def main():
    if os.path.isfile(outcar_name):
        outcar(outcar_name)
    else:
        print("cannot find '{}'".format(outcar_name))
    if os.path.isfile(vasprun_name):
        VASPRun(vasprun_name)
    else:
        print("cannot find '{}'".format(vasprun_name))

if __name__ == "__main__":
    main()
