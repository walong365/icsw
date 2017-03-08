# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
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

import subprocess
import json
import sys
import os


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
    if connection_type == "rdesktop":
        command = ["wfreerdp.exe", "/f", "/u:{}".format(username), "/p:{}".format(password), "/v:{}".format(hostname)]
    elif connection_type == "ssh":
        command = ["putty.exe", "-l", username, "-pw", password, hostname]

    if command:
        subprocess.call(command)

if __name__ == "__main__":
    main()
