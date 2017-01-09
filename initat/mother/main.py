# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2009,2012-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" mother daemon, main part """

from __future__ import unicode_literals, print_function

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.conf import settings
from initat.tools import configfile
import initat.mother.server
from initat.mother.config import global_config


def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("DATABASE_DEBUG", configfile.bool_c_var(False, help_string="enable database debug mode [%(default)s]", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )
    settings.DEBUG = global_config["DATABASE_DEBUG"]
    settings.DATABASE_DEBUG = global_config["DATABASE_DEBUG"]
    initat.mother.server.ServerProcess().loop()
    sys.exit(0)
