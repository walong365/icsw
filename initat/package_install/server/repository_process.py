#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2012-2015 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server, repository process """

import os
import time

from django.db import connection
from django.db.models import Q

from initat.cluster.backbone.models import package_search
from initat.tools import logging_tools, server_command, threading_tools
from .config import global_config
from .structs import RepoTypeRpmYum, RepoTypeRpmZypper, SubprocessStruct


class RepoProcess(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        # close database connection
        connection.close()
        self.register_func("rescan_repos", self._rescan_repos)
        self.register_func("reload_searches", self._reload_searches)
        self.register_func("clear_cache", self._clear_cache)
        self.register_func("search", self._search)
        self._correct_search_states()
        self.__background_commands = []
        self.register_timer(self._check_delayed, 1)
        # set repository type
        if os.path.isfile("/etc/centos-release") or os.path.isfile("/etc/redhat-release"):
            self.repo_type = RepoTypeRpmYum(self)
        else:
            self.repo_type = RepoTypeRpmZypper(self)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _correct_search_states(self):
        inv_states = package_search.objects.exclude(Q(deleted=True) & Q(current_state="done"))
        for inv_state in inv_states:
            inv_state.current_state = "done"
            inv_state.save()

    def _check_delayed(self):
        if len(self.__background_commands):
            self.log(
                "{} running in background".format(
                    logging_tools.get_plural("command", len(self.__background_commands))
                )
            )
        cur_time = time.time()
        new_list = []
        for cur_del in self.__background_commands:
            if cur_del.Meta.use_popen:
                if cur_del.finished():
                    # print "finished delayed"
                    # print "cur_del.send_return()"
                    pass
                elif abs(cur_time - cur_del._init_time) > cur_del.Meta.max_runtime:
                    self.log("delay_object runtime exceeded, stopping")
                    cur_del.terminate()
                    # cur_del.send_return()
                else:
                    new_list.append(cur_del)
            else:
                if not cur_del.terminated:
                    new_list.append(cur_del)
        self.__background_commands = new_list
    # commands

    def _clear_cache(self, *args, **kwargs):
        self.log("clearing cache")
        self.__background_commands.append(
            SubprocessStruct(
                self,
                None,
                self.repo_type.CLEAR_CACHE,
                start=True,
                verbose=global_config["DEBUG"],
            )
        )

    def _rescan_repos(self, *args, **kwargs):
        if args:
            srv_com = server_command.srv_command(source=args[0])
        else:
            srv_com = None
        self.log("rescan repositories")
        self.__background_commands.append(
            SubprocessStruct(
                self,
                srv_com,
                self.repo_type.SCAN_REPOS,
                start=True,
                verbose=global_config["DEBUG"],
                post_cb_func=self.repo_type.repo_scan_result
            )
        )

    def _search(self, s_string):
        self.log("searching for '{}'".format(s_string))
        self.__background_commands.append(
            SubprocessStruct(
                self,
                None,
                self.repo_type.search_package(s_string),
                start=True,
                verbose=global_config["DEBUG"],
                post_cb_func=self.repo_type.search_result
            )
        )

    def _reload_searches(self, *args, **kwargs):
        self.log("reloading searches")
        if len(args):
            srv_com = server_command.srv_command(source=args[0])
            srv_com.set_result("ok reloading searches")
            self.send_pool_message("remote_call_async_result", unicode(srv_com))
        search_list = []
        for cur_search in package_search.objects.filter(Q(deleted=False) & Q(current_state__in=["ini", "wait"])):
            search_list.append((self.repo_type.search_package(cur_search.search_string), cur_search))
        if search_list:
            self.log("{} found".format(logging_tools.get_plural("search", len(search_list))))
            self.__background_commands.append(
                SubprocessStruct(
                    self,
                    None,
                    search_list,
                    start=True,
                    verbose=global_config["DEBUG"],
                    pre_cb_func=self.repo_type.init_search,
                    post_cb_func=self.repo_type.search_result
                )
            )
        else:
            self.log("nothing to search", logging_tools.LOG_LEVEL_WARN)
