import wmi
import subprocess


if __name__=="__main__":
    print("##############################")
    print("#############DMI##############")
    print("##############################")
    print("##############################")
    print()
    output = None
    with subprocess.Popen([".\scripts\python\dmidecode.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()


    lines = output.decode().split("\r\n")
    for line in lines:
        print(line)
    
    print("##############################")
    print("#############PNP##############")
    print("##############################")
    print("##############################")
    print()
    
    c = wmi.WMI()
    wql = "Select * From Win32_PNPEntity"
    for item in c.query(wql):
        print(item.Caption)
        print(item.Description)
        print(item.DeviceID)
        print(item.Status)
        print()
    
    print("##############################")
    print("###########NETWORK############")
    print("##############################")
    print("##############################")
    print()
    
    wql = "Select * From Win32_NetworkAdapterConfiguration"
    for item in c.query(wql):
        print(item.Caption)
        print(item.IPAddress)
        print(item.MACAddress)
        print()
        
    print("##############################")
    print("#############USB##############")
    print("##############################")
    print("##############################")
    print()
    
    wql = "Select * From Win32_USBController"
    for item in c.query(wql):
        print(item.Caption)
        print()