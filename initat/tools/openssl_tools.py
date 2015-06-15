#!/usr/bin/python -Ot
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel
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

from collections import OrderedDict
import commands
import datetime
import os
import shutil
import stat
import tarfile
import tempfile

from OpenSSL import crypto
from initat.tools import logging_tools
from initat.tools import process_tools

_KEYS = ["CN", "C", "ST", "O", "emailAddress"]

SSL_DIR = "/opt/cluster/share/openssl"
CA_DIR = os.path.join(SSL_DIR, "CAs")
BACKUP_DIR = os.path.join(SSL_DIR, "backups")

CA_MODES = ["ca", "server", "client"]

__all__ = ["openssl_config_mixin", "ca"]


def build_subj(sub_dict):
    return "/{}/".format("/".join(["{}={}".format(_key, sub_dict[_key].replace(" ", r"\ ")) for _key in _KEYS if _key in sub_dict]))


class openssl_config(object):
    def __init__(self, name):
        # lines without part, form is (key, value)
        self._filename = name
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

    def write(self, name=None):
        name = name or self._filename
        _lines = []
        for _part in self._parts:
            if _lines:
                _lines.append("")
            if _part:
                _lines.append("[ {} ]".format(_part))
            if len(self._pdicts[_part]):
                max_key_len = max([len(key) for key in self._pdicts[_part]])
                _form_str = "{{:{:d}s}} = {{}}".format(max_key_len)
                for key, value in self._pdicts[_part].iteritems():
                    _lines.append(_form_str.format(key, value))
        file(name, "w").write("\n".join(_lines))

    def keys(self):
        return self._pdicts.keys()

    def __getitem__(self, key):
        return self._pdicts[key]

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
        if part not in self._parts:
            self._parts.append(part)
        _lines = self._pdicts.setdefault(part, OrderedDict())
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
                    "type": _vals[0],
                    "exp_date": self._parse_date(_vals[1]),
                    "rev_date": self._parse_date(_vals[2]),
                    "rev_cause": self._parse_rev_cause(_vals[2]),
                    "serial": _vals[3],
                    "file": _vals[4],
                    "name": _vals[5],
                }
                # _rev = crypto.Revoked()
                # _rev.set_serial(_vals[3])
                # _rev.set
                # print _rev
        # _cert = crypto.load_certificate(crypto.FILETYPE_PEM, file("/opt/cluster/share/openssl/CAs/testca/newcerts/FE54503631DF0F4B.pem", "r").read())
        # print _cert.get_issuer().der()
        # _cert.get_issuer().CN = "x.y"
        # print _cert.get_issuer().get_components()
        # print _cert.get_serial_number()
        # print crypto.Revoked().all_reasons()

    def _parse_date(self, in_str):
        if in_str:
            return datetime.datetime.strptime(in_str.split(",")[0], "%y%m%d%H%M%SZ")
        else:
            return None

    def format_date(self, in_dt):
        if in_dt is None:
            return ""
        else:
            return in_dt.strftime("%Y%m%d%H%M%SZ")

    def _parse_rev_cause(self, in_str):
        if in_str.count(","):
            return in_str.split(",", 1)[1]
        else:
            return ""


class ssl_secure(object):
    def __init__(self, *args, **kwargs):
        self.__backup = kwargs.get("backup", False)

    def __call__(self, func):
        def _newf(*args, **kwargs):
            _self = args[0]
            ret_value = func(*args, **kwargs)
            for _dir, _dirs, _names in os.walk(_self.ca_dir):
                for _name in _names + _dirs + ["."]:
                    _path = os.path.join(_dir, _name)
                    cur_mode = os.stat(_path)[stat.ST_MODE]
                    new_mode = cur_mode & (stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
                    if cur_mode != new_mode:
                        os.chmod(_path, new_mode)
            if self.__backup:
                _bu_dir = os.path.join(BACKUP_DIR, _self.name)
                if not os.path.isdir(_bu_dir):
                    os.mkdir(_bu_dir)
                os.chmod(_bu_dir, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
                _tar_name = os.path.join(BACKUP_DIR, _self.name, "{}.tar.bz2".format(datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S.%f")))
                _tar = tarfile.open(_tar_name, "w:bz2")
                _tar.add(_self.ca_dir, recursive=True, filter=self._tar_filter)
                _tar.close()
                os.chmod(_tar_name, stat.S_IREAD)
            return ret_value
        return _newf

    def _tar_filter(self, tar_info):
        return tar_info


class ca(object):
    def __init__(self, name, log_com):
        self.log_com = log_com
        self.name = name
        self.password = "{}_PWD".format(self.name)
        self._check_dir()
        self.ca_dir = os.path.join(CA_DIR, self.name)
        self.ssl_config_name = os.path.join(self.ca_dir, "openssl.cnf")
        self.openssl_bin = process_tools.find_file("openssl")
        self.log("openssl command found at {}".format(self.openssl_bin))
        self.ca_ok = os.path.isdir(self.ca_dir)
        self.certs = []
        if self.ca_ok:
            self._read_certs()

    def _check_dir(self):
        if not os.path.isdir(CA_DIR):
            os.makedirs(CA_DIR)
        if not os.path.isdir(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        os.chmod(CA_DIR, stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)
        os.chmod(BACKUP_DIR, stat.S_IEXEC | stat.S_IREAD | stat.S_IWRITE)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[ca {}] {}".format(self.name, what), log_level)

    @property
    def ca_key(self):
        return os.path.join(self.ca_dir, "private", "cakey.pem")

    @property
    def ca_req(self):
        return os.path.join(self.ca_dir, "careq.pem")

    @property
    def ca_cert(self):
        return os.path.join(self.ca_dir, "cacert.pem")

    @ssl_secure(backup=True)
    def create(self, obj_dict):
        os.mkdir(self.ca_dir)
        for _dirs in ["certs", "crl", "newcerts", "private", "keys", "reqs"]:
            os.mkdir(os.path.join(self.ca_dir, _dirs))
        file(os.path.join(self.ca_dir, "index.txt"), "w").close()
        self._create_ssl_config()
        self.ca_ok = False
        _success, _out = self.call_openssl(
            "req",
            "-batch", "-new", "-keyout", self.ca_key, "-out", self.ca_req,
            "-subj", build_subj(obj_dict),
            "-passin", "pass:{}".format(self.password),
            "-passout", "pass:{}".format(self.password),
        )
        if _success:
            _ssl_cnf = openssl_config(self.ssl_config_name)
            _x509_defaults = {
                "ca": [
                    ("authorityKeyIdentifier", "keyid:always,issuer:always"),
                    ("nsCertType", "sslCA, emailCA"),
                    ("keyUsage", "critical, keyCertSign, cRLsign"),
                    ("basicConstraints", "critical,CA:true"),
                ],
                "server": [
                    ("authorityKeyIdentifier", "keyid,issuer:always"),
                    ("nsCertType", "server"),
                    ("basicConstraints", "CA:FALSE"),
                ],
                "client": [
                    ("nsCertType", "client, email, objsign"),
                    ("basicConstraints", "CA:FALSE"),
                    ("keyUsage", "critical, digitalSignature, keyEncipherment"),
                ]
            }
            for _target_mode in CA_MODES:
                _ca_target = "ca_{}".format(_target_mode)
                _ssl_cnf.copy_part(_ssl_cnf.get("ca", "default_ca"), _ca_target)
                _ssl_cnf.set(_ca_target, "dir", self.ca_dir)
                _cert_target = "cert_{}".format(_target_mode)
                _policy_target = "policy_{}".format(_target_mode)
                _ssl_cnf.set(_ca_target, "x509_extensions", _cert_target)
                _ssl_cnf.set(_cert_target, [
                    ("subjectKeyIdentifier", "hash"),
                    ("issuerAltName", "issuer:copy"),
                    ("subjectAltName", "email:copy"),
                    ("nsComment", "openssl_tool generated {} certificate".format(_target_mode)),
                ])
                _ssl_cnf.set(_policy_target, [
                    ("countryName", "optional"),
                    ("stateOrProvinceName", "optional"),
                    ("organizationName", "optional"),
                    ("organizationalUnitName", "optional"),
                    ("commonName", "supplied"),
                    ("emailAddress", "optional"),
                ])
                _ssl_cnf.set(_cert_target, _x509_defaults.get(_target_mode, []))
                _ssl_cnf.set(_ca_target, "policy", _policy_target)
            _ssl_cnf.write()
            # copy default_
            _success, _out = self.call_openssl(
                "ca", "-create_serial",
                "-name", "ca_ca",
                "-subj", build_subj(obj_dict),
                "-out", self.ca_cert, "-days", obj_dict["days"], "-batch",
                "-keyfile", self.ca_key, "-selfsign",
                "-extensions", "v3_ca",
                "-passin", "pass:{}".format(self.password),
                "-infiles", self.ca_req,
            )
        self.ca_ok = _success
        return self.ca_ok

    def _create_ssl_config(self):
        if not os.path.exists(self.ssl_config_name):
            _src_file = None
            for _check in ["/etc/ssl/openssl.cnf"]:
                if os.path.exists(_check):
                    _src_file = _check
                    break
            if _src_file:
                self.log("creating {} from {}".format(self.ssl_config_name, _src_file))
                _cnf = openssl_config(_src_file)
                _cnf.set(None, "HOME", SSL_DIR)
                _cnf.set("req_distinguished_name", [
                    ("countryName_default", "AT"),
                    ("stateOrProvinceName_default", "Vienna"),
                    ("0.organizationName_default", "init.at"),
                    ("emailAddress_default", "cluster@init.at"),
                ])
                _cnf.set("req", "default_bits", 4096)

                _cnf.write(self.ssl_config_name)
                os.chmod(self.ssl_config_name, stat.S_IREAD | stat.S_IWRITE)
            else:
                self.log("cannot create {}: no src_file found".format(self.ssl_config_name), logging_tools.LOG_LEVEL_CRITICAL)

    @ssl_secure(backup=True)
    def new_cert(self, obj_dict, mode, file_name, **kwargs):
        if mode in ["ca"]:
            raise KeyError("mode '{}' not allowed".format(mode))
        run_ok = False
        _cert_temp = tempfile.mkdtemp("_cert")
        _success, _out = self.call_openssl("genrsa", "-out", os.path.join(_cert_temp, "key.pem"), "1024")
        _ext_file = os.path.join(_cert_temp, "extfile")
        if _success:
            _success, _out = self.call_openssl(
                "req", "-batch", "-new", "-key", os.path.join(_cert_temp, "key.pem"),
                "-subj", build_subj(obj_dict),
                "-out", os.path.join(_cert_temp, "req.pem"),
                )
            if _success:
                # empty file
                file(_ext_file, "w").close()
                if "device" in kwargs:
                    _dev = kwargs["device"]
                    _add_list = ["DNS:{}".format(_dns) for _dns in _dev.all_dns()] + ["IP:{}".format(_ip) for _ip in _dev.all_ips() if _ip]
                    if _add_list:
                        file(_ext_file, "w").write("subjectAltName={}".format(",".join(_add_list)))
                _success, _out = self.call_openssl(
                    "ca",
                    "-batch", "-policy", "policy_anything",
                    "-name", "ca_{}".format(mode),
                    "-days", obj_dict["days"],
                    "-subj", build_subj(obj_dict),
                    "-passin", "pass:{}".format(self.password),
                    "-out", os.path.join(_cert_temp, "cert.pem"),
                    "-extfile", _ext_file,
                    "-infiles", os.path.join(_cert_temp, "req.pem"),
                )
                if _success:
                    run_ok = True
                    # copy request and key
                    _serial = "{:x}".format(
                        crypto.load_certificate(crypto.FILETYPE_PEM, file(os.path.join(_cert_temp, "cert.pem"), "r").read()).get_serial_number()
                    ).upper()
                    for src_file, dst_dir in [("key.pem", "keys"), ("req.pem", "reqs")]:
                        file(os.path.join(self.ca_dir, dst_dir, "{}.pem".format(_serial)), "w").write(file(os.path.join(_cert_temp, src_file), "r").read())
                    # create target file
                    _tf = file(file_name, "w")
                    for _fn in ["key.pem", "cert.pem"]:
                        # print "**", _fn, file(os.path.join(_cert_temp, _fn), "r").read()
                        _tf.write(file(os.path.join(_cert_temp, _fn), "r").read())
                    _tf.close()
        shutil.rmtree(_cert_temp)
        return run_ok

    @ssl_secure()
    def _read_certs(self):
        _ssl_cnf = openssl_config(self.ssl_config_name)
        self.db = ca_index(_ssl_cnf.get("ca_ca", "database", expand=True))

    @ssl_secure(backup=True)
    def revoke_cert(self, serial, cause):
        _ssl_cnf = openssl_config(self.ssl_config_name)
        _cert = self.db[serial]
        _success, _out = self.call_openssl(
            "ca",
            "-batch",
            "-name", self.name,
            "-revoke", os.path.join(_ssl_cnf.get(self.name, "new_certs_dir", expand=True), "{}.pem".format(serial)),
            "-passin", "pass:{}".format(self.password),
            "-crl_reason", cause,
        )
        return _success

    def call_openssl(self, command, *args):
        _com = "{} {} {} {}".format(
            self.openssl_bin,
            command,
            "-config {}".format(self.ssl_config_name) if command in ["ca", "req"] else "",
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
