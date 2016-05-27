import subprocess

if __name__=="__main__":
    with subprocess.Popen([".\scripts\python\dmidecode212.exe", "--dump"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()
        
        print(output)
    
    
        
    