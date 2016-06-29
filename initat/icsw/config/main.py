#
# Copyright (C) 2001-2006,2014-2016 Andreas Lang-Nevyjel
#
# this file is part of cluster-backbone
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" show config script for simple use in CSW """

import datetime
import base64
import os
import stat
import sys
import bz2

from initat.tools import logging_tools, process_tools


def show_command(options):
    for f_name in options.files:
        _obj_name = f_name if not options.short_path else os.path.basename(f_name)
        for _rc in ["/", ".", "-"]:
            _obj_name = _obj_name.replace(_rc, "_")
        while _obj_name.startswith("_"):
            _obj_name = _obj_name[1:]
        obj_name = "{}_object".format(_obj_name)
        try:
            f_stat = os.stat(f_name)
            content = file(f_name).read()
        except:
            print(
                "error reading file '{}': {}".format(
                    f_name,
                    process_tools.get_except_info()
                )
            )
        else:
            if not options.binary:
                f_lines = content.split("\n")
                _f_info = logging_tools.get_plural("line", f_lines)
            else:
                _f_info = "binary"
            out_lines = [
                "",
                "# from {} ({}, host {}, size was {}, {})".format(
                    f_name,
                    datetime.datetime.now(),
                    process_tools.get_machine_name(short=False),
                    logging_tools.get_size_str(f_stat[stat.ST_SIZE]),
                    _f_info,
                ),
                "",
                "{} = config.add_file_object('{}')".format(obj_name, f_name),
            ]
            if options.binary:
                out_lines.extend(
                    [
                        "import bz2",
                        "import base64",
                        "",
                        u"{} += bz2.decompress(base.b64decode('{}'))".format(
                            obj_name,
                            base64.b64encode(bz2.compress(content)),
                        )
                    ]
                )
            else:
                if options.full_strip:
                    f_lines = [_line.strip() for _line in f_lines if _line.strip()]
                if options.remove_hashes:
                    f_lines = [_line for _line in f_lines if (not _line.startswith("#") or _line.startswith("#!"))]
                p_line = " " * 4
                try:
                    out_lines.append(
                        u"{} += [\n{}]\n".format(
                            obj_name,
                            "".join(
                                [
                                    u"{}'{}',\n".format(p_line, _line.replace("'", '"').replace("\\", "\\\\")) for _line in f_lines
                                ]
                            )
                        )
                    )
                except UnicodeDecodeError:
                    print
                    print("'{}' seems to be a binary file, please use -b switch".format(f_name))
                    print
                    sys.exit(3)
            out_lines.append(
                u"{}.mode = 0{:o}".format(
                    obj_name,
                    stat.S_IMODE(f_stat[stat.ST_MODE])
                )
            )
            print "\n".join(out_lines)


def main(opt_ns):
    if opt_ns.childcom == "show":
        show_command(opt_ns)
