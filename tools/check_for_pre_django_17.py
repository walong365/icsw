#!/usr/bin/python-init -Otu
#
# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
#
# this file is part of cluster-backbone-sql
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

""" checks for pre-django1.7 models and saves them away """

import os

BACKBONE_DIR = "/opt/python-init/lib/python/site-packages/initat/cluster/backbone"
MIG_DIR = os.path.join(BACKBONE_DIR, "migrations")
MODELES_DIR = os.path.join(BACKBONE_DIR, "models")
PRE_MODELES_DIR = os.path.join(BACKBONE_DIR, "models16")


def check_for_pre():
    _south_found = False
    _south_dirs = []
    if os.path.isdir(MIG_DIR):
        _entries = [_entry for _entry in os.listdir(MIG_DIR) if _entry.endswith(".py") and _entry[0].isdigit()]
        if _entries:
            # migration dir is not empty
            _south = [file(os.path.join(MIG_DIR, _entry), "r").read(1000).count("south") for _entry in _entries]
            if any(_south):
                print("South migrations found in {}".format(MIG_DIR))
                _south_found = True
    if _south_found:
        print("moving models_dir from {} to {}".format(MODELES_DIR, PRE_MODELES_DIR))
        os.rename(MODELES_DIR, PRE_MODELES_DIR)

if __name__ == "__main__":
    check_for_pre()
