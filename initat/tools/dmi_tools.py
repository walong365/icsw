# Copyright (C) 2015-2016 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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

""" parse dmidecode output """

import re
import tempfile
import commands

from lxml.builder import E

from initat.tools import process_tools, server_command

DMI_TYPES = {
    0: "BIOS",
    1: "System",
    2: "Base Board",
    3: "Chassis",
    4: "Processor",
    5: "Memory Controller",
    6: "Memory Module",
    7: "Cache",
    8: "Port Connector",
    9: "System Slots",
    10: "On Board Devices",
    11: "OEM Strings",
    12: "System Configuration Options",
    13: "BIOS Language",
    14: "Group Associations",
    15: "System Event Log",
    16: "Physical Memory Array",
    17: "Memory Device",
    18: "32-bit Memory Error",
    19: "Memory Array Mapped Address",
    20: "Memory Device Mapped Address",
    21: "Built-in Pointing Device",
    22: "Portable Battery",
    23: "System Reset",
    24: "Hardware Security",
    25: "System Power Controls",
    26: "Voltage Probe",
    27: "Cooling Device",
    28: "Temperature Probe",
    29: "Electrical Current Probe",
    30: "Out-of-band Remote Access",
    31: "Boot Integrity Services",
    32: "System Boot",
    33: "64-bit Memory Error",
    34: "Management Device",
    35: "Management Device Component",
    36: "Management Device Threshold Data",
    37: "Memory Channel",
    38: "IPMI Device",
    39: "Power Supply",
    126: "Inactive",
    127: "End of Table",
}

_BIOS_PRESENT_RE = re.compile("^SMBIOS (?P<version>\S+) present.$")
_STRUCTURE_RE = re.compile("^(?P<num_struct>\d+) structures occupying (?P<size>\d+) bytes.$")
_DMI_HEADER_RE = re.compile("^Handle 0x(?P<handle>[a-fA-F0-9]+), DMI type (?P<dmi_type>\d+), (?P<length>\d+) bytes$")


def parse_dmi_output(lines):
    # not beautifull but working

    def _parse_handle():
        if lines:
            h_line = lines.pop(0)
            header_m = _DMI_HEADER_RE.match(h_line)
            if not header_m:
                raise ValueError("error interpreting header_line '{}'".format(h_line))
            _handle_struct = {
                "handle": int(header_m.group("handle"), 16),
                "dmi_type": int(header_m.group("dmi_type")),
                "length": int(header_m.group("length")),
                "header": lines.pop(0),
            }
            _dict = {}
        if lines:
            while lines[0].strip():
                _line = lines.pop(0)
                if _line.startswith("\t\t"):
                    # add to previous _key
                    if type(_dict[_key]) != list:
                        _dict[_key] = [_dict[_key]]
                    _dict[_key].append(_line.strip())
                else:
                    _line = _line.strip()
                    if _line.endswith(":"):
                        _key = _line[:-1].strip()
                        _dict[_key] = []
                    else:
                        # print _line
                        if _line.count(":"):
                            _key, _value = _line.split(":", 1)
                        else:
                            _key, _value = (_line, "")
                        _key = _key.strip()
                        _dict[_key] = _value.strip()
            if _dict:
                _handle_struct["values"] = _dict
        return _handle_struct

    _struct = {"num_lines": len(lines), "handles": []}
    try:
        # header
        if lines:
            first_line = lines.pop(0)
            if not first_line.startswith("#"):
                raise ValueError("first line '{}' does not start with '#'".format(first_line))
            next_line = lines.pop(0)
            if next_line.startswith("Scanning"):
                next_line = lines.pop(0)
            if next_line.startswith("Reading"):
                next_line = lines.pop(0)
            _bios_m = _BIOS_PRESENT_RE.match(next_line)
            _struct["version"] = _bios_m.group("version")
            _structure_m = _STRUCTURE_RE.match(lines.pop(0))
            _struct["num_struct"] = int(_structure_m.group("num_struct"))
            _struct["size"] = int(_structure_m.group("size"))

            if len(lines) > 0 and lines[0].startswith("Table at"):
                lines.pop(0)

            while lines:
                while lines and not lines[0].strip():
                    lines.pop(0)
                if lines:
                    _struct["handles"].append(_parse_handle())
            for line in lines:
                _empty_line = True if not len(line.strip()) else False

            # print _empty_line, line
    except:
        _struct["valid"] = False
        _struct["error"] = process_tools.get_except_info()
    else:
        _struct["valid"] = True
    return _struct

def dmi_struct_to_xml(dmi_dict):
    _main = E.dmi_tree(
        valid="1" if dmi_dict["valid"] else "0",
        version=dmi_dict.get("version", "0.0"),
        num_lines="{:d}".format(dmi_dict.get("num_lines", 0)),
        size="{:d}".format(dmi_dict.get("size", 0)),
    )
    _handles = E.handles()
    _main.append(_handles)
    for _hs in dmi_dict.get("handles", []):
        _xml = E.handle(
            dmi_type="{:d}".format(_hs["dmi_type"]),
            header=_hs["header"],
            length="{:d}".format(_hs["length"]),
            handle="{:d}".format(_hs["handle"]),
        )
        if "error" in dmi_dict:
            _xml.attrib["error"] = dmi_dict["error"]
        if "values" in _hs:
            _values = E.values()
            _xml.append(_values)
            for _key, _value in _hs["values"].iteritems():
                if type(_value) == list:
                    _values.append(
                        E.value(
                            *[
                                E.single(_val) for _val in _value
                            ],
                            key=_key
                        )
                    )
                else:
                    _values.append(
                        E.value(_value, key=_key)
                    )
        _handles.append(_xml)
    return _main


def decompress_dmi_info(in_str):
    _dmi_bin = process_tools.find_file("dmidecode")
    with tempfile.NamedTemporaryFile() as tmp_file:
        file(tmp_file.name, "w").write(server_command.decompress(in_str))
        _dmi_stat, dmi_result = commands.getstatusoutput(
            "{} --from-dump {}".format(
                _dmi_bin,
                tmp_file.name
            )
        )
        _xml = dmi_struct_to_xml(parse_dmi_output(dmi_result.split("\n")))
    return _xml
