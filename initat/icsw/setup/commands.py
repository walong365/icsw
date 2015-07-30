# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel init.at
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
""" database setup for NOCTUA / CORVUS / NESTOR """

import os
import pwd
import importlib
import fnmatch
import grp
import shutil
import stat
import sys
import time
import subprocess

from initat.tools import logging_tools, process_tools, config_store

from .utils import generate_password, DirSave, get_icsw_root
from .connection_tests import test_psql, test_mysql, test_sqlite

CS_NAME = "icsw.general"
ICSW_ROOT = get_icsw_root()
CMIG_DIR = os.path.join(ICSW_ROOT, "initat", "cluster", "backbone", "migrations")
MIGRATION_DIRS = [
    "reversion",
    "django/contrib/auth",
    "initat/cluster/backbone",
    "initat/cluster/liebherr",
]

# which apps needs syncing
SYNC_APPS = ["liebherr", "licadmin"]

NEEDED_DIRS = ["/var/log/cluster"]

BACKBONE_DIR = os.path.join(ICSW_ROOT, "initat/cluster/backbone")
PRE_MODELS_DIR = os.path.join(BACKBONE_DIR, "models16")
MODELS_DIR = os.path.join(BACKBONE_DIR, "models")
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

AVAILABLE_DATABASES = [key for key, value in DB_PRESENT.items() if value]
if "psql" in AVAILABLE_DATABASES:
    DEFAULT_ENGINE = "psql"
else:
    try:
        DEFAULT_ENGINE = AVAILABLE_DATABASES[0]
    except IndexError:
        DEFAULT_ENGINE = ""

DB_FILE = "/etc/sysconfig/cluster/db.cf"


def call_manage(args, **kwargs):
    _output = kwargs.get("output", False)
    command = [os.path.join(ICSW_ROOT, "initat", "cluster", "manage.py")] + args
    com_str = " ".join(command)
    s_time = time.time()
    c_stat = 0
    try:
        c_out = subprocess.check_output(command)
    except subprocess.CalledProcessError as e:
        c_stat = e.returncode
        c_out = e.output

    e_time = time.time()
    if c_stat == 256 and c_out.lower().count("nothing seems to have changed"):
        c_stat = 0
    if c_stat:
        print(
            "something went wrong calling '{}' in {} ({:d}):".format(
                com_str,
                logging_tools.get_diff_time_str(e_time - s_time),
                c_stat
            )
        )
        for _line in c_out.split("\n"):
            print("  {}".format(_line))
        if _output:
            return False, c_out
        else:
            return False
    else:
        print(
            "success calling '{}' in {}".format(
                com_str,
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        # print c_out
        if _output:
            return True, c_out
        else:
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


def enter_data(c_dict, engine_selected, database_selected):
    print("-" * 20)
    print("enter exit to exit installation")
    if not engine_selected:
        c_dict["_engine"] = _input("DB engine", c_dict["_engine"], choices=AVAILABLE_DATABASES)
    if c_dict["_engine"] == "sqlite":
        c_dict["host"] = ""
        c_dict["user"] = ""
    else:
        c_dict["host"] = _input("DB host", c_dict["host"])
        c_dict["user"] = _input("DB user", c_dict["user"])
    if not database_selected:
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
    c_dict = {
        "host": opts.host,
        "user": opts.user,
        "database": opts.database if opts.database is not None else DEFAULT_DATABASE,
        "passwd": opts.passwd,
        "_engine": opts.engine if opts.engine is not None else DEFAULT_ENGINE,
    }
    while True:
        # enter all relevant data
        enter_data(c_dict, opts.engine is not None, opts.database is not None)

        if c_dict["_engine"] == "sqlite":

            if opts.db_path is None or opts.db_file_owner is None or opts.db_file_group is None:
                print(
                    "please set path to the sqlite file directory via --db-path and owner and group " +
                    "for the database file via --db-file-owner and --db-file-group"
                )
                return False

            if not os.path.isdir(opts.db_path):
                print("database dir {} does not exist, creating...".format(opts.db_path))
                os.makedirs(opts.db_path)
            file_path = os.path.join(opts.db_path, opts.database)

            # try numeric
            try:
                uid = int(opts.db_file_owner)
            except ValueError:
                try:
                    uid = pwd.getpwnam(opts.db_file_owner).pw_uid
                except KeyError:
                    print("invalid user name {}".format(opts.db_file_owner))
                    return False

            try:
                gid = int(opts.db_file_group)
            except ValueError:
                try:
                    gid = grp.getgrnam(opts.db_file_group).gr_gid
                except KeyError:
                    print("invalid group {}".format(opts.db_file_group))
                    return False

            # create db file
            open(file_path, 'a').close()
            # set owner/mode
            os.chown(file_path, uid, gid)
            os.chmod(file_path, int(opts.db_file_mode, 8))
            # sqlite also requires the directory to be writable, probably for temporary files
            os.chown(opts.db_path, uid, gid)

            c_dict["database"] = file_path

        test_obj = {"psql": test_psql, "mysql": test_mysql, "sqlite": test_sqlite}[c_dict["_engine"]](c_dict)
        if test_obj.test_connection():
            print("connection successful")
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
        fm_dir = os.path.join(ICSW_ROOT, mig_dir, "migrations")
        if os.path.isdir(fm_dir):
            print("clearing migrations for {}".format(mig_dir))
            shutil.rmtree(fm_dir)


def check_migrations():
    print("checking existing migrations")
    any_found = False
    for mig_dir in MIGRATION_DIRS:
        fm_dir = os.path.join(ICSW_ROOT, mig_dir, "migrations")
        if os.path.isdir(fm_dir):
            print("Found an existing migration dir {} for {}".format(fm_dir, mig_dir))
            any_found = True
    if any_found:
        print("please check your migrations")
        sys.exit(4)
    else:
        print("no migrations found, OK")


def check_for_pre17(opts):
    if os.path.isdir(PRE_MODELS_DIR):
        print("pre-1.7 models dir {} found".format(PRE_MODELS_DIR))
        # first step: move 1.7 models / serializers away
        _move_dirs = ["models", "serializers"]
        for _dir in _move_dirs:
            os.rename(
                os.path.join(BACKBONE_DIR, _dir),
                os.path.join(BACKBONE_DIR, ".{}".format(_dir))
            )
        # next step: move pre-models to current models
        os.rename(PRE_MODELS_DIR, MODELS_DIR)
        # next step: remove all serializer relations from model files
        _files_found = 0
        _INIT_MODS = [
            "ipvx_tools", "logging_tools", "net_tools", "process_tools", "server_command"
        ]
        for _path in [os.path.join(MODELS_DIR, _entry) for _entry in os.listdir(MODELS_DIR) if _entry.endswith(".py")]:
            _files_found += 1
            new_lines = []
            _add = True
            _removed, _kept = (0, 0)
            for _line_num, _line in enumerate(file(_path, "r").readlines(), 1):
                _line = _line.rstrip()
                empty_line = True if not _line.strip() else False
                _ser_line = _line.strip().startswith("class") and (_line.count("serializers.ModelSerializer") or _line.strip().endswith("serializer):"))
                _import_line = _line.strip().startswith("import ") and _line.strip().split()[1] in _INIT_MODS
                if not empty_line:
                    if _ser_line:
                        print("detected serializer line '{}'@{:d}".format(_line, _line_num))
                        _add = False
                        # add dummy declaration
                        new_lines.append("{} = True".format(_line.split()[1].split("(")[0]))
                    elif _import_line:
                        print("detected import INIT line '{}'@{:d}".format(_line, _line_num))
                        _add = True
                        _line = "from initat.tools import {}".format(_line.strip().split()[1])
                    elif _line[0] != " ":
                        _add = True
                    else:
                        # leave _add flag on old value
                        pass
                if _add:
                    new_lines.append(_line)
                    _kept += 1
                else:
                    _removed += 1
            print("file {}: removed {:d}, kept {:d}".format(_path, _removed, _kept))
            print("")
            file(_path, "w").write("\n".join(new_lines))
        if not _files_found:
            print("no .py-files found in {}, exit...".format(MODELS_DIR))
            sys.exit(-1)
        # next step: delete south models
        _mig_dir = os.path.join(BACKBONE_DIR, "migrations")
        _mig_save_dict = {}
        for _entry in sorted(os.listdir(_mig_dir)):
            if _entry[0].isdigit() and _entry.count("py"):
                _num = int(_entry[0:4])
                _path = os.path.join(_mig_dir, _entry)
                if _num >= 799:
                    _mig_save_dict[_path] = file(_path, "r").read()
                    print("    storing file {} for later restore".format(_path))
                print("    removing file {}".format(_path))
                os.unlink(_path)
        # next step: migrate backbone
        migrate_app("backbone", migrate_args=["--fake"])
        # next step: move pre-1.7 models dir away
        os.rename(os.path.join(MODELS_DIR), os.path.join(BACKBONE_DIR, ".models_pre17"))
        # next step: move 1.7 models back in place
        for _dir in _move_dirs:
            os.rename(os.path.join(BACKBONE_DIR, ".{}".format(_dir)), os.path.join(BACKBONE_DIR, _dir))
        # restore migation files
        for _key, _value in _mig_save_dict.iteritems():
            file(_key, "w").write(_value)


def check_for_0800(opts):
    # move away all migrations above 0800
    ds0 = DirSave(CMIG_DIR, 800)
    _list_stat, _list_out = call_manage(["migrate", "backbone", "--list", "--no-color"], output=True)
    ds0.restore()
    ds0.cleanup()
    if not _list_stat:
        sys.exit(7)
    applied = True if _list_out.count("[X] 0800_base") else False
    if applied:
        print("0800_base already applied")
    else:
        print("0800_base not reached, migrating to stable 0800")
        # move away all migrations >= 0800
        ds1 = DirSave(CMIG_DIR, 799)
        # rename models dir
        os.rename(MODELS_DIR, MODELS_DIR_SAVE)
        os.rename(Z800_MODELS_DIR, MODELS_DIR)
        # migrate
        migrate_app("backbone")
        # move back
        os.rename(MODELS_DIR, Z800_MODELS_DIR)
        os.rename(MODELS_DIR_SAVE, MODELS_DIR)
        # move all files back
        ds1.restore(800)
        # fake migration
        call_manage(["makemigrations", "backbone", "--merge", "--noinput"])
        call_manage(["migrate", "backbone", "--noinput", "--fake"])
        ds1.restore()
        ds1.cleanup()


def migrate_app(_app, **kwargs):
    if not _app:
        print("")
        print("migrating everything...")
        print("")
    call_manage(["makemigrations", _app.split(".")[-1], "--noinput"] + kwargs.get("make_args", []))
    call_manage(["migrate", _app.split(".")[-1], "--noinput"] + kwargs.get("migrate_args", []))


def apply_migration(_app, **kwargs):
    success = call_manage(["migrate", _app.split(".")[-1], "--noinput"] + kwargs.get("migrate_args", []))
    return success


def create_db(opts):
    if os.getuid():
        print("need to be root to create database")
        sys.exit(0)
    # for fixed migration we do not touch existing migration files
    # if opts.clear_migrations:
    #     clear_migrations()
    # check_migrations()
    # schemamigrations
    ds0 = DirSave(CMIG_DIR, 799)
    os.environ["INIT_REMOVE_APP_NAME_1"] = "django.contrib.sites"
    os.environ["INIT_REMOVE_APP_NAME_2"] = "initat.cluster."
    for _app in ["auth", "contenttypes"]:
        apply_migration(_app)
    del os.environ["INIT_REMOVE_APP_NAME_1"]
    for _app in ["sites"]:
        apply_migration(_app)
    del os.environ["INIT_REMOVE_APP_NAME_2"]
    ds0.restore()
    ds0.cleanup()
    # we now go for the 0800
    check_for_0800(opts)
    apply_migration("backbone")
    # reversion needs access to proper user model
    apply_migration("reversion")

    # migrate apps without any dependencies
    for _app in ["django.contrib.admin", "django.contrib.sessions"]:
        apply_migration(_app)

    if opts.no_initial_data:
        print("")
        print("skipping initial data insert")
        print("")
    else:
        if not opts.no_superuser:
            su_pw = generate_password(size=8)
            os.environ["DJANGO_SUPERUSER_PASSWORD"] = su_pw
            print("creating superuser {} (email {}, password is {})".format(opts.superuser, opts.email, su_pw))
            call_manage(["createsuperuser", "--login={}".format(opts.superuser), "--email={}".format(opts.email), "--noinput"])
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]
        call_manage(["createinitialrevisions"])
        call_update_funcs(opts)


def migrate_db(opts):
    if os.path.isdir(CMIG_DIR):
        check_for_pre17(opts)
        check_for_0800(opts)
        print("migrating current cluster database schemata")
        for _sync_app in SYNC_APPS:
            _app_dir = os.path.join(ICSW_ROOT, "initat", "cluster", _sync_app)
            if os.path.isdir(_app_dir):
                print("found app {}, disabled automatic migrations, please migrate by hand".format(_sync_app))
                # call_manage(["makemigrations", _sync_app, "--noinput"])
                # call_manage(["migrate", _sync_app, "--noinput"])
        subprocess.check_output("/opt/cluster/sbin/pis/check_local_settings.py")
        auth_app_name = "django.contrib.auth"
        for _app in ["backbone", auth_app_name, "reversion", "django.contrib.admin", "django.contrib.sessions"]:
            if app_has_unapplied_migrations(_app.split(".")[-1]):
                print("migrating app {}".format(_app))
                success = apply_migration(_app)

                if not success and _app == auth_app_name:
                    # in old installations, we used to have a custom migration due to a patch for a model in auth.
                    # django 1.8 then added own migrations for auth, which resulted in a divergence.
                    # we can however just fix that by merging the migrations, which we attempt here.
                    print("attempting to fix auth migration divergence due to django-1.8")
                    call_manage(["makemigrations", "auth", "--merge", "--noinput"])
                    # try to migrate again (can't do anything in case of failure though)
                    apply_migration(_app)

            else:
                print("no unapplied migrations found for app {}".format(_app))
        print("")
        call_manage(["createinitialrevisions"])
        call_update_funcs(opts)
    else:
        print("cluster migration dir {} not present, please create database".format(CMIG_DIR))
        sys.exit(5)


def call_update_funcs(opts):
    create_fixtures()
    call_manage(["create_cdg", "--name", opts.system_group_name])
    call_manage(["migrate_to_domain_name"])
    call_manage(["migrate_to_new_logging_scheme"])
    call_manage(["migrate_to_config_catalog"])
    call_manage(["ensure_cluster_id"])


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


def setup_django():
    import django
    django.setup()

    from django.db.migrations.recorder import MigrationRecorder
    from django.apps import apps
    from django.db import connection
    return connection, apps, MigrationRecorder


def app_has_unapplied_migrations(app_name):
    # Note: We cannot configure Django globally, because some config files
    # might not exist yet.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

    connection, apps, MigrationRecorder = setup_django()

    recorder = MigrationRecorder(connection)
    applied_migrations = {
        migration_name for app_name_, migration_name in recorder.applied_migrations()
        if app_name_ == app_name
    }
    migration_directory = os.path.join(apps.get_app_path(app_name), "migrations")
    migrations_on_disk = set(
        fnmatch.filter(os.listdir(migration_directory), "*.py")
    )
    migrations_on_disk = {os.path.splitext(i)[0] for i in migrations_on_disk}
    migrations_on_disk.remove("__init__")
    return len(migrations_on_disk - applied_migrations) > 0


def main(args):
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
        print("No database access libraries installed, please install some of them")
        sys.exit(1)

    # flag: setup db_cf data
    if args.disable_auto_update:
        cs_store = config_store.ConfigStore(CS_NAME)
        cs_store["db.auto.update"] = False
        cs_store.write()
        print("disabled auto_update_flag")
    else:
        cs_store = config_store.ConfigStore(CS_NAME)
        cs_store["db.auto.update"] = True
        cs_store.write()
        print("enabled auto_update_flag")
    db_exists = os.path.exists(DB_FILE)
    call_create_db = True
    call_migrate_db = False
    call_create_fixtures = False
    if db_exists:
        if args.only_fixtures:
            setup_db_cf = False
            call_create_db = False
            call_migrate_db = False
            call_create_fixtures = True
        elif args.migrate:
            setup_db_cf = False
            call_create_db = False
            call_migrate_db = True
        else:
            if args.use_existing:
                # use existing db_cf
                setup_db_cf = False
            else:
                if args.ignore_existing:
                    print("DB access file {} already exists, ignoring ...".format(DB_FILE))
                    setup_db_cf = True
                else:
                    print("DB access file {} already exists, exiting ...".format(DB_FILE))
                    sys.exit(1)
    else:
        setup_db_cf = True
        if args.use_existing:
            print("DB access file {} does not exist ...".format(DB_FILE))
    if setup_db_cf:
        if not create_db_cf(args):
            print("Creation of {} not successfull, exiting".format(DB_FILE))
            sys.exit(3)
    check_db_rights()
    if call_create_db:
        create_db(args)
    if call_migrate_db:
        migrate_db(args)
    if call_create_fixtures:
        create_fixtures()
