import subprocess
from common import nrpe_encode

if __name__=="__main__":
    output = None
    with subprocess.Popen([".\scripts\python\lstopo-no-graphics.exe", "--of", "xml"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        print((nrpe_encode(output)))
