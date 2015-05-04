# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from initat.tools import configfile
from initat.tools import process_tools

global_config = configfile.get_global_config(process_tools.get_programm_name())

from initat.md_config_server.config.mon_config import *
from initat.md_config_server.config.base_config import base_config
from initat.md_config_server.config.content_emitter import content_emitter
from initat.md_config_server.config.var_cache import var_cache
from initat.md_config_server.config.build_cache import build_cache
from initat.md_config_server.config.config_dir import config_dir
from initat.md_config_server.config.host_type_config import host_type_config
from initat.md_config_server.config.main_config import main_config
from initat.md_config_server.config.sync_config import sync_config
from initat.md_config_server.config.check_command import check_command
from initat.md_config_server.config.templates import *
from initat.md_config_server.config.objects import *
