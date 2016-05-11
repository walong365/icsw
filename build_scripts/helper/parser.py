#!/usr/bin/python-init -Otu
#
# Copyright (C) 2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw
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

""" parser for pre_build_scripts """

import argparse


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--specfile", type=str)
    parser.add_argument("--increase-release-on-build", type=int)
    parser.add_argument("--binary-dir", type=str)
    args = parser.parse_args()
    args.increase_release_on_build = True if int(args.increase_release_on_build) else False
    return args
