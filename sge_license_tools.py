#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

import logging_tools
import os
import process_tools
import re
import sys

SITE_CONF_NAME = "lic_SITES.conf"
ACT_SITE_NAME = "actual_SITE"
DEFAULT_SITE = "local"
BASE_DIR = "/etc/sysconfig/licenses"


DEFAULT_CONFIG = {
    "LMUTIL_PATH": "/opt/cluster/bin/lmutil",
    "LICENSE_FILE": ""
}


def get_sge_environment():
    _sge_dict = {}
    for _key in ["sge_root", "sge_cell"]:
        if _key.upper() not in os.environ:
            _file = os.path.join("/etc", _key)
            if os.path.isfile(_file):
                _sge_dict[_key.upper()] = file(_file, "r").read().strip()
            else:
                print("Error, no {} environment variable set or defined in {}".format(_key.upper(), _file))
        else:
            _sge_dict[_key.upper()] = os.environ[_key.upper()]
    arch_util = "{}/util/arch".format(_sge_dict["SGE_ROOT"])
    if not os.path.isfile(arch_util):
        print("No arch-utility found in {}/util".format(_sge_dict["SGE_ROOT"]))
        sys.exit(1)
    _sge_stat, sge_arch = call_command(arch_util)
    sge_arch = sge_arch.strip()
    qconf_bin = "{}/bin/{}/qconf".format(_sge_dict["SGE_ROOT"], sge_arch)
    if not os.path.isfile(qconf_bin):
        print("No qconf command found under {}".format(_sge_dict["SGE_ROOT"]))
        sys.exit(1)
    print(
        ", ".join(["{} is {}".format(_key, _sge_dict[_key]) for _key in sorted(_sge_dict.iterkeys())])
    )
    return _sge_dict


def get_sge_log_line(sge_dict):
    return ", ".join(["{} is {}".format(_key, sge_dict[_key]) for _key in sorted(sge_dict.iterkeys())])


def get_sge_complexes(sge_dict):
    _complex_stat, complex_out = call_command("{} -sc".format(sge_dict["QCONF_BIN"]), 1)
    defined_complexes = [_line for _line in complex_out.split("\n") if _line.strip() and not _line.strip().startswith("#")]
    return defined_complexes, [_line.split()[0] for _line in defined_complexes]


class sge_license(object):
    def __init__(self, attribute, **kwargs):
        self.__name = attribute.lower()
        self.__attribute = attribute
        self.license_type = kwargs.get("license_type", "simple")
        self.__num_lic_servers, self.__lic_servers = (0, [])
        if self.license_type == "simple":
            lsp_parts = kwargs["license_server"].split(",")
            self.__num_lic_servers = len(lsp_parts)
            for lsp_part in lsp_parts:
                port, host = lsp_part.split("@")
                self.__lic_servers.append((int(port), host))
        self.total_num = 0
        self.used_num = 0
        # flag if license is currently in use
        self.is_used = False
        self.changed = True
        # nodegroup dict, currently disabled
        self.__ng_dict = kwargs.get("ng_dict", {})

    def _get_license_type(self):
        return self.__license_type

    def _set_license_type(self, lt):
        self.__license_type = lt
    license_type = property(_get_license_type, _set_license_type)

    def _set_changed(self, changed):
        self.__changed = changed

    def _get_changed(self):
        c = self.__changed
        self.__changed = False
        return c
    changed = property(_get_changed, _set_changed)

    def get_mvect_entries(self, mvect_entry):
        r_list = [
            mvect_entry(
                "lic.%s.used" % (self.name),
                info="Licenses used for %s (%s)" % (self.name, self.info),
                default=0
            ),
            mvect_entry(
                "lic.%s.free" % (self.name),
                info="Licenses free for %s (%s)" % (self.name, self.info),
                default=0
            ),
        ]
        r_list[0].update(self.used_num)
        r_list[1].update(self.free_num)
        for ng_key in self.__ng_dict.iterkeys():
            add_entry = mvect_entry(
                "lic.{}.{}.used".format(self.name, ng_key),
                info="Licenses used for {} on {} ({})".format(self.name, ng_key, self.info),
                default=0
                )
            add_entry.update(self.__lic_sub_dict[ng_key])
            r_list.append(add_entry)
        return r_list

    def _get_info(self):
        if self.license_type == "simple":
            return "simple via server {}".format(self.get_lic_server_spec())
        else:
            return "compound [{} {}]".format(
                self.__operand,
                ",".join(["%s (x%d)" % (key, self.__mult_dict[key]) for key in sorted(self.__source_licenses)])
            )
    info = property(_get_info)

    def get_lic_server_spec(self):
        return ",".join(["{:d}@{}".format(port, host) for port, host in self.__lic_servers])

    def get_num_lic_servers(self):
        return self.__num_lic_servers

    def _set_is_used(self, is_used):
        self.__is_used = is_used

    def _get_is_used(self):
        return self.__is_used
    is_used = property(_get_is_used, _set_is_used)

    def _get_name(self):
        return self.__name
    name = property(_get_name)

    def _get_attribute(self):
        return self.__attribute
    attribute = property(_get_attribute)

    def _set_total_num(self, total):
        self.__total = total

    def _get_total_num(self):
        return self.__total
    total_num = property(_get_total_num, _set_total_num)

    def _set_used_num(self, used):
        self.__used = used

    def _get_used_num(self):
        return self.__used
    used_num = property(_get_used_num, _set_used_num)

    def _get_free_num(self):
        return self.__total - self.__used
    free_num = property(_get_free_num)

    def get_port(self, idx=0):
        return self.__lic_servers[idx][0]

    def get_host(self, idx=0):
        return self.__lic_servers[idx][1]

    def set_compound_operand(self, oper="none"):
        self.__operand = oper.lower()

    def set_source_licenses(self, src_lic=[]):
        self.__source_licenses = set(src_lic)
        self.__mult_dict = dict([(key, src_lic.count(key)) for key in self.__source_licenses])

    def handle_compound(self, lic_dict):
        log_lines = []
        # init to zero
        found_keys = [key for key in lic_dict.keys() if key in self.__source_licenses]
        if found_keys:
            if self.__operand == "add":
                # only supported opperand
                new_total = sum([lic_dict[key].total_num * self.__mult_dict[key] for key in found_keys])
                new_used = sum([lic_dict[key].used_num * self.__mult_dict[key] for key in found_keys])
                if new_total != self.total_num:
                    log_lines.append(
                        (
                            "total for {} changed from {:d} to {:d}".format(
                                self.name,
                                self.total_num,
                                new_total
                            ),
                            logging_tools.LOG_LEVEL_OK
                        )
                    )
                    self.total_num = new_total
                    self.changed = True
                if new_used != self.used_num:
                    log_lines.append(("used for %s changed from %d to %d" % (self.__name,
                                                                             self.used_num,
                                                                             new_used),
                                      logging_tools.LOG_LEVEL_OK))
                    self.used_num = new_used
                    self.changed = True
            elif self.__operand == "max":
                pass
        else:
            self.total_num = 0
            self.used_num = 0
        return log_lines


def get_site_license_file_name(base_dir, act_site):
    return os.path.normpath(os.path.join(base_dir, "lic_{}.conf".format(act_site)))


def get_site_config_file_name(base_dir, act_site):
    return os.path.normpath(os.path.join(base_dir, "lic_{}.src_config".format(act_site)))


class text_file(object):
    def __init__(self, f_name, **kwargs):
        self.__name = f_name
        self.__opts = {key: value for key, value in kwargs.iteritems()}
        self.__read = False
        if not os.path.isfile(self.__name) and kwargs.get("create", False):
            self.write(kwargs.get("content", []))

    def _read_content(self):
        if not os.path.isfile(self.__name):
            if self.__opts.get("ignore_missing", True):
                self.__read = True
                self._lines = self.__opts.get("content", [])
            else:
                raise IOError("file '{}' does not exist".format(self.__name))
        else:
            self.__read = True
            self._lines = file(self.__name, "r").read().split("\n")
        if self.__opts.get("strip_empty", True):
            self._lines = [_entry for _entry in self._lines if _entry.strip()]
        if self.__opts.get("strip_hash", True):
            self._lines = [_entry for _entry in self._lines if not _entry.strip().startswith("#")]

    def write(self, content, mode="w"):
        if type(content) == dict:
            file(self.__name, mode).write("\n".join(["{}={}".format(key, value) for key, value in content.iteritems()] + [""]))
        else:
            file(self.__name, mode).write("\n".join(content + [""]))

    @property
    def lines(self):
        if not self.__read:
            self._read_content()
        return self._lines

    @property
    def dict(self):
        if not self.__read:
            self._read_content()
        return {key.strip(): value.strip() for key, value in [_line.split("=", 1) for _line in self._lines if _line.strip().count("=")]}


def read_text_file(tf_name, ignore_hashes=False):
    tfr_name = os.path.normpath(tf_name)
    if not os.path.isfile(tfr_name):
        raise IOError("No file named '{}' found".format(tfr_name))
    else:
        lines = [sline for sline in [line.strip() for line in open(tfr_name, "r").read().split("\n")] if sline]
        if ignore_hashes:
            lines = [line for line in lines if not line.startswith("#")]
    return lines


def read_site_config_file(base_dir, cf_name):
    try:
        lines = read_text_file("%s/%s" % (base_dir, cf_name), True)
    except IOError:
        print "An IOError occured: %s" % (process_tools.get_except_info())
        sys.exit(1)
    else:
        return lines


def read_default_site_file(base_dir, cf_name):
    act_site = ""
    try:
        lines = read_text_file("%s/%s" % (base_dir, cf_name), True)
    except IOError:
        pass
    else:
        if lines:
            act_site = lines[0].strip()
    return act_site


def parse_site_config_file(base_dir, act_site, act_conf):
    slf_name = os.path.normpath("%s/lic_%s.src_config" % (base_dir, act_site))
    try:
        lines = read_text_file(slf_name)
    except IOError:
        print "An IOError occured (%s) while reading sit_config for site '%s', ignoring..." % (process_tools.get_except_info(), act_site)
    else:
        for key, value in [x for x in [y.split(None, 1) for y in lines] if len(x) == 2]:
            act_conf[key.upper()] = value
    return act_conf


def parse_license_lines(lines, act_site, **kwargs):
    new_dict = {}
    # simple license
    slic_re = re.compile("^lic_{}_(?P<name>\S+)\s+(?P<act_lic_server_setting>\S+)\s+(?P<attribute>\S+)\s+(?P<tot_num>\d+)\s*$".format(act_site))
    # compound license
    clic_re = re.compile("^clic_{}_(?P<name>\S+)\s+(?P<lic_operand>\S+)\s+(?P<attribute>\S+)\s+(?P<source_licenses>\S+)\s*$".format(act_site))
    for line in lines:
        if line.strip().startswith("#"):
            # is comment line, nevertheless parse the line
            comment = True
            line = line[1:].strip()
        else:
            comment = False
        simple_lic = slic_re.match(line)
        compound_lic = clic_re.match(line)
        if simple_lic:
            new_lic = sge_license(
                simple_lic.group("attribute"),
                license_server=simple_lic.group("act_lic_server_setting"),
                license_type="simple",
                ng_dict=kwargs.get("ng_dict", {}))
            new_lic.total_num = int(simple_lic.group("tot_num"))
        elif compound_lic:
            new_lic = sge_license(
                compound_lic.group("attribute"),
                license_type="compound",
                ng_dict=kwargs.get("ng_dict", {}))
            new_lic.set_compound_operand(compound_lic.group("lic_operand"))
            new_lic.set_source_licenses([part.strip() for part in compound_lic.group("source_licenses").split(",")])
        else:
            new_lic = None
        if new_lic:
            if not comment:
                new_lic.is_used = True
            if new_lic.name in new_dict:
                print("WARNING, license {} (attribute {}) already set".format(
                    new_lic.name,
                    new_lic.attribute,
                ))
            else:
                new_dict[new_lic.name] = new_lic
    return new_dict


def call_command(command, exit_on_fail=0, show_output=False):
    _stat, _out = process_tools.getstatusoutput(command)
    if _stat:
        print("Something went wrong while calling '{}' (code {:d}):".format(command, _stat))
        for _line in _out.split("\n"):
            print(" * {}".format(_line))
        if exit_on_fail:
            sys.exit(exit_on_fail)
    else:
        if show_output:
            print(
                "Output of '{}': {}".format(
                    command,
                    _out and "{}".format(logging_tools.get_plural("line", len(_out.split("\n")))) or "<no output>"
                )
            )
            for _line in _out.split("\n"):
                print(" - {}".format(_line))
    return _stat, _out
