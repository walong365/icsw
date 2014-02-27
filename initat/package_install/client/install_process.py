#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2014 Andreas Lang-Nevyjel
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

from initat.package_install.client.command import simple_command
from initat.package_install.client.config import global_config, VERSION_STRING
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import logging_tools
import os
import process_tools
import server_command
import threading_tools

RPM_QUERY_FORMAT = "%{NAME}\n%{INSTALLTIME}\n%{VERSION}\n%{RELEASE}\n"

def get_repo_str(in_repo):
    # copy from initat.cluster.backbone.models.package_repo.repo_str
    _vf = [
        "[%s]" % (in_repo.findtext("alias")),
        "name=%s" % (in_repo.findtext("name")),
        "enabled=%d" % (1 if in_repo.findtext("enabled") == "True" else 0),
        "autorefresh=%d" % (1 if in_repo.findtext("autorefresh") == "True" else 0),
        "baseurl=%s" % (in_repo.findtext("url")),
        "type=%s" % (in_repo.findtext("repo_type") or "NONE"),
    ]
    if in_repo.findtext("service_name"):
        _vf.append("service=%s" % (in_repo.findtext("service_name")))
    else:
        _vf.append("keeppackages=0")
    _vf.append("")
    return "\n".join(_vf)

def get_srv_command(**kwargs):
    return server_command.srv_command(
        package_client_version=VERSION_STRING,
        debian="1" if global_config["DEBIAN"] else "0",
        **kwargs)

class install_process(threading_tools.process_obj):
    """ handles all install and external command stuff """
    def __init__(self, name):
        threading_tools.process_obj.__init__(
            self,
            name,
            loop_timer=1000.0)
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
            zmq_debug=global_config["ZMQ_DEBUG"],
            context=self.zmq_context,
            init_logger=True)
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
                    self.log(" %s is '%s'" % (pp_attr, cur_init.attrib[pp_attr].replace("\n", "\\n")))
            # only do something if a pre_command ist set
            if pc_set:
                simple_command(
                    cur_init.attrib["pre_command"],
                    short_info="package",
                    done_func=self._command_done,
                    log_com=self.log,
                    info="install package",
                    command_stage="pre",
                    data=cur_init)
            else:
                cur_init.append(E.main_result(E.info("nothing to do")))
                self.pdc_done(cur_init)
        else:
            # check for pending commands
            self.handle_pending_commands()
    def _command_done(self, hc_sc):
        cur_out = hc_sc.read()
        self.log("hc_com '%s' (stage %s) finished with stat %d (%d bytes)" % (
            hc_sc.com_str.replace("\n", "\\n"),
            hc_sc.command_stage,
            hc_sc.result,
            len(cur_out)))
        for line_num, line in enumerate(cur_out.split("\n")):
            self.log(" %3d %s" % (line_num + 1, line))
        hc_sc.terminate()
        if cur_out.startswith("<?xml") and hc_sc.command_stage == "main":
            xml_out = etree.fromstring(cur_out)
        else:
            # todo: transform output to XML for sending back to server
            # pre and post commands
            xml_out = E.stdout(cur_out)
        # store in xml
        hc_sc.data.append(getattr(E, "%s_result" % (hc_sc.command_stage))(xml_out))
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
                        data=hc_sc.data)
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
                    cur_pdc.attrib["retry_count"] = "%d" % (int(cur_pdc.attrib["retry_count"]) + 1)
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
            self.log("try to handle %s" % (cur_com))
            if cur_com in ["send_info"]:
                self.log("... ignoring", logging_tools.LOG_LEVEL_WARN)
            elif cur_com in ["repo_list"]:
                self._handle_repo_list(first_com)
                self._process_commands()
            elif cur_com in ["package_list"]:
                # print first_com.pretty_print()
                if len(first_com.xpath(".//ns:package_list/root/list-item")):
                    # clever enqueue ? FIXME
                    for _cur_pdc in first_com.xpath(".//ns:package_list/root/list-item"):
                        # rewrite
                        cur_pdc = E.package_device_connection()
                        for entry in _cur_pdc:
                            if entry.tag in ["target_state", "installed", "device", "idx"]:
                                cur_pdc.attrib[entry.tag] = entry.text or ""
                                if entry.tag == "idx":
                                    cur_pdc.attrib["pk"] = entry.text or ""
                            elif entry.tag in ["force_flag", "nodeps_flag"]:
                                cur_pdc.attrib[entry.tag] = "1" if entry.text.lower() in ["true"] else "0"
                            else:
                                # ignore the rest
                                # print "ignore: %s='%s'" % (entry.tag, entry.text)
                                pass
                        package = E.package()
                        for entry in _cur_pdc.find("package"):
                            if entry.tag in ["name", "version", "idx", "package_repo", "device"]:
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
                        self.package_commands.append(cur_pdc)
                    self.log(logging_tools.get_plural("package command", len(self.package_commands)))
                    self._process_commands()
                else:
                    self.log("empty package_list, removing")
            else:
                self.log("unknown command '%s', ignoring..." % (cur_com), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("handle_pending_commands: %d pending, %d package" % (
                len(self.pending_commands),
                len(self.package_commands)))
    def get_always_latest(self, pack_xml):
        return int(pack_xml.attrib.get("always_latest", "0"))
    def package_name(self, pack_xml):
        if self.get_always_latest(pack_xml):
            return pack_xml.attrib["name"]
        else:
            return "%s-%s" % (
                pack_xml.attrib["name"],
                pack_xml.attrib["version"],
            )

class yum_install_process(install_process):
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
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q %s --queryformat=\"%s\"" % (self.package_name(pack_xml), RPM_QUERY_FORMAT)
                cur_pdc.attrib["post_command"] = "/bin/rpm -q %s --queryformat=\"%s\"" % (self.package_name(pack_xml), RPM_QUERY_FORMAT)
    def _decide(self, hc_sc, cur_out):
        cur_pdc = hc_sc.data
        is_installed = False if cur_out.count("is not installed") else True
        self.log(
            "installed flag from '%s': %s" % (
                cur_out,
                str(is_installed),
                )
            )
        pack_xml = cur_pdc[0]
        yum_com = {"install" : "install",
                   "upgrade" : "update",
                   "erase"   : "erase"}.get(cur_pdc.attrib["target_state"])
        package_name = self.package_name(pack_xml)
        if (is_installed and yum_com in ["install", "upgrade"]) or (not is_installed and yum_com in ["erase"]):
            self.log("doing nothing, running post_command")
            # FIXME, handle post command
            # if is_installed:
            #    return True, E.stdout("package %s is installed" % (package_name))
            # else:
            #    return True, E.stdout("package %s is not installed" % (package_name))
        else:
            self.log("starting action '%s'" % (yum_com))
            yum_com = "/usr/bin/yum -y %s %s" % (
                yum_com,
                package_name,
                )
            simple_command(
                yum_com,
                short_info="package",
                done_func=self._command_done,
                command_stage="main",
                log_com=self.log,
                info="handle package",
                data=cur_pdc)
            # return False, None
    def _handle_repo_list(self, in_com):
        self.log("repo_list handling for yum-based distributions not implemented, FIXME", logging_tools.LOG_LEVEL_ERROR)

class zypper_install_process(install_process):
    response_type = "zypper_xml"
    def build_command(self, cur_pdc):
        # print etree.tostring(cur_pdc, pretty_print=True)
        if cur_pdc.tag == "special_command":
            if cur_pdc.attrib["command"] == "refresh":
                cur_pdc.attrib["pre_command"] = "/usr/bin/zypper -q -x refresh"
        else:
            pack_xml = cur_pdc[0]
            if cur_pdc.attrib["target_state"] == "keep":
                # just check install state
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q %s --queryformat=\"%s\"" % (self.package_name(pack_xml), RPM_QUERY_FORMAT)
            else:
                cur_pdc.attrib["pre_command"] = "/bin/rpm -q %s --queryformat=\"%s\"" % (self.package_name(pack_xml), RPM_QUERY_FORMAT)
                cur_pdc.attrib["post_command"] = "/bin/rpm -q %s --queryformat=\"%s\"" % (self.package_name(pack_xml), RPM_QUERY_FORMAT)
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
            "installed flag from '%s': %s, target state is '%s', always_latest is '%s'" % (
                cur_out,
                str(is_installed),
                cur_pdc.attrib["target_state"],
                str(always_latest),
                )
            )
        zypper_com = {
            "install" : "in",
            "upgrade" : "up",
            "erase"   : "rm",
        }.get(cur_pdc.attrib["target_state"])
        # o already installed and cmd == in
        # o already installed and cmd == up and always_latest flag not set
        # o not installed and cmd == rm
        if (is_installed and zypper_com in ["in"]) or (is_installed and zypper_com in ["up"] and not always_latest) or (not is_installed and zypper_com in ["rm"]):
            self.log("doing nothing")
            if is_installed:
                cur_pdc.append(E.main_result(
                    E.stdout("package %s is installed" % (package_name))
                ))
            else:
                cur_pdc.append(E.main_result(
                    E.stdout("package %s is not installed" % (package_name))
                ))
            return True
        else:
            if not is_installed and zypper_com == "up" and always_latest:
                zypper_com = "in"
                self.log("changing zypper_com to '%s' (always_latest flag)" % (zypper_com), logging_tools.LOG_LEVEL_WARN)
            self.log("starting action '%s'" % (zypper_com))
            cur_pdc.attrib["pre_zypper_com"] = zypper_com
            # flags: xml output, non-interactive
            zypper_com = "/usr/bin/zypper -x -n %s %s %s" % (
                zypper_com,
                "-f" if int(cur_pdc.attrib["force_flag"]) else "",
                package_name,
            )
            simple_command(
                zypper_com,
                short_info="package",
                done_func=self._command_done,
                command_stage="main",
                log_com=self.log,
                info="handle package",
                data=cur_pdc)
            return False
            # return False, None
#     def _post_decide(self, hc_sc, cur_out):
#         _stage = hc_sc.command_stage
#         cur_pdc = hc_sc.data
#         print "***", cur_out, hc_sc.data.attrib
#         # o already installed and cmd == in
#         # o already installed and cmd == up and always_latest flag not set
#         # o not installed and cmd == rm
#         if False:
#             # if is_installed:
#             #    return True, E.stdout("package %s is installed" % (package_name))
#             # else:
#             #    return True, E.stdout("package %s is not installed" % (package_name))
#             pass
#         else:
#             pass
#             # flags: xml output, non-interactive
#             # return False, None
    def _handle_repo_list(self, in_com):
        # print etree.tostring(in_com.tree, pretty_print=True)
        # new code
        in_repos = in_com.xpath(".//ns:repo_list/root")[0]
        # old code
        # in_repos = in_com.xpath(".//ns:repos")[0]
        self.log("handling repo_list (%s)" % (logging_tools.get_plural("entry", len(in_repos))))
        # manual comparision, better modify them with zypper, FIXME ?
        repo_dir = "/etc/zypp/repos.d"
        cur_repo_names = [entry[:-5] for entry in os.listdir(repo_dir) if entry.endswith(".repo")]
        self.log("%s found in %s" % (
            logging_tools.get_plural("repository", len(cur_repo_names)),
            repo_dir))
        # _new_repo_names = in_repos.xpath(".//package_repo/@alias")
        _new_repo_names = in_repos.xpath(".//alias/text()")
        old_repo_dict = dict([(f_name, file(os.path.join(repo_dir, "%s.repo" % (f_name)), "r").read()) for f_name in cur_repo_names])
        # new_repo_dict = dict([(in_repo.findtextattrib["alias"], get_repo_str(in_repo)) for in_repo in in_repos])
        new_repo_dict = dict([(in_repo.findtext("alias"), get_repo_str(in_repo)) for in_repo in in_repos])
        rewrite_repos = False
        if any([old_repo_dict[name] != new_repo_dict[name] for name in set(cur_repo_names) & set (new_repo_dict.keys())]):
            self.log("repository content differs, forcing rewrite")
            rewrite_repos = True
        elif set(cur_repo_names) ^ set(new_repo_dict.keys()):
            self.log("list of old and new repositories differ, forcing rewrite")
            rewrite_repos = True
        if rewrite_repos and global_config["MODIFY_REPOS"]:
            self.log("rewritting repo files")
            # remove old ones
            for old_r_name in old_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "%s.repo" % (old_r_name))
                try:
                    os.unlink(f_name)
                except:
                    self.log("cannot remove %s: %s" % (f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("removed %s" % (f_name))
            for new_r_name in new_repo_dict.iterkeys():
                f_name = os.path.join(repo_dir, "%s.repo" % (new_r_name))
                try:
                    file(f_name, "w").write(new_repo_dict[new_r_name])
                except:
                    self.log("cannot create %s: %s" % (f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("created %s" % (f_name))
            self.package_commands.append(E.special_command(send_return="0", command="refresh", init="0"))

