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

VERS_FILES = {
    "openmpi": "/opt/cluster/share/openmpi_versions",
    "mpich": "/opt/cluster/share/mpich_versions",
}


def main():
    mode = os.path.basename(sys.argv[0]).split("_")[0]
    VERS_FILE = VERS_FILES[mode]
    if len(sys.argv) < 3:
        print("Need version and filename")
        sys.exit(-1)
    new_v, new_f = (sys.argv[1], sys.argv[2])
    if not os.path.exists(new_f):
        print("File {} (version {}) does not exist".format(new_f, new_v))
        sys.exit(-2)
    if os.path.isfile(VERS_FILE):
        cur_vers = dict([line.strip().split(None, 1) for line in file(VERS_FILE, "r").read().split("\n") if line.strip().count(" ")])
    else:
        cur_vers = {}
    cur_vers[new_v] = new_f
    print("content of version dict {}:".format(VERS_FILE))
    pprint.pprint(cur_vers)
    file(VERS_FILE, "w").write("\n".join(["{} {}".format(key, value) for key, value in cur_vers.iteritems()] + [""]))

if __name__ == "__main__":
    main()
