#!/usr/bin/python-init -Otu
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
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
# -*- coding: utf-8 -*-
#
""" create version file for ICSW """

import argparse
import datetime
import importlib
import os
import sys

from initat.tools import config_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, help="Version [%(default)s]", default="1.0")
    parser.add_argument("--release", type=str, help="Release [%(default)s]", default="1")
    parser.add_argument("--target", type=str, help="version file target [%(default)s]", default="/tmp/version.py")
    opts = parser.parse_args()
    _now = datetime.datetime.now()
    cs_name = os.path.basename(opts.target).split("_")[0]
    _new_s = config_store.ConfigStore(cs_name, quiet=True, read=False)
    _new_s.file_name = opts.target
    _new_s["software"] = "{}-{}".format(opts.version, opts.release)
    _new_s["build.time"] = _now.strftime("%Y-%m-%d %H:%M:%S")
    _new_s["build.machine"] = os.uname()[1]
    _dir = os.path.dirname(__file__)
    _dir = os.path.join(_dir, "..", "initat", "cluster", "backbone", "models")
    sys.path.append(_dir)
    _func_mod = importlib.import_module("version_functions")
    _new_s["database"] = _func_mod.get_database_version()
    _new_s["models"] = _func_mod.get_models_version()
    _new_s.write()
    sys.exit(0)


if __name__ == "__main__":
    main()
