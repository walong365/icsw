# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" simple caching wrapper """

from initat.tools import process_tools


class my_cached_file(process_tools.cached_file):
    def __init__(self, name, **kwargs):
        self.hosts = set()
        process_tools.cached_file.__init__(self, name, **kwargs)

    def changed(self):
        if self.content:
            self.log("reread file {}".format(self.name))
            self.hosts = set(
                [
                    cur_line.strip() for cur_line in self.content.strip().split("\n") if cur_line.strip() and not cur_line.strip().startswith("#")
                ]
            )
        else:
            self.hosts = set()

    def __contains__(self, h_name):
        return h_name in self.hosts
