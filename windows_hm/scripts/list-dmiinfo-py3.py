import subprocess
import json

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\dmidecode212.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        
        lines = []
        
        for line in output.decode().split("\r\n"):
            lines.append(line)
            if line == "End Of Table":
                break
        
        print(json.dumps(lines))