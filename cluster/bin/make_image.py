#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2012 Andreas Lang, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-backbone
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
""" create image """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import configfile
import argparse
import process_tools
from django.db.models import Q
from initat.cluster.backbone.models import image
import config_tools
import threading_tools
import logging_tools
import time
import subprocess
from django.db import connection
from lxml import etree

global_config = configfile.get_global_config(process_tools.get_programm_name())

VERSION_STRING = "1.2"

class package_check(object):
    NEEDED_PACKAGES = [
        "python-init",
        "ethtool-init",
        "host-monitoring",
        "meta-server",
        "logging-server",
        "package-client",
        "loadmodules",
        "python-modules-base",
        "child"]
    def __init__(self, log_com, img_obj):
        self.__log_com = log_com
        self.__image = img_obj
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[pc] %s" % (what), log_level)
    def check(self):
        self.log("checking image at path %s" % (self.__image.source))
        res_str = self._call("zypper -x -R %s search -i | xmllint --recover - 2>/dev/null " % (self.__image.source))
        #print type(res_str), res_str
        res_xml = etree.fromstring(res_str)
        all_packs = set(res_xml.xpath(".//solvable[@status='installed' and @kind='package']/@name"))
        missing_packages = set(package_check.NEEDED_PACKAGES) - all_packs
        return missing_packages
    def _call(self, cmd_string):
        self.log("calling '%s'" % (cmd_string))
        return subprocess.check_output(cmd_string, shell=True)

class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__verbose = global_config["VERBOSE"]
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        connection.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
        if self.__verbose:
            print "[%4s.%-10s] %s" % (logging_tools.get_log_level_str(log_level), self.name, what)
    def loop_post(self):
        self.__log_template.close()

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__verbose = global_config["VERBOSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(
            self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"]
        )
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # log config
        self._log_config()
        self.device = config_tools.server_check(server_type="image_server").effective_device
        if not self.device and not global_config["FORCE_SERVER"]:
            self.log("not an image server", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("not an image server")
        else:
            self.log("image server is '%s'" % (unicode(self.device) if self.device else "---"))
            for cur_num in xrange(global_config["BUILDERS"]):
                self.add_process(build_process("builder_%d" % (cur_num)), start=True)
        connection.close()
        self.__build_lock = False
        self.init_build()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
        if self.__verbose:
            print "[%4s.%-10s] %s" % (logging_tools.get_log_level_str(lev), self.name, what)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested: %s" % (err_cause), logging_tools.LOG_LEVEL_ERROR)
            self["exit_requested"] = True
            print "exit because of %s" % (err_cause)
    def loop_post(self):
        if self.__build_lock:
            self.log("removing buildlock")
            cur_img = self._get_image()
            cur_img.build_lock = False
            cur_img.save()
        self.__log_template.close()
    def init_build(self):
        try:
            cur_img = self.check_build_lock()
            if not cur_img.builds:
                cur_img.builds = 0
            cur_img.builds += 1
            cur_img.save()
            self.log("setting build number to %d" % (cur_img.builds))
            self._check_dirs(cur_img)
            self._check_packages(cur_img)
            if global_config["BUILD_IMAGE"]:
                self.log("building image from %s" % (cur_img.source))
                self._generate_dir_list(cur_img)
        except:
            self._int_error("build failed: %s" % (process_tools.get_except_info()))
        else:
            self._int_error("done")
    def _check_packages(self, cur_img):
        cur_pc = package_check(self.log, cur_img)
        missing = cur_pc.check()
        if missing:
            self.log("missing packages: %s" % (", ".join(sorted(list(missing)))), logging_tools.LOG_LEVEL_ERROR)
            if not global_config["IGNORE_ERRORS"]:
                raise ValueError, "packages missing (%s)" % (", ".join(missing))
        else:
            self.log("all packages installed")
    def _generate_dir_list(self, cur_img):
        self.__dir_list = set([cur_entry for cur_entry in os.listdir(cur_img.source) if cur_entry not in ["media", "mnt", "proc", "sys"] and not os.path.islink(os.path.join(cur_img.source, cur_entry))])
        self.log("directory list is %s" % (", ".join(sorted(list(self.__dir_list)))))
    def _check_dirs(self, cur_img):
        self.__image_dir = os.path.join("/tftpboot", "images", cur_img.name)
        self.__system_dir = os.path.join(self.__image_dir, "system")
        for c_dir, create in [
            (cur_img.source, False),
            (os.path.join(cur_img.source, "bin"), False),
            (os.path.join(cur_img.source, "sbin"), False),
            (self.__image_dir, True),
            (self.__system_dir, True),
            ]:
            if not os.path.isdir(c_dir):
                if create:
                    try:
                        os.makedirs(c_dir)
                    except:
                        raise
                    else:
                        self.log("created %s" % (c_dir))
                else:
                    raise ValueError, "%s is not a directory" % (c_dir)
            else:
                self.log("%s checked (is_dir)" % (c_dir))
        if os.path.isdir(self.__system_dir):
            self._clean_directory(self.__system_dir)
    def _clean_directory(self, t_dir):
        self.log("cleaning directory %s" % (t_dir))
        for entry in os.listdir(t_dir):
            f_path = os.path.join(t_dir, entry)
            try:
                os.unlink(f_path)
            except:
                raise
            else:
                self.log("removed %s" % (f_path))
    def _get_image(self):
        return image.objects.get(Q(name=global_config["IMAGE_NAME"]))
    def check_build_lock(self):
        img = self._get_image()
        if img.build_lock:
            if global_config["OVERRIDE"]:
                self.log("image is locked, overriding (ignoring) lock")
                self.__build_lock = True
            else:
                raise ValueError, "image is locked"
        else:
            self.log("setting build lock")
            img.build_lock = True
            img.save()
            self.__build_lock = True
        return img

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    all_imgs = sorted(image.objects.all().values_list("name", flat=True))
    if not all_imgs:
        print "No images found"
        sys.exit(1)
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("COMPRESSION"         , configfile.str_c_var("bz2", help_string="compression method [%(default)s]", choices=["bz2", "gz", "xz"])),
        ("VERBOSE"             , configfile.bool_c_var(False, help_string="be verbose [%(default)s]", action="store_true", only_commandline=True, short_options="v")),
        ("IMAGE_NAME"          , configfile.str_c_var(all_imgs[0], help_string="image to build [%(default)s]", choices=all_imgs)),
        ("MODIFY_IMAGE"        , configfile.bool_c_var(True, short_options="m", help_string="do not modify image (no chroot calls) [%(default)s]", action="store_false")),
        ("IGNORE_ERRORS"       , configfile.bool_c_var(False, short_options="i", help_string="ignore image errors [%(default)s]", action="store_true")),
        ("FORCE_SERVER"        , configfile.bool_c_var(False, short_options="f", help_string="force being an image server [%(default)s]", action="store_true")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("BUILDERS"            , configfile.int_c_var(4, help_string="numbers of builders [%(default)i]", type=int)),
        ("OVERRIDE"            , configfile.bool_c_var(False, help_string="override build lock [%(default)s]", action="store_true")),
        ("BUILD_IMAGE"         , configfile.bool_c_var(False, help_string="build image [%(default)s]", action="store_true")),
            ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
