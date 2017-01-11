import subprocess
from common import nrpe_encode
       
if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\pciutils\lspci.exe", "-v", "-mm"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        print((nrpe_encode(output)))
