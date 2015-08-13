# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" cluster-config-server, tree creation """

import base64
import os
import sys
import time

from django.db.models import Q
from initat.cluster.backbone.models import wc_files, tree_node
from initat.cluster_config_server.base_objects import new_config_object, dir_object, copy_object, \
    link_object, delete_object, file_object
from initat.cluster_config_server.generators import do_fstab, do_nets, do_routes, do_ssh, do_uuid, \
    do_etc_hosts, do_hosts_equiv, do_uuid_old
from initat.cluster_config_server.partition_setup import partition_setup
from initat.tools import logging_tools
from initat.tools import process_tools


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
            # intermediate, can be overwritten
            self.content_node = new_config_object(self.path, "?", mode="0755")
            self.content_node_valid = False
        else:
            self.content_node = c_node
            self.content_node_valid = True

    def add_config(self, c_pk):
        self.used_config_pks.add(c_pk)

    def get_path(self):
        if self.parent:
            return os.path.join(self.parent.get_path(), self.path)
        else:
            return self.path

    def get_node(self, path, c_node, dir_node=False, use_existing=False, overwrite_existing=False):
        if self.root_node:
            # normalize path at top level
            path = os.path.normpath(path)
        if path == self.path:
            # found
            if self.is_dir == dir_node:
                if self.content_node_valid:
                    if self.content_node != c_node:
                        if not use_existing and not overwrite_existing:
                            raise ValueError(
                                "content node '{}' already set, missing append=True or overwrite=True (a={} / o={}) ?".format(
                                    path,
                                    str(use_existing),
                                    str(overwrite_existing),
                                )
                            )
                        if overwrite_existing:
                            self.content_node.content = []
                else:
                    self.content_node = c_node
                # match, return myself
                if self.content_node.c_type == "l":
                    self.is_link = True
                self.intermediate = False
                return self
            else:
                raise ValueError(
                    "request node ({}, {}) is a {}".format(
                        path,
                        "dir" if dir_node else "file",
                        "dir" if self.is_dir else "file"
                    )
                )
        else:
            path_list = path.split(os.path.sep)
            if path_list[0] != self.path:
                raise KeyError("path mismatch: {} != {}".format(path_list[0], self.path))
            if path_list[1] not in self.childs:
                if len(path_list) == 2 and not dir_node:
                    # add content node (final node)
                    self.childs[path_list[1]] = tree_node_g(path_list[1], c_node, parent=self, is_dir=False)
                else:
                    # add (intermediate) dir node
                    self.childs[path_list[1]] = tree_node_g(path_list[1], None, parent=self, intermediate=True)
            return self.childs[path_list[1]].get_node(
                os.path.join(*path_list[1:]),
                c_node,
                dir_node=dir_node,
                use_existing=use_existing,
                overwrite_existing=overwrite_existing,
            )

    def get_type_str(self):
        return "dir" if self.is_dir else ("link" if self.is_link else "file")

    def __unicode__(self):
        sep_str = "  " * self.nest_level
        ret_f = [
            "%s%s%s (%s) %s%s    :: %d/%d/%o" % (
                "[I]" if self.intermediate else "   ",
                "[E]" if self.error_flag else "   ",
                sep_str,
                self.get_type_str(),
                "{} -> {}".format(
                    self.path,
                    self.content_node.source
                ) if self.is_link else self.path,
                "/" if self.is_dir else "",
                self.content_node.uid,
                self.content_node.gid,
                self.content_node.mode
            )
        ]
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
        # print "wn", self.path, "**", "".join(self.content_node.content)
        _c = "".join(self.content_node.content)
        if self.content_node.binary:
            _c = base64.b64encode(_c)
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
            binary=self.content_node.binary,
            content=_c
        )
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
        active_identifier = cur_bc.conf_dict["net"].identifier.replace(" ", "_")
        cur_c.log(
            "writing config files for {} to {}".format(
                active_identifier,
                cur_c.node_dir
            )
        )
        config_dir = os.path.join(cur_c.node_dir, "content_{}".format(active_identifier))
        if not os.path.isdir(config_dir):
            cur_c.log("creating directory {}".format(config_dir))
            os.mkdir(config_dir)
        config_dict = {
            "f": os.path.join(cur_c.node_dir, "config_files_{}".format(active_identifier)),
            "l": os.path.join(cur_c.node_dir, "config_links_{}".format(active_identifier)),
            "d": os.path.join(cur_c.node_dir, "config_dirs_{}".format(active_identifier)),
            "e": os.path.join(cur_c.node_dir, "config_delete_{}".format(active_identifier)),
        }
        _line_dict = {}
        num_dict = dict([(key, 0) for key in config_dict.iterkeys()])
        for cur_tn, cur_wc in write_list:
            if cur_wc.dest_type not in ["i", "?"] and not cur_tn.intermediate:
                eff_type = cur_tn.node.content_node.get_effective_type()
                _lines = _line_dict.setdefault(eff_type, [])
                num_dict[eff_type] += 1
                out_name = os.path.join(config_dir, "{:d}".format(num_dict[eff_type]))
                try:
                    add_line = cur_tn.node.content_node.write_object(out_name)
                except:
                    cur_c.log(
                        "error creating node {}: {}".format(
                            cur_tn.node.content_node.dest,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                else:
                    _lines.append("{:d} {}".format(num_dict[eff_type], add_line))
        for _key, _lines in _line_dict.iteritems():
            file(config_dict[_key], "w").write("\n".join(_lines + [""]))
        cur_c.log("wrote {}".format(logging_tools.get_plural("file", len(_line_dict))))
        # print cur_c.node_dir, dir(cur_c)
        # print cur_bc.conf_dict["net"]
        # pprint.pprint(cur_bc.conf_dict)
        cur_c.log("wrote {}".format(logging_tools.get_plural("node", nodes_written)))


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
        self.b_client.log("[bc] {}".format(what), level, **kwargs)

    def close(self):
        self.log("done in {}".format(logging_tools.get_diff_time_str(time.time() - self.__s_time)))
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
        return getattr(
            self,
            "_add_{}_object".format(
                {
                    "l": "link",
                    "e": "delete",
                    "f": "file",
                    "c": "copy",
                    "d": "dir"
                }[new_obj.c_type]
            )
        )(new_obj)

    def add_copy_object(self, fon, source, **kwargs):
        return self._add_copy_object(copy_object(fon, config=self, source=source, **kwargs))

    def _add_copy_object(self, c_obj):
        cur_node = self.g_tree.get_node(c_obj.dest, c_obj)
        if cur_node not in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        return cur_node.content_node

    def add_file_object(self, fon, **kwargs):
        return self._add_file_object(
            file_object(fon, config=self, **kwargs),
            append=kwargs.get("append", False),
            overwrite=kwargs.get("overwrite", False),
        )

    def _add_file_object(self, f_obj, append=False, overwrite=False):
        cur_node = self.g_tree.get_node(f_obj.dest, f_obj, use_existing=append, overwrite_existing=overwrite)
        if cur_node not in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        f_obj.set_config(self)
        return cur_node.content_node

    def add_dir_object(self, don, **kwargs):
        return self._add_dir_object(dir_object(don, config=self, **kwargs))

    def _add_dir_object(self, d_obj):
        cur_node = self.g_tree.get_node(d_obj.dest, d_obj, dir_node=True)
        if cur_node not in self.__touched_objects:
            self.__touched_objects.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        d_obj.set_config(self)
        return cur_node.content_node

    def add_delete_object(self, don, **kwargs):
        return self._add_delete_object(delete_object(don, config=self, **kwargs))

    def _add_delete_object(self, d_obj):
        cur_node = self.g_tree.get_node(d_obj.dest, d_obj)
        if cur_node not in self.__deleted_files:
            self.__deleted_files.append(cur_node)
        cur_node.add_config(self.cur_conf.pk)
        return None

    def add_link_object(self, fon, source, **kwargs):
        return self._add_link_object(link_object(fon, config=self, source=source, **kwargs))

    def _add_link_object(self, l_obj):
        cur_node = self.g_tree.get_node(l_obj.dest, l_obj)
        if cur_node not in self.__touched_links:
            self.__touched_links.append(cur_node)
        l_obj.set_config(self)
        cur_node.add_config(self.cur_conf.pk)
        return cur_node.content_node

    def process_scripts(self, conf_pk):
        cur_conf = self.config_dict[conf_pk]
        self.cur_conf = cur_conf
        # build local variables
        local_vars = dict(
            sum(
                [
                    [
                        (
                            cur_var.name, cur_var.value
                        ) for cur_var in getattr(cur_conf, "config_{}_set".format(var_type)).all()
                    ] for var_type in ["str", "int", "bool", "blob"]
                ],
                []
            )
        )
        # copy local vars
        conf_dict = self.conf_dict
        for key, value in local_vars.iteritems():
            conf_dict[key] = value
        self.log(
            "config {}: {} defined, {} enabled, {}".format(
                cur_conf.name,
                logging_tools.get_plural("script", len(cur_conf.config_script_set.all())),
                logging_tools.get_plural("script", len([cur_scr for cur_scr in cur_conf.config_script_set.all() if cur_scr.enabled])),
                logging_tools.get_plural("local variable", len(local_vars.keys()))
            )
        )
        for cur_script in [cur_scr for cur_scr in cur_conf.config_script_set.all() if cur_scr.enabled]:
            self.init_uid_gid()
            lines = cur_script.value.split("\n")
            self.log(
                " - scriptname '{}' (pri {:d}) has {}".format(
                    cur_script.name,
                    cur_script.priority,
                    logging_tools.get_plural("line", len(lines))
                )
            )
            start_c_time = time.time()
            try:
                code_obj = compile(
                    cur_script.value.replace("\r\n", "\n") + "\n",
                    "<script {}>".format(cur_script.name),
                    "exec"
                )
            except:
                exc_info = process_tools.exception_info()
                self.log(
                    "error during compile of {} ({})".format(
                        cur_script.name,
                        logging_tools.get_diff_time_str(time.time() - start_c_time)
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                    register=True
                )
                for line in exc_info.log_lines:
                    self.log("   *** {}".format(line), logging_tools.LOG_LEVEL_ERROR)
                conf_dict["called"].setdefault(False, []).append((cur_conf.pk, [line for line in exc_info.log_lines]))
            else:
                compile_time = time.time() - start_c_time
                # prepare stdout / stderr
                start_time = time.time()
                stdout_c, stderr_c = (logging_tools.dummy_ios(), logging_tools.dummy_ios())
                old_stdout, old_stderr = (sys.stdout, sys.stderr)
                sys.stdout, sys.stderr = (stdout_c, stderr_c)
                self.__touched_objects, self.__touched_links, self.__deleted_files = ([], [], [])
                try:
                    ret_code = eval(
                        code_obj,
                        {},
                        {
                            # old version
                            "dev_dict": conf_dict,
                            # new version
                            "conf_dict": conf_dict,
                            "router_obj": self.router_obj,
                            "config": self,
                            "dir_object": dir_object,
                            "delete_object": delete_object,
                            "copy_object": copy_object,
                            "link_object": link_object,
                            "file_object": file_object,
                            "do_ssh": do_ssh,
                            "do_etc_hosts": do_etc_hosts,
                            "do_hosts_equiv": do_hosts_equiv,
                            "do_nets": do_nets,
                            "do_routes": do_routes,
                            "do_fstab": do_fstab,
                            "do_uuid": do_uuid,
                            "do_uuid_old": do_uuid_old,
                            "partition_setup": partition_setup,
                        }
                    )
                except:
                    exc_info = process_tools.exception_info()
                    conf_dict["called"].setdefault(False, []).append((cur_conf.pk, [line for line in exc_info.log_lines]))
                    self.log(
                        "An Error occured during eval() after {}:".format(logging_tools.get_diff_time_str(time.time() - start_time)),
                        logging_tools.LOG_LEVEL_ERROR,
                        register=True
                    )
                    for line in exc_info.log_lines:
                        self.log(" *** {}".format(line), logging_tools.LOG_LEVEL_ERROR)
                    # log stdout / stderr
                    self._show_logs(stdout_c, stderr_c)
                    # create error-entry, preferable not direct in config :-)
                    # FIXME
                    # remove objects
                    if self.__touched_objects:
                        self.log(
                            "{} touched : {}".format(
                                logging_tools.get_plural("object", len(self.__touched_objects)),
                                ", ".join([cur_obj.get_path() for cur_obj in self.__touched_objects])
                            )
                        )
                        for to in self.__touched_objects:
                            to.error_flag = True
                    else:
                        self.log("no objects touched")
                    if self.__touched_links:
                        self.log(
                            "{} touched: {}".format(
                                logging_tools.get_plural("link", len(self.__touched_links)),
                                ", ".join([cur_link.get_path() for cur_link in self.__touched_links])
                            )
                        )
                        for tl in self.__touched_links:
                            tl.error_flag = True
                    else:
                        self.log("no links touched")
                    if self.__deleted_files:
                        self.log(
                            "{} deleted: {}".format(
                                logging_tools.get_plural("delete", len(self.__deleted_files)),
                                ", ".join([cur_dl.get_path() for cur_dl in self.__deleted_files])
                            )
                        )
                        for d_file in self.__deleted_files:
                            d_file.error_flag = True
                    else:
                        self.log("no objects deleted")
                else:
                    conf_dict["called"].setdefault(True, []).append(cur_conf.pk)
                    if ret_code is None:
                        ret_code = 0
                    self.log(
                        "  exited after {} ({} compile time) with return code {:d}".format(
                            logging_tools.get_diff_time_str(time.time() - start_time),
                            logging_tools.get_diff_time_str(compile_time),
                            ret_code
                        )
                    )
                    self._show_logs(stdout_c, stderr_c, register_error=True, pre_str="{} wrote something to stderr".format(cur_conf.name))
                finally:
                    sys.stdout, sys.stderr = (old_stdout, old_stderr)
                    code_obj = None
        # print unicode(self.g_tree)
        # remove local vars
        for key in local_vars.iterkeys():
            del conf_dict[key]
        del self.cur_conf

    def _show_logs(self, stdout_c, stderr_c, **kwargs):
        for log_line in [line.rstrip() for line in stdout_c.get_content().split("\n") if line.strip()]:
            self.log("out: {}".format(log_line))
        for log_line in [line.rstrip() for line in stderr_c.get_content().split("\n") if line.strip()]:
            self.log("*** err: {}".format(log_line), logging_tools.LOG_LEVEL_ERROR)
            if kwargs.get("register_error", False):
                self.log(kwargs.get("pre_str", "stderr"), logging_tools.LOG_LEVEL_ERROR, register=True)
