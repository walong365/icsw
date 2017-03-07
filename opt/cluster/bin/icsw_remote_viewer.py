#!/usr/bin/python3-init
#
# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

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

    username = config_dict["username"]
    password = config_dict["password"]
    hostname = config_dict["host"]
    connection_type = config_dict["connection_type"]

    command = []
    if connection_type == "ssh":
        command = ["sshpass", "-p", "{}".format(password), "ssh", "{}@{}".format(username, hostname)]
    elif connection_type == "rdesktop":
        command = ["rdesktop", "-u", username, "-p", password]

    konsole_binary = shutil.which("konsole")
    if konsole_binary:
        command = [konsole_binary, "--new-tab", "-e"]
        command.extend(command)
        subprocess.call(command)
        return

    gnome_terminal_binary = shutil.which("gnome-terminal")
    if gnome_terminal_binary:
        command = [gnome_terminal_binary, "-e", '{}'.format(" ".join(command))]
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
