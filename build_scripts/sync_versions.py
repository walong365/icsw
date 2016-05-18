#!/usr/bin/python-init -Otu
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw
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

""" modify build.spec to force dependencies """

import sys
from helper import parser


def main():
    args = parser.parse()
    if args.increase_release_on_build:
        print("specfile is at {}".format(args.specfile))
        _lines = file(args.specfile).read().split("\n")
        _new_lines = []
        _modified = 0
        _version, _release = (None, None)
        for _line in _lines:
            if _line.lower().startswith("version:") and _version is None:
                _version = _line.strip().split()[1]
            if _line.lower().startswith("release:") and _release is None:
                _release = _line.strip().split()[1]
            if _version and _release:
                if _line.lower().startswith("requires:"):
                    for _sw in ["icsw-client", "icsw-server"]:
                        if _line.count(_sw):
                            _new_line = "Requires: {} >= {}-{}".format(_sw, _version, _release)
                            if _line != _new_line:
                                _line = _new_line
                                _modified += 1
            _new_lines.append(_line)
        if _modified:
            print("Modified {:d} line(s), rewriting specfile".format(_modified))
            file(args.specfile, "w").write("\n".join(_new_lines))
    else:
        print("rebuild run, not modify specfile")
    sys.exit(0)


if __name__ == "__main__":
    main()
