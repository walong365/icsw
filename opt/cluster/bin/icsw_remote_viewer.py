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
    subprocess.check_call([XDG_DESKTOP_MENU_BINARY, "install", "--novendor", XDG_DESKTOP_MENU_CONFIG_FILE])


def main():
    config_file = sys.argv[1]

    with open(config_file, "rb") as f:
        config_dict = json.loads(f.read().decode())

    os.remove(config_file)

    username = config_dict["ssh_username"]
    password = config_dict["ssh_password"]
    hostname = config_dict["host"]

    ssh_command = ["sshpass", "-p", "{}".format(password), "ssh", "{}@{}".format(username, hostname)]

    konsole_binary = shutil.which("konsole")
    if konsole_binary:
        command = [konsole_binary, "--new-tab", "-e"]
        command.extend(ssh_command)
        subprocess.call(command)
        return

    gnome_terminal_binary = shutil.which("gnome-terminal")
    if gnome_terminal_binary:
        command = [gnome_terminal_binary, "-e", '{}'.format(" ".join(ssh_command))]
        subprocess.call(command)
        return

if __name__ == "__main__":
    if sys.argv[1] in ["install", "uninstall"]:
        if XGD_MIME_BINARY and XDG_DESKTOP_MENU_BINARY:
            if sys.argv[1] == "install":
                sys.exit(install())
            elif sys.argv[1] == "uninstall":
                sys.exit(uninstall())
        else:
            print("xdg-mime or xdg-desktop-menu binary not found!")
    else:
        sys.exit(main())
