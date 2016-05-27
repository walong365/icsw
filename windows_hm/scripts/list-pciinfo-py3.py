import subprocess
import json

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\pciutils\lspci.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        print(output.decode())