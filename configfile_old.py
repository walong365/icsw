#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009 Andreas Lang-Nevyjel, init.at
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
import process_tools
import logging_tools
import array
import socket
import datetime
import config_tools

class c_var(object):
    def __init__(self, def_val, c_type, **args):
        self.__default_val = def_val
        self.__val_type = c_type
        self.__info = args.get("info", "")
        self.__source = args.get("source", "default")
        loc_type = [type(inst) for inst in {"i"   :  [1, 1L],
                                            "b"   : [True],
                                            "s"   : ["1"],
                                            "f"   : [1.0],
                                            "B"   : ["1"],
                                            "a"   : [[1, 2]],
                                            "d"   : [{0 : 1}],
                                            "ddt" : [datetime.datetime(2007, 1, 1)],
                                            "dtd" : [datetime.timedelta(1)]}[self.__val_type]]
        if type(def_val) not in loc_type:
            raise TypeError, "Type of Default-value differs from given type (%s, %s)" % (type(def_val), str(loc_type))
        self.set_value(self.__default_val)
        self.__fixed = args.get("fixed", False)
        self.set_is_global()
    def set_is_global(self, is_global=True):
        self.__is_global = is_global
    def is_global(self):
        return self.__is_global
    def get_long_type(self):
        return {"s"   : "String",
                "b"   : "Boolean",
                "i"   : "Integer",
                "f"   : "Float",
                "B"   : "Blob",
                "a"   : "Array",
                "d"   : "Dict",
                "ddt" : "Datetime",
                "dtd" : "Timedelta"}[self.__val_type]
    def get_value(self):
        return self.act_val
    def get_pretty_value(self):
        if self.__val_type == "B":
            return "blob with len %d" % (len(self.act_val))
        elif self.__val_type == "b":
            return self.act_val and "True" or "False"
        else:
            return self.act_val
    def str_to_val(self, val):
        if self.__val_type == "i":
            return int(val)
        elif self.__val_type == "b":
            if type(val) == type(""):
                if val.lower().startswith("t"):
                    return True
                else:
                    return False
            else:
                return bool(val)
        elif self.__val_type in ["a", "d"]:
            return val
        elif self.__val_type in ["ddt", "dtd"]:
            return val
        elif self.__val_type == "f":
            return float(val)
        else:
            return str(val)
    def get_source(self):
        return self.__source
    def get_type(self):
        return self.__val_type
    def is_fixed(self):
        return self.__fixed
    def set_value(self, val, source="default"):
        try:
            r_val = self.str_to_val(val)
        except TypeError:
            raise TypeError, "Type Error for value %s" % (str(val))
        except ValueError:
            raise ValueError, "Value Error for value %s" % (str(val))
        else:
            self.act_val = r_val
            if source and (source != "default" or self.__source == "default"):
                self.__source = source
    def __str__(self):
        return "%s (source %s, %s) : %s" % (self.get_long_type(),
                                            self.__source,
                                            "global" if self.__is_global else "local",
                                            self.get_pretty_value())
    def get_info(self):
        return self.__info

class int_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "i", **args)

class float_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "f", **args)

class str_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "s", **args)

class blob_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "B", **args)

class bool_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "b", **args)

class array_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "a", **args)

class dict_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "d", **args)

class datetime_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "ddt", **args)

class timedelta_c_var(c_var):
    def __init__(self, def_val, **args):
        c_var.__init__(self, def_val, "dtd", **args)

class configuration(object):
    def __init__(self, name, init_dict={}, **args):
        self.__name = name
        self.__verbose = args.get("verbose", False)
        self.__c_dict = {}
        self.clear_log()
        self.set_log_hook(args.get("log_hook", None))
        self.add_config_dict(init_dict)
    def set_log_hook(self, hook):
        self.log_hook = hook
    def get_log(self, **args):
        ret_val = [entry for entry in self.__log_array]
        if args.get("clear", False):
            self.clear_log()
        return ret_val
    def clear_log(self):
        self.__log_array = []
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.log_hook:
            self.log_hook(what, log_level)
        else:
            self.__log_array.append((what, log_level))
    def copy_flags(self, var_dict):
        # copy flags (right now only global / local) for given var_names
        for var_name, var_value in var_dict.iteritems():
            self.__c_dict[var_name].set_is_global(var_value.is_global())
    def add_config_dict(self, a_dict):
        for key, value in a_dict.iteritems():
            if key in self.__c_dict and self.__verbose:
                self.log("Replacing config for key %s" % (key))
            self.__c_dict[key] = value
            if self.__verbose:
                self.log("Setting config for key %s to %s" % (key, value))
    def get_pretty_value(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].get_pretty_value()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def __getitem__(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].get_value()
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
                    pv = self.get_pretty_value(key)
                    f_obj.add_line((key, "list with %s:" % (logging_tools.get_plural("entry", len(pv))), self.get_type(key), self.get_source(key)))
                    idx = 0
                    for entry in pv:
                        f_obj.add_line(("", "", entry, str(idx), "---"))
                        idx += 1
                else:
                    f_obj.add_line((key, self.is_global(key) and "global" or "local", str(self.get_pretty_value(key)), self.get_type(key), self.get_source(key)))
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
            return self.__c_dict[key].get_value()
        else:
            return def_v
    def get_source(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].get_source()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def is_fixed(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].is_fixed()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def is_global(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].is_global()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def get_type(self, key):
        if key in self.__c_dict:
            return self.__c_dict[key].get_type()
        else:
            raise KeyError, "Key %s not found in c_dict" % (key)
    def parse_file(self, file_name, **args):
        # args:
        # section ... only read arugments from the given section (if found)
        scan_section = args.get("section", "global")
        act_section = "global"
        pf1 = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)\s*$")
        pf2 = re.compile("^(?P<key>\S+)\s+(?P<value>.+)\s*$")
        sec_re = re.compile("^\[(?P<section>\S+)\]$")
        if os.path.isfile(file_name):
            try:
                lines = [x for x in [y.strip() for y in file(file_name, "r").read().split("\n")] if x and not x.startswith("#")]
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
                                    self[key] = (value, "%s, sec %s" % (file_name, act_section))
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
    def write_file(self, file_name, always_try=False):
        if not os.path.isfile(file_name) or always_try:
            all_keys = sorted(self.__c_dict.keys())
            try:
                #file(file_name, "w").write("\n".join(["# %s \n%s\n%s = %s\n" % (self.__c_dict[k],
                #                                                                self.__c_dict[k].get_info() and "# %s \n" % (self.__c_dict[k].get_info()) or "",
                #                                                                k,
                #                                                                self.__c_dict[k].get_value()) for k in all_keys] + [""]))
                file(file_name, "w").write("\n".join(sum([["# %s" % (self.__c_dict[k]),
                                                           "# %s" % (self.__c_dict[k].get_info() if self.__c_dict[k].get_info() else "no info"),
                                                           "%s = %s" % (k, 
                                                                        "\"\"" if self.__c_dict[k].get_value() == "" else self.__c_dict[k].get_value()),
                                                           ""] for k in all_keys],
                                                         [""])))
            except:
                self.log("Error while writing file %s: %s" % (file_name, process_tools.get_except_info()))
            else:
                pass
            
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
            print "Unknown type %d for readconfig" % (type)
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
    
def reload_global_config(dc, gcd, server_type, host_name = ""):
    if not host_name:
        host_name = socket.gethostname().split(".")[0]
    num_serv, serv_idx, s_type, s_str, config_idx, real_config_name = process_tools.is_server(dc, server_type, True, False, host_name.split(".")[0])
    # read global configs
    if num_serv:
        # dict of local vars without specified host
        l_var_wo_host = {}
        for short in ["str",
                      "int",
                      "blob",
                      "bool"]:
            # very similiar code appears in config_tools.py
            sql_str = "SELECT cv.* FROM new_config c INNER JOIN device_config dc LEFT JOIN config_%s cv ON cv.new_config=c.new_config_idx WHERE (cv.device=0 OR cv.device=%d) AND dc.device=%d AND dc.new_config=c.new_config_idx AND c.name='%s' ORDER BY cv.device, cv.name" % (short, config_idx, serv_idx, real_config_name)
            dc.execute(sql_str)
            for db_rec in [y for y in dc.fetchall() if y["name"]]:
                if db_rec["name"].count(":"):
                    var_global = False
                    local_host_name, var_name = db_rec["name"].split(":", 1)
                else:
                    var_global = True
                    local_host_name, var_name = (host_name, db_rec["name"])
                if type(db_rec["value"]) == type(array.array("b")):
                    new_val = str_c_var(db_rec["value"].tostring(), source="%s_table" % (short))
                elif short == "int":
                    new_val = int_c_var(int(db_rec["value"]), source="%s_table" % (short))
                elif short == "bool":
                    new_val = bool_c_var(bool(db_rec["value"]), source="%s_table" % (short))
                else:
                    new_val = str_c_var(db_rec["value"], source="%s_table" % (short))
                new_val.set_is_global(var_global)
                if local_host_name == host_name:
                    if var_name.upper() in gcd and gcd.is_fixed(var_name.upper()):
                        # present value is fixed, keep value, only copy global / local status
                        gcd.copy_flags({var_name.upper() : new_val})
                    else:
                        gcd.add_config_dict({var_name.upper() : new_val})
                elif local_host_name == "":
                    l_var_wo_host[var_name.upper()] = new_val
        # check for vars to insert
        for wo_var_name, wo_var in l_var_wo_host.iteritems():
            if not wo_var_name in gcd or gcd.get_source(wo_var_name) == "default":
                gcd.add_config_dict({wo_var_name : wo_var})
    
def read_global_config(dc, server_type, init_dict=None, host_name=""):
    if init_dict is None:
        init_dict = {}
    gcd = configuration(server_type.replace("%", ""), init_dict)
    reload_global_config(dc, gcd, server_type, host_name)
    return gcd

class device_variable(object):
    def __init__(self, dc, dev_idx, var_name, **args):
        self.__dev_idx = dev_idx
        self.__var_name = var_name
        self.__var_type, self.__description = (None, "not set")
        dc.execute("SELECT * FROM device_variable WHERE device=%s AND name=%s", (dev_idx, var_name))
        if dc.rowcount:
            act_dv = dc.fetchone()
            self.__var_idx = act_dv["device_variable_idx"]
            self.set_stuff(var_type = act_dv["var_type"],
                           description = act_dv["description"])
            self.set_value(act_dv["val_%s" % (self.__var_type_name)], type_ok=True)
        else:
            self.__var_idx = 0
        self.set_stuff(**args)
        if "value" in args:
            self.set_value(args["value"])
        if (not self.__var_idx and "value" in args) or args.get("force_update", False):
            # update if device_variable not found and args[value] is set
            self.update(dc)
    def update(self, dc):
        if self.__var_idx:
            dc.execute("UPDATE device_variable SET val_%s=%%s, description=%%s, var_type=%%s WHERE device_variable_idx=%%s" % (self.__var_type_name), (self.__var_value,
                                                                                                                                                       self.__description,
                                                                                                                                                       self.__var_type,
                                                                                                                                                       self.__var_idx))
        else:
            dc.execute("INSERT INTO device_variable SET val_%s=%%s, description=%%s, var_type=%%s, name=%%s, device=%%s" % (self.__var_type_name), (self.__var_value,
                                                                                                                                                    self.__description,
                                                                                                                                                    self.__var_type,
                                                                                                                                                    self.__var_name,
                                                                                                                                                    self.__dev_idx))
            self.__var_idx = dc.insert_id()
    def is_set(self):
        return self.__var_idx and True or False
    def set_stuff(self, **args):
        if "value" in args:
            self.set_value(args["value"])
        if "var_type" in args:
            self.__var_type = args["var_type"]
            self.__var_type_name = {"s" : "str",
                                    "i" : "int" ,
                                    "b" : "blob",
                                    "t" : "time",
                                    "d" : "date"}[self.__var_type]
        if "description" in args:
            self.__description = args["description"]
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
        for k in config.keys():
            #print k,config.get_source(k)
            #print "write", k, config.get_source(k)
            #if config.get_source(k) == "default":
            # only deal with int and str-variables
            tab_type = {"i" : "int",
                        "s" : "str",
                        "b" : "bool"}.get(config.get_type(k), None)
            if tab_type:
                # var global / local
                var_range_name = config.is_global(k) and "global" or "local"
                # build real var name
                real_k_name = config.is_global(k) and k or "%s:%s" % (host_name, k)
                #print config.is_global(k), k, real_k_name
                sql_str = "SELECT cv.*, dc.device FROM device_config dc INNER JOIN config_%s cv INNER JOIN device d INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE " % (tab_type) + \
                          "d.device_group=dg.device_group_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND " + \
                          "d.device_idx=%d AND dc.new_config=%d AND cv.new_config=dc.new_config AND cv.name='%s' AND (cv.device=0 OR cv.device=%d)" % (srv_info.server_device_idx,
                                                                                                                                                       srv_info.config_idx,
                                                                                                                                                       real_k_name,
                                                                                                                                                       srv_info.server_device_idx)
                dc.execute(sql_str)
                #print dc.rowcount, sql_str
                if not dc.rowcount:
                    # insert default value
                    sql_str, sql_tuple = ("INSERT INTO config_%s SET name=%%s, descr=%%s, new_config=%%s, value=%%s" % (tab_type), (real_k_name,
                                                                                                                                    "%s default value from %s on %s" % (var_range_name,
                                                                                                                                                                        srv_info.config_name,
                                                                                                                                                                        full_host_name),
                                                                                                                                    srv_info.config_idx,
                                                                                                                                    config[k]))
                    dc.execute(sql_str, sql_tuple)
                else:
                    # already in db
                    #sql_str = ""
                    act_db_record = dc.fetchone()
                    if config[k] != act_db_record["value"]:
                        sql_str, sql_tuple = ("UPDATE config_%s SET value=%%s WHERE config=%%s AND name=%%s" % (tab_type), (config[k],
                                                                                                                            srv_info.config_idx,
                                                                                                                            real_k_name))
                        dc.execute(sql_str, sql_tuple)
                        # changed
                        #print "Change", real_k_name, k, config[k], act_db_record["value"]
    return log_lines
