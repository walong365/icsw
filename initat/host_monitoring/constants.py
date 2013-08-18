#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011,2012,2013 Andreas Lang-Nevyjel
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

""" host-monitoring, with 0MQ and twisted support, constants """

import os

TIME_FORMAT = "%.3f"

CONFIG_DIR = "/etc/sysconfig/host-monitoring.d"
MAPPING_FILE_IDS = os.path.join(CONFIG_DIR, "collrelay_0mq_mapping")
MAPPING_FILE_TYPES = os.path.join(CONFIG_DIR, "0mq_clients")
MASTER_FILE_NAME = os.path.join(CONFIG_DIR, "monitor_master")
