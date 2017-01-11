# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" parser for icsw setup command """



import os

from .commands import DB_CS_FILENAME
from .constants import AVAILABLE_DATABASES
from .utils import generate_password
from ..icsw_logging import install_global_logger


class Parser(object):
    def __init__(self):
        pass

    def link(self, parser, **kwargs):
        self.parser = parser.add_parser(
            "setup", help="Create database and perform initial setup"
        )
        self.parser.set_defaults(execute=self.execute)
        self.add_db_group()
        self.add_migration_group()
        self.add_creation_group()
        self.add_update_group()
        self.add_automatic_group()
        self.add_webfrontend_group()
        if "sqlite" in AVAILABLE_DATABASES:
            self.add_sqlite_group()

    def execute(self, options):
        from .commands import main
        install_global_logger()
        main(options)

    def add_db_group(self):
        group = self.parser.add_argument_group("database options")
        group.add_argument(
            "--engine", choices=AVAILABLE_DATABASES,
            help="choose database engine [%(default)s]", 
        )
        group.add_argument(
            "--user", type=str, default="cdbuser",
            help="set name of database user"
        )
        group.add_argument(
            "--passwd", type=str, default=generate_password(),
            help="set password for database user"
        )
        group.add_argument(
            "--database", type=str, help="set name of cluster database",
            default="cdbase"
        )
        group.add_argument(
            "--host", type=str, default="localhost", help="set database host"
        )
        group.add_argument(
            "--port", type=int, help="set database port"
        )
        group.add_argument(
            "--ignore-existing", default=False, action="store_true",
            help="Ignore existing db.cf file {} [%(default)s]".format(DB_CS_FILENAME)
        )
        group.add_argument(
            "--use-existing", default=False, action="store_true",
            help="use existing db.cf file {} [%(default)s]".format(DB_CS_FILENAME)
        )

    def add_migration_group(self):
        group = self.parser.add_argument_group("migration options")
        group.add_argument(
            "--clear-migrations", default=False, action="store_true",
            help="clear migrations before database creationg [%(default)s]"
        )
        group.add_argument(
            "--no-initial-data", default=False, action="store_true",
            help="disable inserting of initial data [%(default)s], only useful" 
            " for the migration from an older version of the clustersoftware"
        )
        group.add_argument(
            "--migrate", default=False, action="store_true",
            help="migrate current cluster database [%(default)s]"
        )

    def add_creation_group(self):
        group = self.parser.add_argument_group("database creation options")
        group.add_argument(
            "--superuser", default="admin", type=str,
            help="name of the superuser [%(default)s]"
        )
        group.add_argument(
            "--email", default="admin@localhost", type=str,
            help="admin address of superuser [%(default)s]"
        )
        group.add_argument(
            "--no-superuser", default=False, action="store_true",
            help="do not create a superuser [%(default)s]"
        )
        group.add_argument(
            "--system-group-name", default="system", type=str,
            help="name of system group [%(default)s]"
        )

    def add_update_group(self):
        group = self.parser.add_argument_group("update options")
        group.add_argument(
            "--only-fixtures",
            default=False,
            action="store_true",
            help="only call create_fixtures"
        )

    def add_automatic_group(self):
        group = self.parser.add_argument_group("automatic update options")
        group.add_argument(
            "--disable-auto-update",
            default=False,
            action="store_true",
            help="disable automatic update [%(default)s]"
        )
        group.add_argument(
            "--enable-auto-update",
            default=False,
            action="store_true",
            help="enable automatic update [%(default)s]"
        )

    def add_webfrontend_group(self):
        wf = self.parser.add_argument_group("webfrontend options")
        wf.add_argument(
            "--init-webfrontend",
            default=False,
            action="store_true",
            help="builds caches for the webfrontend [%(default)s]"
        )

    def add_sqlite_group(self):
        """
        if [ -f /etc/debian_version ] ; then
            usermod -G idg www-data
        elif [ -f /etc/redhat-release ] ; then
            usermod -G idg apache
        else
            usermod -G idg wwwrun
        fi
        """
        # dummy default user
        _default_user = "idlog"
        for _file, _default_user in [
            ("/etc/debian_version", "www-data"),
            ("/etc/redhat-release", "apache"),
            ("/etc/SuSE-release", "wwwrun"),
        ]:
            if os.path.exists(_file):
                break
        group = self.parser.add_argument_group("sqlite database file options")
        group.add_argument(
            "--db-path",
            type=str,
            default="/opt/cluster/db",
            help="path to sqlite database file directory"
        )
        group.add_argument(
            "--db-file-owner",
            type=str,
            default=_default_user,
            help="owner of the database file"
        )
        group.add_argument(
            "--db-file-group",
            type=str,
            default="idg",
            help="group of the database file"
        )
        group.add_argument(
            "--db-file-mode",
            type=str,
            default="660",
            help="database file access mode"
        )
