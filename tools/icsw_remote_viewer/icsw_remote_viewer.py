#!/usr/bin/python3-init

import sys
import shutil
import subprocess
import os
import json


def main():
    config_file = sys.argv[1]

    with open(config_file, "rb") as f:
        config_dict = json.loads(f.read().decode())

    os.remove(config_file)

    username = config_dict["ssh_username"]
    password = config_dict["ssh_password"]
    hostname = config_dict["host"]

    konsole_binary = shutil.which("konsole")
    if konsole_binary:
        subprocess.call([konsole_binary, "--new-tab", "-e", "sshpass", "-p", "{}".format(password), "ssh",
                         "{}@{}".format(username, hostname)])

if __name__ == "__main__":
    sys.exit(main())
