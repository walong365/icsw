#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012,2013 Andreas Lang-Nevyjel, init.at
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

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import re
import tempfile
import configfile
import cluster_location
import base64
import os.path
import time
import pprint
import stat
import logging_tools
import process_tools
import array
import server_command
import config_tools
import threading_tools
import net_tools
import uuid_tools
import zmq
import crypt
from django.db import connection
from lxml import etree
from lxml.builder import E
from initat.cluster.backbone.models import device, network, config, device_variable, net_ip, \
     boot_uuid, netdevice, partition, sys_partition, wc_files, tree_node, config_str, \
     cached_log_status, cached_log_source, log_source, devicelog, domain_tree_node
from django.db.models import Q
import module_dependency_tools
import networkx

try:
    from cluster_config_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_PUB_PORT = 8005
SERVER_PULL_PORT = 8006
NCS_PORT = 8010
GATEWAY_THRESHOLD = 1000

def pretty_print(name, obj, offset):
    lines = []
    off_str = " " * offset
    if type(obj) == dict:
        if name:
            head_str = "%s%s(D):" % (off_str, name)
            lines.append(head_str)
        else:
            head_str = ""
        keys = sorted(obj.keys())
        max_len = max([len(key) for key in keys])
        for key in keys:
            lines.extend(pretty_print(
                ("%s%s" % (key, " " * max_len))[0:max_len],
                obj[key],
                len(head_str)))
    elif type(obj) in [list, tuple]:
        head_str = "%s%s(L %d):" % (off_str, name, len(obj))
        lines.append(head_str)
        idx = 0
        for value in obj:
            lines.extend(pretty_print("%d" % (idx), value, len(head_str)))
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
    def __init__(self, destination, c_type, **kwargs):
        self.dest = destination
        self.c_type = c_type
        self.content = []
        self.source_configs = set()
        self.source = kwargs.get("source", "")
        self.uid, self.gid = (0, 0)
        if self.c_type not in ["i", "?"]:
            # use keyword arg if present, otherwise take global CONFIG
            cur_config = kwargs.get("config", globals()["CONFIG"])
            self.mode = cur_config.dir_mode if self.c_type == "d" else (cur_config.link_mode if self.c_type == "l" else cur_config.file_mode)
            if "config" not in kwargs:
                cur_config._add_object(self)
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
    def get_effective_type(self):
        return self.c_type
    def __eq__(self, other):
        if self.dest == other.dest and self.c_type == other.c_type:
            return True
        else:
            return False
    def set_config(self, conf):
        self.add_config(conf.get_name())
    # compatibility calls (mode, uid and gid)
    def set_mode(self, mode):
        self.mode = mode
    def set_uid(self, uid):
        self.uid = uid
    def set_gid(self, gid):
        self.gid = gid
    def _set_mode(self, mode):
        if type(mode) == type(""):
            self.__mode = int(mode, 8)
        else:
            self.__mode = mode
    def _get_mode(self):
        return self.__mode
    mode = property(_get_mode, _set_mode)
    def append(self, what):
        self +=what
    def __iadd__(self, line):
        if type(line) in [str, unicode]:
            self.content.append("%s\n" % (line))
        elif type(line) == type([]):
            self.content.extend(["%s\n" % (s_line) for s_line in line])
        elif type(line) == dict:
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
    def write_object(self, t_file):
        return "__override__ write_object (%s)" % (t_file)

class internal_object(new_config_object):
    def __init__(self, destination):
        new_config_object.__init__(self, destination, "i", mode="0755")
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.mode = ref_config.mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid
    def write_object(self, t_file):
        return ""

class file_object(new_config_object):
    def __init__(self, destination, **kwargs):
        """ example from ba/ca:
        a=config.add_file_object("/etc/services", from_image=True, dev_dict=dev_dict)
        new_content = []
        print len(a.content)
        for line in a.content:
            if line.lstrip().startswith("mult"):
                print line
        """
        new_config_object.__init__(self, destination, "f", **kwargs)
        self.set_mode("0644")
        if kwargs.get("from_image", False):
            s_dir = kwargs["dev_dict"]["image"].get("source", None)
            if s_dir:
                s_content = file("%s/%s" % (s_dir, destination), "r").read()
                self +=s_content.split("\n")
    def set_config(self, ref_config):
        self.mode = ref_config.file_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid
    def write_object(self, t_file):
        file(t_file, "w").write("".join(self.content))
        return "%d %d %s %s" % (self.uid,
                                self.gid,
                                oct(self.mode),
                                self.dest)

class link_object(new_config_object):
    def __init__(self, destination, source, **kwargs):
        new_config_object.__init__(self, destination, "l", source=source, **kwargs)
    def set_config(self, ref_config):
        self.mode = ref_config.file_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid
    def write_object(self, t_file):
        return "%s %s" % (self.source, self.dest)

class dir_object(new_config_object):
    def __init__(self, destination, **kwargs):
        new_config_object.__init__(self, destination, "d", **kwargs)
    def set_config(self, ref_config):
        self.mode = ref_config.dir_mode
        self.uid = ref_config.uid
        self.gid = ref_config.gid
    def write_object(self, t_file):
        return "%d %d %s %s" % (self.uid,
                                self.gid,
                                oct(self.mode),
                                self.dest)

class delete_object(new_config_object):
    def __init__(self, destination, **kwargs):
        new_config_object.__init__(self, destination, "e", **kwargs)
        self.recursive = kwargs.get("recursive", False)
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
    def write_object(self, t_file):
        return "%d %s" % (self.recursive, self.dest)

class copy_object(new_config_object):
    def __init__(self, destination, source, **kwargs):
        new_config_object.__init__(self, destination, "c", source=source, **kwargs)
        self.content = [file(self.source, "r").read()]
        orig_stat = os.stat(self.source)
        self.uid, self.gid, self.mode = (orig_stat[stat.ST_UID],
                                         orig_stat[stat.ST_GID],
                                         stat.S_IMODE(orig_stat[stat.ST_MODE]))
    def get_effective_type(self):
        return "f"
    def set_config(self, ref_config):
        new_config_object.set_config(self, ref_config)
        self.set_mode(ref_config.get_dir_mode())
        self.set_uid(ref_config.get_uid())
        self.set_gid(ref_config.get_gid())
    def write_object(self, t_file):
        file(t_file, "w").write("".join(self.content))
        os.chmod(t_file, 0644)
        return "%d %d %s %s" % (self.uid,
                                self.gid,
                                oct(self.mode),
                                self.dest)

class tree_node_g(object):
    """ tree node representation for intermediate creation of tree_node structure """
    def __init__(self, path="", c_node=None, is_dir=True, parent=None, intermediate=False):
        self.path = path
        if parent:
            self.nest_level = parent.nest_level + 1
        else:
            self.nest_level = 0
        self.parent = parent
        self.is_dir = is_dir
        # intermediate node
        self.intermediate = True
        # link related stuff
        self.is_link = False
        self.link_source = ""
        self.root_node = self.path == ""
        # for bookkeeping
        self.used_config_pks = set()
        self.error_flag = False
        if self.is_dir:
            self.childs = {}
        if c_node is None:
            self.content_node = new_config_object(self.path, "?", mode="0755")
        else:
            self.content_node = c_node
    def add_config(self, c_pk):
        self.used_config_pks.add(c_pk)
    def get_path(self):
        if self.parent:
            return "%s/%s" % (self.parent.get_path(), self.path)
        else:
            return "%s" % (self.path)
    def get_node(self, path, c_node, dir_node=False, use_existing=False):
        if self.root_node:
            # normalize path at top level
            path = os.path.normpath(path)
        if path == self.path:
            if self.is_dir == dir_node:
                if self.content_node != c_node:
                    if not use_existing:
                        raise ValueError, "content node '%s' already set, missing append=True ?" % (path)
                # match, return myself
                if self.content_node.c_type == "l":
                    self.is_link = True
                self.intermediate = False
                return self
            else:
                raise ValueError, "request node (%s, %s) is a %s" % (
                    path,
                    "dir" if dir_node else "file",
                    "dir" if self.is_dir else "file")
        else:
            path_list = path.split(os.path.sep)
            if path_list[0] != self.path:
                raise KeyError, "path mismatch: %s != %s" % (path_list[0], self.path)
            if path_list[1] not in self.childs:
                if len(path_list) == 2 and not dir_node:
                    # add content node
                    self.childs[path_list[1]] = tree_node_g(path_list[1], c_node, parent=self, is_dir=False)
                else:
                    # add dir node
                    self.childs[path_list[1]] = tree_node_g(path_list[1], c_node, parent=self, intermediate=True)
            return self.childs[path_list[1]].get_node(os.path.join(*path_list[1:]), c_node, dir_node=dir_node, use_existing=use_existing)
    def get_type_str(self):
        return "dir" if self.is_dir else ("link" if self.is_link else "file")
    def __unicode__(self):
        sep_str = "  " * self.nest_level
        ret_f = ["%s%s%s (%s) %s%s    :: %d/%d/%o" % (
            "[I]" if self.intermediate else "   ",
            "[E]" if self.error_flag else "   ",
            sep_str,
            self.get_type_str(),
            "%s -> %s" % (self.path, self.content_node.source) if self.is_link else self.path,
            "/" if self.is_dir else "",
        self.content_node.uid,
        self.content_node.gid,
        self.content_node.mode)]
        if self.is_dir:
            ret_f.extend([unicode(cur_c) for cur_c in self.childs.itervalues()])
        return "\n".join(ret_f)
    def write_node(self, cur_c, cur_bc, **kwargs):
        node_list = []
        cur_tn = tree_node(
            device=cur_bc.conf_dict["device"],
            is_dir=self.is_dir,
            is_link=self.is_link,
            intermediate=self.intermediate,
            parent=kwargs.get("parent", None))
        cur_tn.save()
        cur_tn.node = self
        cur_wc = wc_files(
            device=cur_bc.conf_dict["device"],
            dest=self.path,
            tree_node=cur_tn,
            error_flag=self.error_flag,
            mode=self.content_node.mode,
            uid=self.content_node.uid,
            gid=self.content_node.gid,
            dest_type=self.content_node.c_type,
            source=self.content_node.source,
            content="".join(self.content_node.content))
        cur_wc.save()
        node_list.append((cur_tn, cur_wc))
        if self.is_dir:
            node_list.extend(sum([cur_child.write_node(cur_c, cur_bc, parent=cur_tn) for cur_child in self.childs.itervalues()], []))
        return node_list

class generated_tree(tree_node_g):
    def __init__(self):
        tree_node_g.__init__(self, "")
    def write_config(self, cur_c, cur_bc):
        cur_c.log("creating tree")
        tree_node.objects.filter(Q(device=cur_bc.conf_dict["device"])).delete()
        write_list = self.write_node(cur_c, cur_bc)
        nodes_written = len(write_list)
        # tree_node.objects.bulk_create([cur_tn for cur_tn, cur_wc in write_list])
        # wc_files.objects.bulk_create([cur_wc for cur_tn, cur_wc in write_list])
        # print write_list
        active_identifier = cur_bc.conf_dict["net"].identifier
        cur_c.log("writing config files for %s to %s" % (
            active_identifier,
            cur_c.node_dir))
        config_dir = os.path.join(cur_c.node_dir, "content_%s" % (active_identifier))
        if not os.path.isdir(config_dir):
            cur_c.log("creating directory %s" % (config_dir))
            os.mkdir(config_dir)
        config_dict = {
            "f" : "%s/config_files_%s" % (cur_c.node_dir, active_identifier),
            "l" : "%s/config_links_%s" % (cur_c.node_dir, active_identifier),
            "d" : "%s/config_dirs_%s" % (cur_c.node_dir, active_identifier),
            "e" : "%s/config_delete_%s" % (cur_c.node_dir, active_identifier)}
        handle_dict = {}
        num_dict = dict([(key, 0) for key in config_dict.iterkeys()])
        for cur_tn, cur_wc in write_list:
            if cur_wc.dest_type not in ["i", "?"] and not cur_tn.intermediate:
                eff_type = cur_tn.node.content_node.get_effective_type()
                handle = handle_dict.setdefault(eff_type, file(config_dict[eff_type], "w"))
                num_dict[eff_type] += 1
                out_name = os.path.join(config_dir, "%d" % (num_dict[eff_type]))
                try:
                    add_line = cur_tn.node.content_node.write_object(out_name)
                except:
                    cur_c.log("error creating node %s: %s" % (
                        cur_tn.node.content_node.dest,
                        process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    handle.write("%d %s\n" % (num_dict[eff_type], add_line))
        cur_c.log("closing %s" % (logging_tools.get_plural("handle", len(handle_dict.keys()))))
        [handle.close() for handle in handle_dict.itervalues()]
        # print cur_c.node_dir, dir(cur_c)
        # print cur_bc.conf_dict["net"]
        # pprint.pprint(cur_bc.conf_dict)
        cur_c.log("wrote %s" % (logging_tools.get_plural("node", nodes_written)))

class build_container(object):
    def __init__(self, b_client, config_dict, conf_dict, g_tree, router_obj):
        self.b_client = b_client
        # dict of all configs (pk -> config)
        self.config_dict = config_dict
        # config dict
        self.conf_dict = conf_dict
        # router object
        self.router_obj = router_obj
        self.g_tree = g_tree
        self.__s_time = time.time()
        self.file_mode, self.dir_mode, self.link_mode = ("0644", "0755", "0644")
        self.log("init build continer")
    def init_uid_gid(self):
        self.uid, self.gid = (0, 0)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK, **kwargs):
        self.b_client.log("[bc] %s" % (what), level, **kwargs)
    def close(self):
        self.log("done in %s" % (logging_tools.get_diff_time_str(time.time() - self.__s_time)))
        del self.b_client
        del self.config_dict
        del self.g_tree
    def _set_dir_mode(self, mode):
        self.__dir_mode = mode
    def _get_dir_mode(self):
        return self.__dir_mode
    dir_mode = property(_get_dir_mode, _set_dir_mode)
    def _set_file_mode(self, mode):
        self.__file_mode = mode
    def _get_file_mode(self):
        return self.__file_mode
    file_mode = property(_get_file_mode, _set_file_mode)
    def _set_link_mode(self, mode):
        self.__link_mode = mode
    def _get_link_mode(self):
        return self.__link_mode
    link_mode = property(_get_link_mode, _set_link_mode)
    def _add_object(self, new_obj):
        return getattr(self, "_add_%s_object" % ({
            "l" : "link",
            "e" : "delete",
            "f" : "file",
            "c" : "copy",
            "d" : "dir"}[new_obj.c_type]))(new_obj)
    def add_copy_object(self, fon, source, **kwargs):
        return self._add_copy_object(copy_object(fon, config=self, source=source, **kwargs))
    def _add_copy_object(self, c_obj):
        cur_node = self.g_tree.get_node(c_obj.dest, c_obj)
        if not cur_node in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        return cur_node.content_node
    def add_file_object(self, fon, **kwargs):
        return self._add_file_object(file_object(fon, config=self, **kwargs), append=kwargs.get("append", False))
    def _add_file_object(self, f_obj, append=False):
        cur_node = self.g_tree.get_node(f_obj.dest, f_obj, use_existing=append)
        if not cur_node in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        f_obj.set_config(self)
        return cur_node.content_node
    def add_dir_object(self, don, **kwargs):
        return self._add_dir_object(dir_object(don, config=self, **kwargs))
    def _add_dir_object(self, d_obj):
        cur_node = self.g_tree.get_node(d_obj.dest, d_obj, dir_node=True)
        if not cur_node in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        d_obj.set_config(self)
        return cur_node.content_node
    def add_delete_object(self, don, **kwargs):
        return self._add_delete_object(delete_object(don, config=self, **kwargs))
    def _add_delete_object(self, d_obj):
        cur_node = self.g_tree.get_node(d_obj.dest, d_obj)
        if not cur_node in self.__deleted_files:
            self.__deleted_files.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        return None
    def add_link_object(self, fon, source, **kwargs):
        return self._add_link_object(link_object(fon, config=self, source=source, **kwargs))
    def _add_link_object(self, l_obj):
        cur_node = self.g_tree.get_node(l_obj.dest, l_obj)
        if not cur_node in self.__touched_links:
            self.__touched_links.append(cur_node)
        l_obj.set_config(self)
        cur_node.add_config(self.cur_conf.pk)
        return cur_node.content_node
    def process_scripts(self, conf_pk):
        cur_conf = self.config_dict[conf_pk]
        self.cur_conf = cur_conf
        # build local variables
        local_vars = dict(sum(
            [[(cur_var.name, cur_var.value) for cur_var in getattr(cur_conf, "config_%s_set" % (var_type)).all()] for var_type in ["str", "int", "bool", "blob"]], []))
        # copy local vars
        conf_dict = self.conf_dict
        for key, value in local_vars.iteritems():
            conf_dict[key] = value
        self.log("config %s: %s defined, %s enabled, %s" % (
            cur_conf.name,
            logging_tools.get_plural("script", len(cur_conf.config_script_set.all())),
            logging_tools.get_plural("script", len([cur_scr for cur_scr in cur_conf.config_script_set.all() if cur_scr.enabled])),
            logging_tools.get_plural("local variable", len(local_vars.keys()))))
        for cur_script in [cur_scr for cur_scr in cur_conf.config_script_set.all() if cur_scr.enabled]:
            self.init_uid_gid()
            lines = cur_script.value.split("\n")
            self.log(" - scriptname '%s' (pri %d) has %s" % (
                cur_script.name,
                cur_script.priority,
                logging_tools.get_plural("line", len(lines))))
            start_c_time = time.time()
            try:
                code_obj = compile(
                    cur_script.value.replace("\r\n", "\n") + "\n",
                    "<script %s>" % (cur_script.name),
                    "exec")
            except:
                exc_info = process_tools.exception_info()
                self.log("error during compile of %s (%s)" % (
                    cur_script.name,
                    logging_tools.get_diff_time_str(time.time() - start_c_time)),
                         logging_tools.LOG_LEVEL_ERROR,
                         register=True)
                for line in exc_info.log_lines:
                    self.log("   *** %s" % (line), logging_tools.LOG_LEVEL_ERROR)
            else:
                compile_time = time.time() - start_c_time
                # prepare stdout / stderr
                start_time = time.time()
                stdout_c, stderr_c = (logging_tools.dummy_ios(), logging_tools.dummy_ios())
                old_stdout, old_stderr = (sys.stdout, sys.stderr)
                sys.stdout, sys.stderr = (stdout_c  , stderr_c)
                self.__touched_objects, self.__touched_links, self.__deleted_files = ([], [], [])
                try:
                    # FIXME, not threadsafe (thread safety needed here ?)
                    global CONFIG
                    CONFIG = self
                    ret_code = eval(code_obj, {}, {
                        # old version
                        "dev_dict"        : conf_dict,
                        # new version
                        "conf_dict"       : conf_dict,
                        "router_obj"      : self.router_obj,
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
                        "do_uuid"         : do_uuid,
                        "partition_setup" : partition_setup,
                        })
                except:
                    exc_info = process_tools.exception_info()
                    conf_dict["called"].setdefault(False, []).append((cur_conf.pk, [line for line in exc_info.log_lines]))
                    self.log("An Error occured during eval() after %s:" % (logging_tools.get_diff_time_str(time.time() - start_time)),
                             logging_tools.LOG_LEVEL_ERROR,
                             register=True)
                    for line in exc_info.log_lines:
                        self.log(" *** %s" % (line), logging_tools.LOG_LEVEL_ERROR)
                    # log stdout / stderr
                    self._show_logs(stdout_c, stderr_c)
                    # create error-entry, preferable not direct in config :-)
                    # FIXME
                    # remove objects
                    if self.__touched_objects:
                        self.log("%s touched : %s" % (
                            logging_tools.get_plural("object", len(self.__touched_objects)),
                            ", ".join([cur_obj.get_path() for cur_obj in self.__touched_objects])))
                        for to in self.__touched_objects:
                            to.error_flag = True
                    else:
                        self.log("no objects touched")
                    if self.__touched_links:
                        self.log("%s touched : %s" % (
                            logging_tools.get_plural("link", len(self.__touched_links)),
                            ", ".join([cur_link.get_path() for cur_link in self.__touched_links])))
                        for tl in self.__touched_links:
                            tl.error_flag = True
                    else:
                        self.log("no links touched")
                    if self.__deleted_files:
                        self.log("%s deleted : %s" % (
                            logging_tools.get_plural("delete", len(self.__deleted_files)),
                            ", ".join([cur_dl.get_path() for cur_dl in self.__deleted_files])))
                        for d_file in self.__deleted_files:
                            d_file.error_flag = True
                    else:
                        self.log("no objects deleted")
                else:
                    conf_dict["called"].setdefault(True, []).append(cur_conf.pk)
                    if ret_code == None:
                        ret_code = 0
                    self.log("  exited after %s (%s compile time) with return code %d" % (
                        logging_tools.get_diff_time_str(time.time() - start_time),
                        logging_tools.get_diff_time_str(compile_time),
                        ret_code))
                    self._show_logs(stdout_c, stderr_c, register_error=True, pre_str="%s wrote something to stderr" % (cur_conf.name))
                finally:
                    del CONFIG
                    sys.stdout, sys.stderr = (old_stdout, old_stderr)
                    code_obj = None
        # print unicode(self.g_tree)
        # remove local vars
        for key in local_vars.iterkeys():
            del conf_dict[key]
        del self.cur_conf
    def _show_logs(self, stdout_c, stderr_c, **kwargs):
        for log_line in [line.rstrip() for line in stdout_c.get_content().split("\n") if line.strip()]:
            self.log("out: %s" % (log_line))
        for log_line in [line.rstrip() for line in stderr_c.get_content().split("\n") if line.strip()]:
            self.log("*** err: %s" % (log_line), logging_tools.LOG_LEVEL_ERROR)
            if kwargs.get("register_error", False):
                self.log(kwargs.get("pre_str", "stderr"), logging_tools.LOG_LEVEL_ERROR, register=True)

def do_uuid(conf):
    conf_dict = conf.conf_dict
    uuid_str = "urn:uuid:%s" % (conf_dict["device"].uuid)
    cdf_file = conf.add_file_object("/etc/sysconfig/cluster/.cluster_device_uuid")
    cdf_file.append(uuid_str)
    hm_uuid = conf.add_file_object("/etc/sysconfig/host-monitoring.d/0mq_id")
    hm_uuid.append(
        etree.tostring(
            E.bind_info(E.zmq_id(uuid_str, bind_address="*")),
            pretty_print=True,
            xml_declaration=True,
        )
    )

def do_nets(conf):
    conf_dict = conf.conf_dict
    sys_dict = conf_dict["system"]
    append_dict, dev_dict = ({}, {})
    write_order_list, macs_used, lu_table = ([], {}, {})
    for check_for_bootdevice in [False, True]:
        for cur_ip in conf_dict["node_if"]:
            if (not check_for_bootdevice and cur_ip.netdevice_id == conf_dict["device"].bootnetdevice_id) or (check_for_bootdevice and not cur_ip.netdevice_id == conf_dict["device"].bootnetdevice_id):
                if int(cur_ip.netdevice.macaddr.replace(":", ""), 16) != 0 and cur_ip.netdevice.macaddr.lower() in macs_used.keys():
                    print "*** error, macaddress %s on netdevice %s already used for netdevice %s" % (cur_ip.netdevice.macaddr, cur_ip.netdevice.devname, macs_used[cur_ip.netdevice.macaddr.lower()])
                else:
                    macs_used[cur_ip.netdevice.macaddr.lower()] = cur_ip.netdevice.devname
                    write_order_list.append(cur_ip.netdevice_id)
                    lu_table[cur_ip.netdevice_id] = cur_ip
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
        cur_ip = lu_table[net_idx]
        cur_nd = cur_ip.netdevice
        cur_net = cur_ip.network
        cur_dtn = cur_ip.domain_tree_node
        if cur_dtn is None:
            cur_dtn = domain_tree_node.objects.get(Q(depth=0))
        if cur_nd.pk == conf_dict["device"].bootnetdevice_id:
            if sys_dict["vendor"] == "suse":
                new_co = conf.add_file_object("/etc/HOSTNAME")
                new_co += "%s%s.%s" % (conf_dict["host"], cur_dtn.node_postfix, cur_dtn.full_name)
            elif sys_dict["vendor"] == "debian":
                new_co = conf.add_file_object("/etc/hostname")
                new_co += "%s%s.%s" % (conf_dict["host"], cur_dtn.node_postfix, cur_dtn.full_name)
            else:
                new_co = conf.add_file_object("/etc/sysconfig/network", append=True)
                new_co += "HOSTNAME=%s" % (conf_dict["host"])
                new_co += "NETWORKING=yes"
        log_str = "netdevice %10s (mac %s)" % (cur_nd.devname, cur_nd.macaddr)
        if sys_dict["vendor"] == "suse":
            # suse-mode
            if ((sys_dict["version"] >= 9 and sys_dict["release"] > 0) or sys_dict["version"] > 9):
                act_filename = None
                if any([cur_nd.devname.startswith(cur_pf) for cur_pf in ["eth", "myri", "ib"]]):
                    mn = re.match("^(?P<devname>.+):(?P<virtual>\d+)$", cur_nd.devname)
                    if mn:
                        log_str += ", virtual of %s" % (mn.group("devname"))
                        append_dict.setdefault(mn.group("devname"), {})
                        append_dict[mn.group("devname")][mn.group("virtual")] = {
                            "BROADCAST" : cur_net.broadcast,
                            "IPADDR"    : cur_ip.ip,
                            "NETMASK"   : cur_net.netmask,
                            "NETWORK"   : cur_net.network}
                    else:
                        # FIXME; take netdevice even with zero macaddr
                        if int(cur_nd.macaddr.replace(":", ""), 16) != 0 or True:
                            dev_dict[cur_nd.devname] = cur_nd.macaddr
                            if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10 or (sys_dict["version"], sys_dict["release"]) == (10, 10)):
                                # openSUSE 10.3, >= 11.0
                                if cur_nd.vlan_id:
                                    act_filename = "ifcfg-vlan%d" % (cur_nd.vlan_id)
                                else:
                                    act_filename = "ifcfg-%s" % (cur_nd.devname)
                            else:
                                act_filename = "ifcfg-eth-id-%s" % (cur_nd.macaddr)
                                if global_config["ADD_NETDEVICE_LINKS"]:
                                    conf.add_link_object("/etc/sysconfig/network/%s" % (act_filename), "/etc/sysconfig/network/ifcfg-%s" % (cur_nd.devname))
                        else:
                            log_str += ", ignoring (zero macaddress)"
                else:
                    act_filename = "ifcfg-%s" % (cur_nd.devname)
                if act_filename:
                    act_file = {
                        "BOOTPROTO" : "static",
                        "BROADCAST" : cur_net.broadcast,
                        "IPADDR"    : cur_ip.ip,
                        "NETMASK"   : cur_net.netmask,
                        "NETWORK"   : cur_net.network,
                        "STARTMODE" : "onboot"
                    }
                    if cur_nd.vlan_id:
                        act_file["ETHERDEVICE"] = cur_nd.devname
                    if not cur_nd.fake_macaddr:
                        pass
                    elif int(cur_nd.fake_macaddr.replace(":", ""), 16) != 0:
                        log_str += ", with fake_macaddr"
                        act_file["LLADDR"] = cur_nd.fake_macaddr
                        conf.add_link_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (cur_nd.fake_macaddr), act_filename)
                    new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                    new_co += act_file
            else:
                act_filename = "ifcfg-%s" % (cur_nd.devname)
                act_file = {
                    "BOOTPROTO"     : "static",
                    "BROADCAST"     : cur_net.broadcast,
                    "IPADDR"        : cur_ip.ip,
                    "NETMASK"       : cur_net.netmask,
                    "NETWORK"       : cur_net.network,
                    "REMOTE_IPADDR" : "",
                    "STARTMODE"     : "onboot",
                    "WIRELESS"      : "no"}
                new_co = conf.add_file_object("/etc/sysconfig/network/%s" % (act_filename))
                new_co += act_file
        elif sys_dict["vendor"] == "debian":
            glob_nf += ""
            if net["devname"] == "lo":
                glob_nf += "iface %s inet loopback" % (cur_nd.devname)
            else:
                glob_nf += "iface %s inet static" % (cur_nd.devname)
                glob_nf += "      address %s" % (cur_ip.ip)
                glob_nf += "      netmask %s" % (cur_net.netmask)
                glob_nf += "    broadcast %s" % (cur_net.broadcast)
                if net["devname"] == boot_dev:
                    glob_nf += "      gateway %s" % (def_ip)
                if not cur_nd.fake_macaddr:
                    pass
                elif int(cur_nd.fake_macaddr.replace(":", ""), 16) != 0:
                    log_str += ", with fake_macaddr"
                    glob_nf += "    hwaddress ether %s" % (cur_nd.fake_macaddr)
        else:
            # redhat-mode
            act_filename = "ifcfg-%s" % (cur_nd.devname)
            if cur_nd.devname == "lo":
                d_file = "/etc/sysconfig/network-scripts/%s" % (act_filename)
            else:
                d_file = "/etc/sysconfig/network-scripts/%s" % (act_filename)
            new_co = conf.add_file_object(d_file)
            new_co += {
                "BOOTPROTO" : "static",
                "BROADCAST" : cur_net.broadcast,
                "IPADDR"    : cur_ip.ip,
                "NETMASK"   : cur_net.netmask,
                "NETWORK"   : cur_net.network,
                "DEVICE"    : cur_nd.devname,
                "ONBOOT"    : "yes"}
            if global_config["WRITE_REDHAT_HWADDR_ENTRY"]:
                new_co += {"HWADDR" : cur_nd.macaddr.lower()}
        # print log_str
    # handle virtual interfaces for Systems above SUSE 9.0
    for orig, virtuals in append_dict.iteritems():
        for virt, stuff in virtuals.iteritems():
            co = conf.add_file_object("/etc/sysconfig/network/ifcfg-eth-id-%s" % (dev_dict[orig]))
            co += {
                "BROADCAST_%s" % (virt) : stuff["BROADCAST"],
                "IPADDR_%s" % (virt)    : stuff["IPADDR"],
                "NETMASK_%s" % (virt)   : stuff["NETMASK"],
                "NETWORK_%s" % (virt)   : stuff["NETWORK"],
                "LABEL_%s" % (virt)     : virt}

def get_default_gw(conf):
    conf_dict = conf.conf_dict
    # how to get the correct gateway:
    # if all gw_pris < GATEWAY_THRESHOLD the server is the gateway
    # if any gw_pris >= GATEWAY_THRESHOLD the one with the highest gw_pri is taken
    gw_list = []
    for cur_ip in conf_dict["node_if"]:
        if cur_ip.netdevice.vlan_id:
            net_dev_name = "vlan%d" % (cur_ip.netdevice.vlan_id)
        else:
            net_dev_name = cur_ip.netdevice.devname
        gw_list.append((cur_ip.netdevice.pk, net_dev_name, cur_ip.network.gw_pri, cur_ip.network.gateway, cur_ip.netdevice.macaddr))
    # determine gw_pri
    def_ip, boot_dev, gw_source, boot_mac = ("", "", "<not set>", "")
    # any wg_pri above GATEWAY_THRESHOLD ?
    if gw_list:
        print "Possible gateways:"
        for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list:
            print " idx %3d, dev %6s, gw_pri %6d, gw_ip %15s, mac %s%s" % (
                netdev_idx,
                net_devname,
                gw_pri,
                gw_ip,
                net_mac,
                gw_pri > GATEWAY_THRESHOLD and "(*)" or "")
    max_gw_pri = max([gw_pri for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list])
    if  max_gw_pri > GATEWAY_THRESHOLD:
        gw_source = "network setting (gw_pri %d > %d)" % (max_gw_pri, GATEWAY_THRESHOLD)
        boot_dev, def_ip, boot_mac = [(net_devname, gw_ip, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if gw_pri == max_gw_pri][0]
    elif "mother_server_ip" in conf_dict:
        # we use the bootserver_ip as gateway
        server_ip = conf_dict["mother_server_ip"]
        boot_dev, act_gw_pri, boot_mac = ([(net_devname, gw_pri, net_mac) for netdev_idx, net_devname, gw_pri, gw_ip, net_mac in gw_list if netdev_idx == conf_dict["device"].bootnetdevice_id] + [("", 0, "")])[0]
        gw_source = "server address taken as ip from mother_server (gw_pri %d < %d and bootnetdevice_idx ok)" % (act_gw_pri, GATEWAY_THRESHOLD)
        def_ip = server_ip
    else:
        # nothing found
        pass
    return gw_source, def_ip, boot_dev, boot_mac

def do_routes(conf):
    conf_dict = conf.conf_dict
    sys_dict = conf_dict["system"]
    if sys_dict["vendor"] == "debian":
        pass
    else:
        if sys_dict["vendor"] == "suse":
            filename = "/etc/sysconfig/network/routes"
        else:
            filename = "/etc/sysconfig/static-routes"
        new_co = conf.add_file_object(filename)
        for cur_ip in conf_dict["node_if"]:
            cur_nd = cur_ip.netdevice
            cur_nw = cur_ip.network
            if cur_nd.vlan_id:
                net_dev_name = "vlan%d" % (cur_nd.vlan_id)
            else:
                net_dev_name = cur_nd.devname
            if cur_ip.network.network_type.identifier != "l":
                if sys_dict["vendor"] == "suse":
                    if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10):
                        # openSUSE 10.3, >= 11.0
                        new_co += "%s 0.0.0.0 %s %s" % (cur_nw.network, cur_nw.netmask, net_dev_name)
                    else:
                        new_co += "%s 0.0.0.0 %s eth-id-%s" % (cur_nw.network, cur_nw.netmask, cur_nd.macaddr)
                elif sys_dict["vendor"] == "redhat" or sys_dict["vendor"].lower().startswith("centos"):
                    new_co += "any net %s netmask %s dev %s" % (cur_nw.network, cur_nw.netmask, cur_nd.devname)
        gw_source, def_ip, boot_dev, boot_mac = get_default_gw(conf)
        if def_ip:
            if sys_dict["vendor"] == "suse":
                new_co += "# from %s" % (gw_source)
                if sys_dict["vendor"] == "suse" and ((sys_dict["version"] == 10 and sys_dict["release"] == 3) or sys_dict["version"] > 10):
                    # openSUSE 10.3
                    new_co += "default %s - %s" % (def_ip, boot_dev)
                else:
                    new_co += "default %s - eth-id-%s" % (def_ip, boot_mac)
            elif sys_dict["vendor"] == "redhat" or sys_dict["vendor"].lower().startswith("centos"):
                # redhat-mode
                act_co = conf.add_file_object("/etc/sysconfig/network", append=True)
                act_co += "# from %s" % (gw_source)
                act_co += "GATEWAY=%s" % (def_ip)

def do_ssh(conf):
    conf_dict = conf.conf_dict
    ssh_types = ["rsa1", "dsa", "rsa"]
    ssh_field_names = []
    for ssh_type in ssh_types:
        ssh_field_names.extend(["ssh_host_%s_key" % (ssh_type), "ssh_host_%s_key_pub" % (ssh_type)])
    found_keys_dict = dict([(key, None) for key in ssh_field_names])
    for cur_var in device_variable.objects.filter(Q(device=conf_dict["device"]) & Q(name__in=ssh_field_names)):
        try:
            cur_val = base64.b64decode(cur_var.val_blob)
        except:
            pass
        else:
            found_keys_dict[cur_var.name] = cur_val
    print "found %s in database: %s" % (
        logging_tools.get_plural("key", len(found_keys_dict.keys())),
        ", ".join(sorted(found_keys_dict.keys())))
    new_keys = []
    for ssh_type in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn = "ssh_host_%s_key_pub" % (ssh_type)
        if not found_keys_dict[privfn] or not found_keys_dict[pubfn]:
            # delete previous versions
            device_variable.objects.filter(Q(device=conf_dict["device"]) & Q(name__in=[privfn, pubfn])).delete()
            print "Generating %s keys..." % (privfn)
            sshkn = tempfile.mktemp("sshgen")
            sshpn = "%s.pub" % (sshkn)
            if ssh_type:
                os.system("ssh-keygen -t %s -q -b 1024 -f %s -N ''" % (ssh_type, sshkn))
            else:
                os.system("ssh-keygen -q -b 1024 -f %s -N ''" % (sshkn))
            found_keys_dict[privfn] = file(sshkn, "rb").read()
            found_keys_dict[pubfn] = file(sshpn, "rb").read()
            os.unlink(sshkn)
            os.unlink(sshpn)
            new_keys.extend([privfn, pubfn])
    if new_keys:
        new_keys.sort()
        print "%s to create: %s" % (logging_tools.get_plural("key", len(new_keys)),
                                    ", ".join(new_keys))
        for new_key in new_keys:
            new_dv = device_variable(
                device=conf_dict["device"],
                name=new_key,
                var_type="b",
                description="SSH key %s" % (new_key),
                val_blob=base64.b64encode(found_keys_dict[new_key]))
            new_dv.save()
    for ssh_type in ssh_types:
        privfn = "ssh_host_%s_key" % (ssh_type)
        pubfn = "ssh_host_%s_key_pub" % (ssh_type)
        pubfrn = "ssh_host_%s_key.pub" % (ssh_type)
        for var in [privfn, pubfn]:
            new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_pub", ".pub")))
            new_co.bin_append(found_keys_dict[var])
            if var == privfn:
                new_co.mode = "0600"
        if ssh_type == "rsa1":
            for var in [privfn, pubfn]:
                new_co = conf.add_file_object("/etc/ssh/%s" % (var.replace("_rsa1", "").replace("_pub", ".pub")))
                new_co.bin_append(found_keys_dict[var])
                if var == privfn:
                    new_co.mode = "0600"

def do_fstab(conf):
    act_ps = partition_setup(conf)
    fstab_co = conf.add_file_object("/etc/fstab")
    fstab_co += act_ps.fstab

class partition_setup(object):
    def __init__(self, conf):
        root_dev = None
        part_valid = False
        part_list = partition.objects.filter(Q(partition_disc__partition_table=conf.conf_dict["device"].act_partition_table)).select_related("partition_disc", "partition_disc__partition_table", "partition_fs")
        if len(part_list):
            part_valid = True
            disc_dict, fstab, sfdisk, parted = ({}, [], [], [])
            fspart_dict = {}
            first_disc, root_part, root_part_type = (None, None, None)
            old_pnum, act_pnum = (0, 0)
            lower_size, upper_size = (0, 0)
            for cur_part in part_list:
                cur_disc = cur_part.partition_disc
                cur_pt = cur_disc.partition_table
                if root_dev is None:
                    root_dev = conf.conf_dict["device"].partdev
                    # partition prefix for cciss partitions
                    part_pf = "p" if root_dev.count("cciss") else ""
                is_valid, pt_name = (cur_pt.valid, cur_pt.name)
                if not is_valid:
                    part_valid = False
                    break
                act_pnum, act_disc = (cur_part.pnum, cur_disc.disc)
                if not first_disc:
                    first_disc = act_disc
                if act_disc == first_disc:
                    act_disc = root_dev
                fs_name = cur_part.partition_fs.name
                disc_dict.setdefault(act_disc, {})
                if act_pnum:
                    disc_dict[act_disc][act_pnum] = cur_part
                # generate sfdisk-entry
                while old_pnum < act_pnum - 1:
                    old_pnum += 1
                    sfdisk.append(",0, ")
                if cur_part and fs_name != "ext":
                    if cur_part.size:
                        upper_size += cur_part.size
                    else:
                        # to be replaced by stage2 by actual upper size
                        upper_size = 0
                else:
                    upper_size = 0
                parted.append("mkpart %s %s %s %s" % (
                    fs_name == "ext" and "extended" or (act_pnum < 5 and "primary" or "logical"),
                    {"ext3"  : "ext2",
                     "ext4"  : "ext2",
                     "btrfs" : "ext2",
                     "xfs"   : "ext2",
                     "swap"  : "linux-swap",
                     "lvm"   : "ext2",
                     "ext"   : ""}.get(fs_name, fs_name),
                    "%d" % (lower_size),
                    fs_name == "ext" and "_" or ("%d" % (upper_size) if upper_size else "_")
                ))
                if fs_name == "lvm":
                    parted.append("set %d lvm on" % (act_pnum))
                if upper_size:
                    lower_size = upper_size
                else:
                    upper_size = lower_size
                if cur_part.size and fs_name != "ext":
                    sfdisk.append(",%d,0x%s" % (cur_part.size, cur_part.partition_hex))
                else:
                    sfdisk.append(",,0x%s" % (cur_part.partition_hex))
                fs = fs_name or "auto"
                if (cur_part.mountpoint and fs_name != "ext") or fs_name == "swap":
                    act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                    mp = cur_part.mountpoint if cur_part.mountpoint else fs
                    if mp == "/":
                        root_part, root_part_type = (act_part, fs)
                    if not fspart_dict.has_key(fs):
                        fspart_dict[fs] = []
                    fspart_dict[fs].append(act_part)
                    fstab.append("%-20s %-10s %-10s %-10s %d %d" % (
                        act_part,
                        mp,
                        fs,
                        cur_part.mount_options and cur_part.mount_options or "rw",
                        cur_part.fs_freq,
                        cur_part.fs_passno))
                old_pnum = act_pnum
            print "  creating partition info for partition_table '%s' (root_device %s, partition postfix is '%s')" % (pt_name, root_dev, part_pf)
            if part_valid:
                for sys_part in sys_partition.objects.filter(Q(partition_table=conf.conf_dict["device"].act_partition_table)):
                    fstab.append("%-20s %-10s %-10s %-10s %d %d" % (
                        sys_part.name,
                        sys_part.mountpoint,
                        sys_part.name,
                        sys_part.mount_options and sys_part.mount_options or "rw",
                        0,
                        0))
                self.fspart_dict, self.root_part, self.root_part_type, self.fstab, self.sfdisk, self.parted = (
                    fspart_dict,
                    root_part,
                    root_part_type,
                    fstab,
                    sfdisk,
                    parted)
                # logging
                for what, name in [(fstab , "fstab "),
                                   (sfdisk, "sfdisk"),
                                   (parted, "parted")]:
                    print "Content of %s (%s):" % (name, logging_tools.get_plural("line", len(what)))
                    for line_num, line in zip(xrange(len(what)), what):
                        print " - %3d %s" % (line_num + 1, line)
            else:
                raise ValueError, "Partition-table %s is not valid" % (pt_name)
        else:
            raise ValueError, "Found no partition-info"
    def create_part_files(self, pinfo_dir):
        if self.fspart_dict:
            for pn, pp in self.fspart_dict.iteritems():
                file("%s/%sparts" % (pinfo_dir, pn), "w").write("\n".join(pp + [""]))
            for file_name, content in [("rootpart"    , self.root_part),
                                       ("rootparttype", self.root_part_type),
                                       ("fstab"       , "\n".join(self.fstab)),
                                       ("sfdisk"      , "\n".join(self.sfdisk)),
                                       ("parted"      , "\n".join(self.parted))]:
                file("%s/%s" % (pinfo_dir, file_name), "w").write("%s\n" % (content))

# generate /etc/hosts for nodes, including routing-info
def do_etc_hosts(conf):
    conf_dict = conf.conf_dict
    route_obj = conf.router_obj
    all_paths = []
    for cur_ip in conf_dict["node_if"]:
        all_paths.extend(networkx.shortest_path(route_obj.nx, cur_ip.netdevice_id, weight="weight").values())
    all_paths = sorted([route_obj.add_penalty(cur_path) for cur_path in all_paths])
    all_nds = set([cur_path[-1] for penalty, cur_path in all_paths])
    nd_lut = dict([(cur_nd.pk, cur_nd) for cur_nd in netdevice.objects.filter(Q(pk__in=all_nds)).select_related("device").prefetch_related("net_ip_set", "net_ip_set__network", "net_ip_set__domain_tree_node")])
    all_ips, ips_used = ([], set())
    for penalty, cur_path in all_paths:
        cur_nd = nd_lut[cur_path[-1]]
        for cur_ip in cur_nd.net_ip_set.all():
            if cur_ip.ip not in ips_used:
                # copy penalty value
                cur_ip.value = penalty
                ips_used.add(cur_ip.ip)
                # also check network identifiers ? FIXME
                all_ips.append((cur_nd, cur_ip))
    # ip addresses already written
    new_co = conf.add_file_object("/etc/hosts", append=True)
    # two iterations: at first the devices that match my local networks, than the rest
    tl_dtn = domain_tree_node.objects.get(Q(depth=0))
    loc_dict, max_len = ({}, 0)
    for cur_nd, cur_ip in all_ips:
        out_names = []
        cur_dtn = cur_ip.domain_tree_node or tl_dtn
        # override wrong settings for lo
        if not (cur_ip.alias.strip() and cur_ip.alias_excl):
            out_names.append("%s%s" % (cur_nd.device.name, cur_dtn.node_postfix))
        out_names.extend(cur_ip.alias.strip().split())
        if "localhost" in [entry.split(".")[0] for entry in out_names]:
            out_names = [entry for entry in out_names if entry.split(".")[0] == "localhost"]
        if cur_dtn.create_short_names:
            # also create short_names
            out_names = (" ".join(["%s.%s %s" % (entry, cur_dtn.full_name, entry) for entry in out_names])).split()
        else:
            # only print the long names
            out_names = ["%s.%s" % (entry, cur_dtn.full_name) for entry in out_names]
        loc_dict.setdefault(cur_ip.value, []).append([cur_ip.ip] + out_names)
        max_len = max(max_len, len(out_names) + 1)
    for pen, stuff in loc_dict.iteritems():
        for l_e in stuff:
            l_e.extend([""] * (max_len - len(l_e)) + ["#%d" % (pen)])
    for p_value in sorted(loc_dict.keys()):
        act_list = sorted(loc_dict[p_value])
        max_len = [0] * len(act_list[0])
        for line in act_list:
            max_len = [max(max_len[entry], len(line[entry])) for entry in range(len(max_len))]
        form_str = " ".join(["%%-%ds" % (part) for part in max_len])
        new_co += ["# penalty %d" % (p_value), ""] + [form_str % (tuple(entry)) for entry in act_list] + [""]

def do_hosts_equiv(conf):
    # no longer needed
    return

class network_tree(dict):
    def __init__(self):
        all_nets = network.objects.all().select_related("network_type", "master_network")
        for cur_net in all_nets:
            self[cur_net.pk] = cur_net
            self.setdefault(cur_net.network_type.identifier, {})[cur_net.pk] = cur_net
            # idx_list, self and slaves
            cur_net.idx_list = [cur_net.pk]
        for net_pk, cur_net in self.iteritems():
            if type(net_pk) in [int, long]:
                if cur_net.network_type.identifier == "s" and cur_net.master_network_id in self and self[cur_net.master_network_id].network_type.identifier == "p":
                    self[cur_net.master_network_id].idx_list.append(net_pk)

class build_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        self.router_obj = config_tools.router_object(self.log)
        self.config_src = log_source.objects.get(Q(pk=global_config["LOG_SOURCE_IDX"]))
        self.register_func("generate_config", self._generate_config)
        # for requests from config_control
        self.register_func("complex_request", self._complex_request)
        build_client.init(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        build_client.close_clients()
        self.__log_template.close()
    def _complex_request(self, queue_id, dev_name, req_name, *args, **kwargs):
        self.log("got request '%s' for '%s' (%d)" % (req_name, dev_name, queue_id))
        cur_c = build_client.get_client(name=dev_name)
        success = getattr(cur_c, req_name)(*args)
        self.send_pool_message("complex_result", queue_id, success)
    def _generate_config(self, attr_dict, **kwargs):
        if global_config["DEBUG"]:
            cur_query_count = len(connection.queries)
        # get client
        cur_c = build_client.get_client(**attr_dict)
        cur_c.log("starting config build")
        s_time = time.time()
        dev_sc = None
        # get device by name
        try:
            b_dev = device.objects.select_related("device_type", "device_group").prefetch_related("netdevice_set", "netdevice_set__net_ip_set").get(Q(name=cur_c.name))
        except device.DoesNotExist:
            cur_c.log("device not found by name", logging_tools.LOG_LEVEL_ERROR, state="done")
        except device.MultipleObjectsReturned:
            cur_c.log("more than one device with name '%s' found" % (cur_c.name), logging_tools.LOG_LEVEL_ERROR, state="done")
        else:
            dev_sc = config_tools.server_check(
                short_host_name=cur_c.name,
                server_type="node",
                fetch_network_info=True)
            cur_c.log("server_check report(): %s" % (dev_sc.report()))
            cur_net_tree = network_tree()
            # sanity checks
            if not cur_c.create_config_dir():
                cur_c.log("creating config_dir", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif (b_dev.prod_link_id == 0 or not b_dev.prod_link):
                cur_c.log("no valid production_link set", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif len(cur_net_tree.get("b", {})) > 1:
                cur_c.log("more than one boot network found", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif not len(cur_net_tree.get("b", {})):
                cur_c.log("no boot network found", logging_tools.LOG_LEVEL_ERROR, state="done")
            elif not len(cur_net_tree.get("p", {})):
                cur_c.log("no production networks found", logging_tools.LOG_LEVEL_ERROR, state="done")
            else:
                cur_c.log("found %s: %s" % (
                    logging_tools.get_plural("production network", len(cur_net_tree["p"])),
                    ", ".join([unicode(cur_net) for cur_net in cur_net_tree["p"].itervalues()])))
                act_prod_net = None
                for prod_net in cur_net_tree["p"].itervalues():
                    cur_c.clean_directory(prod_net.identifier)
                    cur_c.log("%s %s" % (
                        "active" if prod_net.pk == b_dev.prod_link_id else "inactive",
                        prod_net.get_info()))
                    if prod_net.pk == b_dev.prod_link.pk:
                        act_prod_net = prod_net
                if not act_prod_net:
                    cur_c.log("invalid production link", logging_tools.LOG_LEVEL_ERROR, state="done")
                else:
                    ips_in_prod = [cur_ip.ip for cur_ip in dev_sc.identifier_ip_lut.get("p", [])]
                    if ips_in_prod:
                        netdevices_in_net = [dev_sc.ip_netdevice_lut[ip] for ip in ips_in_prod]
                        if b_dev.bootnetdevice_id and b_dev.bootnetdevice:
                            net_devs_ok = [net_dev for net_dev in netdevices_in_net if net_dev.pk == b_dev.bootnetdevice.pk]
                            net_devs_warn = [net_dev for net_dev in netdevices_in_net if net_dev.pk != b_dev.bootnetdevice.pk]
                        else:
                            net_devs_ok, net_devs_warn = ([], netdevices_in_net)
                        if len(net_devs_ok) == 1:
                            boot_netdev = net_devs_ok[0]
                            # finaly, we have the device, the boot netdevice, actual production net
                            self._generate_config_step2(cur_c, b_dev, act_prod_net, boot_netdev, dev_sc)
                        elif len(net_devs_ok) > 1:
                            cur_c.log("too many netdevices (%d) with IP in production network found" % (len(net_devs_ok)), logging_tools.LOG_LEVEL_ERROR, state="done")
                        elif len(net_devs_warn) == 1:
                            cur_c.log(" one netdevice with IP in production network found but not on bootnetdevice", logging_tools.LOG_LEVEL_ERROR, state="done")
                        else:
                            cur_c.log("too many netdevices (%d) with IP in production network found (not on bootnetdevice!)" % (len(net_devs_warn)), logging_tools.LOG_LEVEL_ERROR, state="done")
                    else:
                        cur_c.log("no IP-address in production network", logging_tools.LOG_LEVEL_ERROR, state="done")
        cur_c.log_kwargs("after build", only_new=False)
        # done (yeah ?)
        # send result
        e_time = time.time()
        if dev_sc:
            dev_sc.device.add_log(self.config_src, cached_log_status(int(cur_c.state_level)), "built config in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        cur_c.log("built took %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        if global_config["DEBUG"]:
            tot_query_count = len(connection.queries) - cur_query_count
            cur_c.log("queries issued: %d" % (tot_query_count))
            for q_idx, act_sql in enumerate(connection.queries[cur_query_count:], 1):
                cur_c.log(" %4d %s" % (q_idx, act_sql["sql"][:120]))
        # pprint.pprint(cur_c.get_send_dict())
        self.send_pool_message("client_update", cur_c.get_send_dict())
    def _generate_config_step2(self, cur_c, b_dev, act_prod_net, boot_netdev, dev_sc):
        self.router_obj.check_for_update()
        running_ip = [ip.ip for ip in dev_sc.identifier_ip_lut["p"] if dev_sc.ip_netdevice_lut[ip.ip].pk == boot_netdev.pk][0]
        full_postfix = act_prod_net.get_full_postfix()
        cur_c.log("IP in production network '%s' is %s, full network_postfix is '%s'" % (
            act_prod_net.identifier,
            running_ip,
            full_postfix))
        # multiple configs
        multiple_configs = ["server"]
        all_servers = config_tools.device_with_config("%server%")
        def_servers = all_servers.get("server", [])
        if not def_servers:
            cur_c.log("no Servers found", logging_tools.LOG_LEVEL_ERROR, state="done")
        else:
            srv_names = sorted(["%s%s" % (cur_srv.short_host_name, full_postfix) for cur_srv in def_servers])
            cur_c.log("%s found: %s" % (
                logging_tools.get_plural("server", len(def_servers)),
                ", ".join(srv_names)
            ))
            # store in act_prod_net
            conf_dict = {}
            conf_dict["servers"] = srv_names
            for server_type in sorted(all_servers.keys()):
                if server_type not in multiple_configs:
                    routing_info, act_server, routes_found = ([66666666], None, 0)
                    for actual_server in all_servers[server_type]:
                        act_routing_info = actual_server.get_route_to_other_device(self.router_obj, dev_sc, filter_ip=running_ip, allow_route_to_other_networks=True)
                        if act_routing_info:
                            routes_found += 1
                            # store in some dict-like structure
                            conf_dict["%s:%s" % (actual_server.short_host_name, server_type)] = "%s%s" % (actual_server.short_host_name, full_postfix)
                            conf_dict["%s:%s_ip" % (actual_server.short_host_name, server_type)] = act_routing_info[0][2][1][0]
                            if server_type in ["config_server", "mother_server"] and actual_server.device.pk == b_dev.bootserver_id:
                                routing_info, act_server = (act_routing_info[0], actual_server)
                            else:
                                if act_routing_info[0][0] < routing_info[0]:
                                    routing_info, act_server = (act_routing_info[0], actual_server)
                        else:
                            cur_c.log("empty routing info for %s to %s" % (
                                server_type,
                                actual_server.device.name), logging_tools.LOG_LEVEL_WARN)
                    if act_server:
                        server_ip = routing_info[2][1][0]
                        conf_dict[server_type] = "%s%s" % (act_server.short_host_name, full_postfix)
                        conf_dict["%s_ip" % (server_type)] = server_ip
                        cur_c.log("  %20s: %-25s (IP %15s)%s" % (
                            server_type,
                            conf_dict[server_type],
                            server_ip,
                            " (best of %d)" % (routes_found) if routes_found > 1 else ""))
                    else:
                        cur_c.log("  %20s: not found" % (server_type))
            new_img = b_dev.new_image
            if new_img:
                conf_dict["system"] = {
                    "vendor"  : new_img.sys_vendor,
                    "version" : new_img.sys_version,
                    "release" : new_img.sys_release,
                }
            else:
                self.log("no image defined, using defaults")
                conf_dict["system"] = {
                    "vendor"  : "suse",
                    "version" : 12,
                    "release" : 3,
                    }
            conf_dict["device"] = b_dev
            conf_dict["net"] = act_prod_net
            conf_dict["host"] = b_dev.name
            conf_dict["hostfq"] = b_dev.full_name
            conf_dict["device_idx"] = b_dev.pk
            # image is missing, FIXME
# #                    dc.execute("SELECT * FROM image WHERE image_idx=%s", (self["new_image"]))
# #                    if dc.rowcount:
# #                        act_prod_net["image"] = dc.fetchone()
# #                    else:
# #                        act_prod_net["image"] = {}
            config_pks = list(config.objects.filter(
                Q(device_config__device=b_dev) |
                (Q(device_config__device__device_group=b_dev.device_group_id) &
                 Q(device_config__device__device_type__identifier="MD"))). \
                              order_by("-priority", "name").distinct().values_list("pk", flat=True))
            parent_pks = []
            while True:
                new_pks = set(config.objects.exclude(parent_config=None).filter(Q(pk__in=config_pks + parent_pks)).values_list("parent_config", flat=True)) - set(config_pks + parent_pks)
                if new_pks:
                    parent_pks.extend(list(new_pks))
                else:
                    break
            pseudo_config_list = config.objects.all(). \
                prefetch_related("config_str_set", "config_int_set", "config_bool_set", "config_blob_set", "config_script_set"). \
                order_by("-priority", "name")
            config_dict = dict([(cur_pc.pk, cur_pc) for cur_pc in pseudo_config_list])
            # copy variables
            for p_config in pseudo_config_list:
                for var_type in ["str", "int", "bool", "blob"]:
                    for cur_var in getattr(p_config, "config_%s_set" % (var_type)).all():
                        conf_dict["%s.%s" % (p_config.name, cur_var.name)] = cur_var.value
            for cur_conf in pseudo_config_list:
                # cur_conf.show_variables(cur_c.log, detail=global_config["DEBUG"])
                pass
            cur_c.log("%s found: %s, %s found: %s" % (
                logging_tools.get_plural("config", len(config_pks)),
                ", ".join([config_dict[pk].name for pk in config_pks]) if config_pks else "no configs",
                logging_tools.get_plural("parent config", len(parent_pks)),
                ", ".join([config_dict[pk].name for pk in parent_pks]) if parent_pks else "no parent configs"))
            # extend with parent pks
            config_pks.extend(list(parent_pks))
            # node interfaces
            conf_dict["node_if"] = []
            taken_list, not_taken_list = ([], [])
            for cur_net in b_dev.netdevice_set.all().prefetch_related("net_ip_set", "net_ip_set__network", "net_ip_set__network__network_type", "net_ip_set__domain_tree_node"):
                for cur_ip in cur_net.net_ip_set.all():
                    # if cur_ip.network_id
                    if cur_ip.network_id in act_prod_net.idx_list:
                        take_it, cause = (True, "network_index in list")
                    elif cur_ip.network.network_type.identifier == "l":
                        take_it, cause = (True, "network_type is loopback")
                    else:
                        if cur_ip.domain_tree_node and cur_ip.domain_tree_node.always_create_ip:
                            take_it, cause = (True, "network_index not in list but always_create_ip set")
                        else:
                            take_it, cause = (False, "network_index not in list and always_create_ip not set")
                    if take_it:
                        conf_dict["node_if"].append(cur_ip)
                        taken_list.append((cur_ip, cause))
                    else:
                        not_taken_list.append((cur_ip, cause))
            cur_c.log("%s in taken_list" % (logging_tools.get_plural("Netdevice", len(taken_list))))
            for entry, cause in taken_list:
                cur_c.log("  - %-6s (IP %-15s, network %-20s) : %s" % (
                    entry.netdevice.devname,
                    entry.ip,
                    unicode(entry.network),
                    cause))
            cur_c.log("%s in not_taken_list" % (logging_tools.get_plural("Netdevice", len(not_taken_list))))
            for entry, cause in not_taken_list:
                cur_c.log("  - %-6s (IP %-15s, network %-20s) : %s" % (
                    entry.netdevice.devname,
                    entry.ip,
                    unicode(entry.network),
                    cause))
            # create config
            config_obj = internal_object("CONFIG_VARS")
            # config_obj.add_config("config_vars")
            config_obj += pretty_print("", conf_dict, 0)
            # dict: which configg was called (sucessfully)
            conf_dict["called"] = {}
            cur_c.conf_dict, cur_c.link_dict, cur_c.erase_dict = ({}, {}, {})
            cur_c.conf_dict[config_obj.dest] = config_obj
            new_tree = generated_tree()
            cur_bc = build_container(cur_c, config_dict, conf_dict, new_tree, self.router_obj)
            for pk in config_pks:
                cur_bc.process_scripts(pk)
            new_tree.write_config(cur_c, cur_bc)
            if False in conf_dict["called"]:
                cur_c.log("error in scripts for %s: %s" % (
                    logging_tools.get_plural("config", len(conf_dict["called"][False])),
                    ", ".join(sorted([unicode(config_dict[pk]) for pk, err_lines in conf_dict["called"][False]]))),
                          logging_tools.LOG_LEVEL_ERROR,
                          state="done")
                cur_c.add_set_keys("error_dict")
                cur_c.error_dict = dict([(unicode(config_dict[pk]), err_lines) for pk, err_lines in conf_dict["called"][False]])
            else:
                cur_c.log("config built", state="done")
            cur_bc.close()

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._re_insert_config()
        self._log_config()
        self.__msi_block = self._init_msi_block()
        self._init_subsys()
        self._init_network_sockets()
        self.add_process(build_process("build"), start=True)
        connection.close()
        self.register_func("client_update", self._client_update)
        self.register_func("complex_result", self._complex_result)
        self.__run_idx = 0
        self.__pending_commands = {}
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_subsys(self):
        self.log("init subsystems")
        config_control.init(self)
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _re_insert_config(self):
        cluster_location.write_config("config_server", global_config)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("cluster-config-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/cluster-config-server start"
            msi_block.stop_command = "/etc/init.d/cluster-config-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def loop_end(self):
        config_control.close_clients()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()
    def _init_network_sockets(self):
        my_0mq_id = uuid_tools.get_uuid().get_urn()
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PUB_PORT"] , self._new_com),
            ("pull"  , zmq.PULL  , global_config["SERVER_PULL_PORT"], self._new_com),
            ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, my_0mq_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.RCVHWM, 256)
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.core.error.ZMQError:
                self.log("error binding to %s{%d}: %s" % (
                    conn_str,
                    sock_type,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                client.close()
            else:
                self.log("bind to port %s{%d}" % (conn_str,
                                                  sock_type))
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client
    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            try:
                cur_com = srv_com["command"].text
            except:
                if srv_com.tree.find("nodeinfo") is not None:
                    node_text = srv_com.tree.findtext("nodeinfo")
                    src_id = data[0].split(":")[0]
                    if not config_control.has_client(src_id):
                        try:
                            new_dev = device.objects.get(Q(uuid=src_id) | Q(uuid__startswith=src_id[:-5]))
                        except device.DoesNotExist:
                            self.log("no device with UUID %s found in database" % (src_id),
                                     logging_tools.LOG_LEVEL_ERROR)
                            cur_c = None
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
                            zmq_sock.send_unicode("error unknown UUID")
                        else:
                            cur_c = config_control.add_client(new_dev)
                    else:
                        cur_c = config_control.get_client(src_id)
                    if cur_c is not None:
                        cur_c.handle_nodeinfo(data[0], node_text)
                else:
                    self.log("got command '%s' from %s, ignoring" % (etree.tostring(srv_com.tree), data[0]),
                             logging_tools.LOG_LEVEL_ERROR)
            else:
                srv_com.update_source()
                if cur_com == "register":
                    self._register_client(c_uid, srv_com)

                else:
                    if c_uid.endswith("webfrontend"):
                        # special command from webfrontend, FIXME
                        srv_com["command"].attrib["source"] = "external"
                        self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                    else:
                        try:
                            cur_client = None # client.get(c_uid)
                        except KeyError:
                            self.log("unknown uid %s, not known" % (c_uid),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                        else:
                            cur_client.new_command(srv_com)
        else:
            self.log("wrong number of data chunks (%d != 2), data is '%s'" % (len(data), data[:20]),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_wfe_command(self, zmq_sock, c_uid, srv_com):
        cur_com = srv_com["command"].text
        self.__run_idx += 1
        srv_com["command"].attrib["run_idx"] = "%d" % (self.__run_idx)
        srv_com["command"].attrib["uuid"] = c_uid
        self.__pending_commands[self.__run_idx] = srv_com
        # get device names
        device_list = device.objects.filter(Q(pk__in=[cur_dev.attrib["pk"] for cur_dev in srv_com["devices:devices"]]))
        self.log("got command %s for %s: %s" % (
            cur_com,
            logging_tools.get_plural("device", len(device_list)),
            ", ".join([unicode(cur_dev) for cur_dev in device_list])))
        dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device_list])
        # set device state
        for cur_dev in srv_com["devices:devices"]:
            cur_dev.attrib["internal_state"] = "pre_init"
            cur_dev.attrib["run_idx"] = "%d" % (self.__run_idx)
            cur_dev.text = unicode(dev_dict[int(cur_dev.attrib["pk"])])
            cur_dev.attrib["name"] = dev_dict[int(cur_dev.attrib["pk"])].name
        self._handle_command(self.__run_idx)
    def create_config(self, queue_id, s_req):
        # create a build_config request
        cur_com = server_command.srv_command(command="build_config")
        cur_com["devices"] = cur_com.builder(
            "devices",
            cur_com.builder("device", pk="%d" % (s_req.cc.device.pk))
        )
        cur_com["command"].attrib["source"] = "config_control"
        self._handle_wfe_command(None, str(queue_id), cur_com)
    def _handle_command(self, run_idx):
        cur_com = self.__pending_commands[run_idx]
        for cur_dev in cur_com["devices:devices"]:
            if cur_dev.attrib["internal_state"] == "pre_init":
                cur_dev.attrib["internal_state"] = "generate_config"
                self.send_to_process(
                    "build",
                    cur_dev.attrib["internal_state"],
                    dict(cur_dev.attrib),
                    )
        num_pending = len(cur_com.xpath(None, ".//ns:device[not(@internal_state='done')]"))
        if not num_pending:
            self.log("nothing pending, sending return")
            self._send_return(cur_com)
            del self.__pending_commands[run_idx]
    def _send_return(self, cur_com):
        if cur_com["command"].attrib["source"] == "external":
            self._send_simple_return(cur_com["command"].attrib["uuid"], unicode(cur_com))
        else:
            config_control.complex_result(int(cur_com["command"].attrib["uuid"]), unicode(cur_com))
    def _send_simple_return(self, zmq_id, send_str):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(zmq_id, zmq.SNDMORE)
        send_sock.send_unicode(unicode(send_str))
    def _client_update(self, *args, **kwargs):
        src_proc, src_id, upd_dict = args
        run_idx = upd_dict.get("run_idx", -1)
        if run_idx in self.__pending_commands:
            cur_com = self.__pending_commands[run_idx]
            cur_dev = cur_com.xpath(None, ".//ns:device[@name='%s']" % (upd_dict["name"]))[0]
            for key, value in upd_dict.iteritems():
                if key.endswith("_dict"):
                    new_dict = E.info_dict()
                    for s_key, s_value in value.iteritems():
                        # very hackish, fixme
                        new_dict.append(E.entry("\n".join(s_value), key=s_key))
                    cur_dev.append(new_dict)
                else:
                    if type(value) in [int, long]:
                        cur_dev.attrib[key] = "%d" % (value)
                    else:
                        cur_dev.attrib[key] = value
            self._handle_command(run_idx)
        else:
            self.log("got client_update with unknown run_idx %d" % (upd_dict["run_idx"]),
                     logging_tools.LOG_LEVEL_ERROR)
    def _complex_result(self, src_proc, src_id, queue_id, result, **kwargs):
        config_control.complex_result(queue_id, result)

class simple_request(object):
    def __init__(self, cc, zmq_id, node_text):
        self.cc = cc
        self.zmq_id = zmq_id
        if zmq_id.count(":") == 2:
            src_ip = zmq_id.split(":")[-1]
        else:
            src_ip = "0.0.0.0"
        self.src_ip = src_ip
        self.server_ip = "0.0.0.0"
        self.node_text = node_text
        self.command = node_text.strip().split()[0]
        self.data = " ".join(node_text.strip().split()[1:])
        self.server_ip = None
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.cc.log(what, log_level)
    def _find_best_server(self, conf_list):
        dev_sc = config_tools.server_check(
            short_host_name=self.cc.device.name,
            server_type="node",
            fetch_network_info=True)
        bs_list = []
        for cur_conf in conf_list:
            srv_routing = cur_conf.get_route_to_other_device(
                self.cc.router_obj,
                dev_sc,
                filter_ip=self.src_ip,
                allow_route_to_other_networks=False)
            if srv_routing:
                bs_list.append((srv_routing[0][0], cur_conf))
        if bs_list:
            return sorted(bs_list)[0][1]
        else:
            self.log("no result in find_best_server (%s)" % (logging_tools.get_plural("entry", len(conf_list))))
            return None
    def _get_config_str_vars(self, cs_name):
        config_pks = config.objects.filter(
            Q(device_config__device=self.cc.device) |
            (Q(device_config__device__device_group=self.cc.device.device_group_id) &
             Q(device_config__device__device_type__identifier="MD"))). \
            order_by("-priority", "name").distinct().values_list("pk", flat=True)
        c_vars = config_str.objects.filter(Q(config__in=config_pks) & Q(name=cs_name))
        ent_list = []
        for c_var in c_vars:
            for act_val in [part.strip() for part in c_var.value.strip().split() if part.strip()]:
                if act_val not in ent_list:
                    ent_list.append(act_val) #
        return ent_list
    def _get_valid_server_struct(self, s_list):
        # list of boot-related config names
        bsl_servers = set(["kernel_server", "image_server", "mother_server"])
        # list of server_types which has to be mapped to the mother-server
        map_to_mother = set(["kernel_server", "image_server"])
        for type_name in s_list:
            conf_list = config_tools.device_with_config(type_name).get(type_name, [])
            if conf_list:
                if type_name in bsl_servers:
                    # config name (from s_list) is in bsl_servers
                    valid_server_struct = None
                    for srv_found in conf_list:
                        # iterate over servers
                        if srv_found.device and srv_found.device.pk == self.cc.device.bootserver_id:
                            # found bootserver, match
                            valid_server_struct = srv_found
                            break
                else:
                    valid_server_struct = self._find_best_server(conf_list)
            else:
                # no config found
                valid_server_struct = None
            if valid_server_struct:
                # exit if srv_struct found
                break
        if valid_server_struct and type_name in map_to_mother:
            # remap to mother_server
            valid_server_struct = config_tools.server_check(
                server_type="mother_server",
                short_host_name=valid_server_struct.short_host_name,
                fetch_network_info=True)
        if valid_server_struct:
            dev_sc = config_tools.server_check(
                short_host_name=self.cc.device.name,
                server_type="node",
                fetch_network_info=True)
            # check if there is a route between us and server
            srv_routing = valid_server_struct.get_route_to_other_device(
                self.cc.router_obj,
                dev_sc,
                filter_ip=self.src_ip,
                allow_route_to_other_networks=False)
            if not srv_routing:
                self.log("found valid_server_struct %s but no route" % (
                    valid_server_struct.server_info_str),
                         logging_tools.LOG_LEVEL_ERROR)
                valid_server_struct = None
            else:
                self.server_ip = srv_routing[0][2][1][0]
                self.log("found valid_server_struct %s (device %s) with ip %s" % (
                    valid_server_struct.server_info_str,
                    unicode(valid_server_struct.device),
                    self.server_ip))
        else:
            self.log("no valid server_struct found (search list: %s)" % (", ".join(s_list)),
                     logging_tools.LOG_LEVEL_ERROR)
        return valid_server_struct
    def create_config_dir(self):
        # link to build client
        self.cc.complex_config_request(self, "create_config_dir")
    def get_partition(self):
        # link to build client
        self.cc.complex_config_request(self, "get_partition")
    def create_config_dir_result(self, result):
        if result:
            return "ok created config dir"
        else:
            return "error cannot create config dir"
    def get_partition_result(self, result):
        if result:
            return "ok created partition info"
        else:
            return "error cannot create partition info"
    def build_config_result(self, result):
        xml_result = server_command.srv_command(source=result)
        res_node = xml_result.xpath(None, ".//ns:device[@pk='%d']" % (self.cc.device.pk))[0]
        self.log("result node has %s:" % (logging_tools.get_plural("attribute", len(res_node.attrib))))
        for key, value in res_node.attrib.iteritems():
            self.log("   %-10s: %s" % (key, value))
        del self.cc.pending_config_requests[self.cc.device.name]
        self.cc.done_config_requests[self.cc.device.name] = "ok config built" if int(res_node.attrib["state_level"]) in [logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_WARN] else "error building config"

class config_control(object):
    """  struct to handle simple config requests """
    def __init__(self, cur_dev):
        self.__log_template = None
        self.device = cur_dev
        self.create_logger()
        config_control.router_obj.check_for_update()
        self.__com_dict = {
            "get_kernel"              : self._handle_get_kernel,
            "get_kernel_name"         : self._handle_get_kernel,
            "get_syslog_server"       : self._handle_get_syslog_server,
            "get_package_server"      : self._handle_get_package_server,
            "hello"                   : self._handle_hello,
            "get_init_mods"           : self._handle_get_init_mods,
            "locate_module"           : self._handle_locate_module,
            "get_target_sn"           : self._handle_get_target_sn,
            "get_partition"           : self._handle_get_partition,
            "get_image"               : self._handle_get_image,
            "create_config"           : self._handle_create_config,
            "ack_config"              : self._handle_ack_config,
            "get_add_group"           : self._handle_get_add_group,
            "get_add_user"            : self._handle_get_add_user,
            "get_del_group"           : self._handle_get_del_group,
            "get_del_user"            : self._handle_get_del_user,
            "get_start_scripts"       : self._handle_get_start_scripts,
            "get_stop_scripts"        : self._handle_get_stop_scripts,
            "get_root_passwd"         : self._handle_get_root_passwd,
            "get_additional_packages" : self._handle_get_additional_packages,
            "set_kernel"              : self._handle_set_kernel,
            "modify_bootloader"       : self._handle_modify_bootloader,
        }
    def refresh(self):
        self.device = device.objects.get(Q(pk=self.device.pk))
    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           self.device.name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=config_control.srv_process.zmq_context,
                init_logger=True)
            self.log("added client")
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def complex_config_request(self, s_req, req_name):
        self.log("routing config_request '%s'" % (req_name))
        q_id = config_control.queue(self, s_req, req_name)
        config_control.srv_process.send_to_process(
            "build",
            "complex_request",
            q_id,
            self.device.name,
            req_name,
            s_req.data)
    def complex_config_result(self, s_req, req_name, result):
        ret_str = getattr(s_req, "%s_result" % (req_name))(result)
        if ret_str is not None:
            self.log("handled delayed '%s' (src_ip %s), returning %s" % (
                s_req.node_text,
                s_req.src_ip,
                ret_str))
            config_control.srv_process._send_simple_return(s_req.zmq_id, ret_str)
        else:
            self.log("got result for delayed '%s' (src_ip %s)" % (
                s_req.node_text,
                s_req.src_ip))
        del s_req
    def handle_nodeinfo(self, src_id, node_text):
        s_time = time.time()
        s_req = simple_request(self, src_id, node_text)
        com_call = self.__com_dict.get(s_req.command, None)
        if com_call:
            ret_str = com_call(s_req)
        else:
            ret_str = "error unknown command '%s'" % (node_text)
        if ret_str is None:
            self.log("waiting for answer")
        else:
            e_time = time.time()
            self.log("handled nodeinfo '%s' (src_ip %s) in %s, returning %s" % (
                s_req.node_text,
                s_req.src_ip,
                logging_tools.get_diff_time_str(e_time - s_time),
                ret_str))
            config_control.srv_process._send_simple_return(s_req.zmq_id, ret_str)
            del s_req
    # command snippets
    def _handle_get_add_user(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("ADD_USER")))
    def _handle_get_add_group(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("ADD_GROUP")))
    def _handle_get_del_user(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("DEL_USER")))
    def _handle_get_del_group(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("DEL_GROUP")))
    def _handle_get_start_scripts(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("START_SCRIPTS")))
    def _handle_get_stop_scripts(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("STOP_SCRIPTS")))
    def _handle_get_root_passwd(self, s_req):
        # not very save, FIXME
        return "ok %s" % (self.device.root_passwd.strip() or crypt.crypt("init4u", process_tools.get_machine_name()))
    def _handle_get_additional_packages(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("ADDITIONAL_PACKAGES")))
    def _handle_ack_config(self, s_req):
        if self.device.name in config_control.done_config_requests:
            ret_str = config_control.done_config_requests[self.device.name]
            del config_control.done_config_requests[self.device.name]
            return ret_str
        if not self.device.name in config_control.pending_config_requests:
            self.log("strange, got ack but not in done nor pending list", logging_tools.LOG_LEVEL_ERROR)
            self._handle_create_config(s_req)
            return "warn waiting for config"
        else:
            return "warn waiting for config"
    def _handle_create_config(self, s_req):
        if self.device.name in config_control.pending_config_requests:
            return "warn already in pending list"
        elif self.device.name in config_control.done_config_requests:
            return "ok config already built"
        else:
            config_control.pending_config_requests[self.device.name] = True
            q_id = config_control.queue(self, s_req, "build_config")
            config_control.srv_process.create_config(q_id, s_req)
            return "ok started building config"
    def _handle_modify_bootloader(self, s_req):
        return "ok %s" % ("yes" if self.device.act_partition_table.modify_bootloader else "no")
    def _handle_get_image(self, s_req):
        cur_img = self.device.new_image
        if not cur_img:
            return "error no image set"
        else:
            if cur_img.build_lock:
                return "error image is locked"
            else:
                vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "image_server"])
                if vs_struct:
                    if vs_struct.config_name.startswith("mother"):
                        # is mother_server
                        dir_key = "TFTP_DIR"
                    else:
                        # is tftpboot_export
                        dir_key = "EXPORT"
                    vs_struct.fetch_config_vars()
                    if vs_struct.has_key(dir_key):
                        return "ok %s %s %s %s %s" % (
                            s_req.server_ip,
                            os.path.join(vs_struct[dir_key], "images", cur_img.name),
                            cur_img.version,
                            cur_img.release,
                            cur_img.builds)
                    else:
                        return "error key %s not found" % (dir_key)
                else:
                    return "error resolving server"
    def _handle_get_target_sn(self, s_req):
        # get prod_net info
        prod_net = self.device.prod_link
        if not prod_net:
            self.log("no prod_link set", logging_tools.LOG_LEVEL_ERROR)
        vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "mother_server"])
        if vs_struct:
            # routing ok, get export directory
            if vs_struct.config_name.startswith("mother"):
                # is mother_server
                dir_key = "TFTP_DIR"
            else:
                # is tftpboot_export
                dir_key = "EXPORT"
            vs_struct.fetch_config_vars()
            if vs_struct.has_key(dir_key):
                kernel_source_path = "%s/kernels/" % (vs_struct[dir_key])
                return "ok %s %s %d %d %s %s %s" % (
                    self.device.new_state.status,
                    prod_net.identifier,
                    self.device.rsync,
                    self.device.rsync_compressed,
                    self.device.name,
                    s_req.server_ip,
                    "%s/%s" % (vs_struct[dir_key], "config"))
            else:
                return "error key %s not found" % (dir_key)
        else:
            return "error resolving server"
    def _handle_locate_module(self, s_req):
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            kernel_name = dev_kernel.name
            # build module dict
            # mod_dict = dict([(key, None) for key in [key.endswith(".ko") and key[:-3] or (key.endswith(".o") and key[:-2] or key) for key in s_req.data]])
            kernel_dir = os.path.join(global_config["TFTP_DIR"],
                                      "kernels",
                                      kernel_name)
            dep_h = module_dependency_tools.dependency_handler(kernel_dir, log_com=self.log)
            dep_h.resolve(s_req.data.split(), firmware=False, resolve_module_dict=True)
            for key, value in dep_h.module_dict.iteritems():
                self.log("kmod mapping: %20s -> %s" % (key, value))
            for value in dep_h.auto_modules:
                self.log("dependencies: %20s    %s" % ("", value))
            # walk the kernel dir
            # mod_list = ["%s.o" % (key) for key in mod_dict.keys()] + ["%s.ko" % (key) for key in mod_dict.keys()]
            return "ok %s" % (" ".join([mod_name[len(global_config["TFTP_DIR"]) : ] for mod_name in dep_h.module_dict.itervalues()]))
        else:
            return "error no kernel set"
    def _handle_get_init_mods(self, s_req):
        db_mod_list = s_req._get_config_str_vars("INIT_MODS")
        return "ok %s" % (" ".join(db_mod_list))
        # add modules which depends to the used partition type
        # not implemented, FIXME
        # dc.execute("SELECT DISTINCT ps.name FROM partition_table pt INNER JOIN device d LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx LEFT JOIN partition_fs ps ON ps.partition_fs_idx=p.partition_fs WHERE d.device_idx=%s AND d.partition_table=pt.partition_table_idx AND ps.identifier='f'", c_req["device_idx"])
        # db_mod_list.extend([db_rec["name"] for db_rec in dc.fetchall() if db_rec["name"] and db_rec["name"] not in db_mod_list])
    def _handle_hello(self, s_req):
        return s_req.create_config_dir()
    def _handle_get_partition(self, s_req):
        return s_req.get_partition()
    def _handle_get_syslog_server(self, s_req):
        vs_struct = s_req._get_valid_server_struct(["syslog_server"])
        if vs_struct:
            return "ok %s" % (s_req.server_ip)
        else:
            return "error no syslog-server defined"
    def _handle_get_package_server(self, s_req):
        vs_struct = s_req._get_valid_server_struct(["package_server"])
        if vs_struct:
            return "ok %s" % (s_req.server_ip)
        else:
            return "error no package-server defined"
    def _handle_get_kernel(self, s_req):
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "kernel_server"])
            if not vs_struct:
                return "error no server found"
            else:
                vs_struct.fetch_config_vars()
                if vs_struct.config_name.startswith("mother"):
                    # is mother_server
                    dir_key = "TFTP_DIR"
                else:
                    # is tftpboot_export
                    dir_key = "EXPORT"
                if vs_struct.has_key(dir_key):
                    kernel_source_path = os.path.join(vs_struct[dir_key], "kernels")
                    if s_req.command == "get_kernel":
                        return "ok NEW %s %s/%s" % (
                            s_req.server_ip,
                            kernel_source_path,
                            dev_kernel.name)
                    else:
                        return "ok NEW %s %s" % (
                            s_req.server_ip,
                            dev_kernel.name)
                else:
                    return "error key %s not found" % (dir_key)
        else:
            return "error no kernel set"
    def _handle_set_kernel(self, s_req):
        # maybe we can do something better here
        return "ok got it but better fixme :-)"
    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()
    @staticmethod
    def close_clients():
        for cur_c in config_control.__cc_dict.itervalues():
            cur_c.close()
    @staticmethod
    def init(srv_process):
        config_control.srv_process = srv_process
        config_control.cc_log("init config_control")
        config_control.__cc_dict = {}
        config_control.__lut_dict = {}
        config_control.__queue_dict = {}
        config_control.__queue_num = 0
        config_control.pending_config_requests = {}
        config_control.done_config_requests = {}
        config_control.router_obj = config_tools.router_object(config_control.cc_log)
    @staticmethod
    def queue(cc_obj, s_req, req_name):
        config_control.__queue_num += 1
        config_control.__queue_dict[config_control.__queue_num] = (cc_obj, s_req, req_name)
        return config_control.__queue_num
    @staticmethod
    def complex_result(queue_id, result):
        cc_obj, s_req, req_name = config_control.__queue_dict[queue_id]
        del config_control.__queue_dict[queue_id]
        cc_obj.complex_config_result(s_req, req_name, result)
    @staticmethod
    def cc_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        config_control.srv_process.log("[cc] %s" % (what), log_level)
    @staticmethod
    def has_client(search_spec):
        return search_spec in config_control.__lut_dict
    @staticmethod
    def get_client(search_spec):
        loc_cc = config_control.__lut_dict.get(search_spec, None)
        loc_cc.refresh()
        return loc_cc
    @staticmethod
    def add_client(new_dev):
        if new_dev.name not in config_control.__cc_dict:
            new_c = config_control(new_dev)
            config_control.__cc_dict[new_dev.name] = new_c
            for key in ["pk", "name", "uuid"]:
                config_control.__lut_dict[getattr(new_dev, key)] = new_c
            config_control.cc_log("added client %s" % (unicode(new_dev)))
        else:
            config_control.__cc_dict[new_dev.name].refresh()
        return config_control.__cc_dict[new_dev.name]

class build_client(object):
    """ holds all the necessary data for a complex config request """
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.pk = int(kwargs.get("pk", device.objects.values("pk").get(Q(name=self.name))["pk"]))
        self.create_logger()
        self.set_keys, self.logged_keys = ([], [])
    def cleanup(self):
        self.clean_old_kwargs()
        self.clean_errors()
    def clean_old_kwargs(self):
        for del_kw in self.set_keys:
            if del_kw not in ["name", "pk"]:
                delattr(self, del_kw)
        self.set_keys = [key for key in self.set_keys if key in ["name", "pk"]]
        self.logged_keys = []
    def clean_errors(self):
        self.__error_dict = {}
    def set_kwargs(self, **kwargs):
        new_keys = [key for key in kwargs.keys() if key not in ["name", "pk"]]
        self.set_keys = sorted(self.set_keys + new_keys)
        for key in new_keys:
            setattr(self, key, kwargs[key])
        for force_int in ["pk", "run_idx"]:
            if hasattr(self, force_int):
                setattr(self, force_int, int(getattr(self, force_int)))
        self.log_kwargs(only_new=True)
    def log_kwargs(self, info_str="", only_new=True):
        if only_new:
            log_keys = [key for key in self.set_keys if key not in self.logged_keys]
        else:
            log_keys = self.set_keys
        if len(self.set_keys):
            self.log("%s defined, %d new%s:" % (
                logging_tools.get_plural("attribute", len(self.set_keys)),
                len(log_keys),
                ", %s" % (info_str) if info_str else ""))
        for key in sorted(log_keys):
            self.log(" %-24s : %s" % (key, getattr(self, key)))
        self.logged_keys = self.set_keys
    def add_set_keys(self, *keys):
        self.set_keys = list(set(self.set_keys) | set(keys))
    def get_send_dict(self):
        return dict([(key, getattr(self, key)) for key in self.set_keys + ["name", "pk"]])
    def create_logger(self):
        self.__log_template = logging_tools.get_logger(
            "%s.%s" % (global_config["LOG_NAME"],
                       self.name.replace(".", r"\.")),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=build_client.srv_process.zmq_context,
            init_logger=True)
        self.log("added client (%s [%d])" % (self.name, self.pk))
    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK, **kwargs):
        self.__log_template.log(level, what)
        if "state" in kwargs:
            self.add_set_keys("info_str", "state_level")
            self.internal_state = kwargs["state"]
            self.info_str = what
            self.state_level = "%d" % (level)
        if kwargs.get("register", False):
            self.__error_dict.setdefault(level, []).append(what)
    @staticmethod
    def bc_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        build_client.srv_process.log("[bc] %s" % (what), log_level)
    @staticmethod
    def init(srv_process):
        build_client.__bc_dict = {}
        build_client.srv_process = srv_process
        build_client.bc_log("init build_client")
    @staticmethod
    def close_clients():
        for cur_c in build_client.__bc_dict.itervalues():
            cur_c.close()
    @staticmethod
    def get_client(**kwargs):
        name = kwargs["name"]
        if name not in build_client.__bc_dict:
            new_c = build_client(**kwargs)
            build_client.__bc_dict[name] = new_c
            build_client.bc_log("added client %s" % (name))
        else:
            new_c = build_client.__bc_dict[name]
        new_c.cleanup()
        new_c.set_kwargs(**kwargs)
        return new_c
    # config-related calls
    def get_partition(self, *args):
        part_name = args[0]
        loc_tree = generated_tree()
        loc_dev = device.objects.get(Q(pk=self.pk))
        self.log("set act_partition_table and partdev to %s" % (part_name))
        loc_dev.act_partition_table = loc_dev.partition_table
        loc_dev.partdev = part_name
        loc_dev.save()
        success = False
        dummy_cont = build_container(self, {}, {"device" : loc_dev}, loc_tree, None)
        try:
            loc_ps = partition_setup(dummy_cont)
        except:
            self.log("cannot generate partition info: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            base_dir = os.path.join(global_config["CONFIG_DIR"], loc_dev.name)
            pinfo_dir = os.path.join(base_dir, "pinfo")
            if not os.path.isdir(pinfo_dir):
                try:
                    os.mkdir(pinfo_dir)
                except OSError:
                    self.log("cannot create pinfo_directory %s: %s" % (pinfo_dir,
                                                                       process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
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
                loc_ps.create_part_files(pinfo_dir)
                success = True
        return success
    def create_config_dir(self, *args):
        base_dir = global_config["CONFIG_DIR"]
        # FIXME
        self.__source_host = self.name
        node_dir, node_link = (
            os.path.join(base_dir, self.__source_host),
            os.path.join(base_dir, self.name))
        self.set_kwargs(node_dir=node_dir)
        self.node_dir = node_dir
        success = True
        if not os.path.isdir(node_dir):
            try:
                os.mkdir(node_dir)
            except OSError:
                self.log("cannot create config_directory %s: %s" % (node_dir,
                                                                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                success = False
            else:
                self.log("created config directory %s" % (node_dir))
        if os.path.isdir(node_dir):
            if os.path.islink(node_link):
                if os.readlink(node_dir) != self.__source_host:
                    try:
                        os.unlink(node_link)
                    except:
                        self.log("cannot delete wrong link %s: %s" % (node_link,
                                                                      process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        success = False
                    else:
                        self.log("Removed wrong link %s" % (node_link))
            if not os.path.islink(node_link) and node_link != node_dir:
                try:
                    os.symlink(self.__source_host, node_link)
                except:
                    self.log("cannot create link from %s to %s: %s" % (node_link,
                                                                       self.__source_host,
                                                                       process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    success = False
                else:
                    self.log("Created link from %s to %s" % (node_link,
                                                             self.__source_host))
        return success
    def clean_directory(self, prod_key):
        # cleans directory of network_key
        rem_file_list, rem_dir_list = ([], [])
        dir_list = ["%s/configdir_%s" % (self.node_dir, prod_key),
                    "%s/config_dir_%s" % (self.node_dir, prod_key),
                    "%s/content_%s" % (self.node_dir, prod_key)]
        file_list = ["%s/config_files_%s" % (self.node_dir, prod_key),
                     "%s/config_dirs_%s" % (self.node_dir, prod_key),
                     "%s/config_links_%s" % (self.node_dir, prod_key),
                     "%s/config_delete_%s" % (self.node_dir, prod_key),
                     "%s/config_%s" % (self.node_dir, prod_key),
                     "%s/configl_%s" % (self.node_dir, prod_key),
                     "%s/config_d%s" % (self.node_dir, prod_key)]
        for old_name in dir_list:
            if os.path.isdir(old_name):
                rem_file_list.extend(["%s/%s" % (old_name, file_name) for file_name in os.listdir(old_name)])
                rem_dir_list.append(old_name)
        for old_name in file_list:
            if os.path.isfile(old_name):
                rem_file_list.append(old_name)
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
            self.log("removed %s for key '%s'" % (
                " and ".join([logging_tools.get_plural(key, value) for key, value in num_removed.iteritems()]),
                prod_key))
        else:
            self.log("config on disk for key '%s' was empty" % (prod_key))

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("USER"                , configfile.str_c_var("idccs", help_string="user to run as [%(default)s]")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var(["idg"])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"     , configfile.int_c_var(SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"    , configfile.int_c_var(SERVER_PULL_PORT, help_string="server pull port [%(default)d]")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="config_server")
    if not sql_info.effective_device:
        print "not a config_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "config_server", [
        ("TFTP_DIR"                  , configfile.str_c_var("/tftpboot")),
        ("MONITORING_PORT"           , configfile.int_c_var(NCS_PORT)),
        ("LOCALHOST_IS_EXCLUSIVE"    , configfile.bool_c_var(True)),
        ("HOST_CACHE_TIME"           , configfile.int_c_var(10 * 60)),
        ("WRITE_REDHAT_HWADDR_ENTRY" , configfile.bool_c_var(True)),
        ("ADD_NETDEVICE_LINKS"       , configfile.bool_c_var(False)),
    ])
    global_config.add_config_entries([
        ("CONFIG_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "config"))),
        ("IMAGE_DIR"  , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "images"))),
        ("KERNEL_DIR" , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "kernels")))])
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("config-server", "Cluster ConfigServer", device=sql_info.effective_device).pk))])
# #    loc_config["SERVER_IDX"] = sql_info.server_device_idx
# #    log_lines = []
# #    loc_config["LOG_SOURCE_IDX"] = process_tools.create_log_source_entry(dc, sql_info.server_device_idx, "config_server", "Cluster config Server")
# #    nagios_master_list = config_tools.device_with_config("nagios_master", dc)
# #    if nagios_master_list.keys():
# #        nagios_master_name = nagios_master_list.keys()[0]
# #        nagios_master = nagios_master_list[nagios_master_name]
# #        # good stuff :-)
# #        for routing_info in sql_info.get_route_to_other_device(dc, nagios_master):
# #            if routing_info[1] in ["l", "p", "o"]:
# #                loc_config["NAGIOS_IP"] = routing_info[3][1][0]
# #                break
# #    if loc_config["FIXIT"]:
# #        process_tools.fix_directories(loc_config["USER_NAME"], loc_config["GROUP_NAME"], [glob_config["LOG_DIR"], "/var/run/cluster-config-server", glob_config["CONFIG_DIR"]])
# #        process_tools.fix_files(loc_config["USER_NAME"], loc_config["GROUP_NAME"], ["/var/log/cluster-config-server.out", "/tmp/cluster-config-server.out"])
# #    dc.release()
    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/cluster-config-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "cluster-config-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging cluster-config-server on %s" % (long_host_name)
    ret_code = server_process().loop()
    sys.exit(ret_code)

if __name__ == "__main__":
    main()

