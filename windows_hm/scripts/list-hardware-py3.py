import wmi
import bz2
import base64
import json

if __name__=="__main__":
    c = wmi.WMI()

    #Win32_PhysicalMemory class
    #https://msdn.microsoft.com/en-us/library/windows/desktop/aa394347%28v=vs.85%29.aspx

    _info_dict = {}
    _info_dict['memory'] = []
    _info_dict['cpu'] = []
    _info_dict['gpu'] = []
    _info_dict['hdd'] = []
    _info_dict['logical'] = []

    wql = "Select * From Win32_PhysicalMemory"
    for item in c.query(wql):
        _sub_info_dict = {}
        _sub_info_dict['banklabel'] = item.BankLabel if item.BankLabel else "Unknown"
        _sub_info_dict['capacity'] = item.Capacity
        _sub_info_dict['formfactor'] = item.FormFactor
        _sub_info_dict['memorytype'] = item.MemoryType
        _sub_info_dict['manufacturer'] = item.Manufacturer
        _info_dict['memory'].append(_sub_info_dict)

    #Win32_Processor class
    #https://msdn.microsoft.com/en-us/library/windows/desktop/aa394373%28v=vs.85%29.aspx

    wql = "Select * From Win32_Processor"
    for item in c.query(wql):
        _sub_info_dict = {}
        _sub_info_dict['name'] = item.Name
        _sub_info_dict['numberofcores'] = item.NumberOfCores
        _info_dict['cpu'].append(_sub_info_dict)

    #Win32_VideoController class
    #https://msdn.microsoft.com/en-us/library/windows/desktop/aa394512%28v=vs.85%29.aspx

    wql = "Select * From Win32_VideoController"
    for item in c.query(wql):
        _sub_info_dict = {}
        _sub_info_dict['name'] = item.Caption
        _sub_info_dict['driverversion'] = item.DriverVersion
        _info_dict['gpu'].append(_sub_info_dict)

    # Win32_DiskDrive class
    #https://msdn.microsoft.com/en-us/library/windows/desktop/aa394132%28v=vs.85%29.aspx

    wql = "Select * From Win32_DiskDrive"
    for item in c.query(wql):
        _sub_info_dict = {}
        _sub_info_dict['name'] = item.Caption
        _sub_info_dict['serialnumber'] = item.SerialNumber
        _sub_info_dict['size'] = item.Size
        _info_dict['hdd'].append(_sub_info_dict)

    print(json.dumps(_info_dict))


    # Win32_DiskDrive class
    #https://msdn.microsoft.com/en-us/library/windows/desktop/aa394173%28v=vs.85%29.aspx

    wql = "Select * From Win32_LogicalDisk"
    for item in c.query(wql):
        _sub_info_dict = {}
        _sub_info_dict['name'] = item.Caption
        _sub_info_dict['size'] = item.Size
        _sub_info_dict['free'] = item.FreeSpace
        _info_dict['logical'].append(_sub_info_dict)


    output = json.dumps(_info_dict)
    print(base64.b64encode(bz2.compress(bytes(output, "utf-8"))))