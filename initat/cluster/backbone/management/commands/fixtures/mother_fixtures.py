# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for mother """

from initat.cluster.backbone import factories

def add_fixtures(**kwargs):
    factories.Config(name="mother_server", description="enables basic nodeboot via PXE functionalities",
        server_config=True, system_config=True,
        )
    factories.Config(name="kernel_server", description="device holds kernels for nodes",
        server_config=True, system_config=True,
        )
    factories.Config(name="image_server", description="device holds images for nodes",
        server_config=True, system_config=True,
        )
