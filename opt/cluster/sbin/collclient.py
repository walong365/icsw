#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2016 Andreas Lang-Nevyjel
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

""" client for host-monitoring """

import os
import sys

if not __file__.startswith("/opt/cluster"):
    _add_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _add_path not in sys.path:
        sys.path.insert(0, _add_path)

from initat.host_monitoring import main

sys.exit(main.main())
