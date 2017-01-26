# Copyright (C) 2007-2009,2013-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" rrd-grapher for graphing rrd-data """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.rrd_grapher.config import global_config
from initat.tools import configfile
import sys


def run_code():
    from initat.rrd_grapher.server import ServerProcess
    ServerProcess().loop()


def main():
    global_config.add_config_entries(
        [
            ("SERVER_PATH", configfile.bool_c_var(False, help_string="set server_path to store RRDs [%(default)s]")),
            ("RRD_DIR", configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc", database=True)),
            ("RRD_CACHED_DIR", configfile.str_c_var("/var/run/rrdcached", database=True)),
            ("RRD_CACHED_SOCKET", configfile.str_c_var("/var/run/rrdcached/rrdcached.sock", database=True)),
            ("GRAPHCONFIG_BASE", configfile.str_c_var("/opt/cluster/share/rrd_grapher/", help_string="name of colortable file", database=True)),
            ("COMPOUND_DIR", configfile.str_c_var("/opt/cluster/share/rrd_grapher/", help_string="include dir for compound XMLs", database=True)),
        ]
    )
    run_code()
    sys.exit(0)
