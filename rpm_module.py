# Copyright (C) 2001,2002,2003,2004,2005,2006,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of package-tools
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
""" frontend tools for rpm handling """

import sys
import imp
import os
import exceptions
import cpu_database


def __import__(name):
    if name in sys.modules:
        mod = sys.modules[name]
    else:
        old_sys_path = [x for x in sys.path]
        for add_dir in ["/usr/lib64/python/site-packages",
                        "/usr/lib/python/site-packages"]:
            if os.path.isdir(add_dir) and add_dir not in sys.path:
                sys.path.append(add_dir)
        # print sys.path
        fp, pathname, description = imp.find_module(name)
        sys.path = old_sys_path
        try:
            mod = imp.load_module(name, fp, pathname, description)
        finally:
            if fp:
                fp.close()
    return mod

try:
    rpm = __import__("rpm")
except ImportError:
    rpm = None


def get_canonical_architecture():
    can_arch = "???"
    arch = os.uname()[4]
    cpu_bi = cpu_database.get_cpu_basic_info()
    vendor_id, _cpu_family, _cpu_model = (cpu_bi["vendor_id"], cpu_bi["cpu family"], cpu_bi["model"])
    if arch.startswith("i") and arch.endswith("86"):
        if vendor_id.lower().count("amd"):
            can_arch = "athlon"
        elif not cpu_bi["flags"].count("cmov"):
            can_arch = "i586"
    return can_arch


def arch_norm(my_arch, target_arch):
    arch_dict = {
        "athlon": "i686",
        "i686": "i586",
        "i586": "i486",
        "i486": "i386",
        "i386": "noarch",
        # amd64
        "x86_64": "athlon",
        "amd64": "x86_64",
        "ia32e": "x86_64"
    }
    if my_arch == target_arch:
        diff = 1
    elif my_arch in arch_dict:
        diff = arch_norm(arch_dict[my_arch], target_arch)
        if diff:
            diff += 1
    else:
        diff = 0
    return diff


def get_TransactionSet(root_dir="/"):
    if rpm:
        if root_dir != "/":
            return rpm.TransactionSet(root_dir)
        else:
            return rpm.TransactionSet()
    else:
        return None


def rpm_module_ok():
    return rpm and True or False


def get_rpm_module():
    return rpm


class RPMError(exceptions.Exception):
    def __init__(self, args=None):
        exceptions.Exception.__init__(self)
        self.value = args

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "RPMError %s" % (str(self.value))


def return_package_header(name):
    try:
        fdno = os.open(name, os.O_RDONLY)
    except OSError:
        raise RPMError("Error opening file %s" % (name))
    my_ts = rpm.TransactionSet()
    my_ts.setVSFlags(~(rpm.RPMVSF_NOMD5 | rpm.RPMVSF_NEEDPAYLOAD))
    try:
        header = my_ts.hdrFromFdno(fdno)
    except rpm.error:
        raise RPMError("Error opening package %s" % (name))
    if type(header) != rpm.hdr:
        raise RPMError("Error opening package %s" % (name))
    my_ts.setVSFlags(0)
    os.close(fdno)
    del fdno
    return header


def get_needs_string(needs_int):
    needs_str = "".join([ns for ni, ns in [(rpm.RPMSENSE_LESS, "<"),
                                           (rpm.RPMSENSE_GREATER, ">"),
                                           (rpm.RPMSENSE_EQUAL, "=")] if needs_int & ni]) or "?"
    return needs_str


class rpm_package(object):
    def __init__(self, header, list_flags=""):
        self.set_basic_info(header)
        # list_flags, string, subset of "pdco"
        for lf in list_flags:
            getattr(self, "set_%ss" % {"p": "provide",
                                       "d": "depend",
                                       "c": "conflict",
                                       "o": "obsolete"}[lf])(header)

    def set_basic_info(self, header):
        self.bi = {}
        for what in ["name", "group", "epoch", "version", "release", "size", "arch", "summary", "installtime"]:
            self.bi[what] = header[what]  # getattr(rpm, "RPMTAG_%s" % (what.upper()))]
        for l_name in ["provide", "depend", "conflict", "obsolete"]:
            setattr(self, "%ss_list" % (l_name), None)
        # print self.bi

    def correct_flags(self, flag_list):
        returnflags = []
        if flag_list:
            if type(flag_list) != list:
                flag_list = [flag_list]
            for flag in flag_list:
                if flag:
                    returnflags.append(flag & 0xf)
                else:
                    returnflags.append(flag)
        return returnflags

    def correct_version(self, vers_list):
        if vers_list is None:
            returnvers = [(None, None, None)]
        else:
            returnvers = []
            if type(vers_list) != list:
                vers_list = [vers_list]
            for ver in vers_list:
                if ver:
                    returnvers.append(self.string_to_version(ver))
                else:
                    returnvers.append((None, None, None))
        return returnvers

    def string_to_version(self, strng):
        s1 = strng.split(":", 1)
        if len(s1) == 1:
            epoch, sub_str = ("0", strng)
        else:
            epoch, sub_str = s1
        s2 = sub_str.split("-", 1)
        if len(s2) == 1:
            version, release = (sub_str, "")
        else:
            version, release = s2
        epoch, version, release = tuple([x or None for x in [epoch, version, release]])
        return (epoch, version, release)

    def unique_via_dict(self, in_list):
        return dict([(x, 0) for x in in_list]).keys()

    def get_dep_list(self, header, name_tag, flag_tag, version_tag):
        names = header[name_tag]
        if names:
            lst = self.unique_via_dict(zip(names, self.correct_flags(header[flag_tag]), self.correct_version(header[version_tag])))
        else:
            lst = []
        return lst

    def set_provides(self, header):
        self.provides_list = self.get_dep_list(header,
                                               rpm.RPMTAG_PROVIDENAME,
                                               rpm.RPMTAG_PROVIDEFLAGS,
                                               rpm.RPMTAG_PROVIDEVERSION)

    def set_depends(self, header):
        self.depends_list = self.get_dep_list(header,
                                              rpm.RPMTAG_REQUIRENAME,
                                              rpm.RPMTAG_REQUIREFLAGS,
                                              rpm.RPMTAG_REQUIREVERSION)

    def set_conflicts(self, header):
        self.conflicts_list = self.get_dep_list(header,
                                                rpm.RPMTAG_CONFLICTNAME,
                                                rpm.RPMTAG_CONFLICTFLAGS,
                                                rpm.RPMTAG_CONFLICTVERSION)

    def set_obsoletes(self, header):
        self.obsoletes_list = self.get_dep_list(header,
                                                rpm.RPMTAG_OBSOLETENAME,
                                                rpm.RPMTAG_OBSOLETEFLAGS,
                                                rpm.RPMTAG_OBSOLETEVERSION)
