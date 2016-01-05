# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel
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
""" cluster-server, backup process """

import bz2
import datetime
import os
import stat
import subprocess
import time
from optparse import OptionParser

from django.conf import settings

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.management.commands import dumpdataslow
from initat.cluster_server.config import global_config
from initat.tools import logging_tools, process_tools, threading_tools


class dummy_file(file):
    ending = None


class backup_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        db_tools.close_connection()
        self.register_func("start_backup", self._start_backup)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def get_ignore_list(self, table_name=False):
        from django.apps import apps
        # from django.db.models import get_apps, get_models
        ignore_list = []
        for _config in apps.get_app_configs():
            for _model in _config.get_models():
                if hasattr(_model, "CSW_Meta"):
                    if not getattr(_model.CSW_Meta, "backup", True):
                        if table_name:
                            ignore_list.append(_model._meta.db_table)
                        else:
                            ignore_list.append("{}.{}".format(_model._meta.app_label, _model._meta.model_name))
        return ignore_list

    def _start_backup(self, *args, **kwargs):
        self.log("starting backup")
        bu_dir = global_config["DATABASE_DUMP_DIR"]
        if not os.path.isdir(bu_dir):
            self.log("creating bu_dir {}".format(bu_dir))
            os.mkdir(bu_dir)
        # delete old files
        for entry in os.listdir(bu_dir):
            if entry.count(".") and entry.split(".")[-1] in ["zip", "bz2", "psql"]:
                f_name = os.path.join(bu_dir, entry)
                # _stat = os.stat(f_name)
                diff_dt = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.stat(f_name)[stat.ST_CTIME])
                if diff_dt.days > global_config["DATABASE_KEEP_DAYS"]:
                    self.log("removing backup %s" % (f_name))
                    os.unlink(f_name)
        for bu_type, bu_call in [
            ("database", self._database_backup),
            ("normal", self._normal_backup),
        ]:
            self.log("--------- backup type {} -------------".format(bu_type))
            s_time = time.time()
            bu_call(bu_dir)
            e_time = time.time()
            self.log("{} backup finished in {}".format(bu_type, logging_tools.get_diff_time_str(e_time - s_time)))
        self._exit_process()

    def _normal_backup(self, bu_dir):
        # start 'normal' django backup
        bu_name = datetime.datetime.now().strftime("db_bu_django_%Y%m%d_%H:%M:%S")
        full_path = os.path.join(
            bu_dir,
            bu_name)
        self.log("storing backup in {}".format(full_path))
        buf_com = dumpdataslow.Command()
        buf_com.stdout = dummy_file(full_path, "wb")
        opts, args = OptionParser(option_list=buf_com.option_list).parse_args(
            [
                "-a",
                "--format",
                "xml",
                "--traceback",
            ] + sum(
                [
                    ["-e", _ignore] for _ignore in self.get_ignore_list()
                ],
                []
            ) + [
                "auth",
                "contenttypes",
                "sessions",
                "sites",
                "admin",
                "backbone",
            ]
        )
        buf_com.handle(*args, **vars(opts))
        buf_com.stdout.close()
        file("{}.bz2".format(full_path), "wb").write(bz2.compress(file(full_path, "r").read()))
        os.unlink(full_path)

    def _database_backup(self, bu_dir):
        bu_name = datetime.datetime.now().strftime("db_bu_database_%Y%m%d_%H:%M:%S.psql")
        full_path = os.path.join(
            bu_dir,
            bu_name
        )
        _def_db = settings.DATABASES.get("default", None)
        if not _def_db:
            self.log("no default database found", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("found default database, keys:")
            for _key in sorted(_def_db.keys()):
                self.log("    {}={}".format(_key, _def_db[_key]))
            _engine = _def_db.get("ENGINE", "unknown").split(".")[-1]
            bu_dict = {
                "postgresql_psycopg2": {
                    "dump_bin": "pg_dump",
                    "cmdline": "{DUMP} -c -f {FILENAME} -F c -Z 4 -h {HOST} -U {USER} {NAME} -w {EXCLUDE}",
                    "pgpass": True
                }
            }
            if _engine in bu_dict:
                _bu_info = bu_dict[_engine]
                _bin = process_tools.find_file(_bu_info["dump_bin"])
                if not _bin:
                    self.log("cannot find dump binary {}".format(_bu_info["dump_bin"]), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("found dump binary {} in {}".format(_bu_info["dump_bin"], _bin))
                    cmdline = _bu_info["cmdline"].format(
                        DUMP=_bin,
                        FILENAME=full_path,
                        EXCLUDE=" ".join(["-T {}".format(_ignore) for _ignore in self.get_ignore_list(True)]),
                        **_def_db
                    )
                    _pgpass = _bu_info.get("pgpass", False)
                    if _pgpass:
                        _pgpassfile = "/root/.pgpass"
                        if os.path.exists(_pgpassfile):
                            _passcontent = file(_pgpassfile, "r").read()
                        else:
                            _passcontent = None
                        file(_pgpassfile, "w").write("{HOST}:*:{NAME}:{USER}:{PASSWORD}\n".format(**_def_db))
                        os.chmod(_pgpassfile, 0600)
                    try:
                        _output = subprocess.check_output(cmdline.split(), stderr=subprocess.PIPE)
                    except subprocess.CalledProcessError:
                        self.log(
                            "error calling {}: {}".format(
                                cmdline,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log("successfully called {}: {}".format(cmdline, _output))
                    if _pgpass:
                        if _passcontent:
                            file(_pgpassfile, "w").write(_passcontent)
                            os.chmod(_pgpassfile, 0600)
                        else:
                            os.unlink(_pgpassfile)
            else:
                self.log("unsupported engine '{}' for database backup".format(_engine), logging_tools.LOG_LEVEL_WARN)

    def loop_post(self):
        self.__log_template.close()
