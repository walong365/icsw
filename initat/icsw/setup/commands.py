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
""" database setup for NOCTUA / CORVUS / NESTOR """

import fnmatch
import grp
import pwd
import os
import shutil
import stat
import subprocess
import sys
import time

from initat.constants import GEN_CS_NAME, ICSW_ROOT, BACKBONE_DIR, DB_ACCESS_CS_NAME, \
    CLUSTER_DIR
from initat.tools import logging_tools, process_tools, config_store
from .connection_tests import test_psql, test_mysql, test_sqlite
from .constants import *
from .utils import generate_password, DirSave, remove_pyco, DummyFile


DB_CS_FILENAME = config_store.ConfigStore.build_path(DB_ACCESS_CS_NAME)


class SetupLogger(object):
    nest_level = 0

    def __init__(self, func):
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self._func = func

    def __repr__(self):
        return self._func

    def debug(self, what):
        print(
            "<DBG>{}".format(what)
        )

    def __call__(self, *args, **kwargs):
        SetupLogger.nest_level += 1
        _pf = "  " * SetupLogger.nest_level
        self.debug(
            "{}[{:d}] Entering {} ({}{}, {}{})".format(
                _pf,
                SetupLogger.nest_level,
                self.__name__,
                logging_tools.get_plural("arg", len(args)),
                " [{}]".format(", ".join([str(_val) for _val in args])) if args else "",
                logging_tools.get_plural("kwarg", len(kwargs)),
                " [{}]".format(", ".join(list(kwargs.keys()))) if kwargs else "",
            )
        )
        s_time = time.time()
        ret_value = self._func(*args, **kwargs)
        e_time = time.time()
        self.debug(
            "{}[{:d}] Leaving {}, call took {}".format(
                _pf,
                SetupLogger.nest_level,
                self.__name__,
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        SetupLogger.nest_level -= 1
        return ret_value


@SetupLogger
def selinux_enabled():
    _bin = process_tools.find_file("getenforce")
    if _bin:
        c_out = subprocess.check_output(_bin)
        if c_out.strip() == "Enforcing":
            return True
        return False
    else:
        return False


@SetupLogger
def call_manage(args, **kwargs):
    return call_ext_programm(args, prog="manage", **kwargs)


@SetupLogger
def call_icsw(args, **kwargs):
    return call_ext_programm(args, prog="icsw", **kwargs)


@SetupLogger
def call_ext_programm(args, **kwargs):
    prog = kwargs.pop("prog")
    _output = kwargs.get("output", False)
    _show_output = kwargs.get("show_output", False)
    if prog == "manage":
        command = [os.path.join(ICSW_ROOT, "initat", "cluster", "manage.py")] + args
    else:
        command = [os.path.join(ICSW_ROOT, "initat", "icsw", "main.py")] + args
    com_str = " ".join(command)
    s_time = time.time()
    c_stat = 0
    try:
        c_out = subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        c_stat = e.returncode
        c_out = e.output
    c_out = c_out.decode("utf-8")

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
        if _show_output:
            print(c_out)
        if _output:
            return True, c_out
        else:
            return True


@SetupLogger
def _input(in_str, default, **kwargs):
    _choices = kwargs.get("choices", [])
    is_int = isinstance(default, int)
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
    _cur_inp = None

    while sys.stdin.isatty():
        try:
            sys.__stdout__.write("{:<30s} : ".format("{} ({})".format(in_str, _def_str)))
            sys.__stdout__.flush()
            _cur_inp = input()
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


@SetupLogger
def enter_data(c_dict, opts):
    print("-" * 20)
    print("enter exit to exit installation")

    # if parameters have been specified in opts, we do not query any more.

    if opts.engine is None:
        c_dict["_engine"] = _input("DB engine", c_dict["_engine"], choices=AVAILABLE_DATABASES)
    if c_dict["_engine"] == "sqlite":
        c_dict["host"] = ""
        c_dict["user"] = ""
    else:
        if opts.host is None:
            c_dict["host"] = _input("DB host", c_dict["host"])
        if opts.user is None:
            c_dict["user"] = _input("DB user", c_dict["user"])
    if opts.database is None:
        c_dict["database"] = _input("DB name", c_dict["database"])
    if c_dict["_engine"] == "sqlite":
        c_dict["passwd"] = ""
        c_dict["port"] = 0
    else:
        def_port = {"mysql": 3306, "psql": 5432, "sqlite": 0}[c_dict["_engine"]]
        if opts.passwd is None:
            c_dict["passwd"] = _input("DB passwd", c_dict["passwd"])
        if opts.port is None:
            c_dict["port"] = _input("DB port", def_port)
    c_dict["engine"] = {
        "mysql": "django.db.backends.mysql",
        "psql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }[c_dict["_engine"]]


@SetupLogger
def init_webfrontend(opts):
    if False:
        for _what, _command, _target in [
            ("collecting static", "collectstatic --noinput -c", None),
            ("building url_list", "show_icsw_urls", os.path.join(ICSW_ROOT, "initat", "cluster", "frontend", "templates", "all_urls.html")),
        ]:
            print(_what)
            _success, _output = call_manage(_command.split(), output=True)
            if _success and _target:
                print(
                    "    writing {} to {}".format(
                        logging_tools.get_size_str(len(_output), long_format=True),
                        _target,
                    )
                )
                open(_target, "w").write(_output)
    for _what, _command, _target in [
        ("modify app.js", "inject_addons --srcfile /srv/www/init.at/icsw/app.js --modify --with-addons=yes", None),
        ("modify main.html", "inject_addons --srcfile /srv/www/init.at/icsw/main.html --modify --with-addons=yes", None),
    ]:
        print(_what)
        _success, _output = call_manage(_command.split(), output=True)
        if not _success:
            print("Something went wrong ({:d}): {}".format(_success, _output))
    # already configured; run collectstatic
    _RELOAD_FLAG = "/opt/cluster/etc/uwsgi/reload/webfrontend.touch"
    if os.path.exists("/opt/cluster/etc/uwsgi/reload"):
        print("touching reload flag {}".format(_RELOAD_FLAG))
        open(_RELOAD_FLAG, "w").write("")
    else:
        print("no uwsgi reload-dir found, please (re)start uwsgi-init via")
        print("")
        print("icsw service restart uwsgi-init")
        print("")


@SetupLogger
def create_db_cf(opts):
    c_dict = {
        "host": opts.host,
        "user": opts.user,
        "port": opts.port,
        "database": opts.database,
        "passwd": opts.passwd,
        "_engine": opts.engine,
    }
    if c_dict['database'] is None:
        c_dict['database'] = DEFAULT_DATABASE
    if c_dict['_engine'] is None:
        c_dict['_engine'] = DEFAULT_ENGINE

    all_parameters_forced = all(entry is not None for entry in c_dict.values())

    connection_successful = False
    while not connection_successful:
        # enter all relevant data
        enter_data(
            c_dict,
            opts,
        )

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
            connection_successful = True
        else:
            print("cannot connect, please check your settings and / or the setup of your database:")
            test_obj.show_config()

            if all_parameters_forced:
                # don't loop if all parameters were forced
                break

    if not connection_successful:
        print("failed to connect to database")
        return False

    # content
    _cs = config_store.ConfigStore(DB_ACCESS_CS_NAME, access_mode=config_store.AccessModeEnum.LOCAL, fix_prefix_on_read=False)
    for _key in sorted(c_dict):
        if not _key.startswith("_"):
            _cs["db.{}".format(_key.lower())] = c_dict[_key]
    _cs["db.info"] = "Database from {}".format(time.ctime())
    _cs.set_type("db.passwd", "password")
    print("The file {} should be readable for root and the uwsgi processes".format(DB_CS_FILENAME))
    try:
        _cs.write()
    except:
        print("cannot create {}: {}".format(DB_CS_FILENAME, process_tools.get_except_info()))
        print("content of {}:".format(DB_ACCESS_CS_NAME))
        print("")
        print(_cs.show())
        print("")
        return False
    else:
        return True


@SetupLogger
def clear_migrations():
    print("clearing existing migrations")
    for mig_dir in MIGRATION_DIRS:
        fm_dir = os.path.join(ICSW_ROOT, mig_dir, "migrations")
        if os.path.isdir(fm_dir):
            print("clearing migrations for {}".format(mig_dir))
            shutil.rmtree(fm_dir)


@SetupLogger
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


def alarm(msg):
    _len = len(msg)
    print("")
    print("*" * (_len + 8))
    print("*** {} ***".format(msg))
    print("*" * (_len + 8))
    print("")


@SetupLogger
def check_for_0800(opts):
    # move away all migrations above 0800
    ds0 = DirSave(CMIG_DIR, 800)
    # create dummy 0001_initial.py file for the list-command to succeed
    dummy_mig = DummyFile(
        os.path.join(MIGRATIONS_DIR, "0001_initial.py"),
        """
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]
"""
    )
    _list_stat, _list_out = call_manage(["showmigrations", "backbone", "--no-color"], output=True)
    dummy_mig.restore()
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
        alarm("0800 MODELS ARE NOW ACTIVE")
        os.rename(MODELS_DIR, MODELS_DIR_SAVE)
        os.rename(Z800_MODELS_DIR, MODELS_DIR)
        os.environ["ICSW_0800_MIGRATION"] = "yes"
        # migrate (to 0800_models version)
        migrate_app("backbone")
        del os.environ["ICSW_0800_MIGRATION"]
        # move back
        os.rename(MODELS_DIR, Z800_MODELS_DIR)
        os.rename(MODELS_DIR_SAVE, MODELS_DIR)
        # move all files back
        ds1.restore(800)
        alarm("0800 models no longer active")
        # fake migration (to 0800)
        call_manage(["makemigrations", "backbone", "--merge", "--noinput"])
        if not os.path.exists(os.path.join(MIGRATIONS_DIR, "0801_merge.py")):
            # create dummy merge file
            alarm("creating dummy merge file")
            call_manage(["makemigrations", "backbone", "-n", "merge", "--empty", "--noinput"])
        call_manage(["migrate", "backbone", "--noinput", "--fake"])
        ds1.restore()
        ds1.cleanup()


@SetupLogger
def migrate_app(_app, **kwargs):
    if not _app:
        print("")
        print("migrating everything...")
        print("")
    else:
        print("calling makemigrations / migrate for app {}".format(_app))
    call_manage(["makemigrations", _app.split(".")[-1], "--noinput"] + kwargs.get("make_args", []))
    call_manage(["migrate", _app.split(".")[-1], "--noinput"] + kwargs.get("migrate_args", []))


@SetupLogger
def apply_migration(_app, **kwargs):
    success = call_manage(
        [
            "migrate", _app.split(".")[-1]
        ] + kwargs.get("target_migration", []) + [
            "--noinput"
        ] + kwargs.get("migrate_args", [])
    )
    return success


@SetupLogger
def create_db(opts, first_run):
    if os.getuid():
        print("need to be root to create database")
        sys.exit(0)
    # for fixed migration we do not touch existing migration files
    # if opts.clear_migrations:
    #     clear_migrations()
    # check_migrations()
    # schemamigrations
    if first_run:
        print("Doing fast initial migration")
        # first step: migrate contenttypes
        DummyFile(
            os.path.join(MIGRATIONS_DIR, "0001_initial.py"),
            """
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
    ]
    """
        )
        DummyFile(
            os.path.join(MIGRATIONS_DIR, "0801_merge.py"),
            """
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0800_base'),
    ]
    """
        )
        # first step: fast sync without migrations
        os.environ["ICSW_DISABLE_MIGRATIONS"] = "yes"
        apply_migration("", migrate_args=["--run-syncdb"])
        del os.environ["ICSW_DISABLE_MIGRATIONS"]
        # second step: create dummy migrations
        apply_migration("contenttypes", migrate_args=["--fake-initial", "--fake"])
        # go to migration 0982'
        apply_migration("backbone", target_migration=["0982"], migrate_args=["--fake-initial", "--fake"])
        apply_migration("admin", migrate_args=["--fake-initial", "--fake"])
        apply_migration("reversion", migrate_args=["--fake-initial", "--fake"])
        apply_migration("backbone", migrate_args=["--fake-initial", "--fake"])
        apply_migration("auth", migrate_args=["--fake-initial", "--fake"])
        apply_migration("sessions", migrate_args=["--fake-initial", "--fake"])
        apply_migration("sites", migrate_args=["--fake-initial", "--fake"])
    else:
        ds0 = DirSave(CMIG_DIR, 799)
        os.environ["INIT_REMOVE_APP_NAME_1"] = "django.contrib.sites"
        os.environ["INIT_REMOVE_APP_NAME_2"] = "initat.cluster."
        for _app in ["auth", "contenttypes", "sites"]:
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


@SetupLogger
def migrate_db(opts):
    remove_pyco(BACKBONE_DIR)
    if os.path.isdir(CMIG_DIR):
        check_for_0800(opts)
        _merge_file = os.path.join(MIGRATIONS_DIR, "0801_merge.py")
        if not os.path.exists(_merge_file):
            alarm("merge_file not found, skipping migration")
        else:
            print("migrating current cluster database schemata")
            for _sync_app in SYNC_APPS:
                _app_dir = os.path.join(ICSW_ROOT, "initat", "cluster", _sync_app)
                if os.path.isdir(_app_dir):
                    print("found app {}, disabled automatic migrations, please migrate by hand".format(_sync_app))
                    # call_manage(["makemigrations", _sync_app, "--noinput"])
                    # call_manage(["migrate", _sync_app, "--noinput"])
            subprocess.check_output("/opt/cluster/sbin/pis/check_content_stores_server.py")
            auth_app_name = "django.contrib.auth"
            for _app in ["backbone", auth_app_name, "reversion", "django.contrib.admin", "django.contrib.sessions", "django.contrib.sites"]:
                if app_has_unapplied_migrations(_app.split(".")[-1]):
                    print("migrating app {}".format(_app))
                    success = apply_migration(_app)

                    if not success:
                        if _app == auth_app_name:
                            # in old installations, we used to have a custom migration due to a patch for a model in auth.
                            # django 1.8 then added own migrations for auth, which resulted in a divergence.
                            # we can however just fix that by merging the migrations, which we attempt here.
                            print("attempting to fix auth migration divergence due to django-1.8")
                            call_manage(["makemigrations", "auth", "--merge", "--noinput"])
                            # try to migrate again (can't do anything in case of failure though)
                            apply_migration(_app)
                        elif _app == "backbone":
                            print("error in migrating {}, trying to merge auth".format(_app))
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


@SetupLogger
def call_update_funcs(opts):
    from initat.cluster.backbone.models.internal import BackendConfigFileTypeEnum
    from initat.host_monitoring.constants import JSON_DEFINITION_FILE
    create_version_entries()
    create_fixtures()
    call_manage(["create_cdg", "--name", opts.system_group_name])
    call_manage(["migrate_to_domain_name"])
    call_manage(["migrate_to_config_catalog"])
    # at first sync config enums
    call_icsw(["config", "enum", "--sync"])
    # install new moncc file
    call_icsw(
        [
            "config",
            "upload",
            "--type",
            BackendConfigFileTypeEnum.mcc_json.name,
            "--mode",
            "cjson",
            os.path.join(CLUSTER_DIR, "share", "json_defs", JSON_DEFINITION_FILE)
        ]
    )
    # install new monioring commands
    call_manage(
        [
            "link_mcc_commands",
        ]
    )
    # then init ova system
    call_icsw(["license", "ova", "--init"])


@SetupLogger
def create_version_entries():
    call_manage(["create_version_entries"], show_output=True)


@SetupLogger
def create_fixtures():
    call_manage(["create_icsw_fixtures"])
    call_manage(["init_icsw_permissions", "--modify"])


@SetupLogger
def check_db_rights():
    if os.path.isfile(DB_CS_FILENAME):
        c_stat = os.stat(DB_CS_FILENAME)
        if c_stat[stat.ST_UID] == 0 & c_stat[stat.ST_GID]:
            if not c_stat.st_mode & stat.S_IROTH:
                print("setting R_OTHER flag on {} (because owned by root.root)".format(DB_CS_FILENAME))
                os.chmod(DB_CS_FILENAME, c_stat.st_mode | stat.S_IROTH)


@SetupLogger
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
        print(
            "{} missing: {}".format(
                logging_tools.get_plural("directory", len(_missing_dirs)),
                ", ".join(sorted(_missing_dirs))
            )
        )
        sys.exit(6)


@SetupLogger
def setup_django():
    import django
    django.setup()

    from django.db.migrations.recorder import MigrationRecorder
    from django.apps import apps
    from django.db import connection
    return connection, apps, MigrationRecorder


@SetupLogger
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
    migration_directory = os.path.join(apps.get_app_config(app_name).path, "migrations")
    migrations_on_disk = set(
        fnmatch.filter(os.listdir(migration_directory), "*.py")
    )
    migrations_on_disk = {os.path.splitext(i)[0] for i in migrations_on_disk}
    migrations_on_disk.remove("__init__")
    return len(migrations_on_disk - applied_migrations) > 0


@SetupLogger
def main(args):
    if selinux_enabled():
        print("SELinux is enabled, refuse to operate")
        sys.exit(-1)
    _check_dirs()
    DB_MAPPINGS = {
        "psql": "python-modules-psycopg2",
        "mysql": "python-modules-mysql",
        "sqlite": "python-init",
    }
    if not all(DB_PRESENT.values()):
        print("missing databases layers:")
        for _key in list(DB_PRESENT.keys()):
            if not DB_PRESENT[_key]:
                print(" {:6s} : {}".format(_key, DB_MAPPINGS[_key]))
    if not any(DB_PRESENT.values()):
        print("No database access libraries installed, please install some of them")
        sys.exit(1)

    # flag: setup db_cf data
    if args.disable_auto_update:
        cs_store = config_store.ConfigStore(GEN_CS_NAME)
        cs_store["db.auto.update"] = False
        cs_store.write()
        print("disabled auto_update_flag")
    elif args.enable_auto_update:
        cs_store = config_store.ConfigStore(GEN_CS_NAME)
        cs_store["db.auto.update"] = True
        cs_store.write()
        print("enabled auto_update_flag")
    db_exists = config_store.ConfigStore.exists(DB_ACCESS_CS_NAME)
    call_create_db = True
    call_migrate_db = False
    call_create_fixtures = False
    call_init_webfrontend = args.init_webfrontend
    # FIXME, too many flags ...
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
                _db_cf_f = config_store.ConfigStore(DB_ACCESS_CS_NAME, quiet=True, fix_prefix_on_read=False)
                if not len(list(_db_cf_f.keys())):
                    print("DB access file {} already exists but is empty, ignoring ...".format(DB_ACCESS_CS_NAME))
                    setup_db_cf = True
                elif args.ignore_existing:
                    print("DB access file {} already exists but will be overwritten ...".format(DB_ACCESS_CS_NAME))
                    setup_db_cf = True
                else:
                    print("DB access file {} already exists, will not setup new database ...".format(DB_ACCESS_CS_NAME))
                    call_create_db = False
                    setup_db_cf = False
    else:
        setup_db_cf = True
        if args.use_existing:
            print("DB access file {} does not exist ...".format(DB_ACCESS_CS_NAME))
    if setup_db_cf:
        if not create_db_cf(args):
            print("Creation of {} not successfull, exiting".format(DB_ACCESS_CS_NAME))
            sys.exit(3)
        else:
            # this flag is used as an indicator for new setups (no 0800 migration needed)
            _db_cf_created = True
    else:
        _db_cf_created = False
    check_db_rights()
    if call_create_db:
        create_db(args, _db_cf_created)
        call_init_webfrontend = True
    if call_migrate_db:
        migrate_db(args)
        call_init_webfrontend = True
    if call_create_fixtures:
        create_fixtures()
    if call_init_webfrontend:
        init_webfrontend(args)
