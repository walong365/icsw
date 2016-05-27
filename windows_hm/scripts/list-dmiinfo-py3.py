import subprocess
import json

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\dmidecode212.exe"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        
        lines = []
        
        sh_first_line = True
        
        for line in str(output).split("\\r\\n"):
            if sh_first_line:
                lines.append(line[2:])
                sh_first_line = False
            else:
                lines.append(line)
            if line == "End Of Table":
                break
        
        print(json.dumps(lines))