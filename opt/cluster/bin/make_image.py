#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2005,2012-2015 Andreas Lang-Nevyjel, init.at
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

import django
django.setup()

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import image
from lxml import etree  # @UnresolvedImports
from initat.tools import config_tools
from initat.tools import configfile
from initat.tools import logging_tools
import pprint
from initat.tools import process_tools
import shutil
import stat
import statvfs
import subprocess
import tempfile
from initat.tools import threading_tools
import time
import shutil

global_config = configfile.get_global_config(process_tools.get_programm_name())

VERSION_STRING = "1.3"
SLASH_NAME = "SLASH"

NEEDED_PACKAGES_1 = [
    "python-init",
    "ethtool-init",
    "host-monitoring",
    "meta-server",
    "logging-server",
    "package-client",
    "loadmodules",
    "python-modules-base",
    "child",
    "modules-init",
]

NEEDED_PACKAGES_2 = [
    "python-init",
    "ethtool-init",
    "icsw-client",
    "modules-init",
]

COMPRESS_MAP = {
    "gz": "z",
    "bz2": "j",
    "xz": "J"
}


class package_check(object):
    def __init__(self, log_com, img_obj):
        self.__log_com = log_com
        self.__image = img_obj

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[pc] {}".format(what), log_level)

    def check(self, pack_list):
        if os.path.isfile(os.path.join(self.__image.source, "etc", "SuSE-release")):
            return self.check_zypper(pack_list)
        elif os.path.isfile(os.path.join(self.__image.source, "etc", "redhat-release")):
            return self.check_yum(pack_list)
        else:
            self.log("image type not identifier", logging_tools.LOG_LEVEL_ERROR)
            return set(pack_list)

    def check_yum(self, pack_list):
        self.log("checking image at path {} with yum (rpm)".format(self.__image.source))
        res_set = set([line.strip() for line in self._call("chroot {} rpm -qa --queryformat=\"%{{NAME}}\\n\"".format(self.__image.source)).split("\n")])
        missing_packages = set(pack_list) - res_set
        return missing_packages

    def check_zypper(self, pack_list):
        self.log("checking image at path {} with zypper".format(self.__image.source))
        res_str = self._call("zypper -x -R {} --no-refresh search -i | xmllint --recover - 2>/dev/null ".format(self.__image.source))
        try:
            res_xml = etree.fromstring(res_str)
        except:
            self.log("error interpreting zypper output '{}'".format(res_str), logging_tools.LOG_LEVEL_ERROR)
            all_packs = set()
        else:
            all_packs = set(res_xml.xpath(".//solvable[@status='installed' and @kind='package']/@name", smart_strings=False))
        missing_packages = set(pack_list) - all_packs
        return missing_packages

    def _call(self, cmd_string):
        self.log("calling '{}'".format(cmd_string))
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
        self.register_func("compress", self._compress)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
        if self.__verbose:
            print "[{:4s}.{:<10s}] {}".format(logging_tools.get_log_level_str(log_level), self.name, what)

    def loop_post(self):
        self.__log_template.close()

    def _compress(self, *args, **kwargs):
        s_time = time.time()
        target_dir, system_dir, image_dir = args[0:3]
        if target_dir == SLASH_NAME:
            _dir_mode = False
            file_list = args[3]
            link_list = args[4]
            self.log(
                "compressing files '{}' and links '{}' (from dir {} to {})".format(
                    ", ".join(file_list),
                    ", ".join(link_list),
                    system_dir,
                    image_dir
                )
            )
            t_size = sum([os.stat(os.path.join(system_dir, entry))[stat.ST_SIZE] for entry in file_list])
        else:
            _dir_mode = True
            file_list, link_list = ([], [])
            self.log("compressing directory '{}' (from dir {} to {})".format(target_dir, system_dir, image_dir))
            t_size = int(self._call("du -sb {}".format(os.path.join(system_dir, target_dir))).split()[0])
        t_file = os.path.join(
            image_dir,
            "{}.tar.{}".format(
                target_dir,
                global_config["COMPRESSION"]
            )
        )
        self.log(
            "size is {} (target file is {})".format(
                logging_tools.get_size_str(t_size),
                t_file
            )
        )
        c_flag = COMPRESS_MAP[global_config["COMPRESSION"]]
        comp_opt = ""
        if global_config["COMPRESSION_OPTION"]:
            if global_config["COMPRESSION"] == "xz":
                comp_opt = "export XZ_OPT='{}'".format(global_config["COMPRESSION_OPTION"])
        self._call(
            "cd {} ; {} tar -c{}f {} --preserve-permissions {} {}".format(
                system_dir,
                "{};".format(comp_opt) if comp_opt else "",
                c_flag,
                t_file,
                " ".join(file_list) if not _dir_mode else target_dir,
                " ".join(link_list) if not _dir_mode else "",
            )
        )
        new_size = os.stat(t_file)[stat.ST_SIZE]
        self.log(
            "target size is {} (from 100 % to {:.2f} %)".format(
                logging_tools.get_size_str(new_size),
                100. * new_size / t_size if t_size else 0,
            )
        )
        e_time = time.time()
        self.log("compressing {} took {}".format(target_dir, logging_tools.get_diff_time_str(e_time - s_time)))
        self.send_pool_message("compress_done", target_dir)

    def _call(self, cmd, **kwargs):
        self.log("calling '{}' in image".format(cmd))
        cmd_string = "{} 2>&1".format(cmd)
        try:
            result = subprocess.check_output(cmd_string, shell=True)
        except subprocess.CalledProcessError, what:
            self.log("result ({:d}): {}".format(what.returncode, unicode(what)), logging_tools.LOG_LEVEL_ERROR)
            result = what.output
        for line_num, line in enumerate(result.strip().split("\n"), 1):
            if line.rstrip():
                self.log("  line {:2d}: {}".format(line_num, line.rstrip()))
        return result


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__start_time = time.time()
        self.__verbose = global_config["VERBOSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(
            self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"]
        )
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("compress_done", self._compress_done)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # log config
        self._log_config()
        self.device = config_tools.server_check(server_type="image_server").effective_device
        if not self.device and not global_config["FORCE_SERVER"]:
            self.log("not an image server", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("not an image server")
        elif not process_tools.find_file("xmllint"):
            self.log("xmllint not found", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("xmllint not found")
        else:
            self.log("image server is '{}'".format(unicode(self.device) if self.device else "---"))
            self.__builder_names = []
            for cur_num in xrange(global_config["BUILDERS"]):
                builder_name = "builder_{:d}".format(cur_num)
                self.__builder_names.append(builder_name)
                self.add_process(build_process(builder_name), start=True)
        connection.close()
        self.__build_lock = False
        if not self["exit_requested"]:
            self.init_build()

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
        if self.__verbose:
            print "[{:4s}.{:<10s}] {}".format(logging_tools.get_log_level_str(lev), self.name, what)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested: {}".format(err_cause), logging_tools.LOG_LEVEL_ERROR)
            self["exit_requested"] = True
            print("exit because of {}".format(err_cause))

    def loop_post(self):
        if self.__build_lock:
            self.log("removing buildlock")
            cur_img = self._get_image()
            cur_img.build_lock = False
            cur_img.release += 1
            if not cur_img.builds:
                cur_img.builds = 1
            else:
                cur_img.builds += 1
            cur_img.build_machine = process_tools.get_machine_name(short=False)
            cur_img.save()
        e_time = time.time()
        self.log("build took {}".format(logging_tools.get_diff_time_str(e_time - self.__start_time)))
        self.__log_template.close()

    def init_build(self):
        do_exit = True
        try:
            cur_img = self.check_build_lock()
            if not cur_img.builds:
                cur_img.builds = 0
            cur_img.builds += 1
            cur_img.save()
            self.log("setting build number to {:d}".format(cur_img.builds))
            self._check_dirs(cur_img)
            self._check_packages(cur_img)
            self._umount_dirs(cur_img)
            if global_config["CHECK_SIZE"]:
                self._check_size(cur_img)
            else:
                self.log("size checking disabled", logging_tools.LOG_LEVEL_WARN)
            if global_config["BUILD_IMAGE"]:
                # get image from database (in case something has changed)
                cur_img = self._get_image()
                self.log("building image from {}".format(cur_img.source))
                self._generate_dir_list(cur_img)
                self._copy_image(cur_img)
                self._clean_image(cur_img)
                self._init_compress_image()
                do_exit = False
        except:
            self._int_error("build failed: {}".format(process_tools.get_except_info()))
        else:
            if do_exit:
                self._int_error("done")

    def _compress_done(self, *args, **kwargs):
        b_name, _b_pid, dir_name = args
        self.__pending[b_name] = False
        self.log("compression of {} finished".format(dir_name))
        self._next_compress()
        if not self.__pending_dirs and not self.__pending_files and not self.__pending_links and not any(self.__pending.values()):
            self._create_tdir()
            self._clean_system_dir()
            self._call(None, "sync")
            self._int_error("done")

    def _clean_system_dir(self):
        """ cleaning system dir """
        self._clean_directory(self.__system_dir, remove_directory=True)

    def _create_tdir(self):
        self.log("creating tdir file")
        temp_dir = tempfile.mkdtemp()
        self.log("tempdir is '{}'".format(temp_dir))
        targ_file = os.path.join(self.__image_dir, ".tdir.tar.{}".format(global_config["COMPRESSION"]))
        for targ_dir in self.__dir_list:
            t_file = os.path.join(temp_dir, targ_dir)
            s_dir = os.path.join(self.__system_dir, targ_dir)
            file(t_file, "w").close()
            os.chmod(t_file, os.stat(s_dir)[stat.ST_MODE])
            os.chown(t_file, os.stat(s_dir)[stat.ST_UID], os.stat(s_dir)[stat.ST_GID])
        self._call(
            None,
            "cd {} ; tar -c{}f {} *".format(
                temp_dir,
                COMPRESS_MAP[global_config["COMPRESSION"]],
                targ_file,
            )
        )
        self.log("removing '{}'".format(temp_dir))
        shutil.rmtree(temp_dir)

    def _init_compress_image(self):
        """ compressing image """
        for cur_file in os.listdir(self.__image_dir):
            full_path = os.path.join(self.__image_dir, cur_file)
            if os.path.isfile(full_path):
                if cur_file.lower().count(".tar"):
                    self.log("removing {}".format(full_path))
                    os.unlink(full_path)
        self.__pending_dirs = [entry for entry in self.__dir_list]
        self.__pending_files = [entry for entry in self.__file_list]
        self.__pending_links = [entry for entry in self.__link_list]
        self.__pending = dict([(builder_name, False) for builder_name in self.__builder_names])
        for _idx in xrange(global_config["BUILDERS"]):
            self._next_compress()

    def _next_compress(self):
        if self.__pending_dirs or self.__pending_files or self.__pending_links:
            if self.__pending_dirs:
                next_dir = self.__pending_dirs.pop(0)
                s_files, s_links = ([], [])
            else:
                next_dir = SLASH_NAME
                s_files = [entry for entry in self.__pending_files]
                s_links = [entry for entry in self.__pending_links]
                self.__pending_files = []
                self.__pending_links = []
            free_builder = [key for key, value in self.__pending.iteritems() if not value][0]
            self.__pending[free_builder] = True
            self.send_to_process(
                free_builder,
                "compress",
                next_dir,
                self.__system_dir,
                self.__image_dir,
                s_files,
                s_links,
            )
        else:
            self.log(
                "no dirs or files pending, waiting for {}".format(
                    logging_tools.get_plural("compression job", len([True for value in self.__pending.itervalues() if value]))
                )
            )

    def _copy_image(self, cur_img):
        """ copy image """
        self.log("copying {}".format(logging_tools.get_plural("directory", len(self.__dir_list))))
        for dir_num, cur_dir in enumerate(self.__dir_list, 1):
            self.log(
                "[{:2d} of {:2d}] copying directory {}".format(
                    dir_num,
                    len(self.__dir_list),
                    cur_dir,
                )
            )
            s_time = time.time()
            self._call(
                cur_img,
                "cp -a {} {}".format(
                    os.path.join(cur_img.source, cur_dir),
                    os.path.join(self.__system_dir, cur_dir)
                )
            )
            e_time = time.time()
            self.log(
                "copied directory {} in {}".format(
                    cur_dir,
                    logging_tools.get_diff_time_str(e_time - s_time)
                )
            )
        for cur_file in self.__file_list:
            s_time = time.time()
            shutil.copy2(
                os.path.join(cur_img.source, cur_file),
                os.path.join(self.__system_dir, cur_file),
            )
            e_time = time.time()
            self.log(
                "copied file {} in {}".format(
                    cur_file,
                    logging_tools.get_diff_time_str(e_time - s_time)
                )
            )
        for cur_link in self.__link_list:
            s_time = time.time()
            self._call(
                cur_img,
                "cp -a {} {}".format(
                    os.path.join(cur_img.source, cur_link),
                    os.path.join(self.__system_dir, cur_link),
                )
            )
            e_time = time.time()
            self.log(
                "copied link {} in {}".format(
                    cur_link,
                    logging_tools.get_diff_time_str(e_time - s_time)
                )
            )

    def _clean_image(self, cur_img):
        """ clean system after copy """
        self.log("cleaning image")
        for clean_dir in [
            "/var/lib/meta-server",
            "/etc/zypp/repos.d",
        ]:
            t_dir = os.path.join(self.__system_dir, clean_dir[1:])
            self._clean_directory(t_dir)
        boot_dir = os.path.join(self.__system_dir, "boot")
        if os.path.isdir(boot_dir):
            for cur_entry in os.listdir(boot_dir):
                if any([cur_entry.lower().startswith(prefix) for prefix in ["system", "vmlinu", "init"]]):
                    full_path = os.path.join(self.__system_dir, "boot", cur_entry)
                    self.log("removing {}".format(full_path))
                    os.unlink(full_path)
        # call SuSEconfig, FIXME
        # check init-scripts, FIXME

    def _check_size(self, cur_img):
        """ check size of target directory """
        target_free_size = os.statvfs(self.__image_dir)[statvfs.F_BFREE] * os.statvfs(self.__image_dir)[statvfs.F_BSIZE]
        orig_size = int(self._call(cur_img, "du -sb {}".format(cur_img.source)).split()[0])
        self.log("size of image is {}, free space is {} (at {})".format(
            logging_tools.get_size_str(orig_size),
            logging_tools.get_size_str(target_free_size),
            self.__image_dir,
        ))
        cur_img.size = orig_size
        # size_string is automatically set in pre_save handler
        cur_img.save()
        if orig_size * 1.2 > target_free_size:
            raise ValueError(
                "not enough free space ({}, image has {})".format(
                    logging_tools.get_size_str(target_free_size),
                    logging_tools.get_size_str(orig_size)
                )
            )

    def _umount_dirs(self, cur_img):
        """ umount directories """
        for um_dir in ["proc", "sys"]:
            self._call(cur_img, "umount /{}".format(um_dir), chroot=True)

    def _check_packages(self, cur_img):
        """ check packages in image """
        cur_pc = package_check(self.log, cur_img)
        missing_1 = cur_pc.check(NEEDED_PACKAGES_1)
        missing_2 = cur_pc.check(NEEDED_PACKAGES_2)
        if missing_1 and missing_2:
            self.log("missing packages 1: {}".format(", ".join(sorted(list(missing_1)))), logging_tools.LOG_LEVEL_ERROR)
            self.log("missing packages 2: {}".format(", ".join(sorted(list(missing_2)))), logging_tools.LOG_LEVEL_ERROR)
            if not global_config["IGNORE_ERRORS"]:
                raise ValueError("packages missing ({})".format(", ".join(sorted(list(missing_1 | missing_2)))))
        else:
            self.log("all packages installed")

    def _generate_dir_list(self, cur_img):
        self.__dir_list = set(
            [
                cur_entry for cur_entry in os.listdir(cur_img.source) if cur_entry not in [
                    "media", "mnt", "proc", "sys"
                ] and os.path.isdir(os.path.join(cur_img.source, cur_entry)) and not os.path.islink(os.path.join(cur_img.source, cur_entry))
            ]
        )
        self.__file_list = set([cur_entry for cur_entry in os.listdir(cur_img.source) if os.path.isfile(os.path.join(cur_img.source, cur_entry))])
        self.__link_list = set([cur_entry for cur_entry in os.listdir(cur_img.source) if os.path.islink(os.path.join(cur_img.source, cur_entry))])
        self.log("directory list is {}".format(", ".join(sorted(list(self.__dir_list)))))
        self.log("file list is {}".format(", ".join(sorted(list(self.__file_list))) or "<EMPTY>"))
        self.log("link list is {}".format(", ".join(sorted(list(self.__link_list))) or "<EMPTY>"))

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
                        self.log("created {}".format(c_dir))
                else:
                    raise ValueError("{} is not a directory".format(c_dir))
            else:
                self.log("{} checked (is_dir)".format(c_dir))
        if os.path.isdir(self.__system_dir):
            self._clean_directory(self.__system_dir)

    def _clean_directory(self, t_dir, **kwargs):
        if os.path.isdir(t_dir):
            if t_dir.startswith(self.__system_dir):
                self.log("cleaning directory {}".format(t_dir))
                for entry in os.listdir(t_dir):
                    f_path = os.path.join(t_dir, entry)
                    if os.path.isfile(f_path):
                        os.unlink(f_path)
                    elif os.path.islink(f_path):
                        os.unlink(f_path)
                    else:
                        try:
                            shutil.rmtree(f_path)
                        except:
                            raise
                        else:
                            self.log("removed {}".format(f_path))
                if kwargs.get("remove_directory", False):
                    os.rmdir(t_dir)
                    self.log("removed {}".format(t_dir))
            else:
                self.log("directory '{}' does not start with {}".format(t_dir, self.__system_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("directory '{}' does not exist".format(t_dir), logging_tools.LOG_LEVEL_WARN)

    def _get_image(self):
        return image.objects.get(Q(name=global_config["IMAGE_NAME"]))

    def check_build_lock(self):
        img = self._get_image()
        if img.build_lock:
            if global_config["OVERRIDE"]:
                self.log("image is locked, overriding (ignoring) lock")
                self.__build_lock = True
            else:
                raise ValueError("image is locked")
        else:
            self.log("setting build lock")
            img.build_lock = True
            img.save()
            self.__build_lock = True
        return img

    def _call(self, cur_img, cmd, **kwargs):
        self.log("calling '{}'{}".format(cmd, " in image" if kwargs.get("chroot", False) else ""))
        cmd_string = "{} 2>&1".format(cmd)
        if kwargs.get("chroot", False):
            cmd_string = "chroot {} {}".format(cur_img.source, cmd_string)
        try:
            result = subprocess.check_output(cmd_string, shell=True)
        except subprocess.CalledProcessError, what:
            self.log("result ({:d}): {}".format(what.returncode, unicode(what)), logging_tools.LOG_LEVEL_ERROR)
            result = what.output
        for line_num, line in enumerate(result.strip().split("\n"), 1):
            if line.rstrip():
                self.log("  line {:2d}: {}".format(line_num, line.rstrip()))
        return result


def main():
    prog_name = global_config.name()
    all_imgs = sorted(image.objects.all().values_list("name", flat=True))
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
            ("COMPRESSION", configfile.str_c_var("xz", help_string="compression method [%(default)s]", choices=["bz2", "gz", "xz"])),
            ("COMPRESSION_OPTION", configfile.str_c_var("", help_string="options for compressor [%(default)s]")),
            ("VERBOSE", configfile.bool_c_var(False, help_string="be verbose [%(default)s]", action="store_true", only_commandline=True, short_options="v")),
            (
                "MODIFY_IMAGE",
                configfile.bool_c_var(True, short_options="m", help_string="do not modify image (no chroot calls) [%(default)s]", action="store_false")
            ),
            ("IGNORE_ERRORS", configfile.bool_c_var(False, short_options="i", help_string="ignore image errors [%(default)s]", action="store_true")),
            ("FORCE_SERVER", configfile.bool_c_var(False, short_options="f", help_string="force being an image server [%(default)s]", action="store_true")),
            ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
            ("LOG_NAME", configfile.str_c_var(prog_name)),
            ("BUILDERS", configfile.int_c_var(4, help_string="numbers of builders [%(default)i]")),
            ("OVERRIDE", configfile.bool_c_var(False, help_string="override build lock [%(default)s]", action="store_true")),
            ("BUILD_IMAGE", configfile.bool_c_var(False, help_string="build (compress) image [%(default)s]", action="store_true", only_commandline=True)),
            ("CHECK_SIZE", configfile.bool_c_var(True, help_string="image size check [%(default)s]", action="store_false")),
        ]
    )
    if all_imgs:
        global_config.add_config_entries(
            [
                ("IMAGE_NAME", configfile.str_c_var(all_imgs[0], help_string="image to build [%(default)s]", choices=all_imgs)),
            ]
        )
    global_config.parse_file()
    process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    _options = global_config.handle_commandline(
        description="{}, version is {}".format(
            prog_name,
            VERSION_STRING
        ),
        add_writeback_option=True,
        positional_arguments=False
    )
    global_config.write_file()
    if not all_imgs:
        print("No images found")
        sys.exit(1)
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
