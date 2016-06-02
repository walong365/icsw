import subprocess
import base64
import bz2

if __name__=="__main__":
    output = None
    with subprocess.Popen([".\scripts\python\lstopo-no-graphics.exe", "--of", "xml"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()

        print(base64.b64encode(bz2.compress(output)))