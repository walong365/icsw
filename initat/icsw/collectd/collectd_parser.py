#!/usr/bin/python-init -OtB
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel (lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" collectd parser """


class Parser(object):
    def link(self, sub_parser, **kwargs):
        inst_xml = kwargs.get("instance_xml")
        if "collectd" in inst_xml:
            return self._add_collectd_parser(sub_parser, inst_xml=inst_xml)

    def _add_collectd_parser(self, sub_parser, inst_xml):
        parser = sub_parser.add_parser("collectd", help="collectd helper commands")
        parser.set_defaults(subcom="collectd", execute=self._execute)
        com_list = ["host_list", "key_list"]
        parser.add_argument(
            "command",
            type=str,
            choices=com_list,
            help="command to execute [%(default)s]",
        )
        parser.add_argument(
            "arguments",
            nargs="*",
            help="additional arguments",
        )
        parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
        parser.add_argument("-p", help="port [%(default)d]", default=inst_xml.get_port_dict("collectd", command=True), dest="port", type=int)
        parser.add_argument("-H", help="host [%(default)s] or server", default="localhost", dest="host")
        parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
        parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="cdf", dest="identity_string")
        parser.add_argument("--host-filter", help="set filter for host name [%(default)s]", type=str, default=".*", dest="host_filter")
        parser.add_argument("--key-filter", help="set filter for key name [%(default)s]", type=str, default=".*", dest="key_filter")
        parser.add_argument("--mode", type=str, default="tcp", choices=["tcp", "memcached"], help="set access type [%(default)s]")
        parser.add_argument("--mc-addr", type=str, default="127.0.0.1", help="address of memcached [%(default)s]")
        parser.add_argument("--mc-port", type=int, default=inst_xml.get_port_dict("memcached", command=True), help="port of memcached [%(default)d]")
        return parser

    def _execute(self, opt_ns):
        from .main import main
        main(opt_ns)
