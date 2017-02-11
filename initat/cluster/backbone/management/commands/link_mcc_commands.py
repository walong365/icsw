#!/usr/bin/python3-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Andreas Lang-Nevyjel
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
""" link moncheck commands with defined commands or set own uuids """

import sys
from django.core.management.base import BaseCommand

from initat.cluster.backbone.models import mon_check_command, BackendConfigFile, \
    BackendConfigFileTypeEnum
from initat.tools import logging_tools
from django.db.models import Q
import pprint


class Command(BaseCommand):
    help = "Link mon_check_commands with defined hm-commands"

    def handle(self, **options):
        cur_cc = BackendConfigFile.get(BackendConfigFileTypeEnum.mcc_json)
        if cur_cc is None:
            print("nothing found to link")
            sys.exit(1)
        # iterate over all mon_ccs witthout an UUID
        undef_moncc = mon_check_command.objects.filter(Q(uuid=""))
        if undef_moncc.count():
            print(
                "Found {}, matching against {}".format(
                    logging_tools.get_plural("unlinked mon_check_command", undef_moncc.count()),
                    str(cur_cc),
                )
            )
            # get structure
            struct = cur_cc.structure
            luts = {
                "cmd": {},
                "name": {},
            }
            for cmd in struct["command_list"]:
                luts["cmd"][cmd["icinga_cmdline"]] = cmd
                luts["name"][cmd["name"]] = cmd
            for u_m in undef_moncc:
                matches = {
                    "cmd": u_m.command_line in luts["cmd"],
                    "name": u_m.name in luts["name"],
                }
                if any(matches.values()):
                    if matches["cmd"]:
                        # command match, perfect
                        u_m.uuid = luts["cmd"][u_m.command_line]["uuid"]
                        u_m.save(update_fields=["uuid"])
                    elif matches["name"]:
                        # match via name
                        u_m.uuid = luts["name"][u_m.name]["uuid"]
                        u_m.save(update_fields=["uuid"])
                else:
                    # print("m:", u_m.idx, u_m.command_line)
                    pass
            # iterate over all still undefined (== without UUID)
            for u_m in mon_check_command.objects.filter(Q(uuid="")):
                u_m.save()
