from _collections import defaultdict


def format_mac_address(mac_address):
    return mac_address.upper()


class Hardware(object):
    def __init__(self, lshw_tree=None, win32_tree=None):
        self.cpus = []
        self.memory = None
        self.memory_modules = []
        self.gpus = []
        self.hdds = []
        self.network_devices = []

        if lshw_tree is not None:
            for sub_tree in lshw_tree.xpath(
                    "//node[@id='cpu' and @class='processor']"):
                self.cpus.append(HardwareCPU(sub_tree))

            sub_tree = lshw_tree.xpath(
                "/list/node/node[@id='core' and @class='bus']"
                "/node[@id='memory' and @class='memory']")[0]
            self.memory = HardwareMemory(sub_tree)

            for sub_tree in lshw_tree.xpath(
                    "//node[@id='memory' and @class='memory']/node"):
                memory_module = MemoryModule(sub_tree)
                # don't add empty slots
                if memory_module.capacity:
                    self.memory_modules.append(memory_module)

            for sub_tree in lshw_tree.xpath(
                    "//node[@id='display' and @class='display']"):
                self.gpus.append(HardwareGPU(sub_tree))

            for sub_tree in lshw_tree.xpath(
                    "//node[@id='disk' and @class='disk']"):
                self.hdds.append(HardwareHdd(sub_tree))

            for sub_tree in lshw_tree.xpath(
                    "//node[@id='network' and @class='network']"):
                self.network_devices.append(
                    HardwareNetwork(sub_tree)
                    )

        if win32_tree:
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

    def __init__(self, lshw_tree=None, win32_tree=None):
        self._check()

        self._tree = lshw_tree if lshw_tree is not None else win32_tree
        self._path_w32 = None

        if lshw_tree is not None:
            self._populate_lshw(lshw_tree)
        elif win32_tree:
            self._populate_win32(win32_tree)

    def __repr__(self):
        infos = []
        for (key, value) in self.__dict__.items():
            if not key.startswith('_') and value is not None:
                infos.append('{}={}'.format(key, repr(value)))
        return '{}({})'.format(self.__class__.__name__, ', '.join(infos))

    def _populate_lshw(self, lshw_tree):
        for (prop_name, (xpath_expr, func)) in self.LSHW_ELEMENTS.items():
            try:
                element = lshw_tree.xpath(xpath_expr)[0]
            except IndexError:
                continue
            try:
                value = element.text
            except AttributeError:
                value = element
            if func:
                value = func(value)
            setattr(self, prop_name, value)

    def _populate_win32(self, win32_tree):
        for (prop_name, (dict_key, func)) in self.WIN32_ELEMENTS.items():
            value = win32_tree[dict_key] if dict_key else None
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)

        self._path_w32 = win32_tree['_path']

    def _check(self):
        # Sanity check: The lshw and Win32 dict must define the same keys.
        if not set(self.LSHW_ELEMENTS) == set(self.WIN32_ELEMENTS):
            raise AssertionError


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
        'product': ('Description', str),
        'manufacturer': ('Manufacturer', str),
        'version': ('Version', str),
        'serial': ('ProcessorId', str),
        'number_of_cores': ('NumberOfCores', int),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.product = None
        self.manufacturer = None
        self.version = None
        self.serial = None
        self.number_of_cores = None
        super(HardwareCPU, self).__init__(lshw_tree, win32_tree)


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

    LSHW_ELEMENTS = {
        'manufacturer': ('vendor', str),
        'capacity': ('size', int),
        'serial': ('serial', str),
        'bank_label': ('slot', str),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394197(v=vs.85).aspxq
    WIN32_ELEMENTS = {
        'manufacturer': ('Manufacturer', str),
        'capacity': ('Capacity', int),
        'serial': ('SerialNumber', str),
        'bank_label': ('DeviceLocator', str),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.manufacturer = None
        self.capacity = None
        self.serial = None
        self.bank_label = None
        super(MemoryModule, self).__init__(
            lshw_tree=lshw_tree, win32_tree=win32_tree
        )


class HardwareGPU(HardwareBase):
    """Represents a graphics adapter."""

    LSHW_ELEMENTS = {
        'description': ('description', str),
        'product': ('product', str),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394512%28v=vs.85%29.aspx
    WIN32_ELEMENTS = {
        'description': ('Description', str),
        'product': ('VideoProcessor', str),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.description = None
        self.product = None
        super(HardwareGPU, self).__init__(lshw_tree, win32_tree)


class HardwareHdd(HardwareBase):
    """Represents a hard disc device."""

    LSHW_ELEMENTS = {
        'description': ('description', str),
        'product': ('product', str),
        'device_name': ('logicalname', str),
        'serial': ('serial', str),
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

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.description = None
        self.product = None
        self.device_name = None
        self.serial = None
        self.size = None

        self.partitions = []
        super(HardwareHdd, self).__init__(lshw_tree, win32_tree)


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
    WIN32_ELEMENTS = {
        'size': ('Size', int),
        'index': ('Index', int),
        'bootable': ('Bootable', bool),
        'device_name': ('DeviceID', str),
        'type': ('Type', str),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.size = None
        self.index = None
        self.bootable = None
        self.device_name = None

        self.logical = None

        super(Partition, self).__init__(lshw_tree=lshw_tree,
            win32_tree=win32_tree)

    def _set_from_logical_win32(self, logical_disc):
        self.free_space = logical_disc.free_space
        self.file_system = logical_disc.file_system


class LogicalDisc(HardwareBase):
    """Represents the file system level information."""

    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394173(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'device_name': ('DeviceID', str),
        'file_system': ('FileSystem', str),
        'size': ('Size', int),
        'free_space': ('FreeSpace', int),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.device_name = None
        self.file_system = None
        self.size = None
        self.free_space = None
        super(LogicalDisc, self).__init__(lshw_tree=lshw_tree,
            win32_tree=win32_tree)

    def _check(self):
        pass


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
        'device_name': ('DeviceID', str),
        'mac_address': ('MACAddress', str),
        'speed': ('Speed', int),
    }

    def __init__(self, lshw_tree=None, win32_tree=None):
        self.product = None
        self.manufacturer = None
        self.device_name = None
        self.mac_address = None
        self.speed = None  # bit/s
        super(HardwareNetwork, self).__init__(lshw_tree, win32_tree)
