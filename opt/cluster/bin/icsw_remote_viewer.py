#!/usr/bin/python3-init
#
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

import argparse
import json
import logging
import os
import shutil
import subprocess
import time
import sys
from enum import Enum

from initat.constants import CLUSTER_DIR

VIEWER_DIR = os.path.join(
    CLUSTER_DIR,
    "share",
    "icsw_remote_viewer",
)

XDG_DESKTOP_MENU_CONFIG_FILE = os.path.join(
    VIEWER_DIR,
    "icsw_remote_viewer.desktop"
)
XGD_MIME_CONFIG = os.path.join(
    VIEWER_DIR,
    "icsw_remote_viewer.xml"
)


class BinaryEnum(Enum):
    xdg_mime = "xdg-mime"
    xdg_desktop_menu = "xdg-desktop-menu"
    gnome_terminal = "gnome-terminal"
    rdesktop = "rdesktop"
    konsole = "konsole"
    sshpass = "sshpass"


class RemoteHandler(object):
    def __init__(self):
        self.uid = os.getuid()
        self._init_logging()
        self.logger.info("starting RemoteHandler, pid={:d}".format(os.getpid()))
        self._find_binaries()
        self._parse()

    def _init_logging(self):
        formatter = logging.Formatter("%(asctime)s : %(levelname)-5s (%(threadName)s.%(process)d) %(message)s")
        fh = logging.FileHandler("/tmp/.remote_viewer_{:d}".format(os.getuid()))
        fh.setFormatter(formatter)
        logger = logging.Logger(name="remote_viewer")
        logger.addHandler(fh)
        self.logger = logger

    def _close_logging(self):
        self.logger.info("done")
        del self.logger

    def _find_binaries(self):
        self.binaries = {}
        for _bin_enum in BinaryEnum:
            _path = shutil.which(_bin_enum.value)
            if _path:
                self.logger.info("found '{}' at {}".format(_bin_enum.value, _path))
            else:
                self.logger.error("binary '{}' not found".format(_bin_enum.value))
            self.binaries[_bin_enum] = _path

    def _parse(self):
        ap = argparse.ArgumentParser()
        _options = ["connect", "install", "uninstall"]
        ap.add_argument(
            "--action",
            default=_options[0],
            type=str,
            choices=_options,
            help="what to do [%(default)s]",
        )
        ap.add_argument(
            "--config-file",
            default="",
            type=str,
            help="configfile to operate on [%(default)s]",
        )
        ap.add_argument(
            "--keep",
            default=False,
            action="store_true",
            help="keep configfile (no deletion) [%(default)s]",
        )
        self.opts = ap.parse_args()
        self.logger.info("parsed options: {}".format(str(self.opts)))

    def handle(self):
        _result = getattr(self, "handle_{}".format(self.opts.action))()
        self._close_logging()
        return _result

    def _interpret_command(self, cmd_list):
        _new_cmd_list = []
        for entry in cmd_list:
            if isinstance(entry, BinaryEnum):
                _path = self.binaries[entry]
                if _path:
                    _new_cmd_list.append(_path)
                else:
                    self.logger.error("Binary {} not found".format(str(entry)))
            else:
                _new_cmd_list.append(entry)
        return _new_cmd_list

    def handle_connect(self):
        if not self.opts.config_file:
            self.logger.error("No configfile given")
        else:
            with open(self.opts.config_file, "rb") as f:
                config_dict = json.loads(f.read().decode())
            if not self.opts.keep:
                self.logger.warning("removing config-file {}".format(self.opts.config_file))
                os.remove(self.opts.config_file)

            # print("*", config_dict)
            username = config_dict["username"]
            password = config_dict["password"]
            hostname = config_dict["host"]
            connection_type = config_dict["connection_type"]

            command = []
            if connection_type == "ssh":
                command = [
                    BinaryEnum.sshpass,
                    "-p",
                    "{}".format(password),
                    "ssh",
                    "{}@{}".format(username, hostname)
                ]
            elif connection_type == "rdesktop":
                command = [
                    BinaryEnum.rdesktop,
                    "-u",
                    username,
                    "-p",
                    password,
                    hostname
                ]

            # check for konsoles
            if self.binaries[BinaryEnum.konsole]:
                command = [
                    BinaryEnum.konsole,
                    "--hold",
                    "--new-tab",
                    "-e",
                    " ".join(self._interpret_command(command))
                ]
            elif self.binaries[BinaryEnum.gnome_terminal]:
                command = [
                    BinaryEnum.gnome_terminal,
                    "-e",
                    '{}'.format(" ".join(self._interpret_command(command)))
                ]
            else:
                self.logger.error("no console command found")
                command = None
            if command:
                subprocess.call(self._interpret_command(command))
                return
        return 0

    def handle_install(self):
        self.handle_uninstall()
        self.logger.info("Installing handlers for icsw-remote-viewer files")
        self._call_commands(
            [
                BinaryEnum.xdg_mime,
                "install",
                "--novendor",
                XGD_MIME_CONFIG
            ],
            [
                BinaryEnum.xdg_desktop_menu,
                "install",
                "--novendor",
                XDG_DESKTOP_MENU_CONFIG_FILE
            ]
        )
        return 0

    def handle_uninstall(self):
        self.logger.info("Uninstalling handlers for icsw-remote-viewer files")
        self._call_commands(
            [
                BinaryEnum.xdg_mime,
                "uninstall",
                XGD_MIME_CONFIG
            ],
            [
                BinaryEnum.xdg_desktop_menu,
                "uninstall",
                XDG_DESKTOP_MENU_CONFIG_FILE
            ]
        )
        return 0

    def _call_commands(self, *cmd_list):
        self.logger.info("handling {:d} commands".format(len(cmd_list)))
        for _cmd in cmd_list:
            if self.binaries[_cmd[0]]:
                s_time = time.time()
                _cmd = self._interpret_command(_cmd)
                subprocess.check_call(
                    _cmd
                )
                e_time = time.time()
                self.logger.info(
                    "called '{}', took {:.2f} seconds".format(
                        " ".join(_cmd),
                        e_time - s_time
                    )
                )
            else:
                self.logger.error(
                    "binary {} is missing".format(
                        _cmd[0].value
                    )
                )


if __name__ == "__main__":
    sys.exit(RemoteHandler().handle())
