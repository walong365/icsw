# Copyright (C) 2001-2009,2011-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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
""" module for handling config files """

import argparse
import datetime
import grp
import os
import pwd
import re
import sys
import threading
from collections import OrderedDict
from multiprocessing import current_process, util, forking, managers
from multiprocessing.managers import BaseManager, BaseProxy, Server

from initat.tools import logging_tools, process_tools


class config_proxy(BaseProxy):
    def add_config_entries(self, ce_list, **kwargs):
        return self._callmethod("add_config_entries", (ce_list,), kwargs)

    def handle_commandline(self, **kwargs):
        kwargs["proxy_call"] = True
        ret_value, exit_code = self._callmethod("handle_commandline", [], kwargs)
        # handle exit code
        if exit_code is not None:
            sys.exit(exit_code)
        return ret_value

    def get_log(self, **kwargs):
        return self._callmethod("get_log", [], kwargs)

    def fixed(self, key):
        return self._callmethod("fixed", (key,))

    def get_type(self, key):
        return self._callmethod("get_type", (key,))

    def is_global(self, key):
        return self._callmethod("is_global", (key,))

    def set_global(self, key, value):
        return self._callmethod("set_global", (key, value))

    def database(self, key):
        return self._callmethod("database", (key,))

    def keys(self):
        return self._callmethod("keys")

    def __getitem__(self, key):
        return self._callmethod("__getitem__", (key,))

    def __delitem__(self, key):
        return self._callmethod("__delitem__", (key,))

    def get_source(self, key):
        return self._callmethod("get_source", (key,))

    def get(self, key, default):
        return self._callmethod("get", (key, default))

    def __setitem__(self, key, value):
        return self._callmethod("__setitem__", (key, value))

    def __contains__(self, key):
        return self._callmethod("__contains__", (key,))

    def parse_file(self, *args, **kwargs):
        return self._callmethod("parse_file", (args), kwargs)

    def get_config_info(self):
        return self._callmethod("get_config_info")

    def single_process_mode(self):
        return self._callmethod("single_process_mode")

    def name(self):
        return self._callmethod("name")

    def get_argument_stuff(self):
        return self._callmethod("get_argument_stuff")

    def help_string(self, key):
        return self._callmethod("help_string", (key,))

    def set_uid_gid(self, uid, gid):
        if isinstance(uid, basestring):
            uid = pwd.getpwnam(uid)[2]
        if isinstance(gid, basestring):
            gid = grp.getgrnam(gid)[2]
        cur_address = self._manager.address
        addr_path = os.path.dirname(cur_address)
        os.chown(addr_path, uid, gid)
        os.chown(cur_address, uid, gid)
        return self._callmethod("set_uid_gid", (uid, gid))


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
            "only_commandline", "info", "source", "fixed", "action",
            "help_string", "short_options", "choices", "nargs", "database",
        }
        if kw_keys:
            print "*** {} for _conf_var('{}') left: {} ***".format(
                logging_tools.get_plural("keyword argument", len(kw_keys)),
                str(self.value),
                ", ".join(sorted(kw_keys)),
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
        return type(val) == type(datetime.datetime.now())


class timedelta_c_var(_conf_var):
    descr = "Timedelta"
    short_type = "dtd"
    long_time = "timedelta"

    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)

    def check_type(self, val):
        return type(val) == type(datetime.timedelta(1))


class configuration(object):
    def __init__(self, name, *args, **kwargs):
        self.__name = name
        self.__verbose = kwargs.get("verbose", False)
        self.__spm = kwargs.pop("single_process_mode", False)
        self.__c_dict = OrderedDict()
        self.clear_log()
        if args:
            self.add_config_entries(*args)

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
    # def copy_flags(self, var_dict):
    #    # copy flags (right now only global / local) for given var_names
    #    for var_name, var_value in var_dict.iteritems():
    #        self.__c_dict[var_name].is_global = var_value.is_global()

    def set_uid_gid(self, new_uid, new_gid):
        os.setgid(new_gid)
        os.setegid(new_gid)
        os.setuid(new_uid)
        os.seteuid(new_uid)

    def single_process_mode(self):
        return self.__spm

    def help_string(self, key):
        return self.__c_dict[key]._help_string

    def get_var(self, key):
        return self.__c_dict[key]

    def add_config_entries(self, entries, **kwargs):
        if type(entries) == dict:
            entries = sorted([(key, value) for key, value in entries.iteritems()])
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

    def pretty_print(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].pretty_print()
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def __getitem__(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].value
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def __delitem__(self, key):
        if key in self.__c_dict:
            del self.__c_dict[key]
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def __setitem__(self, key, value):
        if key in self.__c_dict:
            if type(value) == tuple:
                value, source = value
            else:
                source = None
            self.__c_dict[key].set_value(value, source)
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

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

    def get_source(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].source
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def fixed(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].fixed
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def is_global(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].is_global
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def set_global(self, key, value):
        if key in self.__c_dict:
            self.__c_dict[key].is_global = value
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def database(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].database
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def get_type(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].short_type
        else:
            raise KeyError("Key {} not found in c_dict".format(key))

    def parse_file(self, *args, **kwargs):
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

    def handle_commandline(self, **kwargs):
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
                    options, rest_args = (my_parser.parse_args(), [])
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


class my_server(Server):
    def serve_forever(self):
        """
        Run the server forever, modified version to prevent early exit.
        """
        if sys.version_info[0] == 3:
            self.stop_event = threading.Event()
        current_process()._manager_server = self
        _run = True
        try:
            while _run:
                try:
                    while True:
                        try:
                            c = self.listener.accept()
                        except (OSError, IOError):
                            continue
                        _thread = threading.Thread(target=self.handle_request, args=(c,))
                        _thread.daemon = True
                        _thread.start()
                except (KeyboardInterrupt):
                    pass
                except (SystemExit):
                    # system exit requested, exit loop
                    _run = False
                except:
                    raise
        finally:
            self.stop = 999
            self.listener.close()


class config_manager(BaseManager):
    # monkey-patch Server
    _Server = my_server

    @staticmethod
    def _finalize_manager(process, address, authkey, state, _Client):
        '''
        Shutdown the manager process; will be registered as a finalizer
        '''
        if process.is_alive():
            util.info('sending shutdown message to manager')
            try:
                conn = _Client(address, authkey=authkey)
                try:
                    forking.dispatch(conn, None, 'shutdown')
                finally:
                    conn.close()
            except Exception:
                pass
            process.join(timeout=0.2)
            if process.is_alive():
                util.info('manager still alive')
                if hasattr(process, 'terminate'):
                    util.info('trying to `terminate()` manager process')
                    process.terminate()
                    process.join(timeout=0.1)
                    if process.is_alive():
                        util.info('manager still alive after terminate')

        state.value = managers.State.SHUTDOWN
        try:
            del BaseProxy._address_to_local[address]
        except KeyError:
            pass

config_manager.register(
    "config",
    configuration,
    config_proxy,
    exposed=[
        "parse_file", "add_config_entries", "set_uid_gid",
        "single_process_mode", "help_string",
        "get_log", "handle_commandline", "keys", "get_type", "get", "get_source",
        "is_global", "database", "is_global", "set_global",
        "__getitem__", "__setitem__", "__contains__", "__delitem__",
        "get_config_info", "name", "get_argument_stuff", "fixed",
    ]
)

cur_manager = config_manager()

CONFIG_MANAGER_INIT = False


def get_global_config(c_name, single_process=False, ignore_lock=False):
    # lock against double-init, for instance md-config-server includes process_monitor_mod which
    # in turn tries to start the global_config manager (but from a different module)
    if not globals()["CONFIG_MANAGER_INIT"] or ignore_lock:
        globals()["CONFIG_MANAGER_INIT"] = True
        if single_process:
            return configuration(c_name, single_process_mode=True)
        else:
            cur_manager.start()
            _ret = cur_manager.config(c_name)
            globals()["CONFIG_MANAGER"] = _ret
            return _ret
    else:
        return globals()["CONFIG_MANAGER"]


# not needed ?
def terminate_manager():
    cur_manager.shutdown()


class gc_proxy(object):
    def __init__(self, g_config):
        self.global_config = g_config
        self.__dict = {}

    def __getitem__(self, key):
        if key not in self.__dict:
            self.__dict[key] = self.global_config[key]
        return self.__dict[key]


def enable_config_access(user_name, group_name):
    address = cur_manager.address
    process_tools.change_user_group_path(address, user_name, group_name)
    process_tools.change_user_group_path(os.path.dirname(address), user_name, group_name)


def get_manager_pid():
    if cur_manager.address:
        return cur_manager._process.pid
    else:
        return None


# type:
# 0 ... only read the file,  strip empty- and comment lines
# 1 ... parse the lines according to VAR = ARG,  return dictionary
def readconfig(name, c_type=0, in_array=[]):
    ret_code, ret_array = (False, [])
    try:
        rcf = [y for y in [x.strip() for x in file(name, "r").read().split("\n")] if y and not re.match("^\s*#.*$", y)]
    except:
        pass
    else:
        if c_type == 0:
            ret_code, ret_array = (True, rcf)
        elif c_type == 1:
            cd = {_key: [] for _key in in_array}
            for line in rcf:
                lm = re.match("^\s*(?P<key>[^=]+)\s*=\s*(?P<value>\S+)\s*$", line)
                if lm:
                    act_k = lm.group("key").strip()
                    arg = lm.group("value").strip()
                    if act_k in in_array:
                        cd[act_k].append(arg)
                    else:
                        cd[act_k] = arg
            ret_code, ret_array = (True, cd)
        else:
            print("Unknown type {:d} for readconfig".format(c_type))
    return (ret_code, ret_array)


def check_str_config(in_dict, name, default):
    if not in_dict:
        in_dict = {}
    if name in in_dict:
        av = in_dict[name]
    else:
        av = default
    in_dict[name] = av
    return in_dict


def check_flag_config(in_dict, name, default):
    if not in_dict:
        in_dict = {}
    if name in in_dict:
        try:
            av = int(in_dict[name])
        except:
            av = default
        if av < 0 or av > 1:
            av = default
    else:
        av = default
    in_dict[name] = av
    return in_dict


def check_int_config(in_dict, name, default, minv=None, maxv=None):
    if not in_dict:
        in_dict = {}
    if name in in_dict:
        try:
            av = int(in_dict[name])
        except:
            av = default
        if minv:
            av = max(av, minv)
        if maxv:
            av = min(av, maxv)
    else:
        av = default
    in_dict[name] = av
    return in_dict
