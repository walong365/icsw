#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012,2013 Andreas Lang-Nevyjel
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
""" package server """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import cluster_location
import config_tools
import configfile
import datetime
import logging_tools
import pprint
import process_tools
import server_command
import subprocess
import threading_tools
import time
import uuid_tools
import zmq
from lxml import etree
from lxml.builder import E
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import package_repo, package_search, cluster_timezone, \
     package_search_result, device_variable, device, package, package_device_connection

try:
    from package_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "??.??-??"

P_SERVER_PUB_PORT = 8007
PACKAGE_CLIENT_PORT = 2003

ADD_PACK_PATH = "additional_packages"
DEL_PACK_PATH = "deleted_packages"

LAST_CONTACT_VAR_NAME = "package_server_last_contact"
PACKAGE_VERSION_VAR_NAME = "package_client_version"
DIRECT_MODE_VAR_NAME = "package_client_direct_mode"

SQL_ACCESS = "cluster_full_access"

CONFIG_NAME = "/etc/sysconfig/cluster/package_server_clients.xml"

class repository(object):
    def __init__(self):
        pass

class rpm_repository(repository):
    pass

class repo_type(object):
    def __init__(self, master_process):
        self.master_process = master_process
        self.log_com = master_process.log
        self.log("repository type is %s (%s)" % (self.REPO_TYPE_STR,
                                                 self.REPO_SUBTYPE_STR))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[rt] %s" % (what), log_level)

class repo_type_rpm_yum(repo_type):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "yum"
    SCAN_REPOS = "yum repolist all"
    REPO_CLASS = rpm_repository
    def search_package(self, s_string):
        return "yum -q --showduplicates search %s" % (s_string)
    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        cur_mode = 0
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        for line in s_struct.read().split("\n"):
            if line.startswith("repo id"):
                cur_mode = 1
            elif line.startswith("repolist:"):
                cur_mode = 0
            else:
                if cur_mode == 1:
                    parts = line.strip().replace("enabled:", "enabled").split()
                    while parts[-1] not in ["disabled", "enabled"]:
                        parts.pop(-1)
                    repo_name = parts.pop(0)
                    repo_enabled = True if parts.pop(-1) == "enabled" else False
                    repo_info = " ".join(parts)
                    # print repo_name, repo_enabled, repo_info
                    try:
                        cur_repo = package_repo.objects.get(Q(name=repo_name))
                    except package_repo.DoesNotExist:
                        cur_repo = package_repo(name=repo_name)
                        new_repos.append(cur_repo)
                    found_repos.append(cur_repo)
                    old_repos -= set([cur_repo.name])
                    cur_repo.alias = repo_info
                    cur_repo.enabled = repo_enabled
                    cur_repo.gpg_check = False
                    cur_repo.save()
        self.log("found %s" % (logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log("found %s: %s" % (logging_tools.get_plural("old repository", len(old_repos)),
                                       ", ".join(sorted(old_repos))), logging_tools.LOG_LEVEL_ERROR)
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        # if s_struct.src_id:
        #    self.master_process.send_pool_message(
        #        "delayed_result",
        #        s_struct.src_id,
        #        "rescanned %s" % (logging_tools.get_plural("repository", len(found_repos))),
        #        server_command.SRV_REPLY_STATE_OK)
        self.master_process._reload_searches()
    def init_search(self, s_struct):
        cur_search = s_struct.run_info["stuff"]
        cur_search.last_search_string = cur_search.search_string
        cur_search.num_searches += 1
        cur_search.current_state = "run"
        cur_search.save(update_fields=["last_search_string", "current_state", "num_searches"])
    def search_result(self, s_struct):
        cur_mode = 0
        found_packs = []
        for line in s_struct.read().split("\n"):
            if line.startswith("===="):
                cur_mode = 1
            elif not line.strip():
                cur_mode = 2
            else:
                if cur_mode == 1:
                    p_name = line.split()[0].strip()
                    if p_name and p_name != ":":
                        found_packs.append(p_name)
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        cur_search.results = len(found_packs)
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        self.log("found for %s: %d" % (cur_search.search_string, cur_search.results))
        for p_name in found_packs:
            parts = p_name.split("-")
            rel_arch = parts.pop(-1)
            arch = rel_arch.split(".")[-1]
            release = rel_arch[:-(len(arch) + 1)]
            version = parts.pop(-1)
            name = "-".join(parts)
            new_sr = package_search_result(
                name=name,

                arch=arch,
                version="%s-%s" % (version, release),
                package_search=cur_search,
                copied=False,
                package_repo=None)
            new_sr.save()

class repo_type_rpm_zypper(repo_type):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "zypper"
    SCAN_REPOS = "zypper --xml lr"
    REPO_CLASS = rpm_repository
    def search_package(self, s_string):
        return "zypper --xml search -s %s" % (s_string)
    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        repo_xml = etree.fromstring(s_struct.read())
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        for repo in repo_xml.xpath(".//repo-list/repo"):
            try:
                cur_repo = package_repo.objects.get(Q(name=repo.attrib["name"]))
            except package_repo.DoesNotExist:
                cur_repo = package_repo(name=repo.attrib["name"])
                new_repos.append(cur_repo)
            found_repos.append(cur_repo)
            old_repos -= set([cur_repo.name])
            cur_repo.alias = repo.attrib["alias"]
            cur_repo.repo_type = repo.attrib.get("type", "unknown")
            cur_repo.enabled = True if int(repo.attrib["enabled"]) else False
            cur_repo.autorefresh = True if int(repo.attrib["autorefresh"]) else False
            cur_repo.gpg_check = True if int(repo.attrib["gpgcheck"]) else False
            cur_repo.url = repo.findtext("url")
            cur_repo.save()
        self.log("found %s" % (logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log("found %s: %s" % (logging_tools.get_plural("old repository", len(old_repos)),
                                       ", ".join(sorted(old_repos))), logging_tools.LOG_LEVEL_ERROR)
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        if s_struct.src_id:
            self.master_process.send_pool_message(
                "delayed_result",
                s_struct.src_id,
                "rescanned %s" % (logging_tools.get_plural("repository", len(found_repos))),
                server_command.SRV_REPLY_STATE_OK)
        self.master_process._reload_searches()
    def init_search(self, s_struct):
        cur_search = s_struct.run_info["stuff"]
        cur_search.last_search_string = cur_search.search_string
        cur_search.num_searches += 1
        cur_search.current_state = "run"
        cur_search.save(update_fields=["last_search_string", "current_state", "num_searches"])
    def search_result(self, s_struct):
        res_xml = etree.fromstring(s_struct.read())
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        cur_search.results = len(res_xml.xpath(".//solvable"))
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        # all repos
        repo_dict = dict([(cur_repo.name, cur_repo) for cur_repo in package_repo.objects.all()])
        # delete previous search results
        cur_search.package_search_result_set.all().delete()
        self.log("found for %s: %d" % (cur_search.search_string, cur_search.results))
        for result in res_xml.xpath(".//solvable"):
            new_sr = package_search_result(
                name=result.attrib["name"],
                kind=result.attrib["kind"],
                arch=result.attrib["arch"],
                version=result.attrib["edition"],
                package_search=cur_search,
                copied=False,
                package_repo=repo_dict[result.attrib["repository"]])
            new_sr.save()

class subprocess_struct(object):
    run_idx = 0
    class Meta:
        max_usage = 2
        max_runtime = 300
        use_popen = True
        verbose = False
    def __init__(self, master_process, src_id, com_line, **kwargs):
        self.log_com = master_process.log
        subprocess_struct.run_idx += 1
        self.run_idx = subprocess_struct.run_idx
        # copy Meta keys
        for key in dir(subprocess_struct.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(subprocess_struct.Meta, key))
        if "verbose" in kwargs:
            self.Meta.verbose = kwargs["verbose"]
        self.src_id = src_id
        self.command_line = com_line
        self.multi_command = type(self.command_line) == list
        self.com_num = 0
        self.popen = None
        self.pre_cb_func = kwargs.get("pre_cb_func", None)
        self.post_cb_func = kwargs.get("post_cb_func", None)
        self._init_time = time.time()
        if kwargs.get("start", False):
            self.run()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[ss %d/%d] %s" % (self.run_idx, self.com_num, what), log_level)
    def run(self):
        run_info = {"stuff" : None}
        if self.multi_command:
            if self.command_line:
                cur_cl, add_stuff = self.command_line[self.com_num]
                if type(cur_cl) == type(()):
                    # in case of tuple
                    run_info["comline"] = cur_cl[0]
                else:
                    run_info["comline"] = cur_cl
                run_info["stuff"] = add_stuff
                run_info["command"] = cur_cl
                run_info["run"] = self.com_num
                self.com_num += 1
            else:
                run_info["comline"] = None
        else:
            run_info["comline"] = self.command_line
        self.run_info = run_info
        if run_info["comline"]:
            if self.Meta.verbose:
                self.log("popen '%s'" % (run_info["comline"]))
            self.current_stdout = ""
            if self.pre_cb_func:
                self.pre_cb_func(self)
            self.popen = subprocess.Popen(run_info["comline"], shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    def read(self):
        if self.popen:
            self.current_stdout = "%s%s" % (self.current_stdout, self.popen.stdout.read())
            return self.current_stdout
        else:
            return None
    def process_result(self):
        if self.post_cb_func:
            self.post_cb_func(self)
    def finished(self):
        if self.run_info["comline"] is None:
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        else:
            self.run_info["result"] = self.popen.poll()
            if self.Meta.verbose:
                if self.run_info["result"] is None:
                    self.log("pending")
                else:
                    self.log("finished with %s" % (str(self.run_info["result"])))
            fin = False
            if self.run_info["result"] is not None:
                self.process_result()
                if self.multi_command:
                    if self.com_num == len(self.command_line):
                        # last command
                        fin = True
                    else:
                        # next command
                        self.run()
                else:
                    fin = True
            else:
                self.current_stdout = "%s%s" % (self.current_stdout, self.popen.stdout.read())
        return fin

class repo_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        self.register_func("rescan_repos", self._rescan_repos)
        self.register_func("reload_searches", self._reload_searches)
        self.register_func("search", self._search)
        self.__background_commands = []
        self.register_timer(self._check_delayed, 1)
        # set repository type
        if os.path.isfile("/etc/centos-release"):
            self.repo_type = repo_type_rpm_yum(self)
        else:
            self.repo_type = repo_type_rpm_zypper(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _check_delayed(self):
        if len(self.__background_commands):
            self.log("%s running in background" % (logging_tools.get_plural("command", len(self.__background_commands))))
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
    def _rescan_repos(self, *args, **kwargs):
        if args:
            srv_com = server_command.srv_command(source=args[0])
        else:
            srv_com = None
        self.log("rescan repositories")
        self.__background_commands.append(subprocess_struct(
            self,
            0 if srv_com is None else int(srv_com["return_id"].text),
            self.repo_type.SCAN_REPOS,
            start=True,
            verbose=global_config["DEBUG"],
            post_cb_func=self.repo_type.repo_scan_result))
    def _search(self, s_string):
        self.log("searching for '%s'" % (s_string))
        self.__background_commands.append(subprocess_struct(self, 0, self.repo_type.search_package(s_string), start=True, verbose=global_config["DEBUG"], post_cb_func=self.repo_type.search_result))
    def _reload_searches(self, *args, **kwargs):
        self.log("reloading searches")
        search_list = []
        for cur_search in package_search.objects.filter(Q(deleted=False) & Q(current_state__in=["ini", "wait"])):
            search_list.append((self.repo_type.search_package(cur_search.search_string), cur_search))
        if search_list:
            self.log("%s found" % (logging_tools.get_plural("search", len(search_list))))
            self.__background_commands.append(subprocess_struct(
                self,
                0,
                search_list,
                start=True,
                verbose=global_config["DEBUG"],
                pre_cb_func=self.repo_type.init_search,
                post_cb_func=self.repo_type.search_result))
        else:
            self.log("nothing to search", logging_tools.LOG_LEVEL_WARN)

class client(object):
    all_clients = {}
    def __init__(self, c_uid, name):
        self.uid = c_uid
        self.name = name
        self.__version = ""
        self.device = device.objects.get(Q(name=self.name))
        self.__log_template = None
        self.__last_contact = None
    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           self.name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=client.srv_process.zmq_context,
                init_logger=True)
            self.log("added client")
    @staticmethod
    def init(srv_process):
        client.srv_process = srv_process
        client.uid_set = set()
        client.name_set = set()
        client.lut = {}
        if not os.path.exists(CONFIG_NAME):
            file(CONFIG_NAME, "w").write(etree.tostring(E.package_clients(), pretty_print=True))
        client.xml = etree.fromstring(file(CONFIG_NAME, "r").read())
        for client_el in client.xml.xpath(".//package_client"):
            client.register(client_el.text, client_el.attrib["name"])
    @staticmethod
    def get(key):
        return client.lut[key]
    @staticmethod
    def register(uid, name):
        if uid not in client.uid_set:
            try:
                new_client = client(uid, name)
            except device.DoesNotExist:
                client.srv_process.log("no client with name '%s' found" % (name), logging_tools.LOG_LEVEL_ERROR)
                if name.count("."):
                    s_name = name.split(".")[0]
                    client.srv_process.log("trying with short name '%s'" % (s_name), logging_tools.LOG_LEVEL_WARN)
                    try:
                        new_client = client(uid, s_name)
                    except:
                        new_client = None
                    else:
                        client.srv_process.log("successfull with short name", logging_tools.LOG_LEVEL_WARN)
            if client is not None:
                client.uid_set.add(uid)
                client.name_set.add(name)
                client.lut[uid] = new_client
                client.lut[name] = new_client
                client.srv_process.log("added client %s (%s)" % (name, uid))
                cur_el = client.xml.xpath(".//package_client[@name='%s']" % (name))
                if not len(cur_el):
                    client.xml.append(E.package_client(uid, name=name))
                    file(CONFIG_NAME, "w").write(etree.tostring(client.xml, pretty_print=True))
    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.create_logger()
        self.__log_template.log(level, what)
    def send_reply(self, srv_com):
        self.srv_process.send_reply(self.uid, srv_com)
    def __unicode__(self):
        return u"%s (%s)" % (self.name,
                             self.uid)
    def _modify_device_variable(self, var_name, var_descr, var_type, var_value):
        try:
            cur_var = device_variable.objects.get(Q(device=self.device) & Q(name=var_name))
        except device_variable.DoesNotExist:
            cur_var = device_variable(
                device=self.device,
                name=var_name)
        cur_var.description = var_descr
        cur_var.set_value(var_value)
        cur_var.save()
    def _set_version(self, new_vers):
        if new_vers != self.__version:
            self.log("changed version from '%s' to '%s'" % (self.__version,
                                                            new_vers))
            self.__version = new_vers
            self._modify_device_variable(
                PACKAGE_VERSION_VAR_NAME,
                "actual version of the client",
                "s",
                self.__version)
    def _expand_var(self, var):
        return var.replace("%{ROOT_IMPORT_DIR}", global_config["ROOT_IMPORT_DIR"])
    def _get_package_list(self, srv_com):
        resp = srv_com.builder(
            "packages",
            *[cur_pdc.get_xml(with_package=True) for cur_pdc in package_device_connection.objects.filter(Q(device=self.device)).select_related("package")]
        )
        srv_com["package_list"] = resp
    def _get_repo_list(self, srv_com):
        repo_list = package_repo.objects.filter(Q(publish_to_nodes=True))
        send_ok = [cur_repo for cur_repo in repo_list if cur_repo.distributable]
        self.log("%s, %d to send" % (
            logging_tools.get_plural("publish repo", len(repo_list)),
            len(send_ok),
            ))
        resp = srv_com.builder(
            "repos",
            *[cur_repo.get_xml() for cur_repo in send_ok]
        )
        srv_com["repo_list"] = resp
    def _package_info(self, srv_com):
        pdc_xml = srv_com.xpath(None, ".//package_device_connection")[0]
        info_xml = srv_com.xpath(None, ".//result")
        if len(info_xml):
            info_xml = info_xml[0]
            cur_pdc = package_device_connection.objects.select_related("package").get(Q(pk=pdc_xml.attrib["pk"]))
            cur_pdc.response_type = pdc_xml.attrib["response_type"]
            self.log("got package_info for %s (type is %s)" % (unicode(cur_pdc.package), cur_pdc.response_type))
            cur_pdc.response_str = etree.tostring(info_xml)
            cur_pdc.interpret_response()
            cur_pdc.save(update_fields=["response_type", "response_str", "installed"])
        else:
            self.log("got package_info without result", logging_tools.LOG_LEVEL_WARN)
    def new_command(self, srv_com):
        s_time = time.time()
        self.__last_contact = s_time
        cur_com = srv_com["command"].text
        if "package_client_version" in srv_com:
            self._set_version(srv_com["package_client_version"].text)
        self._modify_device_variable(LAST_CONTACT_VAR_NAME, "last contact of the client", "d", datetime.datetime(*time.localtime()[0:6]))
        srv_com.update_source()
        send_reply = False
        if cur_com == "get_package_list":
            srv_com["command"] = "package_list"
            self._get_package_list(srv_com)
            send_reply = True
        elif cur_com == "get_repo_list":
            srv_com["command"] = "repo_list"
            self._get_repo_list(srv_com)
            send_reply = True
        elif cur_com == "package_info":
            self._package_info(srv_com)
        else:
            self.log("unknown command '%s'" % (cur_com),
                     logging_tools.LOG_LEVEL_ERROR)
        if send_reply:
            self.send_reply(srv_com)
        e_time = time.time()
        self.log("handled command %s in %s" % (
            cur_com,
            logging_tools.get_diff_time_str(e_time - s_time)))

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(
            self, "main", zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._log_config()
        # idx for delayed commands
        self.__delayed_id, self.__delayed_struct = (0, {})
        self._re_insert_config()
        self.__msi_block = self._init_msi_block()
        self._init_clients()
        self._init_network_sockets()
        self.add_process(repo_process("repo"), start=True)
        # close DB connection
        connection.close()
        self.register_timer(self._send_update, 3600, instant=True)
        self.register_func("delayed_result", self._delayed_result)
        self.send_to_process("repo", "rescan_repos")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_clients(self):
        client.init(self)
    def _register_client(self, c_uid, srv_com):
        client.register(c_uid, srv_com["source"].attrib["host"])
    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("package_server", global_config)
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/package-server start"
            msi_block.stop_command = "/etc/init.d/package-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got SIGHUP, rescanning repositories")
        self.send_to_process("repo", "rescan_all")
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def loop_end(self):
        for c_name in client.name_set:
            client.get(c_name).close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()
    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            cur_com = srv_com["command"].text
            if cur_com == "register":
                self._register_client(c_uid, srv_com)
            else:
                if c_uid.endswith("webfrontend"):
                    self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                else:
                    try:
                        cur_client = client.get(c_uid)
                    except KeyError:
                        srv_com.update_source()
                        srv_com["result"] = None
                        self.log("got command '%s' from %s" % (cur_com, c_uid))
                        # check for normal command
                        if cur_com == "get_0mq_id":
                            srv_com["zmq_id"] = self.bind_id
                            srv_com["result"].attrib.update({
                                "reply" : "0MQ_ID is %s" % (self.bind_id),
                                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                        elif cur_com == "status":
                            srv_com["result"].attrib.update({
                                "reply" : "up and running",
                                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                        else:
                            self.log(
                                "unknown uid %s (command %s), not known" % (
                                    c_uid,
                                    cur_com,
                                    ),
                                        logging_tools.LOG_LEVEL_CRITICAL)
                            srv_com["result"].attrib.update({
                                "reply" : "unknown command '%s'" % (cur_com),
                                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
                        zmq_sock.send_unicode(c_uid, zmq.SNDMORE)
                        zmq_sock.send_unicode(unicode(srv_com))
                    else:
                        cur_client.new_command(srv_com)
        else:
            self.log("wrong number of data chunks (%d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _delayed_result(self, src_name, src_pid, ext_id, ret_str, ret_state, **kwargs):
        in_uid, srv_com = self.__delayed_struct[ext_id]
        del self.__delayed_struct[ext_id]
        self.log("sending delayed return for %s" % (unicode(srv_com)))
        srv_com["result"].attrib.update({
            "reply" : ret_str,
            "state" : "%d" % (ret_state)})
        zmq_sock = self.socket_dict["router"]
        zmq_sock.send_unicode(unicode(in_uid), zmq.SNDMORE)
        zmq_sock.send_unicode(unicode(srv_com))
    def _handle_wfe_command(self, zmq_sock, in_uid, srv_com):
        in_com = srv_com["command"].text
        self.log("got server_command %s from %s" % (
            in_com,
            in_uid))
        srv_com.update_source()
        immediate_return = True
        srv_com["result"] = None
        srv_com["result"].attrib.update({
            "reply" : "result not set",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_UNSET)})
        if in_com == "new_config":
            all_devs = srv_com.xpath(None, ".//ns:device_command/@name")
            if not all_devs:
                valid_devs = list(client.name_set)
            else:
                valid_devs = [name for name in all_devs if name in client.name_set]
            self.log("%s requested, %s found" % (
                logging_tools.get_plural("device", len(all_devs)),
                logging_tools.get_plural("device" , len(valid_devs))))
            for cur_dev in all_devs:
                srv_com.xpath(None, ".//ns:device_command[@name='%s']" % (cur_dev))[0].attrib["config_sent"] = "1" if cur_dev in valid_devs else "0"
            if valid_devs:
                self._send_update(command="new_config", dev_list=valid_devs)
            srv_com["result"].attrib.update({
                "reply" : "send update to %d of %d %s" % (
                    len(valid_devs),
                    len(all_devs),
                    logging_tools.get_plural("device", len(all_devs))),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK if len(valid_devs) == len(all_devs) else server_command.SRV_REPLY_STATE_WARN)})
        elif in_com == "reload_searches":
            self.send_to_process("repo", "reload_searches")
            srv_com["result"].attrib.update({
                "reply" : "ok reloading",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        elif in_com == "rescan_repos":
            self.__delayed_id += 1
            self.__delayed_struct[self.__delayed_id] = (in_uid, srv_com)
            srv_com["return_id"] = self.__delayed_id
            self.send_to_process("repo", "rescan_repos", unicode(srv_com))
            immediate_return = False
        elif in_com == "sync_repos":
            all_devs = list(client.name_set)
            self.log("sending sync_repos to %s" % (logging_tools.get_plural("device", len(all_devs))))
            if all_devs:
                self._send_update(command="sync_repos", dev_list=all_devs)
            srv_com["result"].attrib.update({
                "reply" : "send sync_repos to %s" % (
                    logging_tools.get_plural("device", len(all_devs))),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        else:
            srv_com["result"].attrib.update({
                "reply" : "command %s not known" % (in_com),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        # print srv_com.pretty_print()
        if immediate_return:
            zmq_sock.send_unicode(unicode(in_uid), zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
    def _init_network_sockets(self):
        my_0mq_id = "%s:package-server:" % (uuid_tools.get_uuid().get_urn())
        self.bind_id = my_0mq_id
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PUB_PORT"] , self._new_com),
            ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, self.bind_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.RCVHWM, 256)
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.core.error.ZMQError:
                self.log(
                    "error binding to %s{%d}: %s" % (
                        conn_str,
                        sock_type,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL)
                client.close()
            else:
                self.log("bind to port %s{%d}, ID is %s" % (
                    conn_str,
                    sock_type,
                    self.bind_id,
                    ))
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client
    def send_reply(self, t_uid, srv_com):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(t_uid, zmq.SNDMORE | zmq.NOBLOCK)
        send_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)
    def _send_update(self, command="send_info", dev_list=[]):
        send_list = dev_list or client.name_set
        self.log("send command %s to %s" % (command,
                                            logging_tools.get_plural("client", len(send_list))))
        send_com = server_command.srv_command(command=command)
        for target_name in send_list:
            cur_c = client.get(target_name)
            if cur_c is not None:
                self.send_reply(cur_c.uid, send_com)
            else:
                self.log("no client with name '%s' found" % (target_name), logging_tools.LOG_LEVEL_WARN)

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"                    , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"                , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"                 , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"             , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"                    , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                     , configfile.str_c_var("idpacks", help_string="user to run as [%(default)s]")),
        ("GROUP"                    , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"                   , configfile.array_c_var(["idg"])),
        ("FORCE"                    , configfile.bool_c_var(False, help_string="force running ", action="store_true", only_commandline=True)),
        ("LOG_DESTINATION"          , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"                 , configfile.str_c_var(prog_name)),
        ("VERBOSE"                  , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"          , configfile.int_c_var(P_SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
        ("NODE_PORT"                , configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="port where the package-clients are listening [%(default)d]")),
        ("DELETE_MISSING_REPOS"     , configfile.bool_c_var(False, help_string="delete non-existing repos from DB")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="package_server")
    if not sql_info.effective_device:
        print "not a package_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("package-server", "Cluster PackageServer", device=sql_info.effective_device).pk))])
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/package-server"])
    process_tools.renice()
    process_tools.fix_sysconfig_rights()
    process_tools.change_user_group_path(os.path.dirname(os.path.join(process_tools.RUN_DIR, global_config["PID_NAME"])), global_config["USER"], global_config["GROUP"])
    configfile.enable_config_access(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "package-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging package-server on %s" % (long_host_name)
    ret_code = server_process().loop()
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
