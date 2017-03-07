#!/usr/bin/python3-init

import sys
import shutil
import subprocess
import os
import json

XDG_DESKTOP_MENU_CONFIG_FILE = "/opt/cluster/share/icsw_remote_viewer/icsw_remote_viewer.desktop"
XGD_MIME_CONFIG = "/opt/cluster/share/icsw_remote_viewer/icsw_remote_viewer.xml"

XGD_MIME_BINARY = shutil.which("xdg-mime")
XDG_DESKTOP_MENU_BINARY = shutil.which("xdg-desktop-menu")


def uninstall():
    subprocess.check_call([XGD_MIME_BINARY, "uninstall", XGD_MIME_CONFIG])
    subprocess.check_call([XDG_DESKTOP_MENU_BINARY, "uninstall", XDG_DESKTOP_MENU_CONFIG_FILE])


def install():
    uninstall()
    subprocess.check_call([XGD_MIME_BINARY, "install", "--novendor", XGD_MIME_CONFIG])
    subprocess.check_call([XDG_DESKTOP_MENU_BINARY, "uninstall", "--novendor", XDG_DESKTOP_MENU_CONFIG_FILE])


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
    if len(sys.argv) > 1:
        if XGD_MIME_BINARY and XDG_DESKTOP_MENU_BINARY:
            if sys.argv[1] == "install":
                sys.exit(install())
            elif sys.argv[1] == "uninstall":
                sys.exit(uninstall())
        else:
            print("xdg-mime or xdg-desktop-menu binary not found!")
    else:
        sys.exit(main())
