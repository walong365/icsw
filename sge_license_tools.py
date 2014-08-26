#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of init-license-tools
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

from lxml import etree
from lxml.builder import E
import datetime
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

EXPIRY_DT = "%d-%b-%Y"


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
    for _bn in ["qconf", "qstat"]:
        _bin = "{}/bin/{}/{}".format(_sge_dict["SGE_ROOT"], sge_arch, _bn)
        if not os.path.isfile(_bin):
            print("No {} command found under {}".format(_bn, _sge_dict["SGE_ROOT"]))
            sys.exit(1)
        _sge_dict["{}_BIN".format(_bn.upper())] = _bin
    _sge_dict["SGE_ARCH"] = sge_arch
    return _sge_dict


def get_sge_log_line(sge_dict):
    return ", ".join(["{} is {}".format(_key, sge_dict[_key]) for _key in sorted(sge_dict.iterkeys())])


def get_sge_complexes(sge_dict):
    _complex_stat, complex_out = call_command("{} -sc".format(sge_dict["QCONF_BIN"]), 1)
    defined_complexes = [_line for _line in complex_out.split("\n") if _line.strip() and not _line.strip().startswith("#")]
    return defined_complexes, [_line.split()[0] for _line in defined_complexes]


class sge_license(object):
    def __init__(self, attribute, **kwargs):
        # default values
        self.__lic_servers = []
        # just for bookkeeping
        self.expires = None
        self.site = kwargs.get("site", "unknown")
        self.used_num = 0
        if etree.iselement(attribute):
            # init from xml
            _xml = attribute
            # print etree.tostring(_xml, pretty_print=True)
            if _xml.get("source", "file") == "server":
                _version = _xml.find("version")
                # xml from license check
                self.name = _xml.get("name")
                self.attribute = _xml.get("name")
                self.license_type = "simple"
                # do not set license servers
                self.total_num = int(_xml.get("issued", "0"))
                self.reserved_num = int(_xml.get("reserved", "0"))
                # show in frontend / command tools
                self.show = True
                # is used: set for SGE
                self.is_used = False
                # limit usage (reserve this number of licenses for external usage)
                self.limit_num = 0
                self.added = "unknown"
                if _version is not None and _version.get("expiry", ""):
                    self.expires = datetime.datetime.strptime(_version.get("expiry"), EXPIRY_DT)
            else:
                self.name = _xml.get("name")
                self.attribute = _xml.get("attribute")
                self.license_type = _xml.get("type")
                if self.license_type == "simple":
                    for _lic_srv in _xml.findall("license_servers/license_server"):
                        self.__lic_servers.append((int(_lic_srv.get("port")), _lic_srv.get("address")))
                else:
                    self.__eval_str = _xml.get("eval_str")
                self.total_num = int(_xml.get("total"))
                self.reserved_num = int(_xml.get("reserved"))
                self.limit_num = int(_xml.get("limit", "0"))
                self.is_used = True if int(_xml.get("in_use", "0")) else False
                self.show = True if int(_xml.get("show", "1")) else False
                self.added = _xml.get("added", "unknown")
                self.expires = _xml.get("expires", "")
                if self.expires:
                    self.expires = datetime.datetime.strptime(self.expires, EXPIRY_DT)
                self.used_num = 0
        else:
            self.is_used = False
            self.total_num = 0
            self.reserved_num = 0
            self.limit_num = 0
            self.show = True
            self.name = attribute.lower()
            self.attribute = attribute
            self.license_type = kwargs.get("license_type", "simple")
            if self.license_type == "simple":
                lsp_parts = kwargs["license_server"].split(",")
                for lsp_part in lsp_parts:
                    port, host = lsp_part.split("@")
                    self.__lic_servers.append((int(port), host))
            else:
                self.__eval_str = kwargs.get("eval_str", "1")
            self.added = "unknown"

    def update(self, other):
        if isinstance(other, sge_license):
            if other.expires:
                self.expires = other.expires
            self.total_num = other.total_num
            self.reserved_num = other.reserved_num
        else:
            # xml input from server
            self.total_num = int(other.get("issued", "0"))
            self.reserved_num = int(other.get("reserved", "0"))

    @property
    def full_name(self):
        return "{}_{}_{}".format(
            "lic" if self.license_type == "simple" else "clic",
            self.site,
            self.name,
        )

    def reset(self):
        # reset usage counters
        # used from server
        self.used_num = 0

    def get_xml(self):
        base_lic = E.license(
            full_name=self.full_name,
            name=self.name,
            attribute=self.attribute,
            type=self.license_type,
            total="{:d}".format(self.total_num),
            reserved="{:d}".format(self.reserved_num),
            show="1" if self.show else "0",
            limit="{:d}".format(self.limit_num),
            added=self.added,
            in_use="1" if self.is_used else "0",
        )
        if self.license_type == "simple":
            base_lic.attrib.update(
                {
                    "expires": "" if not self.expires else self.expires.strftime(EXPIRY_DT)
                }
            )
            base_lic.append(
                E.license_servers(
                    *[E.license_server("{:d}@{}".format(_srv[0], _srv[1]), address=_srv[1], port="{:d}".format(_srv[0])) for _srv in self.__lic_servers]
                )
            )

        else:
            base_lic.attrib.update(
                {
                    "eval_str": self.__eval_str
                }
            )
            pass
        return base_lic

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
        return r_list

    def get_info_line(self):
        return [
            logging_tools.form_entry(self.name, header="name"),
            logging_tools.form_entry("yes" if self.is_used else "no", header="for SGE"),
            logging_tools.form_entry("yes" if self.show else "no", header="show"),
            logging_tools.form_entry_right(self.total_num, header="total"),
            logging_tools.form_entry_right(self.reserved_num, header="reserved"),
            logging_tools.form_entry_right(self.limit_num, header="limit"),
            logging_tools.form_entry_right(self.used_num, header="used"),
            logging_tools.form_entry_right(0, header="SGE"),
            logging_tools.form_entry_right(0, header="external"),
        ]

    def _get_info(self):
        if self.license_type == "simple":
            return "simple via {}".format(logging_tools.get_plural("server", len(self.__lic_servers)))
        else:
            return "complex [{}]".format(self.__eval_str)
    info = property(_get_info)

    def _get_free_num(self):
        return self.__total - self.__used
    free_num = property(_get_free_num)

    def get_port(self, idx=0):
        return self.__lic_servers[idx][0]

    def get_host(self, idx=0):
        return self.__lic_servers[idx][1]

    def set_eval_str(self, eval_str):
        self.__eval_str = eval_str

    def handle_complex(self, lic_dict):
        log_lines = []
        _simple_keys = [_key for _key, _value in lic_dict.iteritems() if _value.license_type == "simple"]
        for _type in ["total", "used", "limit"]:
            t_attr = "{}_num".format(_type)
            _glob = {_key: getattr(lic_dict[_key], t_attr) for _key in _simple_keys}
            try:
                _result = eval(self.__eval_str, _glob)
            except:
                log_lines.append(
                    (
                        "error in eval() for {}: {}".format(
                            self.name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL,
                    )
                )
                setattr(self, t_attr, 0)
            else:
                if _result != getattr(self, t_attr):
                    log_lines.append(
                        (
                            "{} for {} changed from {:d} to {:d}".format(
                                _type,
                                self.name,
                                getattr(self, t_attr),
                                _result
                            ),
                            logging_tools.LOG_LEVEL_OK
                        )
                    )
                    setattr(self, t_attr, _result)
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
        elif type(content) in [str, unicode]:
            file(self.__name, mode).write(content)
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


def build_license_xml(act_site, in_dict):
    lic_xml = E.licenses(site=act_site)
    for _key, _value in in_dict.iteritems():
        lic_xml.append(_value.get_xml())
    return lic_xml


def handle_complex_licenses(actual_licenses):
    _lines = []
    comp_keys = [_key for _key, _value in actual_licenses.iteritems() if _value.is_used and _value.license_type == "complex"]
    for comp_key in sorted(comp_keys):
        _lines.extend(actual_licenses[comp_key].handle_complex(actual_licenses))
    return _lines


def parse_license_lines(lines, act_site, **kwargs):
    new_dict = {}
    # simple license
    slic_re = re.compile("^lic_{}_(?P<name>\S+)\s+(?P<act_lic_server_setting>\S+)\s+(?P<attribute>\S+)\s+(?P<tot_num>\d+)\s*$".format(act_site))
    # complex license
    clic_re = re.compile("^clic_{}_(?P<name>\S+)\s+(?P<attribute>\S+)\s+(?P<eval_str>\S+)\s*$".format(act_site))
    if lines and lines[0].startswith("<"):
        # XML format
        _tree = etree.fromstring("\n".join(lines))
        _site = _tree.attrib["site"]
        # todo, compare _site with act_site
        # print _site, act_site
        new_dict = {}
        for _lic_xml in _tree.findall("license"):
            new_lic = sge_license(_lic_xml, site=_site)
            new_dict[new_lic.name] = new_lic
    else:
        # old format, convert
        for line in lines:
            if line.strip().startswith("#"):
                # is comment line, nevertheless parse the line
                comment = True
                line = line[1:].strip()
            else:
                comment = False
            simple_lic = slic_re.match(line)
            complex_lic = clic_re.match(line)
            if simple_lic:
                new_lic = sge_license(
                    simple_lic.group("attribute"),
                    license_server=simple_lic.group("act_lic_server_setting"),
                    license_type="simple",
                    ng_dict=kwargs.get("ng_dict", {}),
                    site=act_site,
                )
                new_lic.total_num = int(simple_lic.group("tot_num"))
            elif complex_lic:
                new_lic = sge_license(
                    complex_lic.group("attribute"),
                    license_type="complex",
                    ng_dict=kwargs.get("ng_dict", {}),
                    site=act_site,
                    eval_str=complex_lic.group("eval_str")
                )
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
        try:
            file(get_site_license_file_name(BASE_DIR, act_site), "w").write(
                etree.tostring(
                    build_license_xml(
                        act_site,
                        new_dict,
                    ),
                    pretty_print=True
                )
            )
        except:
            pass
    return new_dict


def update_usage(lic_dict, srv_xml):
    [_value.reset() for _value in lic_dict.itervalues()]
    for cur_lic in srv_xml.xpath(".//license[@name]", smart_strings=False):
        name = cur_lic.attrib["name"]
        act_lic = lic_dict.get(name, None)
        if act_lic and act_lic.is_used:
            act_lic.update(cur_lic)
            act_lic.used_num = int(cur_lic.get("used", "0"))


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
