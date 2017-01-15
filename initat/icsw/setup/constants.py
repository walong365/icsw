# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
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
""" database setup for NOCTUA / CORVUS / NESTOR """

import importlib
import os

from initat.constants import LOG_ROOT, BACKBONE_DIR

__all__ = [
    "CMIG_DIR",
    "MIGRATION_DIRS",
    "MIGRATIONS_DIR",
    "NEEDED_DIRS",
    "MODELS_DIR",
    "MODELS_DIR_SAVE",
    "Z800_MODELS_DIR",
    "DB_PRESENT",
    "DEFAULT_DATABASE",
    "DEFAULT_ENGINE",
    "AVAILABLE_DATABASES",
    "SYNC_APPS",
]

#
# directories
#

CMIG_DIR = os.path.join(BACKBONE_DIR, "migrations")
MIGRATION_DIRS = [
    "reversion",
    "django/contrib/sites",
    "django/contrib/auth",
    "initat/cluster/backbone",
    "initat/cluster/liebherr",
]

#
# which apps needs syncing
#

SYNC_APPS = ["liebherr", "licadmin"]

NEEDED_DIRS = [LOG_ROOT]

MODELS_DIR = os.path.join(BACKBONE_DIR, "models")
MIGRATIONS_DIR = os.path.join(BACKBONE_DIR, "migrations")
MODELS_DIR_SAVE = os.path.join(BACKBONE_DIR, ".models_save")
Z800_MODELS_DIR = os.path.join(BACKBONE_DIR, "0800_models")

#
# Database related values
#

DEFAULT_DATABASE = "cdbase"
DB_PRESENT = {
    "psql": True,
    "mysql": True,
    "sqlite": True,
}

for module_name, key in (
    ("psycopg2", "psql"),
    ("MySQLdb", "mysql"),
    ("sqlite3", "sqlite"),
):
    try:
        importlib.import_module(module_name)
    except:
        DB_PRESENT[key] = False

AVAILABLE_DATABASES = [key for key, value in list(DB_PRESENT.items()) if value]
if "psql" in AVAILABLE_DATABASES:
    DEFAULT_ENGINE = "psql"
else:
    try:
        DEFAULT_ENGINE = AVAILABLE_DATABASES[0]
    except IndexError:
        DEFAULT_ENGINE = ""
