# Copyright (C) 2001-2006,2011,2013-2017 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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

""" interpret PCI layout """

import os
import re
import struct

from lxml.builder import E

from initat.tools import server_command


def get_pci_dicts(fname=None):
    vdict, cdict = ({}, {})
    if fname:
        search_names = [fname]
    else:
        search_names = [
            "/opt/cluster/share/pci/pci.ids",
        ]
    lines = []
    for search_name in search_names:
        if os.path.isfile(search_name):
            with open(search_name, "r") as file_:
                lines = file_.read().decode("utf-8").split('\n')
                break
    classline = re.compile("^C (..)\s+(.*)$")
    subclassline = re.compile("^\t(..)\s+(.*)$")
    vendorline = re.compile("^(.{4})\s+(.*)$")
    devline = re.compile("^\t(.{4})\s+(.*)$")
    _sdevline = re.compile("^\t\t(.*)$")
    actvendor = None
    actclass = None
    mode = True
    for pline in lines:
        line = pline.rstrip()
        if line and not line.startswith("#"):
            if mode:
                classmatch = classline.match(line)
                if classmatch:
                    mode = False
                else:
                    vendormatch = vendorline.match(line)
                    if vendormatch:
                        actvendor = vendormatch.group(1)
                        vdict[actvendor] = {
                            "name": vendormatch.group(2).strip()
                        }
                    else:
                        devmatch = devline.match(line)
                        if devmatch:
                            vdict[actvendor][devmatch.group(1)] = devmatch.group(2).strip()
            if not mode:
                classmatch = classline.match(line)
                if classmatch:
                    actclass = classmatch.group(1)
                    cdict[actclass] = {
                        "name": classmatch.group(2).strip()
                    }
                else:
                    subclassmatch = subclassline.match(line)
                    if subclassmatch:
                        cdict[actclass][subclassmatch.group(1)] = subclassmatch.group(2).strip()
    return vdict, cdict


def get_actual_pci_struct(vdict=None, cdict=None):
    if not vdict and not cdict:
        vdict, cdict = get_pci_dicts()
    pdict = {}
    try:
        tlines = open("/proc/bus/pci/devices", "r").readlines()
    except:
        pass
    else:
        okline = re.compile("^(..)(..)\s+(\S+)\s+.*$")
        for tline in tlines:
            line = tline.strip()
            okmatch = okline.match(line)
            if okmatch:
                bus = int(okmatch.group(1), 16)
                bdev = int(okmatch.group(2), 16)
                bdev0 = bdev >> 3
                bdev1 = bdev - (bdev0 << 3)
                vendor = okmatch.group(3)[0:4]
                device = okmatch.group(3)[4:8]
                fname = "/proc/bus/pci/{:02x}/{:02x}.{:x}".format(bus, bdev0, bdev1)
                pcdomain = int("0000", 16)
                try:
                    fbytes = open(fname, "r").read(64)
                except:
                    pclass = "0"
                    subclass = "0"
                    revision = "0"
                else:
                    pclass = "{:02x}".format(struct.unpack("B", fbytes[11])[0])
                    subclass = "{:02x}".format(struct.unpack("B", fbytes[10])[0])
                    revision = "{:02x}".format(struct.unpack("B", fbytes[8])[0])
                actd = {
                    "domain": pcdomain,
                    "vendor": vendor,
                    "device": device,
                    "class": pclass,
                    "subclass": subclass,
                    "vendorname": "unknown vendor {}".format(vendor),
                    "devicename": "unknown device {}".format(device),
                    "classname": "unknown class {}".format(pclass),
                    "subclassname": "unknown subclass {}".format(subclass),
                    "revision": revision
                }
                if vendor in vdict:
                    actd["vendorname"] = vdict[vendor]["name"]
                    if device in vdict[vendor]:
                        actd["devicename"] = vdict[vendor][device]
                if pclass in cdict:
                    actd["classname"] = cdict[pclass]["name"]
                    if subclass in cdict[pclass]:
                        actd["subclassname"] = cdict[pclass][subclass]
                pdict.setdefault(pcdomain, {}).setdefault(bus, {}).setdefault(bdev0, {})[bdev1] = actd
    return pdict


# helper functions
def compress_pci_info(in_struct):
    return server_command.compress(in_struct, marshal=True)


def decompress_pci_info(in_struct):
    return server_command.decompress(in_struct, marshal=True)


def pci_struct_to_xml(pci_dict):
    def sub_struct(_parent, _name, _id):
        _new_el = getattr(E, _name)(id="{:d}".format(_id))
        _parent.append(_new_el)
        return _new_el

    _main = E.pci_tree()
    for _dom_id in sorted(pci_dict.keys()):
        _dom = sub_struct(_main, "dom", _dom_id)
        for _bus_id in sorted(pci_dict[_dom_id].keys()):
            _bus = sub_struct(_dom, "bus", _bus_id)
            for _slot_id in sorted(pci_dict[_dom_id][_bus_id].keys()):
                _slot = sub_struct(_bus, "slot", _slot_id)
                for _func_id in sorted(pci_dict[_dom_id][_bus_id][_slot_id].keys()):
                    _func = sub_struct(_slot, "func", _func_id)
                    _func_s = pci_dict[_dom_id][_bus_id][_slot_id][_func_id]
                    for _key, _value in _func_s.items():
                        if isinstance(_value, int):
                            _value = "{:d}".format(_value)
                        _func.attrib[_key] = _value
    return _main
