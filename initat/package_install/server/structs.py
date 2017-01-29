# Copyright (C) 2001-2017 Andreas Lang-Nevyjel
#
# this file is part of package-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" package server, base structures """

import datetime
import os
import subprocess
import time
import urllib.parse

from django.db.models import Q
from lxml import etree
from lxml.builder import E
from rest_framework_xml.renderers import XMLRenderer

from initat.cluster.backbone.models import package_repo, cluster_timezone, \
    package_search_result, device_variable, device, package_device_connection, \
    package_service
from initat.cluster.backbone.serializers import package_device_connection_wp_serializer, \
    package_repo_serializer
from initat.tools import logging_tools, process_tools, server_command, config_store
from .config import global_config
from .constants import CLIENT_CS_NAME, PACKAGE_VERSION_VAR_NAME, LAST_CONTACT_VAR_NAME


class Repository(object):
    def __init__(self):
        pass


class RPMRepository(Repository):
    pass


class RepoType(object):
    def __init__(self, master_process):
        self.master_process = master_process
        self.log_com = master_process.log
        self.log(
            "repository type is {} ({})".format(
                self.REPO_TYPE_STR,
                self.REPO_SUBTYPE_STR
            )
        )

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[rt] {}".format(what), log_level)

    def rescan_repos(self, srv_com):
        # return None of BackgroundCommandStruct
        self.log("dummy rescan repos call", logging_tools.LOG_LEVEL_WARN)
        return None

    def init_search(self, s_struct):
        cur_search = s_struct.run_info["stuff"]
        cur_search.last_search_string = cur_search.search_string
        cur_search.num_searches += 1
        cur_search.results = 0
        cur_search.current_state = "run"
        cur_search.save(update_fields=["last_search_string", "current_state", "num_searches", "results"])


class RepoTypeRpmYum(RepoType):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "yum"
    SCAN_REPOS = "yum -v repolist all --color=no"
    CLEAR_CACHE = "yum -y clean all"
    REPO_CLASS = RPMRepository

    def search_package(self, s_string):
        return "yum -v --showduplicates search {}".format(s_string)

    def rescan_repos(self, srv_com):
        return SubprocessStruct(
            self.master_process,
            srv_com,
            self.SCAN_REPOS,
            start=True,
            verbose=global_config["DEBUG"],
            post_cb_func=self.repo_scan_result
        )

    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        repo_list = []
        cur_repo_dict = {}
        for line in s_struct.read().split("\n"):
            # strip spaces
            line = line.strip()
            if line.count(":"):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key.startswith("repo-"):
                    key = key[5:]
                    cur_repo_dict[key] = value
            else:
                # empty line, set repo_id to zero
                if cur_repo_dict:
                    repo_list.append(cur_repo_dict)
                cur_repo_dict = {}
        if cur_repo_dict:
            repo_list.append(cur_repo_dict)
        # map:
        # id ........ name
        # status .... disabled / enabled
        # baseurl ... url
        # name ...... alias
        for _dict in repo_list:
            try:
                cur_repo = package_repo.objects.get(Q(name=_dict["id"]))
            except package_repo.DoesNotExist:
                cur_repo = package_repo(name=_dict["id"])
                new_repos.append(cur_repo)
            repo_enabled = True if _dict.get("status", "disabled").lower() == "enabled" else False
            found_repos.append(cur_repo)
            old_repos -= {cur_repo.name}
            # print repo_name, repo_enabled, repo_info
            cur_repo.alias = _dict["name"]
            cur_repo.enabled = repo_enabled
            cur_repo.url = _dict.get("baseurl", "http://").split()[0]
            cur_repo.gpg_check = False
            # dummy value
            cur_repo.repo_type = _dict.get("type", "yum")
            cur_repo.save()
        self.log("found {}".format(logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("old repository", len(old_repos)),
                    ", ".join(sorted(old_repos))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        if s_struct.srv_com is not None:
            s_struct.srv_com.set_result(
                "rescanned {}".format(logging_tools.get_plural("repository", len(found_repos)))
            )
            self.master_process.send_pool_message(
                "remote_call_async_result",
                str(s_struct.srv_com),
            )
        self.master_process._reload_searches()

    def search_result(self, s_struct):
        cur_mode, _ln = (0, None)
        found_packs = []
        for line in s_struct.read().split("\n"):
            if line.startswith("===="):
                # header done
                cur_mode = 1
                _ln = 0
            elif not line.strip():
                # empty line, check for new package
                cur_mode = 1
                _ln = 0
            else:
                if cur_mode == 1:
                    _ln += 1
                    if _ln == 1:
                        p_info = [line.strip().split()[0]]
                    else:
                        if line.lower().startswith("repo") and line.count(":"):
                            p_info.append(line.strip().split(":")[1].strip())
                            found_packs.append(p_info)
                    # p_name = line.split()[0].strip()
                    # if p_name and p_name != ":":
                    #    if p_name[0].isdigit() and p_name.count(":"):
                    #        p_name = p_name.split(":", 1)[1]
                    #    found_packs.append(p_name)
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        _found = 0
        cur_search.results = _found
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        # delete previous search results
        cur_search.package_search_result_set.all().delete()
        self.log("parsing results... ({:d} found)".format(len(found_packs)))
        repo_dict = {_repo.name: _repo for _repo in package_repo.objects.all()}
        for p_name, repo_name in found_packs:
            if repo_name == "installed":
                continue
            try:
                parts = p_name.split("-")
                rel_arch = parts.pop(-1)
                arch = rel_arch.split(".")[-1]
                release = rel_arch[:-(len(arch) + 1)]
                version = parts.pop(-1)
                name = "-".join(parts)
            except:
                self.log("cannot parse package name {}: {}".format(p_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                _found += 1
                new_sr = package_search_result(
                    name=name,
                    arch=arch,
                    version="{}-{}".format(version, release),
                    package_search=cur_search,
                    copied=False,
                    package_repo=repo_dict.get(repo_name, None)
                )
                new_sr.save()
        cur_search.results = _found
        cur_search.save(update_fields=["results"])
        self.log("found for {}: {:d}".format(cur_search.search_string, cur_search.results))


class RepoTypeDebDebian(RepoType):
    REPO_TYPE_STR = "deb"
    REPO_SUBTYPE_STR = "debian"

    def search_package(self, s_string):
        return "aptitude search -F '%p %V' --disable-columns {}".format(s_string)

    def _parse_url(self, url):
        _res = urllib.parse.urlparse(url)
        _netloc = _res.netloc
        if _netloc.count("@"):
            _upwd, _netloc = _netloc.split("@", 1)
            _user, _password = _upwd.split(":", 1)
        else:
            _user, _password = (None, None)
        return _res, _netloc, _user, _password

    def search_result(self, s_struct):
        cur_mode, _ln = (0, None)
        found_packs = []
        for line in s_struct.read().split("\n"):
            found_packs.append(line.strip().split())
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        _found = 0
        cur_search.results = _found
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        # delete previous search results
        cur_search.package_search_result_set.all().delete()
        self.log("parsing results... ({:d} found)".format(len(found_packs)))
        repo_dict = {_repo.name: _repo for _repo in package_repo.objects.all()}
        for _parts in found_packs:
            try:
                p_name, p_ver = _parts
                version, release = p_ver.split("-", 1)
                _found += 1
                new_sr = package_search_result(
                    name=p_name,
                    version="{}-{}".format(version, release),
                    package_search=cur_search,
                    copied=False,
                )
                new_sr.save()
            except:
                self.log(
                    "cannot interpret line '{}': {}".format(
                        _parts,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        cur_search.results = _found
        cur_search.save(update_fields=["results"])
        self.log("found for {}: {:d}".format(cur_search.search_string, cur_search.results))

    def rescan_repos(self, srv_com):
        def _read_file(f_name):
            return [
                line.strip() for line in open(f_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")
            ]
        self.log("debian scan")
        _src_list_dir = "/etc/apt"
        _src_list = _read_file(os.path.join(_src_list_dir, "sources.list"))
        _sub_dir = os.path.join(_src_list_dir, "sources.list.d")
        if os.path.isdir(_sub_dir):
            for entry in os.listdir(_sub_dir):
                _path = os.path.join(_sub_dir, entry)
                _src_list.extend(_read_file(_path))
        self.log("src_list has {}".format(logging_tools.get_plural("line", len(_src_list))))
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        new_repos = []
        found_repos = []
        for _line in _src_list:
            _parts = _line.split()
            if len(_parts) == 4:
                if _parts[0] == "deb":
                    parsed, netloc, user, password = self._parse_url(_parts[1])
                    name = "{}{}".format(netloc, parsed.path)
                    try:
                        cur_repo = package_repo.objects.get(Q(name=name))
                    except package_repo.DoesNotExist:
                        cur_repo = package_repo(name=name)
                        new_repos.append(cur_repo)
                    old_repos -= {cur_repo.name}
                    cur_repo.alias = ""
                    cur_repo.deb_distribution = _parts[2]
                    cur_repo.deb_components = _parts[3]
                    cur_repo.repo_type = ""
                    cur_repo.username = user or ""
                    cur_repo.password = password or ""
                    cur_repo.url = "{}://{}{}".format(
                        parsed.scheme,
                        netloc,
                        parsed.path,
                    )
                    cur_repo.enabled = True
                    cur_repo.priority = 0
                    cur_repo.autorefresh = True
                    cur_repo.gpg_check = False
                    cur_repo.save()
                else:
                    self.log("skipping line with type {} ('{}')".format(_parts[0], _line), logging_tools.LOG_LEVEL_WARN)
                pass
            else:
                self.log("unparseable line '{}'".format(_line), logging_tools.LOG_LEVEL_ERROR)
        self.log("found {}".format(logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("old repository", len(old_repos)),
                    ", ".join(sorted(old_repos))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        if srv_com is not None:
            srv_com.set_result(
                "rescanned {}".format(logging_tools.get_plural("repository", len(found_repos)))
            )
            self.master_process.send_pool_message(
                "remote_call_async_result",
                str(srv_com),
            )
        # self.master_process._reload_searches()
        return None


class RepoTypeRpmZypper(RepoType):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "zypper"
    # changed on 2014-02-27, query services (includes repositories)
    SCAN_REPOS = "zypper --xml ls -r -d"
    CLEAR_CACHE = "zypper clean -a"
    REPO_CLASS = RPMRepository

    def search_package(self, s_string):
        return "zypper --xml search -s {}".format(s_string)

    def rescan_repos(self, srv_com):
        return SubprocessStruct(
            self.master_process,
            srv_com,
            self.SCAN_REPOS,
            start=True,
            verbose=global_config["DEBUG"],
            post_cb_func=self.repo_scan_result
        )

    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        repo_xml = etree.fromstring(s_struct.read())
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        priority_found = False
        for repo in repo_xml.xpath(".//repo", smart_strings=False):
            if repo.getparent().tag == "service":
                service_xml = repo.getparent()
                try:
                    cur_srv = package_service.objects.get(Q(name=service_xml.attrib["name"]))
                except package_service.DoesNotExist:
                    cur_srv = package_service(
                        name=service_xml.attrib["name"],
                        alias=service_xml.attrib["alias"],
                        url=service_xml.attrib["url"],
                        type=service_xml.attrib["type"],
                        enabled=True if int(service_xml.attrib["enabled"]) else False,
                        autorefresh=True if int(service_xml.attrib["autorefresh"]) else False,
                    )
                    cur_srv.save()
            else:
                cur_srv = None
            try:
                cur_repo = package_repo.objects.get(Q(name=repo.attrib["name"]))
            except package_repo.DoesNotExist:
                cur_repo = package_repo(name=repo.attrib["name"])
                new_repos.append(cur_repo)
            found_repos.append(cur_repo)
            old_repos -= {cur_repo.name}
            cur_repo.alias = repo.attrib["alias"]
            cur_repo.repo_type = repo.attrib.get("type", "")
            if "priority" in repo.attrib:
                priority_found = True
            cur_repo.priority = int(repo.attrib.get("priority", "99"))
            cur_repo.enabled = True if int(repo.attrib["enabled"]) else False
            cur_repo.autorefresh = True if int(repo.attrib["autorefresh"]) else False
            cur_repo.gpg_check = True if int(repo.attrib["gpgcheck"]) else False
            cur_repo.url = repo.findtext("url")
            cur_repo.service = cur_srv
            cur_repo.save()
        if not priority_found:
            self.log("no priorities defined in XML-output, rescanning using normal output", logging_tools.LOG_LEVEL_ERROR)
            _zypper_com = "/usr/bin/zypper lr -p"
            _stat, _out = subprocess.getstatusoutput(_zypper_com)
            if _stat:
                self.log("error scanning via '{}' ({:d}): {}".format(_zypper_com, _stat, _out))
            else:
                _lines = _out.strip().split("\n")[2:]
                for _line in _lines:
                    _parts = [_p.strip() for _p in _line.split("|")]
                    if len(_parts) == 6:
                        _name, _pri = (_parts[2], int(_parts[5]))
                        try:
                            cur_repo = package_repo.objects.get(Q(name=_name))
                        except package_repo.DoesNotExist:
                            self.log("no repository with name '{}' found".format(_name), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            if _pri != cur_repo.priority:
                                self.log(
                                    "changing priority of {} from {:d} to {:d}".format(
                                        cur_repo.name,
                                        cur_repo.priority,
                                        _pri,
                                    )
                                )
                            cur_repo.priority = _pri
                            cur_repo.save()
        self.log("found {}".format(logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("old repository", len(old_repos)),
                    ", ".join(sorted(old_repos))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        if s_struct.srv_com is not None:
            s_struct.srv_com.set_result(
                "rescanned {}".format(logging_tools.get_plural("repository", len(found_repos)))
            )
            self.master_process.send_pool_message(
                "remote_call_async_result",
                str(s_struct.srv_com),
            )
        self.master_process._reload_searches()

    def search_result(self, s_struct):
        res_xml = etree.fromstring(s_struct.read())
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        cur_search.results = len(res_xml.xpath(".//solvable", smart_strings=False))
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        # all repos
        repo_dict = dict([(cur_repo.name, cur_repo) for cur_repo in package_repo.objects.all()])
        # delete previous search results
        cur_search.package_search_result_set.all().delete()
        self.log("found for {}: {:d}".format(cur_search.search_string, cur_search.results))
        for result in res_xml.xpath(".//solvable", smart_strings=False):
            if result.attrib["repository"] in repo_dict:
                new_sr = package_search_result(
                    name=result.attrib["name"],
                    kind=result.attrib["kind"],
                    arch=result.attrib["arch"],
                    version=result.attrib["edition"],
                    package_search=cur_search,
                    copied=False,
                    package_repo=repo_dict[result.attrib["repository"]]
                )
                new_sr.save()
            else:
                self.log(
                    "unknown repository '{}' for package '{}'".format(
                        result.attrib["repository"],
                        result.attrib["name"],
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )


class SubprocessStruct(object):
    run_idx = 0

    class Meta:
        max_usage = 2
        max_runtime = 300
        use_popen = True
        verbose = False

    def __init__(self, master_process, srv_com, com_line, **kwargs):
        self.log_com = master_process.log
        SubprocessStruct.run_idx += 1
        self.run_idx = SubprocessStruct.run_idx
        # copy Meta keys
        for key in dir(SubprocessStruct.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(SubprocessStruct.Meta, key))
        if "verbose" in kwargs:
            self.Meta.verbose = kwargs["verbose"]
        self.srv_com = srv_com
        self.command_line = com_line
        self.multi_command = isinstance(self.command_line, list)
        self.com_num = 0
        self.popen = None
        self.pre_cb_func = kwargs.get("pre_cb_func", None)
        self.post_cb_func = kwargs.get("post_cb_func", None)
        self._init_time = time.time()
        if kwargs.get("start", False):
            self.run()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[ss {:d}/{:d}] {}".format(self.run_idx, self.com_num, what), log_level)

    def run(self):
        run_info = {"stuff": None}
        if self.multi_command:
            if self.command_line:
                cur_cl, add_stuff = self.command_line[self.com_num]
                if isinstance(cur_cl, tuple):
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
                self.log("popen '{}'".format(run_info["comline"]))
            self.current_stdout = ""
            if self.pre_cb_func:
                self.pre_cb_func(self)
            self.popen = subprocess.Popen(run_info["comline"], shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

    def read(self):
        if self.popen:
            self.current_stdout = "{}{}".format(self.current_stdout, self.popen.stdout.read().decode("utf-8"))
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
                    self.log("finished with {}".format(str(self.run_info["result"])))
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
                self.current_stdout = "{}{}".format(self.current_stdout, self.popen.stdout.read())
        return fin


class Client(object):
    all_clients = {}
    name_set = set()

    def __init__(self, c_uid, name):
        self.uid = c_uid
        self.name = name
        self.__version = ""
        self.__client_gen = 0
        self.device = device.objects.get(Q(name=self.name))
        self.__log_template = None
        self.__last_contact = None

    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "{}.{}".format(
                    global_config["LOG_NAME"],
                    self.name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=Client.srv_process.zmq_context,
                init_logger=True
            )
            self.log("added client")

    @staticmethod
    def init(srv_process):
        OLD_CONFIG_NAME = "/etc/sysconfig/cluster/package_server_clients.xml"
        Client.srv_process = srv_process
        Client.uuid_set = set()
        Client.name_set = set()
        Client.lut = {}
        if not config_store.ConfigStore.exists(CLIENT_CS_NAME):
            _create = True
            _cs = config_store.ConfigStore(CLIENT_CS_NAME, log_com=Client.srv_process.log, read=False, prefix="client")
            if os.path.exists(OLD_CONFIG_NAME):
                _xml = etree.fromstring(open(OLD_CONFIG_NAME, "r").read())
                for _idx, _entry in enumerate(_xml.findall(".//package_client")):
                    _cs["{:d}".format(_idx)] = {
                        "name": _entry.attrib["name"],
                        "uuid": _entry.text,
                    }
            Client.CS = _cs
        else:
            Client.CS = config_store.ConfigStore(CLIENT_CS_NAME, log_com=Client.srv_process.log, prefix="client")
            _create = False
        if _create:
            Client.CS.write()
            _cs.write()
        for client_num in list(Client.CS.keys()):
            _stuff = Client.CS[client_num]
            Client.register(_stuff["uuid"], _stuff["name"])

    @staticmethod
    def full_uuid(in_uuid):
        return "urn:uuid:{}:package-client:".format(in_uuid)

    @staticmethod
    def get(key):
        return Client.lut[key]

    @staticmethod
    def register(uid, name):
        if (not uid.endswith(":pclient:")) and (not uid.endswith(":package-client:")):
            uid = "{}:package-client:".format(uid)
        if uid not in Client.uuid_set:
            try:
                new_client = Client(uid, name)
            except device.DoesNotExist:
                Client.srv_process.log("no client with name '{}' found".format(name), logging_tools.LOG_LEVEL_ERROR)
                if name.count("."):
                    s_name = name.split(".")[0]
                    Client.srv_process.log("trying with short name '{}'".format(s_name), logging_tools.LOG_LEVEL_WARN)
                    try:
                        new_client = Client(uid, s_name)
                    except:
                        new_client = None
                    else:
                        Client.srv_process.log("successfull with short name", logging_tools.LOG_LEVEL_WARN)
                else:
                    Client.srv_process.log("trying with name '{}'".format(name), logging_tools.LOG_LEVEL_WARN)
                    try:
                        new_client = Client(uid, name)
                    except:
                        new_client = None
                    else:
                        Client.srv_process.log("successfull with name", logging_tools.LOG_LEVEL_WARN)
            if new_client is not None:
                Client.uuid_set.add(uid)
                Client.name_set.add(name)
                Client.lut[uid] = new_client
                Client.lut[name] = new_client
                Client.lut[name.split(".")[0]] = new_client
                Client.srv_process.log("added client {} ({})".format(name, uid))
                found = False
                _keys = list(Client.CS.keys())
                for _key in _keys:
                    _client = Client.CS[_key]
                    if _client["name"] == name:
                        found = True
                        if _client["uuid"] != uid:
                            _client["uuid"] = uid
                            Client.CS[_key] = _client
                            Client.CS.write()
                        break
                if not found:
                    if len(_keys):
                        _new_idx = "{:d}".format(max([int(_val) for _val in _keys]) + 1)
                    else:
                        _new_idx = "0"
                    Client.CS[_new_idx] = {
                        "name": name,
                        "uuid": uid,
                    }
                    Client.CS.write()

    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.create_logger()
        self.__log_template.log(level, what)

    def send_reply(self, srv_com):
        self.srv_process.send_reply(self.uid, srv_com)

    def __unicode__(self):
        return "{} ({})".format(
            self.name,
            self.uid
        )

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
            if global_config["SUPPORT_OLD_CLIENTS"]:
                try:
                    if new_vers.count("-"):
                        major, minor = new_vers.split("-")[0].split(".")
                        if (int(major) >= 3 and int(minor) >= 1) or (int(major) == 2):
                            self.__client_gen = 1
                except:
                    self.log("cannot interpret version '{}'".format(new_vers))
            else:
                self.__client_gen = 1
            self.log(
                "changed version from '{}' to '{}' (generation {:d})".format(
                    self.__version,
                    new_vers,
                    self.__client_gen,
                )
            )
            self.__version = new_vers
            self._modify_device_variable(
                PACKAGE_VERSION_VAR_NAME,
                "actual version of the client",
                "s",
                self.__version
            )

    def _expand_var(self, var):
        return var.replace("%{ROOT_IMPORT_DIR}", global_config["ROOT_IMPORT_DIR"])

    def _get_package_list(self, srv_com):
        _kernels = self.device.kerneldevicehistory_set.all()
        if _kernels.count():
            cur_kernel = _kernels[0].kernel
        else:
            cur_kernel = None
        _images = self.device.imagedevicehistory_set.all()
        if _images.count():
            cur_image = _images[0].image
        else:
            cur_image = None
        pdc_list = package_device_connection.objects.filter(
            Q(device=self.device)
        ).prefetch_related(
            "kernel_list", "image_list"
        ).select_related(
            "package",
            "package__target_repo"
        )
        # send to client
        send_list = []
        # pre-delete list
        pre_delete_list = []
        for cur_pdc in pdc_list:
            take = True
            pre_delete = False
            if cur_pdc.image_dep:
                if cur_image not in cur_pdc.image_list.all():
                    self.log(
                        "appending package '{}' to pre-delete list because image '{}' not in image_list '{}'".format(
                            str(cur_pdc.package),
                            str(cur_image),
                            ", ".join([str(_v) for _v in cur_pdc.image_list.all()]),
                        )
                    )
                    pre_delete = True
                    take = False
            if cur_pdc.kernel_dep:
                if cur_kernel not in cur_pdc.kernel_list.all():
                    self.log(
                        "appending package '{}' to pre-delete list because kernel '{}' not in kernel_list '{}'".format(
                            str(cur_pdc.package),
                            str(cur_kernel),
                            ", ".join([str(_v) for _v in cur_pdc.kernel_list.all()]),
                        )
                    )
                    pre_delete = True
                    take = False
            if pre_delete:
                pre_delete_list.append(cur_pdc)
            if take:
                send_list.append(cur_pdc)
        self.log(
            "{} in source list, {} in send_list, {} in pre-delete list".format(
                logging_tools.get_plural("package", len(pdc_list)),
                logging_tools.get_plural("package", len(send_list)),
                logging_tools.get_plural("package", len(pre_delete_list)),
            )
        )
        if self.__client_gen == 1:
            # new generation
            _pre_del_xml = etree.fromstring(
                XMLRenderer().render(
                    package_device_connection_wp_serializer(pre_delete_list, many=True).data
                ).encode("utf-8")
            )
            resp = etree.fromstring(
                XMLRenderer().render(
                    package_device_connection_wp_serializer(send_list, many=True).data
                ).encode("utf-8")
            )
            for _entry in resp:
                _entry.append(E.pre_delete("False"))
            if len(_pre_del_xml):
                for _entry in _pre_del_xml:
                    _entry.append(E.pre_delete("True"))
                    # insert at top of the list
                    resp.insert(0, _entry)
        else:
            resp = srv_com.builder(
                "packages",
                # we don't support pre_delete
                *[cur_pdc.get_xml(with_package=True) for cur_pdc in send_list]
            )
        srv_com["package_list"] = resp

    def _get_repo_list(self, srv_com):
        repo_list = package_repo.objects.filter(Q(publish_to_nodes=True))
        send_ok = [cur_repo for cur_repo in repo_list if cur_repo.distributable]
        self.log(
            "{}, {:d} to send".format(
                logging_tools.get_plural("publish repo", len(repo_list)),
                len(send_ok),
            )
        )
        if self.__client_gen == 1:
            resp = etree.fromstring(
                XMLRenderer().render(
                    package_repo_serializer(send_ok, many=True).data
                ).encode("utf-8")
            )
        else:
            resp = srv_com.builder(
                "repos",
                *[cur_repo.get_xml() for cur_repo in send_ok]
            )
        srv_com["repo_list"] = resp

    def _package_info(self, srv_com):
        pdc_xml = srv_com.xpath(".//package_device_connection", smart_strings=False)[0]
        info_xml = srv_com.xpath(".//result|.//main_result", smart_strings=False)
        if len(info_xml):
            info_xml = info_xml[0]
            _pk = pdc_xml.attrib["pk"]
            try:
                cur_pdc = package_device_connection.objects.select_related("package").get(Q(pk=_pk))
            except package_device_connection.DoesNotExist:
                self.log("pdc with pk={} does not exist".format(_pk), logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_pdc.response_type = pdc_xml.attrib["response_type"]
                self.log("got package_info for {} (type is {})".format(str(cur_pdc.package), cur_pdc.response_type))
                cur_pdc.response_str = etree.tostring(info_xml)
                # print cur_pdc.response_str
                cur_pdc.interpret_response()
                cur_pdc.save(
                    update_fields=[
                        "response_type", "response_str", "installed", "install_time",
                        "installed_name", "installed_version", "installed_release"
                    ]
                )
        else:
            self.log("got package_info without result", logging_tools.LOG_LEVEL_WARN)

    def new_command(self, srv_com):
        s_time = time.time()
        self.__last_contact = s_time
        cur_com = srv_com["command"].text
        if "result" in srv_com:
            try:
                _log_str, _log_level = srv_com.get_log_tuple()
            except KeyError:
                self.log(
                    "some keys missing in result-node ({}): {}".format(
                        cur_com,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                return None
            else:
                if _log_level > logging_tools.LOG_LEVEL_WARN:
                    # to stop avalance of new_config
                    self.log("got '{}' for {}".format(_log_str, cur_com), _log_level)
                    return None
        if "package_client_version" in srv_com:
            self._set_version(srv_com["package_client_version"].text)
        self._modify_device_variable(LAST_CONTACT_VAR_NAME, "last contact of the client", "d", datetime.datetime(*time.localtime()[0:6]))
        srv_com.update_source()
        if cur_com == "get_package_list":
            srv_com["command"] = "package_list"
            self._get_package_list(srv_com)
        elif cur_com == "get_repo_list":
            srv_com["command"] = "repo_list"
            self._get_repo_list(srv_com)
        elif cur_com == "package_info":
            self._package_info(srv_com)
            srv_com = None
        else:
            srv_com.set_result(
                "unknown package-client command '{}'".format(
                    cur_com
                ),
                server_command.SRV_REPLY_STATE_ERROR
            )
            self.log(
                "unknown command '{}'".format(cur_com),
                logging_tools.LOG_LEVEL_ERROR
            )
        return srv_com
