# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
# -*- coding: utf-8 -*-
#
""" return version information """

import hashlib
import os


def is_debug_run():
    return True if not os.path.dirname(__file__).startswith("/opt") else False


def get_models_version():
    _dir = os.path.dirname(__file__)
    while not _dir.endswith("models"):
        _dir = os.path.split(_dir)
    my_md5 = hashlib.md5()
    for _sdir, _dlist, _flist in os.walk(_dir):
        for _file in [_entry for _entry in _flist if _entry.endswith(".py")]:
            _fp = os.path.join(_sdir, _file)
            if os.path.exists(_fp):
                my_md5.update(file(_fp, "r").read())
    return my_md5.hexdigest()


def get_database_version():
    _dir = os.path.dirname(__file__)
    while not _dir.endswith("models"):
        _dir = os.path.split(_dir)
    _dir = os.path.join(_dir, "..", "migrations")
    highest_patch = 0
    for _sdir, _dlist, _flist in os.walk(_dir):
        for _file in _flist:
            if _file.endswith(".py") and _file[0].isdigit():
                highest_patch = max(highest_patch, int(_file.split("_")[0]))
    return "v1.{:05d}".format(highest_patch)
