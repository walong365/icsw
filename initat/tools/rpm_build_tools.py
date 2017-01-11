#
# Copyright (c) 2007-2008,2012,2014-2017 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
""" classes for building rpm-packages """



import argparse
import subprocess
import os
import pwd
import stat
import sys

from initat.tools import logging_tools, process_tools

SCRIPT_TYPES = ["post", "pre", "postun", "preun"]

default_ns = argparse.Namespace(
    packager="{}@{}".format(pwd.getpwuid(os.getuid())[0], process_tools.get_machine_name()),
    user="root",
    group="root",
    provides="",
    arch={"i686": "i586"}.get(os.uname()[4], os.uname()[4])
)


class package_parser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        self.add_argument(
            "-s",
            "--summary",
            dest="summary",
            help="Summary string [%(default)s]",
            default="files and packages for directory"
        )
        self.add_argument(
            "-d",
            "--description",
            dest="description",
            help="Description string [%(default)s]",
            default="autogenerated package"
        )
        self.add_argument(
            "-p",
            "--packager",
            dest="packager",
            help="set packager [%(default)s]",
            default=default_ns.packager
        )
        self.add_argument(
            "-P",
            "--package-group",
            dest="package_group",
            help="set package-group [%(default)s]",
            default="System/Monitoring"
        )
        self.add_argument(
            "-u",
            "--user",
            dest="user",
            default=default_ns.user,
            help="user to use for package [%(default)s]"
        )
        self.add_argument(
            "-g",
            "--group",
            dest="group",
            default=default_ns.group,
            help="group to use for package [%(default)s]"
        )
        self.add_argument(
            "-n",
            dest="name",
            default="",
            help="name of package [%(default)s]",
            required=True
        )
        self.add_argument(
            "-v",
            dest="version",
            default="1",
            help="package version [%(default)s]"
        )
        self.add_argument(
            "-r",
            dest="release",
            default="0",
            help="package release [%(default)s]"
        )
        self.add_argument(
            "-a",
            "--arch",
            dest="arch",
            help="set package architecture [%(default)s]",
            default=default_ns.arch
        )
        self.add_argument(
            "--post-script",
            default="",
            help="filename of post-script content"
        )
        self.add_argument(
            "--pre-script",
            default="",
            help="filename of pre-script content"
        )
        self.add_argument(
            "--postun-script",
            default="",
            help="filename of postun-script content"
        )
        self.add_argument(
            "--preun-script",
            default="",
            help="filename of preun-script content"
        )
        self.add_argument(
            "--provides",
            default="",
            type=str,
            help="string of for the %%provide attribute"
        )
        self.add_argument(
            "args",
            nargs="+",
            help="file specifier (SRC[:DST])"
        )

    def parse_args(self):
        opts = argparse.ArgumentParser.parse_args(self)
        # read pre / post scripts
        for _scr_name in SCRIPT_TYPES:
            _scr_name = "{}_script".format(_scr_name)
            if getattr(opts, _scr_name):
                try:
                    setattr(opts, _scr_name, open(getattr(opts, _scr_name), "r").read())
                except:
                    print(
                        "error handling {} : {}".format(
                            _scr_name,
                            process_tools.get_except_info()
                        )
                    )
                    sys.exit(1)
        return opts


class build_package(object):
    def __init__(self, pack_ns, **kwargs):
        self.__value_dict = {}
        self.__pack_ns = pack_ns
        # default: build went wrong
        self.build_ok = False
        self._check_system_settings()
        self["doc_dirs"] = ["man", "doc", "example", "examples"]
        self["inst_options"] = " -p -o root -g root "
        self["inst_binary"] = "install"
        for key, value in kwargs.items():
            self[key] = value
        self._set_package_file_names()

    def __setitem__(self, key, value):
        self.__value_dict[key] = value

    def __getitem__(self, key):
        if key in self.__value_dict:
            return self.__value_dict[key]
        elif hasattr(self.__pack_ns, key):
            return getattr(self.__pack_ns, key)
        else:
            return getattr(default_ns, key)

    def get(self, key, default):
        if key in self:
            return self[key]
        else:
            return default

    def __contains__(self, key):
        if key in self.__value_dict:
            return True
        elif hasattr(self.__pack_ns, key):
            return True
        else:
            return hasattr(default_ns, key)

    def _check_system_settings(self):
        sys_dict = process_tools.fetch_sysinfo()[1]
        sys_version = sys_dict["version"]
        if sys_dict["vendor"] in ["redhat", "centos"]:
            self.rpm_base_dir = "/usr/src/redhat"
        elif sys_dict["vendor"] in ["debian"]:
            self.rpm_base_dir = "/usr/src/rpm"
        else:
            self.rpm_base_dir = "/usr/src/packages"
        if sys_dict["vendor"] != "redhat" and (sys_version.startswith("8") or sys_version == "sles8"):
            self.rpm_build_com = "rpm"
        else:
            self.rpm_build_com = "rpmbuild"
        self._check_system_dirs()

    def _check_system_dirs(self):
        if os.getuid() == 0:
            if not os.path.isdir(self.rpm_base_dir):
                os.mkdir(self.rpm_base_dir)
            for file_n in [
                "SPECS", "SOURCES", "RPMS", "BUILD", "SRPMS", "RPMS/i386", "RPMS/i586", "RPMS/noarch", "RPMS/i686"
            ]:
                t_dir = os.path.join(self.rpm_base_dir, file_n)
                if not os.path.isdir(t_dir):
                    print("  Generating directory {} ... ".format(t_dir))
                    os.mkdir(t_dir)

    def _set_package_file_names(self):
        self.spec_file_name = os.path.join(
            self.rpm_base_dir,
            "SPECS",
            "{}.spec".format(self["name"])
        )
        self.tgz_file_name = os.path.join(
            self.rpm_base_dir,
            "SOURCES",
            "{}.tgz".format(self["name"])
        )
        self.short_package_name = "{}-{}-{}.{}.rpm".format(self["name"], self["version"], self["release"], self["arch"])
        self.long_package_name = os.path.join(
            self.rpm_base_dir,
            "RPMS",
            self["arch"],
            self.short_package_name
        )
        self.src_package_name = os.path.join(
            self.rpm_base_dir,
            "SRPMS",
            "{}-{}-{}.src.rpm".format(self["name"], self["version"], self["release"])
        )

    def write_specfile(self, content):
        print("Generating specfile ...")
        spec_contents = [
            "%define debug_package %{nil}",
            "%%define VERSION %s" % (self["version"]),
            "%%define RELEASE %s" % (self["release"]),
            # no longer needed
            # "%define SPACE \" \"",
            "Name: %s" % (self["name"]),
            "Version: %s" % (self["version"]),
            "Release: %s" % (self["release"]),
            "Group: %s" % (self["package_group"]),
            "provides: {}".format(self["provides"]) if self["provides"] else "",
            "License: GPL",
            "Vendor: init.at Informationstechnologie GmbH",
            "Summary: %s" % (self.get("summary", "no summary")),
            "Source: %s" % (os.path.basename(self.tgz_file_name)),
            "BuildRoot: %{_tmppath}/%{name}-%{version}-build",
            "Packager: %s" % (self["packager"]),
            "%define _binary_payload w9.bzdio",
            "%%define _topdir %s" % (self.rpm_base_dir),
            "%description",
            "%s" % (self["description"]),
            "%prep",
            "%setup -c",
            "%build",
            "%install",
            "rm -rf \"$RPM_BUILD_ROOT\"",
            "mkdir -p \"$RPM_BUILD_ROOT\""]
        dest_files = []
        inst_bin = "%s %s" % (self["inst_binary"],
                              self["inst_options"])
        for _src_dir, dest_dir in content.get_types("d"):
            spec_contents.extend(
                [
                    "%s -d \"${RPM_BUILD_ROOT}%s\"" % (
                        inst_bin,
                        self._str_rep(dest_dir)
                    )
                ]
            )
            # dest_files.append(dest_dir)
        dirs_created = set()
        for src_file, dest_file in content.get_types("f"):
            t_dir = os.path.dirname(dest_file)
            if t_dir not in dirs_created:
                dirs_created.add(t_dir)
                spec_contents.append(
                    "mkdir -p \"${{RPM_BUILD_ROOT}}{}\"".format(
                        self._str_rep(t_dir),
                    )
                )
            spec_contents.append(
                "cp -a \"/{}\" \"${{RPM_BUILD_ROOT}}{}\"".format(
                    self._str_rep(src_file),
                    self._str_rep(dest_file)
                )
            )
            dest_files.append(dest_file)
        for src_link, dest_link in content.get_types("la") + content.get_types("lr"):
            # print "***", src_link, dest_link
            if src_link.endswith("/"):
                # directory link
                spec_contents.extend(
                    [
                        "linktarget=\"${RPM_BUILD_ROOT}/%s\"" % (self._str_rep(src_link[:-1])),
                        "mkdir -p $(dirname \"${linktarget}\")",
                        "ln -sf \"%s\" \"$linktarget\"" % (self._str_rep(dest_link)),
                    ]
                )
            else:
                # file link
                spec_contents.extend(
                    [
                        "linktarget=\"${RPM_BUILD_ROOT}/%s\"" % (self._str_rep(src_link)),
                        "mkdir -p $(dirname \"${linktarget}\")",
                        "ln -sf \"%s\" \"$linktarget\"" % (self._str_rep(dest_link)),
                    ]
                )
            dest_files.append(src_link)
        for script_type in SCRIPT_TYPES:
            script_key = "%s_script" % (script_type)
            if script_key in self:
                script_content = self[script_key]
                if isinstance(script_content, str):
                    script_content = script_content.split("\n")
                spec_contents.extend(
                    [
                        "",
                        "%{}".format(script_type),
                    ] + script_content + [
                        ""
                    ]
                )
        spec_contents.extend(
            [
                "%clean",
                "rm -rf \"$RPM_BUILD_ROOT\"",
                "%files",
                "%defattr(-,{},{})".format(
                    self["user"],
                    self["group"]
                )
            ]
        )
        for df in dest_files:
            # file_dirs = os.path.dirname(df).split("/")
            # if [x for x in file_dirs if x in self["doc_dirs"]]:
            #    spec_contents.append("%%doc \"%s\"" % (df))
            spec_contents.append("\"{}\"".format(df))
            # spec_contents.extend(["%%dir \"%s\"" % (act_dir) for act_dir in dest_dirs])
        for _src_dir, dest_dir in content.get_types("d"):
            spec_contents.append("%dir {}".format(dest_dir))
        open(self.spec_file_name, "wb").write("\n".join(spec_contents + [""]))
        # spec_file.close()

    def _str_rep(self, in_str):
        return in_str.replace("(", "\(").replace(")", "\)").replace("$", "\$")

    def create_tgz_file(self, content):
        tgz_files = content.get_tgz_files()
        print("Generating tgz-file (%s) ..." % (logging_tools.get_plural("entry", len(tgz_files))))
        num_sim = 200
        first_call = True
        while tgz_files:
            if first_call:
                tar_com = "tar -cpszf"
            else:
                tar_com = "tar -Apszf"
                first_call = False
            tar_com = "%s %s %s" % (
                tar_com,
                self.tgz_file_name,
                (" ".join(tgz_files[:num_sim])).replace("$", "\$"),
            )
            c_stat, c_out = subprocess.getstatusoutput(tar_com)
            if c_stat:
                print(
                    " *** Error for creating tar-file (%d): %s" % (
                        c_stat,
                        c_out or "no output"
                    )
                )
            else:
                print(".")
            tgz_files = tgz_files[num_sim:]
        print()

    def build_package(self):
        print("Building package...")
        stat, out = subprocess.getstatusoutput(
            "%s --target %s-init.at\\\\\ Informationstechnologie\\\\\ GmbH-Linux -ba %s" % (
                self.rpm_build_com,
                self["arch"],
                self.spec_file_name
            )
        )
        if stat:
            out_lines = out.split("\n")
            print(
                "Some error occured ({:d}), {}:".format(
                    stat,
                    logging_tools.get_plural("line", len(out_lines))
                )
            )
            for line in out_lines:
                print("    {}".format(line.rstrip()))
        else:
            self.build_ok = True


class file_content_list(object):
    def __init__(self, s_points, **args):
        # content_list, format (type, source, dest)
        # for type == f : s_file, d_file
        self.__content_list = []
        # list of arguments
        start_points, exclude_paths = (set(), set())
        for s_point in s_points:
            # expand
            if s_point[0] in ["!"]:
                exclude_paths.update({part.strip() for part in s_point[1:].split(",")})
            else:
                if s_point.startswith("*"):
                    start_points.update({s_point[1:].strip()})
                else:
                    start_points.update({part.strip() for part in s_point.split(",")})
        # print start_points, exclude_paths
        # check for exclude paths
        if exclude_paths:
            exclude_paths = [os.path.realpath(part) for part in exclude_paths]
            print(
                "{}: {}".format(
                    logging_tools.get_plural("exclude path", len(exclude_paths)),
                    ", ".join(sorted(exclude_paths))
                )
            )
            exclude_not_ok = [part for part in exclude_paths if not os.path.exists(part)]
            if exclude_not_ok:
                print(
                    "Error, {}: {}".format(
                        logging_tools.get_plural("nonexisting exclude path", len(exclude_not_ok)),
                        ", ".join(exclude_not_ok)
                    )
                )
                sys.exit(-1)
        exc_dir_names = set(args.get("exclude_dir_names", []))
        # iterate over start_points
        for start_point in start_points:
            excl_dict = {
                "files": [],
                "dirs": []
            }
            files_found = []
            if start_point.count(":") > 1:
                print(
                    "Error, need a source- and an optional destination path ({}), found too many ({:d}) colons".format(
                        start_point,
                        start_point.count(":")
                    )
                )
                sys.exit(-1)
            if start_point.count(":"):
                source_part, dest_part = start_point.split(":", 1)
            else:
                source_part, dest_part = (start_point, start_point)
            source_part = os.path.normpath(source_part)
            if os.path.islink(source_part):
                link_target = os.readlink(source_part)
                if link_target.startswith("/"):
                    print("  Absolute Link {} -> {}".format(source_part, link_target))
                    self._add_absolute_link_to_content(source_part, link_target, source_part, dest_part)
                else:
                    print("  Relative Link {] -> {}".format(source_part, link_target))
                    self._add_relative_link_to_content(source_part, link_target, source_part, dest_part)
            else:
                source_part = os.path.realpath(source_part)
                if os.path.isfile(source_part):
                    source_part = self._remove_leading_slash(source_part)
                    dest_part = self._add_leading_slash(dest_part)
                    self._add_file_to_content(source_part, source_part, dest_part)
                    files_found.append(self._get_file_info(source_part))
                elif os.path.isdir(source_part):
                    source_part = self._remove_leading_slash(source_part)
                    dest_part = self._add_leading_slash(dest_part)
                    for dir_path, dir_names, file_names in os.walk(self._add_leading_slash(source_part)):
                        if os.path.split(dir_path)[1] in exc_dir_names or len([True for part in exclude_paths if os.path.normpath(part) == dir_path]):
                            # print " +++ skipping dir %s and everything below" % (dir_path)
                            excl_dict["dirs"].append(dir_path)
                            while dir_names:
                                # we have to pop every entry to keep the list intact
                                dir_names.pop(0)
                        else:
                            for rem_dir in [act_dir for act_dir in dir_names if act_dir in exc_dir_names]:
                                # print "+++ removing directory %s/%s from walk" % (dir_path, rem_dir)
                                excl_dict["dirs"].append(os.path.join(dir_path, rem_dir))
                                dir_names.remove(rem_dir)
                            self._add_dir_to_content(dir_path, source_part, dest_part)
                            for entry in dir_names + file_names:
                                full_path = os.path.normpath(os.path.join(dir_path, entry))
                                if [True for part in exclude_paths if full_path.startswith(part)]:
                                    # exclude
                                    excl_dict["files"].append(full_path)
                                else:
                                    if os.path.islink(full_path):
                                        link_target = os.readlink(full_path)
                                        if link_target.startswith("/"):
                                            print(
                                                "  Absolute Link {} -> {}".format(
                                                    full_path,
                                                    link_target
                                                )
                                            )
                                            self._add_absolute_link_to_content(full_path, link_target, source_part, dest_part)
                                        else:
                                            print(
                                                "  Relative Link {} -> {}".format(
                                                    full_path,
                                                    link_target
                                                )
                                            )
                                            self._add_relative_link_to_content(full_path, link_target, source_part, dest_part)
                                    elif os.path.isfile(full_path):
                                        self._add_file_to_content(full_path, source_part, dest_part)
                                        files_found.append(self._get_file_info(full_path))
                else:
                    print(
                        "*** startpoint {} is neither file nor dir ...".format(
                            source_part
                        )
                    )
            if files_found:
                print(
                    "{}: added {} (total {})".format(
                        start_point,
                        logging_tools.get_plural("file", len(files_found)),
                        logging_tools.get_size_str(sum(files_found), long_format=True)
                    )
                )
            if sum([len(e_list) for e_list in list(excl_dict.values())]):
                print(
                    "\nexclude info for {}: {}\n".format(
                        start_point,
                        ", ".join(
                            [
                                "{}: {:d}".format(
                                    key,
                                    len(value)
                                ) for key, value in excl_dict.items()
                            ]
                        )
                    )
                )
        # pprint.pprint(self.__content_list)

    def _remove_leading_slash(self, path):
        while path.startswith("/"):
            path = path[1:]
        return path

    def _add_leading_slash(self, path):
        if not path.startswith("/"):
            path = "/{}".format(path)
        return path

    def _add_file_to_content(self, s_file, s_part, d_part):
        self.__content_list.append(("f", self._remove_leading_slash(s_file), os.path.normpath(s_file.replace(s_part, d_part))))

    def _add_dir_to_content(self, d_path, s_part, d_part):
        self.__content_list.append(("d", d_path, os.path.normpath(d_path.replace(s_part, d_part))))

    def _add_absolute_link_to_content(self, link_src, link_dst, s_part, d_part):
        self.__content_list.append(("la", os.path.normpath(link_src.replace(s_part, d_part)), link_dst))

    def _add_relative_link_to_content(self, link_src, link_dst, s_part, d_part):
        self.__content_list.append(("lr", os.path.normpath(link_src), link_dst))

    def _get_file_info(self, f_name):
        return os.stat("/{}".format(f_name))[stat.ST_SIZE]

    def show_content(self):
        # print "Passt"
        # return
        file_dict = {_v[1]: _v[2] for _v in self.__content_list if _v[0] == "f"}
        dir_dict = {_v[1]: _v[2] for _v in self.__content_list if _v[0] == "d"}
        file_keys, dir_keys = (
            sorted(file_dict.keys()),
            sorted(dir_dict.keys())
        )
        if file_keys:
            print(
                "Content of file-list (source -> dest, {}):".format(
                    logging_tools.get_plural("entry", len(file_keys))
                )
            )
            for sf in file_keys:
                print("  {:<40s} -> {}".format(sf, file_dict[sf]))
        if dir_keys:
            print(
                "Content of dir-list (source -> dest, {}):".format(
                    logging_tools.get_plural("entry", len(dir_keys))
                )
            )
            for sd in dir_keys:
                print("  {:<40s} -> {}".format(sd, dir_dict[sd]))

    def __ne__(self):
        return True if self.__content_list else False

    def get_types(self, s_type):
        return [
            (src, dst) for e_type, src, dst in self.__content_list if e_type == s_type
        ]

    def get_tgz_files(self):
        return [
            "\"/{}\"".format(src) for e_type, src, _dst in self.__content_list if e_type == "f"
        ]
