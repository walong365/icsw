from collections import defaultdict
import wmi
import bz2
import base64
import json

if __name__=="__main__":
    c = wmi.WMI()
    classes = ('Win32_PhysicalMemory', 'Win32_PhysicalMemoryArray',
        'Win32_Processor', 'Win32_VideoController', 'Win32_DiskDrive',
        'Win32_LogicalDisk', 'Win32_NetworkAdapter', 'Win32_ComputerSystem')

    info = defaultdict(list)
    for class_name in c.classes:
        if class_name not in classes:
            continue
        results = c.query('SELECT * FROM {}'.format(class_name))
        for result in results:
            info_result = {}
            for prop in result.properties.keys():
                value = getattr(result, prop)
                info_result[prop] = value
            info[class_name].append(info_result)

    output = json.dumps(info)
    print(base64.b64encode(bz2.compress(bytes(output, "utf-8"))))
