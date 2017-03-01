# -*- coding: utf-8 -*-
#
# Copyright (C) 2014,2016-2017 Andreas Lang-Nevyjel
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


import ast
import binascii
import os
import re
from collections import defaultdict, OrderedDict

from enum import IntEnum

from initat.tools.server_command import srv_command


SIZE_RE = re.compile("(\d*) ([kMG])B")
INDEX_RE = re.compile("(\d)*$")

BINARY_FACTOR = {
    "k": 1024,
    "M": 1024 ** 2,
    "G": 1024 ** 3,
}

MEMORY_FORM_FACTORS = {
    0: "Unknown",
    1: "Other",
    2: "SIP",
    3: "DIP",
    4: "ZIP",
    5: "SOJ",
    6: "Proprietary",
    7: "SIMM",
    8: "DIMM",
    9: "TSOP",
    10: "PGA",
    11: "RIMM",
    12: "SODIMM",
    13: "SRIMM",
    14: "SMD",
    15: "SSMP",
    16: "QFP",
    17: "TQFP",
    18: "SOIC",
    19: "LCC",
    20: "PLCC",
    21: "BGA",
    22: "FPBGA",
    23: "LGA",
}

MEMORY_TYPES = {
    0: "Unknown",
    1: "Other",
    2: "DRAM",
    3: "Synchronous DRAM",
    4: "Cache DRAM",
    5: "EDO",
    6: "EDRAM",
    7: "VRAM",
    8: "SRAM",
    9: "RAM",
    10: "ROM",
    11: "FLASH",
    12: "EEPROM",
    13: "FEPROM",
    14: "EPROM",
    15: "CDRAM",
    16: "3DRAM",
    17: "SDRAM",
    18: "SGRAM",
    19: "RDRAM",
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    25: "FBD2",
}

EDID_MANUFACTURER = {
    'AAC': 'AcerView',
    'AOC': 'AOC',
    'APP': 'Apple Computer',
    'AST': 'AST Research',
    'CPL': 'Compal',
    'CPQ': 'Compaq',
    'CTX': 'CTX',
    'DEC': 'DEC',
    'DEL': 'Dell',
    'DPC': 'Delta',
    'DWE': 'Daewoo',
    'EIZ': 'EIZO',
    'ELS': 'ELSA',
    'EPI': 'Envision',
    'FCM': 'Funai',
    'FUJ': 'Fujitsu',
    'GSM': 'LG Electronics',
    'GWY': 'Gateway 2000',
    'HEI': 'Hyundai',
    'HIT': 'Hitachi',
    'HSL': 'Hansol',
    'HTC': 'Hitachi/Nissei',
    'HWP': 'HP',
    'IBM': 'IBM',
    'ICL': 'Fujitsu ICL',
    'IVM': 'Iiyama',
    'KDS': 'Korea Data Systems',
    'MEI': 'Panasonic',
    'MEL': 'Mitsubishi Electronics',
    'NAN': 'Nanao',
    'NEC': 'NEC',
    'NOK': 'Nokia Data',
    'PHL': 'Philips',
    'REL': 'Relisys',
    'SAM': 'Samsung',
    'SGI': 'SGI',
    'SNY': 'Sony',
    'SRC': 'Shamrock',
    'SUN': 'Sun Microsystems',
    'TAT': 'Tatung',
    'TOS': 'Toshiba',
    'TSB': 'Toshiba',
    'VSC': 'ViewSonic',
    'ZCM': 'Zenith',
}


class DMIType(IntEnum):
    system = 1
    base_board = 2
    chassis = 3
    processor = 4
    memory_controller = 5
    memory_module = 6
    cache = 7
    port_connector = 8
    system_slots = 9
    on_board_devices = 10
    oem_strings = 11
    system_configuration_options = 12
    bios_language = 13
    group_associations = 14
    system_event_log = 15
    physical_memory_array = 16
    memory_device = 17
    _32_bit_memory_error = 18
    memory_array_mapped_address = 19
    memory_device_mapped_address = 20
    built_in_pointing_device = 21
    portable_battery = 22
    system_reset = 23
    hardware_security = 24
    system_power_controls = 25
    voltage_probe = 26
    cooling_device = 27
    temperature_probe = 28
    electrical_current_probe = 29
    out_of_band_remote_access = 30
    boot_integrity_services = 31
    system_boot = 32
    _64_bit_memory_error = 33
    management_device = 34
    management_device_component = 35
    management_device_threshold_data = 36
    memory_channel = 37
    ipmi_device = 38
    power_supply = 39
    additional_information = 40
    onboard_device = 41


def format_mac_address(mac_address):
    return mac_address.upper()


def parse_size(size_str):
    try:
        (num, prefix) = SIZE_RE.search(size_str).groups()
    except AttributeError:
        pass
    else:
        return int(num) * BINARY_FACTOR[prefix]


def _parse_lsblk(dump):
    def to_bool(s):
        return bool(int(s))

    def to_int(s):
        return int(s) if s else None

    def unescape(match):
        return chr(int(match.groups()[0], base=16))

    escape_re = re.compile('\\\\x(\d\d)')
    mappers = {
        'RA': int,
        'RO': to_bool,
        'RM': to_bool,
        'SIZE': to_int,
        'ALIGNMENT': int,
        'MIN-IO': int,
        'OPT-IO': int,
        'PHY-SEC': int,
        'LOG-SEC': int,
        'ROTA': to_bool,
        'RQ-SIZE': int,
        'DISC-ALN': int,
        'DISC-GRAN': int,
        'DISC-MAX': int,
        'DISC-ZERO': int,
        'WSAME': int,
        'RAND': to_bool,
    }
    result = dump["result"]
    if dump["version"] == 0:
        # original version, only space delimitered, impossible to parse
        lines = result.split('\n')
        header = lines.pop(0).split()
        raw_data = [line.strip().split() for line in lines if line.strip()]
    elif dump["version"] == 1:
        # new version, list format, column are separated by vertical blank lines
        if result.startswith("b'"):
            result = ast.literal_eval(result).decode("utf-8")

        lines = result.strip().split('\n')
        _seps = [0]
        longest_line = max([len(line) for line in lines])
        for idx in range(longest_line):
            if all([line[idx] == " " for line in lines if len(line) > idx]):
                _seps.append(idx)
        _seps.append(longest_line)
        # print(_seps)
        # print("*", lines[0])
        line = lines[0]
        line = "{}{}".format(line, " " * longest_line)[0:longest_line]
        header = [
            line[_seps[_idx - 1]:_seps[_idx] + 1].strip() for _idx in range(1, len(_seps))
        ]
        # print(raw_data)
        _seps = _seps[:-1]
        new_seps = []
        # reorganize headers
        for _sep, _header in zip(_seps, header):
            if header:
                new_seps.append(_sep)
        new_seps.append(longest_line)
        raw_data = []
        for line in lines:
            line = "{}{}".format(line, " " * longest_line)[0:longest_line]
            _parts = [
                line[new_seps[_idx - 1]:new_seps[_idx] + 1].strip() for _idx in range(1, len(_seps))
            ]
            raw_data.append(_parts)
        header = raw_data.pop(0)
    rows = []
    for data in raw_data:
        data = [escape_re.sub(unescape, d).strip() for d in data]
        if len(data) != len(header):
            # problem
            continue
        data = OrderedDict([(k, v) for (k, v) in zip(header, data)])
        # if available, apply the mapping function
        for (key, value) in data.items():
            if key in mappers:
                # print("*", key, value, mappers[key], data)
                data[key] = mappers[key](value)
        rows.append(data)

    return rows


def _parse_edid(blob):
    def _bits(bytes):
        bin_strs = ["{:08b}".format(b) for b in bytes]
        return ''.join(bin_strs)

    def _decode_edi(bits):
        return chr(int(bits, base=2) + ord('A') - 1)

    # see https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
    result = {}
    magic = blob[0:8]
    assert magic.encode('hex') == '00ffffffffffff00'
    manufacturer_blob = blob[8:10]
    manufacturer_bits = _bits(manufacturer_blob)
    slices = [
        (1, 6),
        (6, 11),
        (11, 16),
    ]
    manufacturer = [
        _decode_edi(manufacturer_bits[slice(*s)])
        for s in slices
    ]
    result['manufacturer'] = EDID_MANUFACTURER.get(''.join(manufacturer))
    result['product'] = binascii.hexlify(blob[10:12]).decode('ascii')
    result['serial'] = binascii.hexlify(blob[12:16]).decode('ascii')
    result['week'] = blob[16]
    result['year'] = blob[17] + 1990
    result['version'] = binascii.hexlify(blob[18:19]).decode('ascii')

    return result


class Hardware(object):
    def __init__(self, lshw_dump=None, win32_tree=None, dmi_head=None,
                 lsblk_dump=None, partinfo_tree=None, xrandr_dump=None):
        self.cpus = []
        self.memory = None
        self.memory_modules = []
        self.gpus = []
        self.hdds = []
        self.logical_disks = []
        self.network_devices = []
        self.displays = []

        self._mount_point_logical_disks = {}

        if lsblk_dump:
            self._process_lsblk(lsblk_dump)
        if lshw_dump is not None:
            self._process_lshw(lshw_dump)
        if win32_tree:
            self._process_win32(win32_tree)
        if dmi_head:
            self._process_dmi_head(dmi_head)
        if partinfo_tree is not None:
            self._process_partinfo(partinfo_tree)
        if xrandr_dump:
            self._process_xrandr(xrandr_dump)

    def _process_lsblk(self, lsblk_dump):
        self._lsblk_dump = lsblk_dump
        entries = _parse_lsblk(lsblk_dump)
        type_entries = defaultdict(list)

        disc_re_unix = re.compile(
            "^/dev/([shv]d[a-z]{1,2}|dm-(\d+)|md\d+|mapper/.*|ida/(.*)|"
            "cciss/(.*))$"
        )

        for e in entries:
            if "TYPE" in e:
                type_entries[e['TYPE']].append(e)
            elif "MODEL" in e and (e["MODEL"] == "LOGICAL VOLUME" or e["MODEL"] == "LOGICAL"):
                # old lsblk, try to guess
                # sles11sp3 (Liebherr)
                type_entries["disk"].append(e)
            elif "GROUP" in e and e["GROUP"] == "disk" and "FSTYPE" in e and len(
                e["FSTYPE"]
            ) == 0 and "SIZE" in e and e["SIZE"] and e["SIZE"] > 0:
                if "KNAME" in e:
                    if disc_re_unix.match(e["KNAME"]) or disc_re_unix.match("/dev/{}".format(e["KNAME"])):
                        type_entries["disk"].append(e)
            elif "FSTYPE" in e and len(e["FSTYPE"]) > 0:
                type_entries["part"].append(e)

        name_object = {}
        for disk_entry in type_entries['disk']:
            hdd = HardwareHdd(lsblk_entry=disk_entry)
            if hdd not in self.hdds:
                self.hdds.append(hdd)
                name_object[hdd.device_name] = hdd
        # disk, partitions
        for part_entry in type_entries['part']:
            # print(part_entry)
            partition = Partition(lsblk_entry=part_entry)
            logical = LogicalDisc(lsblk_entry=part_entry)
            partition.logical = logical
            # add partition to the disk
            if partition._parent:
                parent_hdd = name_object.get(partition._parent)
                if parent_hdd:
                    parent_hdd.partitions.append(partition)
            else:
                for hdd in self.hdds:
                    if len(partition.device_name) > len(hdd.device_name) and \
                            partition.device_name.startswith(hdd.device_name):
                        hdd.partitions.append(partition)

        # logical disk
        for entry in entries:
            logical = LogicalDisc(lsblk_entry=entry)
            if logical.mount_point:
                self._mount_point_logical_disks[logical.mount_point] = logical

    def _process_lshw(self, lshw_dump):
        for sub_tree in lshw_dump.xpath(
            "//node[starts-with(@id, 'cpu') and @class='processor' and not(@disabled='true')]"
        ):
            self.cpus.append(HardwareCPU(sub_tree))

        sub_tree = lshw_dump.xpath(
            "/list/node/node[@id='core' and @class='bus']"
            "/node[starts-with(@id, 'memory') and @class='memory']"
        )[0]
        self.memory = HardwareMemory(sub_tree)

        for sub_tree in lshw_dump.xpath(
            "//node[starts-with(@id, 'memory') and @class='memory']/node"
        ):
            memory_module = MemoryModule(sub_tree)
            # don't add empty slots
            if memory_module.capacity:
                self.memory_modules.append(memory_module)

        for sub_tree in lshw_dump.xpath(
            "//node[starts-with(@id, 'display') and @class='display']"
        ):
            self.gpus.append(HardwareGPU(sub_tree))

        # add further disk information not available from lsblk
        device_hdds = {hdd.device_name: hdd for hdd in self.hdds}
        for sub_tree in lshw_dump.xpath(
            "//node[starts-with(@id, 'disk') and @class='disk']"
        ):
            lshw_hdd = HardwareHdd(sub_tree)
            hdd = device_hdds.get(lshw_hdd.device_name)
            if not hdd:
                hdd = device_hdds.get(os.path.split(lshw_hdd.device_name)[-1])
            if hdd:
                # lshw serial seems to be more accurate, overwrite value from lsblk
                if lshw_hdd.serial:
                    hdd.serial = lshw_hdd.serial
                hdd.update(lshw_hdd)

        for sub_tree in lshw_dump.xpath(
                "//node[starts-with(@id, 'network') and @class='network']"):
            self.network_devices.append(
                HardwareNetwork(sub_tree)
            )

    def _process_win32(self, win32_tree):
        self._win32_tree = win32_tree
        for sub_tree in win32_tree['Win32_Processor']:
            self.cpus.append(HardwareCPU(win32_tree=sub_tree))

        self.memory = HardwareMemory(
            win32_tree=win32_tree['Win32_ComputerSystem'][0]
        )

        for sub_tree in win32_tree['Win32_PhysicalMemory']:
            self.memory_modules.append(MemoryModule(win32_tree=sub_tree))

        for sub_tree in win32_tree['Win32_VideoController']:
            self.gpus.append(HardwareGPU(win32_tree=sub_tree))

        logical_path_logical = {}
        for sub_tree in win32_tree['Win32_LogicalDisk']:
            logical = LogicalDisc(win32_tree=sub_tree)
            self.logical_disks.append(logical)
            logical_path_logical[logical._path_w32] = logical

        partition_path_logical = self._map_win32(
            win32_tree['Win32_LogicalDiskToPartition']
        )

        partition_path_partitions = {}
        for sub_tree in win32_tree['Win32_DiskPartition']:
            partition = Partition(win32_tree=sub_tree)
            logical_paths = partition_path_logical[partition._path_w32]
            if logical_paths:
                # the physical partition has a corresponding logical entry
                partition.logical = logical_path_logical[logical_paths[0]]
            partition_path_partitions[partition._path_w32] = partition

        disk_path_partition = self._map_win32(
            win32_tree['Win32_DiskDriveToDiskPartition']
        )
        for sub_tree in win32_tree['Win32_DiskDrive']:
            hdd = HardwareHdd(win32_tree=sub_tree)
            hdd.partitions = [
                partition_path_partitions[p] for p in disk_path_partition[hdd._path_w32]
            ]
            self.hdds.append(hdd)

        for sub_tree in win32_tree['Win32_NetworkAdapter']:
            if sub_tree['PhysicalAdapter']:
                self.network_devices.append(
                    HardwareNetwork(win32_tree=sub_tree))

        for sub_tree in win32_tree['Win32_DesktopMonitor']:
            self.displays.append(Display(win32_tree=sub_tree))

    def _process_dmi_head(self, dmi_head):
        self.memory_modules = []
        for dmi_handle in dmi_head.assetdmihandle_set.filter(dmi_type=17):
            memory_module = MemoryModule(dmi_handle=dmi_handle)
            # don't add empty slots
            if memory_module.capacity:
                self.memory_modules.append(memory_module)

    def _process_partinfo(self, partinfo_tree):
        info_keys = ['dev_dict', 'partitions', 'lvm_dict', 'disk_usage']

        # parse result XML
        result = srv_command(source=partinfo_tree)
        self._partinfo_tree = {}
        for info_key in info_keys:
            try:
                res_tree = result[info_key]
            except KeyError:
                pass
            else:
                if not isinstance(res_tree, dict):
                    res_tree = result._interpret_el(res_tree)
                self._partinfo_tree[info_key] = res_tree

        # add disk usage information to logical disks
        disk_free = self._partinfo_tree.get('disk_usage')
        if disk_free:
            for usage in disk_free:
                mountpoint = usage['mountpoint']
                try:
                    logical = self._mount_point_logical_disks[mountpoint]
                except KeyError:
                    pass
                else:
                    logical.size = usage['total']
                    logical.free_space = usage['free']
                    self.logical_disks.append(logical)

    def _process_xrandr(self, xrandr_dump):
        # some helper classes for parsing the
        class _VirtScreen():
            def __init__(self, index, resolution):
                self.index = index
                self.resolution = resolution
                self.connections = []

        class _Connection():
            indent_re = re.compile("([ \t]*)(.*)")
            info_re = re.compile("(.*?):\s*(.*)")
            res_re = re.compile("\d+x\d+ ")
            timing_re = re.compile("[hv]: ")

            def __init__(self, connector, index):
                self.connector = connector
                self.index = index
                self.resolutions = []

                self._infos = OrderedDict()
                self._state = None
                self._cur_key = None

            def parse_line(self, line):
                (indent, remaining) = self.indent_re.match(line).groups()
                remaining = remaining.rstrip()
                info_match = self.info_re.match(remaining)
                res_match = self.res_re.match(remaining)
                timing_match = self.timing_re.match(remaining)
                if (indent[0] == '\t' and info_match):
                    # start of information line
                    (key, value) = info_match.groups()
                    self._state = 'info'
                    self._cur_key = key
                    self._infos[self._cur_key] = [value]
                elif (indent[0] == '\t' and len(indent) > 1):
                    # continuation of information line
                    assert self._state == 'info'
                    self._infos[self._cur_key].append(remaining)
                elif res_match:
                    # start of resolution info
                    self._state = 'res'
                    resolution = ScreenResolution(remaining)
                    self.resolutions.append(resolution)
                elif timing_match:
                    # timing line
                    assert self._state == 'res'
                    # discard info

            @property
            def infos(self):
                # do a little bit of post-processing
                res = OrderedDict()
                for (key, lines) in self._infos.items():
                    if len(lines) == 1:
                        res[key] = lines[0]
                    else:
                        res[key] = [l for l in lines if l]
                if 'EDID' in res:
                    hex_string = ''.join(res['EDID'])
                    res['EDID'] = bytes.fromhex(hex_string)
                return res

        virt_screen_re = re.compile(
            "Screen (?P<index>\d+): minimum (\d+ x \d+), "
            "current (?P<resolution>\d+ x \d+), maximum (\d+ x \d+)"
        )
        connectors = "DP|HDMI|VIRTUAL|DVI-I|VGA"
        connection_re = re.compile(
            "(?P<connector>{})-?(?P<index>\d+) "
            "(dis)?connected ".format(connectors)
        )
        self._xrandr_dump = xrandr_dump

        lines = xrandr_dump.decode().split('\n')
        virt_screens = []
        for line in lines:
            m = virt_screen_re.match(line)
            # virtual screen
            if m:
                virt_screen = _VirtScreen(**m.groupdict())
                virt_screens.append(virt_screen)
                continue

            # connection
            m = connection_re.match(line)
            if m:
                connection = _Connection(**m.groupdict())
                virt_screen.connections.append(connection)
                continue

            connection.parse_line(line)

        # now create the display objects
        for virt_screen in virt_screens:
            for connection in virt_screen.connections:
                infos = connection.infos
                if 'EDID' in infos:
                    edid = _parse_edid(infos['EDID'])
                    display = Display()
                    display.manufacturer = edid['manufacturer']
                    display.product = edid['product']
                    display.serial = edid['serial']
                    for resolution in connection.resolutions:
                        if '+preferred' in resolution.flags:
                            break
                    (display.x_resolution, display.y_resolution) = \
                        list(map(int, resolution.resolution.split('x')))
                    self.displays.append(display)

        self.virt_screen = virt_screens

    @staticmethod
    def _map_win32(sub_tree):
        mapping = defaultdict(list)
        for (dependent, andntecedent) in sub_tree:
            mapping[andntecedent].append(dependent)
        return mapping


class HardwareBase(object):
    # a dict of the form {prop_name: (xpath_expr, func)}
    LSHW_ELEMENTS = {}
    # a dict of the form {prop_name: (dict_key, func)}
    WIN32_ELEMENTS = {}
    # a dict of the form {prop_name: (handle_key, func)}
    DMI_ELEMENTS = {}

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self._tree = None
        self._path_w32 = None

        if lshw_dump is not None:
            self._tree = lshw_dump
            self._populate_lshw()
        elif win32_tree:
            self._tree = win32_tree
            self._populate_win32()
        elif dmi_handle:
            self._tree = {
                h.key: h.__dict__
                for h in dmi_handle.assetdmivalue_set.all()
            }
            self._populate_dmi()

    def __repr__(self):
        infos = []
        for (name, value) in list(self.__dict__.items()):
            if not name.startswith('_') and value is not None:
                infos.append('{}={}'.format(name, repr(value)))
        return '{}({})'.format(self.__class__.__name__, ', '.join(infos))

    def update(self, hw_instance):
        for (name, value) in list(hw_instance.__dict__.items()):
            cur_value = getattr(self, name)
            if cur_value is None:
                setattr(self, name, value)

    def _populate_lshw(self):
        for (prop_name, (xpath_expr, func)) in list(self.LSHW_ELEMENTS.items()):
            try:
                element = self._tree.xpath(xpath_expr)[0]
            except IndexError:
                continue
            try:
                value = element.text
            except AttributeError:
                value = element
            if func:
                value = func(value)
            setattr(self, prop_name, value)

    def _populate_win32(self):
        for (prop_name, (dict_key, func)) in list(self.WIN32_ELEMENTS.items()):
            value = self._tree[dict_key] if dict_key else None
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)

        self._path_w32 = self._tree['_path']

    def _populate_dmi(self):
        for (prop_name, (handle_key, func)) in list(self.DMI_ELEMENTS.items()):
            if handle_key in self._tree:
                value = self._tree[handle_key]['value']
                if value is not None and func:
                    value = func(value)
            else:
                value = "N/A"
            setattr(self, prop_name, value)


class HardwareCPU(HardwareBase):
    """Represents the physical CPU."""

    LSHW_ELEMENTS = {
        'product': ('product', str),
        'manufacturer': ('vendor', str),
        'version': ('version', str),
        'serial': ('serial', str),
        'number_of_cores': ("configuration/setting[@id='cores']/@value", int),
        'vendor': ('vendor', str)
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394373%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'product': ('Name', str),
        'manufacturer': ('Manufacturer', str),
        'version': ('Version', str),
        'serial': ('ProcessorId', str),
        'number_of_cores': ('NumberOfCores', int),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.product = None
        self.manufacturer = None
        self.version = None
        self.serial = None
        self.number_of_cores = None
        self.vendor = None
        super(HardwareCPU, self).__init__(lshw_dump, win32_tree, dmi_handle)


class HardwareMemory(HardwareBase):
    """Represent the system-wide memory information."""
    LSHW_ELEMENTS = {
        'size': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394102(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'size': ('TotalPhysicalMemory', int),
    }


class MemoryModule(HardwareBase):
    """Represents a DRAM module."""

#     LSHW_ELEMENTS = {
#         'manufacturer': ('vendor', unicode),
#         'capacity': ('size', int),
#         'serial': ('serial', unicode),
#         'bank_label': ('slot', unicode),
#     }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394347(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'manufacturer': ('Manufacturer', str),
        'capacity': ('Capacity', int),
        'serial': ('SerialNumber', str),
        'bank_label': ('DeviceLocator', str),
        'form_factor': ('FormFactor', int),
        'type': ('MemoryType', int),
    }
    DMI_ELEMENTS = {
        'manufacturer': ('Manufacturer', str),
        'capacity': ('Size', parse_size),
        'serial': ('Serial Number', str),
        'bank_label': ('Bank Locator', str),
        'form_factor': ('Form Factor', str),
        'type': ('Type', str),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.manufacturer = None
        self.capacity = None
        self.serial = None
        self.bank_label = None
        self.form_factor = None
        self.type = None
        super(MemoryModule, self).__init__(lshw_dump, win32_tree, dmi_handle)

    def _populate_win32(self):
        super(MemoryModule, self)._populate_win32()
        self.form_factor = MEMORY_FORM_FACTORS[self.form_factor]
        self.type = MEMORY_TYPES[self.type]


class HardwareGPU(HardwareBase):
    """Represents a graphics adapter."""

    LSHW_ELEMENTS = {
        'description': ('description', str),
        'product': ('product', str),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394512%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'description': ('Description', str),
        'product': ('Name', str),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.description = None
        self.product = None
        super(HardwareGPU, self).__init__(lshw_dump, win32_tree, dmi_handle)


class HardwareHdd(HardwareBase):
    """Represents a hard disc device."""

    LSHW_ELEMENTS = {
        'description': ('description', str),
        'product': ('product', str),
        'device_name': ('logicalname', str),
        'serial': ('serial', str),
        # "size" is the size of the physical disk whereas "capacity" is the
        # size of the corresponding file system (cf. the output of "lsblk")
        'size': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394132%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'description': ('Description', str),
        'product': ('Caption', str),
        'device_name': ('DeviceID', str),
        'serial': ('SerialNumber', str),
        'size': ('Size', int),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None,
                 lsblk_entry=None):
        self.description = None
        self.product = None
        self.device_name = None
        self.serial = None
        self.size = None
        self._lsblk_entry = lsblk_entry

        self.partitions = []

        if lsblk_entry:
            self._populate_lsblk()

        super(HardwareHdd, self).__init__(lshw_dump, win32_tree, dmi_handle)

    def __eq__(self, other):
        cmp_items = ["description", "product", "device_name", "serial", "size"]
        for cmp_item in cmp_items:
            if getattr(self, cmp_item) != getattr(other, cmp_item):
                return False
        return True

    def _populate_lsblk(self):
        entry = self._lsblk_entry
        self.device_name = entry['KNAME']
        if 'MODEL' in entry:
            self.product = entry['MODEL']
        if 'SERIAL' in entry:
            self.serial = entry['SERIAL']
        if 'SIZE' in entry:
            self.size = int(entry['SIZE'])


class Partition(HardwareBase):
    """Represents the partition information as available from the partition
    table."""
    type_map = {
        'vfat': 'fat',
        'LVM2_member': 'lvm'
    }

    LSHW_ELEMENTS = {
        'size': (None, str),
        'index': (None, int),
        'bootable': (None, str),
        'device_name': ('logicalname', str),
        'type': (None, str),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394135(v=vs.85).aspx
    # Note: WMI doesn't provide any information about the partition type hex.
    WIN32_ELEMENTS = {
        'size': ('Size', int),
        'index': ('Index', int),
        'bootable': ('Bootable', bool),
        'device_name': ('DeviceID', str),
        'type': ('Type', str),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None,
                 lsblk_entry=None):
        self.size = None
        self.index = None
        self.bootable = None
        self.device_name = None
        self.type = None
        self._lsblk_entry = lsblk_entry

        self.logical = None

        if lsblk_entry:
            self._populate_lsblk()

        super(Partition, self).__init__(lshw_dump, win32_tree, dmi_handle)

    def _populate_lsblk(self):
        entry = self._lsblk_entry
        self.size = entry['SIZE']
        match = INDEX_RE.search(entry['KNAME'])
        if match:
            self.index = match.group()
        self.device_name = entry['KNAME']
        self.type = self.type_map.get(entry['FSTYPE'], entry['FSTYPE'])
        self._parent = None
        if "PKNAME" in entry:
            self._parent = entry['PKNAME']

    def _set_from_logical_win32(self, logical_disc):
        self.free_space = logical_disc.free_space
        self.file_system = logical_disc.file_system


class LogicalDisc(HardwareBase):
    """Represents the file system level information."""
    type_map = {
        'vfat': 'fat',
    }

    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394173(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'device_name': ('DeviceID', str),
        'mount_point': ('DeviceID', str),
        'file_system': ('FileSystem', str.lower),
        'size': ('Size', int),
        'free_space': ('FreeSpace', int),
    }

    def __init__(
        self,
        lshw_dump=None, win32_tree=None, dmi_handle=None,
        lsblk_entry=None
    ):
        self.device_name = None
        self.mount_point = None
        self.file_system = None
        self.size = None
        self.free_space = None
        self._lsblk_entry = lsblk_entry

        if lsblk_entry:
            self._populate_lsblk()

        super(LogicalDisc, self).__init__(lshw_dump, win32_tree, dmi_handle)

    def _populate_lsblk(self):
        entry = self._lsblk_entry
        self.device_name = entry['KNAME']
        self.mount_point = entry['MOUNTPOINT']
        if self.mount_point == '[SWAP]':
            self.mount_point = None
        self.file_system = self.type_map.get(entry['FSTYPE'], entry['FSTYPE'])
        self.size = entry['SIZE']
        self.free_space = 0


class HardwareNetwork(HardwareBase):
    """Represents a network device."""

    LSHW_ELEMENTS = {
        'product': ('product', str),
        'manufacturer': ('vendor', str),
        'device_name': ('logicalname', str),
        'mac_address': ('serial', format_mac_address),
        'speed': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394216(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'product': ('ProductName', str),
        'manufacturer': ('Manufacturer', str),
        'device_name': ('NetConnectionID', str),
        'mac_address': ('MACAddress', str),
        'speed': ('Speed', int),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.product = None
        self.manufacturer = None
        self.device_name = None
        self.mac_address = None
        self.speed = None  # bit/s
        super(HardwareNetwork, self).__init__(
            lshw_dump,
            win32_tree,
            dmi_handle,
        )


class Display(HardwareBase):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394122(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'manufacturer': ('MonitorManufacturer', str),
        'product': ('Caption', str),
        'serial': (None, str),
        'x_resolution': ('ScreenWidth', int),
        'y_resolution': ('ScreenHeight', int),
    }

    def __init__(self, win32_tree=None):
        self.manufacturer = None
        self.product = None
        self.serial = None
        self.x_resolution = None
        self.y_resolution = None
        super(Display, self).__init__(
            win32_tree=win32_tree,
        )


class ScreenResolution():
    resolution_re = re.compile(
        '(\d+x\d+)\s+\(0x([0-9A-Fa-f]+)\)\s+([\d.]+)MHz(.*)'
    )

    def __init__(self, xrandr_line):
        match = self.resolution_re.match(xrandr_line)
        (self.resolution, self.hex, frequency, remainder) = match.groups()
        self.frequency = float(frequency)
        self.flags = remainder.split()


if __name__ == "__main__":
    # testcode for parsing
    result = """
NAME                                     KNAME MAJ:MIN FSTYPE      MOUNTPOINT                     LABEL UUID                                   RO RM MODEL                    SIZE OWNER GROUP MODE       ALIGNMENT MIN-IO OPT-IO PHY-SEC LOG-SEC ROTA SCHED
sda                                      sda     8:0                                                                                            0  0 LOGICAL VOLUME   299966445568 root  disk  brw-rw----         0 524288 524288     512     512    1 cfq
sda1                                     sda1    8:1   ext3        /boot                                f72f9c80-32bb-4b09-9ee2-eb5c52469dae    0  0                     271056896 root  disk  brw-rw----         0 524288 524288     512     512    1 cfq
sda2                                     sda2    8:2   swap        [SWAP]                               7a49d927-a99c-43c1-a3f7-5d132a4d98d8    0  0                   17182490624 root  disk  brw-rw----         0 524288 524288     512     512    1 cfq
sda3                                     sda3    8:3   btrfs                                            dd0b54c3-d6c3-4d26-95b4-30b7bf13bc31    0  0                   34357116928 root  disk  brw-rw----         0 524288 524288     512     512    1 cfq
sda4                                     sda4    8:4   LVM2_member                                      SwdYsx-SttO-EuA3-vXzW-vOay-7wAq-pJBnEh  0  0                  248154947584 root  disk  brw-rw----         0 524288 524288     512     512    1 cfq
data-apps (dm-3)                         dm-3  253:3   ext3        /usr/local/share/apps                c264fa8d-9f88-415b-a7a7-071351839458    0  0                   68719476736 root  disk  brw-rw----         0 524288 524288     512     512    1
data-opt (dm-4)                          dm-4  253:4   xfs         /opt                                 ab9d8f62-52f0-4bf2-b781-ba1defa0bdf7    0  0                   89238011904 root  disk  brw-rw----         0 524288 524288     512     512    1
data-rrd (dm-5)                          dm-5  253:5   ext3        /var/cache/rrd                       c5355afa-a291-4e4d-97d3-54253d0df51c    0  0                    4294967296 root  disk  brw-rw----         0 524288 524288     512     512    1
data-home_rsmadmin (dm-6)                dm-6  253:6   ext3        /usr/local/share/home/rsmadmin       72c02a84-d369-4816-9936-0e150b7e4367    0  0                   85899345920 root  disk  brw-rw----         0 524288 524288     512     512    1
sdb                                      sdb     8:16  LVM2_member                                      FBcoGZ-A9eE-iUgd-Cyle-LIXg-Mj40-VVBbD3  0  0 LOGICAL VOLUME   299966445568 root  disk  brw-rw----         0 262144 262144     512     512    1 cfq
3600508b1001cf5e18e7a6238386e805d (dm-7) dm-7  253:7   LVM2_member                                      FBcoGZ-A9eE-iUgd-Cyle-LIXg-Mj40-VVBbD3  0  0                  299966445568 root  disk  brw-rw----         0 262144 262144     512     512    1 cfq
data2-cransys (dm-0)                     dm-0  253:0   xfs         /usr/local/share/home/cransys        f79947e3-21cf-40ad-b770-e6429aec046c    0  0                  107374182400 root  disk  brw-rw----         0 262144 262144     512     512    1
data2-cluster (dm-1)                     dm-1  253:1   xfs         /opt/cluster/system                  bce52cd1-773a-4562-8e14-a0f6b34e535b    0  0                   34359738368 root  disk  brw-rw----         0 262144 262144     512     512    1
data2-ansys17 (dm-2)                     dm-2  253:2   xfs                                              7f4b1b4b-9208-4bdf-8d52-a502ba2287c0    0  0                   42949672960 root  disk  brw-rw----         0 262144 262144     512     512    1
sr0                                      sr0    11:0                                                                                            0  1 DVD ROM UJ8C2      1073741312 root  cdrom brw-rw----         0    512      0     512     512    1 cfq
loop0                                    loop0   7:0                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop1                                    loop1   7:1                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop2                                    loop2   7:2                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop3                                    loop3   7:3                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop4                                    loop4   7:4                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop5                                    loop5   7:5                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop6                                    loop6   7:6                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
loop7                                    loop7   7:7                                                                                            0  0                               root  disk  brw-rw----         0      0      0       0     512    1
"""
    lines = result.strip().split('\n')
    _seps = [0]
    longest_line = max([len(line) for line in lines])
    for idx in range(longest_line):
        if all([line[idx] == " " for line in lines if len(line) > idx]):
            _seps.append(idx)
    _seps.append(longest_line)
    print(_seps)
    print("*", lines[0])
    line = lines[0]
    _line = "{}{}".format(line, " " * longest_line)[0:longest_line]
    header = [
        line[_seps[_idx - 1]:_seps[_idx] + 1].strip() for _idx in range(1, len(_seps))
    ]
    # print(raw_data)
    _seps = _seps[:-1]
    new_seps = []
    # reorganize headers
    for _sep, _header in zip(_seps, header):
        if header:
            new_seps.append(_sep)
    new_seps.append(longest_line)
    raw_data = []
    for line in lines:
        _line = "{}{}".format(line, " " * longest_line)[0:longest_line]
        _parts = [
            line[new_seps[_idx - 1]:new_seps[_idx] + 1].strip() for _idx in range(1, len(_seps))
        ]
        raw_data.append(_parts)
    import pprint
    pprint.pprint(raw_data)
    # print(len(_seps), len(header))
    # print("H=", header)
