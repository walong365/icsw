# Copyright (C) 2001-2015 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" install process structures """

from lxml import etree  # @UnresolvedImport
import urlparse
import os

from lxml.builder import E

from initat.package_install.client.command import simple_command
from initat.package_install.client.config import global_config
from initat.client_version import VERSION_STRING
from initat.tools import logging_tools, process_tools, threading_tools, config_store, server_command

RPM_QUERY_FORMAT = "%{NAME}\n%{INSTALLTIME}\n%{VERSION}\n%{RELEASE}\n"


def get_repo_str(_type, in_repo):
    def get_url(in_repo):
        _url = in_repo.findtext("url")
        _username = in_repo.findtext("username")
        _password = in_repo.findtext("password")
        if _username:
            _parsed = urlparse.urlparse(_url)
            _url = "{}://{}:{}@{}{}".format(
                _parsed.scheme,
                _username,
                _password,
                _parsed.netloc,
                _parsed.path,
            )
        return _url

    if _type == "zypper":
        # copy from initat.cluster.backbone.models.package_repo.repo_str
        _vf = [
            "[{}]".format(in_repo.findtext("alias")),
            "name={}".format(in_repo.findtext("name")),
            "enabled={:d}".format(1 if in_repo.findtext("enabled") == "True" else 0),
            "autorefresh={:d}".format(1 if in_repo.findtext("autorefresh") == "True" else 0),
            "baseurl={}".format(get_url(in_repo)),
            "type={}".format(in_repo.findtext("repo_type") or "NONE"),
        ]
        if in_repo.findtext("priority"):
            _vf.append("priority={:d}".format(int(in_repo.findtext("priority"))))
        if in_repo.findtext("service_name"):
            _vf.append("service={}".format(in_repo.findtext("service_name")))
        else:
            _vf.append("keeppackages=0")
        _vf.append("")
    elif _type == "deb":
        _vf = [
            "deb {} {} {}".format(
                get_url(in_repo),
                in_repo.findtext("deb_distribution"),
                in_repo.findtext("deb_components"),
            )
        ]
    else:
        # yum repository
        _vf = [
            "[{}]".format(in_repo.findtext("name").replace("/", "_")),
            "name={}".format(in_repo.findtext("alias")),
            "enabled={:d}".format(1 if in_repo.findtext("enabled") == "True" else 0),
            "autorefresh={:d}".format(1 if in_repo.findtext("autorefresh") == "True" else 0),
            "baseurl={}".format(get_url(in_repo)),
            "type={}".format(in_repo.findtext("repo_type") or "NONE"),
        ]
        if in_repo.findtext("priority"):
            _vf.append("priority={:d}".format(int(in_repo.findtext("priority"))))
        if in_repo.findtext("service_name"):
            _vf.append("service={}".format(in_repo.findtext("service_name")))
        else:
            _vf.append("keeppackages=0")
        _vf.append("")
    return "\n".join(_vf)


def get_srv_command(**kwargs):
    return server_command.srv_command(
        package_client_version=VERSION_STRING,
        debian="1" if global_config["DEBIAN"] else "0",
        **kwargs
    )


class InstallProcess(threading_tools.process_obj):
    """ handles all install and external command stuff """
    def __init__(self, name):
        threading_tools.process_obj.__init__(
            self,
            name,
            loop_timer=1000.0
        )
        self.commands = []
        self.register_func("command_batch", self._command_batch)
        # commands pending becaus of missing package list
        self.pending_commands = []
        # list of pending package commands
        self.package_commands = []
        self.register_timer(self._check_commands, 10)

    @property
    def packages(self):
        return self._packages

    @packages.setter
    def packages(self, in_list):
        self._packages = in_list
        self.packages_valid = True
        self.handle_pending_commands()

    @packages.deleter
    def packages(self):
        if self.packages_valid:
            self.packages_valid = False
            del self._packages

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        self.CS = config_store.ConfigStore("client", self.log)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _command_batch(self, com_list, *args, **kwargs):
        com_list = [server_command.srv_command(source=cur_com) for cur_com in com_list]
        self.pending_commands.extend(com_list)
        self.handle_pending_commands()

    def send_to_server(self, send_xml, info_str="no info"):
        self.send_pool_message("send_to_server", send_xml["command"].text, unicode(send_xml), info_str)

    def package_command_done(self, t_com):
        self.package_commands.remove(t_com)
        self.handle_pending_commands()

    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.set_loop_timer(1000)

    def _process_commands(self):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        # check if any commands are pending
        not_init = [cur_com for cur_com in self.package_commands if not int(cur_com.get("init"))]
        if not_init:
            cur_init = not_init[0]
            cur_init.attrib["init"] = "1"
            # delete pre/post command strings
            pp_attrs = ["pre_command", "post_command"]
            for pp_attr in pp_attrs:
                if pp_attr in cur_init.attrib:
                    del cur_init.attrib[pp_attr]
            self.build_command(cur_init)
            pc_set = False
            for pp_attr in pp_attrs:
                if pp_attr in cur_init.attrib:
                    pc_set = True
                    self.log(" {} is '{}'".format(pp_attr, cur_init.attrib[pp_attr].replace("\n", "\\n")))
            # only do something if a pre_command ist set
            if pc_set:
                simple_command(
                    cur_init.attrib["pre_command"],
                    short_info="package",
                    done_func=self._command_done,
                    log_com=self.log,
                    info="install package",
                    command_stage="pre",
                    data=cur_init
                )
            else:
                cur_init.append(E.main_result(E.info("nothing to do")))
                self.pdc_done(cur_init)
        else:
            # check for pending commands
            self.handle_pending_commands()

    def _command_done(self, hc_sc):
        cur_out = hc_sc.read()
        self.log("hc_com '{}' (stage {}) finished with stat {:d} ({:d} bytes)".format(
            hc_sc.com_str.replace("\n", "\\n"),
            hc_sc.command_stage,
            hc_sc.result,
            len(cur_out)))
        for line_num, line in enumerate(cur_out.split("\n")):
            self.log(" {:3d} {}".format(line_num + 1, line))
        hc_sc.terminate()
        if cur_out.startswith("<?xml") and hc_sc.command_stage == "main":
            try:
                xml_out = etree.fromstring(cur_out)  # @UndefinedVariable
            except:
                self.log(
                    "error parsing XML string ({:d} bytes, first 100: '{}'): {}".format(
                        len(cur_out),
                        cur_out[:100],
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                xml_out = E.stdout(cur_out)
        else:
            # todo: transform output to XML for sending back to server
            # pre and post commands
            xml_out = E.stdout(cur_out)
        # store in xml
        hc_sc.data.append(getattr(E, "{}_result".format(hc_sc.command_stage))(xml_out))
        # print "***", hc_sc.command_stage
        if hc_sc.data.tag == "package_device_connection":
            # only send something back for package_device_connection commands
            if hc_sc.command_stage == "pre":
                self.log("pre-command finished, deciding what to do")
                post_present = "post_command" in hc_sc.data.attrib
                if post_present:
                    send_return = self._pre_decide(hc_sc, cur_out.strip())
                else:
                    self.log("nothing to do, sending return")
                    hc_sc.data.append(E.main_result())
                    send_return = True
            elif hc_sc.command_stage == "main":
                send_return = False
                post_present = "post_command" in hc_sc.data.attrib
                if post_present:
                    simple_command(
                        hc_sc.data.attrib["post_command"],
                        short_info="package",
                        done_func=self._command_done,
                        log_com=self.log,
                        info="install package",
                        command_stage="post",
                        data=hc_sc.data
                    )
            elif hc_sc.command_stage == "post":
                # self._post_decide(hc_sc, cur_out.strip())
                send_return = True
            if send_return:
                # remove from package_commands
                self.pdc_done(hc_sc.data)
        else:
            # remove other commands (for instance refresh)
            new_list = [cur_com for cur_com in self.package_commands if cur_com != hc_sc.data]
            self.package_commands = new_list
            self._process_commands()
        del hc_sc

    def pdc_done(self, cur_pdc):
        self.log("pdc done")
        keep_pdc = False
        # print etree.tostring(cur_pdc, pretty_print=True)
        if cur_pdc.find("main_result") is not None:
            xml_info = cur_pdc.find("main_result")
            if cur_pdc.find("pre_result") is not None:
                xml_info.append(cur_pdc.find("pre_result"))
            if cur_pdc.find("post_result") is not None:
                xml_info.append(cur_pdc.find("post_result"))
            # print "+++++", xml_info
            # check for out-of date repositories
            # this code makes no sense for flat-text responses
            warn_text = (" ".join([cur_el.text for cur_el in xml_info.findall(".//message[@type='warning']")])).strip().lower()
            info_text = (" ".join([cur_el.text for cur_el in xml_info.findall(".//message[@type='info']")])).strip().lower()
            if info_text.count("already installed"):
                pass
            elif warn_text.count("outdated") and not len(xml_info.findall(".//to-install")):
                if int(cur_pdc.get("retry_count", "0")) > 2:
                    self.log("retried too often, ingoring warning", logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("repository is outdated, forcing refresh and keeping pdc", logging_tools.LOG_LEVEL_WARN)
                    keep_pdc = True
                    cur_pdc.attrib["init"] = "0"
                    cur_pdc.attrib["retry_count"] = "{:d}".format(int(cur_pdc.attrib["retry_count"]) + 1)
                    self.package_commands.insert(0, E.special_command(send_return="0", command="refresh", init="0"))
            cur_pdc.attrib["response_type"] = self.response_type
        else:
            cur_pdc.attrib["response_type"] = "unknown"
        if int(cur_pdc.attrib["send_return"]):
            srv_com = server_command.srv_command(
                command="package_info",
                info=cur_pdc)
            self.send_to_server(srv_com)
        if not keep_pdc:
            # remove pdc
            new_list = [cur_com for cur_com in self.package_commands if cur_com != cur_pdc]
            self.package_commands = new_list
        self._process_commands()

    def handle_pending_commands(self):
        while self.pending_commands and not self.package_commands:
            # now the fun starts, we have a list of commands and a valid local package list
            first_com = self.pending_commands.pop(0)
            cur_com = first_com["command"].text
            self.log("try to handle {}".format(cur_com))
            if cur_com in ["repo_list"]:
                self._handle_repo_list(first_com)
                self._process_commands()
            elif cur_com in ["clear_cache"]:
                self._clear_cache()
                self._process_commands()
            elif cur_com in ["package_list"]:
                # print first_com.pretty_print()
                _added = 0
                if len(first_com.xpath(".//ns:package_list/root/list-item")):
                    # clever enqueue ? FIXME
                    for _cur_pdc in first_com.xpath(".//ns:package_list/root/list-item"):
                        # rewrite
                        # print etree.tostring(_cur_pdc, pretty_print=True)
                        cur_pdc = E.package_device_connection()
                        for entry in _cur_pdc:
                            if entry.tag in ["target_state", "installed", "device", "idx"]:
                                cur_pdc.attrib[entry.tag] = entry.text or ""
                                if entry.tag == "idx":
                                    cur_pdc.attrib["pk"] = entry.text or ""
                            elif entry.tag in ["force_flag", "nodeps_flag", "pre_delete"]:
                                cur_pdc.attrib[entry.tag] = "1" if entry.text.lower() in ["true"] else "0"
                            else:
                                # ignore the rest
                                # print "ignore: %s='%s'" % (entry.tag, entry.text)
                                pass
                        package = E.package()
                        for entry in _cur_pdc.find("package"):
                            if entry.tag in ["name", "version", "idx", "package_repo", "device", "target_repo_name"]:
                                package.attrib[entry.tag] = entry.text or ""
                            elif entry.tag in ["always_latest"]:
                                package.attrib[entry.tag] = "1" if entry.text.lower() in ["true"] else "0"
                            else:
                                # ignore the rest
                                # print "ignore: %s='%s'" % (entry.tag, entry.text)
                                pass
                        cur_pdc.append(package)
                        # set flag to not init
                        cur_pdc.attrib["init"] = "0"
                        # flag to send return to server
                        cur_pdc.attrib["send_return"] = "1"
                        # retry count
                        cur_pdc.attrib["retry_count"] = "0"
                        _added += 1
                        self.package_commands.append(cur_pdc)
                    self.log(
                        "{} present (added {:d})".format(
                            logging_tools.get_plural("package command", len(self.package_commands)),
                            _added,
                        )
                    )
                    self._process_commands()
                else:
                    self.log("empty package_list, removing")
            else:
                self.log("unknown command '{}', ignoring...".format(cur_com), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log(
                "handle_pending_commands: {:d} pending, {:d} package".format(
                    len(self.pending_commands),
                    len(self.package_commands)
                )
            )

    def get_always_latest(self, pack_xml):
        return int(pack_xml.attrib.get("always_latest", "0"))

    def package_name(self, pack_xml):
        if self.get_always_latest(pack_xml):
            return pack_xml.attrib["name"]
        else:
            return "{}-{}".format(
                pack_xml.attrib["name"],
                pack_xml.attrib["version"],
            )

    def _clear_cache(self):
        self.package_commands.append(E.special_command(send_return="0", command="refresh", init="0"))


class DebianInstallProcess(InstallProcess):
    response_type = "debian_flat"

    def _read_file(self, f_name):
        return [
            line.strip() for line in file(f_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")
        ]

    def _handle_repo_list(self, in_com):
        # print etree.tostring(in_com.tree, pretty_print=True)
        # new code
        in_repos = in_com.xpath(".//ns:repo_list/root")
        if not len(in_repos):
            self.log("no repo_list found in srv_com, server too old ?", logging_tools.LOG_LEVEL_ERROR)
            return
        in_repos = in_repos[0]
        self.log("handling repo_list ({})".format(logging_tools.get_plural("entry", len(in_repos))))

        _src_list_dir = "/etc/apt"
        _f_list = [os.path.join(_src_list_dir, "sources.list")]
        _src_list = self._read_file(os.path.join(_src_list_dir, "sources.list"))
        _sub_dir = os.path.join(_src_list_dir, "sources.list.d")
        if os.path.isdir(_sub_dir):
            for entry in os.listdir(_sub_dir):
                _path = os.path.join(_sub_dir, entry)
                _f_list.append(_path)
                _src_list.extend(self._read_file(_path))

        self.log(
            "{} found in and below {}".format(
                logging_tools.get_plural("repository", len(_src_list)),
                _src_list_dir,
            )
        )

        # _new_repo_names = in_repos.xpath(".//package_repo/@alias")
        _new_repo_names = in_repos.xpath(".//alias/text()")
        new_repo_list = [get_repo_str("deb", in_repo) for in_repo in in_repos]
        rewrite_repos = True
        if rewrite_repos and self.CS["pc.modify.repos"]:
            self.log("rewritting repo files")
            # remove old ones
            for old_f_name in _f_list:
                try:
                    os.unlink(old_f_name)
                except:
                    self.log("cannot remove {}: {}".format(old_f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removed {}".format(old_f_name))
            f_name = "/etc/apt/sources.list"
            file(f_name, "w").write("\n".join(new_repo_list + [""]))
            self.log("created {}".format(f_name))
            self._clear_cache()


class YumInstallProcess(InstallProcess):
    response_type = "yum_flat"

    def build_command(self, cur_pdc):
        # print etree.tostring(cur_pdc, pretty_print=True)
        if cur_pdc.tag == "special_command":
            if cur_pdc.attrib["command"] == "refresh":
                cur_pdc.attrib["pre_command"] = "/usr/bin/yum -y clean all ; /usr/bin/yum -y makecache"
        else:
            if cur_pdc.attrib["target_state"] == "keep":
                # nothing to do
                pass
            else:
                pack_xml = cur_pdc[0]
                # yum_com = {"install" : "install",
                #           "upgrade" : "update",
                #           "erase"   : "erase"}.get(cur_pdc.attrib["target_state"])
                # yum_com = "/usr/bin/yum -y %s %s-%s" % (
                #    yum_com,
                #    pack_xml.attrib["name"],
                #    pack_xml.attrib["version"],
                # )
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q {} --queryformat=\"{}\"".format(self.package_name(pack_xml), RPM_QUERY_FORMAT)
                cur_pdc.attrib["post_command"] = "/bin/rpm -q {} --queryformat=\"{}\"".format(self.package_name(pack_xml), RPM_QUERY_FORMAT)

    def _pre_decide(self, hc_sc, cur_out):
        cur_pdc = hc_sc.data
        is_installed = False if cur_out.count("is not installed") else True
        self.log(
            "installed flag from '{}': {}".format(
                cur_out,
                str(is_installed),
            )
        )
        pack_xml = cur_pdc[0]
        yum_com = {
            "install": "install",
            "upgrade": "update",
            "erase": "erase"
        }.get(cur_pdc.attrib["target_state"])
        options = {
            "install": "--nogpgcheck",
            "upgrade": "--nogpgcheck",
            "erase": "",
        }.get(cur_pdc.attrib["target_state"])
        package_name = self.package_name(pack_xml)
        always_latest = self.get_always_latest(pack_xml)
        if (is_installed and yum_com in ["install", "upgrade"]) or (not is_installed and yum_com in ["erase"]):
            self.log("doing nothing, running post_command")
            if is_installed:
                cur_pdc.append(
                    E.main_result(
                        E.stdout("package {} is installed".format(package_name))
                    )
                )
            else:
                cur_pdc.append(
                    E.main_result(
                        E.stdout("package {} is not installed".format(package_name))
                    )
                )
            return True
        else:
            if not is_installed and yum_com == "update" and always_latest:
                yum_com = "install"
                self.log("changing yum_com to '{}' (always_latest flag)".format(yum_com), logging_tools.LOG_LEVEL_WARN)
            self.log("starting action '{}'".format(yum_com))
            yum_com = "/usr/bin/yum -y {} {} {}".format(
                yum_com,
                package_name,
                options,
            )
            simple_command(
                yum_com,
                short_info="package",
                done_func=self._command_done,
                command_stage="main",
                log_com=self.log,
                info="handle package",
                data=cur_pdc
            )
            # return False, None

    def _handle_repo_list(self, in_com):
        # print etree.tostring(in_com.tree, pretty_print=True)
        in_repos = in_com.xpath(".//ns:repo_list/root")[0]
        self.log("handling repo_list ({})".format(logging_tools.get_plural("entry", len(in_repos))))
        # manual comparision, better modify them with zypper, FIXME ?
        repo_dir = "/etc/yum.repos.d"
        cur_repo_names = [entry[:-5] for entry in os.listdir(repo_dir) if entry.endswith(".repo")]
        self.log(
            "{} found in {}".format(
                logging_tools.get_plural("repository", len(cur_repo_names)),
                repo_dir
            )
        )
        # _new_repo_names = in_repos.xpath(".//package_repo/@alias")
        _new_repo_names = in_repos.xpath(".//alias/text()")
        old_repo_dict = {f_name: file(os.path.join(repo_dir, "{}.repo".format(f_name)), "r").read() for f_name in cur_repo_names}
        new_repo_dict = {in_repo.findtext("name").replace("/", "_"): get_repo_str("yum", in_repo) for in_repo in in_repos}
        rewrite_repos = False
        if any([old_repo_dict[name] != new_repo_dict[name] for name in set(cur_repo_names) & set(new_repo_dict.keys())]):
            self.log("repository content differs, forcing rewrite")
            rewrite_repos = True
        elif set(cur_repo_names) ^ set(new_repo_dict.keys()):
            self.log("list of old and new repositories differ, forcing rewrite")
            rewrite_repos = True
        if rewrite_repos and self.CS["pc.modify.repos"]:
            self.log("rewritting repo files")
            # remove old ones
            for old_r_name in old_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "{}.repo".format(old_r_name))
                try:
                    os.unlink(f_name)
                except:
                    self.log("cannot remove {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removed {}".format(f_name))
            for new_r_name in new_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "{}.repo".format(new_r_name))
                try:
                    file(f_name, "w").write(new_repo_dict[new_r_name])
                except:
                    self.log("cannot create {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("created {}".format(f_name))
            self._clear_cache()


class ZypperInstallProcess(InstallProcess):
    response_type = "zypper_xml"

    def build_command(self, cur_pdc):
        # print etree.tostring(cur_pdc, pretty_print=True)
        if cur_pdc.tag == "special_command":
            if cur_pdc.attrib["command"] == "refresh":
                cur_pdc.attrib["pre_command"] = "/usr/bin/zypper -q -x --gpg-auto-import-keys refresh -f"
            else:
                self.log("unknown special command '{}'".format(cur_pdc.attrib["command"]), logging_tools.LOG_LEVEL_ERROR)
        else:
            pack_xml = cur_pdc[0]
            if cur_pdc.attrib["target_state"] == "keep":
                # just check install state
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q {} --queryformat=\"{}\"".format(self.package_name(pack_xml), RPM_QUERY_FORMAT)
            else:
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q {} --queryformat=\"{}\"".format(self.package_name(pack_xml), RPM_QUERY_FORMAT)
                cur_pdc.attrib["post_command"] = "/bin/rpm -q {} --queryformat=\"{}\"".format(self.package_name(pack_xml), RPM_QUERY_FORMAT)

    def _pre_decide(self, hc_sc, cur_out):
        _stage = hc_sc.command_stage
        cur_pdc = hc_sc.data
        is_installed = False if cur_out.count("is not installed") else True
        cur_pdc.attrib["pre_installed"] = "1" if is_installed else "0"
        cur_pdc.attrib["pre_zypper_com"] = ""
        pack_xml = cur_pdc[0]
        package_name = self.package_name(pack_xml)
        always_latest = self.get_always_latest(pack_xml)
        self.log(
            "installed flag from '{}': {}, target state is '{}', always_latest is '{}'".format(
                cur_out,
                str(is_installed),
                cur_pdc.attrib["target_state"],
                str(always_latest),
            )
        )
        zypper_com = {
            "install": "in",
            "upgrade": "up",
            "erase": "rm",
        }.get(cur_pdc.attrib["target_state"])
        # o already installed and cmd == in
        # o already installed and cmd == up and always_latest flag not set
        # o not installed and cmd == rm
        if (is_installed and zypper_com in ["in"]) or (
            is_installed and zypper_com in ["up"] and not always_latest
        ) or (not is_installed and zypper_com in ["rm"]):
            self.log("doing nothing")
            if is_installed:
                cur_pdc.append(
                    E.main_result(
                        E.stdout("package {} is installed".format(package_name))
                    )
                )
            else:
                cur_pdc.append(
                    E.main_result(
                        E.stdout("package {} is not installed".format(package_name))
                    )
                )
            return True
        else:
            if not is_installed and zypper_com == "up" and always_latest:
                zypper_com = "in"
                self.log("changing zypper_com to '{}' (always_latest flag)".format(zypper_com), logging_tools.LOG_LEVEL_WARN)
            self.log("starting action '{}'".format(zypper_com))
            cur_pdc.attrib["pre_zypper_com"] = zypper_com
            if pack_xml.attrib["target_repo_name"]:
                _repo_filter = "-r '{}'".format(pack_xml.attrib["target_repo_name"])
            else:
                _repo_filter = ""
            # flags: xml output, non-interactive
            zypper_com = "/usr/bin/zypper -x -n {} {} {} {}".format(
                zypper_com,
                _repo_filter,
                "-f" if (int(cur_pdc.attrib["force_flag"]) and zypper_com not in ["rm"]) else "",
                package_name,
            )
            simple_command(
                zypper_com,
                short_info="package",
                done_func=self._command_done,
                command_stage="main",
                log_com=self.log,
                info="handle package",
                data=cur_pdc
            )
            return False

    def _handle_repo_list(self, in_com):
        # print etree.tostring(in_com.tree, pretty_print=True)
        # new code
        in_repos = in_com.xpath(".//ns:repo_list/root")
        if not len(in_repos):
            self.log("no repo_list found in srv_com, server too old ?", logging_tools.LOG_LEVEL_ERROR)
            return
        in_repos = in_repos[0]
        self.log("handling repo_list ({})".format(logging_tools.get_plural("entry", len(in_repos))))
        # manual comparision, better modify them with zypper, FIXME ?
        repo_dir = "/etc/zypp/repos.d"
        cur_repo_names = [entry[:-5] for entry in os.listdir(repo_dir) if entry.endswith(".repo")]
        self.log("{} found in {}".format(
            logging_tools.get_plural("repository", len(cur_repo_names)),
            repo_dir))
        # _new_repo_names = in_repos.xpath(".//package_repo/@alias")
        _new_repo_names = in_repos.xpath(".//alias/text()")
        old_repo_dict = {f_name: file(os.path.join(repo_dir, "{}.repo".format(f_name)), "r").read() for f_name in cur_repo_names}
        new_repo_dict = {in_repo.findtext("alias"): get_repo_str("zypper", in_repo) for in_repo in in_repos}
        rewrite_repos = False
        if any([old_repo_dict[name] != new_repo_dict[name] for name in set(cur_repo_names) & set(new_repo_dict.keys())]):
            self.log("repository content differs, forcing rewrite")
            rewrite_repos = True
        elif set(cur_repo_names) ^ set(new_repo_dict.keys()):
            self.log("list of old and new repositories differ, forcing rewrite")
            rewrite_repos = True
        if rewrite_repos and self.CS["pc.modify.repos"]:
            self.log("rewritting repo files")
            # remove old ones
            for old_r_name in old_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "{}.repo".format(old_r_name))
                try:
                    os.unlink(f_name)
                except:
                    self.log("cannot remove {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removed {}".format(f_name))
            for new_r_name in new_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "{}.repo".format(new_r_name))
                try:
                    file(f_name, "w").write(new_repo_dict[new_r_name])
                except:
                    self.log("cannot create {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("created {}".format(f_name))
            self._clear_cache()
