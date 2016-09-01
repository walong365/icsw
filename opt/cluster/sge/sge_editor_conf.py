#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2007,2014-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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
""" simple wrapper script for editing sge configs """

import os
import sys

from initat.tools import logging_tools


def main():
    fname = sys.argv[1]
    c_lines = [_line.strip() for _line in file(fname, "r").read().splitlines()]
    a_lines = []
    cont_line, act_line = (False, "")
    for line in c_lines:
        c_line = cont_line
        if line.endswith("\\"):
            line = line[:-1]
            cont_line = True
        else:
            cont_line = False
        if c_line:
            act_line += line
        else:
            act_line = line
        if not cont_line and act_line:
            a_lines += [act_line]
    content = dict([_line.split(None, 1) for _line in a_lines])
    try:
        new_keys = dict(
            [
                _line.split(None, 1) for _line in [
                    _entry.strip() for _entry in file("/tmp/.qconf_config", "r").read().splitlines()
                ]
            ]
        )
    except:
        pass
    else:
        k_new, k_change = (set(), set())
        for key, value in new_keys.iteritems():
            if key in content:
                old_val = ",".join([_line.strip() for _line in content.get(key, "").split(",")])
                new_val = ",".join([_line.strip() for _line in value.split(",")])
                if old_val != new_val:
                    k_change.add(key)
                    print("Altered key '{}' from '{}' to '{}'".format(key, old_val, new_val))
                    content[key] = new_val
            else:
                k_new.add(key)
                print(
                    "Set key '{}' to '{}'".format(key, value)
                )
                content[key] = value
        k_new = sorted(list(k_new))
        k_change = sorted(list(k_change))
        if k_new or k_change:
            print(
                "Set {}: {}, changed {}: {}".format(
                    logging_tools.get_plural("key", len(k_new)),
                    ", ".join(k_new) or "none",
                    logging_tools.get_plural("key", len(k_change)),
                    ", ".join(k_change) or "none",
                )
            )
            file(fname, "w").write("\n".join(["{} {}".format(key, str(content[key])) for key in sorted(content.keys())] + [""]))
        try:
            os.unlink("/tmp/.qconf_config")
        except:
            pass

if __name__ == "__main__":
    main()
