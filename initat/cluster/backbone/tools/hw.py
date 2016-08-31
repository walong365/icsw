
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

            for sub_tree in win32_tree['Win32_VideoController']:
                self.gpus.append(HardwareGPU(win32_tree=sub_tree))

            for sub_tree in win32_tree['Win32_DiskDrive']:
                self.hdds.append(HardwareHdd(win32_tree=sub_tree))

            for sub_tree in win32_tree['Win32_NetworkAdapter']:
                if sub_tree['PhysicalAdapter']:
                    self.network_devices.append(
                        HardwareNetwork(win32_tree=sub_tree))


class HardwareBase(object):
    # a dict of the form {prop_name: (xpath_expr, func)}
    LSHW_ELEMENTS = {}
    # a dict of the form {prop_name: (dict_key, func)}
    WIN32_ELEMENTS = {}

    def __init__(self, lshw_tree=None, win32_tree=None):
        # Sanity check: The lshw and Win32 dict must define the same keys.
        if not set(self.LSHW_ELEMENTS) == set(self.WIN32_ELEMENTS):
            raise AssertionError

        self._tree = lshw_tree if lshw_tree is not None else win32_tree

        if lshw_tree is not None:
            self._populate_lshw(lshw_tree)
        elif win32_tree:
            self._populate_win32(win32_tree)

    def __unicode__(self):
        infos = []
        for (key, value) in self.__dict__.items():
            if value:
                infos.append('{}: {}'.format(key, value))
        return ', '.join(infos)

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
            value = win32_tree[dict_key]
            if value is not None and func:
                value = func(value)
            setattr(self, prop_name, value)


class HardwareCPU(HardwareBase):
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
    LSHW_ELEMENTS = {
        'size': ('size', int),
    }
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa394102(v=vs.85).aspx
    WIN32_ELEMENTS = {
        'size': ('TotalPhysicalMemory', int),
    }


class HardwareGPU(HardwareBase):
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
        super(HardwareHdd, self).__init__(lshw_tree, win32_tree)


class HardwareNetwork(HardwareBase):
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
