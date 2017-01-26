# Copyright (C) 2001-2009,2011-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

import array
import base64
import bz2
import datetime
import functools
import json
import os
import uuid

from initat.icsw.service import instance
from initat.tools import logging_tools, process_tools


class _conf_var(object):
    argparse_type = None

    def __init__(self, def_val, **kwargs):
        self.__default_val = def_val
        if not self.check_type(def_val):
            raise TypeError(
                "Type of Default-value differs from given type ({}, {})".format(
                    type(def_val),
                    str(self.short_type)
                )
            )
        self.source = kwargs.get("source", "default")
        self.value = self.__default_val
        self.__help_string = kwargs.get("help_string", None)
        self.__database = kwargs.get("database", False)
        self.__database_flag_set = "database" in kwargs
        kw_keys = set(kwargs) - {
            "source", "help_string", "database",
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
            _val = base64.b64encode(bz2.compress(self.value)).decode("ascii")
            _def_val = base64.b64encode(bz2.compress(self.__default_val)).decode("ascii")
        else:
            _val = self.value
            _def_val = self.__default_val
        _kwargs = {
            "source": self.source,
            "help_string": self.__help_string,
        }
        if self.__database_flag_set:
            # add database value only if the database_flag was set from the __init__ kwargs
            # (not only via the default value)
            _kwargs["database"] = self.database
        return json.dumps(
            {
                # to determine type
                "descr": self.descr,
                # first argument
                "default_value": _def_val,
                # current value
                "value": _val,
                # kwargs
                "kwargs": _kwargs,
            }
        )

    @property
    def help_string(self):
        return self.__help_string

    @help_string.setter
    def help_string(self, value):
        self.__help_string = value

    @property
    def database(self):
        return self.__database

    @database.setter
    def database(self, database):
        self.__database = database

    @property
    def database_flag_set(self):
        return self.__database_flag_set

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
            if isinstance(r_val, tuple) or isinstance(r_val, list):
                _c_val = set(r_val)
            else:
                _c_val = set([r_val])
            self.value = r_val
            if source and (source != "default" or self.source == "default"):
                self.source = source

    def __str__(self):
        return "{} (source {}) : {}".format(
            self.descr,
            self.source,
            self.pretty_print()
        )


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
        return isinstance(val, int)


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
        return isinstance(val, float)


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
        return isinstance(val, str)


class blob_c_var(_conf_var):
    # holds bytestrings
    descr = "Blob"
    short_type = "B"
    long_type = "blob"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return str(val)

    def check_type(self, val):
        return isinstance(val, bytes)

    def pretty_print(self):
        return "blob with len {:d}".format(len(self.act_val))


class bool_c_var(_conf_var):
    descr = "Bool"
    short_type = "b"
    long_type = "bool"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        if isinstance(val, str):
            if val.lower().startswith("t"):
                return True
            else:
                return False
        else:
            return bool(val)

    def check_type(self, val):
        return isinstance(val, bool)

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
        return isinstance(val, list) or isinstance(val, str)


class dict_c_var(_conf_var):
    descr = "Dict"
    short_type = "d"
    long_type = "dict"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return isinstance(val, dict)


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
        self._version = uuid.uuid4().urn
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
            raise KeyError("Key {} not defined ({})".format(args[0], self.config.key_info))


class Configuration(object):
    def __init__(self, name, *args, **kwargs):
        self.__mc_enabled = kwargs.get("mc_enabled", True)
        self.__name = name
        self.__backend_init = False
        self.mc_prefix = ""
        self.__spm = kwargs.pop("single_process_mode", False)
        self._reopen_mc(True)
        self.clear_log()
        if args:
            self.add_config_entries(*args)

    def as_dict(self):
        return {key: self.__c_dict[key].value for key in self.keys()}

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
            import memcache
            if not first:
                self.__mc_client.disconnect_all()
            try:
                inst_xml = instance.InstanceXML(quiet=True)
                _mc_addr = "127.0.0.1"
                _mc_port = inst_xml.get_port_dict("memcached", command=True)
                self.__mc_addr = "{}:{:d}".format(_mc_addr, _mc_port)
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
        return self.__c_dict[key].help_string

    def get_var(self, key):
        return self.__c_dict[key]

    def add_config_entries(self, entries, **kwargs):
        if isinstance(entries, dict):
            entries = sorted([(key, value) for key, value in entries.items()])
        self.__c_dict.update_mode = True
        for key, value in entries:
            # check for override of database flag
            if "database" in kwargs and not value.database_flag_set:
                value.database = kwargs["database"]
            self.__c_dict[key] = value
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
            if isinstance(value, tuple):
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
            f_obj = logging_tools.NewFormList()
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
                                logging_tools.form_entry(entry),
                                logging_tools.form_entry(str(idx)),
                                logging_tools.form_entry("---"),
                            ]
                        )
                else:
                    f_obj.append(
                        [
                            logging_tools.form_entry(key, header="key"),
                            logging_tools.form_entry(self.pretty_print(key), header="value"),
                            logging_tools.form_entry(self.get_type(key), pre_str=", (", post_str=" from ", header="type"),
                            logging_tools.form_entry(self.get_source(key), post_str=")", header="source"),
                        ]
                    )
            ret_str = str(f_obj).split("\n")
        else:
            ret_str = []
        return ret_str

    def keys(self):
        return list(self.__c_dict.keys())

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
    def database(self, key):
        return self.__c_dict[key].database

    @ConfigKeyError
    def get_type(self, key):
        return self.__c_dict[key].short_type

    def from_database(self, sql_info, init_list=[]):
        from django.db.models import Q
        from initat.tools import configfile
        from initat.cluster.backbone.models import config_blob, \
            config_bool, config_int, config_str
        _VAR_LUT = {
            "int": config_int,
            "str": config_str,
            "blob": config_blob,
            "bool": config_bool,
        }

        self.add_config_entries(init_list, database=True)
        if sql_info.effective_device:
            # dict of local vars without specified host
            for short in [
                "str",
                "int",
                "blob",
                "bool",
            ]:
                # very similiar code appears in config_tools.py
                src_sql_obj = _VAR_LUT[short].objects
                if init_list:
                    src_sql_obj = src_sql_obj.filter(
                        Q(name__in=[var_name for var_name, _var_value in init_list])
                    )
                for db_rec in src_sql_obj.filter(
                    Q(config=sql_info.config) &
                    Q(config__device_config__device=sql_info.effective_device)
                ).order_by("name"):
                    var_name = db_rec.name
                    source = "{}_table (pk={})".format(short, db_rec.pk)
                    if isinstance(db_rec.value, array.array):
                        new_val = configfile.str_c_var(db_rec.value.tostring(), source=source)
                    elif short == "int":
                        new_val = configfile.int_c_var(int(db_rec.value), source=source)
                    elif short == "bool":
                        new_val = configfile.bool_c_var(bool(db_rec.value), source=source)
                    else:
                        new_val = configfile.str_c_var(db_rec.value, source=source)
                    _present_in_config = var_name in self
                    if _present_in_config:
                        # copy settings from config
                        new_val.database = self.database(var_name)
                        new_val.help_string = self.help_string(var_name)
                    self.add_config_entries([(var_name.upper(), new_val)])

    def to_database(self, sql_info):
        from django.db.models import Q
        from initat.cluster.backbone.models import config_blob, \
            config_bool, config_int, config_str

        def strip_description(descr):
            if descr:
                descr = " ".join(
                    [
                        entry for entry in descr.strip().split() if not entry.count("(default)")
                        ]
                )
            return descr

        type_dict = {
            "i": config_int,
            "s": config_str,
            "b": config_bool,
            "B": config_blob,
        }
        if sql_info.effective_device and sql_info.config:
            for key in sorted(self.keys()):
                # print k,config.get_source(k)
                # print "write", k, config.get_source(k)
                # if config.get_source(k) == "default":
                # only deal with int and str-variables
                var_obj = type_dict.get(self.get_type(key), None)
                # print key, var_obj, self.database(key)
                if var_obj is not None and self.database(key):
                    other_types = set([value for _key, value in list(type_dict.items()) if _key != self.get_type(key)])
                    # var global / local
                    var_range_name = "global"
                    # build real var name
                    real_k_name = key
                    try:
                        cur_var = var_obj.objects.get(
                            Q(name=real_k_name) &
                            Q(config=sql_info.config) &
                            (Q(device=0) | Q(device=None) | Q(device=sql_info.effective_device.pk))
                        )
                    except var_obj.DoesNotExist:
                        # check other types
                        other_var = None
                        for other_var_obj in other_types:
                            try:
                                other_var = other_var_obj.objects.get(
                                    Q(name=real_k_name) & Q(config=sql_info.config) & (
                                        Q(device=0) | Q(device=None) | Q(device=sql_info.effective_device.pk)
                                    )
                                )
                            except other_var_obj.DoesNotExist:
                                pass
                            else:
                                break
                        if other_var is not None:
                            # other var found, delete
                            other_var.delete()
                        # description
                        _new_var = var_obj(
                            name=real_k_name,
                            description="",
                            config=sql_info.config,
                            device=None,
                            value=self[key],
                        )
                        _new_var.save()
                    else:
                        if self[key] != cur_var.value:
                            cur_var.value = self[key]
                            cur_var.save()
                    # update description
                    _cur_descr = cur_var.description or ""
                    if self.help_string(key):
                        new_descr = strip_description(self.help_string(key))
                    else:
                        new_descr = "{} default value from {} on {}".format(
                            var_range_name,
                            sql_info.config_name,
                            sql_info.short_host_name,
                        )
                    if new_descr and new_descr != _cur_descr and _cur_descr.count("default value from"):
                        cur_var.description = new_descr
                        cur_var.save(update_fields=["description"])
                else:
                    # print "X", key
                    pass


def get_global_config(c_name, single_process_mode=False, mc_enabled=True):
    return Configuration(
        c_name,
        single_process_mode=single_process_mode,
        mc_enabled=mc_enabled
    )
