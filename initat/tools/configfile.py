# Copyright (C) 2001-2009,2011-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not,   to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" module for handling config files, now implemented using MemCache """

from __future__ import unicode_literals, print_function

import argparse
import base64
import bz2
import datetime
import functools
import json
import os
import re
import uuid

import memcache

from initat.icsw.service import instance
from initat.tools import logging_tools, process_tools


class _conf_var(object):
    argparse_type = None

    def __init__(self, def_val, **kwargs):
        self.__default_val = def_val
        self.__info = kwargs.get("info", "")
        if not self.check_type(def_val):
            raise TypeError(
                "Type of Default-value differs from given type ({}, {})".format(
                    type(def_val),
                    str(self.short_type)
                )
            )
        self.source = kwargs.get("source", "default")
        self.fixed = kwargs.get("fixed", False)
        self.is_global = kwargs.get("is_global", True)
        self.value = self.__default_val
        # for commandline options
        self._help_string = kwargs.get("help_string", None)
        self._short_opts = kwargs.get("short_options", None)
        self._choices = kwargs.get("choices", None)
        self._nargs = kwargs.get("nargs", None)
        self._database_set = "database" in kwargs
        self._database = kwargs.get("database", False)
        self._only_commandline = kwargs.get("only_commandline", False)
        kw_keys = set(kwargs) - {
            "only_commandline", "info", "source", "fixed", "action", "is_global",
            "help_string", "short_options", "choices", "nargs", "database",
        }
        if kw_keys:
            print(
                "*** {} for _conf_var('{}') left: {} ***".format(
                    logging_tools.get_plural("keyword argument", len(kw_keys)),
                    str(self.value),
                    ", ".join(sorted(kw_keys)),
                )
            )

    def serialize(self):
        if self.descr in ["Blob"]:
            _val = base64.b64encode(bz2.compress(self.value))
            _def_val = base64.b64encode(bz2.compress(self.__default_val))
        else:
            _val = self.value
            _def_val = self.__default_val
        return json.dumps(
            {
                # to determine type
                "descr": self.descr,
                # first argument
                "default_value": _def_val,
                # current value
                "value": _val,
                # kwargs
                "kwargs": {
                    "info": self.__info,
                    "source": self.source,
                    "fixed": self.fixed,
                    "is_global": self.is_global,
                    "help_string": self._help_string,
                    "short_options": self._short_opts,
                    "choices": self._choices,
                    "nargs": self._nargs,
                    "database": self.database,
                    "only_commandline": self._only_commandline,
                }
            }
        )

    def is_commandline_option(self):
        return True if self._help_string else False

    def get_commandline_info(self):
        if self._help_string:
            return "is commandline option, help_string is '{}'".format(self._help_string)
        else:
            return "no commandline option"

    def add_argument(self, name, arg_parser):
        if self._short_opts:
            if len(self._short_opts) > 1:
                opts = ["--{}".format(self._short_opts)]
            else:
                opts = ["-{}".format(self._short_opts)]
        else:
            opts = ["--{}".format(name.lower())]
            if name.lower().count("_"):
                opts.append("--{}".format(name.lower().replace("_", "-")))
        kwargs = {
            "dest": name,
            "help": self._help_string,
        }
        if self._choices:
            kwargs["choices"] = self._choices
        if self._nargs:
            kwargs["nargs"] = self._nargs
        if self.argparse_type is None:
            if self.short_type == "b":
                # bool
                arg_parser.add_argument(*opts, action="store_{}".format("false" if self.__default_val else "true"), default=self.__default_val, **kwargs)
            else:
                print("*? unknown short_type in _conf_var ?*", self.short_type, name, self.argparse_type)
        else:
            arg_parser.add_argument(*opts, type=self.argparse_type, default=self.value, **kwargs)

    @property
    def database(self):
        return self._database

    @database.setter
    def database(self, database):
        self._database = database

    @property
    def is_global(self):
        return self.__is_global

    @is_global.setter
    def is_global(self, is_global):
        self.__is_global = is_global

    @property
    def fixed(self):
        return self.__fixed

    @fixed.setter
    def fixed(self, fixed):
        self.__fixed = fixed

    @property
    def source(self):
        return self.__source

    @source.setter
    def source(self, source):
        self.__source = source

    def pretty_print(self):
        # default: return value
        return self.act_val

    def str_to_val(self, val):
        # default: return value
        return val

    @property
    def value(self):
        return self.act_val

    @value.setter
    def value(self, value):
        self.act_val = value

    def set_value(self, val, source="default"):
        try:
            r_val = self.str_to_val(val)
        except TypeError:
            raise TypeError("Type Error for value {}".format(str(val)))
        except ValueError:
            raise ValueError("Value Error for value {}".format(str(val)))
        else:
            if type(r_val) in {tuple, list}:
                _c_val = set(r_val)
            else:
                _c_val = set([r_val])
            if self._choices and _c_val - set(self._choices):
                print(
                    "ignoring value {} for {} (not in choices: {})".format(
                        r_val,
                        self.descr,
                        str(self._choices),
                    )
                )
            else:
                self.value = r_val
                if source and (source != "default" or self.source == "default"):
                    self.source = source

    def __str__(self):
        return "{} (source {}, {}) : {}".format(
            self.descr,
            self.source,
            "global" if self.__is_global else "local",
            self.pretty_print()
        )

    def get_info(self):
        return self.__info


class int_c_var(_conf_var):
    descr = "Integer"
    short_type = "i"
    long_type = "int"
    argparse_type = int

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return int(val)

    def check_type(self, val):
        return type(val) in [int, long]


class float_c_var(_conf_var):
    descr = "Float"
    short_type = "f"
    long_type = "float"
    argparse_type = float

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return float(val)

    def check_type(self, val):
        return type(val) == float


class str_c_var(_conf_var):
    descr = "String"
    short_type = "s"
    long_type = "str"
    argparse_type = str

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return str(val)

    def check_type(self, val):
        return isinstance(val, basestring)


class blob_c_var(_conf_var):
    descr = "Blob"
    short_type = "B"
    long_type = "blob"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return str(val)

    def check_type(self, val):
        return type(val) == str

    def pretty_print(self):
        return "blob with len {:d}".format(len(self.act_val))


class bool_c_var(_conf_var):
    descr = "Bool"
    short_type = "b"
    long_type = "bool"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        if isinstance(val, basestring):
            if val.lower().startswith("t"):
                return True
            else:
                return False
        else:
            return bool(val)

    def check_type(self, val):
        return type(val) == bool

    def pretty_print(self):
        return "True" if self.act_val else "False"


class array_c_var(_conf_var):
    descr = "Array"
    short_type = "a"
    long_type = "array"
    argparse_type = str

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return type(val) in [list, str]


class dict_c_var(_conf_var):
    descr = "Dict"
    short_type = "d"
    long_type = "dict"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return type(val) == dict


class datetime_c_var(_conf_var):
    descr = "Datetime"
    short_type = "ddt"
    long_type = "datetime"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return isinstance(val, datetime.datetime)


class timedelta_c_var(_conf_var):
    descr = "Timedelta"
    short_type = "dtd"
    long_time = "timedelta"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return isinstance(val, datetime.timedelta)


CONFIG_PREFIX = "__ICSW__$conf$__"


class MemCacheBasedDict(object):
    def __init__(self, mc_client, prefix, single_process_mode, enabled):
        self.__spm = single_process_mode
        self.__enabled = enabled
        self.mc_client = mc_client
        self.prefix = prefix
        self._dict = {}
        self._keys = []
        # version tag
        self._version = None
        # update mode, used for faster updates
        self.__update_mode = False
        self._check_mc()

    def enable(self):
        if not self.__enabled:
            self.__enabled = True
            if not self.__spm:
                self._store_full_dict()

    @property
    def update_mode(self):
        return self.__update_mode

    @update_mode.setter
    def update_mode(self, mode):
        self.__update_mode = mode
        if not self.__update_mode:
            self._store_full_dict()

    def _mc_key(self, key):
        return "{}_{}".format(self.prefix, key)

    def _get(self, key):
        return self.mc_client.get(self._mc_key(key))

    def _set(self, key, value):
        return self.mc_client.set(self._mc_key(key), value)

    def _check_mc(self):
        if not self.__spm and self.__enabled:
            _mc_vers = self._get("version")
            if not self._version:
                # get version
                if _mc_vers is None:
                    # version not found, store full dict
                    self._store_full_dict()
                else:
                    # read full dict
                    self._read_full_dict()
            elif self._version != _mc_vers:
                # reread
                self._read_full_dict()

    def _change_version(self):
        self._version = uuid.uuid4().get_urn()
        # print os.getpid(), "CV ->", self._version
        self._set("version", self._version)

    def _store_full_dict(self):
        if not self.__spm and self.__enabled:
            for _key in self._keys:
                self._update_key(_key)
            self._store_keys()

    def _store_keys(self):
        self._set("keys", json.dumps(self._keys))
        self._change_version()

    def _update_key(self, key):
        self._set("k_{}".format(key), self._dict[key].serialize())

    def _key_modified(self, key):
        if not self.__spm and self.__enabled:
            self._update_key(key)
            self._store_keys()

    def _dummy_init(self):
        self._keys = []
        self._dict = {}
        self._store_full_dict()

    def _read_full_dict(self):
        try:
            self._version = self._get("version")
            self._keys = json.loads(self._get("keys"))
            self._dict = {}
            for _key in self._keys:
                # print "*", _key
                # deserialize dict
                _raw = self._get("k_{}".format(_key))
                try:
                    _json = json.loads(_raw)
                except:
                    # print os.getpid(), "JSON", _key, _raw, "*"
                    raise
                _is_blob = _json["descr"] in ["Blob"]
                if _is_blob:
                    _json["default_value"] = bz2.decompress(base64.b64decode(_json["default_value"]))
                # print _raw
                _obj = {
                    "Timedelta": timedelta_c_var,
                    "Datetime": datetime_c_var,
                    "Dict": dict_c_var,
                    "Array": array_c_var,
                    "Bool": bool_c_var,
                    "Blob": blob_c_var,
                    "String": str_c_var,
                    "Float": float_c_var,
                    "Integer": int_c_var,
                }[_json["descr"]](_json["default_value"], **_json["kwargs"])
                if _is_blob:
                    _obj.value = bz2.decompress(base64.b64decode(_json["value"]))
                else:
                    _obj.value = _json["value"]
                self._dict[_key] = _obj
        except:
            print(
                "Something went wrong in deserializing config with prefix {}: {}, pid={:d}".format(
                    self.prefix,
                    process_tools.get_except_info(),
                    os.getpid(),
                )
            )
            # something went wrong, start with empty dict
            self._dummy_init()

    # public functions

    def keys(self):
        self._check_mc()
        return self._keys

    def __contains__(self, _key):
        self._check_mc()
        return _key in self._keys

    def __setitem__(self, key, value):
        # print os.getpid(), "store", key
        self._check_mc()
        if key not in self._keys:
            self._keys.append(key)
        self._dict[key] = value
        if not self.__update_mode:
            self._key_modified(key)

    def __getitem__(self, key):
        self._check_mc()
        # print os.getpid(), "get", key
        # print self._dict
        return self._dict[key]

    def __delitem__(self, key):
        self._check_mc()
        self._keys.remove(key)
        del self._dict[key]
        if not self.__spm and self.__enabled:
            self.mc_client.delete(self._mc_key(key))
            self._store_keys()

    def key_changed(self, key):
        self._key_modified(key)


class ConfigKeyError(object):
    def __init__(self, *args, **kwargs):
        self._func = args[0]

    def __get__(self, obj, objtype):
        """ Support instance methods. """
        # copy object
        self.config = obj
        # partial magic
        return functools.partial(self.__call__, obj)

    def __call__(self, *args, **kwargs):
        try:
            return self._func(*args, **kwargs)
        except KeyError:
            raise KeyError("Key {} not defined ({})".format(args[0], self.obj.key_info))


class Configuration(object):
    def __init__(self, name, *args, **kwargs):
        inst_xml = instance.InstanceXML(quiet=True)
        self.__mc_enabled = kwargs.get("mc_enabled", True)
        _mc_addr = "127.0.0.1"
        _mc_port = inst_xml.get_port_dict("memcached", command=True)
        self.__mc_addr = "{}:{:d}".format(_mc_addr, _mc_port)
        self.__name = name
        self.__backend_init = False
        self.mc_prefix = ""
        self.__verbose = kwargs.get("verbose", False)
        self.__spm = kwargs.pop("single_process_mode", False)
        self._reopen_mc(True)
        self.clear_log()
        if args:
            self.add_config_entries(*args)

    @property
    def mc_prefix(self):
        return self.__mc_prefix

    @mc_prefix.setter
    def mc_prefix(self, prefix):
        self.__mc_prefix = "{}{}{}".format(CONFIG_PREFIX, self.__name, prefix)
        if self.__backend_init:
            self.__c_dict.prefix = self.__mc_prefix

    def enable_mc(self):
        # enable memcached backend, can only be enabled (not disabled)
        if not self.__mc_enabled:
            self.__mc_enabled = True
            self.__c_dict.enable()

    def delete(self):
        # remove global config
        _keys = list(self.keys())
        for key in _keys:
            del self[key]

    def close(self):
        # to be called for every new process
        self._reopen_mc()

    def _reopen_mc(self, first=False):
        if self.__spm:
            self.__mc_client = None
        else:
            if not first:
                self.__mc_client.disconnect_all()
            try:
                self.__mc_client = memcache.Client([self.__mc_addr])
            except:
                raise
        self.__backend_init = True
        self.__c_dict = MemCacheBasedDict(self.__mc_client, self.__mc_prefix, self.__spm, self.__mc_enabled)

    def get_log(self, **kwargs):
        ret_val = [entry for entry in self.__log_array]
        if kwargs.get("clear", True):
            self.clear_log()
        return ret_val

    def name(self):
        return self.__name

    def clear_log(self):
        self.__log_array = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_array.append((what, log_level))

    @property
    def single_process_mode(self):
        return self.__spm

    def help_string(self, key):
        return self.__c_dict[key]._help_string

    def get_var(self, key):
        return self.__c_dict[key]

    def add_config_entries(self, entries, **kwargs):
        if type(entries) == dict:
            entries = sorted([(key, value) for key, value in entries.iteritems()])
        self.__c_dict.update_mode = True
        for key, value in entries:
            # check for override of database flag
            if not value._database_set and "database" in kwargs:
                if self.__verbose:
                    self.log("override database flag for '{}', setting to '{}'".format(key, str(kwargs["database"])))
                value.database = kwargs["database"]
            if key in self.__c_dict and self.__verbose:
                self.log("Replacing config for key {}".format(key))
            self.__c_dict[key] = value
            if self.__verbose:
                self.log("Setting config for key {} to {}".format(key, value))
        self.__c_dict.update_mode = False

    @property
    def key_info(self):
        return "{}".format(", ".join(sorted(self.__c_dict.keys())))

    @ConfigKeyError
    def pretty_print(self, key):
        return self.__c_dict[key].pretty_print()

    @ConfigKeyError
    def __getitem__(self, key):
        # print os.getpid(), key
        return self.__c_dict[key].value

    @ConfigKeyError
    def __delitem__(self, key):
        del self.__c_dict[key]

    def __setitem__(self, key, value):
        if key in self.__c_dict:
            if type(value) == tuple:
                value, source = value
            else:
                source = None
            self.__c_dict[key].set_value(value, source)
            # import the signal changes
            self.__c_dict.key_changed(key)
        else:
            raise KeyError("Key {} not known ({})".format(key, self.key_info))

    def get_config_info(self):
        gk = sorted(self.keys())
        if gk:
            f_obj = logging_tools.new_form_list()
            for key in gk:
                if self.get_type(key) in ["a", "d"]:
                    pv = self.pretty_print(key)
                    f_obj.append(
                        [
                            logging_tools.form_entry(key),
                            logging_tools.form_entry("list with {}:".format(logging_tools.get_plural("entry", len(pv)))),
                            logging_tools.form_entry(self.get_type(key)),
                            logging_tools.form_entry(self.get_source(key)),
                        ]
                    )
                    for idx, entry in enumerate(pv):
                        f_obj.append(
                            [
                                logging_tools.form_entry(""),
                                logging_tools.form_entry(""),
                                logging_tools.form_entry(entry),
                                logging_tools.form_entry(str(idx)),
                                logging_tools.form_entry("---"),
                            ]
                        )
                else:
                    f_obj.append(
                        [
                            logging_tools.form_entry(key, header="key"),
                            logging_tools.form_entry(self.is_global(key) and "global" or "local", post_str=" : ", header="global"),
                            logging_tools.form_entry(self.pretty_print(key), header="value"),
                            logging_tools.form_entry(self.get_type(key), pre_str=", (", post_str=" from ", header="type"),
                            logging_tools.form_entry(self.get_source(key), post_str=")", header="source"),
                        ]
                    )
            ret_str = unicode(f_obj).split("\n")
        else:
            ret_str = []
        return ret_str

    def keys(self):
        return self.__c_dict.keys()

    def has_key(self, key):
        return key in self.__c_dict

    def __contains__(self, key):
        return key in self.__c_dict

    def get(self, key, def_v):
        if key in self.__c_dict:
            return self.__c_dict[key].value
        else:
            return def_v

    def get_cvar(self, key):
        return self.__c_dict[key]

    @ConfigKeyError
    def get_source(self, key):
        return self.__c_dict[key].source

    @ConfigKeyError
    def fixed(self, key):
        return self.__c_dict[key].fixed

    @ConfigKeyError
    def is_global(self, key):
        return self.__c_dict[key].is_global

    @ConfigKeyError
    def set_global(self, key, value):
        self.__c_dict[key].is_global = value

    @ConfigKeyError
    def database(self, key):
        return self.__c_dict[key].database

    @ConfigKeyError
    def get_type(self, key):
        return self.__c_dict[key].short_type

    def parse_file(self, *args, **kwargs):
        # only used in proepilogue, to be removed ...
        # TODO, Fixme
        if len(args):
            file_name = args[0]
        else:
            file_name = os.path.join("/etc", "sysconfig", self.__name)
        # kwargs:
        # section ... only read arugments from the given section (if found)
        scan_section = kwargs.get("section", "global")
        act_section = "global"
        pf1 = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)\s*$")
        pf2 = re.compile("^(?P<key>\S+)\s+(?P<value>.+)\s*$")
        sec_re = re.compile("^\[(?P<section>\S+)\]$")
        if os.path.isfile(file_name):
            try:
                lines = [line.strip() for line in open(file_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
            except:
                self.log(
                    "Error while reading file {}: {}".format(
                        file_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                for line in lines:
                    sec_m = sec_re.match(line)
                    if sec_m:
                        act_section = sec_m.group("section")
                    else:
                        for mo in [pf1, pf2]:
                            ma = mo.match(line)
                            if ma:
                                break
                        if act_section == scan_section:
                            if ma:
                                key, value = (ma.group("key"), ma.group("value"))
                                try:
                                    cur_type = self.get_type(key)
                                except KeyError:
                                    self.log(
                                        "Error: key {} not defined in dictionary for get_type".format(
                                            key
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR
                                    )
                                else:
                                    # interpret using eval
                                    if cur_type == "s":
                                        if value not in ["\"\""]:
                                            if value[0] == value[-1] and value[0] in ['"', "'"]:
                                                pass
                                            else:
                                                # escape strings
                                                value = "\"{}\"".format(value)
                                    try:
                                        self[key] = (
                                            eval("{}".format(value)),
                                            "{}, sec {}".format(file_name, act_section)
                                        )
                                    except KeyError:
                                        self.log(
                                            "Error: key {} not defined in dictionary".format(
                                                key
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
                                    else:
                                        if self.__verbose:
                                            self.log(
                                                "Changing value of key {} to {}".format(
                                                    key,
                                                    self.__c_dict[key]
                                                )
                                            )
                            else:
                                self.log(
                                    "Error parsing line '{}'".format(
                                        str(line)
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
        else:
            self.log(
                "Cannot find file {}".format(
                    file_name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _argparse_exit(self, status=0, message=None):
        if message:
            print(message)
        self.exit_code = status

    def _argparse_error(self, message):
        if message:
            print("_argparse_error:", message)
        self.exit_code = 2

    def get_argument_stuff(self):
        return {
            "positional_arguments": self.positional_arguments,
            "other_arguments": self.other_arguments,
            "arg_list": self.positional_arguments + self.other_arguments
        }

    def handle_commandline(self, *opt_args, **kwargs):
        if len(opt_args):
            opt_args = list(opt_args)
        else:
            opt_args = None
        proxy_call = kwargs.pop("proxy_call", False)
        pos_arguments = kwargs.pop("positional_arguments", False)
        pos_arguments_optional = kwargs.pop("positional_arguments_optional", False)
        partial = kwargs.pop("partial", False)
        self.exit_code = None
        my_parser = argparse.ArgumentParser(**kwargs)
        if proxy_call:
            # monkey-patch argparser if called from proxy
            my_parser.exit = self._argparse_exit
            my_parser.error = self._argparse_error
        argparse_entries = []
        for key in self.keys():
            c_var = self.get_cvar(key)
            if c_var.is_commandline_option():
                argparse_entries.append(key)
                c_var.add_argument(key, my_parser)
        if argparse_entries:
            if pos_arguments:
                my_parser.add_argument(
                    "arguments",
                    nargs="*" if pos_arguments_optional else "+",
                    help="additional arguments"
                )
            try:
                if partial:
                    options, rest_args = my_parser.parse_known_args()
                else:
                    options, rest_args = (my_parser.parse_args(opt_args), [])
            except:
                # catch parse errors
                if self.exit_code is not None:
                    # set dummy values
                    options, rest_args = (argparse.Namespace(), [])
                else:
                    raise
            self.other_arguments = rest_args
            if not self.exit_code:
                # only handle options if exit_code is None
                for key in argparse_entries:
                    self[key] = getattr(options, key)
                self.positional_arguments = options.arguments if pos_arguments else []
        else:
            options = argparse.Namespace()
        if proxy_call:
            return options, self.exit_code
        else:
            return options


def get_global_config(c_name, single_process_mode=False, mc_enabled=True):
    return Configuration(
        c_name,
        single_process_mode=single_process_mode,
        mc_enabled=mc_enabled
    )
