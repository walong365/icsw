#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012,2013 Andreas Lang-Nevyjel
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

from django.db import connection
from initat.cluster_server.config import global_config
from initat.core.management.commands import dumpdatafast, dumpdataslow
from optparse import OptionParser
import bz2
import datetime
import logging_tools
import os
import stat
import threading_tools
import time

class dummy_file(file):
    ending = None

class backup_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        connection.close()
        self.register_func("start_backup", self._start_backup)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def _start_backup(self, *args, **kwargs):
        self.log("starting backup")
        bu_dir = global_config["DATABASE_DUMP_DIR"]
        if not os.path.isdir(bu_dir):
            self.log("creating bu_dir %s" % (bu_dir))
            os.mkdir(bu_dir)
        # delete old files
        for entry in os.listdir(bu_dir):
            if entry.count(".") and entry.split(".")[-1] in ["zip", "bz2"]:
                f_name = os.path.join(bu_dir, entry)
                diff_dt = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.stat(f_name)[stat.ST_CTIME])
                if diff_dt.days > global_config["DATABASE_KEEP_DAYS"]:
                    self.log("removing backup %s" % (f_name))
                    os.unlink(f_name)
        self._fast_backup(bu_dir)
        self._normal_backup(bu_dir)
        self._exit_process()
    def _fast_backup(self, bu_dir):
        # start 'fast' django backup
        s_time = time.time()
        bu_name = datetime.datetime.now().strftime("db_bu_fast_%Y%m%d_%H:%M:%S")
        self.log("storing backup in %s" % (os.path.join(
            bu_dir,
            bu_name)))
        # set BASE_OBJECT
        dumpdatafast.BASE_OBJECT = self
        buf_com = dumpdatafast.Command()
        opts, args = OptionParser(option_list=buf_com.option_list).parse_args([
            "-d",
            bu_dir,
            "-b",
            "--one-file",
            bu_name])
        buf_com._handle(*args, **vars(opts))
        # clear base object
        dumpdatafast.BASE_OBJECT = None
        e_time = time.time()
        self.log("fast backup finished in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def _normal_backup(self, bu_dir):
        # start 'normal' django backup
        s_time = time.time()
        bu_name = datetime.datetime.now().strftime("db_bu_django_%Y%m%d_%H:%M:%S")
        full_path = os.path.join(
            bu_dir,
            bu_name)
        self.log("storing backup in %s" % (full_path))
        buf_com = dumpdataslow.Command()
        buf_com.stdout = dummy_file(full_path, "wb")
        opts, args = OptionParser(option_list=buf_com.option_list).parse_args([
            "-a",
            "--format",
            "xml",
            "--traceback",
            "auth",
            "contenttypes",
            "sessions",
            "sites",
            "messages",
            "admin",
            "backbone",
        ])
        buf_com.handle(*args, **vars(opts))
        buf_com.stdout.close()
        file("%s.bz2" % (full_path), "wb").write(bz2.compress(file(full_path, "r").read()))
        os.unlink(full_path)
        e_time = time.time()
        self.log("normal backup finished in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
    def loop_post(self):
        self.__log_template.close()

