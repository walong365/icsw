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

""" database setup for NOCTUA / CORVUS """

from django.utils.crypto import get_random_string
import argparse
import commands
import logging_tools
import os
import process_tools
import random
import shutil
import stat
import string
import sys
import time

DB_PRESENT = {}
LIB_DIR = "/opt/python-init/lib/python/site-packages"
CMIG_DIR = os.path.join(LIB_DIR, "initat", "cluster", "backbone", "migrations")
MIGRATION_DIRS = [
    "static_precompiler",
    "reversion",
    "django/contrib/auth",
    "initat/cluster/backbone",
    "initat/cluster/liebherr",
]
AUTO_FLAG = "/etc/sysconfig/cluster/db_auto_update"
SYNC_APPS = ["liebherr"]

NEEDED_DIRS = ["/var/log/cluster"]

BACKBONE_DIR = "/opt/python-init/lib/python/site-packages/initat/cluster/backbone"
PRE_MODELES_DIR = os.path.join(BACKBONE_DIR, "models16")

try:
    import psycopg2  # @UnresolvedImport
except:
    DB_PRESENT["psql"] = False
else:
    DB_PRESENT["psql"] = True

try:
    import MySQLdb  # @UnresolvedImport
except:
    DB_PRESENT["mysql"] = False
else:
    DB_PRESENT["mysql"] = True

try:
    import sqlite3  # @UnresolvedImport
except:
    DB_PRESENT["sqlite"] = False
else:
    DB_PRESENT["sqlite"] = True

DB_FILE = "/etc/sysconfig/cluster/db.cf"
LS_FILE = "/etc/sysconfig/cluster/local_settings.py"


# copy from check_local_settings.py
def check_local_settings():
    LS_DIR = os.path.dirname(LS_FILE)
    sys.path.append(LS_DIR)
    try:
        from local_settings import SECRET_KEY  # @UnresolvedImports
    except:
        SECRET_KEY = None
    if SECRET_KEY in [None, "None"]:
        print("creating file {} with secret key".format(LS_FILE))
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        SECRET_KEY = get_random_string(50, chars)
        file(LS_FILE, "w").write("\n".join(
            [
                "SECRET_KEY = \"%s\"" % (SECRET_KEY),
                "",
            ]
            ))
    sys.path.remove(LS_DIR)


def call_manage(args):
    com_str = " ".join([os.path.join(LIB_DIR, "initat", "cluster", "manage.py")] + args)
    s_time = time.time()
    c_stat, c_out = commands.getstatusoutput(com_str)
    e_time = time.time()
    if c_stat == 256 and c_out.lower().count("nothing seems to have changed"):
        c_stat = 0
    if c_stat:
        print("something went wrong calling '{}' in {} ({:d}):".format(
            com_str,
            logging_tools.get_diff_time_str(e_time - s_time),
            c_stat))
        for _line in c_out.split("\n"):
            print("  {}".format(_line))
        return False
    else:
        print("success calling '{}' in {}".format(
            com_str,
            logging_tools.get_diff_time_str(e_time - s_time),
            ))
        # print c_out
        return True


def _input(in_str, default, **kwargs):
    _choices = kwargs.get("choices", [])
    is_int = type(default) in [int, long]
    if is_int:
        _choice_str = ", ".join(["{:d}".format(_val) for _val in sorted(_choices)])
        _def_str = "{:d}".format(default)
    else:
        _choice_str = ", ".join(sorted(_choices))
        _def_str = default
    if _choices:
        print("possible choices for {}: {}".format(in_str, _choice_str))
    if len(_choices) == 1:
        return _choices[0]
    while True:
        try:
            _cur_inp = raw_input(
                "{:<30s} : ".format(
                    "{} ({})".format(
                        in_str,
                        _def_str,
                    )
                )
            )
        except (KeyboardInterrupt, EOFError):
            print("\nenter exit to abort\n")
        else:
            if _cur_inp == "exit":
                print("exit entered, installation aborted")
                sys.exit(2)
            _cur_inp = _cur_inp.strip()
            if _cur_inp == "":
                _cur_inp = default
            if is_int:
                try:
                    _cur_inp = int(_cur_inp)
                except:
                    print("please enter an integer")
                    _cur_inp = ""
            if _cur_inp:
                if _choices and _cur_inp not in _choices:
                    print("possible choices for {}: {}".format(in_str, _choice_str))
                else:
                    break
    return _cur_inp


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
            conn = sqlite3.connect(
                database=self["database"],
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


def enter_data(c_dict, db_choices):
    print("-" * 20)
    print("enter exit to exit installation")
    c_dict["_engine"] = _input("DB engine", c_dict["_engine"], choices=db_choices)
    if c_dict["_engine"] == "sqlite":
        c_dict["host"] = ""
        c_dict["user"] = ""
    else:
        c_dict["host"] = _input("DB host", c_dict["host"])
        c_dict["user"] = _input("DB user", c_dict["user"])
    c_dict["database"] = _input("DB name", c_dict["database"])
    if c_dict["_engine"] == "sqlite":
        c_dict["passwd"] = ""
        c_dict["port"] = 0
    else:
        def_port = {"mysql": 3306, "psql": 5432, "sqlite": 0}[c_dict["_engine"]]
        c_dict["passwd"] = _input("DB passwd", c_dict["passwd"])
        c_dict["port"] = _input("DB port", def_port)
    c_dict["engine"] = {
        "mysql": "django.db.backends.mysql",
        "psql": "django.db.backends.postgresql_psycopg2",
        "sqlite": "django.db.backends.sqlite3",
        }[c_dict["_engine"]]


def create_db_cf(opts):
    db_choices = [_key for _key in ["psql", "mysql", "sqlite"] if DB_PRESENT[_key]]
    c_dict = {
        "host": opts.host,
        "user": opts.user,
        "database": opts.database,
        "passwd": opts.passwd,
        "_engine": opts.engine,  # "psql" if "psql" in db_choices else db_choices[0],
    }
    while True:
        # enter all relevant data
        enter_data(c_dict, db_choices)
        test_obj = {"psql": test_psql, "mysql": test_mysql, "sqlite": test_sqlite}[c_dict["_engine"]](c_dict)
        if test_obj.test_connection():
            print("connection successfull")
            break
        else:
            print("cannot connect, please check your settings and / or the setup of your database:")
            test_obj.show_config()
    # content
    _content = [
        "DB_{}={}".format(
            key.upper(),
            str(c_dict[key]),
            ) for key in sorted(c_dict) if not key.startswith("_")
        ] + [""]
    print("The file {} should be readable for root and the uwsgi processes".format(DB_FILE))
    try:
        file(DB_FILE, "w").write("\n".join(_content))
    except:
        print("cannot create {}: {}".format(DB_FILE, process_tools.get_except_info()))
        print("content of {}:".format(DB_FILE))
        print("")
        print("\n".join(_content))
        print("")
        return False
    else:
        return True


def clear_migrations():
    print("clearing existing migrations")
    for mig_dir in MIGRATION_DIRS:
        fm_dir = os.path.join(LIB_DIR, mig_dir, "migrations")
        if os.path.isdir(fm_dir):
            print("clearing migrations for {}".format(mig_dir))
            shutil.rmtree(fm_dir)


def check_migrations():
    print("checking existing migrations")
    any_found = False
    for mig_dir in MIGRATION_DIRS:
        fm_dir = os.path.join(LIB_DIR, mig_dir, "migrations")
        if os.path.isdir(fm_dir):
            print("Found an existing migration dir {} for {}".format(fm_dir, mig_dir))
            any_found = True
    if any_found:
        print("please check your migrations")
        sys.exit(4)
    else:
        print("no migrations found, OK")


def get_pw(size=10):
    return "".join([string.ascii_letters[random.randint(0, len(string.ascii_letters) - 1)] for _idx in xrange(size)])


def check_for_pre17(opts):
    # BACKBONE_DIR = "/opt/python-init/lib/python/site-packages/initat/cluster/backbone"
    if os.path.isdir(PRE_MODELES_DIR):
        print("pre-1.7 models dir {} found".format(PRE_MODELES_DIR))
        # first step: move 1.7 models / serializers away
        _move_dirs = ["models", "serializers"]
        for _dir in _move_dirs:
            os.rename(os.path.join(BACKBONE_DIR, _dir), os.path.join(BACKBONE_DIR, ".{}".format(_dir)))
        # next step: move pre-models to current models
        os.rename(PRE_MODELES_DIR, os.path.join(BACKBONE_DIR, "models"))
        # next step: remove all serializer relations from model files
        for _entry in os.listdir(os.path.join(BACKBONE_DIR, "models")):
            if _entry.endswith(".py"):
                _path = os.path.join(BACKBONE_DIR, "models", _entry)
                new_lines = []
                _add = True
                for _line in file(_path, "r").readlines():
                    _line = _line.rstrip()
                    empty_line = True if not _line.strip() else False
                    _ser_line = _line.strip().startswith("class") and (_line.count("serializers.ModelSerializer") or _line.strip().endswith("serializer):"))
                    if not empty_line:
                        if _ser_line:
                            _add = False
                            new_lines.append("{} = True".format(_line.split()[1].split("(")[0]))
                        elif _line[0] != " ":
                            _add = True
                    if _add:
                        new_lines.append(_line)
                file(_path, "w").write("\n".join(new_lines))
        # next step: delete south models
        _mig_dir = os.path.join(BACKBONE_DIR, "migrations")
        for _entry in os.listdir(_mig_dir):
            if _entry[0].isdigit() and _entry.count("py"):
                _full_path = os.path.join(_mig_dir, _entry)
                print("    removing file {}".format(_full_path))
                os.unlink(_full_path)
        # next step: migrate backbone
        migrate_app("backbone", migrate_args=["--fake"])
        # next step: move pre-1.7 models dir away
        os.rename(os.path.join(BACKBONE_DIR, "models"), os.path.join(BACKBONE_DIR, ".models_pre17"))
        # next step: move 1.7 models back in place
        for _dir in _move_dirs:
            os.rename(os.path.join(BACKBONE_DIR, ".{}".format(_dir)), os.path.join(BACKBONE_DIR, _dir))


def migrate_app(_app, **kwargs):
    if not _app:
        print("")
        print("migrating everything...")
        print("")
    call_manage(["makemigrations", _app.split(".")[-1], "--noinput"] + kwargs.get("make_args", []))
    call_manage(["migrate", _app.split(".")[-1], "--noinput"] + kwargs.get("migrate_args", []))


def create_db(opts):
    if os.getuid():
        print("need to be root to create database")
        sys.exit(0)
    if opts.clear_migrations:
        clear_migrations()
    check_migrations()
    migrate_app("")
    # schemamigrations
    for _app in ["django.contrib.auth", "reversion", "static_precompiler"]:
        migrate_app(_app)
    if opts.no_initial_data:
        print("")
        print("skipping initial data insert")
        print("")
    else:
        if not opts.no_superuser:
            su_pw = get_pw(size=8)
            os.environ["DJANGO_SUPERUSER_PASSWORD"] = su_pw
            print("creating superuser {} (email {}, password is {})".format(opts.superuser, opts.email, su_pw))
            call_manage(["createsuperuser", "--login={}".format(opts.superuser), "--email={}".format(opts.email), "--noinput"])
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]
        call_update_funcs(opts)


def migrate_db(opts):
    if os.path.isdir(CMIG_DIR):
        check_for_pre17(opts)
        print("migrating current cluster database schemata")
        for _sync_app in SYNC_APPS:
            _app_dir = os.path.join(LIB_DIR, "initat", "cluster", _sync_app)
            if os.path.isdir(_app_dir):
                print("found app {}".format(_sync_app))
                # _mig_dir = os.path.join(_app_dir, "migrations")
                # if not os.path.isdir(_mig_dir):
                #    print("initial migration for {}".format(_sync_app))
                #    call_manage(["migrate", _sync_app, "--noinput"])
                # if os.path.isdir(_mig_dir):
                # _py_files = [_entry for _entry in os.listdir(_mig_dir) if _entry.endswith(".py")]
                # if _py_files == ["__init__.py"]:
                #    # initial schema migration call
                #    call_manage(["schemamigration", _sync_app, "--initial"])
                call_manage(["makemigrations", _sync_app, "--noinput"])
                call_manage(["migrate", _sync_app, "--noinput"])
        check_local_settings()
        for _app in ["backbone", "django.contrib.auth", "reversion", "static_precompiler"]:
            migrate_app(_app)
        call_update_funcs(opts)
    else:
        print("cluster migration dir {} not present, please create database".format(CMIG_DIR))
        sys.exit(5)


def call_update_funcs(opts):
    create_fixtures()
    call_manage(["create_cdg --name {}".format(opts.system_group_name)])
    call_manage(["migrate_to_domain_name"])
    call_manage(["migrate_to_config_catalog"])


def create_fixtures():
    call_manage(["create_fixtures"])
    call_manage(["init_csw_permissions"])


def check_db_rights():
    if os.path.isfile(DB_FILE):
        c_stat = os.stat(DB_FILE)
        if c_stat[stat.ST_UID] == 0 & c_stat[stat.ST_GID]:
            if not c_stat.st_mode & stat.S_IROTH:
                print "setting R_OTHER flag on {} (because owned by root.root)".format(DB_FILE)
                os.chmod(DB_FILE, c_stat.st_mode | stat.S_IROTH)


def _check_dirs():
    _missing_dirs = []
    for _dir in NEEDED_DIRS:
        if not os.path.isdir(_dir):
            try:
                os.makedirs(_dir)
            except:
                print("Cannot create directory '{}'".format(_dir))
        if not os.path.isdir(_dir):
            _missing_dirs.append(_dir)
    if _missing_dirs:
        print("{} missing: {}".format(logging_tools.get_plural("directory", len(_missing_dirs)), ", ".join(sorted(_missing_dirs))))
        sys.exit(6)


def main():
    default_pw = get_pw()
    my_p = argparse.ArgumentParser()
    db_choices = [_key for _key in ["psql", "mysql", "sqlite"] if DB_PRESENT[_key]]
    if db_choices:
        _def_engine = "psql" if "psql" in db_choices else db_choices[0]
    else:
        _def_engine = ""
    db_flags = my_p.add_argument_group("database options")
    db_flags.add_argument("--ignore-existing", default=False, action="store_true", help="Ignore existing db.cf file {} [%(default)s]".format(DB_FILE))
    db_flags.add_argument("--engine", default=_def_engine, type=str, help="choose database engine [%(default)s]", choices=db_choices)
    db_flags.add_argument("--use-existing", default=False, action="store_true", help="use existing db.cf file {} [%(default)s]".format(DB_FILE))
    db_flags.add_argument("--user", type=str, default="cdbuser", help="set name of database user")
    db_flags.add_argument("--passwd", type=str, default=default_pw, help="set password for database user")
    db_flags.add_argument("--database", type=str, default="cdbase", help="set name of cluster database")
    db_flags.add_argument("--host", type=str, default="localhost", help="set database host")
    mig_opts = my_p.add_argument_group("migration options")
    mig_opts.add_argument("--clear-migrations", default=False, action="store_true", help="clear migrations before database creationg [%(default)s]")
    mig_opts.add_argument(
        "--no-initial-data",
        default=False,
        action="store_true",
        help="disable inserting of initial data [%(default)s], only usefull for the migration form an older version of the clustersoftware"
    )
    mig_opts.add_argument("--migrate", default=False, action="store_true", help="migrate current cluster database [%(default)s]")
    create_opts = my_p.add_argument_group("database creation options")
    create_opts.add_argument("--superuser", default="admin", type=str, help="name of the superuser [%(default)s]")
    create_opts.add_argument("--email", default="admin@localhost", type=str, help="admin address of superuser [%(default)s]")
    create_opts.add_argument("--no-superuser", default=False, action="store_true", help="do not create a superuser [%(default)s]")
    create_opts.add_argument("--system-group-name", default="system", type=str, help="name of system group [%(default)s]")
    upd_opts = my_p.add_argument_group("update options")
    upd_opts.add_argument("--only-fixtures", default=False, action="store_true", help="only call create_fixtures")
    auc_flags = my_p.add_argument_group("automatic update options")
    auc_flags.add_argument("--enable-auto-update", default=False, action="store_true", help="enable automatic update [%(default)s]")
    auc_flags.add_argument("--disable-auto-update", default=False, action="store_true", help="disable automatic update [%(default)s]")
    opts = my_p.parse_args()
    _check_dirs()
    DB_MAPPINGS = {
        "psql": "python-modules-psycopg2",
        "mysql": "python-modules-mysql",
        "sqlite": "python-init",
    }
    if not all(DB_PRESENT.values()):
        print("missing databases layers:")
        for _key in DB_PRESENT.keys():
            if not DB_PRESENT[_key]:
                print(" {:6s} : {}".format(_key, DB_MAPPINGS[_key]))
    if not any(DB_PRESENT.values()):
        print("No Database access libraries installed, please install some of them")
        sys.exit(1)
    # flag: setup db_cf data
    if opts.enable_auto_update:
        if os.path.exists(AUTO_FLAG):
            print("auto_udpate_flag {} already exists".format(AUTO_FLAG))
        else:
            try:
                file(AUTO_FLAG, "w").write("\n")
            except:
                print("cannot create auto_update_flag {}: {}".format(AUTO_FLAG, process_tools.get_except_info()))
                sys.exit(-1)
            else:
                print("created auto_update_flag {}".format(AUTO_FLAG))
    elif opts.disable_auto_update:
        if os.path.isfile(AUTO_FLAG):
            try:
                os.unlink(AUTO_FLAG)
            except:
                print("cannot remove auto_update_flag {}: {}".format(AUTO_FLAG, process_tools.get_except_info()))
                sys.exit(-1)
            else:
                print("removed auto_update_flag {}".format(AUTO_FLAG))
        else:
            print("auto_udpate_flag {} not present".format(AUTO_FLAG))
    else:
        db_exists = os.path.exists(DB_FILE)
        call_create_db = True
        call_migrate_db = False
        call_create_fixtures = False
        if db_exists:
            if opts.only_fixtures:
                setup_db_cf = False
                call_create_db = False
                call_migrate_db = False
                call_create_fixtures = True
            elif opts.migrate:
                setup_db_cf = False
                call_create_db = False
                call_migrate_db = True
            else:
                if opts.use_existing:
                    # use existing db_cf
                    setup_db_cf = False
                else:
                    if opts.ignore_existing:
                        print("DB access file {} already exists, ignoring ...".format(DB_FILE))
                        setup_db_cf = True
                    else:
                        print("DB access file {} already exists, exiting ...".format(DB_FILE))
                        sys.exit(1)
        else:
            setup_db_cf = True
            if opts.use_existing:
                print("DB access file {} does not exist ...".format(DB_FILE))
        if setup_db_cf:
            if not create_db_cf(opts):
                print("Creation of {} not successfull, exiting".format(DB_FILE))
                sys.exit(3)
        check_db_rights()
        if call_create_db:
            create_db(opts)
        if call_migrate_db:
            migrate_db(opts)
        if call_create_fixtures:
            create_fixtures()

if __name__ == "__main__":
    main()
