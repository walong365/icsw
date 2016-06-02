import subprocess
import bz2
import base64

       
if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\pciutils\lspci.exe", "-v", "-mm"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()

        print(base64.b64encode(bz2.compress(output)))