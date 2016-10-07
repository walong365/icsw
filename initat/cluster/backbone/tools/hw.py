from collections import defaultdict, OrderedDict
from enum import IntEnum
import re
from docutils.nodes import entry
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
    escape_re = re.compile('\\\\x(\d\d)')

    def to_bool(s):
        return bool(int(s))

    def to_int(s):
        return int(s) if s else None
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

    def unescape(match):
        return chr(int(match.groups()[0], base=16))

    lines = dump.split('\n')
    header = lines[0].split()
    rows = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        data = line.split(' ')
        data = [escape_re.sub(unescape, d).strip() for d in data]
        data = OrderedDict([(k, v) for (k, v) in zip(header, data)])
        for (field_name, func) in mappers.items():
            data[field_name] = func(data[field_name])
        rows.append(data)

    return rows


class Hardware(object):
    def __init__(self, lshw_dump=None, win32_tree=None, dmi_head=None,
                 lsblk_dump=None, partinfo_tree=None):
        self.cpus = []
        self.memory = None
        self.memory_modules = []
        self.gpus = []
        self.hdds = []
        self.logical_disks = []
        self.network_devices = []

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
                "//node[@id='cpu' and @class='processor']"):
            self.cpus.append(HardwareCPU(sub_tree))

        sub_tree = lshw_dump.xpath(
            "/list/node/node[@id='core' and @class='bus']"
            "/node[@id='memory' and @class='memory']")[0]
        self.memory = HardwareMemory(sub_tree)

        for sub_tree in lshw_dump.xpath(
                "//node[@id='memory' and @class='memory']/node"):
            memory_module = MemoryModule(sub_tree)
            # don't add empty slots
            if memory_module.capacity:
                self.memory_modules.append(memory_module)

        for sub_tree in lshw_dump.xpath(
                "//node[@id='display' and @class='display']"):
            self.gpus.append(HardwareGPU(sub_tree))

        # add further disk information not available from lsblk
        device_hdds = {hdd.device_name: hdd for hdd in self.hdds}
        for sub_tree in lshw_dump.xpath(
                "//node[@id='disk' and @class='disk']"):
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
            hdd.partitions = [partition_path_partitions[p]
                for p in disk_path_partition[hdd._path_w32]]
            self.hdds.append(hdd)

        for sub_tree in win32_tree['Win32_NetworkAdapter']:
            if sub_tree['PhysicalAdapter']:
                self.network_devices.append(
                    HardwareNetwork(win32_tree=sub_tree))

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
        for (name, value) in self.__dict__.items():
            if not name.startswith('_') and value is not None:
                infos.append('{}={}'.format(name, repr(value)))
        return '{}({})'.format(self.__class__.__name__, ', '.join(infos))

    def update(self, hw_instance):
        for (name, value) in hw_instance.__dict__.items():
            cur_value = getattr(self, name)
            if cur_value is None:
                setattr(self, name, value)

    def _populate_lshw(self):
        for (prop_name, (xpath_expr, func)) in self.LSHW_ELEMENTS.items():
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
        for (prop_name, (dict_key, func)) in self.WIN32_ELEMENTS.items():
            value = self._tree[dict_key] if dict_key else None
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)

        self._path_w32 = self._tree['_path']

    def _populate_dmi(self):
        for (prop_name, (handle_key, func)) in self.DMI_ELEMENTS.items():
            value = self._tree[handle_key]['value']
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)


class HardwareCPU(HardwareBase):
    """Represents the physical CPU."""

    LSHW_ELEMENTS = {
        'product': ('product', str),
        'manufacturer': ('vendor', str),
        'version': ('version', str),
        'serial': ('serial', str),
        'number_of_cores': ("configuration/setting[@id='cores']/@value", int),
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
#         'manufacturer': ('vendor', str),
#         'capacity': ('size', int),
#         'serial': ('serial', str),
#         'bank_label': ('slot', str),
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

    def _populate_lsblk(self):
        entry = self._lsblk_entry
        self.device_name = entry['KNAME']
        self.product = entry['MODEL']


class Partition(HardwareBase):
    """Represents the partition information as available from the partition
    table."""

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
        'device_name': ('DeviceID', str),
        'mount_point': ('DeviceID', str),
        'file_system': ('FileSystem', unicode.lower),
        'size': ('Size', int),
        'free_space': ('FreeSpace', int),
    }

    def __init__(self, lshw_dump=None, win32_tree=None, dmi_handle=None,
            lsblk_entry=None):
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
