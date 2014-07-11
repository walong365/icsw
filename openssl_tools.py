#!/usr/bin/python -Ot
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" tools for openssl """

import commands
import datetime
import logging_tools
import os
import process_tools
import shutil
import tempfile
from collections import OrderedDict

SSL_DIR = "/opt/cluster/share/openssl"
CA_DIR = os.path.join(SSL_DIR, "CAs")
SSL_CNF = os.path.join(SSL_DIR, "openssl.cnf")

__all__ = ["openssl_config_mixin", "ca"]

def build_subj(sub_dict):
    return "/{}/".format("/".join(["{}={}".format(_key, _value.replace(" ", r"\ ")) for _key, _value in sub_dict.iteritems() if _key not in ["days"]]))

class openssl_config(object):
    def __init__(self, name=SSL_CNF):
        # lines without part, form is (key, value)
        self._parts = []
        self._pdicts = {}
        _part = ""
        self._parts.append(_part)
        _lines = self._pdicts.setdefault(_part, OrderedDict())
        for _line in file(name, "r"):
            _line = _line.split("#")[0].strip()
            if not _line:
                continue
            if _line.startswith("["):
                _part = _line.split("[", 1)[1].strip().split("]")[0].strip()
                if _part not in self._parts:
                    self._parts.append(_part)
                _lines = self._pdicts.setdefault(_part, OrderedDict())
            else:
                key, value = _line.split("=", 1)
                _lines[key.strip()] = value.strip()
    def write(self, name=SSL_CNF):
        _lines = []
        for _part in self._parts:
            if _part:
                _lines.append("[ {} ]".format(_part))
            for key, value in self._pdicts[_part].iteritems():
                _lines.append("{} = {}".format(key, value))
        file(name, "w").write("\n".join(_lines))
    def get(self, part, key, default=None, expand=False):
        if key in self._pdicts[part]:
            _val = self._pdicts[part][key]
            if expand:
                _val = _val.replace("$dir", self._pdicts[part]["dir"])
            return _val
        else:
            return default
    def set(self, part, key, value=None):
        part = part or ""
        if type(key) == list:
            kv_list = key
        else:
            kv_list = [(key, value)]
        _lines = self._pdicts.get(part, OrderedDict())
        for key, value in kv_list:
            _lines[key] = value
        self._pdicts[part] = _lines
    def delete_part(self, part):
        if part in self._parts:
            self._parts.remove(part)
            del self._pdicts[part]
    def copy_part(self, src_part, dst_part):
        if dst_part not in self._parts:
            self._parts.append(dst_part)
        self._pdicts[dst_part] = OrderedDict([(key, value) for key, value in self._pdicts[src_part].iteritems()])

class ca_index(OrderedDict):
    def __init__(self, f_name):
        OrderedDict.__init__(self)
        for _line in file(f_name, "r").read().split("\n"):
            if _line.strip():
                _vals = _line.split("\t")
                self[_vals[3]] = {
                    "type"      : _vals[0],
                    "exp_date"  : self._parse_date(_vals[1]),
                    "rev_date"  : self._parse_date(_vals[2]),
                    "rev_cause" : self._parse_rev_cause(_vals[2]),
                    "serial"    : _vals[3],
                    "file"      : _vals[4],
                    "name"      : _vals[5],
                }
    def _parse_date(self, in_str):
        if in_str:
            return datetime.datetime.strptime(in_str.split(",")[0], "%y%m%d%H%M%SZ")
        else:
            return None
    def format_date(self, in_dt):
        if in_dt is None:
            return ""
        else:
            return datetime.datetime.strftime(in_dt, "%Y%m%d%H%M%SZ")
    def _parse_rev_cause(self, in_str):
        if in_str.count(","):
            return in_str.split(",", 1)[1]
        else:
            return ""

class ca(object):
    def __init__(self, name, openssl_call, obj_dict):
        self.name = name
        self.openssl_call = openssl_call
        self.obj_dict = obj_dict
        self.password = "{}_PWD".format(self.name)
        self.ca_dir = os.path.join(CA_DIR, self.name)
        if not os.path.isdir(self.ca_dir):
            if self.obj_dict is not None:
                self._create()
            else:
                self.ca_ok = False
        else:
            # we assume the CA is ok
            self.ca_ok = True
        self.certs = []
        if self.ca_ok:
            self._read_certs()
    @property
    def ca_key(self):
        return os.path.join(self.ca_dir, "private", "cakey.pem")
    @property
    def ca_req(self):
        return os.path.join(self.ca_dir, "careq.pem")
    @property
    def ca_cert(self):
        return os.path.join(self.ca_dir, "cacert.pem")
    def _create(self):
        os.mkdir(self.ca_dir)
        for _dirs in ["certs", "crl", "newcerts", "private"]:
            os.mkdir(os.path.join(self.ca_dir, _dirs))
        file(os.path.join(self.ca_dir, "index.txt"), "w").close()
        self.ca_ok = False
        _success, _out = self.openssl_call("req", "-batch", "-new", "-keyout", self.ca_key, "-out", self.ca_req,
            "-subj", build_subj(self.obj_dict),
            "-passin", "pass:{}".format(self.password),
            "-passout", "pass:{}".format(self.password),
        )
        if _success:
            _ssl_cnf = openssl_config()
            _ssl_cnf.copy_part(_ssl_cnf.get("ca", "default_ca"), self.name)
            _ssl_cnf.set(self.name, "dir", self.ca_dir)
            _ssl_cnf.write()
            # copy default_
            _success, _out = self.openssl_call("ca", "-create_serial",
                "-name", self.name,
                "-subj", build_subj(self.obj_dict),
                "-out", self.ca_cert, "-days", self.obj_dict["days"], "-batch",
                "-keyfile", self.ca_key, "-selfsign",
                "-extensions", "v3_ca",
                "-passin", "pass:{}".format(self.password),
                "-infiles", self.ca_req,
            )
        self.ca_ok = _success
    def new_cert(self, obj_dict, file_name, **kwargs):
        run_ok = False
        _cert_temp = tempfile.mkdtemp("_cert")
        _success, _out = self.openssl_call("genrsa", "-out", os.path.join(_cert_temp, "serverkey.pem"), "1024")
        _ext_file = os.path.join(_cert_temp, "extfile")
        if _success:
            _success, _out = self.openssl_call("req", "-batch", "-new", "-key", os.path.join(_cert_temp, "serverkey.pem"),
                "-subj", build_subj(obj_dict),
                "-out", os.path.join(_cert_temp, "serverreq.pem"),
                )
            if _success:
                # empty file
                file(_ext_file, "w").close()
                if "device" in kwargs:
                    _dev = kwargs["device"]
                    _add_list = ["DNS:{}".format(_dns) for _dns in _dev.all_dns()] + ["IP:{}".format(_ip) for _ip in _dev.all_ips()]
                    if _add_list:
                        file(_ext_file, "w").write("subjectAltName={}".format(",".join(_add_list)))
                _success, _out = self.openssl_call("ca",
                    "-batch", "-policy", "policy_anything",
                    "-name", self.name,
                    "-days", obj_dict["days"],
                    "-subj", build_subj(obj_dict),
                    "-passin", "pass:{}".format(self.password),
                    "-out", os.path.join(_cert_temp, "servercert.pem"),
                    "-extfile", _ext_file,
                    "-infiles", os.path.join(_cert_temp, "serverreq.pem"),
                )
                if _success:
                    run_ok = True
                    # create target file
                    _tf = file(file_name, "w")
                    for _fn in ["serverkey.pem", "servercert.pem"]:
                        # print "**", _fn, file(os.path.join(_cert_temp, _fn), "r").read()
                        _tf.write(file(os.path.join(_cert_temp, _fn), "r").read())
                    _tf.close()
        shutil.rmtree(_cert_temp)
        return run_ok
    def _read_certs(self):
        _ssl_cnf = openssl_config()
        self.db = ca_index(_ssl_cnf.get(self.name, "database", expand=True))
    def revoke_cert(self, serial, cause):
        _ssl_cnf = openssl_config()
        _cert = self.db[serial]
        _success, _out = self.openssl_call("ca",
            "-batch",
            "-name", self.name,
            "-revoke", os.path.join(_ssl_cnf.get(self.name, "new_certs_dir", expand=True), "{}.pem".format(serial)),
            "-passin", "pass:{}".format(self.password),
            "-crl_reason", cause,
        )
        return _success

class openssl_config_mixin(object):
    def check_ssl_config(self, cur_inst):
        self.cur_inst = cur_inst
        self.openssl_bin = process_tools.find_file("openssl")
        self.log("openssl command is found at {}".format(self.openssl_bin))
        self._check_dir()
        self._check_config()
    def _check_dir(self):
        if not os.path.isdir(CA_DIR):
            os.makedirs(CA_DIR)
    def _check_config(self):
        if not os.path.exists(SSL_CNF):
            _src_file = None
            for _check in ["/etc/ssl/openssl.cnf"]:
                if os.path.exists(_check):
                    _src_file = _check
                    break
            if _src_file:
                self.log("creating {} from {}".format(SSL_CNF, _src_file))
                _cnf = openssl_config(_src_file)
                _cnf.set(None, "HOME", SSL_DIR)
                _cnf.set("req_distinguished_name", [
                    ("countryName_default", "AT"),
                    ("stateOrProvinceName_default", "Vienna"),
                    ("0.organizationName_default", "init.at"),
                    ("emailAddress_default", "lang-nevyjel@init.at"),
                ])
                _cnf.write()
                # file(SSL_CNF, "w").write(file(_src_file, "r").read())
            else:
                self.log("cannot create {}: no src_file found".format(SSL_CNF), logging_tools.LOG_LEVEL_CRITICAL)
    def _build_obj(self, cur_inst, **kwargs):
        obj_dict = {
            "CN" : kwargs.get("cn", ""),
            "C"  : "AT",
            "ST" : "Vienna",
            "O"  : "init.at", # Informationstechnologie GmbH",
            "emailAddress" : "cluster@init.at",
            "days"         : str(kwargs.get("days", 3650)),
        }
        for key, value in obj_dict.iteritems():
            _key = "server_key:{}".format(key)
            if  _key in cur_inst.srv_com:
                obj_dict[key] = cur_inst.srv_com[_key].text
        return obj_dict
    def call_openssl(self, command, *args):
        _com = "{} {} {} {}".format(
            self.openssl_bin,
            command,
            "-config {}".format(SSL_CNF) if command in ["ca", "req"] else "",
            " ".join(args)
        )
        self.log("command '{}'".format(_com))
        success, result = (False, [])
        c_stat, c_out = commands.getstatusoutput(_com)
        if c_stat:
            result = ["{:d}".format(c_stat)] + c_out.split("\n")
        else:
            success = True
            result = c_out.split("\n")
        self.log("result was {:d}".format(c_stat))
        for _line_num, _line in enumerate(result):
            self.log(" {:3d} : {}".format(_line_num + 1, _line))
        return success, result

