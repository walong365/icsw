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
""" call runwoker in a safe way (survice redis restarts) """

import time

from channels.management.commands import runworker
from redis.exceptions import ConnectionError


class Command(runworker.Command):
    help = "Call runworker in a safe way "

    def handle(self, **options):
        _run = True
        while _run:
            try:
                super(Command, self).handle(**options)
            except ConnectionError:
                print("a redis connection error occured, retrying ...")
                time.sleep(2)
            else:
                _run = False
