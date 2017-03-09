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
import functools
import json

from initat.tools import logging_tools


class BaseConfigVar(object):
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
                    logging_tools.get_plural(
                        "keyword argument", len(kw_keys)
                    ),
                    str(self.value),
                    ", ".join(sorted(kw_keys)),
                )
            )

    def serialize(self):
        if self.descr in ["Blob"]:
            _val = base64.b64encode(
                bz2.compress(self.value)
            ).decode("ascii")
            _def_val = base64.b64encode(
                bz2.compress(self.__default_val)
            ).decode("ascii")
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
            raise TypeError(
                "Type Error for value {}".format(
                    str(val)
                )
            )
        except ValueError:
            raise ValueError(
                "Value Error for value {}".format(
                    str(val)
                )
            )
        else:
            if isinstance(r_val, tuple) or isinstance(r_val, list):
                _c_val = set(r_val)
            else:
                _c_val = set([r_val])
            self.value = r_val
            if source and (
                source != "default" or self.source == "default"
            ):
                self.source = source

    def __str__(self):
        return "{} (source {}) : {}".format(
            self.descr,
            self.source,
            self.pretty_print()
        )


class IntegerConfigVar(BaseConfigVar):
    descr = "Integer"
    short_type = "i"
    long_type = "int"
    argparse_type = int

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return int(val)

    def check_type(self, val):
        return isinstance(val, int)


class FloatConfigVar(BaseConfigVar):
    descr = "Float"
    short_type = "f"
    long_type = "float"
    argparse_type = float

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return float(val)

    def check_type(self, val):
        return isinstance(val, float)


class StringConfigVar(BaseConfigVar):
    descr = "String"
    short_type = "s"
    long_type = "str"
    argparse_type = str

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return str(val)

    def check_type(self, val):
        return isinstance(val, str)


class BlobConfigVar(BaseConfigVar):
    # holds bytestrings
    descr = "Blob"
    short_type = "B"
    long_type = "blob"

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

    def str_to_val(self, val):
        return str(val)

    def check_type(self, val):
        return isinstance(val, bytes)

    def pretty_print(self):
        return "blob with len {:d}".format(len(self.act_val))


class BoolConfigVar(BaseConfigVar):
    descr = "Bool"
    short_type = "b"
    long_type = "bool"

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

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


class ArrayConfigVar(BaseConfigVar):
    descr = "Array"
    short_type = "a"
    long_type = "array"
    argparse_type = str

    def __init__(self, def_val, **kwargs):
        BaseConfigVar.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return isinstance(val, list) or isinstance(val, str)


# the following 3 vars are no longer in use, commented them out
# class dict_c_var(_conf_var):
#     descr = "Dict"
#     short_type = "d"
#     long_type = "dict"
#
#     def __init__(self, def_val, **kwargs):
#         _conf_var.__init__(self, def_val, **kwargs)
#
#     def check_type(self, val):
#         return isinstance(val, dict)
#
#
# class datetime_c_var(_conf_var):
#     descr = "Datetime"
#     short_type = "ddt"
#     long_type = "datetime"
#
#     def __init__(self, def_val, **kwargs):
#         _conf_var.__init__(self, def_val, **kwargs)
#
#     def check_type(self, val):
#         return isinstance(val, datetime.datetime)
#
#
# class timedelta_c_var(_conf_var):
#     descr = "Timedelta"
#     short_type = "dtd"
#     long_time = "timedelta"
#
#     def __init__(self, def_val, **kwargs):
#         _conf_var.__init__(self, def_val, **kwargs)
#
#     def check_type(self, val):
#         return isinstance(val, datetime.timedelta)


class ProcessBasedDict(object):
    def __init__(self):
        self.__process_obj = None
        self._dict = {}
        self._keys = set()

    def set_process_obj(self, process_obj: object):
        self.__process_obj = process_obj
        self.__process_obj.register_func("gc_operation", self.gc_operation)

    def gc_operation(self, *args, **kwargs):
        if args[0] == "change":
            # change operation
            key, ser_str = args[1:3]
            _json = json.loads(ser_str)
            _is_blob = _json["descr"] in ["Blob"]
            if _is_blob:
                _json["default_value"] = bz2.decompress(
                    base64.b64decode(
                        _json["default_value"]
                    )
                )
            # get correct variable type for instantiation
            _obj = {
                # "Timedelta": timedelta_c_var,
                # "Datetime": datetime_c_var,
                # "Dict": dict_c_var,
                "Array": ArrayConfigVar,
                "Bool": BoolConfigVar,
                "Blob": BlobConfigVar,
                "String": StringConfigVar,
                "Float": FloatConfigVar,
                "Integer": IntegerConfigVar,
            }[_json["descr"]](_json["default_value"], **_json["kwargs"])
            if _is_blob:
                _obj.value = bz2.decompress(
                    base64.b64decode(
                        _json["value"]
                    )
                )
            else:
                _obj.value = _json["value"]
            # print("*", self.__process_obj.name, key, self._dict[key], "->",  _obj)
            self._dict[key] = _obj
        elif args[0] == "delete":
            key = args[1]
            # print("d", key)
            if key in self._keys:
                self._keys.remove(key)
                del self._dict[key]
        else:
            print("unknown gc_operation", args, kwargs)

    # public functions

    def keys(self):
        return self._keys

    def __contains__(self, _key):
        return _key in self._keys

    def __setitem__(self, key, value):
        # print os.getpid(), "store", key
        if key not in self._keys:
            self._keys.add(key)
        self._dict[key] = value
        if self.__process_obj:
            self.__process_obj.send_to_all_processes(
                "gc_operation",
                "change",
                key,
                self._dict[key].serialize()
            )

    def __getitem__(self, key):
        return self._dict[key]

    def __delitem__(self, key):
        # self._check_mc()
        self._keys.remove(key)
        del self._dict[key]
        if self.__process_obj:
            # we will get the message back if we send this from a child process
            # so we have to check for key existance in the delete operation above
            self.__process_obj.send_to_all_processes(
                "gc_operation",
                "delete",
                key
            )

    def key_changed(self, key):
        # called when a key has changed from Configuration
        if self.__process_obj:
            self.__process_obj.send_to_all_processes(
                "gc_operation",
                "change",
                key,
                self._dict[key].serialize()
            )


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
            raise KeyError(
                "Key {} not defined ({})".format(
                    args[0],
                    self.config.key_info
                )
            )


class Configuration(object):
    def __init__(self, name, *args, **kwargs):
        self.__mc_enabled = kwargs.get("mc_enabled", True)
        self.__name = name
        self.__spm = kwargs.pop("single_process_mode", False)
        self.__c_dict = ProcessBasedDict()
        self.clear_log()
        if args:
            self.add_config_entries(*args)

    def as_dict(self):
        return {key: self.__c_dict[key].value for key in self.keys()}

    def enable_pm(self, process_obj: object):
        # enable process backend, set process pool (or process object) for key changes
        self.__c_dict.set_process_obj(process_obj)

    def delete(self):
        # remove global config
        _keys = list(self.keys())
        for key in _keys:
            del self[key]

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
            entries = sorted(
                [
                    (key, value) for key, value in entries.items()
                ]
            )
        self.__c_dict.update_mode = True
        for key, value in entries:
            # check for override of database flag
            if "database" in kwargs and not value.database_flag_set:
                value.database = kwargs["database"]
            self.__c_dict[key] = value
        self.__c_dict.update_mode = False

    @property
    def key_info(self):
        return "{}".format(
            ", ".join(
                sorted(self.__c_dict.keys())
            )
        )

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
            # print("G", key, value, source)
            self.__c_dict[key].set_value(value, source)
            # import the signal changes
            self.__c_dict.key_changed(key)
        else:
            raise KeyError(
                "Key {} not known ({})".format(
                    key,
                    self.key_info,
                )
            )

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
                            logging_tools.form_entry(
                                "list with {}:".format(
                                    logging_tools.get_plural("entry", len(pv))
                                )
                            ),
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
                            logging_tools.form_entry(
                                self.pretty_print(key),
                                header="value"
                            ),
                            logging_tools.form_entry(
                                self.get_type(key),
                                pre_str=", (",
                                post_str=" from ",
                                header="type"
                            ),
                            logging_tools.form_entry(
                                self.get_source(key),
                                post_str=")",
                                header="source"
                            ),
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

    def from_database(self, sc_result, init_list=[]):
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
        if sc_result.effective_device:
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
                        Q(
                            name__in=[
                                var_name for var_name, _var_value in init_list
                            ]
                        )
                    )
                for db_rec in src_sql_obj.filter(
                    Q(config=sc_result.config) &
                    Q(config__device_config__device=sc_result.effective_device)
                ).order_by("name"):
                    var_name = db_rec.name
                    source = "{}_table (pk={})".format(short, db_rec.pk)
                    if isinstance(db_rec.value, array.array):
                        new_val = configfile.StringConfigVar(
                            db_rec.value.tostring(),
                            source=source
                        )
                    elif short == "int":
                        new_val = configfile.IntegerConfigVar(
                            int(db_rec.value),
                            source=source
                        )
                    elif short == "bool":
                        new_val = configfile.BoolConfigVar(
                            bool(db_rec.value),
                            source=source
                        )
                    else:
                        new_val = configfile.StringConfigVar(
                            db_rec.value,
                            source=source
                        )
                    _present_in_config = var_name in self
                    if _present_in_config:
                        # copy settings from config
                        new_val.database = self.database(var_name)
                        new_val.help_string = self.help_string(var_name)
                    self.add_config_entries([(var_name.upper(), new_val)])

    def to_database(self, sc_result):
        from django.db.models import Q
        from initat.cluster.backbone.models import config_blob, \
            config_bool, config_int, config_str

        def strip_description(descr):
            if descr:
                descr = " ".join(
                    [
                        entry for entry in descr.strip().split() if not entry.count(
                            "(default)"
                        )
                    ]
                )
            return descr

        type_dict = {
            "i": config_int,
            "s": config_str,
            "b": config_bool,
            "B": config_blob,
        }
        if sc_result.effective_device and sc_result.config:
            for key in sorted(self.keys()):
                # print k,config.get_source(k)
                # print "write", k, config.get_source(k)
                # if config.get_source(k) == "default":
                # only deal with int and str-variables
                var_obj = type_dict.get(self.get_type(key), None)
                # print key, var_obj, self.database(key)
                if var_obj is not None and self.database(key):
                    other_types = set(
                        [
                            value for _key, value in list(
                                type_dict.items()
                            ) if _key != self.get_type(key)
                        ]
                    )
                    # var global / local
                    var_range_name = "global"
                    # build real var name
                    real_k_name = key
                    try:
                        cur_var = var_obj.objects.get(
                            Q(name=real_k_name) &
                            Q(config=sc_result.config) &
                            (
                                Q(device=0) |
                                Q(device=None) |
                                Q(device=sc_result.effective_device.pk)
                            )
                        )
                    except var_obj.DoesNotExist:
                        # check other types
                        other_var = None
                        for other_var_obj in other_types:
                            try:
                                other_var = other_var_obj.objects.get(
                                    Q(name=real_k_name) &
                                    Q(config=sc_result.config) &
                                    (
                                        Q(device=0) |
                                        Q(device=None) |
                                        Q(device=sc_result.effective_device.pk)
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
                        cur_var = var_obj(
                            name=real_k_name,
                            description="",
                            config=sc_result.config,
                            device=None,
                            value=self[key],
                        )
                        cur_var.save()
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
                            sc_result.config.name,
                            sc_result.effective_device.name,
                        )
                    if new_descr and new_descr != _cur_descr and _cur_descr.count(
                        "default value from"
                    ):
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
