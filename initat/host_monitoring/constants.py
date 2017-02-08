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
from enum import Enum


TIME_FORMAT = "{:.3f}"

_CONFIG_DIR = "/etc/sysconfig/host-monitoring.d"
MAPPING_FILE_IDS = os.path.join(_CONFIG_DIR, "collrelay_0mq_mapping")

ICINGA_TOP_DIR = "/opt/icinga"
ZMQ_ID_MAP_STORE = "icsw.hm.0mq-mapping"
MACHVECTOR_CS_NAME = "icsw.hm.machvector"
RELAY_SETTINGS_CS_NAME = "icsw.relay.settings"

# number of 0MQ connection errors before we try to re-get the 0MQ id
MAX_0MQ_CONNECTION_ERRORS = 20


class HMAccessClassEnum(Enum):
    # free for all (monitoring)
    level0 = "level0"
    # require level1 (corvus)
    level1 = "level1"
    # require level2 (critical, need extra access level)
    level2 = "level2"


class DynamicCheckServer(Enum):
    snmp_relay = "snmp_relay"
    collrelay = "collrelay"
    native = "native"


class HMABIVersionEnum(Enum):
    # old TCP-based
    v00 = "Version_0.0"
    # 0MQ but also no longer supported
    v10 = "Version_1.0"
    # new Version, includes filtering and Meta-based Parameterhandling
    v20 = "Version_2.0"


class HMIPProtocolEnum(Enum):
    tcp = "tcp"
    udp = "udp"


HM_CURRENT_ABI_VERSION = HMABIVersionEnum.v20

JSON_DEFINITION_FILE = "mon_defs.json"
