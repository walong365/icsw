#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server """

import MySQLdb
import MySQLdb.cursors
import sys
import os
import getopt
import re
import shutil
import tempfile
import configfile
import types
import os.path
import socket
import time
import pprint
import stat
import threading
import logging_tools
import process_tools
import mysql_tools
import array
import server_command
import config_tools
import threading_tools
import net_tools

SERVER_COM_PORT   = 8005
SERVER_NODE_PORT  = 8006
NCS_PORT          = 8010
GATEWAY_THRESHOLD = 1000

SQL_ACCESS = "cluster_full_access"

# --------------------------------------------------------------------------------
class connection_from_node(net_tools.buffer_object):
    # receiving connection object for node connection
    def __init__(self, src, dest_queue):
        self.__dest_queue = dest_queue
        self.__src = src
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        #print "- del new_relay_con"
        pass
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
        if is_p1:
            self.__dest_queue.put(("node_connection", (self, self.__src, what)))
    def send_return(self, what):
        self.lock()
        if self.socket:
            self.add_to_out_buffer(net_tools.add_proto_1_header(what))
        else:
            pass
        self.unlock()
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
            self.close()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def report_problem(self, flag, what):
        self.__dest_queue.put(("node_error", "%s : %s, src is %s" % (net_tools.net_flag_to_str(flag),
                                                                     what,
                                                                     str(self.__src))))
        self.close()

class connection_for_command(net_tools.buffer_object):
    # receiving connection object for command connection
    def __init__(self, src, dest_queue):
        self.__dest_queue = dest_queue
        self.__src = src
        net_tools.buffer_object.__init__(self)
    def __del__(self):
        #print "- del new_relay_con"
        pass
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
        if is_p1:
            self.__dest_queue.put(("new_command", (self, self.__src, what)))
    def send_return(self, what):
        self.lock()
        if self.socket:
            self.add_to_out_buffer(net_tools.add_proto_1_header(what))
        else:
            pass
        self.unlock()
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
            self.close()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def report_problem(self, flag, what):
        self.__dest_queue.put(("command_error", (self, self.__src, "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
        self.close()

class connection_to_node(net_tools.buffer_object):
    # connects to a foreign package-client
    def __init__(self, (act_dict, mach), ret_queue):
        self.__act_dict = act_dict
        self.__mach = mach
        self.__ret_queue = ret_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__act_dict["command"].get_command(), True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__ret_queue.put(("send_ok", ((self.__act_dict, self.__mach), p1_data)))
            self.delete()
    def report_problem(self, flag, what):
        self.__ret_queue.put(("send_error", ((self.__act_dict, self.__mach), "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
        self.delete()

class connection_to_nagios_server(net_tools.buffer_object):
    # connects to a foreign package-client
    def __init__(self, (srv_com, srv_name), ret_queue):
        self.__srv_com = srv_com
        self.__srv_name = srv_name
        self.__ret_queue = ret_queue
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__srv_com, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.out_buffer):
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__ret_queue.put(("srv_send_ok", ((self.__srv_com, self.__srv_name), p1_data)))
            self.delete()
    def report_problem(self, flag, what):
        self.__ret_queue.put(("srv_send_error", ((self.__srv_com, self.__srv_name), "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
        self.delete()
# --------------------------------------------------------------------------------

def pretty_print(name, obj, offset):
    lines = []
    off_str = " " * offset
    if type(obj) == type({}):
        if name:
            head_str = "%s%s(D):" % (off_str, name)
            lines.append(head_str)
        else:
            head_str = ""
        keys = sorted(obj.keys())
        max_len = max([len(x) for x in keys])
        for key in keys:
            lines += pretty_print(("%s%s" % (key, " " * max_len))[0:max_len],
                                  obj[key],
                                  len(head_str))
    elif type(obj) in [type([]), type(())]:
        head_str = "%s%s(L %d):" % (off_str, name, len(obj))
        lines.append(head_str)
        idx = 0
        for value in obj:
            lines += pretty_print("%d" % (idx), value, len(head_str))
            idx += 1
    elif type(obj) == type(""):
        if obj:
            lines.append("%s%s(S): %s" % (off_str, name, obj))
        else:
            lines.append("%s%s(S): (empty string)" % (off_str, name))
    elif type(obj) in [type(2), type(2L)]:
        lines.append("%s%s(I): %d" % (off_str, name, obj))
    else:
        lines.append("%s%s(?): %s" % (off_str, name, str(obj)))
    return lines
        
class new_config_object(object):
    # path and type [(f)ile, (l)ink, (d)ir, (c)opy]
    def __init__(self, destination, o_type):
        self.dest = destination
        self.type = o_type
        self.content = []
        self.source_configs = []
        self.show_error = True
        self.uid, self.gid = (0, 0)
        self.set_error_flag()
    def set_error_flag(self, et = 0):
        self.error_flag = et
    def get_error_flag(self):
        return self.error_flag
    def get_dest(self):
        return self.dest
    def get_type(self):
        return self.type
    def set_source(self, sp):
        self.source = sp
    def set_show_error(self, so):
        self.show_error = so
    def set_config(self, conf):
        self.add_config(conf.get_name())
    def add_config(self, conf):
        if conf not in self.source_configs:
            self.source_configs.append(conf)
    def set_uid(self, uid):
        self.uid = uid
    def set_gid(self, gid):
        self.gid = gid
    def get_uid(self):
        return self.uid
    def get_gid(self):
        return self.gid
    def set_mode(self, mode):
        if type(mode) == type(""):
            self.mode = int(mode)
        else:
            self.mode = mode
    def get_mode(self):
        return self.mode
    def __iadd__(self, line):
        if type(line) == types.StringType:
            self.content.append("%s\n" % (line))
        elif type(line) == type([]):
            self.content.extend(["%s\n" % (x) for x in line])
        elif type(line) == types.DictType:
            for key, value in line.iteritems():
                self.content.append("%s='%s'\n" % (key, value))
        elif type(line) == type(array.array("b")):
            self.content.append(line.tostring())
        return self
    def bin_append(self, bytes):
        if type(bytes) == type(array.array("b")):
            self.content.append(bytes.tostring())
        else:
            self.content.append(bytes)
            
class file_object(new_config_object):
    def __init__(self, destination, **args):
        """ example from ba/ca:
        a=config.add_file_object("/etc/services", from_image=True,dev_dict=dev_dict)
        new_content = []
        print len(a.content)
        for line in a.content:
            if line.lstrip().startswith("mult"):
                print line
        """
        new_config_object.__init__(self, destination, "f")
        self.set_mode("0644")
        if args.get("from_image", False):
            s_dir = args["dev_dict"]["image"].get("source", None)
            if s_dir:
                s_content = file("%s/%s" % (s_dir, destination), "r").read()
                self += s_content.split("\n")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_file_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def write_object(self, dest, disk_int):
        content = "".join(self.content)
        file(dest, "w").write(content)
        os.chmod(dest, 0644)
        ret_state, ret_str = (0, "%d %d %d %s %s" % (disk_int, self.get_uid(), self.get_gid(), self.mode, self.dest))
        sql_tuples = (disk_int,
                      ", ".join(self.source_configs),
                      self.get_uid(),
                      self.get_gid(),
                      int(self.get_mode()),
                      self.get_type(),
                      "",
                      self.dest,
                      self.get_error_flag(),
                      content)
        return ret_state, ret_str, sql_tuples

class link_object(new_config_object):
    def __init__(self, destination):
        new_config_object.__init__(self, destination, "l")
        self.set_mode("0644")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_file_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def set_source(self, sp):
        self.source = sp
    def write_object(self, dest, disk_int):
        ret_state, ret_str = (0, "%s %s" % (self.dest, self.source))
        sql_tuples = (disk_int,
                      ", ".join(self.source_configs),
                      self.get_uid(),
                      self.get_gid(),
                      int(self.get_mode()),
                      self.get_type(),
                      self.source,
                      self.dest,
                      self.get_error_flag(),
                      "")
        return ret_state, ret_str, sql_tuples

class dir_object(new_config_object):
    def __init__(self, destination):
        new_config_object.__init__(self, destination, "d")
        self.set_mode("0755")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_dir_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def write_object(self, dest, disk_int):
        ret_state, ret_str = (0, "%d %d %d %s %s" % (disk_int, self.get_uid(), self.get_gid(), self.mode, self.dest))
        sql_tuples = (disk_int,
                      ", ".join(self.source_configs),
                      self.get_uid(),
                      self.get_gid(),
                      int(self.get_mode()),
                      self.get_type(),
                      "",
                      self.dest,
                      self.get_error_flag(),
                      "")
        return ret_state, ret_str, sql_tuples

class delete_object(new_config_object):
    def __init__(self, destination, recursive=0):
        new_config_object.__init__(self, destination, "e")
        self.recursive = recursive
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
    def write_object(self, dest, disk_int):
        ret_state, ret_str = (0, "%d %s" % (self.recursive, self.dest))
        sql_tuples = (disk_int,
                      ", ".join(self.source_configs),
                      0,
                      0,
                      self.recursive,
                      self.get_type(),
                      "",
                      self.dest,
                      self.get_error_flag(),
                      "")
        return ret_state, ret_str, sql_tuples

class copy_object(new_config_object):
    def __init__(self, destination):
        new_config_object.__init__(self, destination, "c")
        self.set_mode("0755")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_dir_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def set_source(self, sp):
        self.source = sp
    def write_object(self, dest, disk_int):
        ret_state, ret_str = (1, "<UNKNOWN ERROR>")
        if os.path.isfile(self.source):
            orig_stat = os.stat(self.source)
            o_uid, o_gid, o_mode = (orig_stat[stat.ST_UID] or self.get_uid(),
                                    orig_stat[stat.ST_GID] or self.get_gid(),
                                    stat.S_IMODE(orig_stat[stat.ST_MODE]))
            try:
                shutil.copyfile(self.source, dest)
            except IOError:
                ret_state, ret_str = (1, "*** cannot read sourcefile '%s'" % (self.source))
            else:
                os.chmod(dest, 0644)
                ret_state, ret_str = (0, "%d %d %d %s %s" % (disk_int, o_uid, o_gid, oct(o_mode), self.dest))
        else:
            if self.show_error:
                ret_state, ret_str = (1, "*** Sourcefile '%s' not found, skipping..." % (self.source))
            else:
                ret_state, ret_str = (1, "")
        sql_tuples = (disk_int,
                      ", ".join(self.source_configs),
                      self.get_uid(),
                      self.get_gid(),
                      int(self.get_mode()),
                      self.get_type(),
                      self.source,
                      self.dest,
                      self.get_error_flag(),
                      "")
        return ret_state, ret_str, sql_tuples
        
class internal_object(new_config_object):
    def __init__(self, destination):
        new_config_object.__init__(self, destination, "i")
        self.set_mode("0755")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_file_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def write_object(self, dest, disk_int):
        ret_state, ret_str = (0, "")
        sql_tuples = (0,
                      ", ".join(self.source_configs),
                      self.get_uid(),
                      self.get_gid(),
                      int(self.get_mode()),
                      self.get_type(),
                      "",
                      self.dest,
                      self.get_error_flag(),
                      "")
        return ret_state, ret_str, sql_tuples

# dummy container for stdout / stderr
class dummy_container(object):
    def __init__(self):
        self.__content = ""
    def write(self, what):
        self.__content = "%s%s" % (self.__content,
                                   what)
    def get_content(self):
        return self.__content

class pseudo_config(object):
    # used for fetching variables
    def __init__(self, db_rec, c_req):#name, idx, pri, descr, identifier, node_name, log_queue, conf_dict):
        self.is_pseudo = True
        self.__db_rec = db_rec
        self.__c_req = c_req
        #self.name = name
        #self.pri = pri
        #self.idx = idx
        #self.descr = descr
        #self.identifier = identifier
        #self.log_queue = log_queue
        #self.set_node_name(node_name)
        self.__allowed_var_types = ["int", "str", "blob"]
        self.var_dict, self.var_types, self.script_dict = ({},
                                                           dict([(x, []) for x in self.__allowed_var_types]),
                                                           {})
        self.all_scripts = []
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__c_req.log(what, level)
    def add_variable(self, var_type, var):
        if var_type in self.__allowed_var_types:
            self.var_dict[var["name"].lower()] = var
            self.var_types[var_type].append(var["name"].lower())
            added = True
        else:
            added = False
        return added
    def show_variables(self):
        self.var_dict["IDENTIFIER".lower()] = {"name"   : "identifier",
                                               "descr"  : "internal_variable",
                                               "config" : self.__db_rec["new_config_idx"],
                                               "value"  : self.get_name()}
        self.var_types["str"].append("IDENTIFIER".lower())
        self.log(" - pseudo config %-20s (priority %4d): %s" % (self.get_name(),
                                                                self.get_pri(),
                                                                ", ".join([logging_tools.get_plural(var_type, len(self.var_types[var_type])) for var_type in self.__allowed_var_types])))
        if self.__c_req.get_loc_config()["VERBOSE"]:
            for var_type in self.__allowed_var_types:
                for name in self.var_types[var_type]:
                    if var_type == "str":
                        val_str = "'%s'" % (str(self.var_dict[name]["value"]))
                    elif var_type == "int":
                        val_str = "%d" % (self.var_dict[name]["value"])
                    elif var_type == "blob":
                        val_str = "len %s" % (logging_tools.get_plural("byte", len(self.var_dict[name]["value"])))
                    else:
                        val_str = "pri %d with %s" % (self.var_dict[name]["priority"], logging_tools.get_plural("line", len(self.var_dict[name]["value"].split("\n"))))
                    self.log("    %8s %-24s: %s" % (var_type, name, val_str))
    def get_pri(self):
        return self.__db_rec["priority"]
    def get_identifier(self):
        return self.__db_rec["identifier"]
    def get_name(self):
        return self.__db_rec["name"]
    def get_node_name(self):
        return self.__c_req["name"]

class new_config(object):
    def __init__(self, db_rec, c_req):#name, idx, pri, descr, identifier, node_name, log_queue, local_conf):
        self.is_pseudo = False
        self.__db_rec = db_rec
        self.__c_req = c_req
        self.local_conf = db_rec["device"] == c_req["device_idx"]
        self.__allowed_var_types = ["int", "str", "blob", "script"]
        self.var_dict, self.var_types, self.script_dict = ({},
                                                           dict([(x, []) for x in self.__allowed_var_types]),
                                                           {})
        self.all_scripts = []
        self.set_uid(0)
        self.set_gid(0)
        self.set_file_mode("0644")
        self.set_dir_mode("0755")
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__c_req.log(what, level)
    def add_variable(self, var_type, var):
        if var_type in self.__allowed_var_types:
            self.var_dict[var["name"].lower()] = var
            self.var_types[var_type].append(var["name"].lower())
            if var_type == "script":
                self.script_dict.setdefault(var["priority"], []).append(var["name"].lower())
                self.all_scripts.append(var["name"].lower())
            added = True
        else:
            added = False
        return added
    def show_variables(self):
        self.var_dict["IDENTIFIER".lower()] = {"name"   : "identifier",
                                               "descr"  : "internal_variable",
                                               "config" : self.__db_rec["new_config_idx"],
                                               "value"  : self.get_name()}
        self.var_types["str"].append("IDENTIFIER".lower())
        self.log(" - %s config %-20s (priority %4d): %s" % (self.local_conf and "(l)" or "(g)",
                                                            self.get_name(),
                                                            self.get_pri(),
                                                            ", ".join([logging_tools.get_plural(var_type, len(self.var_types[var_type])) for var_type in self.__allowed_var_types])))
        if self.__c_req.get_loc_config()["VERBOSE"]:
            for var_type in self.__allowed_var_types:
                for name in self.var_types[var_type]:
                    if var_type == "str":
                        val_str = "'%s'" % (str(self.var_dict[name]["value"]))
                    elif var_type == "int":
                        val_str = "%d" % (self.var_dict[name]["value"])
                    elif var_type == "blob":
                        val_str = "len %s" % (logging_tools.get_plural("byte", len(self.var_dict[name]["value"])))
                    else:
                        val_str = "pri %d with %s" % (self.var_dict[name]["priority"], logging_tools.get_plural("line", len(self.var_dict[name]["value"].split("\n"))))
                    self.log("    %8s %-24s: %s" % (var_type, name, val_str))
    def __del__(self):
        pass
    def get_config_request(self):
        return self.__c_req
    def set_uid(self, uid):
        self.uid = uid
    def set_gid(self, gid):
        self.gid = gid
    def get_uid(self):
        return self.uid
    def get_gid(self):
        return self.gid
    def set_file_mode(self, mode):
        self.file_mode = mode
    def get_file_mode(self):
        return self.file_mode
    def set_dir_mode(self, mode):
        self.dir_mode = mode
    def get_dir_mode(self):
        return self.dir_mode
    def get_node_name(self):
        return self.__c_req["name"]
    def get_pri(self):
        return self.__db_rec["priority"]
    def get_identifier(self):
        return self.__db_rec["identifier"]
    def get_name(self):
        return self.__db_rec["name"]
    def add_dir_object(self, don):
        if not self.__c_req.conf_dict.has_key(don):
            self.__c_req.conf_dict[don] = dir_object(don)
            self.__c_req.conf_dict[don].set_config(self)
        if don not in self.__touched_objects:
            self.__touched_objects.append(don)
        return self.__c_req.conf_dict[don]
    def add_delete_object(self, eon):
        if not self.__c_req.erase_dict.has_key(eon):
            self.__c_req.erase_dict[eon] = delete_object(eon)
            self.__c_req.erase_dict[eon].set_config(self)
        return self.__c_req.erase_dict[eon]
    def add_copy_object(self, con, source):
        if not self.__c_req.conf_dict.has_key(con):
            self.__c_req.conf_dict[con] = copy_object(con)
            self.__c_req.conf_dict[con].set_config(self)
            self.__c_req.conf_dict[con].set_source(source)
        if con not in self.__touched_objects:
            self.__touched_objects.append(con)
        return self.__c_req.conf_dict[con]
    def add_file_object(self, fon, **args):
        if not self.__c_req.conf_dict.has_key(fon):
            self.__c_req.conf_dict[fon] = file_object(fon, **args)
            self.__c_req.conf_dict[fon].set_config(self)
        if fon not in self.__touched_objects:
            self.__touched_objects.append(fon)
        return self.__c_req.conf_dict[fon]
    def add_link_object(self, lon, source):
        if not self.__c_req.link_dict.has_key(lon):
            self.__c_req.link_dict[lon] = link_object(lon)
            self.__c_req.link_dict[lon].set_config(self)
            self.__c_req.link_dict[lon].set_source(source)
        if lon not in self.__touched_links:
            self.__touched_links.append(lon)
        return self.__c_req.link_dict[lon]
    def del_config(self, cn):
        if self.__c_req.conf_dict.has_key(cn):
            del self.__c_req.conf_dict[cn]
    def get_cursor(self):
        return self.__dc
    def process_scripts(self, dev_dict, dc):
        self.dev_dict = dev_dict
        self.__dc = dc
        self.log("processing script(s) for config %s" % (self.get_name()))
        for pri in sorted(self.script_dict.keys()):
            for script in [self.var_dict[s_name] for s_name in self.script_dict[pri]]:
                if script["enabled"]:
                    lines = script["value"].split("\n")
                    self.log(" - scriptname %s (pri %d, %s)" % (script["name"], pri, logging_tools.get_plural("line", len(lines))))
                    #print "***", script["name"], script["value"].replace("\r", "")
                    start_time = time.time()
                    try:
                        code_obj = compile(script["value"].replace("\r\n", "\n")+"\n", "<script %s>" % (script["name"]), "exec")
                    except:
                        exc_info = process_tools.exception_info()
                        self.log("An Error occured during compile() after %s:" % (logging_tools.get_diff_time_str(time.time() - start_time)),
                                 logging_tools.LOG_LEVEL_ERROR)
                        for line in exc_info.log_lines:
                            self.log(" *** %s" % (line), logging_tools.LOG_LEVEL_ERROR)
                        self.__c_req.register_config_error("error during script compile of '%s'" % (self.get_name()))
                    else:
                        compile_time = time.time() - start_time
                        local_vars = sorted([v0 for v0 in self.var_dict.keys() if v0 not in self.all_scripts])
                        self.log(" - %s: %s" % (logging_tools.get_plural("local variable", len(local_vars)),
                                                ", ".join(local_vars)))
                        # add local vars
                        for var_name in local_vars:
                            dev_dict[var_name] = self.var_dict[var_name]["value"]
                        start_time = time.time()
                        stdout_c, stderr_c = (dummy_container(), dummy_container())
                        old_stdout, old_stderr = (sys.stdout, sys.stderr)
                        sys.stdout, sys.stderr = (stdout_c  , stderr_c  )
                        self.__touched_objects, self.__touched_links, self.__deleted_files = ([], [], [])
                        try:
                            ret_code = eval(code_obj, {}, {"dev_dict"        : dev_dict,
                                                           "config"          : self,
                                                           "dir_object"      : dir_object,
                                                           "delete_object"   : delete_object,
                                                           "copy_object"     : copy_object,
                                                           "link_object"     : link_object,
                                                           "file_object"     : file_object,
                                                           "do_ssh"          : do_ssh,
                                                           "do_etc_hosts"    : do_etc_hosts,
                                                           "do_hosts_equiv"  : do_hosts_equiv,
                                                           "do_nets"         : do_nets,
                                                           "do_routes"       : do_routes,
                                                           "do_fstab"        : do_fstab,
                                                           "partition_setup" : partition_setup})
                        except:
                            sys.stdout, sys.stderr = (old_stdout, old_stderr)
                            # error call
                            dev_dict["called"][self.get_name()] = 0
                            exc_info = process_tools.exception_info()
                            self.log("An Error occured during eval() after %s:" % (logging_tools.get_diff_time_str(time.time() - start_time)),
                                     logging_tools.LOG_LEVEL_ERROR)
                            for line in exc_info.log_lines:
                                self.log(" *** %s" % (line), logging_tools.LOG_LEVEL_ERROR)
                            sql_str, sql_tuple = ("UPDATE config_script SET error_text=%s WHERE config_script_idx=%s", ("\n".join(exc_info.log_lines), script["config_script_idx"]))
                            self.__dc.execute(sql_str, sql_tuple)
                            self.__c_req.register_config_error("error during script eval of '%s'" % (self.get_name()))
                            if self.__touched_objects:
                                self.log("%s touched : %s" % (logging_tools.get_plural("object", len(self.__touched_objects)),
                                                              ", ".join(self.__touched_objects)))
                                for to in self.__touched_objects:
                                    self.__c_req.conf_dict[to].set_error_flag(1)
                            if self.__touched_links:
                                self.log("%s touched : %s" % (logging_tools.get_plural("link", len(self.__touched_links)),
                                                              ", ".join(self.__touched_links)))
                                for tl in self.__touched_links:
                                    self.__c_req.link_dict[tl].set_error_flag(1)
                            else:
                                self.log("no objects touched")
                            if self.__deleted_files:
                                self.log("%s deleted : %s" % (logging_tools.get_plural("delete", len(self.__deleted_files)),
                                                              ", ".join(self.__deleted_files)))
                                for tl in self.__touched_links:
                                    self.__c_req.erase_dict[tl].set_error_flag(1)
                            else:
                                self.log("no objects deleted")
                        else:
                            sys.stdout, sys.stderr = (old_stdout, old_stderr)
                            # call successfull
                            dev_dict["called"][self.get_name()] = 1
                            if ret_code == None:
                                ret_code = 0
                            self.log("  exited after %s (%s compile time) with return code %d" % (logging_tools.get_diff_time_str(time.time() - start_time),
                                                                                                  logging_tools.get_diff_time_str(compile_time),
                                                                                                  ret_code))
                            sql_str = "UPDATE config_script SET error_text='' WHERE config_script_idx=%d" % (script["config_script_idx"])
                            self.__dc.execute(sql_str)
                        # delete local vars
                        for var_name in local_vars:
                            del dev_dict[var_name]
                        for log_line in [x.rstrip() for x in stdout_c.get_content().split("\n")]:
                            if log_line:
                                self.log("out: %s" % (log_line))
                        for log_line in [x.rstrip() for x in stderr_c.get_content().split("\n")]:
                            if log_line:
                                self.log("*** err: %s" % (log_line), logging_tools.LOG_LEVEL_ERROR)
                                self.__c_req.register_config_error("%s something received on stderr" % (self.get_name()))
                        code_obj = None
                else:
                    self.log(" - scriptname %s (pri %d, %s) is disabled, skipping" % (script["name"], pri, logging_tools.get_plural("line", len(lines))))
        del self.dev_dict
        del self.__dc

def do_nets(conf):
    pub_stuff = conf.dev_dict
    sys_dict = pub_stuff["system"]
    append_dict, dev_dict = ({}, {})
    write_order_list, macs_used, lu_table = ([], {}, {})
    for check_for_bootdevice in range(2):
        for net in pub_stuff["node_if"]:
            if (not check_for_bootdevice and net["netdevice_idx"] == pub_stuff["bootnetdevice_idx"]) or (check_for_bootdevice and not net["netdevice_idx"] == pub_stuff["bootnetdevice_idx"]):
                if int(net["macadr"].replace(":", ""), 16) != 0 and net["macadr"].lower() in macs_used.keys():
                    print "*** error, macaddress %s on netdevice %s already used for netdevice %s" % (net["macadr"], net["devname"], macs_used[net["macadr"].lower()])
                else:
                    macs_used[net["macadr"].lower()] = net["devname"]
                    write_order_list.append(net["netdevice_idx"])
                    lu_table[net["netdevice_idx"]] = net
    if sys_dict["vendor"] == "debian":
        glob_nf = conf.add_file_object("/etc/network/interfaces")
        auto_if = []
        for net_idx in write_order_list:
            net = lu_table[net_idx]
            auto_if.append(net["devname"])
        glob_nf += "auto %s" % (" ".join(auto_if))
        # get default gw
        gw_source, def_ip, boot_dev, boot_mac = get_default_gw(conf)
    for net_idx in write_order_list:
        net = lu_table[net_idx]
        if net["netdevice_idx"] == pub_stuff["bootnetdevice_idx"]:
            if sys_dict["vendor"] == "suse":
                new_co = conf.add_file_object("/etc/HOSTNAME")
                new_co += "%s%s.%s" % (pub_stuff["host"], net["postfix"], net["name"])
            elif sys_dict["vendor"] == "debian":
                new_co = conf.add_file_object("/etc/hostname")
                new_co += "%s%s.%s" % (pub_stuff["host"], net["postfix"], net["name"])
            else:
                new_co = conf.add_file_object("/etc/sysconfig/network")
                new_co += "HOSTNAME=%s" % (pub_stuff["host"])
                new_co += "NETWORKING=yes"
        log_str = "netdevice %10s (mac %s)" % (net["devname"], net["macadr"])
        if sys_dict["vendor"] == "suse":
            # suse-mode
            if (sys_dict["version"] >= 9 and sys_dict["release"] > 0) or sys_dict["version"] > 9:
                act_filename = None
                if net["devname"].startswith("eth") or net["devname"].startswith("myri") or net["devname"].startswith("ib"):
                    mn = re.match("^(?P<devname>.+):(?P<virtual>\d+)$", net["devname"])
                    if mn:
                        log_str += ", virtual of %s" % (mn.group("devname"))
                        append_dict.setdefault(mn.group("devname"), {})
                        append_dict[mn.group("devname")][mn.group("virtual")] = {"BROADCAST" : net["broadcast"],
                                                                                 "IPADDR"    : net["ip"],
                                                                                 "NETMASK"   : net["netmask"],
                                                                                 "NETWORK"   : net["network"]}
                    else:
                        if int(net["macadr"].replace(":", ""), 16) != 0:
                            dev_dict[net["devname"]] = net["macadr"]
                            if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10):
                                # openSUSE 10.3
                                act_filename = "ifcfg-%s" % (net["devname"])
                            else:
                                act_filename = "ifcfg-eth-id-%s" % (net["macadr"])
                                if conf.get_config_request().get_glob_config()["ADD_NETDEVICE_LINKS"]:
                                    conf.add_link_object("/etc/sysconfig/network/%s" % (act_filename), "/etc/sysconfig/network/ifcfg-%s" % (net["devname"]))
                        else:
                            log_str += ", ignoring (zero macaddress)"
                else:
                    act_filename = "ifcfg-%s" % (net["devname"])
                if act_filename:
                    act_file = {"BOOTPROTO" : "static",
                                "BROADCAST" : net["broadcast"],
                                "IPADDR"    : net["ip"],
                                "NETMASK"   : net["netmask"],
                                "NETWORK"   : net["network"],
                                "STARTMODE" : "onboot"
                                }
                    if not net["fake_macadr"]:
                        pass
                    elif int(net["fake_macadr"].replace(":", ""), 16) != 0:
                        log_str += ", with fake_macadr"
                        act_file["LLADDR"] = net["fake_macadr"]
                        conf.add_link_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (net["fake_macadr"]), act_filename)
                    new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                    new_co += act_file
            else:
                act_filename = "ifcfg-%s" % (net["devname"])
                act_file = {"BOOTPROTO"     : "static",
                            "BROADCAST"     : net["broadcast"],
                            "IPADDR"        : net["ip"],
                            "NETMASK"       : net["netmask"],
                            "NETWORK"       : net["network"],
                            "REMOTE_IPADDR" : "",
                            "STARTMODE"     : "onboot",
                            "WIRELESS"      : "no"}
                new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                new_co += act_file
        elif sys_dict["vendor"] == "debian":
            glob_nf += ""
            if net["devname"] == "lo":
                glob_nf += "iface %s inet loopback" % (net["devname"])
            else:
                glob_nf += "iface %s inet static" % (net["devname"])
                glob_nf += "      address %s" % (net["ip"])
                glob_nf += "      netmask %s" % (net["netmask"])
                glob_nf += "    broadcast %s" % (net["broadcast"])
                if net["devname"] == boot_dev:
                    glob_nf += "      gateway %s" % (def_ip)
                if not net["fake_macadr"]:
                    pass
                elif int(net["fake_macadr"].replace(":", ""), 16) != 0:
                    log_str += ", with fake_macadr"
                    glob_nf += "    hwaddress ether %s" % (net["fake_macadr"])
        else:
            # redhat-mode
            act_filename = "ifcfg-%s" % (net["devname"])
            if net["devname"] == "lo":
                d_file = "/etc/sysconfig/networking/%s" % (act_filename)
            else:
                d_file = "/etc/sysconfig/network-scripts/%s" % (act_filename)
            new_co = conf.add_file_object(d_file)
            new_co += {"BOOTPROTO" : "static",
                       "BROADCAST" : net["broadcast"],
                       "IPADDR"    : net["ip"],
                       "NETMASK"   : net["netmask"],
                       "NETWORK"   : net["network"],
                       "DEVICE"    : net["devname"]}
            if conf.get_config_request().get_glob_config()["WRITE_REDHAT_HWADDR_ENTRY"]:
                new_co += {"HWADDR" : net["macadr"].lower()}
        print log_str
    # handle virtual interfaces for Systems above SUSE 9.0
    for orig, virtuals in append_dict.iteritems():
        for virt, stuff in virtuals.iteritems():
            co = conf.add_file_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (dev_dict[orig]))
            co += {"BROADCAST_%s" % (virt) : stuff["BROADCAST"],
                   "IPADDR_%s" % (virt)    : stuff["IPADDR"],
                   "NETMASK_%s" % (virt)   : stuff["NETMASK"],
                   "NETWORK_%s" % (virt)   : stuff["NETWORK"],
                   "LABEL_%s" % (virt)     : virt}

def get_default_gw(conf):
    pub_stuff = conf.dev_dict
    nets = pub_stuff["node_if"]
    # how to get the correct gateway:
    # if all gw_pris < GATEWAY_THRESHOLD the server is the gateway
    # if any gw_pris >= GATEWAY_THRESHOLD the one with the highest gw_pri is taken
    gw_list = []
    for net in nets:
        gw_list.append((net["netdevice_idx"], net["devname"], net["gw_pri"], net["gateway"], net["macadr"]))
    # determine gw_pri
    def_ip, boot_dev, gw_source, boot_mac = ("", "", "<not set>", "")
    # any wg_pri above GATEWAY_THRESHOLD ?
    if gw_list:
        print "Possible gateways:"
        for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list:
            print " idxx %3d, dev %6s, gw_pri %6d, gw_ip %15s, mac %s%s" % (netdev_idx,
                                                                           net_devname,
                                                                           gw_pri,
                                                                           gw_ip,
                                                                           net_mac,
                                                                           gw_pri > GATEWAY_THRESHOLD and "(*)" or "")
    max_gw_pri = max([gw_pri for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list])
    if  max_gw_pri > GATEWAY_THRESHOLD:
        gw_source = "network setting (gw_pri %d > %d)" % (max_gw_pri, GATEWAY_THRESHOLD)
        boot_dev, def_ip, boot_mac = [(net_devname, gw_ip, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if gw_pri == max_gw_pri][0]
    else:
        # we use the bootserver_ip as gateway
        server_ip = pub_stuff["mother_server_ip"]
        #server_dict = get_ip_lists(db_dc, [("server", 0)], pub_stuff["bootnetdevice_idx"], pub_stuff["bootserver_idx"])
        boot_dev, act_gw_pri, boot_mac = ([(net_devname, gw_pri, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if netdev_idx == pub_stuff["bootnetdevice_idx"]] + [("", 0, "")])[0]
        gw_source = "server address taken as ip from mother_server (gw_pri %d < %d and bootnetdevice_idx ok)" % (act_gw_pri, GATEWAY_THRESHOLD)
        def_ip = server_ip
    return gw_source, def_ip, boot_dev, boot_mac

def do_routes(conf):
    pub_stuff = conf.dev_dict
    sys_dict, nets = (pub_stuff["system"], pub_stuff["node_if"])
    if sys_dict["vendor"] == "debian":
        pass
    else:
        if sys_dict["vendor"] == "suse":
            filename = "/etc/sysconfig/network/routes"
        else:
            filename = "/etc/sysconfig/static-routes"
        new_co = conf.add_file_object(filename)
        for net in nets:
            if net["identifier"] != "l":
                if sys_dict["vendor"] == "suse":
                    if sys_dict["vendor"] == "suse" and sys_dict["version"] == 10 and sys_dict["release"] == 3:
                        # openSUSE 10.3
                        new_co += "%s 0.0.0.0 %s %s" % (net["network"], net["netmask"], net["devname"])
                    else:
                        new_co += "%s 0.0.0.0 %s eth-id-%s" % (net["network"], net["netmask"], net["macadr"])
                elif sys_dict["vendor"] == "redhat":
                    new_co += "any net %s netmask %s dev %s" % (net["network"], net["netmask"], net["devname"])
        gw_source, def_ip, boot_dev, boot_mac = get_default_gw(conf)
        if def_ip:
            if sys_dict["vendor"] == "suse":
                new_co += "# from %s" % (gw_source)
                if sys_dict["vendor"] == "suse" and sys_dict["version"] == 10 and sys_dict["release"] == 3:
                    # openSUSE 10.3
                    new_co += "default %s - %s" % (def_ip, boot_dev)
                else:
                    new_co += "default %s - eth-id-%s" % (def_ip, boot_mac)
            elif sys_dict["vendor"] == "redhat" or sys_dict["vendor"].lower().startswith("centos"):
                # redhat-mode
                act_co = conf.add_file_object("/etc/sysconfig/network")
                act_co += "# from %s" % (gw_source)
                act_co += "GATEWAY=%s" % (def_ip)

def do_ssh(conf):#c_dict, pub_stuff, db_dc):
    db_dc = conf.get_cursor()
    c_dict = conf.get_config_request().conf_dict
    pub_stuff = conf.dev_dict
    ssh_types = ["rsa1", "dsa", "rsa"]
    ssh_field_names = []
    for ssh_type in ssh_types:
        ssh_field_names.extend(["ssh_host_%s_key" % (ssh_type), "ssh_host_%s_key_pub" % (ssh_type)])
    found_keys_dict = dict([(k, None) for k in ssh_field_names])
    sql_str = "SELECT dv.* FROM device d LEFT JOIN device_variable dv ON dv.device=d.device_idx WHERE d.name='%s' AND (%s)" % (pub_stuff["host"],
                                                                                                                               " OR ".join(["dv.name='%s'" % (x) for x in ssh_field_names]))
    
    db_dc.execute(sql_str)
    for db_rec in db_dc.fetchall():
        if type(db_rec["val_blob"]) == type(array.array("b")):
            found_keys_dict[db_rec["name"]] = db_rec["val_blob"].tostring()
        else:
            found_keys_dict[db_rec["name"]] = db_rec["val_blob"]
    new_keys = []
    for ssh_type in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn  = "ssh_host_%s_key_pub" % (ssh_type)
        if not found_keys_dict[privfn] or not found_keys_dict[pubfn]:
            db_dc.execute("DELETE FROM device_variable WHERE device=%s AND (%s)" % (pub_stuff["device_idx"],
                                                                                    " OR ".join(["name=%s" for x in [privfn, pubfn]])),
                          tuple([privfn, pubfn]))
            
            print "Generating %s keys..." % (privfn)
            sshkn = tempfile.mktemp("sshgen")
            sshpn = "%s.pub" % (sshkn)
            if ssh_type:
                os.system("ssh-keygen -t %s -q -b 1024 -f %s -N ''" % (ssh_type, sshkn))
            else:
                os.system("ssh-keygen -q -b 1024 -f %s -N ''" % (sshkn))
            found_keys_dict[privfn] = file(sshkn, "r").read()
            found_keys_dict[pubfn]  = file(sshpn, "r").read()
            os.unlink(sshkn)
            os.unlink(sshpn)
            new_keys.extend([privfn, pubfn])
    if new_keys:
        new_keys.sort()
        print "%s to create: %s" % (logging_tools.get_plural("key", len(new_keys)),
                                    ", ".join(new_keys))
        for nk in new_keys:
            sql_str, sql_tuple = ("INSERT INTO device_variable SET device=%s, name=%s, var_type='b', description=%s, val_blob=%s", (pub_stuff["device_idx"],
                                                                                                                                    nk,
                                                                                                                                    "SSH key %s" % (nk),
                                                                                                                                    found_keys_dict[nk]))
            db_dc.execute(sql_str, sql_tuple)
    for ssh_type in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn  = "ssh_host_%s_key_pub" % (ssh_type)

        pubfrn = "ssh_host_%s_key.pub" % (ssh_type)
        for var in [privfn, pubfn]:
            new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_pub", ".pub")))
            new_co.bin_append(found_keys_dict[var])
            if var == privfn:
                new_co.set_mode("0600")
        if ssh_type == "rsa1":
            for var in [privfn, pubfn]:
                new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_rsa1", "").replace("_pub", ".pub")))
                new_co.bin_append(found_keys_dict[var])
                if var == privfn:
                    new_co.set_mode("0600")
    
# generate /etc/hosts for nodes, including routing-info
def do_etc_hosts(conf):
    db_dc = conf.get_cursor()
    pub_stuff = conf.dev_dict
    my_nets = pub_stuff["idxs"]
    all_netdevs = [db_rec["netdevice_idx"] for db_rec in pub_stuff["node_if"]]
    sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name as domain_name, nw.postfix, nw.short_names, h.value FROM " + \
        "device d, netip i, netdevice n, network nw, network_type nt, hopcount h WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx " + \
        "AND n.netdevice_idx=h.s_netdevice AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in all_netdevs]))
    db_dc.execute(sql_str)
    all_hosts = [[x for x in db_dc.fetchall()]]
    # self-references
    sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS domain_name, nw.postfix, nw.short_names, n.penalty AS value FROM " + \
        "device d, netip i, netdevice n, network nw, network_type nt WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND " + \
        "d.device_idx=%d ORDER BY d.name, i.ip" % (pub_stuff["device_idx"])
    db_dc.execute(sql_str)
    all_hosts.append([x for x in db_dc.fetchall()])
    # ip addresses already written
    ips_written = []
    new_co = conf.add_file_object("/etc/hosts")
    # two iterations: at first the devices that match my local networks, than the rest
    # out_list
    ips_written = []
    # two iterations: at first the devices that match my local networks, than the rest
    # out_list
    loc_dict, max_len = ({}, 0)
    for hosts in all_hosts:
        for host in hosts:
            if host["ip"] not in ips_written:
                ips_written.append(host["ip"])
                out_names = []
                # override wrong settings for lo
                if host["ip"].startswith("127.0.0.") and conf.get_config_request().get_glob_config()["CORRECT_WRONG_LO_SETUP"]:
                    host["alias"], host["alias_excl"] = ("localhost", 1)
                if not (host["alias"].strip() and host["alias_excl"]):
                    out_names.append("%s%s" % (host["name"], host["postfix"]))
                out_names.extend(host["alias"].strip().split())
                if "localhost" in [x.split(".")[0] for x in out_names]:
                    out_names = [x for x in out_names if x.split(".")[0] == "localhost"]
                if host["short_names"]:
                    # also print short_names
                    out_names = (" ".join(["%s.%s %s" % (x, host["domain_name"], x) for x in out_names])).split()
                else:
                    # only print the long names
                    out_names = ["%s.%s" % (x, host["domain_name"]) for x in out_names]
                loc_dict.setdefault(host["value"], []).append([host["ip"]] + out_names)
                max_len = max(max_len, len(out_names) + 1)
    for pen, stuff in loc_dict.iteritems():
        for l_e in stuff:
            l_e.extend([""] * (max_len-len(l_e)) + ["#%d" % (pen)])
    for p in sorted(loc_dict.keys()):
        act_list = sorted(loc_dict[p])
        max_len = [0] * len(act_list[0])
        for l in act_list:
            max_len = [max(max_len[i], len(l[i])) for i in range(len(max_len))]
        form_str = " ".join(["%%-%ds" % (x) for x in max_len])
        new_co += ["# penalty %d" % (p), ""] + [form_str % (tuple(x)) for x in act_list] + [""]

def do_hosts_equiv(conf):
    db_dc = conf.get_cursor()
    pub_stuff = conf.dev_dict
    new_co = conf.add_file_object("/etc/hosts.equiv")
    my_nets = pub_stuff["idxs"]
    all_netdevs = [x["netdevice_idx"] for x in pub_stuff["node_if"]]
    sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name as domain_name, nw.postfix, nw.short_names, h.value FROM " + \
        "device d, netip i, netdevice n, network nw, network_type nt, hopcount h WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND " + \
        "i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.s_netdevice AND (%s) ORDER BY d.name" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in all_netdevs]))
    db_dc.execute(sql_str)
    all_hosts = [[x for x in db_dc.fetchall()]]
    # self-references
    sql_str = "SELECT DISTINCT d.name, i.ip, i.alias, i.alias_excl, nw.network_idx, n.netdevice_idx, n.devname, nt.identifier, nw.name AS domain_name, nw.postfix, nw.short_names, n.penalty AS value FROM " + \
        "device d, netip i, netdevice n, network nw, network_type nt WHERE nt.network_type_idx=nw.network_type AND i.network=nw.network_idx AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND " + \
        "d.device_idx=%d ORDER BY d.name, i.ip" % (pub_stuff["device_idx"])
    db_dc.execute(sql_str)
    all_hosts.append([x for x in db_dc.fetchall()])
    out_list = []
    for hosts in all_hosts:
        for host in hosts:
            if host["network_idx"] in my_nets:
                out_names = []
                n_idx = host["netdevice_idx"]
                if not (host["alias"].strip() and host["alias_excl"]):
                    out_names.append("%s%s" % (host["name"], host["postfix"]))
                out_names.extend(host["alias"].strip().split())
                out_names = ["%s.%s" % (x, host["domain_name"]) for x in out_names]
                for out_n in out_names:
                    if out_n not in out_list:
                        out_list.append(out_n)
    out_list.sort()
    new_co += out_list
    
def get_sys_dict(dc, im_name):
    dc.execute("SELECT * FROM image i WHERE i.name='%s'" % (im_name))
    if dc.rowcount:
        image_data = dc.fetchone()
        sys_dict = {"vendor"  : image_data["sys_vendor"],
                    "version" : image_data["sys_version"],
                    "release" : image_data["sys_release"]}
        try:
            sys_dict["version"] = int(sys_dict["version"])
        except:
            sys_dict["version"] = 9
        try:
            sys_dict["release"] = int(sys_dict["release"])
        except:
            sys_dict["release"] = 0
        if sys_dict["vendor"]:
            mes_str = "found image with this name, using %s-%d.%d as vendor-id-string ..." % (sys_dict["vendor"], sys_dict["version"], sys_dict["release"])
        else:
            sys_dict = {"vendor"  : "suse",
                        "version" : 9,
                        "release" : 0}
            mes_str = "found image with this name but no sys_vendor field, using %s-%d.%d as vendor-id-string ..." % (sys_dict["vendor"], sys_dict["version"], sys_dict["release"])
    else:
        sys_dict = {"vendor"  : "suse",
                    "version" : 9,
                    "release" : 0}
        mes_str = "found no image with this name, using %s-%d.%d as vendor-id-string ..." % (sys_dict["vendor"], sys_dict["version"], sys_dict["release"])
    return sys_dict, mes_str

class network_tree(object):
    def __init__(self, c_req, dc):
        self.__c_req = c_req
        nw_nf  = ["identifier", "network_idx", "name", "postfix", "network", "netmask", "broadcast", "gateway", "gw_pri"]
        nw_sec_fields = ["sec_%s" % (x) for x in nw_nf]
        nw_ids = ["p", "l", "b"]
        # production dictionaries
        prod_dict = {}
        net_dict = {}
        dc.execute("SELECT %s, nt.identifier as prim_id, %s, t2.identifier AS sec_id FROM network nw INNER JOIN network_type nt LEFT JOIN network s ON s.master_network=nw.network_idx LEFT JOIN " % (", ".join(["nw.%s" % (x) for x in nw_nf]),
                                                                                                                                                                                                      ", ".join(["s.%s AS %s" % (x, y) for x, y in zip(nw_nf, nw_sec_fields)]))+ \
                       "network_type t2 ON t2.network_type_idx=s.network_type WHERE nw.network_type=nt.network_type_idx AND (%s)" % (" OR ".join(["nt.identifier='%s'" % (x) for x in nw_ids])))
        bootnet_idxs, loopback_idx = ([], 0)
        for db_rec in dc.fetchall():
            if not db_rec["identifier"] in net_dict.keys():
                if db_rec["prim_id"] == "l":
                    loopback_idx = db_rec["network_idx"]
                else:
                    net_dict[db_rec["identifier"]] = dict([(key, value) for key, value in db_rec.iteritems() if key not in ["sec_id"] + nw_sec_fields])
                    if db_rec["prim_id"] == "b":
                        # bootnetwork indices
                        bootnet_idxs.append(db_rec["network_idx"])
                    else:
                        prod_dict[db_rec["identifier"]] = {"net"    : net_dict[db_rec["identifier"]],
                                                           "slaves" : [],
                                                           "idxs"   : [db_rec["network_idx"]]}
            if db_rec["prim_id"] == "p" and db_rec["sec_id"] == "s":
                # slave network
                prod_dict[db_rec["identifier"]]["slaves"].append(dict([(key, db_rec[sec_key]) for key, sec_key in zip(nw_nf, nw_sec_fields)]))
                prod_dict[db_rec["identifier"]]["idxs"].append(db_rec["sec_network_idx"])
        # add loopback_idx to idxs
        if loopback_idx:
            for pd_key, pd_stuff in prod_dict.iteritems():
                pd_stuff["idxs"].append(loopback_idx)
        self.production_dict = prod_dict
        self.bootnet_idxs, self.loopback_idx = (bootnet_idxs, loopback_idx)
    def log_network(self, c_req, pd_id):
        net_stuff = self.production_dict[pd_id]
        log_str = "  %sProduction network %s has %s%s" % ("active" if net_stuff["net"]["network_idx"] == c_req["prod_link"] else "",
                                                          pd_id,
                                                          logging_tools.get_plural("slave network", len(net_stuff["slaves"])),
                                                          net_stuff["slaves"] and ": %s" % (", ".join([x["identifier"] for x in net_stuff["slaves"]])) or "")
        c_req.log(log_str)
        
def do_fstab(conf):
    act_ps = partition_setup(conf.get_config_request(), conf.get_cursor())
    fstab_co = conf.add_file_object("/etc/fstab")
    if act_ps.valid:
        fstab_co += act_ps.fstab
    
class build_thread(threading_tools.thread_obj):
    """ handles build_requests for the complete config """
    def __init__(self, log_queue, db_con, glob_config, loc_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        self.__loc_config = loc_config
        threading_tools.thread_obj.__init__(self, "build", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("build_config"  , self._build_config)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("srv_send_ok"    , self._srv_send_ok)
        self.register_func("srv_send_error" , self._srv_send_error)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, node_name=""):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        # clear queue dict
        self.__queue_dict = {}
        # clear net_server
        self.__net_server = None
    def _set_net_server(self, ns):
        self.log("Netserver set")
        self.__net_server = ns
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _build_config(self, dev_name):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        c_req = config_request(self, self.__glob_config, self.__loc_config, "build_config", "build_config", dev_name=dev_name)
        c_req.create_base_structs(dc)
        if c_req.pending:
            c_req.create_config(dc)
        c_req.log_ret_str()
        self.__queue_dict["config"].put(("build_done", (dev_name, c_req.get_ret_str())))
        del c_req
        dc.release()
        self._send_message_to_nagios_server(dev_name)
    def _send_message_to_nagios_server(self, dev_name):
        if self.__loc_config["NAGIOS_IP"]:
            self.log("sending 'host_config_done' to %s (device %s)" % (self.__loc_config["NAGIOS_IP"],
                                                                       dev_name))
            self.__net_server.add_object(net_tools.tcp_con_object(self._new_nagios_server_connection,
                                                                  connect_state_call=self._ncs_connect_state_call,
                                                                  connect_timeout_call=self._ncs_connect_timeout,
                                                                  timeout=10,
                                                                  bind_retries=1,
                                                                  rebind_wait_time=1,
                                                                  target_port=self.__glob_config["NAGIOS_PORT"],
                                                                  target_host=self.__loc_config["NAGIOS_IP"],
                                                                  add_data=(server_command.server_command(command="host_config_done", nodes=[dev_name]), self.__loc_config["NAGIOS_IP"])))
    def _new_nagios_server_connection(self, sock):
        return connection_to_nagios_server(sock.get_add_data(), self.get_thread_queue())
    def _ncs_connect_timeout(self, sock):
        self.get_thread_queue().put(("srv_send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _ncs_connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("srv_send_error", (args["socket"].get_add_data(), "connection error")))
    def _srv_send_error(self, ((srv_com, srv_name), why)):
        self.log("Error sending server_command %s to server %s: %s" % (srv_com.get_command(), srv_name, why), logging_tools.LOG_LEVEL_ERROR)
    def _srv_send_ok(self, ((srv_com, srv_name), result)):
        self.log("Sent server_command %s to server %s (got %s)" % (srv_com.get_command(),
                                                                   srv_name,
                                                                   server_command.server_reply(result).get_result()))
        
class config_request(object):
    """ to hold all the necessary data for a simple config request """
    def __init__(self, sc_thread, glob_config, loc_config, command, src_data, **args):
        # simple_config_thread
        self.__sc_thread = sc_thread
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        if args.has_key("src_part"):
            self.__source_host, self.__source_port = args["src_part"]
        else:
            self.__source_host, self.__source_port = (None, None)
        if args.has_key("dev_name"):
            self.__dev_name = args["dev_name"]
        else:
            self.__dev_name = None
        self.thread_key = args.get("thread_key", 0)
        self.send_to_thread = True
        self.full_src_data, self.command = (src_data, command)
        # build rest of commandline
        data_parts = self.full_src_data.split()
        data_parts.pop(0)
        self.data_parts = data_parts
        self.__node_record = None
        self.__start_time = time.time()
        self.set_ret_str()
        # true until an error occurs or the request is done
        self.pending = True
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__node_record:
            self.__sc_thread.log(what, lev, self.__node_record["name"])
        else:
            self.__sc_thread.log(what, lev)
    def get_glob_config(self):
        return self.__glob_config
    def get_loc_config(self):
        return self.__loc_config
    def get_source_host(self):
        return self.__source_host
    def set_ret_str(self, ret_str="error not set"):
        self.__ret_str = ret_str
        if self.__ret_str.startswith("error"):
            self.pending = False
    def get_ret_str(self):
        return self.__ret_str
    def __getitem__(self, key):
        return self.__node_record[key]
    def __setitem__(self, key, value):
        self.__node_record[key] = value
    def find_route_to_server(self, vs_struct, dc):
        route_ok = False
        server_routing = vs_struct.get_route_to_other_device(dc, self.__conf_dev, filter_ip=self.__source_host)
        if server_routing:
            route_ok = True
            self.server_ip = server_routing[0][2][1][0]
        else:
            self.log("found no route to server (from ip %s)" % (self.__source_host))
            self.set_ret_str("error no route to server found")
        return route_ok
    def create_base_structs(self, dc):
        # resolve ip to device_name (cache, FIXME)
        if self.__source_host:
            # source_host given, resolve according to ip
            sql_str, sql_tuple = ("SELECT d.new_image, d.name, d.root_passwd, d.device_idx, d.prod_link, s.status, d.rsync, d.rsync_compressed, d.bootnetdevice, d.bootserver, i.ip, dg.device, dt.identifier FROM " + \
                                      "status s, device d, netdevice nd, netip i, network nw, network_type nt, device_group dg, device_type dt WHERE d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx " + \
                                      "AND nd.device=d.device_idx AND i.netdevice=nd.netdevice_idx AND (nt.identifier='b' OR nt.identifier='p') AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND " + \
                                      "i.ip=%s AND s.status_idx=d.newstate", (self.__source_host))
        else:
            sql_str, sql_tuple = ("SELECT d.new_image, d.name, d.root_passwd, d.device_idx, d.prod_link, s.status, d.rsync, d.rsync_compressed, d.bootnetdevice, d.bootserver, i.ip, dg.device, dt.identifier FROM " + \
                                      "status s, device d, netdevice nd, netip i, network nw, network_type nt, device_group dg, device_type dt WHERE d.device_group=dg.device_group_idx AND d.device_type=dt.device_type_idx " + \
                                      "AND nd.device=d.device_idx AND i.netdevice=nd.netdevice_idx AND nt.identifier='b' AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND " + \
                                      "d.name=%s AND s.status_idx=d.newstate", (self.__dev_name))
        dc.execute(sql_str, sql_tuple)
        if dc.rowcount:
            self.__node_record = dc.fetchone()
            #print self.__node_record
            # set device_name and source_host from db
            self.__dev_name = self.__node_record["name"]
            self.__source_host = self.__node_record["ip"]
            self.__conf_dev = config_tools.server_check(dc=dc,
                                                        short_host_name=self.__node_record["name"],
                                                        # type is not so important here because the device_idx is resolved from the name
                                                        server_type="node",
                                                        fetch_network_info=True)
        else:
            if dc.rowcount:
                self.log("Found more than one device (%d) matching IP-address %s (command %s)" % (dc.rowcount,
                                                                                                  self.__source_host,
                                                                                                  self.command),
                         logging_tools.LOG_LEVEL_WARN)
                self.set_ret_str("error resolving ip-address ('%s' not unique), see logs" % (self.__source_host))
            else:
                self.log("found no device matching IP-address %s (command %s)" % (self.__source_host,
                                                                                  self.command),
                         logging_tools.LOG_LEVEL_WARN)
                self.set_ret_str("error resolving ip-address ('%s' not found), see logs" % (self.__source_host))
    def get_config_str_vars(self, dc, cs_name, **args):
        dc.execute("SELECT cs.value, dc.device FROM new_config c INNER JOIN device_config dc INNER JOIN device_group dg INNER JOIN " + \
                       "device d LEFT JOIN config_str cs ON cs.new_config=c.new_config_idx LEFT JOIN device d2 on d2.device_idx=dg.device WHERE " + \
                       "cs.name=%s AND d.device_group=dg.device_group_idx AND dc.new_config=c.new_config_idx AND (d2.device_idx=dc.device OR " + \
                       "d.device_idx=dc.device) AND d.device_idx=%s ORDER BY c.priority DESC", (cs_name, self["device_idx"]))
        ent_list = []
        for db_rec in dc.fetchall():
            for act_val in [part.strip() for part in db_rec["value"].split() if part.strip()]:
                if act_val not in ent_list:
                    ent_list.append(act_val)
        return ent_list
    def log_ret_str(self):
        end_time = time.time()
        # logging
        if self.__ret_str.startswith("ok"):
            log_level = logging_tools.LOG_LEVEL_OK
        elif self.__ret_str.startswith("error"):
            log_level = logging_tools.LOG_LEVEL_ERROR
        else:
            log_level = logging_tools.LOG_LEVEL_WARN
        log_str = "return for command '%s' from %s (took %s): %s" % (self.command,
                                                                     self.__source_host,
                                                                     logging_tools.get_diff_time_str(end_time - self.__start_time),
                                                                     self.__ret_str)
        self.log(log_str, log_level)
        self.__node_record = None
        self.__conf_dev = None
    def get_kernel_info_str(self, dc):
        # get kernel info (kernel_str)
        dc.execute("SELECT d.newkernel, d.new_kernel FROM device d WHERE d.device_idx=%s", (self["device_idx"]))
        kernel_info = dc.fetchone()
        if kernel_info["new_kernel"] and not self.__glob_config["PREFER_KERNEL_NAME"]:
            dc.execute("SELECT k.name, k.version, k.release FROM kernel k WHERE k.kernel_idx=%s", (kernel_info["new_kernel"]))
            if dc.rowcount:
                kernel_line = dc.fetchone()
                kernel_str = "%s %s %s" % (kernel_line["name"],
                                           kernel_line["version"],
                                           kernel_line["release"])
                log_str = "new method"
            else:
                kernel_str = kernel_info["name"]
                log_str = "old method, no kernel with kernel_idx %d found" % (kernel_info["new_kernel"])
        else:
            kernel_str = kernel_info["newkernel"] 
            log_str = "old method, no kernel defined"
        self.log("using kernel_str '%s' (%s)" % (kernel_str,
                                                 log_str))
        return kernel_str
    def create_config_dir(self):
        ret_str = "ok config_dir is ok"
        base_dir = self.__glob_config["CONFIG_DIR"]
        node_dir, node_link = ("%s/%s" % (base_dir, self.__source_host),
                               "%s/%s" % (base_dir, self["name"]))
        self.node_dir = node_dir
        if not os.path.isdir(node_dir):
            try:
                os.mkdir(node_dir)
            except OSError:
                self.log("cannot create config_directory %s: %s" % (node_dir,
                                                                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                ret_str = "error creating config directory"
            else:
                self.log("created config directory %s" % (node_dir))
        if os.path.isdir(node_dir):
            if os.path.islink(node_link):
                if os.readlink(node_link) != self.__source_host:
                    try:
                        os.unlink(node_link)
                    except:
                        self.log("cannot delete wrong link %s: %s" % (node_link,
                                                                      process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        ret_str = "error deleting wrong link"
                    else:
                        self.log("Removed wrong link %s" % (node_link))
            if not os.path.islink(node_link):
                try:
                    os.symlink(self.__source_host, node_link)
                except:
                    self.log("cannot create link from %s to %s: %s" % (node_link,
                                                                       self.__source_host,
                                                                       process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    ret_str = "error creating link"
                else:
                    self.log("Created link from %s to %s" % (node_link,
                                                             self.__source_host))
        return ret_str
    def create_pinfo_dir(self):
        ret_str = "ok pinfo_dir is ok"
        base_dir = self.__glob_config["CONFIG_DIR"]
        pinfo_dir = "%s/%s/pinfo" % (base_dir, self.__source_host)
        self.pinfo_dir = pinfo_dir
        if not os.path.isdir(pinfo_dir):
            try:
                os.mkdir(pinfo_dir)
            except OSError:
                self.log("cannot create pinfo_directory %s: %s" % (pinfo_dir,
                                                                   process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                ret_str = "error creating pinfo directory"
            else:
                self.log("created pinfo directory %s" % (pinfo_dir))
        if os.path.isdir(pinfo_dir):
            for file_name in os.listdir(pinfo_dir):
                try:
                    os.unlink("%s/%s" % (pinfo_dir, file_name))
                except:
                    self.log("error removing %s in %s: %s" % (file_name,
                                                              pinfo_dir,
                                                              process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
        return ret_str
    def _handle_get_partition(self, dc):
        if self.data_parts:
            self.create_config_dir()
            self.create_pinfo_dir()
            root_part = self.data_parts[0]
            self.log("setting partition-device to '%s'" % (root_part))
            dc.execute("UPDATE device SET partdev=%s WHERE device_idx=%s AND fixed_partdev=0", (root_part,
                                                                                                self["device_idx"]))
            p_setup = partition_setup(self, dc)
            p_setup.create_part_files(self)
            self.set_ret_str(p_setup.ret_str)
        else:
            self.set_ret_str("error no partition name given from node")
    def _clean_directory(self, pd_key):
        # cleans directory of network_key
        rem_file_list, rem_dir_list = ([], [])
        dir_list = ["%s/configdir_%s" % (self.node_dir, pd_key),
                    "%s/config_dir_%s" % (self.node_dir, pd_key),
                    "%s/content_%s" % (self.node_dir, pd_key)]
        file_list = ["%s/config_%s" % (self.node_dir, pd_key),
                     "%s/configl_%s" % (self.node_dir, pd_key),
                     "%s/config_d%s" % (self.node_dir, pd_key)]
        for old_name in dir_list:
            if os.path.isdir(old_name):
                for file_name in os.listdir(old_name):
                    rem_file_list.append("%s/%s" % (old_name, file_name))
                rem_dir_list.append(old_name)
        for old_name in file_list:
            if os.path.isfile(old_name):
                rem_file_list.append(old_name)
        # remove files and dirs
        num_removed = {"file" : 0,
                       "dir"  : 0}
        for del_name in rem_file_list + rem_dir_list:
            try:
                if os.path.isfile(del_name):
                    ent_type = "file"
                    os.unlink(del_name)
                else:
                    ent_type = "dir"
                    os.rmdir(del_name)
            except:
                self.log("error removing %s %s: %s" % (ent_type, del_name, process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                num_removed[ent_type] += 1
        if sum(num_removed.values()):
            self.log("removed %s for key '%s'" % (" and ".join([logging_tools.get_plural(key, value) for key, value in num_removed.iteritems()]),
                                                  pd_key))
        else:
            self.log("config on disk for key '%s' was empty" % (pd_key))
    def _fetch_image_info(self, dc):
        dc.execute("SELECT d.newimage, d.new_image, i.* FROM device d, image i WHERE d.device_idx=%d AND (i.name = d.newimage OR i.image_idx=d.new_image)" % (self["device_idx"]))
        if dc.rowcount:
            image_data = dc.fetchone()
            # set system_dict
            sys_dict = {"vendor"  : image_data["sys_vendor"],
                        "version" : image_data["sys_version"],
                        "release" : image_data["sys_release"]}
            try:
                sys_dict["version"] = int(sys_dict["version"])
            except:
                sys_dict["version"] = 9
            try:
                sys_dict["release"] = int(sys_dict["release"])
            except:
                sys_dict["release"] = 0
            if sys_dict["vendor"]:
                self.log("found image %s, using %s-%d.%d as vendor-id-string ..." % (image_data["name"],
                                                                                     sys_dict["vendor"],
                                                                                     sys_dict["version"],
                                                                                     sys_dict["release"]))
            else:
                sys_dict = {"vendor"  : "suse",
                            "version" : 9,
                            "release" : 0}
                self.log("found image %s but no sys_vendor field, using %s-%d.%d as vendor-id-string ..." % (image_data["name"],
                                                                                                             sys_dict["vendor"],
                                                                                                             sys_dict["version"],
                                                                                                             sys_dict["release"]),
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            sys_dict = {"vendor"  : "suse",
                        "version" : 9,
                        "release" : 0}
            image_data = {}
            self.log("found no image for this device, using %s-%d.%d as vendor-id-string ..." % (sys_dict["vendor"],
                                                                                                 sys_dict["version"],
                                                                                                 sys_dict["release"]),
                     logging_tools.LOG_LEVEL_ERROR)
        self["image_info"] = image_data
        self["system_dict"] = sys_dict
    def create_config(self, dc):
        # creates the configuration
        self.log("starting build config (device_idx is %d, meta_device_idx is %d)" % (self["device_idx"],
                                                                                      self["device"]))
        # fetch image
        self._fetch_image_info(dc)
        # build network tree
        act_network_tree = network_tree(self, dc)
        ccdir_log = self.create_config_dir()
        if ccdir_log.startswith("error"):
            self.set_ret_str(ccdir_log)
        # some sanity checks
        elif not self["prod_link"]:
            self.set_ret_str("error no valid production_link set")
        elif "b" not in self.__conf_dev.identifier_ip_lut.keys():
            self.set_ret_str("error no address in maintenance (boot) network found")
        elif len(act_network_tree.bootnet_idxs) > 2:
            self.set_ret_str("error more than one boot network found")
        elif len(act_network_tree.bootnet_idxs) == 0:
            self.set_ret_str("error no boot network found")
        elif not act_network_tree.production_dict:
            self.set_ret_str("error no production networks found")
        elif not self["image_info"]:
            self.set_ret_str("error no image defined")
        else:
            maint_ip = self.__conf_dev.identifier_ip_lut["b"][0]
            self.log("boot-ip is %s, config_directory is %s" % (maint_ip, self.node_dir))
            self.log("found %s: %s" % (logging_tools.get_plural("production network", len(act_network_tree.production_dict.keys())),
                                       ", ".join(act_network_tree.production_dict.keys())))
            # search active id
            active_identifier = None
            for pd_key, pd_dict in act_network_tree.production_dict.iteritems():
                self._clean_directory(pd_key)
                act_network_tree.log_network(self, pd_key)
                if pd_dict["net"]["network_idx"] == self["prod_link"] and pd_dict["net"]["prim_id"] == "p":
                    active_identifier = pd_key
                    # this is one of our main dictionaries
                    act_prod_net = pd_dict
            if not active_identifier:
                self.set_ret_str("error invalid production link %d set" % (self["prod_link"]))
            else:
                # ips in active production net
                ips_in_net = self.__conf_dev.identifier_ip_lut.get("p", [])
                if ips_in_net:
                    netdevices_in_net = [self.__conf_dev.ip_netdevice_lut[ip] for ip in ips_in_net]
                    net_idxs_ok   = [idx for idx in netdevices_in_net if idx == self["bootnetdevice"]]
                    net_idxs_warn = [idx for idx in netdevices_in_net if idx != self["bootnetdevice"]]
                    if len(net_idxs_ok) == 1:
                        boot_netdev_idx = net_idxs_ok[0]
                    elif len(net_idxs_ok) > 1:
                        self.set_ret_str("error too many netdevices (%d) with IP in production network %s found" % (len(net_idxs_ok), active_identifier))
                    elif len(net_idxs_warn) == 1:
                        self.log("  one netdevice with IP in production network %s found, NOT on bootnetdevice!" % (active_identifier),
                                 logging_tools.LOG_LEVEL_WARN)
                        boot_netdev_idx = net_idxs_warn[0]
                    else:
                        self.set_ret_str("error Too many netdevices (%d) with IP in production network %s found (NOT on bootnetdevice!)" % (len(net_idxs_warn),
                                                                                                                                            active_identifier))
                else:
                    self.set_ret_str("error No netdevices with IP in production network %s found" % (active_identifier))
            if self.pending:
                full_network_name = "%s.%s" % (act_prod_net["net"]["postfix"],
                                               act_prod_net["net"]["name"])
                # get ip-address of production network
                running_ip = [ip for ip in self.__conf_dev.identifier_ip_lut["p"] if self.__conf_dev.ip_netdevice_lut[ip] == boot_netdev_idx][0]
                self.log("IP in production network '%s' is %s, full_network_name is '%s'" % (act_prod_net["net"]["identifier"],
                                                                                             running_ip,
                                                                                             full_network_name))
                         #print "OK", active_identifier, boot_netdev_idx, running_ip
                # multiple_configs
                multiple_configs = ["server"]
                # get all servers
                all_servers = config_tools.device_with_config("%server%", dc)
                all_servers.set_key_type("config")
                def_servers = all_servers.get("server", [])
                if def_servers:
                    act_prod_net["servers"] = sorted(["%s%s" % (s_struct.short_host_name, full_network_name) for s_struct in def_servers])
                    self.log("found %s: %s" % (logging_tools.get_plural("server", len(def_servers)),
                                               ", ".join(act_prod_net["servers"])))
                    for config_type in sorted(all_servers.keys()):
                        if config_type not in multiple_configs:
                            routing_info, act_server = ([666666], None)
                            for actual_server in all_servers[config_type]:
                                act_routing_info = actual_server.get_route_to_other_device(dc, self.__conf_dev, filter_ip=running_ip)
                                if act_routing_info:
                                    # store detailed config
                                    act_prod_net["%s:%s" % (actual_server.short_host_name, config_type)] = "%s%s" % (actual_server.short_host_name, full_network_name)
                                    act_prod_net["%s:%s_ip" % (actual_server.short_host_name, config_type)] = act_routing_info[0][2][1][0]
                                    if config_type in ["config_server", "mother_server"] and actual_server.server_device_idx == self["bootserver"]:
                                        # always take the bootserver
                                        routing_info, act_server = (act_routing_info[0], actual_server)
                                    else:
                                        if act_routing_info[0][0] < routing_info[0]:
                                            routing_info, act_server = (act_routing_info[0], actual_server)
                                else:
                                    self.log("empty routing info", logging_tools.LOG_LEVEL_WARN)
                            if act_server:
                                server_ip = routing_info[2][1][0]
                                act_prod_net[config_type] = "%s%s" % (act_server.short_host_name, full_network_name)
                                act_prod_net["%s_ip" % (config_type)] = server_ip
                                self.log("  %20s: %-25s (IP %15s)" % (config_type,
                                                                      act_prod_net[config_type],
                                                                      server_ip))
                            else:
                                self.log("  %20s: not found" % (config_type))
                    #pprint.pprint(act_prod_net)
                    #print self["image_info"], self.__system_dict
                    # add stuff to production net
                    act_prod_net["system"]            = self["system_dict"]
                    act_prod_net["host"]              = self["name"]
                    act_prod_net["hostfq"]            = "%s%s" % (self["name"], full_network_name)
                    act_prod_net["device_idx"]        = self["device_idx"]
                    act_prod_net["bootnetdevice_idx"] = self["bootnetdevice"]
                    act_prod_net["bootserver_idx"]    = self["bootserver"]
                    dc.execute("SELECT * FROM image WHERE image_idx=%s", (self["new_image"]))
                    if dc.rowcount:
                        act_prod_net["image"] = dc.fetchone()
                    else:
                        act_prod_net["image"] = {}
                    # fetch configs (cannot use sets because the order is important)
                    config_list, pseudo_config_list = ([], [])
                    config_dict = {}
                    dc.execute("SELECT DISTINCT c.name, c.description, c.new_config_idx, c.priority, ct.name AS identifier, dc.device FROM new_config c, device_config dc, new_config_type ct WHERE dc.new_config=c.new_config_idx AND c.new_config_type=ct.new_config_type_idx AND (dc.device=%s OR dc.device=%s) ORDER BY c.priority DESC, c.name", (self["device_idx"], self["device"]))
                    for db_rec in dc.fetchall():
                        if db_rec["name"] not in config_list:
                            config_list.append(db_rec["name"])
                            act_nc = new_config(db_rec, self)
                            config_dict[act_nc.get_name()] = act_nc
                            config_dict[db_rec["new_config_idx"]] = act_nc
                    # fetch configs not used for this device
                    dc.execute("SELECT DISTINCT c.name, c.description, c.new_config_idx, c.priority, ct.name AS identifier FROM new_config c, new_config_type ct WHERE ct.new_config_type_idx=c.new_config_type ORDER BY c.priority DESC, c.name")
                    for db_rec in dc.fetchall():
                        if db_rec["name"] not in config_list:
                            pseudo_config_list.append(db_rec["name"])
                            act_pc = pseudo_config(db_rec, self)
                            config_dict[act_pc.get_name()] = act_pc
                            config_dict[db_rec["new_config_idx"]] = act_pc
                    # fetch variables
                    var_types = ["int", "str", "blob", "script"]
                    for var_type in var_types:
                        dc.execute("SELECT * FROM config_%s%s" % (var_type,
                                                                  " ORDER BY priority" if var_type == "script" else ""))
                        for db_rec in dc.fetchall():
                            act_conf = config_dict.get(db_rec["new_config"], None)
                            if act_conf and act_conf.add_variable(var_type, db_rec) and var_type != "script":
                                act_prod_net["%s.%s" % (act_conf.get_name(), db_rec["name"])] = db_rec["value"]
                    # log variables
                    for conf_name in config_list + pseudo_config_list:
                        config_dict[conf_name].show_variables()
                    self.log("%s found : %s" % (logging_tools.get_plural("config", len(config_list)),
                                                ", ".join(config_list)) if config_list else "no config found")
                    # build node interface list
                    dc.execute("SELECT n.devname, n.netdevice_idx, n.macadr, i.ip, nw.gw_pri, n.fake_macadr, nw.network_idx, nw.network, nw.netmask, nw.broadcast, nw.gateway, nw.name, nw.postfix, nt.identifier, nw.write_other_network_config FROM " + \
                                   "netdevice n, netip i, network nw, network_type nt WHERE n.device=%d AND nt.network_type_idx=nw.network_type AND i.netdevice=n.netdevice_idx AND nw.network_idx=i.network ORDER BY n.devname" % (self["device_idx"]))
                    act_prod_net["node_if"] = []
                    taken_list, not_taken_list = ([], [])
                    for db_rec in dc.fetchall():
                        #take_it 
                        if db_rec["network_idx"] in act_prod_net["idxs"]:
                            take_it, cause = (1, "network_index in list")
                        else:
                            if db_rec["write_other_network_config"]:
                                take_it, cause = (1, "network_index not in list but write_other_network_config set")
                            else:
                                take_it, cause = (0, "network_index not in list and write_other_network_config not set")
                        if take_it:
                            act_prod_net["node_if"].append(db_rec)
                            taken_list.append((db_rec["devname"], db_rec["ip"], db_rec["name"], cause))
                        else:
                            not_taken_list.append((db_rec["devname"], db_rec["ip"], db_rec["name"], cause))
                    self.log("%s in taken_list" % (logging_tools.get_plural("Netdevice", len(taken_list))))
                    for entry in taken_list:
                        self.log("  - %-6s (IP %-15s, network %-20s) : %s" % tuple(entry))
                    self.log("%s in not_taken_list" % (logging_tools.get_plural("Netdevice", len(not_taken_list))))
                    for entry in  not_taken_list:
                        self.log("  - %-6s (IP %-15s, network %-20s) : %s" % tuple(entry))
                    # now build the config
                    self.__warn_configs, self.__error_configs = ([], [])
                    # add config dict
                    config_obj = internal_object("CONFIG_VARS")
                    config_obj.add_config("config_vars")
                    conf_lines = pretty_print("", act_prod_net, 0)
                    #print "\n".join(conf_lines)
                    for conf_line in conf_lines:
                        config_obj += "%s" % (conf_line)
                    # config dict, link dict and erase dict
                    self.conf_dict, self.link_dict, self.erase_dict = ({}, {}, {})
                    self.conf_dict[config_obj.get_dest()] = config_obj
                    act_prod_net["called"] = {}
                    for conf_name in config_list:
                        config_dict[conf_name].process_scripts(act_prod_net, dc)
                    # write config
                    num_dict = self._write_config(dc, act_prod_net, active_identifier)
                    # cleanup code
                    del config_dict
                    self.log("building took %s (%s)" % (logging_tools.get_diff_time_str(time.time() - self.__start_time),
                                                        logging_tools.get_plural("SQL call", dc.get_exec_counter())))
                    log_str = "wrote %s, %s, %s, %s (%s, %s)" % (logging_tools.get_plural("file", num_dict["f"]),
                                                                 logging_tools.get_plural("link", num_dict["l"]),
                                                                 logging_tools.get_plural("dir", num_dict["d"]),
                                                                 logging_tools.get_plural("delete", num_dict["e"]),
                                                                 "%s [%s]" % (logging_tools.get_plural("warning", len(self.__warn_configs)), ", ".join(self.__warn_configs)) if self.__warn_configs else "no warnings",
                                                                 "%s [%s]" % (logging_tools.get_plural("error", len(self.__error_configs)), ", ".join(self.__error_configs)) if self.__error_configs else "no errors")
                    if self.__error_configs:
                        self.log(log_str, logging_tools.LOG_LEVEL_ERROR)
                        ret_str = "error generating config, see logs"
                    elif self.__warn_configs:
                        self.log(log_str, logging_tools.LOG_LEVEL_WARN)
                        ret_str = "ok generated config with warnings"
                    else:
                        self.log(log_str)
                        ret_str = "ok generated config"
                    self.set_ret_str(ret_str)
                else:
                    self.set_ret_str("error found no servers")
    def _write_config(self, dc, act_prod_net, active_identifier):
        config_dir = "%s/content_%s" % (self.node_dir, active_identifier)
        if not os.path.isdir(config_dir):
            self.log("creating directory %s" % (config_dir))
            os.mkdir(config_dir)
        write_type_dict = {"f" : "f",
                           "c" : "f",
                           "l" : "l",
                           "d" : "d",
                           "e" : "e"}
        config_dict = {"f" : "%s/config_files_%s" % (self.node_dir, active_identifier),
                       "l" : "%s/config_links_%s" % (self.node_dir, active_identifier),
                       "d" : "%s/config_dirs_%s" % (self.node_dir, active_identifier),
                       "e" : "%s/config_delete_%s" % (self.node_dir, active_identifier)}
        handle_dict = {}
        num_dict = dict([(v, 0) for v in write_type_dict.keys()])
        dc.execute("DELETE FROM wc_files WHERE device=%d" % (self["device_idx"]))
        sql_write_list = []
        for config_type in ["i", "f", "c", "l", "d", "e"]:
            if config_type == "l":
                act_dict = self.link_dict
            elif config_type == "e":
                act_dict = self.erase_dict
            else:
                act_dict = self.conf_dict
            klist = sorted([key for key in act_dict.keys() if act_dict[key].get_type() == config_type])
            if klist:
                real_fo = write_type_dict.get(config_type, None)
                if real_fo:
                    handle = handle_dict.setdefault(real_fo, file(config_dict[real_fo], "w"))
                else:
                    handle = None
                for file_name in klist:
                    #print config_type, file_name
                    if real_fo:
                        num_dict[real_fo] += 1
                        acf_name = "%s/%d" % (config_dir, num_dict[real_fo])
                    else:
                        acf_name = None
                    act_co = act_dict[file_name]
                    state, add_line, sql_tuples = act_co.write_object(acf_name, num_dict.get(real_fo, 0))
                    sql_write_list.append(sql_tuples)
                    if not state:
                        if handle:
                            handle.write("%s\n" % (add_line))
                    else:
                        if add_line:
                            self.log(add_line, logging_tools.LOG_LEVEL_ERROR)
                            self.register_config_error("error creating file '%s'" % (file_name))
        for sql_tuple in sql_write_list:
            dc.execute("INSERT INTO wc_files VALUES(0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, null)", tuple([self["device_idx"]] + list(sql_tuple)))
        self.log("closing %s" % (logging_tools.get_plural("handle", len(handle_dict.keys()))))
        [handle.close() for handle in handle_dict.values()]
        return num_dict
    def register_config_warning(self, warn_cause):
        self.__warn_configs.append(warn_cause)
    def register_config_error(self, error_cause):
        self.__error_configs.append(error_cause)

class partition_setup(object):
    def __init__(self, c_req, dc):
        dc.execute("SELECT pt.name, pt.partition_table_idx, pt.valid, pd.*, p.*, ps.name AS psname, d.partdev FROM partition_table pt " + \
                       "INNER JOIN device d LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN " + \
                       "partition p ON p.partition_disc=pd.partition_disc_idx LEFT JOIN partition_fs ps ON ps.partition_fs_idx=p.partition_fs " + \
                       "WHERE d.device_idx=%s AND d.partition_table=pt.partition_table_idx ORDER BY pd.priority, p.pnum", (c_req["device_idx"]))
        root_dev = None
        part_valid = False
        if dc.rowcount:
            part_valid = True
            disc_dict, fstab, sfdisk, parted = ({}, [], [], [])
            fspart_dict = {}
            first_disc, root_part, root_part_type = (None, None, None)
            old_pnum = 0
            lower_size, upper_size = (0, 0)
            for db_rec in dc.fetchall():
                if root_dev is None:
                    root_dev = db_rec["partdev"]
                    # partition prefix for cciss partitions
                    part_pf = "p" if root_dev.count("cciss") else ""
                is_valid, pt_name, part_table_idx = (db_rec["valid"], db_rec["name"], db_rec["partition_table_idx"])
                if not is_valid:
                    part_valid = False
                    break
                if db_rec["disc"]:
                    act_pnum, act_disc = (db_rec["pnum"], db_rec["disc"])
                    if not first_disc:
                        first_disc = act_disc
                    if act_disc == first_disc:
                        act_disc = root_dev
                    disc_dict.setdefault(act_disc, {})
                    if act_pnum:
                        disc_dict[act_disc][act_pnum] = db_rec
                    # generate sfdisk-entry
                    while old_pnum < act_pnum-1:
                        old_pnum += 1
                        sfdisk.append(",0, ")
                    if db_rec["size"] and db_rec["psname"] != "ext":
                        upper_size += db_rec["size"]
                    else:
                        upper_size = 0
                    parted.append("mkpart %s %s %s %s" % (db_rec["psname"] == "ext" and "extended" or (act_pnum < 5 and "primary" or "logical"),
                                                          {"ext3" : "ext2",
                                                           "swap" : "linux-swap",
                                                           "ext"  : ""}.get(db_rec["psname"], db_rec["psname"]),
                                                          "%d" % (lower_size),
                                                          db_rec["psname"] == "ext" and "_" or (upper_size and "%d" % (upper_size) or "_")
                                                          ))
                    if upper_size:
                        lower_size = upper_size
                    else:
                        upper_size = lower_size
                    if db_rec["size"] and db_rec["psname"] != "ext":
                        sfdisk.append(",%d,0x%s" % (db_rec["size"], db_rec["partition_hex"]))
                    else:
                        sfdisk.append(",,0x%s" % (db_rec["partition_hex"]))
                    if db_rec["psname"]:
                        fs = db_rec["psname"]
                    else:
                        fs = "auto"
                    if db_rec["mountpoint"] or fs == "swap":
                        act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                        mp = db_rec["mountpoint"] if db_rec["mountpoint"] else fs
                        if mp == "/":
                            root_part, root_part_type = (act_part, fs)
                        if not fspart_dict.has_key(fs):
                            fspart_dict[fs] = []
                        fspart_dict[fs].append(act_part)
                        fstab.append("%-20s %-10s %-10s %-10s %d %d" % (act_part, mp, fs, db_rec["mount_options"] and db_rec["mount_options"] or "rw", db_rec["fs_freq"], db_rec["fs_passno"]))
                old_pnum = act_pnum
            c_req.log("  creating partition info for partition_table '%s' (root_device %s, partition postfix is '%s')" % (pt_name, root_dev, part_pf))
            if part_valid:
                dc.execute("SELECT s.* FROM sys_partition s WHERE s.partition_table=%s", (part_table_idx))
                for db_rec in dc.fetchall():
                    fstab.append("%-20s %-10s %-10s %-10s %d %d" % (db_rec["name"], db_rec["mountpoint"], db_rec["name"], db_rec["mount_options"] and db_rec["mount_options"] or "rw", 0, 0))
                self.fspart_dict, self.root_part, self.root_part_type, self.fstab, self.sfdisk, self.parted = (fspart_dict,
                                                                                                               root_part,
                                                                                                               root_part_type,
                                                                                                               fstab,
                                                                                                               sfdisk,
                                                                                                               parted)
                # logging
                for what, name in [(fstab, "fstab"),
                                   (sfdisk, "sfdisk")]:
                    c_req.log("Content of %s (%s):" % (name, logging_tools.get_plural("line", len(what))))
                    for line_num, line in zip(xrange(len(what)), what):
                        c_req.log(" - %3d %s" % (line_num + 1, line))
                self.ret_str = "ok %s" % (pt_name)
            else:
                c_req.log("  Partition-table %s is not valid" % (pt_name), logging_tools.LOG_LEVEL_ERROR)
                self.ret_str = "error partition_table %s is invalid" % (pt_name)
        else:
            c_req.log("  Found no partition-info", logging_tools.LOG_LEVEL_ERROR)
            self.ret_str = "error found no partition info"
        self.valid = part_valid
    def create_part_files(self, c_req):
        for pn, pp in self.fspart_dict.iteritems():
            file("%s/%sparts" % (c_req.pinfo_dir, pn), "w").write("\n".join(pp + [""]))
        for file_name, content in [("rootpart"    , self.root_part),
                                   ("rootparttype", self.root_part_type),
                                   ("fstab"       , "\n".join(self.fstab)),
                                   ("sfdisk"      , "\n".join(self.sfdisk)),
                                   ("parted"      , "\n".join(self.parted))]:
            file("%s/%s" % (c_req.pinfo_dir, file_name), "w").write("%s\n" % (content))
        
class config_thread(threading_tools.thread_obj):
    """ handles (simple) config requests from the nodes """
    def __init__(self, log_queue, db_con, glob_config, loc_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        self.__loc_config = loc_config
        threading_tools.thread_obj.__init__(self, "config", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("simple_command", self._simple_command)
        self.register_func("direct_command", self._direct_command)
        self.register_func("build_done"    , self._build_done)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, node_name=""):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        # clear queue dict
        self.__queue_dict = {}
        # handler for simple commands
        self.__command_handler_dict = {"get_target_sn"           : self._handle_get_target_sn,
                                       "get_partition"           : self._handle_get_partition,
                                       "get_image"               : self._handle_get_image,
                                       "get_kernel"              : self._handle_get_kernel,
                                       "get_kernel_name"         : self._handle_get_kernel,
                                       "set_kernel"              : self._handle_set_kernel,
                                       "create_config"           : self._handle_create_config,
                                       "ack_config"              : self._handle_ack_config,
                                       "get_syslog_server"       : self._handle_get_syslog_server,
                                       "get_package_server"      : self._handle_get_package_server,
                                       "get_init_mods"           : self._handle_get_init_mods,
                                       "get_start_scripts"       : self._handle_get_start_scripts,
                                       "get_stop_scripts"        : self._handle_get_stop_scripts,
                                       "hello"                   : self._handle_hello,
                                       "get_root_passwd"         : self._handle_get_root_passwd,
                                       "locate_module"           : self._handle_locate_module,
                                       "get_add_group"           : self._handle_get_add_group,
                                       "get_add_user"            : self._handle_get_add_user,
                                       "get_del_group"           : self._handle_get_del_group,
                                       "get_del_user"            : self._handle_get_del_user,
                                       "get_additional_packages" : self._handle_get_additional_packages,
                                       "get_install_ep"          : self._handle_get_install_ep,
                                       "get_upgrade_ep"          : self._handle_get_upgrade_ep,
                                       "modify_bootloader"       : self._handle_modify_bootloader}
        # list of simple commands
        self.__simple_commands = self.__command_handler_dict.keys()
        # wait_for_build dict
        self.__wait_for_build_dict = {}
        # list of ready configs
        self.__config_ready_list = []
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
        self.__queue_dict["command"].put(("set_simple_commands", self.__simple_commands))
    def _direct_command(self, (con_key, dev_name, src_data)):
        command = src_data.split()[0]
        # command from other thread
        dc = self.__db_con.get_connection(SQL_ACCESS)
        c_req = config_request(self, self.__glob_config, self.__loc_config, command, src_data, dev_name=dev_name, thread_key=con_key)
        c_req.create_base_structs(dc)
        if c_req.pending:
            self.__command_handler_dict[c_req.command](c_req, dc)
        c_req.log_ret_str()
        if c_req.send_to_thread:
            self.__queue_dict["command"].put(("direct_command_done", ((c_req.thread_key, dev_name, c_req.get_ret_str()))))
        del c_req
        dc.release()
    def _simple_command(self, (con_obj, src_part, command, src_data)):
        # command from network
        dc = self.__db_con.get_connection(SQL_ACCESS)
        c_req = config_request(self, self.__glob_config, self.__loc_config, command, src_data, src_part=src_part)
        c_req.create_base_structs(dc)
        if c_req.pending:
            self.__command_handler_dict[c_req.command](c_req, dc)
        con_obj.send_return(c_req.get_ret_str())
        c_req.log_ret_str()
        del c_req
        dc.release()
    def _get_valid_server_struct(self, c_req, dc, type_list):
        # list of bootserver-local servers
        bsl_servers = ["kernel_server", "mother_server", "image_server"]
        # list of config_types which has to be mapped to the mother-server
        map_to_mother = ["kernel_server", "image_server"]
        # iterates over type_list to find a valid server_struct
        for type_name in type_list:
            conf_list = config_tools.device_with_config(type_name, dc)
            if conf_list:
                server_names = conf_list.keys()
                if type_name in bsl_servers:
                    valid_server_struct = None
                    # get only the server wich is the bootserver
                    for server_name in server_names:
                        if conf_list[server_name].device_idx == c_req["bootserver"]:
                            valid_server_name, valid_server_struct = (server_name, conf_list[server_name])
                            break
                else:
                    # take the first server
                    valid_server_name = conf_list.keys()[0]
                    valid_server_struct = conf_list[valid_server_name]
            else:
                valid_server_name, valid_server_struct = ("", None)
            if valid_server_struct:
                break
        if valid_server_struct:
            if type_name in map_to_mother:
                valid_server_struct = config_tools.server_check(dc=dc,
                                                                server_type="mother_server",
                                                                short_host_name=valid_server_name,
                                                                fetch_network_info=True)
        if valid_server_struct:
            c_req.log("found valid_server_struct %s (device %s)" % (valid_server_struct.server_info_str,
                                                                    valid_server_struct.short_host_name))
            # check connectivity to device
            if c_req.find_route_to_server(valid_server_struct, dc):
                pass
            else:
                valid_server_struct = None
        else:
            c_req.set_ret_str("error no valid server found")
            c_req.log("found no valid server_struct (search list: %s)" % (", ".join(type_list)),
                      logging_tools.LOG_LEVEL_ERROR)
        return valid_server_struct
    def _handle_get_image(self, c_req, dc):
        c_req._fetch_image_info(dc)
        image_info = c_req["image_info"]
        if image_info:
            if image_info["build_lock"]:
                c_req.set_ret_str("error image '%s' is locked" % (image_info["name"]))
            else:
                vs_struct = self._get_valid_server_struct(c_req, dc, ["tftpboot_export", "image_server"])
                if vs_struct:
                    # routing ok, get export directory
                    if vs_struct.config_name.startswith("mother"):
                        # is mother_server
                        dir_key = "TFTP_DIR"
                    else:
                        # is tftpboot_export
                        dir_key = "EXPORT"
                    vs_struct.fetch_config_vars(dc)
                    if vs_struct.has_key(dir_key):
                        c_req.set_ret_str("ok %s %s/%s/%s %s %s %s" % (c_req.server_ip,
                                                                       vs_struct[dir_key],
                                                                       "images",
                                                                       image_info["name"],
                                                                       image_info["version"],
                                                                       image_info["release"],
                                                                       image_info["builds"]))
                        dc.execute("UPDATE device SET act_image=%s, actimage=%s, imageversion=%s WHERE device_idx=%s", (image_info["image_idx"],
                                                                                                                        image_info["name"],
                                                                                                                        "%s.%s" % (image_info["version"], image_info["release"]),
                                                                                                                        c_req["device_idx"]))
                    else:
                        c_req.set_ret_str("error key %s not found" % (dir_key))
        else:
            # no image defined in db
            c_req.set_ret_str("error no image set")
    def _handle_set_kernel(self, c_req, dc):
        # maybe we can do something better here
        c_req.set_ret_str("ok got it")
    def _handle_get_kernel(self, c_req, dc):
        # get kernel info (kernel_str)
        kernel_str = c_req.get_kernel_info_str(dc)
        vs_struct = self._get_valid_server_struct(c_req, dc, ["tftpboot_export", "kernel_server"])
        if vs_struct:
            # routing ok, get export directory
            if vs_struct.config_name.startswith("mother"):
                # is mother_server
                dir_key = "TFTP_DIR"
            else:
                # is tftpboot_export
                dir_key = "EXPORT"
            vs_struct.fetch_config_vars(dc)
            if vs_struct.has_key(dir_key):
                kernel_source_path = "%s/kernels/" % (vs_struct[dir_key])
                # build return str
                if c_req.command == "get_kernel":
                    # get kernel with full path
                    c_req.set_ret_str("ok NEW %s %s/%s" % (c_req.server_ip,
                                                           kernel_source_path,
                                                           kernel_str))
                else:
                    c_req.set_ret_str("ok NEW %s %s" % (c_req.server_ip,
                                                        kernel_str))
            else:
                c_req.set_ret_str("error key %s not found" % (dir_key))
    def _handle_get_syslog_server(self, c_req, dc):
        vs_struct = self._get_valid_server_struct(c_req, dc, ["syslog_server"])
        if vs_struct:
            c_req.set_ret_str("ok %s" % (c_req.server_ip))
    def _handle_get_package_server(self, c_req, dc):
        vs_struct = self._get_valid_server_struct(c_req, dc, ["package_server"])
        if vs_struct:
            c_req.set_ret_str("ok %s" % (c_req.server_ip))
    def _handle_hello(self, c_req, dc):
        c_req.set_ret_str(c_req.create_config_dir())
    def _handle_get_root_passwd(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (c_req["root_passwd"]))
    def _handle_get_start_scripts(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "START_SCRIPTS"))))
    def _handle_get_stop_scripts(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "STOP_SCRIPTS"))))
    def _handle_get_add_user(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "ADD_USER"))))
    def _handle_get_add_group(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "ADD_GROUP"))))
    def _handle_get_del_user(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "DEL_USER"))))
    def _handle_get_del_group(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "DEL_GROUP"))))
    def _handle_get_additional_packages(self, c_req, dc):
        c_req.set_ret_str("ok %s" % (" ".join(c_req.get_config_str_vars(dc, "ADDITIONAL_PACKAGES"))))
    def _handle_modify_bootloader(self, c_req, dc):
        dc.execute("SELECT pt.modify_bootloader FROM partition_table pt, device d WHERE d.device_idx=%s AND d.partition_table=pt.partition_table_idx", (c_req["device_idx"]))
        modify_bl = dc.fetchone()["modify_bootloader"]
        c_req.set_ret_str("ok %s" % ("yes" if modify_bl else "no"))
    def _handle_get_init_mods(self, c_req, dc):
        db_mod_list = c_req.get_config_str_vars(dc, "INIT_MODS")
        # add modules which depends to the used partition type
        dc.execute("SELECT DISTINCT ps.name FROM partition_table pt INNER JOIN device d LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx LEFT JOIN partition_fs ps ON ps.partition_fs_idx=p.partition_fs WHERE d.device_idx=%s AND d.partition_table=pt.partition_table_idx AND ps.identifier='f'", c_req["device_idx"])
        db_mod_list.extend([db_rec["name"] for db_rec in dc.fetchall() if db_rec["name"] and db_rec["name"] not in db_mod_list])
        c_req.set_ret_str("ok %s" % (" ".join(db_mod_list)))
    def _handle_locate_module(self, c_req, dc):
        kernel_str = c_req.get_kernel_info_str(dc).split()[0]
        # build module dict
        mod_dict = dict([(key, None) for key in [key.endswith(".ko") and key[:-3] or (key.endswith(".o") and key[:-2] or key) for key in c_req.data_parts]])
        kernel_dir = "%s/kernels/%s" % (self.__glob_config["TFTP_DIR"],
                                        kernel_str)
        # walk the kernel dir
        mod_list = ["%s.o" % (key) for key in mod_dict.keys()] + ["%s.ko" % (key) for key in mod_dict.keys()]
        for dir_name, dir_names, file_names in os.walk(kernel_dir):
            for file_name in file_names:
                if file_name in mod_list:
                    # module is needed
                    mod_name = file_name.endswith(".ko") and file_name[:-3] or (file_name.endswith(".o") and file_name[:-2] or file_name)
                    mod_dict[mod_name] = os.path.normpath("%s/%s" % (dir_name, file_name))
        required_modules, auto_modules = ([mod_loc for mod_loc in mod_dict.values() if mod_loc],
                                          [])
        # handle dependencies
        dep_file = "%s/lib/modules/" % (kernel_dir)
        if os.path.isdir(dep_file):
            dep_file = "%s/%s/modules.dep" % (dep_file, os.listdir(dep_file)[0])
        if os.path.isfile(dep_file):
            # read dependency file
            dep_dict = {}
            actual_line = ""
            for dep_line in [line.replace("\t", " ").strip() for line in file(dep_file, "r").read().split("\n") if line.strip()]:
                if dep_line.endswith("\\"):
                    actual_line = "%s %s" % (actual_line, dep_line[:-1])
                else:
                    actual_line = "%s %s" % (actual_line, dep_line)
                    key, value = actual_line.strip().split(":", 1)
                    dep_dict[os.path.normpath("%s/%s" % (kernel_dir, key))] = [os.path.normpath("%s/%s" % (kernel_dir, mod_name)) for mod_name in value.split()]
                    actual_line = ""
            #pprint.pprint(dep_dict)
            # iterate over auto_modules until all modules are resolved
            while True:
                some_added = False
                for mod_name in required_modules + auto_modules:
                    for new_mod in dep_dict.get(mod_name, []):
                        if new_mod not in auto_modules and new_mod not in required_modules:
                            some_added = True
                            auto_modules.append(new_mod)
                if not some_added:
                    break
        for key, value in mod_dict.iteritems():
            c_req.log("kmod mapping: %20s -> %s" % (key, value))
        for value in auto_modules:
            c_req.log("dependencies: %20s    %s" % ("", value))
        c_req.set_ret_str("ok %s" % (" ".join([mod_name[len(self.__glob_config["TFTP_DIR"]) : ] for mod_name in required_modules + auto_modules])))
    def _handle_get_target_sn(self, c_req, dc):
        # get prod_net info
        prod_net = "none"
        if c_req["prod_link"]:
            dc.execute("SELECT nw.identifier, nw.name FROM network nw WHERE nw.network_idx=%s", (c_req["prod_link"]))
            if dc.rowcount:
                prod_net = dc.fetchone()["identifier"]
            else:
                c_req.log("Error fetching prod_net info (index %d)" % (c_req["prod_link"]),
                          logging_tools.LOG_LEVEL_ERROR)
        else:
            c_req.log("not prod_link set", logging_tools.LOG_LEVEL_ERROR)
        vs_struct = self._get_valid_server_struct(c_req, dc, ["tftpboot_export", "mother_server"])
        if vs_struct:
            # routing ok, get export directory
            if vs_struct.config_name.startswith("mother"):
                # is mother_server
                dir_key = "TFTP_DIR"
            else:
                # is tftpboot_export
                dir_key = "EXPORT"
            vs_struct.fetch_config_vars(dc)
            if vs_struct.has_key(dir_key):
                kernel_source_path = "%s/kernels/" % (vs_struct[dir_key])
                c_req.set_ret_str("ok %s %s %d %d %s %s %s" % (c_req["status"],
                                                               prod_net,
                                                               c_req["rsync"],
                                                               c_req["rsync_compressed"],
                                                               c_req["name"],
                                                               c_req.server_ip,
                                                               "%s/%s" % (vs_struct[dir_key], "config")))
            else:
                c_req.set_ret_str("error key %s not found" % (dir_key))
    def _handle_get_partition(self, c_req, dc):
        c_req._handle_get_partition(dc)
    def _handle_create_config(self, c_req, dc):
        if c_req["name"] in self.__wait_for_build_dict.keys():
            c_req.set_ret_str("ok request already pending")
        else:
            if c_req["name"] in self.__config_ready_list:
                # is in config_ready list, clear to force rebuild
                c_req.log("removing from config_ready_list", logging_tools.LOG_LEVEL_WARN)
                self._remove_from_build_dict(c_req["name"])
                self.__config_ready_list.remove(c_req["name"])
            c_req.set_ret_str("ok started config rebuild")
            self._add_to_build_dict(c_req)
    def _handle_ack_config(self, c_req, dc):
        if c_req["name"] in self.__config_ready_list:
            c_req.set_ret_str(self.__wait_for_build_dict[c_req["name"]]["result"])
            self._remove_from_build_dict(c_req["name"])
            self.__config_ready_list.remove(c_req["name"])
        else:
            self._add_to_build_dict(c_req)
    def _add_to_build_dict(self, c_req):
        if c_req["name"] in self.__wait_for_build_dict.keys():
            c_req.set_ret_str("wait config not ready")
        else:
            c_req.set_ret_str("warning not in wait_dict, adding ...")
            c_req.log("adding to wait_for_build_dict")
            self.__wait_for_build_dict[c_req["name"]] = {"started"      : time.time(),
                                                         "waiting_keys" : [],
                                                         "result"       : "error not set"}
            self.__queue_dict["build"].put(("build_config", c_req["name"]))
        if c_req.thread_key:
            self.__wait_for_build_dict[c_req["name"]]["waiting_keys"].append(c_req.thread_key)
            # wait for answer
            c_req.send_to_thread = False
    def _remove_from_build_dict(self, dev_name):
        self.log("removing device %s from wait_for_build_dict" % (dev_name))
        del self.__wait_for_build_dict[dev_name]
    def _build_done(self, (dev_name, result)):
        if dev_name in self.__wait_for_build_dict.keys():
            wfb_struct = self.__wait_for_build_dict[dev_name]
            wfb_struct["result"] = result
            if dev_name not in self.__config_ready_list:
                self.__config_ready_list.append(dev_name)
            # send to waiting threads
            if wfb_struct["waiting_keys"]:
                self.log("sending result %s to other thread: %s" % (logging_tools.get_plural("time", len(wfb_struct["waiting_keys"])),
                                                                    ", ".join(["key %d" % (value) for value in sorted(wfb_struct["waiting_keys"])])))
                for wait_key in wfb_struct["waiting_keys"]:
                    self.__queue_dict["command"].put(("direct_command_done", (wait_key, dev_name, wfb_struct["result"])))
                # OK? FIXME
                self._remove_from_build_dict(dev_name)
                self.__config_ready_list.remove(dev_name)
            self.log("config_ready_list contains now %s: %s" % (logging_tools.get_plural("entry", len(self.__config_ready_list)),
                                                                ", ".join(sorted(self.__config_ready_list))))
        else:
            self.log("device %s not in wait_for_build_dict" % (dev_name),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_get_install_ep(self, c_req, dc):
        self._handle_get_iu_ep(c_req, dc, "valid_for_install")
    def _handle_get_upgrade_ep(self, c_req, dc):
        self._handle_get_iu_ep(c_req, dc, "valid_for_upgrade")
    def _handle_get_iu_ep(self, c_req, dc, filter):
        dc.execute("SELECT d.newimage, d.new_image, i.*, x.exclude_path FROM device d INNER JOIN image i LEFT JOIN image_excl x ON x.image=i.image_idx WHERE x.%s AND d.device_idx=%d AND (i.name=d.newimage OR i.image_idx=d.new_image)" % (filter,
                                                                                                                                                                                                                                             c_req["device_idx"]))
        if dc.rowcount:
            c_req.set_ret_str("ok %s" % (" ".join([db_rec["exclude_path"].replace("*", "*") for db_rec in dc.fetchall()])))
        else:
            c_req.set_ret_str("ok")
    def _handle_dummy(self, c_req, dc):
        c_req.log("dummy_handler called for command %s (src_data is '%s')" % (c_req.command,
                                                                              c_req.full_src_data),
                  logging_tools.LOG_LEVEL_WARN)
        c_req.set_ret_str("warn dummy_handler called for %s" % (c_req.command))

class command_thread(threading_tools.thread_obj):
    """ handles command from the network and distributes them to the other threads """
    def __init__(self, log_queue, db_con, glob_config, loc_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        self.__loc_config = loc_config
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("srv_command"    , self._srv_command)
        self.register_func("set_net_server" , self._set_net_server)
        self.register_func("send_error"     , self._send_error)
        self.register_func("srv_send_ok"    , self._srv_send_ok)
        self.register_func("srv_send_error" , self._srv_send_error)
        self.register_func("send_ok"        , self._send_ok)
        self.register_func("new_command"    , self._new_command)
        self.register_func("command_error"  , self._command_error)
        self.register_func("node_connection", self._node_connection)
        self.register_func("node_error"     , self._node_error)
        self.register_func("set_queue_dict" , self._set_queue_dict)
        self.register_func("set_simple_commands", self._set_simple_commands)
        self.register_func("direct_command_done", self._direct_command_done)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, node_name=""):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__dev_conf_send_dict = {}
        self.__com_dict = {"new_config"       : None,
                           "new_rsync_config" : None,
                           "create_config"    : self._create_config}
        self.__ret_dict = {}
        self.__local_key = 0
        self.__last_update = time.time()
        # clear queue dict
        self.__queue_dict = {}
        # known simple commands
        self.__simple_commands = []
        # outstanding configs to create
        self.__waiting_configs, self.__wc_key = ({}, 0)
    def _set_simple_commands(self, com_list):
        self.log("got %s from config_thread: %s" % (logging_tools.get_plural("simple command", len(com_list)),
                                                    ", ".join(sorted(com_list))))
        self.__simple_commands = com_list
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _set_net_server(self, ns):
        self.log("Netserver set")
        self.__net_server = ns
    def _srv_command(self, srv_com):
        # not needed right now (copied from package-server), might be usefull in the future ... FIXME
        self.__local_key += 1
        self.__ret_dict[self.__local_key] = {"key"        : self.__local_key,
                                             "command"    : srv_com,
                                             "open"       : len(srv_com.get_nodes()),
                                             "start_time" : time.time(),
                                             "results"    : dict([(k, "") for k in srv_com.get_nodes()])}
        self.log("got srv_command (command %s) for %s: %s" % (srv_com.get_command(),
                                                              logging_tools.get_plural("node", len(srv_com.get_nodes())),
                                                              logging_tools.compress_list(srv_com.get_nodes())))
        for mach in srv_com.get_nodes():
            self.__dev_conf_send_dict.setdefault(mach, {"num" : 0, "last_send" : time.time()})
            self.__dev_conf_send_dict[mach]["num"] += 1
            self.__dev_conf_send_dict[mach]["last_send"] = time.time()
            self.__net_server.add_object(net_tools.tcp_con_object(self._new_node_connection,
                                                                  connect_state_call=self._connect_state_call,
                                                                  connect_timeout_call=self._connect_timeout,
                                                                  timeout=8,
                                                                  bind_retries=1,
                                                                  rebind_wait_time=1,
                                                                  target_port=self.__glob_config["CLIENT_PORT"],
                                                                  target_host=mach,
                                                                  add_data=(self.__ret_dict[self.__local_key],
                                                                            mach)))
        if not self.__ret_dict[self.__local_key]["open"]:
            self._dict_changed(self.__ret_dict[self.__local_key])
    def _send_error(self, ((act_dict, mach), why)):
        self.log("Error for device %s: %s" % (mach, why), logging_tools.LOG_LEVEL_ERROR)
        act_dict["results"][mach] = "error %s" % (why)
        act_dict["open"] -= 1
        self._dict_changed(act_dict)
    def _send_ok(self, ((act_dict, mach), result)):
        act_dict["results"][mach] = result
        act_dict["open"] -= 1
        self._dict_changed(act_dict)
    def _dict_changed(self, act_dict):
        if not act_dict["open"]:
            act_srv_command = act_dict["command"]
            ret_str = "ok got command #%s" % ("#".join([act_dict["results"][x] for x in act_srv_command.get_nodes()]))
            con_obj = act_srv_command.get_key()
            if con_obj:
                self.log("Returning str (took %s): %s" % (logging_tools.get_diff_time_str(time.time() - act_dict["start_time"]), ret_str))
                res_com = server_command.server_reply()
                res_com.set_ok_result("got command")
                res_com.set_node_results(act_dict["results"])
                con_obj.send_return(res_com)
            else:
                if act_srv_command.get_queue():
                    act_srv_command.get_queue().put(("status_result", act_dict["results"]))
                self.log("No need to return str (took %s): %s" % (logging_tools.get_diff_time_str(time.time() - act_dict["start_time"]), ret_str))
            del self.__ret_dict[act_dict["key"]]
            del act_dict
    def _connect_timeout(self, sock):
        self.get_thread_queue().put(("send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("send_error", (args["socket"].get_add_data(), "connection error")))
    def _new_node_connection(self, sock):
        return connection_to_node(sock.get_add_data(), self.get_thread_queue())
    def _command_error(self, (con_obj, (other_ip, other_addr), what)):
        self.log("Error for server_command: %s (%s, port %d)" % (what, other_ip, other_addr), logging_tools.LOG_LEVEL_ERROR)
    def _create_config(self, con_obj, srv_com):
        self.__wc_key += 1
        self.__waiting_configs[self.__wc_key] = {"con_obj"        : con_obj,
                                                 "srv_com"        : srv_com,
                                                 "started"        : time.time(),
                                                 "devs_waiting"   : len(srv_com.get_nodes()),
                                                 "device_results" : dict([(node_name, "error not set") for node_name in srv_com.get_nodes()])}
        self.log("init wait_struct for create_config (key %d, %s: %s)" % (self.__wc_key,
                                                                          logging_tools.get_plural("node", len(srv_com.get_nodes())),
                                                                          ", ".join(sorted(srv_com.get_nodes()))))
        for node in srv_com.get_nodes():
            self.__queue_dict["config"].put(("direct_command", (self.__wc_key, node, "create_config")))
    def _direct_command_done(self, (con_key, dev_name, dev_result)):
        if self.__waiting_configs.has_key(con_key):
            w_struct = self.__waiting_configs[con_key]
            w_struct["devs_waiting"] -= 1
            w_struct["device_results"][dev_name] = dev_result
            if not w_struct["devs_waiting"]:
                # finished
                end_time = time.time()
                self.log("configs done for %s (%s) in %s" % (logging_tools.get_plural("node", len(w_struct["device_results"].keys())),
                                                             ", ".join(sorted(w_struct["device_results"].keys())),
                                                             logging_tools.get_diff_time_str(end_time - w_struct["started"])))
                com_reply = server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK, result="configs built")
                com_reply.set_node_results(w_struct["device_results"])
                w_struct["con_obj"].send_return(com_reply)
                del self.__waiting_configs[con_key]
        else:
            self.log("no waiting_config with key %d found" % (con_key), logging_tools.LOG_LEVEL_ERROR)
    def _new_command(self, (con_obj, (other_ip, other_addr), what)):
        try:
            srv_com = server_command.server_command(what)
        except:
            srv_com = None
        else:
            if srv_com.get_command() == what:
                srv_com = None
        if srv_com:
            srv_com.set_key(con_obj)
            if srv_com.get_command() == "status":
                con_obj.send_return(self._status_com())
            elif srv_com.get_command() == "new_rsync_server_config":
                # unused, FIXME
                res_com = server_command.server_reply()
                res_com.set_state_and_result(server_command.SRV_REPLY_STATE_OK, "ok got it")
                con_obj.send_return(res_com)
                self.__net_server.add_object(net_tools.tcp_con_object(self._new_nagios_server_connection,
                                                                      connect_state_call=self._ncs_connect_state_call,
                                                                      connect_timeout_call=self._ncs_connect_timeout,
                                                                      timeout=10,
                                                                      bind_retries=1,
                                                                      rebind_wait_time=1,
                                                                      target_port=8004,
                                                                      target_host="localhost",
                                                                      add_data=(server_command.server_command(command="write_rsyncd_config"), "localhost")))
            elif srv_com.get_command() in self.__com_dict.keys():
                self.log("got command %s from %s (port %d)" % (srv_com.get_command(), other_ip, other_addr))
                if self.__com_dict[srv_com.get_command()]:
                    # has handle
                    self.__com_dict[srv_com.get_command()](con_obj, srv_com)
                else:
                    # no handle
                    self._srv_command(srv_com)
            else:
                self.log("got unknown command %s from %s (port %d)" % (srv_com.get_command(), other_ip, other_addr), logging_tools.LOG_LEVEL_ERROR)
                res_com = server_command.server_reply()
                res_com.set_error_result("unknown command %s" % (srv_com.get_command()))
                con_obj.send_return(res_com)
        else:
            con_obj.send_return("error unknown command %s (or missing server_command)" % (what))
    def _status_com(self):
        num_ok, num_threads = (self.get_thread_pool().num_threads_running(False),
                               self.get_thread_pool().num_threads(False))
        if num_ok == num_threads:
            ret_com = server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                  result="OK all %d threads running (version %s)" % (num_ok, self.__loc_config["VERSION_STRING"]))
        else:
            ret_com = server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR,
                                                  result="ERROR only %d of %d threads running (version %s)" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"]))
        return ret_com
    # connection to local cluster-server
    def _new_nagios_server_connection(self, sock):
        return connection_to_nagios_server(sock.get_add_data(), self.get_thread_queue())
    def _ncs_connect_timeout(self, sock):
        self.get_thread_queue().put(("srv_send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _ncs_connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("srv_send_error", (args["socket"].get_add_data(), "connection error")))
    def _srv_send_error(self, ((srv_com, srv_name), why)):
        self.log("Error sending server_command %s to server %s: %s" % (srv_com.get_command(), srv_name, why), logging_tools.LOG_LEVEL_ERROR)
    def _srv_send_ok(self, ((srv_com, srv_name), result)):
        self.log("Sent server_command %s to server %s" % (srv_com.get_command(), srv_name))
    def _node_connection(self, (con_obj, src_part, src_data)):
        command = src_data.split()[0]
        if command in self.__simple_commands:
            # simple command, send to config_queue
            self.__queue_dict["config"].put(("simple_command", (con_obj, src_part, command, src_data)))
        else:
            self.log("unknown command %s from %s: '%s'" % (command,
                                                           str(src_part),
                                                           src_data),
                     logging_tools.LOG_LEVEL_WARN)
            con_obj.send_return("error unknown command '%s'" % (command))
    def _node_error(self, error_str):
        self.log("node_error: %s" % (error_str), logging_tools.LOG_LEVEL_ERROR)
        
class error(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class config_error(error):
    def __init__(self, what = "UNKNOWN"):
        error.__init__(self, what)
    
class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config):
        self.__glob_config = glob_config
        self.__handles, self.__log_buffer, self.__global_log = ({}, [], None)
        self.__sep_str = "-" * 50
        threading_tools.thread_obj.__init__(self, "log", queue_size=100, priority=10)
        self.register_func("log", self._log)
        self.register_func("write_file", self._write_file)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__root = self.__glob_config["LOG_DIR"]
        if not os.path.isdir(self.__root):
            try:
                os.makedirs(self.__root)
            except OSError:
                # we have to write to syslog
                self.log("Unable to create '%s' directory" % (self.__root), logging_tools.LOG_LEVEL_ERROR)
                self.__root = "/tmp"
            else:
                pass
        glog_name = "%s/log" % (self.__root)
        self.__global_log = logging_tools.logfile(glog_name)
        self.__global_log.write(self.__sep_str, header = 0)
        self.__global_log.write("(%s) Opening log" % (self.name))
    def _get_handle(self, dev_name, file_name="log", register=True):
        full_name = "%s/%s" % (dev_name, file_name)
        if self.__handles.has_key(full_name):
            handle = self.__handles[full_name]
        else:
            machdir = "%s/%s" % (self.__root, dev_name)
            if not os.path.isdir(machdir):
                self.__global_log.write("Creating dir %s for %s" % (machdir, dev_name))
                os.makedirs(machdir)
            if register:
                handle = logging_tools.logfile("%s/%s" % (machdir, file_name))
                self.__handles[full_name] = handle
                handle.write(self.__sep_str)
                handle.write("Opening log")
            else:
                handle = file("%s/%s" % (machdir, file_name), "w")
        return handle
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__global_log:
            if self.__log_buffer:
                for b_what, b_line in self.__log_buffer:
                    self._log((b_what, b_line))
                self.__log_buffer = []
            self._log((what, lev))
        else:
            self.__log_buffer.append((what, lev))
    def _log(self, l_stuff):
        if len(l_stuff) == 2:
            what, lev = l_stuff
            thread_name, node_name = (self.name, "")
        elif len(l_stuff) == 3:
            what, lev, thread_name = l_stuff
            node_name = ""
        else:
            what, lev, thread_name, node_name = l_stuff
        if node_name:
            handle = self._get_handle(node_name)
        else:
            handle = self.__global_log
        thread_pfix = "(%s)" % (thread_name.endswith("_thread") and thread_name[:-7] or thread_name)
        handle.write("%-6s%s %s" % (logging_tools.get_log_level_str(lev), thread_pfix, what))
    def _write_file(self, (dev_name, file_name, what)):
        self._get_handle(dev_name, file_name, False).write(what)
    def loop_end(self):
        for mach in self.__handles.keys():
            self.__handles[mach].write("Closing log")
            self.__handles[mach].close()
        self.__global_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__handles.keys()))))
        self.__global_log.write("Closing log")
        self.__global_log.close()
        
class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, glob_config, loc_config, log_lines):
        self.__log_buffer = []
        self.__log_queue = None
        self.__glob_config = glob_config
        self.__loc_config = loc_config
        self.__db_con = db_con
        threading_tools.thread_pool.__init__(self, "main_thread", blocking_loop=False)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("new_pid", self._new_pid)
        # msi_block
        self.__msi_block = self._init_msi_block(self.__loc_config["DAEMON"])
        # log thread
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config), start_thread=True).get_thread_queue()
        for what, lev in log_lines:
            self.log(what, lev)
        self._log_config()
        self._re_insert_config()
        self.__ns = net_tools.network_server(timeout=1, log_hook=self.log, poll_verbose=False)
        self.__bind_states = {}
        self.__ns.add_object(net_tools.tcp_bind(self._new_command_con, port=self.__glob_config["COMMAND_PORT"], bind_retries=self.__loc_config["N_RETRY"], bind_state_call=self._bind_state_call, timeout=60))
        self.__ns.add_object(net_tools.tcp_bind(self._new_node_con, port=self.__glob_config["NODE_PORT"], bind_retries=self.__loc_config["N_RETRY"], bind_state_call=self._bind_state_call, timeout=60))
        self.__command_queue = self.add_thread(command_thread(self.__log_queue, self.__db_con, self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        self.__config_queue = self.add_thread(config_thread(self.__log_queue, self.__db_con, self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        self.__build_queue = self.add_thread(build_thread(self.__log_queue, self.__db_con, self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        self.__queue_dict = {"command" : self.__command_queue,
                             "config"  : self.__config_queue,
                             "build"   : self.__build_queue}
        self.__command_queue.put(("set_queue_dict", self.__queue_dict))
        self.__config_queue.put(("set_queue_dict", self.__queue_dict))
        self.__build_queue.put(("set_queue_dict", self.__queue_dict))
        self.__command_queue.put(("set_net_server", self.__ns))
        self.__build_queue.put(("set_net_server", self.__ns))
        self._log_nagios_status()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_buffer:
                self.__log_queue.put([("log", x) for x in self.__log_buffer])
                self.__log_buffer = []
            self.__log_queue.put(("log", (what, lev, threading.currentThread().getName())))
        else:
            self.__log_buffer.append((what, lev, threading.currentThread().getName()))
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        configfile.write_config(dc, "server", self.__glob_config)
        dc.release()
    def _new_pid(self, new_pid):
        self.log("received new_pid message")
        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _init_msi_block(self, daemon):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("cluster-config-server")
            msi_block.add_actual_pid()
            msi_block.set_start_command("/etc/init.d/cluster-config-server start")
            msi_block.set_stop_command("/etc/init.d/cluster-config-server force-stop")
            msi_block.set_kill_pids()
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            self.__ns.set_timeout(0.1)
    def _log_nagios_status(self):
        if self.__loc_config["NAGIOS_IP"]:
            # queue for comsend_ thread
            self.log("Nagios_master-host found at ip %s, enabling sending of hc_done requests" % (self.__loc_config["NAGIOS_IP"]))
        else:
            self.log("No Nagios_master-host found, disabling sending of hc_done requests", logging_tools.LOG_LEVEL_WARN)
    def loop_function(self):
        #if not self["exit_requested"]:
            #self.__command_queue.put("update")
            #if self.__watcher_queue:
            #    self.__watcher_queue.put("update")
        self.__ns.step()
        if self.__loc_config["VERBOSE"]:
            self.log("tqi: %s" % (", ".join(["%s: %d of %d used" % (name, act_used, max_size) for name, (max_size, act_used) in self.get_thread_queue_info().iteritems()])))
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _bind_state_call(self, **args):
        if args["state"] == "error":
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
        elif args["state"] == "ok":
            self.__bind_states[args["port"]] = "ok"
            if len(self.__bind_states.keys()) == 2:
                self.__ns.set_timeout(self.__loc_config["DAEMON"] and 60 or 2)
    def _new_node_con(self, sock, src):
        return connection_from_node(src, self.__command_queue)
    def _new_command_con(self, sock, src):
        return connection_for_command(src, self.__command_queue)

def main():
    #global short_host_name, server_idx, log_source_idx, g_config, log_sources, log_status
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dVvr:hCu:g:fk", ["help"])
    except getopt.GetoptError, bla:
        print "Commandline error : %s" % (process_tools.get_except_info())
        sys.exit(2)
    try:
        from cluster_config_server_version import VERSION_STRING
    except ImportError:
        VERSION_STRING = "unknown.unknown"
    server_full_name = socket.getfqdn(socket.gethostname())
    server_short_name = server_full_name.split(".")[0]
    loc_config = configfile.configuration("local_config", {"PID_NAME"          : configfile.str_c_var("cluster-config-server/cluster-config-server"),
                                                           "SERVER_IDX"        : configfile.int_c_var(0),
                                                           "VERBOSE"           : configfile.bool_c_var(False),
                                                           "N_RETRY"           : configfile.int_c_var(5),
                                                           "DAEMON"            : configfile.bool_c_var(True),
                                                           "VERSION_STRING"    : configfile.str_c_var(VERSION_STRING),
                                                           "SERVER_SHORT_NAME" : configfile.str_c_var(server_short_name),
                                                           "SERVER_FULL_NAME"  : configfile.str_c_var(server_full_name),
                                                           "LOG_STATUS"        : configfile.dict_c_var({}),
                                                           "LOG_SOURCE_IDX"    : configfile.int_c_var(0),
                                                           "KILL_RUNNING"      : configfile.bool_c_var(True),
                                                           "FIXIT"             : configfile.bool_c_var(False),
                                                           "USER_NAME"         : configfile.str_c_var("root"),
                                                           "GROUP_NAME"        : configfile.str_c_var("root"),
                                                           "NAGIOS_IP"         : configfile.str_c_var("")})
    check = False
    pname = os.path.basename(sys.argv[0])
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print "Usage: %s [OPTIONS]" % (pname)
            print "where OPTIONS are:"
            print " -h,--help        this help"
            print " -C               check if this is a cluster-config-server"
            print " -d               run in debug mode (no forking)"
            print " -v               be verbose"
            print " -V               show version"
            print " -f               create and fix needed files and directories"
            print " -u user          run as user USER"
            print " -g group         run as group GROUP"
            print " -k               do not kill running %s" % (pname)
            sys.exit(0)
        if opt == "-k":
            loc_config["KILL_RUNNING"] = False
        if opt == "-C":
            check = True
        if opt == "-d":
            loc_config["DAEMON"] = False
        if opt == "-V":
            print "Version %s" % (loc_config["VERSION_STRING"])
            sys.exit(0)
        if opt == "-v":
            loc_config["VERBOSE"] = True
        if opt == "-r":
            try:
                loc_config["N_RETRY"] = int(arg)
            except:
                print "Error parsing n_retry"
                sys.exit(2)
        if opt == "-f":
            loc_config["FIXIT"] = True
        if opt == "-u":
            loc_config["USER_NAME"] = arg
        if opt == "-g":
            loc_config["GROUP_NAME"] = arg
    ret_code = 1
    db_con = mysql_tools.dbcon_container(with_logging=not loc_config["DAEMON"])
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    glob_config = configfile.read_global_config(dc, "config_server", {"LOG_DIR"                   : configfile.str_c_var("/var/log/cluster/cluster-config-server"),
                                                                      # TFTP_DIR and CONFIG/IMAGE/KERNEL_DIR should come from mother, FIXME
                                                                      "TFTP_DIR"                  : configfile.str_c_var("/tftpboot"),
                                                                      "COMMAND_PORT"              : configfile.int_c_var(SERVER_COM_PORT),
                                                                      "NODE_PORT"                 : configfile.int_c_var(SERVER_NODE_PORT),
                                                                      "NAGIOS_PORT"               : configfile.int_c_var(NCS_PORT),
                                                                      "PREFER_KERNEL_NAME"        : configfile.int_c_var(0),
                                                                      "LOCALHOST_IS_EXCLUSIVE"    : configfile.int_c_var(1),
                                                                      "HOST_CACHE_TIME"           : configfile.int_c_var(10 * 60),
                                                                      "WRITE_REDHAT_HWADDR_ENTRY" : configfile.int_c_var(1),
                                                                      "ADD_NETDEVICE_LINKS"       : configfile.bool_c_var(False),
                                                                      "CORRECT_WRONG_LO_SETUP"    : configfile.int_c_var(1)})
    glob_config.add_config_dict({"CONFIG_DIR" : configfile.str_c_var("%s/%s" % (glob_config["TFTP_DIR"], "config")),
                                 "IMAGE_DIR"  : configfile.str_c_var("%s/%s" % (glob_config["TFTP_DIR"], "images")),
                                 "KERNEL_DIR" : configfile.str_c_var("%s/%s" % (glob_config["TFTP_DIR"], "kernels"))})
    sql_info = config_tools.server_check(dc=dc, server_type="config_server")
    if sql_info.num_servers == 0:
        sys.stderr.write(" Host %s is no cluster-config-server" % (server_full_name))
        dc.release()
        sys.exit(5)
    if check:
        dc.release()
        sys.exit(0)
    if sql_info.num_servers > 1:
        print "Database error for host %s (cluster_config_server): too many entries found (%d)" % (server_full_name, sql_info.num_servers)
        dc.release()
    else:
        loc_config["SERVER_IDX"] = sql_info.server_device_idx
        log_lines = []
        if loc_config["KILL_RUNNING"]:
            kill_dict = process_tools.build_kill_dict(pname)
            for key, value in kill_dict.iteritems():
                log_str = "Trying to kill pid %d (%s) with signal 9 ..." % (key, value)
                try:
                    os.kill(key, 9)
                except:
                    log_str = "%s error (%s)" % (log_str, process_tools.get_except_info())
                else:
                    log_str = "%s ok" % (log_str)
                logging_tools.my_syslog(log_str)
        loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, sql_info.server_device_idx, "config_server", "Cluster config Server")
        nagios_master_list = config_tools.device_with_config("nagios_master", dc)
        if nagios_master_list.keys():
            nagios_master_name = nagios_master_list.keys()[0]
            nagios_master = nagios_master_list[nagios_master_name]
            # good stuff :-)
            for routing_info in sql_info.get_route_to_other_device(dc, nagios_master):
                if routing_info[1] in ["l", "p", "o"]:
                    loc_config["NAGIOS_IP"] = routing_info[3][1][0]
                    break
        if loc_config["FIXIT"]:
            process_tools.fix_directories(loc_config["USER_NAME"], loc_config["GROUP_NAME"], [glob_config["LOG_DIR"], "/var/run/cluster-config-server", glob_config["CONFIG_DIR"]])
            process_tools.fix_files(loc_config["USER_NAME"], loc_config["GROUP_NAME"], ["/var/log/cluster-config-server.out", "/tmp/cluster-config-server.out"])
        dc.release()
        process_tools.renice()
        process_tools.change_user_group(loc_config["USER_NAME"], loc_config["GROUP_NAME"])
        if loc_config["DAEMON"]:
            process_tools.become_daemon()
            process_tools.set_handles({"out" : (1, "cluster-config-server.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")})
        else:
            print "Debugging cluster-config-server on %s" % (loc_config["SERVER_FULL_NAME"])
        thread_pool = server_thread_pool(db_con, glob_config, loc_config, log_lines)
        thread_pool.thread_loop()
        ret_code = 0
    db_con.close()
    del db_con
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
