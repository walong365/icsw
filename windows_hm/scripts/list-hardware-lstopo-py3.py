import subprocess


if __name__=="__main__":
    output = None
    with subprocess.Popen([".\scripts\python\lstopo-no-graphics.exe", "--of", "xml"], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()

    lines = str(output).split('\\r\\n')
    for line in lines:
        print(line)