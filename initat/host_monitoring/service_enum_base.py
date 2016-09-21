# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" serviceEnum Base for 'global' configenum object, for clients """


__all__ = [
    "icswServiceEnumBaseClient"
]


class icswServiceEnumBaseClient(object):
    def __init__(self, name, info="N/A", root_service=True, msi_block_name=None, relayer_service=False):
        self.name = name
        self.info = info
        self.root_service = root_service
        # should match name of instance in {server,client,...}.xml
        self.msi_block_name = msi_block_name or self.name
        self.client_service = True
        self.server_service = False
        self.relayer_service = relayer_service
        self.clear_instance_names()

    def clear_instance_names(self):
        self.instance_name = None
        self.instance_names = []

    def add_instance_name(self, name):
        if name in self.instance_names:
            raise ValueError(
                "instance name '{}' already used for Enum {}".format(
                    name,
                    self.name,
                )
            )
        self.instance_names.append(name)
        if len(self.instance_names) > 1:
            self.instance_name = None
            raise ValueError(
                "more than one ServerInstance set for {}: {}".format(
                    self.name,
                    ", ".join(self.instance_names),
                )
            )
        else:
            self.instance_name = self.instance_names[0]
