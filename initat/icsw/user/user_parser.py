#!/usr/bin/python-init -Ot
#
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2001-2004,2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" small tool for sending mails via commandline """


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_user_parser(sub_parser, server_mode=kwargs["server_mode"])

    def _add_user_parser(self, sub_parser, server_mode):
        parser = sub_parser.add_parser("user", help="user information and tools")
        parser.set_defaults(subcom="user", execute=self._execute)
        parser.add_argument("-f", "--from", type=str, help="from address [%(default)s]", default="root@localhost")
        parser.add_argument("-s", "--subject", type=str, help="subject [%(default)s]", default="mailsubject")
        parser.add_argument("-m", "--server", type=str, help="mailserver to connect [%(default)s]", default="localhost")
        parser.add_argument("-t", "--to", type=str, nargs="*", help="to address [%(default)s]", default="root@localhost")
        parser.add_argument("message", nargs="+", help="message to send")
        if server_mode:
            parser.add_argument("--all", dest="to_all", action="store_true", default=False, help="send mail to all active users [%(default)s]")

    def _execute(self, opt_ns):
        from .main import user_main
        user_main(opt_ns)
