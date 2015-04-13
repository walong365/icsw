#!/usr/bin/python-init -Otu
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cbc_tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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

""" modify the openmpi_version file """

import os
import pprint
import sys

SHARE_DIR = "/opt/cluster/share"

VERS_DIR = os.path.join(SHARE_DIR, "source-versions")

SYSTEM_LIST = ["hpl", "libgoto", "mpich", "openmpi", "sge"]


def main():
    # cleanup old files
    for _entry in os.listdir(SHARE_DIR):
        if _entry in ["mpich_version", "openmpi_versions"]:
            os.unlink(os.path.join(SHARE_DIR, _entry))
    for _sys in SYSTEM_LIST:
        _sys_dir = os.path.join(SHARE_DIR, "sources", _sys)
        _entries = []
        _search_str = {"libgoto": "gotoblas"}.get(_sys, _sys)
        for _entry in os.listdir(_sys_dir):
            if _entry.lower().count(_search_str):
                _parts = [_part for _part in _entry.split("-")[1].split(".") if _part.isdigit()]
                _vers = ".".join(_parts)
                _entries.append((_vers, os.path.join(_sys_dir, _entry)))
        _vers_file = os.path.join(VERS_DIR, "{}_versions".format(_sys))
        file(_vers_file, "w").write("\n".join(["{} {}".format(_vers, _entry) for _vers, _entry in _entries] + [""]))
        print("content of version file {}:".format(_vers_file))
        for _vers, _entry in _entries:
            print("    {} -> {}".format(_vers, _entry))

if __name__ == "__main__":
    main()
