#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2010,2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
""" shows error recorded in the error file """

from initat.debug import ICSW_DEBUG_VARS


def show_current(options):
    print("Current ICSW Debug settings")
    for _var in ICSW_DEBUG_VARS:
        print(
            "{:<30s}: ({:>16s}) {:>20s}, current: {:>20s}".format(
                _var.name,
                str(type(_var.default)),
                str(_var.default),
                str(_var.current),
            )
        )


def clear_current(options):
    for _var in ICSW_DEBUG_VARS:
        print(_var.create_clear_line())


def modify(options):
    for _var in ICSW_DEBUG_VARS:
        print(_var.create_export_line(getattr(options, _var.option_name)))


def main(options):
    if options.show:
        show_current(options)
    elif options.clear:
        clear_current(options)
    else:
        modify(options)
