# -*- coding: utf-8 -*-
#
# Copyright (C) 2014,2016 Andreas Lang-Nevyjel
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


from __future__ import unicode_literals, print_function

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
    print("***", dump, type(dump))
    lines = dump.split('\n')
    header = lines[0].split()
    rows = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        data = line.split(' ')
        data = [escape_re.sub(unescape, d).strip() for d in data]
        if len(data) != len(header):
            # problem
            pass
        data = OrderedDict([(k, v) for (k, v) in zip(header, data)])
        # if available, apply the mapping function
        for (key, value) in data.iteritems():
            if key in mappers:
                data[key] = mappers[key](value)
        rows.append(data)

    return rows


def _parse_edid(blob):
    def _bits(bytes):
        bin_strs = ["{:08b}".format(ord(b)) for b in bytes]
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
    result['product'] = blob[10:12].encode('hex')
    result['serial'] = blob[12:16].encode('hex')
    result['week'] = ord(blob[16])
    result['year'] = ord(blob[17]) + 1990
    result['version'] = blob[18:19].encode('hex')
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
            try:
                self._process_xrandr(xrandr_dump)
            except Exception:
                # parse error
                pass

    def _process_lsblk(self, lsblk_dump):
        self._lsblk_dump = lsblk_dump
        entries = _parse_lsblk(lsblk_dump)
        type_entries = defaultdict(list)
        for e in entries:
            type_entries[e['TYPE']].append(e)

        name_object = {}
        for disk_entry in type_entries['disk']:
            hdd = HardwareHdd(lsblk_entry=disk_entry)
            self.hdds.append(hdd)
            name_object[hdd.device_name] = hdd
        # disk, partitions
        for part_entry in type_entries['part']:
            partition = Partition(lsblk_entry=part_entry)
            logical = LogicalDisc(lsblk_entry=part_entry)
            partition.logical = logical
            # add partition to the disk
            parent_hdd = name_object.get(partition._parent)
            if parent_hdd:
                parent_hdd.partitions.append(partition)
        # logical disk
        for entry in entries:
            logical = LogicalDisc(lsblk_entry=entry)
            if logical.mount_point:
                self._mount_point_logical_disks[logical.mount_point] = \
                    logical

    def _process_lshw(self, lshw_dump):
        for sub_tree in lshw_dump.xpath(
            "//node[@id='cpu' and @class='processor']"
        ):
            self.cpus.append(HardwareCPU(sub_tree))

        sub_tree = lshw_dump.xpath(
            "/list/node/node[@id='core' and @class='bus']"
            "/node[@id='memory' and @class='memory']"
        )[0]
        self.memory = HardwareMemory(sub_tree)

        for sub_tree in lshw_dump.xpath(
            "//node[@id='memory' and @class='memory']/node"
        ):
            memory_module = MemoryModule(sub_tree)
            # don't add empty slots
            if memory_module.capacity:
                self.memory_modules.append(memory_module)

        for sub_tree in lshw_dump.xpath(
            "//node[@id='display' and @class='display']"
        ):
            self.gpus.append(HardwareGPU(sub_tree))

        # add further disk information not available from lsblk
        device_hdds = {hdd.device_name: hdd for hdd in self.hdds}
        for sub_tree in lshw_dump.xpath(
            "//node[@id='disk' and @class='disk']"
        ):
            lshw_hdd = HardwareHdd(sub_tree)
            hdd = device_hdds.get(lshw_hdd.device_name)
            if hdd:
                hdd.update(lshw_hdd)

        for sub_tree in lshw_dump.xpath(
                "//node[@id='network' and @class='network']"):
            self.network_devices.append(
                HardwareNetwork(sub_tree)
            )

    def _process_win32(self, win32_tree):
        self._win32_tree = win32_tree
        for sub_tree in win32_tree['Win32_Processor']:
            self.cpus.append(HardwareCPU(win32_tree=sub_tree))

        self.memory = HardwareMemory(
            win32_tree=win32_tree['Win32_ComputerSystem'][0])

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
                for (key, lines) in self._infos.iteritems():
                    if len(lines) == 1:
                        res[key] = lines[0]
                    else:
                        res[key] = [l for l in lines if l]
                if 'EDID' in res:
                    res['EDID'] = str.decode(''.join(res['EDID']), 'hex')
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

        lines = xrandr_dump.split('\n')
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
                        map(int, resolution.resolution.split('x'))
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
        for (name, value) in self.__dict__.iteritems():
            if not name.startswith('_') and value is not None:
                infos.append('{}={}'.format(name, repr(value)))
        return '{}({})'.format(self.__class__.__name__, ', '.join(infos))

    def update(self, hw_instance):
        for (name, value) in hw_instance.__dict__.iteritems():
            cur_value = getattr(self, name)
            if cur_value is None:
                setattr(self, name, value)

    def _populate_lshw(self):
        for (prop_name, (xpath_expr, func)) in self.LSHW_ELEMENTS.iteritems():
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
        for (prop_name, (dict_key, func)) in self.WIN32_ELEMENTS.iteritems():
            value = self._tree[dict_key] if dict_key else None
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)

        self._path_w32 = self._tree['_path']

    def _populate_dmi(self):
        for (prop_name, (handle_key, func)) in self.DMI_ELEMENTS.iteritems():
            value = self._tree[handle_key]['value']
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)


class HardwareCPU(HardwareBase):
    """Represents the physical CPU."""

    LSHW_ELEMENTS = {
        'product': ('product', unicode),
        'manufacturer': ('vendor', unicode),
        'version': ('version', unicode),
        'serial': ('serial', unicode),
        'number_of_cores': ("configuration/setting[@id='cores']/@value", int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394373%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'product': ('Name', unicode),
        'manufacturer': ('Manufacturer', unicode),
        'version': ('Version', unicode),
        'serial': ('ProcessorId', unicode),
        'number_of_cores': ('NumberOfCores', int),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.product = None
        self.manufacturer = None
        self.version = None
        self.serial = None
        self.number_of_cores = None
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
        'manufacturer': ('Manufacturer', unicode),
        'capacity': ('Capacity', int),
        'serial': ('SerialNumber', unicode),
        'bank_label': ('DeviceLocator', unicode),
        'form_factor': ('FormFactor', int),
        'type': ('MemoryType', int),
    }
    DMI_ELEMENTS = {
        'manufacturer': ('Manufacturer', unicode),
        'capacity': ('Size', parse_size),
        'serial': ('Serial Number', unicode),
        'bank_label': ('Bank Locator', unicode),
        'form_factor': ('Form Factor', unicode),
        'type': ('Type', unicode),
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
        'description': ('description', unicode),
        'product': ('product', unicode),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394512%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'description': ('Description', unicode),
        'product': ('Name', unicode),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None):
        self.description = None
        self.product = None
        super(HardwareGPU, self).__init__(lshw_dump, win32_tree, dmi_handle)


class HardwareHdd(HardwareBase):
    """Represents a hard disc device."""

    LSHW_ELEMENTS = {
        'description': ('description', unicode),
        'product': ('product', unicode),
        'device_name': ('logicalname', unicode),
        'serial': ('serial', unicode),
        # "size" is the size of the physical disk whereas "capacity" is the
        # size of the corresponding file system (cf. the output of "lsblk")
        'size': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394132%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'description': ('Description', unicode),
        'product': ('Caption', unicode),
        'device_name': ('DeviceID', unicode),
        'serial': ('SerialNumber', unicode),
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

    def _populate_lsblk(self):
        entry = self._lsblk_entry
        self.device_name = entry['KNAME']
        self.product = entry['MODEL']


class Partition(HardwareBase):
    """Represents the partition information as available from the partition
    table."""

    LSHW_ELEMENTS = {
        'size': (None, unicode),
        'index': (None, int),
        'bootable': (None, unicode),
        'device_name': ('logicalname', unicode),
        'type': (None, unicode),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394135(v=vs.85).aspx
    # Note: WMI doesn't provide any information about the partition type hex.
    WIN32_ELEMENTS = {
        'size': ('Size', int),
        'index': ('Index', int),
        'bootable': ('Bootable', bool),
        'device_name': ('DeviceID', unicode),
        'type': ('Type', unicode),
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
        self.type = entry['FSTYPE'].lower()
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
        'device_name': ('DeviceID', unicode),
        'mount_point': ('DeviceID', unicode),
        'file_system': ('FileSystem', unicode.lower),
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
        'product': ('product', unicode),
        'manufacturer': ('vendor', unicode),
        'device_name': ('logicalname', unicode),
        'mac_address': ('serial', format_mac_address),
        'speed': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394216(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'product': ('ProductName', unicode),
        'manufacturer': ('Manufacturer', unicode),
        'device_name': ('NetConnectionID', unicode),
        'mac_address': ('MACAddress', unicode),
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
        'manufacturer': ('MonitorManufacturer', unicode),
        'product': ('Caption', unicode),
        'serial': (None, unicode),
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
