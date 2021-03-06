import subprocess
import sys
import time
import os

NSSM_BIN = "nssm.exe"

SERVICE_STOPPED = b"S\x00E\x00R\x00V\x00I\x00C\x00E\x00_\x00S\x00T\x00O\x00P\x00P\x00E\x00D\x00\r\x00\n\x00"


def cleanup_service(service_name):
    # stop service, if running
    try:
        subprocess.check_output([NSSM_BIN, "stop", service_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        pass
        
    # wait for service to stop, if running
    while True:
        try:
            output = subprocess.check_output(["nssm.exe", "status", service_name], stderr=subprocess.STDOUT)
            if output == SERVICE_STOPPED:
                break
            time.sleep(1)
        except subprocess.CalledProcessError:
            break

    # remove old service
    try:
        subprocess.check_output([NSSM_BIN, "remove", service_name, "confirm"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        pass


def install_service(service_name, version_string):
    cleanup_service(service_name)

    python_path = os.path.join(os.getcwd(), "python.exe")
    module_path = "\"{}\"".format(os.path.join(os.getcwd(), "Lib\site-packages\initat\host_monitoring\main_binary.py"))

    # install service
    subprocess.check_output([NSSM_BIN, "install", service_name, python_path, "-B", module_path],
                            stderr=subprocess.STDOUT)

    # set various logging settings
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppStdout", os.path.join(os.getcwd(), "log.txt")],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppStderr", os.path.join(os.getcwd(), "log.txt")],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppStdoutCreationDisposition", "4"],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppStderrCreationDisposition", "4"],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppRotateFiles", "1"],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppRotateOnline", "1"],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "AppRotateBytes", "1000000"],
                            stderr=subprocess.STDOUT)
    subprocess.check_output([NSSM_BIN, "set", service_name, "Description", version_string],
                            stderr=subprocess.STDOUT)
    
    try:
        subprocess.check_output([NSSM_BIN, "start", service_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        pass
    
if __name__ == "__main__":
    _service_name = sys.argv[1]
    install = sys.argv[2] == "install"
    try:
        version_string = sys.argv[3]
    except:
        version_string = None

    if install:
        install_service(_service_name, version_string)
    else:
        cleanup_service(_service_name)

    sys.exit(0)
