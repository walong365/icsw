#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009,2012-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" helper functions """

import encodings.idna


def make_qualified(in_str):
    return in_str.endswith(".") and in_str or u"{}.".format(in_str)


def make_unqualified(in_str):
    return in_str.endswith(".") and in_str[:-1] or in_str


def to_idna(in_str):
    return ".".join([entry and encodings.idna.ToASCII(entry) or "" for entry in in_str.split(".")])
