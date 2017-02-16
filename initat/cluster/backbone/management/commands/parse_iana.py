#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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

"""
parse IANAIfType from https://www.iana.org/assignments/ianaiftype-mib/ianaiftype-mib
"""


l = open("iana_raw.txt", "r").readlines()

n_lines = []
for line in l:
    line = line.strip()
    if not line:
        continue
    if line.startswith("-"):
        n_lines[-1] = "{} {}".format(n_lines[-1], line.split(None, 1)[1])
    else:
        n_lines.append(line)

for line in n_lines:
    p0, p1 = line.split(",", 1)
    comment = p1.strip()
    if comment.startswith("--"):
        comment = comment[2:].strip()
    p0 = p0.strip().replace(" ", "")
    _name = p0.split("(")[0]
    _idx = int(p0.split("(")[1].split(")")[0])
    print("    IANAIfType({:d}, \"{}\", \"{}\"),".format(_idx, _name, comment))
