#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012 Andreas Lang-Nevyjel, init.at
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
""" module for handling config files and extracting routes to configurations """

import os
import os.path
import re
import sys
import process_tools
import logging_tools
import array
import socket
import datetime
import config_tools
import types
import argparse
from collections import OrderedDict
import threading
from django.db.models import Q
from multiprocessing import Manager, current_process
from multiprocessing.managers import BaseManager, BaseProxy, DictProxy, Server
from init.cluster.backbone.models import device_variable, new_config, device, config_blob, config_bool, config_int, config_str, net_ip
import netifaces

class config_proxy(BaseProxy):
    def add_config_entries(self, ce_list, **kwargs):
        return self._callmethod("add_config_entries", (ce_list, ), kwargs)
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
                opts = "--%s" % (self._short_opts)
            else:
                opts = "-%s" % (self._short_opts)
        else:
            opts = "--%s" % (name.lower())
        kwargs = {"dest" : name,
                  "help" : self._help_string}
        if self._choices:
            kwargs["choices"] = self._choices
        if self._nargs:
            kwargs["nargs"] = self._nargs
        if self.argparse_type == None:
            if self.short_type == "b":
                # bool
                if self._only_commandline:
                    arg_parser.add_argument(opts, action="store_%s" % ("false" if self.__default_val else "true"), default=self.__default_val, **kwargs)
                else:
                    arg_parser.add_argument(opts, action="store_%s" % ("false" if self.value else "true"), default=self.value, **kwargs)
            else:
                print "*? unknown short_type in _conf_var ?*", self.short_type, name, self.argparse_type
        else:
            arg_parser.add_argument(opts, type=self.argparse_type, default=self.value, **kwargs)
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
    #def copy_flags(self, var_dict):
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
    def get(self, key, default):
        return self.__c_dict.get(key, default)
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
                #file(file_name, "w").write("\n".join(["# %s \n%s\n%s = %s\n" % (self.__c_dict[k],
                #                                                                self.__c_dict[k].get_info() and "# %s \n" % (self.__c_dict[k].get_info()) or "",
                #                                                                k,
                #                                                                self.__c_dict[k].get_value()) for k in all_keys] + [""]))
                file(file_name, "w").write("\n".join(sum([[
                    "# %s" % (self.__c_dict[key]),
                    "# %s" % (self.__c_dict[key].get_info() if self.__c_dict[key].get_info() else "no info"),
                    "# %s" % (self.__c_dict[key].get_commandline_info()),
                    "%s=%s" % (key, 
                               "\"\"" if self.__c_dict[key].value == "" else self.__c_dict[key].value),
                    ""] for key in all_keys if self.get_cvar(key)._only_commandline == False],
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
                    while 1:
                        try:
                            c = self.listener.accept()
                        except (OSError, IOError):
                            continue
                        t = threading.Thread(target=self.handle_request, args=(c,))
                        t.daemon = True
                        t.start()
                except (KeyboardInterrupt, SystemExit):
                    #print "+++", process_tools.get_except_info()
                    pass
        finally:
            #print "***", process_tools.get_except_info()
            self.stop = 999
            self.listener.close()

class config_manager(BaseManager):
    # monkey-patch Server
    _Server = my_server

config_manager.register("config", configuration, config_proxy, exposed=[
    "parse_file", "add_config_entries", "set_uid_gid",
    "get_log", "handle_commandline", "keys", "get_type", "get", "get_source",
    "is_global", "database",
    "__getitem__", "__setitem__", "__contains__",
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
    
##def reload_global_config(dc, gcd, server_type, host_name = ""):
##    if not host_name:
##        host_name = socket.gethostname().split(".")[0]
##    num_serv, serv_idx, s_type, s_str, config_idx, real_config_name = is_server(dc, server_type, True, False, host_name.split(".")[0])
##    # read global configs
##    if num_serv:
##        # dict of local vars without specified host
##        l_var_wo_host = {}
##        for short in ["str",
##                      "int",
##                      "blob",
##                      "bool"]:
##            # very similiar code appears in config_tools.py
##            sql_str = "SELECT cv.* FROM new_config c INNER JOIN device_config dc LEFT JOIN config_%s cv ON cv.new_config=c.new_config_idx WHERE (cv.device=0 OR cv.device=%d) AND dc.device=%d AND dc.new_config=c.new_config_idx AND c.name='%s' ORDER BY cv.device, cv.name" % (short, config_idx, serv_idx, real_config_name)
##            dc.execute(sql_str)
##            for db_rec in [y for y in dc.fetchall() if y["name"]]:
##                if db_rec["name"].count(":"):
##                    var_global = False
##                    local_host_name, var_name = db_rec["name"].split(":", 1)
##                else:
##                    var_global = True
##                    local_host_name, var_name = (host_name, db_rec["name"])
##                if type(db_rec["value"]) == type(array.array("b")):
##                    new_val = str_c_var(db_rec["value"].tostring(), source="%s_table" % (short))
##                elif short == "int":
##                    new_val = int_c_var(int(db_rec["value"]), source="%s_table" % (short))
##                elif short == "bool":
##                    new_val = bool_c_var(bool(db_rec["value"]), source="%s_table" % (short))
##                else:
##                    new_val = str_c_var(db_rec["value"], source="%s_table" % (short))
##                new_val.is_global = var_global
##                if local_host_name == host_name:
##                    if var_name.upper() in gcd and gcd.fixed(var_name.upper()):
##                        # present value is fixed, keep value, only copy global / local status
##                        gcd.copy_flags({var_name.upper() : new_val})
##                    else:
##                        gcd.add_config_dict({var_name.upper() : new_val})
##                elif local_host_name == "":
##                    l_var_wo_host[var_name.upper()] = new_val
##        # check for vars to insert
##        for wo_var_name, wo_var in l_var_wo_host.iteritems():
##            if not wo_var_name in gcd or gcd.get_source(wo_var_name) == "default":
##                gcd.add_config_dict({wo_var_name : wo_var})
    
def read_config_from_db(g_config, dc, server_type, init_list=[], host_name="", **kwargs):
    if not host_name:
        # AL 20120401 **kwargs delete, FIXME ?
        host_name = process_tools.get_machine_name()
    g_config.add_config_entries(init_list, database=True)
    if dc is not None:
        num_serv, serv_idx, s_type, s_str, config_idx, real_config_name=is_server(dc, server_type.replace("%", ""), True, False, host_name.split(".")[0])
        #print num_serv, serv_idx, s_type, s_str, config_idx, real_config_name
        if num_serv:
            # dict of local vars without specified host
            l_var_wo_host = {}
            for short in ["str",
                          "int",
                          "blob",
                          "bool"]:
                # very similiar code appears in config_tools.py
                #sql_str = "SELECT cv.* FROM new_config c INNER JOIN device_config dc LEFT JOIN config_%s cv ON cv.new_config=c.new_config_idx WHERE (cv.device=0 OR cv.device=%d) AND dc.device=%d AND dc.new_config=c.new_config_idx AND c.name='%s' ORDER BY cv.device, cv.name" % (short, config_idx, serv_idx, real_config_name)
                #dc.execute(sql_str)
                for db_rec in globals()["config_%s" % (short)].objects.filter(
                    (Q(device=0) | Q(device=None) | Q(device=serv_idx)) &
                    (Q(new_config__name=real_config_name)) &
                    (Q(new_config__device_config__device=serv_idx))):
                    if db_rec.name.count(":"):
                        var_global = False
                        local_host_name, var_name = db_rec.name.split(":", 1)
                    else:
                        var_global = True
                        local_host_name, var_name = (host_name, db_rec.name)
                    if type(db_rec.value) == type(array.array("b")):
                        new_val = str_c_var(db_rec.value.tostring(), source="%s_table" % (short))
                    elif short == "int":
                        new_val = int_c_var(int(db_rec.value), source="%s_table" % (short))
                    elif short == "bool":
                        new_val = bool_c_var(bool(db_rec.value), source="%s_table" % (short))
                    else:
                        new_val = str_c_var(db_rec.value, source="%s_table" % (short))
                    present_in_config = var_name in g_config
                    if present_in_config:
                        # copy settings from config
                        new_val.database = g_config.database(var_name)
                    new_val.is_global = var_global
                    if local_host_name == host_name:
                        if var_name.upper() in g_config and g_config.fixed(var_name.upper()):
                            # present value is fixed, keep value, only copy global / local status
                            g_config[var_name.upper].is_global = new_val.is_global
                        else:
                            g_config.add_config_entries([(var_name.upper(), new_val)])
                    elif local_host_name == "":
                        l_var_wo_host[var_name.upper()] = new_val
            # check for vars to insert
            for wo_var_name, wo_var in l_var_wo_host.iteritems():
                if not wo_var_name in g_config or g_config.get_source(wo_var_name) == "default":
                    g_config.add_config_entries([(wo_var_name, wo_var)])
    else:
        print "dc is None in read_config_from_db", server_type, kwargs
    
def read_global_config(dc, server_type, init_dict=None, host_name=""):
    if init_dict is None:
        init_dict = {}
    gcd = configuration(server_type.replace("%", ""), init_dict)
    reload_global_config(dc, gcd, server_type, host_name)
    return gcd

class db_device_variable(object):
    def __init__(self, dc, dev_idx, var_name, **kwargs):
        self.__dev_idx = dev_idx
        self.__var_name = var_name
        self.__var_type, self.__description = (None, "not set")
        try:
            act_dv = device_variable.objects.get(Q(name=var_name) & Q(device=dev_idx))
        except device_variable.DoesNotExist:
            self.__act_dv = None
        else:
            self.__act_dv = act_dv
            self.set_stuff(var_type = act_dv.var_type,
                           description = act_dv.description)
            self.set_value(getattr(act_dv, "val_%s" % (self.__var_type_name)), type_ok=True)
        self.set_stuff(**kwargs)
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if (not self.__act_dv and "value" in kwargs) or kwargs.get("force_update", False):
            # update if device_variable not found and kwargs[value] is set
            self.update(dc)
    def update(self, dc):
        if self.__act_dv:
            self.__act_dv.description = self.__description
            self.__act_dv.var_type = self.__var_type
            setattr(self.__act_dv, "val_%s" % (self.__var_type_name), self.__var_value)
            self.__act_dv.save()
##            dc.execute("UPDATE device_variable SET val_%s=%%s, description=%%s, var_type=%%s WHERE device_variable_idx=%%s" % (self.__var_type_name),
##                       (self.__var_value,
##                        self.__description,
##                        self.__var_type,
##                        self.__var_idx))
        else:
            self.__act_dv = device_variable(
                description=self.__description,
                var_type=self.__var_type,
                name=self.__var_name)
            setattr(self.__act_dv, "val_%s" % (self.__var_type_name), self.__var_type)
            self.__act_dv.save()
##            dc.execute("INSERT INTO device_variable SET val_%s=%%s, description=%%s, var_type=%%s, name=%%s, device=%%s" % (self.__var_type_name),
##                       (self.__var_value,
##                        self.__description,
##                        self.__var_type,
##                        self.__var_name,
##                        self.__dev_idx))
##            self.__var_idx = dc.insert_id()
    def is_set(self):
        return True if self.__act_dv else False
    def set_stuff(self, **kwargs):
        if "value" in kwargs:
            self.set_value(kwargs["value"])
        if "var_type" in kwargs:
            self.__var_type = kwargs["var_type"]
            self.__var_type_name = {"s" : "str",
                                    "i" : "int" ,
                                    "b" : "blob",
                                    "t" : "time",
                                    "d" : "date"}[self.__var_type]
        if "description" in kwargs:
            self.__description = kwargs["description"]
    def set_value(self, value, type_ok=False):
        if not type_ok:
            if type(value) == type(""):
                v_type = "s"
            elif type(value) in [type(0), type(0L)]:
                v_type = "i"
            elif type(value) == type(datetime.datetime(2007, 3, 8)):
                v_type = "d"
            elif type(value) == type(datetime.time()):
                v_type = "t"
            else:
                v_type = "b"
            self.set_stuff(var_type=v_type)
        self.__var_value = value
    def get_value(self):
        return self.__var_value
        
def write_config(dc, server_type, config):
    log_lines = []
    full_host_name = socket.gethostname()
    host_name = full_host_name.split(".")[0]
    srv_info = config_tools.server_check(dc=dc, server_type=server_type, short_host_name=host_name)
    if srv_info.num_servers and srv_info.config_idx:
        for key in config.keys():
            #print k,config.get_source(k)
            #print "write", k, config.get_source(k)
            #if config.get_source(k) == "default":
            # only deal with int and str-variables
            tab_type = {"i" : "int",
                        "s" : "str",
                        "b" : "bool"}.get(config.get_type(key), None)
            if tab_type and config.database(key):
                # var global / local
                var_range_name = config.is_global(key) and "global" or "local"
                # build real var name
                real_k_name = config.is_global(key) and key or "%s:%s" % (host_name, key)
                var_obj = globals()["config_%s" % (tab_type)]
                try:
                    cur_var = var_obj.objects.get(
                        Q(name=real_k_name) &
                        (Q(device=0) | Q(device=None) | Q(device=srv_info.server_device_idx)) &
                        Q(new_config__device_config__device__device_group__device_group=srv_info.server_device_idx)
                    )
                except var_obj.DoesNotExist:
                    var_obj(name=real_k_name,
                            descr="%s default value from %s on %s" % (
                                var_range_name,
                                srv_info.config_name,
                                full_host_name),
                            new_config=new_config.objects.get(Q(pk=srv_info.config_idx)),
                            value=config[key]).save()
                else:
                    if config[key] != cur_var.value:
                        cur_var.value = config[key]
                        cur_var.save()
            else:
                #print "X", key
                pass
    return log_lines

class device_recognition(object):
    def __init__(self, dc, **args):
        self.short_host_name = args.get("short_host_name", socket.getfqdn(socket.gethostname()).split(".")[0])
        try:
            self.device_idx = device.objects.get(Q(name=self.short_host_name)).pk
        except device.DoesNotExist:
            self.device_idx = 0
        self.device_dict = {}
        # get IP-adresses (from IP)
        self.local_ips = net_ip.objects.filter(Q(netdevice__device__name=self.short_host_name)).values_list("ip", flat=True)
        # get configured IP-Adresses
        if_names = netifaces.interfaces()
        ipv4_dict = dict([(cur_if_name, [ip_tuple["addr"] for ip_tuple in value[2]][0]) for cur_if_name, value in [(if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()] if 2 in value])
        self_ips = ipv4_dict.values()
        if self_ips:
            self.device_dict = dict([(cur_dev.pk, cur_dev.name) for cur_dev in device.objects.filter(Q(netdevice__net_ip__ip__in=self_ips))])
##            sql_str = "SELECT d.name, d.device_idx FROM device d, netdevice n, netip i WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND (%s)" % (" OR ".join(["i.ip='%s'" % (ip) for ip in self_ips]))
##            dc.execute(sql_str)
##            self.device_dict = dict([(x["device_idx"], x["name"]) for x in dc.fetchall()])

def is_server(dc, server_type, long_mode=False, report_real_idx=False, short_host_name=""):
    server_idx, s_type, s_str, config_idx, real_server_name = (0, "unknown", "not configured", 0, server_type)
    if server_type.count("%"):
        match_str = " LIKE('%s')" % (server_type)
        dmatch_str = "name__icontains"
        server_info_str = "%s (with wildcard)" % (server_type.replace("%", ""))
    else:
        match_str = "='%s'" % (server_type)
        dmatch_str = "name"
        server_info_str = server_type
    if dc:
        if not short_host_name:
            short_host_name = socket.getfqdn(socket.gethostname()).split(".")[0]
        # old version
        try:
            dev_pk = device.objects.get(Q(name=short_host_name)).pk
        except device.DoesNotExist:
            dev_pk = 0
        my_confs = new_config.objects.filter(
            Q(device_config__device__device_group__device_group__name=short_host_name) &
            Q(**{dmatch_str : server_type})
            ).distinct().values_list(
                "device_config__device", "pk", "name",
                "device_config__device__device_group__device_group__name")
##        sql_str = "SELECT d.name, d.device_idx, dc.new_config, c.name AS confname, dc.device FROM device d " + \
##            "INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg " + \
##            "LEFT JOIN device d2 ON d2.device_idx = dg.device WHERE d.device_group=dg.device_group_idx " + \
##            "AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND c.name%s AND d.name='%s'" % (match_str, short_host_name)
##        dc.execute(sql_str)
##        all_servers = dc.fetchall()
        num_servers = len(my_confs)
        if num_servers == 1:
            my_conf = my_confs[0]
            if my_conf[0] == dev_pk:
                s_type = "real"
            else:
                s_type = "meta"
            server_idx, s_type, s_str, config_idx, real_server_name = (my_conf[0] if report_real_idx else dev_pk,
                                                                       s_type,
                                                                       "%s '%s'-server via hostname '%s'" % (s_type, server_type, short_host_name),
                                                                       my_conf[1],
                                                                       my_conf[2])
        else:
            # get local devices
            dc.execute("SELECT i.ip FROM netip i, netdevice n, device d WHERE n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND d.name='%s'" % (short_host_name))
            local_ips = [x["ip"] for x in dc.fetchall()]
            # check for virtual-device
            dc.execute("SELECT d.device_idx, i.ip, c.name FROM netip i INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device d " + \
                       "INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device=d.device_idx AND " + \
                       "i.netdevice=n.netdevice_idx AND (d2.device_idx=dc.device OR n.device=dc.device) AND dc.new_config=c.new_config_idx AND c.name%s" % (match_str))
            all_ips = {}
            for d_x in [y for y in dc.fetchall() if y["ip"] != "127.0.0.1"]:
                if d_x["ip"] not in local_ips:
                    all_ips[d_x["ip"]] = (d_x["device_idx"], d_x["device_idx"], d_x["name"])
            if_names = netifaces.interfaces()
            ipv4_dict = dict([(cur_if_name, [ip_tuple["addr"] for ip_tuple in value[2]][0]) for cur_if_name, value in [(if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()] if 2 in value])
            self_ips = ipv4_dict.values()
            for ai in all_ips.keys():
                if ai in self_ips:
                    #dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (short_host_name))
                    num_servers, server_idx, s_type, s_str, config_idx, real_server_name = (1,
                                                                                            all_ips[ai][0],
                                                                                            "virtual",
                                                                                            "virtual '%s'-server via IP-address %s" % (server_info_str, ai),
                                                                                            all_ips[ai][1],
                                                                                            all_ips[ai][2])
    else:
        num_servers = 0
    if long_mode:
        return num_servers, server_idx, s_type, s_str, config_idx, real_server_name
    else:
        return num_servers, server_idx
