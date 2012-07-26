#!/usr/bin/python-init -Otu
#
# Copyright (c) 2007,2008 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" classes for build rpm-packages """

import sys
import os
import logging_tools
import pwd
import commands
import socket
import process_tools
import pprint
import stat

SCRIPT_TYPES = ["post", "pre", "postun", "preun"]

class build_package(object):
    def __init__(self, **args):
        self.__value_dict = {}
        # default: build went wrong
        self.build_ok = False
        self._check_system_settings()
        self["summary"] = "files and directories for package"
        self["packager"] = "%s@%s" % (pwd.getpwuid(os.getuid())[0], socket.getfqdn())
        self["description"] = "Auto-generated package"
        self["user"] = "root"
        self["group"] = "root"
        self["doc_dirs"] = ["man", "doc", "example", "examples"]
        self["inst_options"] = " -p -o root -g root "
        self["inst_binary"] = "install"
        for key, value in args.iteritems():
            self[key] = value
    def __setitem__(self, key, value):
        self.__value_dict[key] = value
        needed_keys = ["name", "version", "release", "arch"]
        if key in needed_keys and len([True for key in needed_keys if key in self.__value_dict]) == len(needed_keys):
            self._set_package_file_names()
    def __getitem__(self, key):
        return self.__value_dict[key]
    def has_key(self, key):
        return key in self.__value_dict
    def __contains__(self, key):
        return key in self.__value_dict
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
        self["arch"] = {"i686" : "i586"}.get(os.uname()[4], os.uname()[4])
    def _check_system_dirs(self):
        if os.getuid() == 0:
            if not os.path.isdir(self.rpm_base_dir):
                os.mkdir(self.rpm_base_dir)
            for file_n in ["SPECS", "SOURCES", "RPMS", "BUILD", "SRPMS", "RPMS/i386", "RPMS/i586", "RPMS/noarch", "RPMS/i686"]:
                t_dir = "%s/%s" % (self.rpm_base_dir, file_n)
                if not os.path.isdir(t_dir):
                    print "  Generating directory %s ... " % (t_dir)
                    os.mkdir(t_dir)
    def _set_package_file_names(self):
        self.spec_file_name = "%s/SPECS/%s.spec" % (self.rpm_base_dir, self["name"])
        self.tgz_file_name = "%s/SOURCES/%s.tgz" % (self.rpm_base_dir, self["name"])
        self.short_package_name = "%s-%s-%s.%s.rpm" % (self["name"], self["version"], self["release"], self["arch"])
        self.long_package_name = "%s/RPMS/%s/%s" % (self.rpm_base_dir, self["arch"], self.short_package_name)
        self.src_package_name = "%s/SRPMS/%s-%s-%s.src.rpm" % (self.rpm_base_dir, self["name"], self["version"], self["release"])
    def write_specfile(self, content):
        print "Generating specfile ..."
        spec_contents = ["%define debug_package %{nil}",
                         "%%define VERSION %s" % (self["version"]),
                         "%%define RELEASE %s" % (self["release"]),
                         # no longer needed
                         #"%define SPACE \" \"",
                         "Name: %s" % (self["name"]),
                         "Version: %s" % (self["version"]),
                         "Release: %s" % (self["release"]),
                         "Group: %s" % (self["package_group"]),
                         "License: GPL",
                         "Vendor: init.at Informationstechnologie GmbH",
                         "Summary: %s" % (self["summary"]),
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
        dest_dirs = []
        inst_bin = "%s %s" % (self["inst_binary"],
                              self["inst_options"])
        for src_dir, dest_dir in content.get_types("d"):
            spec_contents.extend(["%s -d \"${RPM_BUILD_ROOT}%s\"" % (inst_bin,
                                                                     self._str_rep(dest_dir))])
            #dest_files.append(dest_dir)
        for src_file, dest_file in content.get_types("f"):
            spec_contents.extend(["mkdir -p \"${RPM_BUILD_ROOT}%s\"" % (self._str_rep(os.path.dirname(dest_file))),
                                  "cp -a \"/%s\" \"${RPM_BUILD_ROOT}%s\"" % (self._str_rep(src_file),
                                                                             self._str_rep(dest_file))])
            dest_files.append(dest_file)
        for src_link, dest_link in content.get_types("la") + content.get_types("lr"):
            #print "***", src_link, dest_link
            if src_link.endswith("/"):
                # directory link
                spec_contents.extend(["linktarget=\"${RPM_BUILD_ROOT}/%s\"" % (self._str_rep(src_link[:-1])),
                                      "mkdir -p $(dirname \"${linktarget}\")",
                                      "ln -sf \"%s\" \"$linktarget\"" % (self._str_rep(dest_link)),
                                      ])
            else:
                # file link
                spec_contents.extend(["linktarget=\"${RPM_BUILD_ROOT}/%s\"" % (self._str_rep(src_link)),
                                      "mkdir -p $(dirname \"${linktarget}\")",
                                      "ln -sf \"%s\" \"$linktarget\"" % (self._str_rep(dest_link)),
                                      ])
            dest_files.append(src_link)
        for script_type in SCRIPT_TYPES:
            script_key = "%s_script" % (script_type)
            if script_key in self:
                script_content = self[script_key]
                if type(script_content) == type(""):
                    script_content = script_content.split("\n")
                spec_contents.extend(["",
                                      "%%%s" % (script_type),
                                      ] + script_content +
                                     [""])
        spec_contents.extend(["%clean",
                              "rm -rf \"$RPM_BUILD_ROOT\"",
                              "%files",
                              "%%defattr(-,%s,%s)" % (self["user"],
                                                      self["group"])])
        for df in dest_files:
            #file_dirs = os.path.dirname(df).split("/")
            #if [x for x in file_dirs if x in self["doc_dirs"]]:
            #    spec_contents.append("%%doc \"%s\"" % (df))
            spec_contents.append("\"%s\"" % (df))
                #spec_contents.extend(["%%dir \"%s\"" % (act_dir) for act_dir in dest_dirs])
        for src_dir, dest_dir in content.get_types("d"):
            spec_contents.append("%%dir %s" % (dest_dir))
        file(self.spec_file_name, "wb").write("\n".join(spec_contents + [""]))
        #spec_file.close()
    def _str_rep(self, in_str):
        return in_str.replace("(", "\(").replace(")", "\)").replace("$", "\$")
    def create_tgz_file(self, content):
        tgz_files = content.get_tgz_files()
        print "Generating tgz-file (%s) ..." % (logging_tools.get_plural("entry", len(tgz_files)))
        num_sim = 200
        first_call = True
        while tgz_files:
            if first_call:
                tar_com = "tar -cpszf"
            else:
                tar_com = "tar -Apszf"
                first_call = False
            tar_com = "%s %s %s" % (tar_com,
                                    self.tgz_file_name,
                                    (" ".join(tgz_files[:num_sim])).replace("$", "\$"))
            c_stat, c_out = commands.getstatusoutput(tar_com)
            if c_stat:
                print " *** Error for creating tar-file (%d): %s" % (c_stat,
                                                                     c_out or "no output")
            else:
                print ".",
            tgz_files = tgz_files[num_sim:]
        print
    def build_package(self):
        print "Building package..."
        stat, out = commands.getstatusoutput("%s --target %s-init.at\\\\\ Informationstechnologie\\\\\ GmbH-Linux -ba %s" % (self.rpm_build_com,
                                                                                                                             self["arch"],
                                                                                                                             self.spec_file_name))
        if stat:
            out_lines = out.split("\n")
            print "Some error occured (%d), %s:" % (stat, logging_tools.get_plural("line", len(out_lines)))
            for line in out_lines:
                print "    %s" % (line.rstrip())
        else:
            self.build_ok = True

class file_content_list_old(object):
    def __init__(self, args, **adict):
        file_dict, dir_dict = ({}, {})
        # list of arguments
        act_args = []
        for arg in args:
            if arg[0] in ["!"]:
                act_list = ["%s%s" % (arg[0], x.strip()) for x in arg[1:].split(",")]
            else:
                act_list = [x.strip() for x in arg.split(",")]
            act_args.extend(act_list)
        # check for exclude paths
        excl_paths = sorted([os.path.normpath(x[1:]) for x in act_args if x.startswith("!")])
        if excl_paths:
            print "%s: %s" % (logging_tools.get_plural("exclude path", len(excl_paths)),
                              ", ".join(excl_paths))
            excl_not_ok = [x for x in excl_paths if not os.path.exists(x)]
            if excl_not_ok:
                print "Error, %s: %s" % (logging_tools.get_plural("noexisting exclude path", len(excl_not_ok)),
                                  ", ".join(excl_not_ok))
                sys.exit(-1)
        exc_dir_names = set(adict.get("exclude_dir_names", []))
        # normal paths
        norm_paths = [x for x in act_args if not x.startswith("!")]
        for fp in norm_paths:
            pt = fp.split(":")
            if len(pt) == 2:
                s_part, d_part = (pt[0], pt[1])
            elif len(pt) == 1:
                s_part, d_part = (pt[0], pt[0])
            else:
                print "Error, need a source- and destination path (%s), found too many semicolons" % (fp)
                sys.exit(-1)
            if os.path.islink(s_part):
                pass
            else:
                s_part = os.path.realpath(s_part)
            if os.path.islink(s_part):
                file_dict[s_part] = d_part
            elif os.path.isfile(s_part):
                if s_part.startswith("/"):
                    s_part = s_part[1:]
                if not d_part.startswith("/"):
                    d_part = "/%s" % (d_part)
                file_dict[s_part] = d_part
            elif os.path.isdir(s_part):
                if s_part.startswith("/"):
                    s_part = s_part[1:]
                if not d_part.startswith("/"):
                    d_part = "/%s" % (d_part)
                f_list, d_list, l_list = ([], [], [])
                num_dir_exclude, num_file_exclude = (0, 0)
                for dir_path, dir_names, file_names in os.walk("/%s" % (s_part)):
                    dir_parts = [part for part in dir_path.replace("//", "/").replace("//", "/").split("/") if part]
                    if exc_dir_names.intersection(set(dir_parts)):
                        print " ... excluding dir %s" % (dir_path)
                    else:
                        rem_dirs = [act_dir for act_dir in dir_names if exc_dir_names.intersection(set(act_dir))]
                        for rem_dir in rem_dirs:
                            dir_names.remove(rem_dir)
                        if os.path.islink(dir_path[1:]):
                            link_name = dir_path[1:]
                            link_target = os.readlink(link_name)
                            print "  DirLink %s -> %s" % (link_name, link_target)
                            if os.readlink(link_name).startswith("/"):
                                l_list += [("a", link_name, link_target)]
                            else:
                                l_list += [("r", link_name, link_target)]
                        else:
                            if [True for x in excl_paths if dir_path.startswith(x)]:
                                num_dir_exclude += 1
                            else:
                                d_list += [dir_path[1:]]
                                for entry in dir_names + file_names:
                                    full_path = os.path.normpath("%s/%s" % (dir_path, entry))
                                    if [True for x in excl_paths if full_path.startswith(x)]:
                                        # exclude
                                        num_file_exclude += 1
                                    else:
                                        if os.path.islink(full_path):
                                            link_target = os.readlink(full_path)
                                            print "  Link %s -> %s" % (full_path, os.readlink(full_path))
                                            if full_path.startswith("/"):
                                                l_list += [("a", full_path[1:], link_target)]
                                            else:
                                                l_list += [("r", full_path[1:], link_target)]
                                        elif os.path.isfile(full_path):
                                            f_list += [full_path[1:]]
                dir_dict[s_part] = (d_list, f_list, l_list, d_part, (num_dir_exclude, num_file_exclude))
                pprint.pprint(dir_dict[s_part])
            else:
                print "Error, not a valid source-path, skipping : %s" % (s_part)
        self.file_dict, self.dir_dict = (file_dict, dir_dict)
    def show_content(self):
        file_keys, dir_keys = (sorted(self.file_dict.keys()),
                               sorted(self.dir_dict.keys()))
        if file_keys:
            print "Content of file-list (source -> dest, %s):" % (logging_tools.get_plural("entry", len(file_keys)))
            for sf in file_keys:
                print "  %-40s -> %s" % (sf, self.file_dict[sf])
        if dir_keys:
            print "Content of dir-list (source -> dest, %s):" % (logging_tools.get_plural("entry", len(dir_keys)))
            for sd in dir_keys:
                d_list, f_list, l_list, d_dir, (num_dir_exclude, num_file_exclude) = self.dir_dict[sd]
                print "  %-40s -> [%3d files, %2d dirs, %2d links, %s, %s] %s" % (sd, len(f_list), len(d_list), len(l_list),
                                                                                  logging_tools.get_plural("dir exclude", num_dir_exclude),
                                                                                  logging_tools.get_plural("file exclude", num_file_exclude),
                                                                                  d_dir)
    def get_tgz_files(self):
        return ["/%s" % (x.replace(" ", "\ ")) for x in self.file_dict.keys()] + \
            [" "] + \
            ["/%s" % (x) for x in self.dir_dict.keys()]

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
                exclude_paths.update(set([part.strip() for part in s_point[1:].split(",")]))
            else:
                if s_point.startswith("*"):
                    start_points.update(set([s_point[1:].strip()]))
                else:
                    start_points.update(set([part.strip() for part in s_point.split(",")]))
        #print start_points, exclude_paths
        # check for exclude paths
        if exclude_paths:
            exclude_paths = [os.path.realpath(part) for part in exclude_paths]
            print "%s: %s" % (logging_tools.get_plural("exclude path", len(exclude_paths)),
                              ", ".join(sorted(exclude_paths)))
            exclude_not_ok = [part for part in exclude_paths if not os.path.exists(part)]
            if exclude_not_ok:
                print "Error, %s: %s" % (logging_tools.get_plural("nonexisting exclude path", len(exclude_not_ok)),
                                         ", ".join(exclude_not_ok))
                sys.exit(-1)
        exc_dir_names = set(args.get("exclude_dir_names", []))
        # iterate over start_points
        for start_point in start_points:
            excl_dict = {"files" : [],
                         "dirs"  : []}
            files_found = []
            if start_point.count(":") > 1:
                print "Error, need a source- and an optional destination path (%s), found too many (%d) colons" % (start_point,
                                                                                                                   start_point.count(":"))
                sys.exit(-1)
            if start_point.count(":"):
                source_part, dest_part = start_point.split(":", 1)
            else:
                source_part, dest_part = (start_point, start_point)
            source_part = os.path.normpath(source_part)
            if os.path.islink(source_part):
                link_target = os.readlink(source_part)
                if link_target.startswith("/"):
                    print "  Absolute Link %s -> %s" % (source_part, link_target)
                    self._add_absolute_link_to_content(source_part, link_target, source_part, dest_part)
                else:
                    print "  Relative Link %s -> %s" % (source_part, link_target)
                    self._add_relative_link_to_content(source_part, link_target, source_part, dest_part)
            else:
                source_part = os.path.realpath(source_part)
                if os.path.isfile(source_part):
                    source_part = self._remove_leading_slash(source_part)
                    dest_part = self._add_leading_slash(dest_part)
                    self._add_file_to_content(source_part, source_part, dest_part)
                    files_found.append(self._get_file_info(source_part))
                elif os.path.isdir(source_part):
                    all_taken = True
                    source_part = self._remove_leading_slash(source_part)
                    dest_part = self._add_leading_slash(dest_part)
                    for dir_path, dir_names, file_names in os.walk(self._add_leading_slash(source_part)):
                        if os.path.split(dir_path)[1] in exc_dir_names or len([True for part in exclude_paths if os.path.normpath(part) == dir_path]):
                            #print " +++ skipping dir %s and everything below" % (dir_path)
                            excl_dict["dirs"].append(dir_path)
                            while dir_names:
                                # we have to pop every entry to keep the list intact
                                dir_names.pop(0)
                        else:
                            for rem_dir in [act_dir for act_dir in dir_names if act_dir in exc_dir_names]:
                                #print "+++ removing directory %s/%s from walk" % (dir_path, rem_dir)
                                excl_dict["dirs"].append("%s/%s" % (dir_path, rem_dir))
                                dir_names.remove(rem_dir)
                            self._add_dir_to_content(dir_path, source_part, dest_part)
                            for entry in dir_names + file_names:
                                full_path = os.path.normpath("%s/%s" % (dir_path, entry))
                                if [True for part in exclude_paths if full_path.startswith(part)]:
                                    # exclude
                                    excl_dict["files"].append(full_path)
                                else:
                                    if os.path.islink(full_path):
                                        link_target = os.readlink(full_path)
                                        if link_target.startswith("/"):
                                            print "  Absolute Link %s -> %s" % (full_path, link_target)
                                            self._add_absolute_link_to_content(full_path, link_target, source_part, dest_part)
                                        else:
                                            print "  Relative Link %s -> %s" % (full_path, link_target)
                                            self._add_relative_link_to_content(full_path, link_target, source_part, dest_part)
                                    elif os.path.isfile(full_path):
                                        self._add_file_to_content(full_path, source_part, dest_part)
                                        files_found.append(self._get_file_info(full_path))
                else:
                    print "*** startpoint %s is neither file nor dir ..." % (source_part)
            if files_found:
                print "%s: added %s (total %s)" % (start_point,
                                                   logging_tools.get_plural("file", len(files_found)),
                                                   logging_tools.get_size_str(sum(files_found), long_version=True))
            if sum([len(e_list) for e_list in excl_dict.values()]):
                print "\nexclude info for %s: %s\n" % (start_point,
                                                       ", ".join(["%s: %d" % (key, len(value)) for key, value in excl_dict.iteritems()]))
        #pprint.pprint(self.__content_list)
    def _remove_leading_slash(self, path):
        while path.startswith("/"):
            path = path[1:]
        return path
    def _add_leading_slash(self, path):
        if not path.startswith("/"):
            path = "/%s" % (path)
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
        return os.stat("/%s" % (f_name))[stat.ST_SIZE]
    def show_content(self):
        print "Passt"
        return
        file_keys, dir_keys = (sorted(self.file_dict.keys()),
                               sorted(self.dir_dict.keys()))
        if file_keys:
            print "Content of file-list (source -> dest, %s):" % (logging_tools.get_plural("entry", len(file_keys)))
            for sf in file_keys:
                print "  %-40s -> %s" % (sf, self.file_dict[sf])
        if dir_keys:
            print "Content of dir-list (source -> dest, %s):" % (logging_tools.get_plural("entry", len(dir_keys)))
            for sd in dir_keys:
                d_list, f_list, l_list, d_dir, (num_dir_exclude, num_file_exclude) = self.dir_dict[sd]
                print "  %-40s -> [%3d files, %2d dirs, %2d links, %s, %s] %s" % (sd, len(f_list), len(d_list), len(l_list),
                                                                                  logging_tools.get_plural("dir exclude", num_dir_exclude),
                                                                                  logging_tools.get_plural("file exclude", num_file_exclude),
                                                                                  d_dir)
    def __ne__(self):
        return True if self.__content_list else False
    def get_types(self, s_type):
        return [(src, dst) for e_type, src, dst in self.__content_list if e_type == s_type]
    def get_tgz_files(self):
        return ["\"/%s\"" % (src) for e_type, src, dst in self.__content_list if e_type == "f"]

def main():
    print "Loadable module, exiting"
    sys.exit(0)
    
if __name__ == "__main__":
    main()
