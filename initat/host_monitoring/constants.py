# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, with 0MQ and twisted support, constants """

import os

TIME_FORMAT = "{:.3f}"

_CONFIG_DIR = "/etc/sysconfig/host-monitoring.d"
MAPPING_FILE_IDS = os.path.join(_CONFIG_DIR, "collrelay_0mq_mapping")

ICINGA_TOP_DIR = "/opt/icinga"
ZMQ_ID_MAP_STORE = "icsw.hm.0mq-mapping"
MACHVECTOR_CS_NAME = "icsw.hm.machvector"
RELAY_SETTINGS_CS_NAME = "icsw.relay.settings"
