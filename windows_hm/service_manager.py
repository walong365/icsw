import subprocess
import sys
import time
import os

NSSM_BIN = "nssm.exe"

def cleanup_service(service_name):
    # stop service, if running
    subprocess.call([NSSM_BIN, "stop", service_name])

    # wait for service to stop, if running
    while True:
        try:
            output = subprocess.check_output(["nssm.exe", "status", service_name])
            if output.strip() == "SERVICE_STOPPED":
                break
            time.sleep(1)
        except subprocess.CalledProcessError:
            break

    # remove old service
    subprocess.call([NSSM_BIN, "remove", service_name, "confirm"])

def install_service(service_name):
    cleanup_service(service_name)

    install_cmd = "\"{} \"{}\"\"".format(os.path.join(os.getcwd(), "python.exe"),
        os.path.join(os.getcwd(), "\Lib\site-packages\initat\host_monitoring\main_windows.py"))

    # install service
    subprocess.check_call([NSSM_BIN, "install", service_name, install_cmd])

    # set various logging settings
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppStdout", os.path.join(os.getcwd(), "log.txt")])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppStderr", os.path.join(os.getcwd(), "log.txt")])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppStdoutCreationDisposition", "4"])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppStderrCreationDisposition", "4"])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppRotateFiles", "1"])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppRotateOnline", "1"])
    subprocess.check_call([NSSM_BIN, "set", service_name, "AppRotateBytes", "1000000"])


if __name__ == "__main__":
    service_name = sys.argv[1]
    install = sys.argv[2] == "install"

    if install:
        install_service(service_name)
    else:
        cleanup_service(service_name)

    sys.exit(0)
