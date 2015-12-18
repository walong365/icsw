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

"""

small tool for sending mails via commandline

Attention: the 'icsw user --mode mail' command is also used by the md-config-server

"""

import pwd
import os


class Parser(object):
    def link(self, sub_parser, **kwargs):
        return self._add_user_parser(sub_parser, server_mode=kwargs["server_mode"])

    def _add_user_parser(self, sub_parser, server_mode):
        _user_name = pwd.getpwuid(os.getuid())[0]
        self.server_mode = server_mode
        parser = sub_parser.add_parser("user", help="user information and tools")
        parser.set_defaults(subcom="user", execute=self._execute)
        if server_mode:
            _choices = ["mail", "list", "export", "import", "modify", "info", "chpasswd"]
            if _user_name in ["root"]:
                _defc = "list"
            else:
                _defc = "info"
        else:
            _choices = ["mail"]
            _defc = "mail"
        parser.add_argument("--mode", type=str, default=_defc, choices=_choices, help="action [%(default)s]")
        parser.add_argument("-f", "--from", type=str, help="from address [%(default)s]", default="root@localhost")
        parser.add_argument("-s", "--subject", type=str, help="subject [%(default)s]", default="mailsubject")
        parser.add_argument("-m", "--server", type=str, help="mailserver to connect [%(default)s]", default="localhost")
        parser.add_argument("-t", "--to", action="append", help="to address [%(default)s]", default=[])
        parser.add_argument("--message", nargs="+", help="message to send")
        if server_mode:
            parser.add_argument(
                "--only-active",
                dest="only_active",
                default=False,
                action="store_true",
                help="filter for active users (in active groups) [%(default)s]",
            )
            from initat.cluster.backbone.models import home_export_list, user
            from django.db.models import Q
            hel = home_export_list()
            parser.add_argument("--user-filter", type=str, default=".*", help="regex for user login filter [%(default)s]")
            parser.add_argument("--group-filter", type=str, default=".*", help="regex for group name filter [%(default)s]")
            parser.add_argument("--use-db-for-mail", dest="use_db", action="store_true", default=False, help="use database as user source [%(default)s]")
            parser.add_argument("--export", type=str, default="", help="filename to (export to / import from) users [%(default)s]")
            parser.add_argument("--default-group", type=str, default="", help="default group from import [%(default)s]")
            parser.add_argument("--with-email", default=False, action="store_true", help="filter for users with a valid email address [%(default)s]")
            parser.add_argument("--sendit", default=False, action="store_true", help="really send email [%(default)s]")
            if hel.exp_dict:
                # build dict
                parser.add_argument(
                    "--new-export",
                    default=0,
                    type=int,
                    choices=[0] + hel.exp_dict.keys(),
                    help="set export entry for modify [%(default)d=keep], info:\n{}".format(
                        "\n".join(
                            [
                                "{:d}={}@{}".format(_key, hel.exp_dict[_key]["createdir"], hel.exp_dict[_key]["name"]) for _key in hel.exp_dict.keys()
                            ]
                        )
                    ),
                )
            parser.add_argument("-Q", "--system-wide-quota", default=False, action="store_true", help="show system-wide quota [%(default)s]")
            parser.add_argument(
                "--username",
                default=_user_name,
                choices=user.objects.filter(Q(active=True) & Q(group__active=True)).values_list("login", flat=True),
                help="user to use for info and changepwd [%(default)s]"
            )
            parser.add_argument("--timeout", default=10, type=int, help="timeout for server connections [%(default)d]")

    def _execute(self, opt_ns):
        from .main import user_main
        opt_ns.server_mode = self.server_mode
        user_main(opt_ns)
