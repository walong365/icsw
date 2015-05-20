#!/usr/bin/python-init -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
import datetime
import os
import re
import subprocess
import sys
import time

from lxml.builder import E
from initat.tools import logging_tools
from initat.tools import process_tools


SITE_CONF_NAME = "lic_SITES.conf"
ACT_SITE_NAME = "actual_SITE"
DEFAULT_SITE = "local"
BASE_DIR = "/etc/sysconfig/licenses"

DEFAULT_CONFIG = {
    "LMUTIL_PATH": "/opt/cluster/bin/lmutil",
    "LICENSE_FILE": ""
}

EXPIRY_DT = "%d-%b-%Y"


# dummy logger
def _log(log_com, what, log_level=logging_tools.LOG_LEVEL_OK):
    if log_com:
        log_com(what, log_level)
    else:
        print(what)


def get_sge_environment(log_com=None):
    _sge_dict = {}
    for _key in ["sge_root", "sge_cell"]:
        if _key.upper() not in os.environ:
            _file = os.path.join("/etc", _key)
            if os.path.isfile(_file):
                _sge_dict[_key.upper()] = file(_file, "r").read().strip()
            else:
                _log(log_com, "Error, no {} environment variable set or defined in {}".format(_key.upper(), _file))
        else:
            _sge_dict[_key.upper()] = os.environ[_key.upper()]
    arch_util = "{}/util/arch".format(_sge_dict["SGE_ROOT"])
    if not os.path.isfile(arch_util):
        _log(log_com, "No arch-utility found in {}/util".format(_sge_dict["SGE_ROOT"]))
        if log_com is None:
            sys.exit(1)
    _sge_stat, sge_arch = call_command(arch_util, log_com=log_com)
    sge_arch = sge_arch.strip()
    for _bn in ["qconf", "qstat"]:
        _bin = "{}/bin/{}/{}".format(_sge_dict["SGE_ROOT"], sge_arch, _bn)
        if not os.path.isfile(_bin):
            _log(log_com, "No {} command found under {}".format(_bn, _sge_dict["SGE_ROOT"]))
            if log_com is None:
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
        self.used = 0
        if etree.iselement(attribute):  # @UndefinedVariable
            # init from xml
            _xml = attribute
            # print etree.tostring(_xml, pretty_print=True)
            if _xml.get("source", "file") == "server":
                # source from license fetch via lmutil lmstat
                _version = _xml.find("version")
                # xml from license check
                self.name = _xml.get("name")
                self.attribute = _xml.get("name")
                self.license_type = "simple"
                # do not set license servers
                self.total = int(_xml.get("issued", "0"))
                self.reserved = int(_xml.get("reserved", "0"))
                # show in frontend / command tools
                self.show = True
                # is used: set for SGE
                self.is_used = False
                # limit usage (reserve this number of licenses for external usage)
                self.limit = 0
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
                    self.__match_str = _xml.get("match_str", "")
                else:
                    self.__eval_str = _xml.get("eval_str")
                self.total = int(_xml.get("total"))
                self.reserved = int(_xml.get("reserved"))
                self.limit = int(_xml.get("limit", "0"))
                self.is_used = True if int(_xml.get("in_use", "0")) else False
                self.show = True if int(_xml.get("show", "1")) else False
                self.added = _xml.get("added", "unknown")
                self.expires = _xml.get("expires", "")
                if self.expires:
                    self.expires = datetime.datetime.strptime(self.expires, EXPIRY_DT)
                self.used = 0
        else:
            self.is_used = False
            self.total = 0
            self.reserved = 0
            self.limit = 0
            self.show = True
            self.name = attribute.lower()
            self.attribute = attribute
            self.license_type = kwargs.get("license_type", "simple")
            if self.license_type == "simple":
                lsp_parts = kwargs["license_server"].split(",")
                for lsp_part in lsp_parts:
                    port, host = lsp_part.split("@")
                    self.__lic_servers.append((int(port), host))
                    self.__match_str = kwargs.get("match_str", "")
            else:
                self.__eval_str = kwargs.get("eval_str", "1")
            self.added = "unknown"

    def update(self, other):
        if isinstance(other, sge_license):
            if other.expires:
                self.expires = other.expires
            self.total = other.total
            self.reserved = other.reserved
        else:
            # xml input from server
            self.total = int(other.get("issued", "0"))
            self.reserved = int(other.get("reserved", "0"))

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
        self.used = 0
        # used from sge
        self.sge_used = 0
        # via qstat
        self.sge_used_requested = 0
        # via match from lmutil / lmstat
        self.sge_used_issued = 0
        self.external_used = 0

    def num_sge_specific(self, lic_xml):
        _num_sge = 0
        if self.__match_str:
            match_re = re.compile(self.__match_str)
            for _usage in lic_xml.findall(".//usage"):
                if match_re.match(_usage.attrib["client_short"]):
                    _num_sge += int(_usage.get("num", "0"))
        return _num_sge

    def get_sge_available(self):
        # return number of available licenses for sge
        return self.total - max(self.external_used, self.limit)

    def get_xml(self, with_usage=False):
        base_lic = E.license(
            full_name=self.full_name,
            name=self.name,
            attribute=self.attribute,
            type=self.license_type,
            total="{:d}".format(self.total),
            reserved="{:d}".format(self.reserved),
            show="1" if self.show else "0",
            limit="{:d}".format(self.limit),
            added=self.added,
            in_use="1" if self.is_used else "0",
        )
        if with_usage:
            base_lic.attrib.update(
                {
                    "used": "{:d}".format(self.used),
                    "free": "{:d}".format(self.free),
                    "sge_used": "{:d}".format(self.sge_used),
                    "sge_used_requested": "{:d}".format(self.sge_used_requested),
                    "sge_used_issued": "{:d}".format(self.sge_used_issued),
                    "external_used": "{:d}".format(self.external_used),
                }
            )
        if self.license_type == "simple":
            base_lic.attrib.update(
                {
                    "expires": "" if not self.expires else self.expires.strftime(EXPIRY_DT),
                    "match_str": self.__match_str,
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
                    "eval_str": self.__eval_str,
                }
            )
            pass
        return base_lic

    def get_mvect_entries(self, mvect_entry):
        r_list = [
            mvect_entry(
                "lic.{}.used".format(self.name),
                info="used {}".format(self.info),
                default=0
            ),
            mvect_entry(
                "lic.{}.free".format(self.name),
                info="free {}".format(self.info),
                default=0
            ),
            mvect_entry(
                "lic.{}.total".format(self.name),
                info="total {}".format(self.info),
                default=0
            ),
            mvect_entry(
                "lic.{}.used_rms".format(self.name),
                info="cluster used {}".format(self.info),
                default=0
            ),
            mvect_entry(
                "lic.{}.used_external".format(self.name),
                info="external used {}".format(self.info),
                default=0
            ),
        ]
        r_list[0].update(self.used)
        r_list[1].update(self.free)
        r_list[2].update(self.total)
        r_list[3].update(self.sge_used)
        r_list[4].update(self.external_used)
        return r_list

    def get_info_line(self):
        return [
            logging_tools.form_entry(self.name, header="name"),
            logging_tools.form_entry(self.license_type, header="type"),
            logging_tools.form_entry("yes" if self.is_used else "no", header="for SGE"),
            logging_tools.form_entry("yes" if self.show else "no", header="show"),
            logging_tools.form_entry_right(self.total, header="total"),
            logging_tools.form_entry_right(self.reserved, header="reserved"),
            logging_tools.form_entry_right(self.limit, header="limit"),
            logging_tools.form_entry_right(self.used, header="used"),
            logging_tools.form_entry_right(self.total - self.limit, header="avail"),
            logging_tools.form_entry_right(self.sge_used, header="cluster"),
            logging_tools.form_entry_right(self.sge_used_requested, header="cluster(requested)"),
            logging_tools.form_entry_right(self.sge_used_issued, header="cluster(issued)"),
            logging_tools.form_entry_right(self.external_used, header="external"),
            logging_tools.form_entry_right(self.free, header="free"),
            logging_tools.form_entry(self.expires.strftime(EXPIRY_DT) if self.expires else "---", header="expires"),
        ]

    def _get_info(self):
        if self.license_type == "simple":
            return "{}, simple via {}".format(self.name, logging_tools.get_plural("server", len(self.__lic_servers)))
        else:
            return "{}, complex [{}]".format(self.name, self.__eval_str)
    info = property(_get_info)

    def _get_free(self):
        return self.total - self.used
    free = property(_get_free)

    def get_port(self, idx=0):
        return self.__lic_servers[idx][0]

    def get_host(self, idx=0):
        return self.__lic_servers[idx][1]

    def set_eval_str(self, eval_str):
        self.__eval_str = eval_str

    def handle_complex(self, lic_dict, prev_dict=None):
        prev_dict = prev_dict or {}
        log_lines = []
        _simple_keys = [_key for _key, _value in lic_dict.iteritems() if _value.license_type == "simple"]
        # return log_lines
        for _type in ["total", "used", "limit", "sge_used_requested", "sge_used_issued"]:
            # if self.license_type == "complex" and _type in ["used", "limit"]:
            #    continue
            t_attr = "{}".format(_type)
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
                if _type == "used" and prev_dict.get(self.name, _result) != _result:
                    log_lines.append(
                        (
                            "{} for {} changed from {:d} to {:d}".format(
                                _type,
                                self.name,
                                prev_dict[self.name],
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


def handle_license_policy(base_dir, flag=None):
    _hlp_fn = os.path.join(base_dir, ".license_policy")
    if flag is not None:
        # flag is given, write
        # - 1 to file if rms-server sets the complex_values of the global execution host or
        # - 0 if the system relies on the loadsensor
        file(_hlp_fn, "w").write("1" if flag else "0")
    else:
        flag = True if int(file(_hlp_fn, "r").read().strip()) else False
    return flag


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
        elif isinstance(content, basestring):
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
        _tree = etree.fromstring("\n".join(lines))  # @UndefinedVariable
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
                new_lic.total = int(simple_lic.group("tot_num"))
            elif complex_lic:
                new_lic = sge_license(
                    complex_lic.group("attribute"),
                    license_type="complex",
                    ng_dict=kwargs.get("ng_dict", {}),
                    site=act_site,
                    eval_str=complex_lic.group("eval_str"),
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


def set_sge_used(lic_dict, used_dict):
    for _key, _lic in lic_dict.iteritems():
        if _key in used_dict:
            _lic.sge_used_requested += used_dict[_key]


def parse_sge_used(sge_dict, log_com=None):
    act_com = "{} -ne -r -xml".format(sge_dict["QSTAT_BIN"])
    c_stat, out = call_command(act_com, log_com=log_com)
    _used = {}
    if not c_stat:
        _tree = etree.fromstring(out)  # @UndefinedVariable
        for _job in _tree.findall(".//job_list[@state='running']"):
            _slots_el = _job.find("slots")
            if _slots_el is not None:
                _slots = int(_slots_el.text)
            else:
                _slots = 1
            _req_list = []
            for _req in _job.findall("hard_request"):
                try:
                    _val = int(float(_req.text) * _slots + 0.5)
                except:
                    # TODO: log exception
                    pass
                else:
                    _used.setdefault(_req.attrib["name"], []).append(_val)
    _used = {_key: sum(_value) for _key, _value in _used.iteritems()}
    return _used


def update_usage(lic_dict, srv_xml):
    [_value.reset() for _value in lic_dict.itervalues()]
    for cur_lic in srv_xml.xpath(".//license[@name]", smart_strings=False):
        name = cur_lic.attrib["name"]
        act_lic = lic_dict.get(name, None)
        if act_lic and act_lic.is_used:
            act_lic.update(cur_lic)
            act_lic.used = int(cur_lic.get("used", "0")) - int(cur_lic.get("reserved", "0"))
            if act_lic.license_type == "simple":
                # decide if this license is external or sge local
                _num_sge = act_lic.num_sge_specific(cur_lic)
                act_lic.sge_used_issued += _num_sge
                # now handled in calculate_usage
                # act_lic.sge_used += abs(act_lic.sge_used_requested - act_lic.sge_used_issued)
                act_lic.external_used += act_lic.used - _num_sge
            else:
                act_lic.external_used += act_lic.used


def calculate_usage(actual_licenses):
    # set external_used / used according to the varous sge_used* fields
    for act_lic in actual_licenses.itervalues():
        if act_lic.is_used:
            act_lic.sge_used = max(act_lic.sge_used_issued, act_lic.sge_used_requested)
            if act_lic.license_type == "simple":
                pass
            else:
                act_lic.external = act_lic.used - act_lic.sge_used


def call_command(command, exit_on_fail=0, show_output=False, log_com=None):
    _stat, _out = process_tools.getstatusoutput(command)
    if _stat:
        _log(log_com, "Something went wrong while calling '{}' (code {:d}):".format(command, _stat), logging_tools.LOG_LEVEL_ERROR)
        for _line in _out.split("\n"):
            _log(log_com, " * {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
        if exit_on_fail:
            sys.exit(exit_on_fail)
    else:
        if show_output:
            _log(
                log_com,
                "Output of '{}': {}".format(
                    command,
                    _out and "{}".format(logging_tools.get_plural("line", len(_out.split("\n")))) or "<no output>"
                )
            )
            for _line in _out.split("\n"):
                _log(
                    log_com,
                    " - {}".format(_line)
                )
    return _stat, _out


class license_check(object):
    def __init__(self, **kwargs):
        self.log_com = kwargs.get("log_com", None)
        self.verbose = kwargs.get("verbose", True)
        self.lmutil_path = kwargs.get("lmutil_path", "/opt/cluster/bin/lmutil")
        if "license_file" in kwargs:
            _lic_file = kwargs["license_file"]
            if _lic_file.count("@"):
                _port, self.server_addr = _lic_file.split("@")
                self.server_port = int(_port)
            else:
                print("unknown license_file '{}'".format(_lic_file))
                sys.exit(-1)
        else:
            self.server_addr = kwargs.get("server", "localhost")
            if self.server_addr.startswith("/"):
                self.server_addr = file(self.server_addr, "r").read().strip().split()[0]
            self.server_port = kwargs.get("port", "1055")
            if type(self.server_port) not in [int, long]:
                if self.server_port.startswith("/"):
                    self.server_port = file(self.server_port, "r").read().strip().split()[0]
                self.server_port = int(self.server_port)
        self.log("license server {} (port {:d})".format(self.server_addr, self.server_port))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if log_level == logging_tools.LOG_LEVEL_OK and not self.verbose:
            return
        what = u"[lc] {}".format(what)
        if self.log_com:
            self.log_com(what, log_level)
        else:
            logging_tools.my_syslog("[{:d}] {}".format(log_level, what))

    def call_external(self, com_line):
        popen = subprocess.Popen(com_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ret_code = popen.wait()
        return ret_code, popen.stdout.read()

    def _strip_string(self, in_str):
        if in_str.endswith(","):
            return in_str[:-1]
        else:
            return in_str

    def check(self, license_names=None):
        s_time = time.time()
        self.log("starting check")
        ret_struct = E.license_info(
            server_address=self.server_addr,
            server_port="{:d}".format(self.server_port)
        )
        if not os.path.isfile(self.lmutil_path):
            _error_str = "LMUTIL_PATH '{}' is not a file".format(self.lmutil_path)
            self.log(_error_str, logging_tools.LOG_LEVEL_ERROR)
            ret_struct.attrib.update({
                "state": "{:d}".format(logging_tools.LOG_LEVEL_ERROR),
                "info": "{}".format(_error_str)}
            )
            line_num = 0
        else:

            ext_code, ext_lines = self.call_external(
                "{} lmstat -a -c {:d}@{}".format(
                    self.lmutil_path,
                    self.server_port,
                    self.server_addr
                )
            )
            if ext_code:
                ret_struct.attrib.update({
                    "state": "{:d}".format(logging_tools.LOG_LEVEL_ERROR),
                    "info": "{}".format(ext_lines)}
                )
                line_num = 0
            else:
                ret_struct.attrib.update(
                    {
                        "state": "{:d}".format(logging_tools.LOG_LEVEL_OK),
                        "info": "call successfull"
                    }
                )
                line_num = self._interpret_result(ret_struct, ext_lines, license_names)
        e_time = time.time()
        ret_struct.attrib["run_time"] = "{:.3f}".format(e_time - s_time)
        self.log(
            "done, {:d} lines in {}".format(
                line_num,
                logging_tools.get_diff_time_str(e_time - s_time)
            )
        )
        return ret_struct

    def _interpret_result(self, ret_struct, ext_lines, license_names):
        ret_struct.append(E.license_servers())
        ret_struct.append(E.licenses())
        found_server = set()
        cur_lic, cur_srv = (None, None)
        # populate structure
        for line_num, line in enumerate(ext_lines.split("\n")):
            if not line.strip():
                continue
            lline = line.lower()
            lparts = lline.strip().split()
            # print lline  # , lparts
            if lline.count("license server status"):
                server_info = lparts[-1]
                server_port, server_addr = server_info.split("@")
                found_server.add(server_addr)
                cur_srv = E.server(info=server_info, address=server_addr, port=server_port)
                ret_struct.find("license_servers").append(cur_srv)
            if cur_srv is not None:
                if lline.count("license file"):
                    cur_srv.append(E.license_file(" ".join(lparts[4:])))
            if lline.strip().startswith("users of"):
                cur_srv = None
                cur_lic_version = None
                lic_stat = lparts[3].strip("(:)")
                if lic_stat == "error":
                    pass
                else:
                    _lic_name = lparts[2][:-1]
                    if lparts[3] == "cannot":
                        # error reading, ignore
                        pass
                    else:
                        if license_names is None or _lic_name in license_names:
                            cur_lic = E.license(
                                name=_lic_name,
                                issued=lparts[5],
                                used=lparts[10],
                                reserved="0",
                                free="{:d}".format(int(lparts[5]) - int(lparts[10])),
                                source="server",
                            )
                            ret_struct.find("licenses").append(cur_lic)
            if cur_lic is not None:
                if "\"{}\"".format(cur_lic.attrib["name"]) == lparts[0]:
                    cur_lic_version = E.version(
                        version=self._strip_string(lparts[1]),
                        # vendor=lparts[-1],
                        floating="false",
                    )
                    if "vendor:" in lparts and "expiry:" in lparts:
                        _v_idx = lparts.index("vendor:")
                        _e_idx = lparts.index("expiry:")
                        _exp = lparts[_e_idx + 1]
                        if _exp not in ["1-jan-0"]:
                            cur_lic_version.attrib["expiry"] = datetime.datetime.strptime(_exp, "%d-%b-%Y").strftime(EXPIRY_DT)
                        cur_lic_version.attrib["vendor"] = self._strip_string(lparts[_v_idx + 1])
                    else:
                        cur_lic_version.attrib["vendor"] = self._strip_string(lparts[-1])
                        cur_lic_version.attrib["expiry"] = ""
                    cur_lic.append(cur_lic_version)
                else:
                    if cur_lic_version is not None:
                        self._feed_license_version(cur_lic, cur_lic_version, lparts)
        return line_num

    def _feed_license_version(self, cur_lic, cur_lic_version, lparts):
        cur_year = datetime.datetime.now().year
        if lparts[0] == "floating":
            cur_lic_version.attrib["floating"] = "true"
        elif lparts[1].count("reservation"):
            if cur_lic_version.find("reservations") is None:
                cur_lic_version.append(E.reservations())
            cur_lic_version.find("reservations").append(E.reservation(
                num=lparts[0],
                target=" ".join(lparts[3:])
            ))
            cur_lic.attrib["reserved"] = "{:d}".format(int(cur_lic.attrib["reserved"]) + int(lparts[0]))
        else:
            if cur_lic_version.find("usages") is None:
                cur_lic_version.append(E.usages())
            # add usage
            if lparts[-1].count("license"):
                num_lics = int(lparts[-2])
                lparts.pop(-1)
                lparts.pop(-1)
                lparts[-1] = lparts[-1][:-1]
            else:
                num_lics = 1
            start_data = " ".join(lparts[7:])
            # remove linger info (if present)
            start_data = (start_data.split("(")[0]).strip()
            co_datetime = datetime.datetime.strptime(
                "{:d} {}".format(
                    cur_year,
                    start_data.title()
                ), "%Y %a %m/%d %H:%M"
            )
            cur_lic_version.find("usages").append(
                E.usage(
                    num="{:d}".format(num_lics),
                    user=lparts[0],
                    client_long=lparts[1],
                    client_short=lparts[2].split(".")[0],
                    client_version=lparts[3][1:-1],
                    checkout_time="{:.2f}".format(time.mktime(co_datetime.timetuple())),
                )
            )


class ExternalLicenses(object):
    def __init__(self, act_base, act_site, log_com, **kwargs):
        self.__verbose = kwargs.get("verbose", False)
        self.__log_com = log_com
        self.__base = act_base
        self.__site = act_site
        self.__lic_file_name = get_site_license_file_name(self.__base, self.__site)
        self.__conf = text_file(
            get_site_config_file_name(self.__base, self.__site),
            content=DEFAULT_CONFIG,
            create=True,
        ).dict
        self.__sge_dict = get_sge_environment(log_com=self.log)
        if self.__verbose:
            self.log("init ExternalLicenses object with site '{}' in {}".format(self.__site, self.__base))
            self.log(get_sge_log_line(self.__sge_dict))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[el] {}".format(what), log_level)

    def read(self):
        self.__license_dict = parse_license_lines(
            text_file(
                self.__lic_file_name,
                ignore_missing=True,
                strip_empty=False,
                strip_hash=False,
            ).lines,
            self.__site,
        )

    def feed_xml_result(self, srv_result):
        # srv_result is an XML snippet
        update_usage(self.__license_dict, srv_result)
        set_sge_used(self.__license_dict, parse_sge_used(self.__sge_dict, log_com=self.log))
        for log_line, log_level in handle_complex_licenses(self.__license_dict):
            if log_level > logging_tools.LOG_LEVEL_WARN:
                self.log(log_line, log_level)
        calculate_usage(self.__license_dict)

    @property
    def config(self):
        # return basic path config (LMUTIL_PATH)
        return self.__conf

    @property
    def licenses(self):
        return self.__license_dict
