from collections import defaultdict
import wmi
import json
from common import nrpe_encode


def path(wmi_object):
    return(wmi_object.Path_.Path)


if __name__=="__main__":
    c = wmi.WMI()
    mapping_classes = [
        'Win32_DiskDriveToDiskPartition', 'Win32_LogicalDiskToPartition',
    ]
    classes = [
        'Win32_PhysicalMemory', 'Win32_PhysicalMemoryArray',
        'Win32_Processor', 'Win32_VideoController', 'Win32_DiskDrive',
        'Win32_DiskPartition', 'Win32_LogicalDisk', 'Win32_NetworkAdapter',
        'Win32_ComputerSystem', 'Win32_DesktopMonitor',
    ]

    mapping_info = defaultdict(list)
    for class_name in mapping_classes:
        results = c.query('SELECT * FROM {}'.format(class_name))
        for result in results:
            key = path(result.Dependent)
            mapping_info[class_name].append((key, path(result.Antecedent)))

    info = defaultdict(list)
    for class_name in classes:
        results = c.query('SELECT * FROM {}'.format(class_name))
        for result in results:
            info_result = {'_path': path(result)}
            for prop in result.properties.keys():
                value = getattr(result, prop)
                info_result[prop] = value
            info[class_name].append(info_result)

    info.update(mapping_info)
    output = json.dumps(info)
    print(nrpe_encode(output))
