# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

# do NOT optimize the imports

from .global_config import global_config

from initat.md_config_server.config.constants import *
from initat.md_config_server.base_config.mon_base_config import *
from initat.md_config_server.config.mon_config_containers import MonFileContainer, MonDirContainer
from initat.md_config_server.config.objects import *
from initat.md_config_server.config.sync_config import SyncConfig
from initat.md_config_server.config.templates import *
from initat.md_config_server.config.main_config import MainConfig, MainConfigContainer
