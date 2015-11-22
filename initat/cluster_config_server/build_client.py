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
""" cluster-config-server, build client """

import os
import shutil

from django.db.models import Q
from initat.cluster.backbone.models import device

from initat.tools import logging_tools, process_tools
from .build_container import BuildContainer, GeneratedTree
from .config import global_config
from .partition_setup import partition_setup


class build_client(object):
    """ holds all the necessary data for a complex config request """
    def __init__(self, **kwargs):
        name = kwargs["name"]
        if name.count("."):
            # fqdn
            self.pk = int(
                kwargs.get(
                    "pk", device.objects.values("pk").get(
                        Q(name=name.split(".")[0]) &
                        Q(domain_tree_node__full_name=name.split(".", 1)[1])
                    )["pk"]
                )
            )
        else:
            # short name
            self.pk = int(kwargs.get("pk", device.objects.values("pk").get(Q(name=name))["pk"]))
        self.name = device.objects.get(Q(pk=self.pk)).full_name
        self.name_list = set([self.name, self.name.split(".")[0]])
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
            self.log(
                "{} defined, {:d} new{}:".format(
                    logging_tools.get_plural("attribute", len(self.set_keys)),
                    len(log_keys),
                    ", {}".format(info_str) if info_str else ""
                )
            )
        for key in sorted(log_keys):
            self.log(" {:<24s} : {}".format(key, getattr(self, key)))
        self.logged_keys = self.set_keys

    def add_set_keys(self, *keys):
        self.set_keys = list(set(self.set_keys) | set(keys))

    def get_send_dict(self):
        return dict([(key, getattr(self, key)) for key in self.set_keys + ["name", "pk"]])

    def create_logger(self):
        self.__log_template = logging_tools.get_logger(
            "{}.{}".format(
                global_config["LOG_NAME"],
                self.name.replace(".", r"\.")
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=build_client.srv_process.zmq_context,
            init_logger=True
        )
        self.log("added client ({} [{:d})".format(self.name, self.pk))

    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK, **kwargs):
        self.__log_template.log(level, what)
        if "state" in kwargs:
            self.add_set_keys("info_str", "state_level")
            self.internal_state = kwargs["state"]
            self.info_str = what
            self.state_level = "{:d}".format(level)
        if kwargs.get("register", False):
            self.__error_dict.setdefault(level, []).append(what)

    @staticmethod
    def bc_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        build_client.srv_process.log("[bc] %s" % (what), log_level)

    @staticmethod
    def init(srv_process):
        build_client.__bc_dict = {}
        build_client.__bc_list = []
        build_client.srv_process = srv_process
        build_client.bc_log("init build_client")

    @staticmethod
    def close_clients():
        for cur_c in build_client.__bc_list:
            cur_c.close()

    @staticmethod
    def get_client(**kwargs):
        name = kwargs["name"]
        if name not in build_client.__bc_dict:
            new_c = build_client(**kwargs)
            for new_name in new_c.name_list:
                build_client.__bc_dict[new_name] = new_c
            build_client.bc_log("added client %s" % (", ".join(new_c.name_list)))
            build_client.__bc_list.append(new_c)
        else:
            new_c = build_client.__bc_dict[name]
        new_c.cleanup()
        new_c.set_kwargs(**kwargs)
        return new_c
    # config-related calls

    def get_partition(self, *args):
        part_name = args[0]
        loc_tree = GeneratedTree()
        loc_dev = device.objects.get(Q(pk=self.pk))
        self.log("set act_partition_table and partdev to %s" % (part_name))
        loc_dev.act_partition_table = loc_dev.partition_table
        loc_dev.partdev = part_name
        loc_dev.save()
        success = False
        dummy_cont = BuildContainer(self, {}, {"device": loc_dev}, loc_tree, None)
        try:
            loc_ps = partition_setup(dummy_cont)
        except:
            self.log(
                "cannot generate partition info: {}".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR
            )
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
        node_dir, node_link = (
            os.path.join(base_dir, self.name),
            os.path.join(base_dir, self.name.split(".")[0]),
        )
        self.log("node_dir is %s, node_link is %s" % (node_dir, node_link))
        self.set_kwargs(node_dir=node_dir)
        self.node_dir = node_dir
        success = True
        if not os.path.isdir(node_dir):
            try:
                os.mkdir(node_dir)
            except OSError:
                self.log(
                    "cannot create config_directory %s: %s" % (
                        node_dir,
                        process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
                success = False
            else:
                self.log("created config directory %s" % (node_dir))
        if os.path.isdir(node_dir):
            if node_dir != node_link:
                if os.path.isdir(node_link) and not os.path.islink(node_link):
                    try:
                        shutil.rmtree(node_link)
                    except:
                        self.log(
                            "cannot rmtree '%s': %s" % (
                                node_link,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("removed tree '%s'" % (node_link))
                if os.path.islink(node_link):
                    if os.readlink(node_link) != self.name:
                        try:
                            os.unlink(node_link)
                        except:
                            self.log(
                                "cannot delete wrong link %s: %s" % (
                                    node_link,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            success = False
                        else:
                            self.log("Removed wrong link %s" % (node_link))
                if not os.path.islink(node_link):
                    try:
                        os.symlink(self.name, node_link)
                    except:
                        self.log("cannot create link from %s to %s: %s" % (node_link,
                                                                           self.name,
                                                                           process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        success = False
                    else:
                        self.log("Created link from %s to %s" % (node_link,
                                                                 self.name))
        return success

    def clean_directory(self, prod_key):
        # cleans directory of network_key
        prod_key = prod_key.replace(" ", "_")
        rem_file_list, rem_dir_list = ([], [])
        dir_list = [
            os.path.join(self.node_dir, "configdir_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_dir_{}".format(prod_key)),
            os.path.join(self.node_dir, "content_{}".format(prod_key)),
        ]
        file_list = [
            os.path.join(self.node_dir, "config_files_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_dirs_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_links_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_delete_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_{}".format(prod_key)),
            os.path.join(self.node_dir, "configl_{}".format(prod_key)),
            os.path.join(self.node_dir, "config_d{}".format(prod_key)),
        ]
        for old_name in dir_list:
            if os.path.isdir(old_name):
                rem_file_list.extend([os.path.join(old_name, file_name) for file_name in os.listdir(old_name)])
                rem_dir_list.append(old_name)
        for old_name in file_list:
            if os.path.isfile(old_name):
                rem_file_list.append(old_name)
        num_removed = {
            "file": 0,
            "dir": 0
        }
        for del_name in rem_file_list + rem_dir_list:
            try:
                if os.path.isfile(del_name):
                    ent_type = "file"
                    os.unlink(del_name)
                else:
                    ent_type = "dir"
                    os.rmdir(del_name)
            except:
                self.log(
                    "error removing {} {}: {}".format(
                        ent_type,
                        del_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                num_removed[ent_type] += 1
        if sum(num_removed.values()):
            self.log(
                "removed {} for key '{}'".format(
                    " and ".join([logging_tools.get_plural(key, value) for key, value in num_removed.iteritems()]),
                    prod_key
                )
            )
        else:
            self.log("config on disk for key '{}' was empty".format(prod_key))
