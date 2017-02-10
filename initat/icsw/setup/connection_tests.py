# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server-server
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
""" database connection tests """

from initat.tools import process_tools


class test_db(dict):
    def __init__(self, db_type, c_dict):
        self.db_type = db_type
        dict.__init__(self)
        self.update(c_dict)

    def test_connection(self):
        return True if self.get_connection() is not None else False

    def get_connection(self):
        return None

    def show_config(self):
        return "No config help defined for db_type {}".format(self.db_type)


class test_psql(test_db):
    def __init__(self, c_dict):
        test_db.__init__(self, "psql", c_dict)

    def get_connection(self):
        dsn = "dbname={} user={} host={} password={} port={:d}".format(
            self["database"],
            self["user"],
            self["host"],
            self["passwd"],
            self["port"],
        )
        print("dsn is '{}'".format(dsn))
        try:
            import psycopg2
            conn = psycopg2.connect(dsn)
        except:
            print("cannot connect: {}".format(process_tools.get_except_info()))
            conn = None
        return conn

    def show_config(self):
        print("")
        print("you can create the database and the user with")
        print("")
        print("CREATE USER {} LOGIN NOCREATEDB UNENCRYPTED PASSWORD '{}';".format(self["user"], self["passwd"]))
        print("CREATE DATABASE {} OWNER {};".format(self["database"], self["user"]))
        print("")
        print("depending on your connection type (via TCP socket or unix domain socket) enter one of the following lines to pg_hba.conf:")
        print("")
        print("local   {:<16s}{:<16s}                md5".format(self["database"], self["user"]))
        print("host    {:<16s}{:<16s}127.0.0.1/32    md5".format(self["database"], self["user"]))
        print("host    {:<16s}{:<16s}::1/128         md5".format(self["database"], self["user"]))
        print("")


class test_mysql(test_db):
    def __init__(self, c_dict):
        test_db.__init__(self, "mysql", c_dict)

    def get_connection(self):
        try:
            import MySQLdb
            conn = MySQLdb.connect(
                host=self["host"],
                user=self["user"],
                passwd=self["passwd"],
                db=self["database"],
                port=self["port"]
            )
        except:
            print("cannot connect: {}".format(process_tools.get_except_info()))
            conn = None
        return conn

    def show_config(self):
        print("")
        print("you can create the database and the user with")
        print("")
        print("CREATE USER '{}'@'localhost' IDENTIFIED BY '{}';".format(self["user"], self["passwd"]))
        print("CREATE DATABASE {};".format(self["database"]))
        print("GRANT ALL ON {}.* TO '{}'@'localhost' IDENTIFIED BY '{}';".format(self["database"], self["user"], self["passwd"]))
        print("FLUSH PRIVILEGES;")
        print("")


class test_sqlite(test_db):
    def __init__(self, c_dict):
        test_db.__init__(self, "sqlite", c_dict)

    def get_connection(self):
        try:
            import sqlite3
            conn = sqlite3.connect(database=self["database"])
        except:
            print("cannot connect: {}".format(process_tools.get_except_info()))
            conn = None
        return conn

    def show_config(self):
        print("")
        print("you can create the database and the user with")
        print("")
        print("CREATE USER '{}'@'localhost' IDENTIFIED BY '{}';".format(self["user"], self["passwd"]))
        print("CREATE DATABASE {};".format(self["database"]))
        print("GRANT ALL ON {}.* TO '{}'@'localhost' IDENTIFIED BY '{}';".format(self["database"], self["user"], self["passwd"]))
        print("FLUSH PRIVILEGES;")
        print("")
