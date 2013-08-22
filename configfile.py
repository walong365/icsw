#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import os
import re
import sys
import process_tools
import logging_tools
import datetime
import types
import argparse
import pwd
import grp
from collections import OrderedDict
import threading
from multiprocessing import Manager, current_process
from multiprocessing.managers import BaseManager, BaseProxy, DictProxy, Server

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
    def write_file(self, *args):
        return self._callmethod("write_file", (args))
    def get_config_info(self):
        return self._callmethod("get_config_info")
    def name(self):
        return self._callmethod("name")
    def get_argument_stuff(self):
        return self._callmethod("get_argument_stuff")
    def set_uid_gid(self, uid, gid):
        if type(uid) in [str, unicode]:
            uid = pwd.getpwnam(uid)[2]
        if type(gid) in [str, unicode]:
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
            raise TypeError, "Type of Default-value differs from given type (%s, %s)" % (type(def_val), str(self.short_type))
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
        self._writeback = kwargs.get("writeback", True)
        self._only_commandline = kwargs.get("only_commandline", False)
    def is_commandline_option(self):
        return True if self._help_string else False
    def get_commandline_info(self):
        if self._help_string:
            return "is commandline option, help_string is '%s'" % (self._help_string)
        else:
            return "no commandline option"
    def add_argument(self, name, arg_parser):
        if self._short_opts:
            if len(self._short_opts) > 1:
                opts = ["--%s" % (self._short_opts)]
            else:
                opts = ["-%s" % (self._short_opts)]
        else:
            opts = ["--%s" % (name.lower())]
            if name.lower().count("_"):
                opts.append("--%s" % (name.lower().replace("_", "-")))
        kwargs = {"dest" : name,
                  "help" : self._help_string}
        if self._choices:
            kwargs["choices"] = self._choices
        if self._nargs:
            kwargs["nargs"] = self._nargs
        if self.argparse_type == None:
            if self.short_type == "b":
                # bool
                if self._only_commandline and not self._writeback:
                    arg_parser.add_argument(*opts, action="store_%s" % ("false" if self.__default_val else "true"), default=self.__default_val, **kwargs)
                else:
                    arg_parser.add_argument(*opts, action="store_%s" % ("false" if self.value else "true"), default=self.value, **kwargs)
            else:
                print "*? unknown short_type in _conf_var ?*", self.short_type, name, self.argparse_type
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
            raise TypeError, "Type Error for value %s" % (str(val))
        except ValueError:
            raise ValueError, "Value Error for value %s" % (str(val))
        else:
            self.value = r_val
            if source and (source != "default" or self.source == "default"):
                self.source = source
    def __str__(self):
        return "%s (source %s, %s) : %s" % (self.descr,
                                            self.source,
                                            "global" if self.__is_global else "local",
                                            self.pretty_print())
    def get_info(self):
        return self.__info

class int_c_var(_conf_var):
    descr = "Integer"
    short_type = "i"
    argparse_type = int
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def str_to_val(self, val):
        return int(val)
    def check_type(self, val):
        return type(val) in [types.IntType, types.LongType]

class float_c_var(_conf_var):
    descr = "Float"
    short_type = "f"
    argparse_type = float
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def str_to_val(self, val):
        return float(val)
    def check_type(self, val):
        return type(val) == types.FloatType

class str_c_var(_conf_var):
    descr = "String"
    short_type = "s"
    argparse_type = str
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def str_to_val(self, val):
        return str(val)
    def check_type(self, val):
        return type(val) in [types.StringType, types.UnicodeType]

class blob_c_var(_conf_var):
    descr = "Blob"
    short_type = "B"
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def str_to_val(self, val):
        return str(val)
    def check_type(self, val):
        return type(val) == types.StringType
    def pretty_print(self):
        return "blob with len %d" % (len(self.act_val))

class bool_c_var(_conf_var):
    descr = "Bool"
    short_type = "b"
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def str_to_val(self, val):
        if type(val) == type(""):
            if val.lower().startswith("t"):
                return True
            else:
                return False
        else:
            return bool(val)
    def check_type(self, val):
        return type(val) == types.BooleanType
    def pretty_print(self):
        return "True" if self.act_val else "False"

class array_c_var(_conf_var):
    descr = "Array"
    short_type = "a"
    argparse_type = str
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def check_type(self, val):
        return type(val) == types.ListType

class dict_c_var(_conf_var):
    descr = "Dict"
    short_type = "d"
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def check_type(self, val):
        return type(val) == types.DictionaryType

class datetime_c_var(_conf_var):
    descr = "Datetime"
    short_type = "ddt"
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def check_type(self, val):
        return type(val) == type(datetime.datetime.now())

class timedelta_c_var(_conf_var):
    descr = "Timedelta"
    short_type = "dtd"
    def __init__(self, def_val, **kwargs):
        _conf_var.__init__(self, def_val, **kwargs)
    def check_type(self, val):
        return type(val) == type(datetime.timedelta(1))

class configuration(object):
    def __init__(self, name, *args, **kwargs):
        self.__name = name
        self.__verbose = kwargs.get("verbose", False)
        self.__c_dict = OrderedDict()
        self.clear_log()
        self.__writeback_changes = False
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
    def add_config_entries(self, entries, **kwargs):
        if type(entries) == type({}):
            entries = [(key, value) for key, value in entries.iteritems()]
        for key, value in entries:
            # check for override of database flag
            if not value._database_set and "database" in kwargs:
                if self.__verbose:
                    self.log("override database flag for '%s', setting to '%s'" % (key, str(kwargs["database"])))
                value.database = kwargs["database"]
            if key in self.__c_dict and self.__verbose:
                self.log("Replacing config for key %s" % (key))
            self.__c_dict[key] = value
            if self.__verbose:
                self.log("Setting config for key %s to %s" % (key, value))
    def pretty_print(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].pretty_print()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def __getitem__(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].value
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def __delitem__(self, key):
        if key in self.__c_dict:
            del self.__c_dict[key]
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def __setitem__(self, key, value):
        if key in self.__c_dict:
            if type(value) == type(()):
                value, source = value
            else:
                source = None
            self.__c_dict[key].set_value(value, source)
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def get_config_info(self):
        gk = sorted(self.keys())
        if gk:
            f_obj = logging_tools.form_list()
            f_obj.set_format_string(2, "s", "-", " : ")
            f_obj.set_format_string(3, "s", "-", " , (")
            f_obj.set_format_string(4, "s", "", "from ", ")")
            for key in gk:
                if self.get_type(key) in ["a", "d"]:
                    pv = self.pretty_print(key)
                    f_obj.add_line((key, "list with %s:" % (logging_tools.get_plural("entry", len(pv))), self.get_type(key), self.get_source(key)))
                    idx = 0
                    for entry in pv:
                        f_obj.add_line(("", "", entry, str(idx), "---"))
                        idx += 1
                else:
                    f_obj.add_line((key, self.is_global(key) and "global" or "local", str(self.pretty_print(key)), self.get_type(key), self.get_source(key)))
            ret_str = str(f_obj).split("\n")
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
            raise KeyError, "Key %s not found in c_dict" % (key)
    def fixed(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].fixed
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def is_global(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].is_global
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def database(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].database
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def get_type(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].short_type
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def parse_file(self, *args, **kwargs):
        if len(args):
            file_name = args[0]
        else:
            file_name = "/etc/sysconfig/%s" % (self.__name)
        # kwargs:
        # section ... only read arugments from the given section (if found)
        scan_section = kwargs.get("section", "global")
        act_section = "global"
        pf1 = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)\s*$")
        pf2 = re.compile("^(?P<key>\S+)\s+(?P<value>.+)\s*$")
        sec_re = re.compile("^\[(?P<section>\S+)\]$")
        if os.path.isfile(file_name):
            try:
                lines = [line.strip() for line in file(file_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
            except:
                self.log("Error while reading file %s: %s" % (file_name,
                                                              process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
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
                                    self.log("Error: key %s not defined in dictionary for get_type" % (key),
                                             logging_tools.LOG_LEVEL_ERROR)
                                else:
                                    # interpret using eval
                                    if cur_type == "s":
                                        if value not in ["\"\""]:
                                            # escape strings
                                            value = "\"%s\"" % (value)
                                    try:
                                        self[key] = (eval("%s" % (value)), "%s, sec %s" % (file_name, act_section))
                                    except KeyError:
                                        self.log("Error: key %s not defined in dictionary" % (key),
                                                 logging_tools.LOG_LEVEL_ERROR)
                                    else:
                                        if self.__verbose:
                                            self.log("Changing value of key %s to %s" % (key, self.__c_dict[key]))
                            else:
                                self.log("Error parsing line '%s'" % (str(line)),
                                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("Cannot find file %s" % (file_name),
                     logging_tools.LOG_LEVEL_ERROR)
    def write_file(self, *args):
        if len(args):
            file_name = args[0]
        else:
            file_name = "/etc/sysconfig/%s" % (self.__name)
        if (not os.path.isfile(file_name)) or (os.path.isfile(file_name) and self.__writeback_changes):
            all_keys = self.__c_dict.keys()
            try:
                # file(file_name, "w").write("\n".join(["# %s \n%s\n%s = %s\n" % (self.__c_dict[k],
                #                                                                self.__c_dict[k].get_info() and "# %s \n" % (self.__c_dict[k].get_info()) or "",
                #                                                                k,
                #                                                                self.__c_dict[k].get_value()) for k in all_keys] + [""]))
                file(file_name, "w").write("\n".join(sum([[
                    "# %s" % (self.__c_dict[key]),
                    "# %s" % (self.__c_dict[key].get_info() if self.__c_dict[key].get_info() else "no info"),
                    "# %s" % (self.__c_dict[key].get_commandline_info()),
                    "%s=%s" % (key,
                               "\"\"" if self.__c_dict[key].value == "" else self.__c_dict[key].value),
                    ""] for key in all_keys if (self.get_cvar(key)._only_commandline == False and self.get_cvar(key)._writeback)],
                                                         [""])))
            except:
                self.log("Error while writing file %s: %s" % (file_name, process_tools.get_except_info()))
            else:
                pass
    def _argparse_exit(self, status=0, message=None):
        if message:
            print message
        self.exit_code = status
    def _argparse_error(self, message):
        if message:
            print "_argparse_error:", message
        self.exit_code = 2
    def get_argument_stuff(self):
        return {"positional_arguments" : self.positional_arguments,
                "other_arguments"      : self.other_arguments,
                "arg_list"             : self.positional_arguments + self.other_arguments}
    def handle_commandline(self, **kwargs):
        proxy_call = kwargs.pop("proxy_call", False)
        add_writeback_option = kwargs.pop("add_writeback_option", True)
        pos_arguments = kwargs.pop("positional_arguments", False)
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
            if add_writeback_option:
                my_parser.add_argument("--writeback", dest="writeback", default=False, action="store_true", help="write back changes to configfile [%(default)s]")
            if pos_arguments:
                my_parser.add_argument("arguments", nargs="+", help="additional arguments")
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
                self.__writeback_changes = options.writeback if add_writeback_option else False
        else:
            options = argparse.Namespace()
        if proxy_call:
            return options, self.exit_code
        else:
            return options

class my_server(Server):
    def serve_forever(self):
        '''
        Run the server forever, modified version to prevent early exit.
        '''
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
                        t = threading.Thread(target=self.handle_request, args=(c,))
                        t.daemon = True
                        t.start()
                except (KeyboardInterrupt, SystemExit):
                    # print "+++", process_tools.get_except_info()
                    pass
        finally:
            # print "***", process_tools.get_except_info()
            self.stop = 999
            self.listener.close()

class config_manager(BaseManager):
    # monkey-patch Server
    _Server = my_server

config_manager.register("config", configuration, config_proxy, exposed=[
    "parse_file", "add_config_entries", "set_uid_gid",
    "get_log", "handle_commandline", "keys", "get_type", "get", "get_source",
    "is_global", "database",
    "__getitem__", "__setitem__", "__contains__", "__delitem__",
    "write_file", "get_config_info", "name", "get_argument_stuff", "fixed"])

cur_manager = config_manager()

def get_global_config(c_name):
    cur_manager.start()
    return cur_manager.config(c_name)

def enable_config_access(user_name, group_name):
    address = cur_manager.address
    process_tools.change_user_group_path(address, user_name, group_name)
    process_tools.change_user_group_path(os.path.dirname(address), user_name, group_name)

def get_manager_pid():
    return cur_manager._process.pid

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
            cd = dict([(x, []) for x in in_array])
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
            print "Unknown type %d for readconfig" % (c_type)
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

# #def reload_global_config(dc, gcd, server_type, host_name = ""):
# #    if not host_name:
# #        host_name = socket.gethostname().split(".")[0]
# #    num_serv, serv_idx, s_type, s_str, config_idx, real_config_name = is_server(dc, server_type, True, False, host_name.split(".")[0])
# #    # read global configs
# #    if num_serv:
# #        # dict of local vars without specified host
# #        l_var_wo_host = {}
# #        for short in ["str",
# #                      "int",
# #                      "blob",
# #                      "bool"]:
# #            # very similiar code appears in config_tools.py
# #            sql_str = "SELECT cv.* FROM new_config c INNER JOIN device_config dc LEFT JOIN config_%s cv ON cv.new_config=c.new_config_idx WHERE (cv.device=0 OR cv.device=%d) AND dc.device=%d AND dc.new_config=c.new_config_idx AND c.name='%s' ORDER BY cv.device, cv.name" % (short, config_idx, serv_idx, real_config_name)
# #            dc.execute(sql_str)
# #            for db_rec in [y for y in dc.fetchall() if y["name"]]:
# #                if db_rec["name"].count(":"):
# #                    var_global = False
# #                    local_host_name, var_name = db_rec["name"].split(":", 1)
# #                else:
# #                    var_global = True
# #                    local_host_name, var_name = (host_name, db_rec["name"])
# #                if type(db_rec["value"]) == type(array.array("b")):
# #                    new_val = str_c_var(db_rec["value"].tostring(), source="%s_table" % (short))
# #                elif short == "int":
# #                    new_val = int_c_var(int(db_rec["value"]), source="%s_table" % (short))
# #                elif short == "bool":
# #                    new_val = bool_c_var(bool(db_rec["value"]), source="%s_table" % (short))
# #                else:
# #                    new_val = str_c_var(db_rec["value"], source="%s_table" % (short))
# #                new_val.is_global = var_global
# #                if local_host_name == host_name:
# #                    if var_name.upper() in gcd and gcd.fixed(var_name.upper()):
# #                        # present value is fixed, keep value, only copy global / local status
# #                        gcd.copy_flags({var_name.upper() : new_val})
# #                    else:
# #                        gcd.add_config_dict({var_name.upper() : new_val})
# #                elif local_host_name == "":
# #                    l_var_wo_host[var_name.upper()] = new_val
# #        # check for vars to insert
# #        for wo_var_name, wo_var in l_var_wo_host.iteritems():
# #            if not wo_var_name in gcd or gcd.get_source(wo_var_name) == "default":
# #                gcd.add_config_dict({wo_var_name : wo_var})

