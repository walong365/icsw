import subprocess
from common import nrpe_encode

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\dmidecode212.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        print((nrpe_encode(output)))
