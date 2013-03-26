#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of cluster-backbone-tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" kernel sync tools """

import sys
import os
from lxml import etree
from lxml.builder import E

LICENSE_FILE="/etc/sysconfig/cluster/cluster_license"

LICENSE_CAPS = [
    ("monitor", "Monitoring services"),
    ("monext" , "Extended monitoring services"),
    ("boot"   , "boot/config facility for nodes"),
    ("package", "Package installation"),
    ("rms"    , "Resource Management system"),
    ("ganglia", "Ganglia monitoring system"),
    ("rest"   , "REST server"),
    ("rrd"    , "RRD functionality"),
]


def check_license(lic_name):
    lic_xml = etree.fromstring(
        open(LICENSE_FILE, "r").read())
    cur_lic = lic_xml.xpath(".//license[@short='%s']" % (lic_name))
    if len(cur_lic):
        return True if cur_lic[0].get("enabled", "no").lower() in ["yes", "true", "1"] else False
    else:
        return False
    
def get_all_licenses():
    lic_xml = etree.fromstring(
        open(LICENSE_FILE, "r").read())
    return lic_xml.xpath(".//license/@short")

def create_default_license():
    if not os.path.isfile(LICENSE_FILE):
        lic_xml = E.cluster(
            E.licenses(
                *[E.license(name, short=name, info=info, enabled="no") for name, info in LICENSE_CAPS]
            )
        )
        file(LICENSE_FILE, "w").write(etree.tostring(lic_xml, pretty_print=True))
        os.chmod(LICENSE_FILE, 0o644)
        print("created license file '%s'" % (LICENSE_FILE))
    else:
        lic_xml = etree.fromstring(
            open(LICENSE_FILE, "r").read())
        changed = False
        for lic_name, info in LICENSE_CAPS:
            if not len(lic_xml.xpath(".//licenses/license[@short='%s']" % (lic_name))):
                changed = True
                lic_xml.find("licenses").append(
                    E.license(lic_name, short=lic_name, info=info, enabled="no")
                )
        if changed:
            print("license file '%s' already present and updated" % (LICENSE_FILE))
            file(LICENSE_FILE, "w").write(etree.tostring(lic_xml, pretty_print=True))
            os.chmod(LICENSE_FILE, 0o644)
        else:
            print("license file '%s' already present" % (LICENSE_FILE))
        
if __name__ == "__main__":
    create_default_license()
