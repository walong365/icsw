# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
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

""" host-monitoring, main part """

import sys

from initat.tools import configfile, process_tools
from initat.constants import IS_PYINSTALLER_BINARY

if IS_PYINSTALLER_BINARY:
    import html
    import html.parser
    import requests_futures
    import requests_futures.sessions

    _ = html
    _ = requests_futures


def main():
    global_config = configfile.get_global_config(
        process_tools.get_programm_name(),
        single_process_mode=True
    )
    from initat.host_monitoring.server import ServerCode
    ret_state = ServerCode(global_config).loop()

    return ret_state


def cleanup_old_files():
    import shutil
    import os

    for path in os.listdir("."):
        _, ext = os.path.splitext(path)
        if ext == ".icsw_old":
            try:
                shutil.rmtree(path)
            except NotADirectoryError:
                try:
                    os.remove(path)
                except PermissionError:
                    pass
            except PermissionError:
                pass

if __name__ == "__main__":
    if not IS_PYINSTALLER_BINARY:
        cleanup_old_files()
    sys.exit(main())
