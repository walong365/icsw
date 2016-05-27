import subprocess
import json

       
if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\pciutils\lspci.exe", "-v", "-mm"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        
        items = []
        
        info_dict = {}
        for line in output.decode().split("\r\n"):
            if len(line) == 0:
                if len(info_dict) > 0:
                    items.append(info_dict)
                    info_dict = {}
            if line.startswith("Slot:"):
                info_dict['slot'] = line.split("\t", 1)[1]
                
                comps = info_dict['slot'].split(":")
                bus = comps[0]
                
                comps = comps[1].split(".")
                slot = comps[0]
                func = comps[1]
                
                info_dict['bus'] = bus
                info_dict['slot'] = slot
                info_dict['func'] = func               
            elif line.startswith("Class:"):
                info_dict['class'] = line.split("\t", 1)[1]
            elif line.startswith("Vendor:"):
                info_dict['vendor'] = line.split("\t", 1)[1]
            elif line.startswith("Device:"):
                info_dict['device'] = line.split("\t", 1)[1]
            elif line.startswith("SVendor:"):
                info_dict['svendor'] = line.split("\t", 1)[1]
            elif line.startswith("SDevice:"):
                info_dict['sdevice'] = line.split("\t", 1)[1]
            elif line.startswith("Rev:"):
                info_dict['rev'] = line.split("\t", 1)[1]
            
        print(json.dumps(items))