#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2009 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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
""" wrapper script to read global definitions from /etc/sysconfig/cluster/webfrontend.py"""

import sys

cluster_conf_dir = "/etc/sysconfig/cluster"
if cluster_conf_dir not in sys.path:
    sys.path.append(cluster_conf_dir)

from webfrontend import SHOW_INDEX_PRI, SESSION_ID_NAME, DEBUG, DEVELOPMENT, \
     SESSION_TIMEOUT, USE_SHM_SESSIONS, IMMEDIATE_APC_OPERATIONS_ALLOWED, PHP_COMPAT
