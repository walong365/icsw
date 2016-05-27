import subprocess
import json

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\pciutils\lspci.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        
        lines = output.decode().split("\r\n")
        
        print(json.dumps([line for line in lines if line]))