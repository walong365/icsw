# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" kernel sync tools """

import commands
import datetime
import gzip
import hashlib
import os
import stat
import tempfile
import time

from django.db.models import Q
from initat.cluster.backbone.models import kernel, kernel_build, device, cluster_timezone
from initat.tools import logging_tools
from initat.tools import process_tools

KNOWN_INITRD_FLAVOURS = ["lo", "cpio", "cramfs"]

KNOWN_KERNEL_SYNC_COMMANDS = [
    "check_kernel_dir",
    "sync_kernels",
    "kernel_sync_data"
]


class KernelHelper(object):
    # filenames to sync
    pos_names = [
        "bzImage",
        "modules.tar.bz2",
        "initrd_cpio.gz",
        "initrd_cramfs.gz",
        "initrd_lo.gz",
        "modules.tar.bz2",
        "xen.gz",
        ".comment",
        ".config",
    ]

    def __init__(self, name, root_dir, log_func, config, **kwargs):
        # meassure the lifetime
        self.__start_time = time.time()
        self.__db_idx = 0
        self.__local_master_server = kwargs.get("master_server", None)
        self.name = name
        try:
            self.__db_kernel = kernel.objects.get(Q(name=name))
        except kernel.DoesNotExist:
            self.__db_kernel = None
        self.name = name
        self.root_dir = root_dir
        self.__config = config
        self.path = os.path.normpath(os.path.join(self.root_dir, self.name))
        self.__config_dict = {}
        self.__log_func = log_func
        self.__bz_path = os.path.join(self.path, "bzImage")
        self.__xen_path = os.path.join(self.path, "xen.gz")
        for c_path in ["config", ".config"]:
            self.__config_path = os.path.join(self.path, c_path)
            if os.path.isfile(self.__config_path):
                try:
                    conf_lines = [
                        _part for _part in [
                            _line.strip() for _line in file(self.__config_path, "r").read().split("\n") if _line.strip()
                        ] if not _part.strip().startswith("#")
                    ]
                except:
                    self.log(
                        "error reading config from {}: {}".format(
                            self.__config_path,
                            process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    self.__config_dict = {
                        _line.split("=", 1)[0]: _line.split("=", 1)[1] for _line in conf_lines
                    }
                    break
            else:
                self.__config_path = None
        self.__initrd_paths = {
            key: "{}/initrd_{}.gz".format(self.path, key) for key in KNOWN_INITRD_FLAVOURS
        }
        self.__initrd_paths["old"] = os.path.join(self.path, "initrd.gz")
        self.__initrd_paths["stage2"] = os.path.join(self.path, "initrd_stage2.gz")
        self.__option_dict = {
            "database": False
        }
        self.__initrd_built = None
        if not os.path.isdir(self.path):
            raise IOError("kernel_dir {} is not a directory".format(self.path))
        if not os.path.isfile(self.__bz_path):
            raise IOError("kernel_dir {} has no bzImage".format(self.path))
        # init db-Fields
        self.__checks = []
        self.__values = {
            "name": self.name,
            "path": self.path,
            "initrd_built": None,
            "module_list": "",
        }

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        # print self.name, what
        self.__log_func("[krnl {}] {}".format(self.name, what), log_level)

    def __getitem__(self, key):
        return self.__option_dict[key]

    def check_md5_sums(self):
        self.__checks.append("md5")
        files_to_check = sorted(
            [
                os.path.normpath(os.path.join(self.path, f_name)) for f_name in ["bzImage", "initrd.gz", "xen.gz", "modules.tar.bz2"] +
                [
                    "initrd_{}.gz".format(key) for key in KNOWN_INITRD_FLAVOURS
                ]
            ]
        )
        md5s_to_check = {
            p_name: os.path.normpath(os.path.join(self.path, ".{}_md5".format(os.path.basename(p_name)))) for p_name in files_to_check if os.path.exists(p_name)
        }
        md5s_to_remove = sorted(
            [
                md5_file for md5_file in [
                    os.path.normpath(os.path.join(self.path, ".{}_md5".format(os.path.basename(p_name)))) for p_name in files_to_check if not os.path.exists(p_name)
                ] if os.path.exists(md5_file)
            ]
        )
        if md5s_to_remove:
            self.log(
                "removing {}: {}".format(
                    logging_tools.get_plural("MD5 file", len(md5s_to_remove)),
                    ", ".join(md5s_to_remove)
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for md5_to_remove in md5s_to_remove:
                md5_name = os.path.basename(md5_to_remove)[1:]
                if md5_name in self.__option_dict:
                    del self.__option_dict[md5_name]
                try:
                    os.unlink(md5_to_remove)
                except:
                    self.log(
                        "error removing {}: {}".format(
                            md5_to_remove,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        if md5s_to_check:
            for src_file, md5_file in md5s_to_check.iteritems():
                md5_name = os.path.basename(md5_file)[1:]
                new_bz5 = True
                if os.path.exists(md5_file):
                    if os.stat(src_file)[stat.ST_MTIME] < os.stat(md5_file)[stat.ST_MTIME]:
                        new_bz5 = False
                if new_bz5:
                    self.log(
                        "doing MD5-sum for {} (stored in {})".format(
                            os.path.basename(src_file),
                            os.path.basename(md5_file)
                        ),
                    )
                    self.__option_dict[md5_name] = (hashlib.md5(file(src_file, "r").read())).hexdigest()
                    file(md5_file, "w").write(self.__option_dict[md5_name])
                else:
                    self.__option_dict[md5_name] = file(md5_file, "r").read()

    def move_old_initrd(self):
        if os.path.isfile(self.__initrd_paths["old"]):
            c_stat, c_out = commands.getstatusoutput("file -z {}".format(self.__initrd_paths["old"]))
            if c_stat:
                self.log(
                    "error getting type of old-flavour initrd.gz {} ({:d}): {}".format(
                        self.__initrd_paths["old"],
                        c_stat,
                        c_out
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                old_flavour = c_out.split(":", 1)[1].strip().lower()
                if old_flavour.count("compressed rom"):
                    old_flavour_str = "cramfs"
                elif old_flavour.count("cpio"):
                    old_flavour_str = "cpio"
                elif old_flavour.count("ext2"):
                    old_flavour_str = "lo"
                else:
                    old_flavour_str = ""
                if not old_flavour_str:
                    self.log(
                        "Unable to recognize flavour for {}".format(self.__initrd_paths["old"]),
                        logging_tools.LOG_LEVEL_WARN,
                    )
                else:
                    self.log(
                        "Recognized flavour {} for {}".format(
                            old_flavour_str,
                            self.__initrd_paths["old"]
                        ),
                    )
                    if os.path.isfile(self.__initrd_paths[old_flavour_str]):
                        self.log(
                            "removing present initrd for flavour ({}) {}".format(
                                old_flavour_str,
                                self.__initrd_paths[old_flavour_str]
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                        os.unlink(self.__initrd_paths[old_flavour_str])
                    self.log(
                        "moving {} to {}".format(
                            self.__initrd_paths["old"],
                            self.__initrd_paths[old_flavour_str]
                        )
                    )
                    try:
                        os.rename(
                            self.__initrd_paths["old"],
                            self.__initrd_paths[old_flavour_str]
                        )
                    except:
                        self.log(
                            "some error occured in rename(): {}".format(
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.check_md5_sums()

    def _update_kernel(self, **kwargs):
        if self.__db_kernel:
            if self.__db_kernel.master_server == self.__local_master_server.pk:
                for key, value in kwargs.iteritems():
                    if not hasattr(self.__db_kernel, key):
                        self.log(
                            "unknown attribute name {}".format(key),
                            logging_tools.LOG_LEVEL_CRITICAL
                        )
                    else:
                        setattr(self.__db_kernel, key, value)
                        self.__db_kernel.save()
            else:
                self.log(
                    "not master of kernel (keys: {})".format(
                        ", ".join(sorted(kwargs.keys()))
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )

    def check_initrd(self):
        # update initrd_built and module_list from initrd.gz
        # check for presence of stage-files
        present_dict = {}
        for initrd_flavour in KNOWN_INITRD_FLAVOURS + ["stage2"]:
            if initrd_flavour == "stage2":
                db_name = "stage2_present"
            else:
                db_name = "stage1_{}_present".format(initrd_flavour)
            present_flag = True if os.path.isfile(self.__initrd_paths[initrd_flavour]) else False
            present_dict[initrd_flavour] = True if present_flag else False
            self.__values[db_name] = present_flag
            self._update_kernel(**{db_name: present_flag})
        if self.__values["initrd_built"] is None:
            present_keys = sorted([key for key in ["cpio", "cramfs", "lo"] if present_dict.get(key, False)])
            if present_keys:
                self.log(
                    "{} for checking initrd: {}".format(
                        logging_tools.get_plural("key", len(present_keys)),
                        ", ".join(
                            [
                                "{} (file {})".format(
                                    key,
                                    os.path.basename(self.__initrd_paths[key])
                                ) for key in present_keys
                            ]
                        )
                    ),
                )
                self.__checks.append("initrd")
                initrd_built = cluster_timezone.localize(datetime.datetime.fromtimestamp(os.stat(self.__initrd_paths[present_keys[0]])[stat.ST_MTIME]))
                # initrd_built = time.localtime(initrd_built)
                self._update_kernel(initrd_built=initrd_built)
                # temporary file and directory
                tmp_dir = tempfile.mkdtemp()
                tfile_name = os.path.join(tmp_dir, ".initrd_check")
                tdir_name = os.path.join(tmp_dir, ".initrd_mdir")
                if not os.path.isdir(tdir_name):
                    os.mkdir(tdir_name)
                checked = False
                for present_key in present_keys:
                    check_path = self.__initrd_paths[present_key]
                    self.log("trying to get modules via {}-flavour ({})".format(present_key, self.__initrd_paths[key]))
                    # flavour-dependend mod_list extraction
                    setup_ok, do_umount = (True, False)
                    if present_key in ["lo", "cramfs"]:
                        try:
                            file(tfile_name, "w").write(gzip.open(check_path, "r").read())
                        except:
                            self.log(
                                "error reading {}: {}".format(
                                    check_path,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            setup_ok = False
                        else:
                            m_com = "mount -o loop {} {}".format(tfile_name, tdir_name)
                            um_com = "umount {}".format(tdir_name)
                            cstat, out = commands.getstatusoutput(m_com)
                            if cstat:
                                self.log(
                                    "error mounting tempfile {} to {}: {}".format(
                                        tfile_name,
                                        tdir_name,
                                        out
                                    )
                                )
                                setup_ok = False
                            else:
                                do_umount = True
                    else:
                        # no setup needed for cpio
                        setup_ok = True
                    # check list
                    if setup_ok:
                        mod_list = set()
                        if present_key in ["lo", "cramfs"]:
                            for dir_name, dir_list, file_list in os.walk(os.path.join(tdir_name, "lib", "modules")):
                                for mod_name in [file_name for file_name in file_list if file_name.endswith(".o") or file_name.endswith(".ko")]:
                                    mod_list.add(mod_name[:-2] if mod_name.endswith(".o") else mod_name[:-3])
                            checked = True
                        else:
                            c_stat, c_out = commands.getstatusoutput("gunzip -c {} | cpio -t".format(check_path))
                            if c_stat:
                                self.log(
                                    "error getting info crom cpio-archive {} ({:d}, {}): {}".format(
                                        check_path,
                                        c_stat,
                                        c_out,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                checked = True
                                mod_lines = [
                                    os.path.basename(
                                        "/{}".format(line)
                                    ) for line in c_out.split("\n") if line.startswith("lib/modules") and (line.endswith(".o") or line.endswith(".ko"))
                                ]
                                mod_list = set(
                                    [
                                        mod_name[:-2] if mod_name.endswith(".o") else mod_name[:-3] for mod_name in mod_lines
                                    ]
                                )
                        mod_list = ",".join(sorted(mod_list))
                        # print "***", present_key, mod_list
                        if mod_list:
                            self.log(
                                "found {}: {}".format(
                                    logging_tools.get_plural("module", len(mod_list.split(","))),
                                    mod_list
                                )
                            )
                        else:
                            self.log("found no modules")
                        if self.__db_idx:
                            if mod_list != self.__values["module_list"]:
                                self._update_kernel(module_list=mod_list)
                        else:
                            self.__values["module_list"] = mod_list
                            self.__values["target_module_list"] = mod_list
                    if do_umount:
                        c_stat, c_out = commands.getstatusoutput(um_com)
                        if c_stat:
                            self.log(
                                "error unmounting tempfile {} from {} ({:d}): {}".format(
                                    tfile_name,
                                    tdir_name,
                                    c_stat,
                                    c_out
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                    if checked:
                        # pass
                        break
                if os.path.isdir(tdir_name):
                    os.rmdir(tdir_name)
                if os.path.isfile(tfile_name):
                    os.unlink(tfile_name)
                os.rmdir(tmp_dir)
            else:
                self.log("not initrd-file found",
                         logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("initrd_built already set")

    def check_unset_master(self):
        self.__checks.append("unset_master")
        if self.__db_kernel:
            if self.__db_kernel.master_server in [0, None]:
                self.__db_kernel.master_server = self.__local_master_server.pk
                self.log("set master_server to local_master (was: 0)")
                self.__db_kernel.save()

    def check_comment(self):
        self.__checks.append("comment")
        comment_file = os.path.join(self.root_dir, ".comment")
        if os.path.isfile(comment_file):
            try:
                comment = " ".join(
                    [
                        _part.strip() for _part in file(comment_file, "r").read().split("\n")
                    ]
                )
            except:
                self.log(
                    "error reading comment-file '{}'".format(comment_file),
                    logging_tools.LOG_LEVEL_WARN,
                )
                comment = ""
            else:
                pass
        else:
            comment = ""
        self._update_kernel(comment=comment)

    def check_version_file(self):
        self.__checks.append("versionfile")
        kernel_version, k_ver, k_rel = (self.name.split("_")[0], 1, 1)
        if kernel_version == self.name:
            config_name = ""
        else:
            config_name = self.name[len(kernel_version) + 1:]
        build_mach = ""
        version_file = os.path.join(self.root_dir, ".version")
        if os.path.isfile(version_file):
            try:
                version_dict = {
                    _part.split("=", 1)[0]: _part.split("=", 1)[1] for _part in [
                        _line.strip() for _line in file(version_file, "r").read().split("\n") if _line.count("=")
                    ]
                }
            except:
                self.log(
                    "error parsing version-file '{}': {}".format(
                        version_file,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                version_dict = {
                    _key: _value for _key, _value in version_dict.iteritems()
                }
                if version_dict.get("kernelversion", kernel_version) != kernel_version:
                    self.log(
                        "warning: parsed kernel_version '{}' != version_file version '{}', using info from version_file".format(
                            kernel_version,
                            version_dict["kernelversion"]
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                    kernel_version = version_dict["kernelversion"]
                if version_dict.get("configname", config_name) != config_name:
                    self.log(
                        "warning: parsed config_name '{}' != version_file config_name '{}', using info from version_file".format(
                            config_name,
                            version_dict["configname"]
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
                    config_name = version_dict["configname"]
                if "version" in version_dict:
                    k_ver, k_rel = [int(x) for x in version_dict["version"].split(".", 1)]
                if "buildmachine" in version_dict:
                    build_mach = version_dict["buildmachine"].split(".")[0]
                    self.__option_dict["kernel_is_local"] = build_mach == self.__config["SERVER_SHORT_NAME"]
        if config_name:
            config_name = "/usr/src/configs/.config_{}".format(config_name)
        self.__values["kernel_version"] = kernel_version
        self.__values["version"] = k_ver
        self.__values["release"] = k_rel
        self.__values["config_name"] = config_name
        return build_mach

    def check_bzimage_file(self):
        self.__checks.append("bzImage")
        major, minor, patchlevel = ("", "", "")
        build_mach = ""
        cstat, out = commands.getstatusoutput("file {}".format(self.__bz_path))
        if cstat:
            self.log(
                "error, cannot file '{}' ({:d}): {}".format(
                    self.__bz_path,
                    cstat,
                    out
                ),
                logging_tools.LOG_LEVEL_ERROR,
            )
        else:
            try:
                for line in [part.strip().lower() for part in out.split(",")]:
                    if line.startswith("version"):
                        vers_str = line.split()[1]
                        if vers_str.count("-"):
                            vers_str, rel_str = vers_str.split("-", 1)
                        else:
                            rel_str = ""
                        vers_parts = vers_str.split(".")
                        major, minor = (vers_parts.pop(0), vers_parts.pop(0))
                        patchlevel = ".".join(vers_parts)
                    if line.count("@"):
                        build_mach = line.split("@", 1)[1].split(")")[0]
            except:
                # FIXME
                pass
        self.__values["major"] = major
        self.__values["minor"] = minor
        self.__values["patchlevel"] = patchlevel
        return build_mach

    def check_kernel_dir(self):
        # if not in database read values from disk
        self.log("Checking directory {} ...".format(self.path))
        self.check_unset_master()
        self.check_comment()
        self.check_xen()
        self.check_config()
        kernel_build_machine_fvf = self.check_version_file()
        kernel_build_machine_vfc = self.check_bzimage_file()
        # determine build_machine
        if kernel_build_machine_fvf:
            build_mach = kernel_build_machine_fvf
        elif kernel_build_machine_vfc:
            build_mach = kernel_build_machine_vfc
        elif self.__config.get("SET_DEFAULT_BUILD_MACHINE", False):
            build_mach = self.__config["SERVER_SHORT_NAME"]
        else:
            build_mach = ""
        if build_mach:
            try:
                build_dev = device.objects.get(Q(name=build_mach))
            except device.DoesNotExist:
                build_dev = None
        else:
            build_dev = None
        self.__values["build_machine"] = build_mach
        self.__values["device"] = build_dev

    def check_xen(self):
        xen_host_kernel = True if os.path.isfile(self.__xen_path) else False
        xen_guest_kernel = False
        if self.__config_dict.get("CONFIG_XEN", False):
            xen_guest_kernel = True
        self._update_kernel(
            xen_host_kernel=xen_host_kernel,
            xen_guest_kernel=xen_guest_kernel
        )

    def check_config(self):
        bc = 0
        if self.__config_dict:
            if self.__config_dict.get("CONFIG_X86_64", "n") == "y" or self.__config_dict.get("CONFIG_64BIT", "n") == "y":
                bc = 64
            else:
                bc = 32
        self._update_kernel(bitcount=bc)

    def set_option_dict_values(self):
        # local kernel ?
        # self.__option_dict["kernel_is_local"] = (self.__db_kernel["build_machine"] or "").split(".")[0] == self.__config["SERVER_SHORT_NAME"]
        # FIXME
        self.__option_dict["kernel_is_local"] = False
        # self.__option_dict["build_machine"] = self.__db_kernel["build_machine"]
        # initrds found, not used right now
        for initrd_flavour in ["lo", "cramfs", "cpio"]:
            self.__option_dict["initrd_flavour_{}".format(initrd_flavour)] = os.path.exists(self.__initrd_paths[initrd_flavour])

    def insert_into_database(self):
        self.__checks.append("SQL insert")
        if not self.__db_kernel:
            new_k = kernel()
            for key, value in self.__values.iteritems():
                setattr(new_k, key, value)
            new_k.enabled = True
            new_k.save()
            self.__db_kernel = new_k
            self.log(
                "inserted new kernel at DB-idx {:d}".format(self.__db_kernel.pk),
            )
            new_kb = kernel_build(
                kernel=new_k,
                version=self.__values["version"],
                release=self.__values["release"],
                build_machine=self.__values["build_machine"],
                device=self.__values["device"]
            )
            new_kb.save()
            self.log("inserted kernel_build at idx {:d}".format(new_kb.pk))
        self.__option_dict["database"] = True

    def check_for_db_insert(self, ext_opt_dict):
        ins = False
        if not self.__option_dict["database"]:
            # check for insert_all or insert_list
            if self.__config.get("IGNORE_KERNEL_BUILD_MACHINE", False) or ext_opt_dict["ignore_kernel_build_machine"]:
                self.log(
                    "ignore kernel build_machine (global: {}, local: {})".format(
                        str(self.__config.get("IGNORE_KERNEL_BUILD_MACHINE", False)),
                        str(ext_opt_dict["ignore_kernel_build_machine"])
                    )
                )
            ins = True
        return ins

    def log_statistics(self):
        t_diff = time.time() - self.__start_time
        self.log(
            "needed {}, {}".format(
                logging_tools.get_diff_time_str(t_diff),
                "{}: {}".format(
                    logging_tools.get_plural("check", len(self.__checks)),
                    ", ".join(self.__checks)
                ) if self.__checks else "no checks"
            )
        )

    def get_option_dict(self):
        return self.__option_dict
