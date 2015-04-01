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

import commands
import logging_tools
import os
import process_tools
import re
import sys

SITE_CONF_NAME = "lic_SITES.conf"
ACT_SITE_NAME = "actual_SITE"
NG_FILE = "/etc/sysconfig/licenses/node_grouping"

DEFAULT_CONFIG = {
    "LM_UTIL_COMMAND" : "lmutil",
    "LM_UTIL_PATH"    : "",
    "LICENSE_FILE"    : ""}

def read_ng_file(log_template):
    if os.path.isfile(NG_FILE):
        ng_lines = [line.strip() for line in file(NG_FILE, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
        ng_dict = dict([(key, re.compile(value)) for key, value in [line.split(None, 1) for line in ng_lines]])
    else:
        ng_dict = {}
    return ng_dict

class sge_license(object):
    def __init__(self, attribute, **kwargs):
        self.__name = attribute.lower()
        self.__attribute = attribute
        self.__license_type = kwargs.get("license_type", "simple")
        self.__num_lic_servers, self.__lic_servers = (0, [])
        if self.__license_type == "simple":
            lsp_parts = kwargs["license_server"].split(",")
            self.__num_lic_servers = len(lsp_parts)
            for lsp_part in lsp_parts:
                port, host = lsp_part.split("@")
                self.__lic_servers.append((int(port), host))
        self.set_total_num()
        self.set_used_num()
        self.set_is_used()
        self.__changed = False
        self.__ng_dict = kwargs.get("ng_dict", {})
        self.clean_hosts()
    def handle_node_grouping(self):
        self.__lic_sub_dict = dict([(ng_key, len([True for host in self.__hosts if ng_re.match(host)])) for ng_key, ng_re in self.__ng_dict.iteritems()])
    def get_hosts(self):
        return self.__hosts
    def clean_hosts(self):
        self.__hosts = []
    def add_host(self, host_name):
        self.__hosts.append(host_name)
    def get_license_type(self):
        return self.__license_type
    def set_changed(self):
        self.__changed = True
    def get_changed(self):
        c = self.__changed
        self.__changed = False
        return c
    def get_mvect_entries(self, mvect_entry):
        r_list = [
            mvect_entry(
                "lic.%s.used" % (self.get_name()),
                info="Licenses used for %s (%s)" % (self.get_name(), self.get_info()),
                default=0
                ),
            mvect_entry(
                "lic.%s.free" % (self.get_name()),
                info="Licenses free for %s (%s)" % (self.get_name(), self.get_info()),
                default=0
                ),
            ]
        r_list[0].update(self.get_used_num())
        r_list[1].update(self.get_free_num())
        for ng_key in self.__ng_dict.iterkeys():
            add_entry = mvect_entry(
                "lic.%s.%s.used" % (self.get_name(), ng_key),
                info="Licenses used for %s on %s (%s)" % (self.get_name(), ng_key, self.get_info()),
                default=0
                )
            add_entry.update(self.__lic_sub_dict[ng_key])
            r_list.append(add_entry)
        return r_list
    def get_info_lines(self):
        lic_lines = ["lic.%s.used:0:Licenses used for %s (%s):1:1:1" % (self.get_name(), self.get_name(), self.get_info()),
                     "lic.%s.free:0:Licenses free for %s (%s):1:1:1" % (self.get_name(), self.get_name(), self.get_info())]
        for ng_key in self.__ng_dict.iterkeys():
            lic_lines.extend([
                "lic.%s.%s.used:0:Licenses used for %s on %s (%s):1:1:1" % (self.get_name(), ng_key, self.get_name(), ng_key, self.get_info())])
        return lic_lines
    def get_value_lines(self):
        value_lines = ["lic.%s.used:i:%d" % (self.get_name(), self.get_used_num()),
                       "lic.%s.free:i:%d" % (self.get_name(), self.get_free_num())]
        for ng_key in self.__ng_dict.iterkeys():
            value_lines.extend(["lic.%s.%s.used:i:%d" % (self.get_name(), ng_key, self.__lic_sub_dict[ng_key])])
        return value_lines
    def get_info(self):
        if self.__license_type == "simple":
            return "simple via server %s" % (self.get_lic_server_spec())
        else:
            return "compound [%s %s]" % (self.__operand,
                                         ",".join(["%s (x%d)" % (key, self.__mult_dict[key]) for key in sorted(self.__source_licenses)]))
    def get_lic_server_spec(self):
        return ",".join(["%d@%s" % (port, host) for port, host in self.__lic_servers])
    def get_num_lic_servers(self):
        return self.__num_lic_servers
    def set_is_used(self, is_used=False):
        self.__is_used = is_used
    def get_is_used(self):
        return self.__is_used
    def get_name(self):
        return self.__name
    def get_attribute(self):
        return self.__attribute
    def set_total_num(self, total=0):
        self.__total = total
    def get_total_num(self):
        return self.__total
    def set_used_num(self, used=0):
        self.__used = used
    def get_used_num(self):
        return self.__used
    def get_free_num(self):
        return self.__total - self.__used
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
                new_total = sum([lic_dict[key].get_total_num() * self.__mult_dict[key] for key in found_keys])
                new_used = sum([lic_dict[key].get_used_num() * self.__mult_dict[key] for key in found_keys])
                if new_total != self.get_total_num():
                    log_lines.append(("total for %s changed from %d to %d" % (self.__name,
                                                                              self.get_total_num(),
                                                                              new_total),
                                      logging_tools.LOG_LEVEL_OK))
                    self.set_total_num(new_total)
                    self.set_changed()
                if new_used != self.get_used_num():
                    log_lines.append(("used for %s changed from %d to %d" % (self.__name,
                                                                             self.get_used_num(),
                                                                             new_used),
                                      logging_tools.LOG_LEVEL_OK))
                    self.set_used_num(new_used)
                    self.set_changed()
            elif self.__operand == "max":
                pass
        else:
            self.set_total_num()
            self.set_used_num()
        return log_lines

def get_site_license_file_name(base_dir, act_site):
    return os.path.normpath("%s/lic_%s.conf" % (base_dir, act_site))

def read_text_file(tf_name, ignore_hashes=False):
    tfr_name = os.path.normpath(tf_name)
    if not os.path.isfile(tfr_name):
        raise IOError, "No file named '%s' found" % (tfr_name)
    else:
        lines = [sline for sline in [line.strip() for line in open(tfr_name, "r").read().split("\n")] if sline]
        if ignore_hashes:
            lines = [line for line in lines if not line.startswith("#")]
    return lines

def read_site_config_file(base_dir, cf_name):
    try:
        lines = read_text_file("%s/%s" % (base_dir, cf_name), True)
    except IOError, what:
        print "An IOError occured: %s" % (process_tools.get_except_info())
        sys.exit(1)
    else:
        return lines

def read_default_site_file(base_dir, cf_name):
    act_site = ""
    try:
        lines = read_text_file("%s/%s" % (base_dir, cf_name), True)
    except IOError, what:
        pass
    else:
        if lines:
            act_site = lines[0].strip()
    return act_site

def read_site_license_file(base_dir, act_site):
    slf_name = get_site_license_file_name(base_dir, act_site)
    try:
        lines = read_text_file(slf_name)
    except IOError, what:
        print "An IOError occured accesing %s (%s), ignoring..." % (slf_name,
                                                                    process_tools.get_except_info())
        lines = []
    return lines

def parse_site_config_file(base_dir, act_site, act_conf):
    slf_name = os.path.normpath("%s/lic_%s.src_config" % (base_dir, act_site))
    try:
        lines = read_text_file(slf_name)
    except IOError, what:
        print "An IOError occured (%s) while reading sit_config for site '%s', ignoring..." % (process_tools.get_except_info(), act_site)
    else:
        for key, value in [x for x in [y.split(None, 1) for y in lines] if len(x) == 2]:
            act_conf[key.upper()] = value
    return act_conf

def parse_license_lines(lines, act_site, **kwargs):
    new_dict = {}
    # simple license
    slic_re = re.compile("^lic_%s_(?P<name>\S+)\s+(?P<act_lic_server_setting>\S+)\s+(?P<attribute>\S+)\s+(?P<tot_num>\d+)\s*$" % (act_site))
    # compound license
    clic_re = re.compile("^clic_%s_(?P<name>\S+)\s+(?P<lic_operand>\S+)\s+(?P<attribute>\S+)\s+(?P<source_licenses>\S+)\s*$" % (act_site))
    for line in lines:
        if line.startswith("#"):
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
            new_lic.set_total_num(int(simple_lic.group("tot_num")))
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
                new_lic.set_is_used(True)
            if new_dict.has_key(new_lic.get_name()):
                print "WARNING, license %s (attribute %s) already set !" % (new_lic.get_name(),
                                                                            new_lic.get_attribute())
            else:
                new_dict[new_lic.get_name()] = new_lic
    return new_dict

def call_command(command, exit_on_fail=0, show_output=False):
    stat, out = commands.getstatusoutput(command)
    if stat:
        print "Something went wrong while calling '%s' (code %d) : " % (command, stat)
        for line in out.split("\n"):
            print " * %s" % (line)
        if exit_on_fail:
            sys.exit(exit_on_fail)
    else:
        if show_output:
            print "Output of '%s': %s" % (command, out and "%s" % (logging_tools.get_plural("line", len(out.split("\n")))) or "<no output>")
            for line in out.split("\n"):
                print " - %s" % (line)
    return stat, out

