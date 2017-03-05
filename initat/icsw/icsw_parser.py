#
# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" parser for icsw command """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import sys

if "--nodb" in sys.argv:
    django = None
else:
    try:
        import django
        django.setup()
    except:
        django = None
    else:
        from initat.cluster.backbone import db_tools
        try:
            if not db_tools.is_reachable():
                django = None
        except:
            # when installing a newer icsw-client package on a machine with an old icsw-server package
            django = None

import importlib
import argparse

from initat.icsw.service.instance import InstanceXML


SC_MAPPING = {
    "service": ".service.service_parser",
    "user": ".user.user_parser",
    "collectd": ".collectd.collectd_parser",
    "job": ".job.job_parser",
    "image": ".image.image_parser",
    "device": ".device.device_parser",
    "setup": ".setup.parser",
    "license": ".license.license_parser",
    "info": ".info.info_parser",
    "error": ".error.error_parser",
    "relay": ".relay.relay_parser",
    "cstore": ".cstore.cstore_parser",
    "logwatch": ".logwatch.logwatch_parser",
    "config": ".config.config_parser",
    "call": ".call.call_parser",
    "debug": ".debug.debug_parser",
}


class ICSWParser(object):
    def __init__(self):
        _parser = argparse.ArgumentParser(prog="icsw", add_help=True)
        _parser.add_argument("--logger", type=str, default="stdout", choices=["stdout", "logserver"], help="choose logging facility")
        _parser.add_argument("--logall", default=False, action="store_true", help="log all (no just warning / error), [%(default)s]")
        _parser.add_argument("--nodb", default=False, action="store_true", help="disable usage of database [%(default)s]")
        self._parser = _parser
        self.sub_parser = self._parser.add_subparsers(help="sub-command help")

    def _add_parser(self, subcom, server_mode, inst_xml):
        try:
            _parser_module = importlib.import_module(
                SC_MAPPING[subcom],
                package="initat.icsw"
            )
        except:
            sub_parser = None
        else:
            try:
                sub_parser = _parser_module.Parser().link(
                    self.sub_parser,
                    server_mode=server_mode,
                    instance_xml=inst_xml,
                )
            except TypeError:
                # can happen when old parsers are still in the path
                sub_parser = None
        return sub_parser

    def _populate_all(self, server_mode, inst_xml):
        for _sc in sorted(SC_MAPPING.keys()):
            self._add_parser(_sc, server_mode, inst_xml)

    def parse_args(self):
        # set constants
        server_mode = True if django is not None else False
        inst_xml = InstanceXML(quiet=True)
        self._populate_all(server_mode, inst_xml)
        # print(dir(self.sub_parser))
        # print(self.sub_parser._get_subactions)
        opt_ns = self._parser.parse_args()
        if not hasattr(opt_ns, "execute"):
            self._parser.print_help()
            sys.exit(0)
        return opt_ns
