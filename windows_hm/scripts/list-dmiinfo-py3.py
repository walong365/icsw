import subprocess
import json
import base64
import bz2

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\dmidecode212.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()

        print(base64.b64encode(bz2.compress(output)))