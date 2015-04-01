#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2013-2014 Andreas Lang-Nevyjel
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

import re

def hostname_expand(hname, in_str):
    host_re = re.compile("^(?P<pre>.*)(?P<type>%h)(?P<post>.*)$")
    hre = True
    while hre:
        hre = host_re.match(in_str)
        if hre:
            in_str = "{}{}{}".format(
                hre.group("pre"),
                hname,
                hre.group("post")
            )
    return in_str
