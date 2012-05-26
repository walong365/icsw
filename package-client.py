#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel
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
""" daemon to automatically install packages (.rpm, .deb) """

import sys
import os
import os.path
import configfile
import copy
import cPickle
import zmq
import net_tools
import uuid_tools
import server_command
import pprint
try:
    import bz2
except:
    bz2 = None
import time
import logging_tools
import commands
import process_tools
import stat
import xml_tools
import threading_tools
import subprocess
import select
from lxml import etree

try:
    from package_client_version import *
except ImportError:
    # instead of unknown-unknown
    VERSION_STRING = "0.0-0"

P_SERVER_PUB_PORT   = 8007
P_SERVER_PULL_PORT  = 8008
PACKAGE_CLIENT_PORT = 2003

LF_NAME = "/var/lock/package_client.lock"

def call_command(com, logger, mode=""):
    start_time = time.time()
    try:
        my_stat, result = commands.getstatusoutput(com)
    except:
        my_stat, result = (1, "error calling %s: %s" % (com,
                                                        process_tools.get_except_info()))
    end_time = time.time()
    logger.info("Issuing command '%s' %stook %s" % (com,
                                                    mode and "(mode %s) " % (mode) or "",
                                                    logging_tools.get_diff_time_str(end_time - start_time)))
    return my_stat, result

# --------------------------------------------------------------------------------
##class connection_to_server(net_tools.buffer_object):
##    # connects to the package-server
##    def __init__(self, com, ret_queue):
##        self.__act_com = com
##        self.__ret_queue = ret_queue
##        net_tools.buffer_object.__init__(self)
##    def setup_done(self):
##        send_str = self.__act_com.toxml()
##        if bz2:
##            send_str = bz2.compress(send_str)
##        self.add_to_out_buffer(net_tools.add_proto_1_header(send_str, True))
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
##        if p1_ok:
##            self.__ret_queue.put(("send_ok", (self.__act_com, p1_data)))
##            self.delete()
##    def report_problem(self, flag, what):
##        self.__ret_queue.put(("send_error", (self.__act_com, "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
##        self.delete()

##class connection_from_server(net_tools.buffer_object):
##    # receiving connection object for server connection
##    def __init__(self, sock, src, dest_queue):
##        self.__dest_queue = dest_queue
##        self.__src = src
##        net_tools.buffer_object.__init__(self)
##    def __del__(self):
##        pass
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
##        if is_p1:
##            self.__dest_queue.put(("server_ok", (self, self.__src, what)))
##    def send_return(self, what):
##        self.lock()
##        if self.socket:
##            self.__tot_sent = 0
##            self.add_to_out_buffer(net_tools.add_proto_1_header(what))
##        else:
##            pass
##        self.unlock()
##    def out_buffer_sent(self, send_len):
##        self.__tot_sent += send_len
##        if self.__tot_sent == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##            self.close()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def report_problem(self, flag, what):
##        self.__dest_queue.put(("server_error", "%s : %s" % (net_tools.net_flag_to_str(flag), what)))
##        self.close()
# --------------------------------------------------------------------------------

class i_rpm(object):
    def __init__(self, logger, nr_dict, is_debian):
        self.nr_dict = nr_dict
        self.__is_debian = is_debian
        self.name, self.version, self.release = (nr_dict["name"], nr_dict["version"], nr_dict["release"])
        self.full_name = "%(name)s-%(version)s-%(release)s" % nr_dict
        self.location = nr_dict["location"]
        self.req_state = {"install" : "I",
                          "upgrade" : "U",
                          "delete"  : "D",
                          "keep"    : "N"}[nr_dict["command"]]
        self.__nodep_flag, self.__force_flag = (nr_dict["nodeps"], nr_dict["force"])
        # override, FIXME
        logger.info("  adding package_info name %s, req_state %s, add_flags '%s', location %s" % (self.full_name, self.req_state, self.get_add_flags(), self.location))
        self.set_act_state(logger)
        self.set_iter_value()
        #print "New i_rpm:", self.full_name, self.req_state, self.act_state
    def set_iter_value(self, what = 0):
        self.__iv = what
    def get_iter_value(self):
        return self.__iv
    def get_act_state(self):
        return self.act_state
    def get_req_state(self):
        return self.req_state
    def set_act_state(self, logger, s_state="-", l_state=None, inst_time=None, d_queue=None, extra_error_field=[]):
        self.__extra_error_field = extra_error_field
        self.act_state = s_state
        self.status = l_state
        if d_queue:
            if type(inst_time) == type(0):
                pass
            elif type(inst_time) == type(""):
                inst_time = int(inst_time)
            logger.info("Sending info about package %s to server (state %s, status %s)" % (self.full_name, self.act_state, self.status))
            #d_queue.put(packet_server_message(("rpm_info", "%s %s %s" % (self.full_name, self.act_state.lower(), self.status))))
            send_dict = {"name"              : self.name,
                         "version"           : self.version,
                         "release"           : self.release,
                         "act_state"         : self.act_state.lower(),
                         "status"            : self.status,
                         "install_time"      : inst_time,
                         "extra_error_lines" : len(self.__extra_error_field)}
            for extra_line, line_num in zip(self.__extra_error_field, range(1, len(self.__extra_error_field) + 1)):
                send_dict["error_line_%d" % (line_num)] = extra_line
            d_queue.put(("package_info", send_dict))
            #if bz2:
            #    d_queue.put(packet_server_message(("new_rpm_info3_c", bz2.compress(server_command.sys_to_net((self.name, self.version, self.release, self.act_state.lower(), self.status, inst_time))))))
            #else:
        #print self.full_name, self.act_state, self.status
    def get_location(self):
        return self.location
    def get_add_flags(self, ins_com=None):
        ret_a = []
        if self.__nodep_flag:
            ret_a.append(self.__is_debian and "--force-depends" or "--nodeps")
        if self.__force_flag and ins_com != "delete":
            ret_a.append(self.__is_debian and "--force-conflicts" or "--force")
        return (" ".join(ret_a)).strip()
    
class install_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, rpm_queue, logger):
        self.__glob_config = glob_config
        self.__logger = logger
        self.__rpm_queue = rpm_queue
        threading_tools.thread_obj.__init__(self, "install", queue_size=100, verbose=self.__glob_config["VERBOSE"] > 0)
        self.register_func("get_rpm_list", self._get_rpm_list)
        self.register_func("install", self._install)
        self.register_func("delete", self._delete)
        self.register_func("upgrade", self._upgrade)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _get_rpm_list(self):
        packages = self._get_rpm_list_int()
        if packages:
            self.__rpm_queue.put(("rpm_list", packages))
        else:
            self.__rpm_queue.put(("rpm_list", "error"))
    def _query_disk_package(self, location, logger):
        start_time = time.time()
        ret_state, ret_str, pack_name, pack_version, pack_release = ("ok", "", "", "", "")
        if self.__glob_config["DEBIAN"]:
            query_str = "dpkg -I %s" % (location)
            log_str = "Querying debian-package file %s via %s" % (location, query_str)
            logger.info(log_str)
            p_stat, result = call_command(query_str, logger)
            if p_stat:
                if location:
                    ret_state, ret_str = ("error", "checking debian-package named %s at %s (%d, %s)" % (pack_name, location, p_stat, result))
                else:
                    ret_state, ret_str = ("error", "checking debian-package %s [empty location string] (%d, %s)" % (pack_name, p_stat, result))
            else:
                val_dict = {}
                descr_found = False
                for line in [x.strip() for x in result.split("\n") if x.strip()]:
                    if descr_found:
                        val_dict["description"] = "%s %s" % (val_dict["description"], line)
                    line_parts = line.split()
                    if line_parts[0].isdigit():
                        pass
                    else:
                        key = line_parts.pop(0).lower()
                        if key.endswith(":"):
                            key = key[:-1]
                        elif key in ["size"]:
                            pass
                        else:
                            key = None
                        if key:
                            val_dict[key] = " ".join(line_parts)
                            if key == "description":
                                descr_found = True
                pack_name, pack_version, pack_release = (val_dict["package"],
                                                         "-".join(val_dict["version"].split("-")[:-1]),
                                                         val_dict["version"].split("-")[-1])
                # remove leading ":" from version
                if pack_version.count(":"):
                    leading_dig = pack_version.split(":")[0]
                    if leading_dig.isdigit():
                        pack_version = ":".join(pack_version.split(":")[1:])
        else:
            query_str = "rpm -qp %s --queryformat=\"%s\"" % (location, self.__query_format_str)
            log_str = "Querying package file %s via %s (old method)" % (location, query_str)
            logger.info(log_str)
            p_stat, result = call_command(query_str, logger)
            if p_stat:
                if location:
                    ret_state, ret_str = ("error", "checking package named %s at %s (%d, %s)" % (pack_name, location, p_stat, result))
                else:
                    ret_state, ret_str = ("error", "checking package %s [empty location string] (%d, %s)" % (pack_name, p_stat, result))
            else:
                package = self._parse_query_result(result)
                if len(package) != 1:
                    ret_state, ret_str = ("error", "parsing rpm-query (%d != 1)" % (len(package)))
                else:
                    pack_name = package.keys()[0]
                    pack_version, pack_release = (package[pack_name][0]["version"],
                                                  package[pack_name][0]["release"])
        return ret_state, ret_str, pack_name, pack_version, pack_release, []
    def _query_installed_package(self, pack_name, logger, mode):
        if self.__glob_config["DEBIAN"]:
            query_str = "dpkg -l %s" % (pack_name)
            p_stat, result = call_command(query_str, self.__logger, mode)
            if p_stat:
                logger.error("error getting information about %s_package(s) for %s: %s" % (mode, pack_name, result))
                pre_package = {}
            else:
                lines = [x.strip() for x in result.split("\n")]
                # drop header-lines
                while True:
                    line = lines.pop(0)
                    if line.count("=") > 20:
                        break
                pre_package = self._parse_query_result("\n".join(lines))
        else:
            query_str = "rpm -q %s --queryformat=\"%s\"" % (pack_name, self.__query_format_str)
            p_stat, result = call_command(query_str, self.__logger, mode)
            if p_stat:
                logger.error("error getting information about %s_package(s) for %s: %s" % (mode, pack_name, result))
                pre_package = {}
            else:
                # packages installed before -Uv command
                pre_package = self._parse_query_result(result)
        return pre_package
    def _install_upgrade_erase_package(self, command, name, short_name, location, add_flags, logger, g_logger):
        flag_field = [x.strip() for x in add_flags.split() if x.strip()]
        log_str = "Command '%s' for package %s, %s" % (command, name, flag_field and "%s: %s" % (logging_tools.get_plural("flag", len(flag_field)), ", ".join(flag_field)) or "no flags")
        g_logger.log(log_str)
        logger.log(log_str)
        # extra error array (for missing packages)
        extra_error_field = []
        if self.__glob_config["DEBIAN"]:
            deb_flags = " ".join([x for x in add_flags.strip().split() if x in ["--force-conflicts", "--force-depends"]])
            if command == "install":
                query_str = "dpkg %s -i %s" % (deb_flags, location)
            elif command == "delete":
                query_str = "dpkg -P %s" % (short_name)
            else:
                query_str = "dpkg %s -i %s" % (deb_flags, location)
            p_stat, result = call_command(query_str, self.__logger)
        else:
            rpm_flags = " ".join([x for x in add_flags.strip().split() if x in ["--force", "--nodeps"]])
            if command == "install":
                query_str = "rpm -iv %s %s" % (rpm_flags, location)
            elif command == "delete":
                query_str = "rpm -e %s %s" % (rpm_flags, name)
            else:
                query_str = "rpm -Uv %s %s" % (rpm_flags, location)
            p_stat, result = call_command(query_str, self.__logger)
            extra_error_field = result.split("\n")[1:]
        res_lines = str(result).split("\n")
        log_str = "done (%s, %s:)" % (logging_tools.get_plural("line", len(res_lines)),
                                      logging_tools.get_plural("extra_line", len(extra_error_field)))
        g_logger.info(log_str)
        logger.info(log_str)
        l_idx, last_line = (0, None)
        for line in res_lines:
            l_idx += 1
            if last_line == None:
                s_idx = l_idx
            elif last_line == line:
                pass
            else:
                act_log_line = " - %3d-%3d : %s" % (s_idx, l_idx - 1, last_line)
                g_logger.info(act_log_line)
                logger.info(act_log_line)
                s_idx = l_idx
            last_line = line
        act_log_line = " - %3d-%3d : %s" % (s_idx, l_idx, last_line or "<empty line>")
        g_logger.info(act_log_line)
        logger.info(act_log_line)
        return p_stat, result, extra_error_field
##    def _parse_query_result(self, q_result):
##        packages, act_p = ({}, None)
##        if self.__glob_config["DEBIAN"]:
##            for line in [y for y in [x.strip() for x in q_result.split("\n")] if y]:
##                try:
##                    flags, name, verrel, info = line.split(None, 3)
##                except:
##                    pass
##                else:
##                    if verrel.count("-"):
##                        ver, rel = verrel.split("-", 1)
##                    else:
##                        ver, rel = (verrel, "0")
##                    if len(flags) == 2:
##                        desired_flag, status_flag = flags
##                        error_flag = ""
##                    else:
##                        desired_flag, status_flag, error_flag = flags
##                    if desired_flag == "p":
##                        # package is purged
##                        pass
##                    elif desired_flag == "r":
##                        # package is removed
##                        pass
##                    else:
##                        packages.setdefault(name, []).append({"flags"       : (desired_flag, status_flag, error_flag),
##                                                              "version"     : ver,
##                                                              "release"     : rel,
##                                                              "summary"     : info,
##                                                              "installtime" : time.time(),
##                                                              "name"        : name})
##        else:
##            for pfix, pline in  [(y[0], y[1:]) for y in [x.strip() for x in q_result.split("\n")] if y]:
##                if pline:
##                    if pfix == "n":
##                        act_p = {"name" : pline}
##                    else:
##                        # ignore unknown prefixes
##                        if act_p and self.__rel_dict.has_key(pfix):
##                            dname = self.__rel_dict[pfix]
##                            act_p[dname] = pline.strip()
##                    if pfix == "t" and act_p:
##                        packages.setdefault(act_p["name"], []).append(act_p)
##                        act_p = {}
##        return packages
##    def _get_rpm_list_int(self):
##        start_time = time.time()
##        if self.__glob_config["DEBIAN"]:
##            query_str = "dpkg -l"
##            self.log("Started query of dpkg-list")
##            p_stat, p_list = call_command(query_str, self.__logger)
##            if p_stat:
##                ret_state = "error"
##            else:
##                ret_state = "ok"
##                lines = [x.strip() for x in p_list.split("\n")]
##                # drop header-lines
##                while True:
##                    line = lines.pop(0)
##                    if line.count("=") > 20:
##                        break
##                packages = self._parse_query_result("\n".join(lines))
##        else:
##            query_str = "rpm -qa --queryformat=\"%s\"" % (self.__query_format_str)
##            self.log("Started query of rpm-list (old method, queryformat=%s)" % (self.__query_format_str))
##            p_stat, p_list = call_command(query_str, self.__logger)
##            if p_stat:
##                ret_state = "error"
##            else:
##                ret_state = "ok"
##                packages = self._parse_query_result(p_list)
##        self.log("%s (%s): %s" % (ret_state,
##                                  logging_tools.get_diff_time_str(time.time() - start_time),
##                                  query_str))
##        if ret_state == "ok":
##            self.log("Found %s [%s where more than one version/release is installed: %s]" % (logging_tools.get_plural("unique package-name", len(packages)),
##                                                                                             logging_tools.get_plural("package", len([x for x in packages.keys() if len(packages[x]) > 1])),
##                                                                                             ", ".join(["%s (%s)" % (x, logging_tools.get_plural("instance", len(packages[x]))) for x in packages.keys() if len(packages[x]) > 1])))
##        else:
##            packages = {}
##        return packages
    def _install(self, package):
        self._package_handler("install", package)
    def _upgrade(self, package):
        self._package_handler("upgrade", package)
    def _delete(self, package):
        self._package_handler("delete", package)
    def _package_handler(self, command, com_opts):
        start_time = time.time()
        act_iter, name, location, add_flags, short_name = com_opts
        pack_logger = logging_tools.get_logger("%s.%s" % (self.__glob_config["LOG_NAME"],
                                                          name.replace(".", "\.")),
                                               self.__glob_config["LOG_DESTINATION"],
                                               init_logger=True)
        pack_logger.info("issuing command '%s' (flags '%s', location '%s', iteration %d)" % (command, add_flags, location, act_iter))
        if command in ["install", "upgrade"]:
            package = {}
            ret_state, ret_str, pack_name, pack_version, pack_release, extra_error_field = self._query_disk_package(location, pack_logger)
            if ret_state == "ok":
                pre_package_dict, pre_package_dict_full_name = (self._query_installed_package(pack_name, pack_logger, "pre-install"), {})
                # check if package to install is already installed
                for inst_stuff in pre_package_dict.get(pack_name, []):
                    # generate a dict with the full package-names for later checks
                    pre_package_dict_full_name["%s-%s-%s" % (pack_name, inst_stuff["version"], inst_stuff["release"])] = inst_stuff
##                     if self.__glob_config["DEBIAN"]:
##                         print inst_stuff["version"], pack_version, inst_stuff["release"], pack_release
                    if inst_stuff["version"] == pack_version and inst_stuff["release"] == pack_release:
                        # copy inst_package instance
                        package = dict([(k, v) for k, v in inst_stuff.iteritems()])
                if package:
                    pack_logger.info("the following package was already installed: %s-%s.%s" % (pack_name, pack_version, pack_release))
                    ret_state, ret_str, extra_error_field = ("ok", "already installed", [])
                else:
                    p_stat, result, extra_error_field = self._install_upgrade_erase_package(command, name, short_name, location, add_flags, pack_logger, self.__logger)
                    if p_stat:
                        ret_state, ret_str = ("error", "installing package %s (%d, %s)" % (location, p_stat, result))
                    else:
                        post_package_dict = self._query_installed_package(pack_name, pack_logger, "post-install")
                        if not post_package_dict:
                            ret_state, ret_str = ("error", "cannot verify installation of %s" % (location))
                        else:
                            if pack_name in post_package_dict.keys():
                                for pack in post_package_dict[pack_name]:
                                    if self.__glob_config["DEBIAN"]:
                                        # highly advanced comparison-routine for debian :-(
                                        if not pack_version:
                                            # needed for j2sdk1.6
                                            pack_version = pack_release
                                            pack_release = "0"
                                        ver_ok = "%s-%s" % (pack["version"], pack["release"]) == "%s-%s" % (pack_version, pack_release)
                                    else:
                                        ver_ok = pack["version"] == pack_version and pack["release"] == pack_release
                                    if ver_ok:
                                        package = dict([(k, v) for k, v in pack.iteritems()])
                                        pack_logger.info(" + Found package (version %s, release %s)" % (pack["version"], pack["release"]))
                                    else:
                                        pack_logger.warning(" - Found package with wrong ver/rel ('%s'/'%s' != '%s'/'%s')" % (pack["version"],
                                                                                                                              pack["release"],
                                                                                                                              pack_version,
                                                                                                                              pack_release))
                                if not package:
                                    pack_logger.warning("Package not found")
                            else:
                                pack_logger.warning("package_name '%s' not found in post_package_dict (ppd_keys: %s)" % (pack_name,
                                                                                                                         ", ".join(post_package_dict.keys())))
                            if not package:
                                ret_state, ret_str = ("error", "package was not installed")
                            else:
                                ret_state, ret_str = ("ok", "installed %s" % (location))
                        if pre_package_dict_full_name:
                            pre_list, post_list = (sorted(pre_package_dict_full_name.keys()), [])
                            for p_n, p_list in post_package_dict.iteritems():
                                post_list.extend([x for x in ["%s-%s-%s" % (p_n, p_d["version"], p_d["release"]) for p_d in p_list] if x != name])
                            post_list.sort()
                            if pre_list != post_list:
                                pack_logger.info("pre_list : %s; %s" % (logging_tools.get_plural("package", len(pre_list)), ", ".join(pre_list)))
                                pack_logger.info("post_list: %s; %s" % (logging_tools.get_plural("package", len(post_list)), ", ".join(post_list)))
                                # we have lost some packages... oh my god...
                                pre_packs = [x for x in pre_list if x not in post_list]
                                pack_logger.warning("due to the -U/iv command we have lost the following %s: %s" % (logging_tools.get_plural("package", len(pre_packs)),
                                                                                                                    ",".join(pre_packs)))
                                for pre_pack in pre_packs:
                                    self.__rpm_queue.put(("lost_package", (pack_name, pre_pack, copy.deepcopy(pre_package_dict_full_name[pre_pack]))))
            pack_logger.info("%s : %s (file %s, %s)" % (ret_state, command, location, ret_str))
            self.__rpm_queue.put(("install_result", (act_iter, ret_state, name, ret_str, copy.deepcopy(package), extra_error_field)))
        else:
            act_iter, name, location, add_flags, short_name = com_opts
            p_stat, result, extra_error_field = self._install_upgrade_erase_package(command, name, short_name, location, add_flags, pack_logger, self.__logger)
            #query_str = "rpm -e %s %s" % (name, add_flags)
            #stat, result = call_command(query_str, pack_log)
            if p_stat:
                ret_state, ret_str = ("error", "deleting package %s (%d, %s)" % (name, p_stat, result))
            else:
                ret_state, ret_str = ("ok", "deleted %s" % (name))
            pack_logger.info("%s : %s" % (ret_state, "erased %s" % (name)))
            self.__rpm_queue.put(("delete_result", (act_iter, ret_state, name, ret_str, {}, extra_error_field)))
        pack_logger.info("return state/str (after %s): %s, %s" % (logging_tools.get_diff_time_str(time.time() - start_time),
                                                                  ret_state,
                                                                  ret_str))
        # remove package logger
        pack_logger.info("CLOSE")
        #pack_log.set_command_and_send("close_log")
        #pack_log.close()
        del pack_logger

class rsync_object(object):
    def __init__(self, logger, glob_config, var_dict):
        self.__glob_config = glob_config
        self.__name = var_dict["name"]
        self.__source_server = var_dict["source_server"]
        self.__target_dir = var_dict["target_dir"]
        self.__p_name = "%s/rsync_%s" % (self.__glob_config["VAR_DIR"],
                                         self.__target_dir.replace("/", "_").replace("__", "_"))
        self.__p_dict = {}
        self.set_act_state(logger, "-", "not set")
        self.set_in_use(False)
    def _read_persistence_info(self):
        if os.path.isfile(self.__p_name):
            try:
                p_dict = cPickle.loads(file(self.__p_name, "r").read())
            except:
                pass
            else:
                print p_dict
    def _write_persistence_info(self):
        try:
            file(self.__p_name, "w").write(cPickle.dumps(self.__p_dict))
        except:
            print process_tools.get_except_info()
    def get_source_server(self):
        return self.__source_server
    def get_dest_dir(self):
        return self.__target_dir
    def set_in_use(self, use_flag):
        self.__in_use = use_flag
    def is_in_use(self):
        return self.__in_use
    def get_name(self):
        return self.__name
    def set_act_state(self, logger, s_state="", status="", last_rsync_time=None, d_queue=None, extra_error_field=[]):
        self.__extra_error_field = extra_error_field
        if s_state:
            self.__act_state = s_state
        if status:
            self.__status = status
        if d_queue:
            logger.info("Sending info about rsync %s to server (state %s, status %s)" % (self.__name,
                                                                                         self.__act_state,
                                                                                         self.__status))
            ri_dict = {"name"      : self.__name,
                       "act_state" : self.__act_state.lower(),
                       "status"    : self.__status}
            if last_rsync_time is not None:
                ri_dict["last_rsync_time"] = last_rsync_time
            d_queue.put(("rsync_object_info", ri_dict))
        self._write_persistence_info()
    def get_act_state(self):
        return self.__act_state

class rsync_install_thread_code(threading_tools.thread_obj):
    def __init__(self, glob_config, rsync_queue, logger):
        self.__glob_config = glob_config
        self.__logger = logger
        self.__rsync_queue = rsync_queue
        threading_tools.thread_obj.__init__(self, "rsync_install", queue_size=100, verbose=self.__glob_config["VERBOSE"] > 0)
        self.register_func("rsync", self._rsync)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _rsync(self, rso):
        com_line = "rsync --stats -a --delete %s::%s %s/" % (rso.get_source_server(),
                                                             rso.get_name(),
                                                             rso.get_dest_dir().replace(" ", "\\ "))
        self.log("starting rsyncing of %s, command_line is '%s'" % (rso.get_name(),
                                                                    com_line))
        s_time = time.time()
        c_stat, out = commands.getstatusoutput(com_line)
        e_time = time.time()
        if c_stat:
            self.log("error rsyncing (%d) after %s: %s" % (c_stat,
                                                           logging_tools.get_diff_time_str(e_time - s_time),
                                                           out),
                     logging_tools.LOG_LEVEL_ERROR)
            rso.set_act_state(self.__logger, "error", out)
        else:
            out_lines = out.split("\n")
            self.log("rsync ok, took %s, gave %s of output:" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                                logging_tools.get_plural("line", len(out_lines))))
            for line in out_lines:
                self.log(" - %s" % (line))
            rso.set_act_state(self.__logger, "ok", "rsynced in %s" % (logging_tools.get_diff_time_str(e_time - s_time)))
        self.__rsync_queue.put(("rsync_result", rso))

class rsync_thread_code(threading_tools.thread_obj):
    def __init__(self, glob_config, comsend_queue, logger):
        self.__glob_config = glob_config
        self.__logger = logger
        self.__comsend_queue = comsend_queue
        threading_tools.thread_obj.__init__(self, "rsync", queue_size=100, verbose=self.__glob_config["VERBOSE"] > 0)
        self.register_func("rsync_request", self._rsync_request)
        self.register_func("rsync_result", self._rsync_result)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.log("starting rsync_install_thread")
        self.__install_queue = self.get_thread_pool().add_thread(rsync_install_thread_code(self.__glob_config, self.get_thread_queue(), self.__logger), start_thread=True).get_thread_queue()
        self.__list_from_server = False
        # lock is active
        self.__lock_active = True
        # rsync dict
        self.__act_rsync_dict = {}
        # actual command list to be processes by install_thread, pending command
        self.__command_list, self.__pending_command = ([], None)
        self.__comsend_queue.put(("thread_alive", "rsync"))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _rsync_request(self, rsync_list):
        self.__act_rsync_dict = {}
        for rsync_node in [rsync_list.item(x) for x in range(rsync_list.length)]:
            new_rsync = rsync_object(self.__logger, self.__glob_config, xml_tools.build_var_dict(rsync_node))
            self.__act_rsync_dict[new_rsync.get_name()] = new_rsync
        self.__list_from_server = True
        if self.__lock_active and not rsync_list.length:
            self.__comsend_queue.put(("delete_rsync_lockfile", "got empty rsync-list from server"))
            self.__lock_active = False
        self._rsync_list_changed()
        self._send_rsync_info()
    def _rsync_list_changed(self):
        if self.__act_rsync_dict:
            rsync_names = sorted(self.__act_rsync_dict.keys())
            for name in rsync_names:
                act_rso = self.__act_rsync_dict[name]
                act_com = None
                if act_rso.get_act_state() == "-":
                    act_com = "rsync"
                elif act_rso.get_state() == "ok":
                    act_rso.set_act_state(self.__logger, "ok", "rsynced", time.time(), self.__comsend_queue)
                if act_com:
                    act_rso.set_act_state(self.__logger, "w", "waiting for %s" % (act_com), d_queue=self.__comsend_queue)
                    # check if install_request is not already in command_list
                    if (act_com, act_rso) not in self.__command_list:
                        self.__command_list.append((act_com, act_rso))
            self._check_for_command_list_change()
        self._check_lock_remove()
    def _send_rsync_info(self):
        self.__comsend_queue.put(("rsync_info", ([x.get_act_state() for x in self.__act_rsync_dict.values()])))
    def _check_lock_remove(self):
        self._send_rsync_info()
        rsync_stat = [x.get_act_state() for x in self.__act_rsync_dict.values() if x.get_act_state().lower() not in ["ok", "error"]]
        if self.__lock_active and not len(rsync_stat) and self.__list_from_server:
            self.__comsend_queue.put(("delete_rsync_lockfile", "state of all rsyncs valid"))
            self.__lock_active = False
    def _check_for_command_list_change(self):
        if not self.__pending_command and self.__command_list:
            act_com, act_rso = self.__command_list[0]
            self.log("sending first command of command_list (%s) to install_queue (%s on %s)" % (logging_tools.get_plural("entry", len(self.__command_list)),
                                                                                                 act_com,
                                                                                                 act_rso.get_name()))
            self.__pending_command = self.__command_list[0]
            act_rso.set_in_use(True)
            self.__install_queue.put((act_com, act_rso))
    def _rsync_result(self, rso):
        rso.set_act_state(self.__logger, d_queue=self.__comsend_queue)
        rso.set_in_use(False)
        self.__command_list.pop(0)
        self.__pending_command = None
        self._check_for_command_list_change()
        self._check_lock_remove()
        
class rpm_thread_code(threading_tools.thread_obj):
    def __init__(self, glob_config, comsend_queue, logger):
        self.__glob_config = glob_config
        self.__logger = logger
        self.__comsend_queue = comsend_queue
        threading_tools.thread_obj.__init__(self, "rpm", queue_size=100, verbose=self.__glob_config["VERBOSE"] > 0)
        self.register_func("rpm_list", self._rpm_list)
        self.register_func("rpm_request", self._rpm_request)
        self.register_func("install_result", self._install_result)
        self.register_func("delete_result", self._delete_result)
        self.register_func("lost_package", self._lost_package)
        self.register_func("reload", self._reload)
        self.register_func("get_rpm_list", self._get_rpm_list)
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__install_queue = self.get_thread_pool().add_thread(install_thread(self.__glob_config, self.get_thread_queue(), self.__logger), start_thread=True).get_thread_queue()
        self.__list_from_server = False
        # RPM dict
        self.__rpm_list_waiting = False
        self.__new_rpm_dict, self.__act_rpm_dict, self.__latest_rpm_list = ({}, {}, 0)
        # action iteration
        self.__act_iter = 0
        # action dicts
        self.__action_dict = {}
        # lock active
        self.__lock_active = True
        # a list of outstanding keys waiting for an rpm_list
        self.__objects_waiting_for_rpm_list = []
        self._check_for_valid_rpm_dict()
        self.__comsend_queue.put(("thread_alive", "rpm"))
    def any_message_received(self):
        self._check_for_valid_rpm_dict()
    def _check_for_valid_rpm_dict(self):
        if not self.__act_rpm_dict and not self.__rpm_list_waiting:
            self.__rpm_list_waiting = True
            self.__install_queue.put("get_rpm_list")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _rpm_list(self, rpm_list):
        if self.__rpm_list_waiting:
            if type(rpm_list) == type(""):
                self.log("could not determine rpm_list, retrying (after a sleep of 1 second) ...")
                time.sleep(1)
                self.__install_queue.put("get_rpm_list")
            else:
                self.__act_rpm_dict, self.__latest_rpm_list = ({}, time.time())
                for name, pack_list in rpm_list.iteritems():
                    for pack in pack_list:
                        full_name = "%s-%s-%s" % (name, pack["version"], pack["release"])
                        self.__act_rpm_dict[full_name] = pack
                self.__rpm_list_waiting = False
                self.log("got rpm_list with %s" % (logging_tools.get_plural("package", len(self.__act_rpm_dict.keys()))))
                for com_obj in self.__objects_waiting_for_rpm_list:
                    com_obj.send_return("ok %s" % (cPickle.dumps(dict([(self.__act_rpm_dict[x]["name"], self.__act_rpm_dict[x]) for x in self.__act_rpm_dict.keys()]))))
                self.__objects_waiting_for_rpm_dict = []
                self._rpm_dict_changed()
        else:
            self.log("got rpm_list but never wanted one ... ?", logging_tools.LOG_LEVEL_WARN)
    def _rpm_request(self, rpm_r_list):
        self.__new_rpm_dict = {}
        for rpm_node in [rpm_r_list.item(x) for x in range(rpm_r_list.length)]:
            new_i_rpm = i_rpm(self.__logger, xml_tools.build_var_dict(rpm_node), self.__glob_config["DEBIAN"])
            self.__new_rpm_dict[new_i_rpm.full_name] = new_i_rpm
        self.__list_from_server = True
        if self.__lock_active and not rpm_r_list.length:
            self.__comsend_queue.put(("delete_rpm_lockfile", "got empty package-list from server"))
            self.__lock_active = False
        self._rpm_dict_changed()
        self._send_rpm_info()
    def _send_rpm_info(self):
        self.__comsend_queue.put(("rpm_info", ([x.get_act_state() for x in self.__new_rpm_dict.values()])))
    def _rpm_dict_changed(self):
        if self.__new_rpm_dict and self.__act_rpm_dict:
            ins_com_list = []
            new_names = sorted(self.__new_rpm_dict.keys())
            for name in new_names:
                ar_d = self.__new_rpm_dict[name]
                if ar_d.get_act_state() == "-":
                    ins_com = None
                    req_st = ar_d.get_req_state()
                    if req_st in ["I", "U"]:
                        # required state is install or upgrade
                        if name in self.__act_rpm_dict.keys():
                            # already installed
                            ar_d.set_act_state(self.__logger, "ok", "package is installed", self.__act_rpm_dict[name]["installtime"], self.__comsend_queue, [])
                        else:
                            if req_st == "I":
                                ins_com = "install"
                            else:
                                ins_com = "upgrade"
                    elif req_st == "D":
                        # required state is delete
                        if name in self.__act_rpm_dict.keys():
                            ins_com = "delete"
                        else:
                            # already deleted
                            ar_d.set_act_state(self.__logger, "ok", "package is deleted", None, self.__comsend_queue, [])
                    elif req_st == "N":
                        # just give me the status
                        if name in self.__act_rpm_dict.keys():
                            # installed
                            ar_d.set_act_state(self.__logger, "ok", "package is installed", self.__act_rpm_dict[name]["installtime"], self.__comsend_queue, [])
                        else:
                            # deleted
                            ar_d.set_act_state(self.__logger, "ok", "package is not installed", None, self.__comsend_queue, [])
                    if ins_com:
                        ar_d.set_act_state(self.__logger, "w", "waiting for %s" % (ins_com), None, self.__comsend_queue, [])
                        ins_com_list.append((ins_com, name))
            if ins_com_list:
                self.__act_iter += 1
                self.__action_dict[self.__act_iter] = {}
                self.log("action_list (iteration %d) has %d entries: %s" % (self.__act_iter, len(ins_com_list), ", ".join(["%s (%s)" % (x[1], x[0]) for x in ins_com_list])))
                for ins_com, name in ins_com_list:
                    self.__action_dict[self.__act_iter][name] = None
                    ar_d = self.__new_rpm_dict[name]
                    ar_d.set_iter_value(self.__act_iter)
                    self.__install_queue.put((ins_com, (self.__act_iter, name, ar_d.get_location(), ar_d.get_add_flags(ins_com), ar_d.name)))
            self._send_rpm_info()
        self._check_lock_remove()
    def _install_result(self, data):
        # make an ldconfig-call
        stat, res = call_command("ldconfig", self.__logger)
        self._in_del_result("install", data)
    def _delete_result(self, data):
        self._in_del_result("delete", data)
    def _in_del_result(self, com, (iter_idx, res_state, res_name, res_descr, pack, extra_error_field)):
        if self.__new_rpm_dict.has_key(res_name):
            #print res_state, res_name, res_descr
            if res_state == "ok":
                if com == "install":
                    self.__new_rpm_dict[res_name].set_act_state(self.__logger, "ok", res_descr, pack["installtime"], self.__comsend_queue, extra_error_field)
                    # get package structure (see above)
                    full_name = "%s-%s-%s" % (pack["name"], pack["version"], pack["release"])
                    self.__act_rpm_dict[full_name] = pack
                else:
                    self.__new_rpm_dict[res_name].set_act_state(self.__logger, "ok", res_descr, 0, self.__comsend_queue, extra_error_field)
                    del self.__act_rpm_dict[res_name]
            else:
                self.__new_rpm_dict[res_name].set_act_state(self.__logger, "error", res_descr, None, self.__comsend_queue, extra_error_field)
            self.__action_dict[iter_idx][res_name] = (res_state, res_descr)
            if iter_idx == self.__act_iter:
                # check if all packages have a defined state
                act_ad = self.__action_dict[iter_idx]
                if not [x for x in act_ad.values() if not x]:
                    err_names = sorted([name for name, x in act_ad.iteritems() if x and x[0].startswith("error")])
                    num_error = len(err_names)
                    self.log("finished action_dict (iteration %d), %s had %s" % (iter_idx,
                                                                                 logging_tools.get_plural("package", len(act_ad.keys())),
                                                                                 logging_tools.get_plural("error", num_error)))
                    if num_error:
                        for name, (state, result) in act_ad.iteritems():
                            if state.startswith("error"):
                                self.log("  - %s : %s; %s" % (name, state, result), logging_tools.LOG_LEVEL_ERROR)
                        # requeue error packages?
                        requeue = True
                        # check for the same errors in the previous action_iteration
                        if self.__action_dict.has_key(iter_idx - 1):
                            prev_err_names = sorted([name for name, x in self.__action_dict[iter_idx - 1].iteritems() if x[0].startswith("error")])
                            if prev_err_names == err_names:
                                self.log("same errors in the previous run, no requeuing", logging_tools.LOG_LEVEL_WARN)
                                requeue = False
                        if requeue:
                            self.log("requeing %s: %s" % (logging_tools.get_plural("error_package", len(err_names)),
                                                          ", ".join(err_names)), logging_tools.LOG_LEVEL_WARN)
                            for name in err_names:
                                self.__new_rpm_dict[name].set_act_state(self.__logger)
                            self._rpm_dict_changed()
                    if self.__action_dict.has_key(iter_idx - 1):
                        if not [x for x in self.__action_dict[iter_idx - 1].values() if not x]:
                            self.log("deleting action_dict for iteration %d" % (iter_idx - 1))
                            del self.__action_dict[iter_idx - 1]
        else:
            self.log("Got install_result %s (%s) for the package '%s' which is not in the list %s" % (res_state, res_descr, res_name, ", ".join(self.__new_rpm_dict.keys())))
        self._send_rpm_info()
        self._check_lock_remove()
    def _check_lock_remove(self):
        rpm_stat = [x.get_act_state() for x in self.__new_rpm_dict.values() if x.get_act_state().lower() not in ["ok", "error"]]
        if self.__lock_active and not len(rpm_stat) and self.__list_from_server:
            self.__comsend_queue.put(("delete_rpm_lockfile", "state of all packages valid"))
            self.__lock_active = False
    def _lost_package(self, (p_name, p_full_name, p_dict)):
        if self.__new_rpm_dict.has_key(p_full_name):
            self.__new_rpm_dict[p_full_name].set_act_state(self.__logger, "ok", "lost while -Uv", None, self.__comsend_queue, [])
        else:
            self.log("Got lost_package_result for the package '%s' which is not in the list %s" % (p_full_name, ", ".join(self.__new_rpm_dict.keys())))
        if self.__act_rpm_dict.has_key(p_full_name):
            del self.__act_rpm_dict[p_full_name]
    def _reload(self):
        if not self.__rpm_list_waiting:
            self.log("forcing reload of rpm-list ...")
            self.__install_queue.put("get_rpm_list")
            self.__act_rpm_dict = {}
            self.__rpm_list_waiting = True
    def _get_rpm_list(self, com_obj):
        #key = stuff
        if self.__act_rpm_dict:
            try:
                last_change = os.stat("/var/lib/rpm/Basenames")[stat.ST_MTIME]
            except:
                last_change = 0
            if not last_change or last_change < self.__latest_rpm_list:
                com_obj.send_return("ok %s" % (cPickle.dumps(dict([(self.__act_rpm_dict[x]["name"], self.__act_rpm_dict[x]) for x in self.__act_rpm_dict.keys()]))))
            elif not self.__rpm_list_waiting:
                self.log("forcing reload of rpm-list because of database_change ...")
                self.__install_queue.put("get_rpm_list")
                self.__act_rpm_dict = {}
                self.__rpm_list_waiting = True
                self.__objects_waiting_for_rpm_list.append(com_obj)
        else:
            self.__objects_waiting_for_rpm_list.append(com_obj)

class comsend_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, ns, logger):
        """ effective main_thread of package-client, handles locking and status info """
        self.__glob_config = glob_config
        self.__logger = logger
        self.__net_server = ns
        threading_tools.thread_obj.__init__(self, "comsend", queue_size=100, verbose=self.__glob_config["VERBOSE"] > 0, gather_timeout=1)
        # actual list of stuff to send to server
        # format: flag (to server ... True, from server ... False), send/recv string
        self.__srv_list = []
        # delay list
        self.__delay_list = []
        self.register_func("get_package_list", self._get_package_list)
        self.register_func("get_rsync_list", self._get_rsync_list)
        self.register_func("hello", self._hello)
        self.register_func("delay", self._delay)
        self.register_func("send_error", self._send_error)
        self.register_func("send_ok", self._send_ok)
        self.register_func("server_error", self._server_error)
        self.register_func("server_ok", self._server_ok)
        self.register_func("delete_rpm_lockfile", self._delete_rpm_lockfile)
        self.register_func("delete_rsync_lockfile", self._delete_rsync_lockfile)
        self.register_func("rpm_info", self._rpm_info)
        self.register_func("rsync_info", self._rsync_info)
        self.register_func("package_info", self._package_info)
        self.register_func("rsync_object_info", self._rsync_object_info)
        self.register_func("request_exit", self._request_exit)
        self.register_func("connection_ok", self._connection_ok)
        self.register_func("connection_refused", self._connection_refused)
        self.register_func("thread_alive", self._thread_alive)
        self.__alive_threads = []
        self.__exit_requested = False
        # number of refused connections
        self.__num_con_refused = 0
        # lockfile exists
        self.__lock_exists = True
        # internal locks
        self.__rpm_lock_exists, self.__rsync_lock_exists = (True, True)
        # incoming-idx
        self.__incoming_idx = 0
        # next send idx
        self.__send_idx = self.__incoming_idx + 1
        # send and pending dict
        self.__send_dict, self.__pending_dict = ({}, {})
        # sub_threads
        self.__rpm_queue, self.__rsync_queue = (None, None)
        # statistics
        self.__num_pack, self.__ok_pack, self.__error_pack = (0, 0, 0)
        self.__num_rsync, self.__ok_rsync, self.__error_rsync = (0, 0, 0)
        # retry queue
        self.__retry_queue = []
        # init info files
        self._init_info_files()
##    def thread_running(self):
##        self.send_pool_message(("new_pid", self.pid))
##        self._log_send_status()
##        self._start_rpm_thread()
##        self._start_rsync_thread()
    def _thread_alive(self, t_name):
        self.__alive_threads.append(t_name)
        self.log("%s alive: %s" % (logging_tools.get_plural("thread", len(self.__alive_threads)),
                                   ", ".join(self.__alive_threads)))
        if len (self.__alive_threads) == 2:
            self.send_pool_message("threads_alive")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def optimize_message_list(self, in_list):
        # new, shiny code 
        ext_list = []
        while in_list:
            act_ref_el = in_list.pop(0)
            ext_list.append(act_ref_el)
            if type(act_ref_el) == type(()) and act_ref_el[0] == "package_info":
                while in_list:
                    new_el = in_list[0]
                    if type(new_el) == type(()) and new_el[0] == "package_info":
                        in_list.pop(0)
                        if type(ext_list[-1][1]) != type([]):
                            ext_list[-1] = (ext_list[-1][0], [ext_list[-1][1]])
                        ext_list[-1][1].append(new_el[1])
                    else:
                        break
        return ext_list
    def _start_rpm_thread(self):
        if not self.__rpm_queue:
            self.log("starting rpm_thread")
            self.__rpm_queue = self.get_thread_pool().add_thread(rpm_thread_code(self.__glob_config, self.get_thread_queue(), self.__logger), start_thread=True).get_thread_queue()
    def _start_rsync_thread(self):
        if not self.__rsync_queue:
            self.log("starting rsync_thread")
            self.__rsync_queue = self.get_thread_pool().add_thread(rsync_thread_code(self.__glob_config, self.get_thread_queue(), self.__logger), start_thread=True).get_thread_queue()
    def loop_end(self):
        self.log("proc %d: %s-thread for package-client exiting" % (self.pid, self.name))
    def _delay(self, (timeout, target_queue, message)):
        self.__delay_list.append((time.time() + timeout, target_queue, message))
    def _request_exit(self):
        self.__exit_requested = True
    def _delete_rpm_lockfile(self, why):
        if self.__rpm_lock_exists:
            self.__rpm_lock_exists = False
            self.log("removing internal rpm_lock because: %s" % (why))
            self._delete_lockfile()
    def _delete_rsync_lockfile(self, why):
        if self.__rsync_lock_exists:
            self.__rsync_lock_exists = False
            self.log("removing internal rsync_lock because: %s" % (why))
            self._delete_lockfile()
    def _delete_lockfile(self):
        if self.__lock_exists:
            if not self.__rpm_lock_exists and not self.__rsync_lock_exists:
                self.__lock_exists = False
                self.log("removing lockfile (neither rpm nor rsync-lock set)")
                process_tools.delete_lockfile(LF_NAME)
    def _package_info(self, info_stuff):
        self.__srv_list.append(("package_info", info_stuff))
        self._srv_list_changed()
        self._check_for_send()
    def _rsync_object_info(self, info_stuff):
        self.__srv_list.append(("rsync_object_info", info_stuff))
        self._srv_list_changed()
        self._check_for_send()
    def _get_package_list(self):
        self.__srv_list.append(("get_package_list", None))
        self._srv_list_changed()
        self._check_for_send()
    def _get_rsync_list(self):
        self.__srv_list.append(("get_rsync_list", None))
        self._srv_list_changed()
        self._check_for_send()
    def _log_send_status(self):
        self.log("SI: actual send_idx is %d, send_dict is %s, trans_dict is %s" % (self.__send_idx,
                                                                                   ", ".join([("%d:%s") % (k, v and "set" or "not set") for k, v in self.__send_dict.iteritems()]) or "empty",
                                                                                   ", ".join([("%d:%d") % (k, v) for k, v in self.__pending_dict.iteritems()]) or "empty"))
    def _hello(self):
        self.log("Actual memory consumption: %s" % (process_tools.beautify_mem_info()))
        if self.__retry_queue:
            err_idx, err_stat = self.__retry_queue.pop(0)
            self.__pending_dict[err_idx] = err_stat
            self._check_for_send()
        if self.__delay_list:
            self.log("Checking %s in delay_list" % (logging_tools.get_plural("entry", len(self.__delay_list))))
            new_list = []
            act_time = time.time()
            for s_time, t_queue, message in self.__delay_list:
                if act_time >= s_time:
                    self.log(" - sending message")
                    t_queue.put(message)
                else:
                    new_list.append((s_time, t_queue, message))
            self.__delay_list = new_list
    def _srv_list_changed(self):
        actual_txt_com = ""
        send_list = []
        #print "srv_list:", len(self.__srv_list)
        for com, p_info_list in self.__srv_list:
            if com != actual_txt_com:
                # start new command
                act_com = xml_tools.xml_command()
                act_com.set_command(com)
                act_com.top_element().appendChild(act_com.createElement("arguments"))
                act_com.add_flag("bz2compression", bz2 and True or False)
                act_com.add_flag("debian_client", self.__glob_config["DEBIAN"])
                act_com.add_flag("version", VERSION_STRING)
                #act_com.add_flag("rpm_direct", rpm_module.rpm_module_ok())
                p_list = act_com.top_element().appendChild(act_com.createElement("packages"))
                send_list.append(act_com)
                actual_txt_com = com
            if p_info_list:
                if type(p_info_list) != type([]):
                    p_info_list = [p_info_list]
                for p_info in p_info_list:
                    act_p = p_list.appendChild(act_com.createElement("package"))
                    for what, value in p_info.iteritems():
                        act_p.appendChild(act_com.create_var_node(what, value))
        # send now
        for send_com in send_list:
            self._new_command_to_send(send_com)
        self.__srv_list = []
    def _new_command_to_send(self, new_com):
        self.__incoming_idx += 1
        self.__send_dict[self.__incoming_idx] = new_com
        self.__pending_dict[self.__incoming_idx] = 0
        self._check_for_send()
    def _server_send_ok(self, ok_idx):
        del self.__pending_dict[ok_idx]
        del self.__send_dict[ok_idx]
        self.__send_idx = ok_idx + 1
        self.log("SI: sending of instance with send_idx %d successfull" % (ok_idx))
        self._check_for_send()
    def _server_send_error(self, error_idx, requeue_flag):
        self.log("SI: sending of instance with send_idx %d failed%s" % (error_idx,
                                                                        ", queueing into retry_queue" if requeue_flag else ""),
                 logging_tools.LOG_LEVEL_ERROR)
        if requeue_flag:
            self.__retry_queue.append((error_idx, 0))
        else:
            del self.__pending_dict[error_idx]
            del self.__send_dict[error_idx]
            self.__send_idx = error_idx + 1
            self._check_for_send()
    def _check_for_send(self):
        if self.__exit_requested:
            pass
        else:
            if self.__send_dict.has_key(self.__send_idx):
                if not self.__pending_dict[self.__send_idx]:
                    self.send_pool_message(("set_target_retry_speed", 10))
                    # ok
                    com = self.__send_dict[self.__send_idx]
                    com.add_flag("send_idx", self.__send_idx)
                    send_str = com.toxml()
                    if bz2:
                        send_str = bz2.compress(send_str)
                    if self.__glob_config.has_key("PACKAGE_SERVER"):
                        self.log("SI: Initiating the send of %s (%s), send_idx is %d" % (logging_tools.get_plural("byte", len(send_str)),
                                                                                         logging_tools.get_plural("package", len(com.top_element().getElementsByTagName("package"))),
                                                                                         self.__send_idx))
                        self.__net_server.add_object(net_tools.tcp_con_object(self._new_server_connection, connect_state_call=self._connect_state_call, connect_timeout_call=self._connect_timeout, timeout=10, bind_retries=1, rebind_wait_time=1, target_port=self.__glob_config["SERVER_PORT"], target_host=self.__glob_config["PACKAGE_SERVER"], add_data=com))
                        self.__pending_dict[self.__send_idx] = 1
                    self._log_send_status()
            else:
                self.log("send_dict empty")
    def _connect_timeout(self, sock):
        self.get_thread_queue().put(("send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("send_error", (args["socket"].get_add_data(), "connection error")))
    def _connection_ok(self):
        self.send_pool_message(("set_target_retry_speed", 120))
        if self.__num_con_refused:
            self.__num_con_refused = 0
            self.log("Clearing number of refused connections")
    def _connection_refused(self, immediate=False):
        next_try = True
        if not self.__num_con_refused:
            self.send_pool_message(("set_target_retry_speed", 10))
        self.__num_con_refused += 1
        self.log("Number of refused connections: %d" % (self.__num_con_refused))
        if self.__num_con_refused > 3 or immediate:
            next_try = False
            self.log("Cannot reach server, giving up...", logging_tools.LOG_LEVEL_ERROR)
            if self.__glob_config["EXIT_ON_FAIL"] or immediate:
                self.log("forcing exit", logging_tools.LOG_LEVEL_WARN)
                self.send_pool_message(("force_exit", "cannot reach server"))
            else:
                self.send_pool_message(("set_target_retry_speed", 120))
            self.get_thread_queue().put(("delete_rpm_lockfile", "cannot reach server"))
            self.get_thread_queue().put(("delete_rsync_lockfile", "cannot reach server"))
            self.__num_con_refused = -1
        return next_try
    def _new_server_connection(self, sock):
        pass
        #return connection_to_server(sock.get_add_data(), self.get_thread_queue())
    def _send_error(self, (err_com, why)):
        # as of 22.8.2003 changed the target-queue from own_queue to retry_queue
        #retry_list.append(packet_server_finish((1, inc_idx)))
        # check for local package-server
        next_try = self._connection_refused()
        flag_dict = err_com.get_flag_dict()
        self.log("%s error-command %d '%s': %s (%s)" % ("Requeuing" if next_try else "Throwing away",
                                                        flag_dict["send_idx"],
                                                        err_com.get_command(),
                                                        why,
                                                        logging_tools.get_plural("package", len(err_com.top_element().getElementsByTagName("package")))),
                 logging_tools.LOG_LEVEL_WARN if next_try else logging_tools.LOG_LEVEL_ERROR)
        self._server_send_error(flag_dict["send_idx"], next_try)
        if self.__glob_config["PACKAGE_SERVER"] in ["localhost", "127.0.0.1"] and err_com.get_command() == "get_package_list":
            if self.__lock_exists:
                self.log("error connecting to localhost '%s' for for get_package_list, clearing lockfile" % (self.__glob_config["PACKAGE_SERVER"]), logging_tools.LOG_LEVEL_ERROR)
                self._delete_rpm_lockfile("localhost not responding")
                self._delete_rsync_lockfile("localhost not responding")
        # sleep for 1 second, FIXME
        time.sleep(1)
    def _send_ok(self, (ok_com, in_data)):
        flag_dict = ok_com.get_flag_dict()
        passed = False
        #print flag_dict
        self.log("successfully sent command %s (idx %d) to server (%s)" % (ok_com.get_command(),
                                                                           flag_dict["send_idx"],
                                                                           logging_tools.get_plural("package",
                                                                                                    len(ok_com.top_element().getElementsByTagName("package")))))
        try:
            recv_command = xml_tools.xml_command(src_type="string", src_name=in_data)
        except:
            # try to interpret as string
            if in_data.startswith("BZh"):
                try:
                    in_bytes = bz2.decompress(in_data)
                except:
                    pass
                else:
                    in_data = in_bytes
            if in_data.startswith("error "):
                self.log("got error-result from server: %s" % (in_data), logging_tools.LOG_LEVEL_ERROR)
                if in_data.count("no package client"):
                    self.log("i am no package_client, exiting", logging_tools.LOG_LEVEL_ERROR)
                    self.get_thread_queue().put(("connection_refused", True))
            else:
                self.log("error parsing xml-command: %s, got %s (starting with %s)" % (process_tools.get_except_info(),
                                                                                       logging_tools.get_plural("byte", len(in_data)),
                                                                                       in_data[:6]), logging_tools.LOG_LEVEL_ERROR)
        else:
            recv_flag_dict = recv_command.get_flag_dict()
            if recv_flag_dict.get("error", False):
                self.log("Got error result from server (command %s, sent %s)" % (recv_command.get_command(),
                                                                                 ok_com.get_command()))
            else:
                if recv_command.get_command() == "package_list":
                    if self.__lock_exists:
                        process_tools.set_lockfile_msg(LF_NAME, "got package list...")
                    p_elements = recv_command.getElementsByTagName("packages").item(0).getElementsByTagName("package")
                    self.log("got package_list from server with %s" % (logging_tools.get_plural("package", len(p_elements))))
                    self._start_rpm_thread()
                    # send request to rpm_queue
                    self.__rpm_queue.put(("rpm_request", p_elements))
                    del p_elements
                    #glfs_wfpi = 1
                elif recv_command.get_command() == "rsync_list":
                    if self.__lock_exists:
                        process_tools.set_lockfile_msg(LF_NAME, "got rsync list...")
                    r_elements = recv_command.getElementsByTagName("rsyncs").item(0).getElementsByTagName("rsync")
                    self.log("got rsync_list from server with %s" % (logging_tools.get_plural("rsync", len(r_elements))))
                    self._start_rsync_thread()
                    self.__rsync_queue.put(("rsync_request", r_elements))
                    del r_elements
                else:
                    self.log("Got command '%s' as result of command '%s'" % (recv_command.get_command(),
                                                                             ok_com.get_command()))
                del recv_command
                passed = True
        if passed:
            self._server_send_ok(flag_dict["send_idx"])
            self.get_thread_queue().put("connection_ok")
        else:
            self._send_error((ok_com, "error-flag set"))
    def _server_error(self, (why)):
        self.log("Error: %s" % (why), logging_tools.LOG_LEVEL_ERROR)
    def _server_ok(self, (com_obj, (src_ip, src_port), command)):
        self.log("Got %s from %s (port %d)" % (command, src_ip, src_port))
        if command == "new_config":
            self._get_package_list()
            ret_str = "ok got %s" % (command)
        elif command == "new_rsync_config":
            self._get_rsync_list()
            ret_str = "ok got %s" % (command)
        elif command == "status":
            num_ok, num_threads = (self.get_thread_pool().num_threads_running(False),
                                   self.get_thread_pool().num_threads(False))
            num_warn, num_error = (0, 0)
            if num_ok == num_threads:
                thread_info = "all %s running" % (logging_tools.get_plural("thread", num_ok))
            else:
                thread_info = "only %d of %s running" % (num_threads, logging_tools.get_plural("thread", num_ok))
                num_error += 1
            if self.__num_pack == self.__ok_pack:
                pack_info = "%s installed" % (logging_tools.get_plural("package", self.__num_pack))
            elif self.__error_pack:
                pack_info = "%s (%d installed, %s)" % (logging_tools.get_plural("package", self.__num_pack),
                                                       self.__ok_pack,
                                                       logging_tools.get_plural("error", self.__error_pack))
                num_error += 1
            else:
                pack_info = "%s (%d installed)" % (logging_tools.get_plural("package", self.__num_pack),
                                                   self.__ok_pack)
                num_warn += 1
            if self.__num_rsync == self.__ok_rsync:
                rsync_info = "%s installed" % (logging_tools.get_plural("rsync", self.__num_rsync))
            elif self.__error_rsync:
                rsync_info = "%s (%d installed, %s)" % (logging_tools.get_plural("rsync", self.__num_rsync),
                                                        self.__ok_rsync,
                                                        logging_tools.get_plural("error", self.__error_rsync))
                num_error += 1
            else:
                rsync_info = "%s (%d installed)" % (logging_tools.get_plural("rsync", self.__num_rsync),
                                                    self.__ok_rsync)
                num_warn += 1
            ret_str = "%s version %s %s, %s, %s" % (num_error and "error" or (num_warn and "warning" or "ok"),
                                                    VERSION_STRING,
                                                    thread_info,
                                                    pack_info,
                                                    rsync_info)
        elif command in ["rpm_list", "rpm_list_force"]:
            if command == "rpm_list_force":
                # send reload to rpm_queue
                self.__rpm_queue.put(("reload"))
            self.__rpm_queue.put(("get_rpm_list", com_obj))
            ret_str = ""
        else:
            self.log("unknown server_command '%s'" % (command), logging_tools.LOG_LEVEL_WARN)
            ret_str = "error unknown command %s" % (command)
        if ret_str:
            if command != "status" or ret_str.startswith("error"):
                self.log("returning %s" % (ret_str))
            com_obj.send_return(ret_str)
    def _init_info_files(self):
        self.__info_files = dict([(key, None) for key in ["packages", "rsyncs"]])
        if not os.path.isdir(self.__glob_config["VAR_DIR"]):
            self.log("var_dir %s not present" % (self.__glob_config["VAR_DIR"]),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            # init files
            for f_name in ["packages", "rsyncs"]:
                self.__info_files[f_name] = "%s/%s_status" % (self.__glob_config["VAR_DIR"],
                                                              f_name)
                self._update_info_file(f_name, "waiting for info", first_write=True)
    def _update_info_file(self, f_name, content, **args):
        if self.__info_files.has_key(f_name):
            if args.get("first_write", False):
                f_mode = "w"
            else:
                f_mode = "a"
            open(self.__info_files[f_name], f_mode).write("%s: %s\n" % (time.ctime(), content))
        else:
            logging_tools.my_syslog("%s: %s" % (f_name, content))
    def _rpm_info(self, in_list):
        #glfs_wfpi = 0
        self.__num_pack, self.__ok_pack, self.__error_pack = (0, 0, 0)
        for p_stat in in_list:
            self.__num_pack += 1
            if p_stat == "error":
                self.__error_pack += 1
            elif p_stat == "ok":
                self.__ok_pack += 1
        self.log("package status: %3d total, %3d ok, %3d error" % (self.__num_pack, self.__ok_pack, self.__error_pack))
        self._update_info()
    def _rsync_info(self, in_list):
        #glfs_wfpi = 0
        self.__num_rsync, self.__ok_rsync, self.__error_rsync = (0, 0, 0)
        for p_stat in [x for x in in_list if x]:
            self.__num_rsync += 1
            if p_stat == "error":
                self.__error_rsync += 1
            elif p_stat == "ok":
                self.__ok_rsync += 1
        self.log("rsync status: %3d total, %3d ok, %3d error" % (self.__num_rsync, self.__ok_rsync, self.__error_rsync))
        self._update_info()
    def _update_info(self):
        info_dict = {"packages" : self.__num_pack and "%d of %d%s" % (self.__ok_pack,
                                                                      self.__num_pack,
                                                                      self.__error_pack and ", %d error" % (self.__error_pack) or "") or "none",
                     "rsyncs"   : self.__num_rsync and "%d of %d%s" % (self.__ok_rsync,
                                                                       self.__num_rsync,
                                                                       self.__error_rsync and ", %d error" % (self.__error_rsync) or "") or "none"}
        for key in info_dict.keys():
            self._update_info_file(key, info_dict[key])
        if self.__lock_exists:
            all_ok = True
            if self.__num_pack:
                if self.__ok_pack != self.__num_pack or self.__error_pack:
                    all_ok = False
            if self.__num_rsync:
                if self.__ok_rsync != self.__num_rsync or self.__error_rsync:
                    all_ok = False
            process_tools.set_lockfile_msg(LF_NAME, "; ".join(["%s: %s" % (key, info_dict[key]) for key in sorted(info_dict.keys())]))
            if all_ok:
                self.send_pool_message("start_sge_execd")

class p_struct(object):
    def __init__(self, in_xml):
        self.in_xml = in_xml
        self.command = in_xml.attrib["command"]
        self.flag_names = ["nodeps", "force"]
        for f_name in self.flag_names:
            setattr(self, f_name, True if in_xml.attrib[f_name] == "1" else False)
        for s_name in ["name", "version", "release", "location"]:
            setattr(self, s_name, in_xml.xpath(".//ns:%s/text()" % (s_name), namespaces={"ns" : server_command.XML_NS})[0])
        self.__log_template = logging_tools.get_logger(
            "%s.%s" % (global_config["LOG_NAME"],
                       self.name.replace(".", r"\.")),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=p_struct.ips.zmq_context,
            init_logger=True)
        self.log("V/R is %s/%s" % (self.version, self.release))
        self.log("location is %s" % (self.location))
    def start(self):
        if self.command in ["install", "upgrade"]:
            self.__query_ok = False
            # init query of package on disk
            p_struct.ips._start_command(
                "dpkg -I %s" % (
                    self.location) if global_config["DEBIAN"] else "rpm -qp %s --queryformat=\"%s\"" % (
                        self.location,
                        p_struct.ips.query_format_str),
                self._disc_query_done,
                log_com=self.log)
    def set_result(self, res_str, res_level=logging_tools.LOG_LEVEL_OK):
        self.log(res_str, res_level)
        self.in_xml.attrib.update({
            "result_level" : "%d" % (res_level),
            "result_str"   : res_str,
            "result_ok"    : "1" if res_level in [logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_WARN] else "0"})
        del self.in_xml.attrib["pending"]
        self.send_info()
        print etree.tostring(self.in_xml, pretty_print=True)
        p_struct.handle()
        #p_struct.ips.package_command_done(self)
    def send_info(self):
        send_com = get_srv_command(command="package_info")
        send_com["package_info"] = copy.deepcopy(self.in_xml)
        p_struct.ips.send_to_server(send_com)
    @staticmethod
    def setup(ips, in_com):
        p_struct.ips = ips
        p_struct.cur_com = in_com
        pack_list = in_com.xpath(None, ".//ns:package")
        for pack in pack_list:
            # move to __init__
            print etree.tostring(pack)
            pack.attrib.update({
                "runs"   : "%d" % (0),
                "result" : "%d" % (0),
            })
        p_struct.p_struct_list = [p_struct(pack) for pack in pack_list]
        p_struct.p_struct_dict = dict([(cur_p.name, cur_p) for cur_p in p_struct.p_struct_list])
        p_struct.g_log("init with %s" % (logging_tools.get_plural("package", len(pack_list))))
        p_struct.handle()
    @staticmethod
    def cmp_element_runs(el_0, el_1):
        runs_0, runs_1 = (int(el_0.attrib["runs"]),
                          int(el_1.attrib["runs"]))
        if runs_0 < runs_1:
            return -1
        elif runs_0 == runs_1:
            return 0
        else:
            return 1
    @staticmethod
    def handle():
        p_list = p_struct.cur_com.xpath(None, ".//ns:package[@pending]")
        if not p_list:
            # nothing pending
            # find packages in non-OK state
            not_finished = p_struct.cur_com.xpath(None, ".//ns:package[not(@pending) and not(@result_ok='1')]")
            if not_finished:
                # generate run_dict
                not_finished = sorted(not_finished, p_struct.cmp_element_runs)
                # decide to go into another loop
                if len(not_finished) == len(p_struct.cur_com.xpath(None, ".//ns:package[@result_str = @previous_result_str and not(@result_ok='1')]")):
                    # all previous results are ident to the current ones
                    p_struct.g_log("results are still the same, exit")
                    p_struct.destroy()
                else:
                    first_nf = not_finished[0]
                    np_name = first_nf.xpath(".//ns:name/text()", namespaces={"ns" : server_command.XML_NS})[0]
                    first_nf.attrib["pending"] = "1"
                    cur_runs = int(first_nf.attrib["runs"])
                    if "result_str" in first_nf.attrib:
                        first_nf.attrib["previous_result_str"] = first_nf.attrib["result_str"]
                    # increase run by 1
                    first_nf.attrib["runs"] = "%d" % (cur_runs + 1)
                    p_struct.p_struct_dict[np_name].send_info()
                    p_struct.p_struct_dict[np_name].start()
            else:
                # every package done
                p_struct.destroy()
    @staticmethod
    def destroy():
        p_struct.g_log("destroying")
        for pack in p_struct.p_struct_list:
            pack.close()
        p_struct.p_struct_list, p_struct.p_struct_dict = ([], {})
        p_struct.ips.package_command_done(p_struct)
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        p_struct.ips.log("[p_struct] %s" % (what), log_level)
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(what, level)
    def close(self):
        self.log("close")
        self.__log_template.close()
    def _disc_query_done(self, sps):
        dp_info = None
        self.log("disc query of %s gave %d%s" % (
            self.location,
            sps.result,
            " (%s)" % (sps.stderr) if sps.result else ""),
                 logging_tools.LOG_LEVEL_ERROR if sps.result else logging_tools.LOG_LEVEL_OK)
        if not sps.result:
            if global_config["DEBIAN"]:
                val_dict = {}
                descr_mode = False
                for line in [s_line.strip() for s_line in sps.stdout.split("\n") if s_line.strip()]:
                    if descr_mode:
                        val_dict["description"] = "%s %s" % (val_dict["description"], line)
                    line_parts = line.split()
                    if line_parts[0].isdigit():
                        pass
                    else:
                        key = line_parts.pop(0).lower()
                        if key.endswith(":"):
                            key = key[:-1]
                        elif key in ["size"]:
                            pass
                        else:
                            key = None
                        if key:
                            val_dict[key] = " ".join(line_parts)
                            if key == "description":
                                descr_mode = True
                dp_info = {"name"    : val_dict["package"],
                           "version" : "-".join(val_dict["version"].split("-")[:-1]),
                           "release" : val_dict["version"].split("-")[-1]}
                # remove leading ":" from version
                if dp_info["version"].count(":"):
                    leading_dig = dp_info["version"].split(":")[0]
                    if leading_dig.isdigit():
                        dp_info["version"] = ":".join(dp_info["version"].split(":")[1:])
            else:
                p_info = p_struct.ips._parse_query_result(sps.stdout)
                if len(p_info) != 1:
                    self.set_result("error parsing result (%d != 1)" % (len(p_info)), logging_tools.LOG_LEVEL_ERROR)
                else:
                    pack_name, vr_info  = (p_info.keys()[0], p_info.values()[0])
                    if len(vr_info) != 1:
                        self.set_result("found more than one package info (%d)" % (len(vr_info)),
                                        logging_tools.LOG_LEVEL_ERROR)
                    else:
                        vr_info = vr_info[0]
                        dp_info = {"name"    : pack_name,
                                   "version" : vr_info["version"],
                                   "release" : vr_info["release"]}
        sps.close()
        if dp_info:
            # compare
            if all([getattr(self, key) == value for key, value in dp_info.iteritems()]):
                self.log("querying of disk package successfull")
                self.__query_ok = True
                # init query of (maybe) already installed package
                self._issue_sys_query("pre")
            else:
                self.set_result("disk_package differs from XML info", logging_tools.LOG_LEVEL_ERROR)
    def _issue_sys_query(self, mode="unknown"):
        self.sys_query_mode = mode
        p_struct.ips._start_command(
            "dpkg -l %s" % (
                self.name) if global_config["DEBIAN"] else "rpm -q %s --queryformat=\"%s\"" % (
                    self.name,
                    p_struct.ips.query_format_str),
            self._sys_query_done,
            log_com=self.log)
    def _sys_query_done(self, sps):
        self.log("sys query of %s (%s) gave %d (%s)" % (
            self.name,
            self.sys_query_mode,
            sps.result,
            sps.stderr.strip() or "<no stderr>"),
                 logging_tools.LOG_LEVEL_ERROR if sps.result else logging_tools.LOG_LEVEL_OK)
        if sps.result:
            self.log(sps.stdout.strip(), logging_tools.LOG_LEVEL_ERROR)
            pre_package = {}
        else:
            if global_config["DEBIAN"]:
                lines = [s_line.strip() for s_line in sps.stdout.split("\n")]
                # drop header-lines
                while True:
                    if lines.pop(0).count("=") > 20:
                        break
                pre_package = self._parse_query_result("\n".join(lines))
            else:
                pre_package = p_struct.ips._parse_query_result(sps.stdout)
        # build dict
        sys_dict = dict([("%s-%s-%s" % (self.name, value["version"], value["release"]), value) for value in pre_package.get(self.name, [])])
        if self.sys_query_mode == "pre":
            # store for post run
            self.pre_query_dict = sys_dict
            # pre-install mode
            if "%s-%s-%s" % (self.name, self.version, self.release) in sys_dict:
                # already installed
                self.set_result("package is already installed")
                #p_struct.ips.package_command_done(self)
            else:
                self._start_iue()
        elif self.sys_query_mode == "post":
            if not sys_dict:
                self.set_result("cannot verify installation", logging_tools.LOG_LEVEL_ERROR)
            else:
                if self.name in sys_dict:
                    for inst_pack in sys_dict[self.name]:
                        version_ok = (inst_pack["version"], inst_pack["release"]) == (self.version, self.release)
                        if version_ok:
                            self.set_result("found package")
                        else:
                            self.set_result("found package with wrong V/R %s/%s" % (
                                inst_pack["version"],
                                inst_pack["release"]),
                                            logging_tools.LOG_LEVEL_WARN)
                else:
                    self.set_result("package not found in dict (%s)" % (", ".join(sys_dict.keys())),
                                    logging_tools.LOG_LEVEL_ERROR)
            pre_dict = self.pre_query_dict
            if sys_dict and pre_dict:
                print "***", sys_dict, pre_dict
            #p_struct.ips.package_command_done(self)
        else:
            self.set_result("unknown query_mode %s, exiting" % (self.sys_query_mode),
                     logging_tools.LOG_LEVEL_ERROR)
            #p_struct.ips.package_command_done(self)
    def _start_iue(self):
        # start install / upgrade / erase
        if global_config["DEBIAN"]:
            pass
        else:
            rpm_flags = " ".join([value for key, value in [
                ("nodeps", "--nodeps"),
                ("force" , "--force" )] if getattr(self, key)])
            if self.command == "install":
                com_line = "rpm -iv %s %s" % (rpm_flags, 
                                              self.location)
            elif self.command == "upgrade":
                com_line = "rpm -Uv %s %s" % (rpm_flags, 
                                              self.location)
            else:
                com_line = "rpm -e %s %s" % (rpm_flags,
                                             self.name)
        self.log("issuing %s (%s) via %s" % (
            self.command,
            ", ".join(["%s=%s" % (key, str(getattr(self, key))) for key in self.flag_names]),
            com_line
        ))
        p_struct.ips._start_command(
            com_line,
            self._iue_command_done,
            log_com=self.log,
            stderr_join=True)
    def _iue_command_done(self, sps):
        self.log("iue command %s for %s gave %d" % (
            self.command,
            self.name,
            sps.result),
                 logging_tools.LOG_LEVEL_ERROR if sps.result else logging_tools.LOG_LEVEL_OK)
        for l_num, cur_line in enumerate(sps.stdout.strip().split("\n")):
            self.log(" - %3d %s" % (l_num + 1, cur_line))
        if sps.result:
            # error, close 
            self.set_result("iue command %s gave (%d): %s" % (
                self.command,
                sps.result,
                sps.stdout.strip()),
                            logging_tools.LOG_LEVEL_ERROR)
            #p_struct.ips.package_command_done(self)
        else:
            # check install
            self._issue_sys_query("post")
    def __unicode__(self):
        return "%s (%s-%s) %s from %s" % (
            self.command,
            self.version,
            self.release,
            self.name,
            self.location)

def get_srv_command(**kwargs):
    return server_command.srv_command(
        package_client_version=VERSION_STRING,
        debian="1" if global_config["DEBIAN"] else "0",
        **kwargs)

class subprocess_struct(object):
    cur_idx = 0
    def __init__(self, com_line, log_com, cb_func=None, **kwargs):
        self.com_line = com_line
        self.log_com = log_com
        subprocess_struct.cur_idx += 1
        self.cur_idx = subprocess_struct.cur_idx
        self.log("commandline is '%s'" % (self.com_line))
        self.result = None
        self.cb_func = cb_func
        self.stderr_join = kwargs.get("stderr_join", False)
        self.s_time = time.time()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[sp %d] %s" % (self.cur_idx, what), log_level)
    def run(self):
        self.popen = subprocess.Popen(
            self.com_line,
            shell=True, 
            stderr=subprocess.STDOUT if self.stderr_join else subprocess.PIPE,
            stdout=subprocess.PIPE)
        self.stderr, self.stdout = ("", "")
    def check(self):
        p_res = self.popen.poll()
        self._read()
        if p_res is not None:
            self.result = p_res
            self.log("finished in %s" % (logging_tools.get_diff_time_str(time.time() - self.s_time)))
            if self.cb_func:
                self._read()
                self.cb_func(self)
    def _read(self):
        if not self.stderr_join:
            if select.select([self.popen.stderr.fileno()], [], [], 0)[0]:
                self.stderr = "%s%s" % (self.stderr, self.popen.stderr.read())
        if select.select([self.popen.stdout.fileno()], [], [], 0)[0]:
            self.stdout = "%s%s" % (self.stdout, self.popen.stdout.read())
    def close(self):
        self.cb_func = None
        del self.popen
        self.stderr = None
        self.stdout = None
            
class install_process(threading_tools.process_obj):
    """ handles all install and external command stuff """
    def __init__(self, name):
        threading_tools.process_obj.__init__(
            self,
            name,
            loop_timer=1000.0)
        self.commands = []
        self.register_func("get_rpm_list", self._get_rpm_list)
        self.register_func("command_batch", self._command_batch)
        # set rpm-query options
        self.query_format_str = "n%{NAME}\\nv%{VERSION}\\nr%{RELEASE}\\nt%{INSTALLTIME}\\ns%{SIZE}\\na%{ARCH}\\nS%{SUMMARY}\\n"
        self.rel_dict = {"n" : "name",
                         "r" : "release",
                         "v" : "version",
                         "t" : "installtime",
                         "s" : "size",
                         "a" : "arch",
                         "S" : "summary"}
        self.packages_valid = False
        # commands pending becaus of missing package list
        self.pending_commands = []
        # list of pending package commands
        self.package_commands = []
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
    def _get_rpm_list(self, *args, **kwargs):
        del self.packages
        if global_config["DEBIAN"]:
            self._start_command("dpkg -l", self._dpkg_list_done)
        else:
            self._start_command("rpm -qa --queryformat=\"%s\"" % (self.query_format_str), self._rpm_list_done)
        #self._start_command("rpm -qa", self._rpm_list_done)
    def _dpkg_list_done(self, sps):
        self.log("dpkg_list_done not implemented", logging_tools.LOG_LEVEL_CRITICAL)
    def _rpm_list_done(self, sps):
        packages = self._parse_query_result(sps.stdout)
        sps.close()
        mult_keys = [key for key, p_list in packages.iteritems() if len(p_list) > 1]
        self.log("Found %s [%s where more than one version/release is installed: %s]" % (
            logging_tools.get_plural("unique package-name", len(packages)),
            logging_tools.get_plural("package", len(mult_keys)),
            ", ".join(["%s (%s)" % (key, logging_tools.get_plural("instance", len(packages[key]))) for key in mult_keys])))
        self.packages = packages
    def _parse_query_result(self, lines):
        packages, act_p = ({}, None)
        if global_config["DEBIAN"]:
            for line in [s_line for s_line in [c_line.strip() for c_line in lines.split("\n")] if c_line]:
                try:
                    flags, name, verrel, info = line.split(None, 3)
                except:
                    pass
                else:
                    if verrel.count("-"):
                        ver, rel = verrel.split("-", 1)
                    else:
                        ver, rel = (verrel, "0")
                    if len(flags) == 2:
                        desired_flag, status_flag = flags
                        error_flag = ""
                    else:
                        desired_flag, status_flag, error_flag = flags
                    if desired_flag == "p":
                        # package is purged
                        pass
                    elif desired_flag == "r":
                        # package is removed
                        pass
                    else:
                        packages.setdefault(name, []).append({
                            "flags"       : (desired_flag, status_flag, error_flag),
                            "version"     : ver,
                            "release"     : rel,
                            "summary"     : info,
                            "installtime" : time.time(),
                            "name"        : name})
        else:
            for pfix, pline in map(lambda c_line: (c_line[0], c_line[1:]), map(lambda el: el.strip() if el.strip() else "- ", lines.split("\n"))):
                if pline.strip():
                    if pfix == "n":
                        act_p = {"name" : pline.strip()}
                    else:
                        # ignore unknown prefixes
                        if act_p and self.rel_dict.has_key(pfix):
                            dname = self.rel_dict[pfix]
                            act_p[dname] = pline.strip()
                    if pfix == "t" and act_p:
                        packages.setdefault(act_p["name"], []).append(act_p)
                        act_p = {}
        return packages
    def _start_command(self, com_line, cb_func, **kwargs):
        if not self.commands:
            # first command
            self.register_timer(self._check_delayed, 1.)
            self.loop_granularity = 10.0
            self.lock_exit()
        new_sp = subprocess_struct(com_line, kwargs.pop("log_com", self.log), cb_func, **kwargs)
        new_sp.run()
        self.commands.append(new_sp)
    def _check_delayed(self):
        done_list = []
        for cur_com in self.commands:
            cur_com.check()
        self.commands = [cur_com for cur_com in self.commands if cur_com.result is None]
        if not self.commands:
            self.unregister_timer(self._check_delayed)
            self.unlock_exit()
    def _command_batch(self, com_list, *args, **kwargs):
        com_list = [server_command.srv_command(source=cur_com) for cur_com in com_list]
        self.pending_commands.extend(com_list)
        self.handle_pending_commands()
    def send_to_server(self, send_xml):
        self.send_pool_message("send_to_server", send_xml["command"].text, unicode(send_xml))
    def _transform(self, in_com):
        t_result = None
        # transform xml snippet (or other data) to a valid package_struct
        if type(in_com) == server_command.srv_command and in_com.xpath(None, ".//ns:packages"):
            p_struct.setup(self, in_com)
            t_result = p_struct
        else:
            self.log("unknown type '%s' for _transform" % (str(type(in_com))), logging_tools.LOG_LEVEL_ERROR)
        return t_result
    def add_package_command(self, in_com):
        t_com = self._transform(in_com)
        if t_com is not None:
            self.package_commands.append(t_com)
        self.log(logging_tools.get_plural("package command", len(self.package_commands)))
    def package_command_done(self, t_com):
        self.package_commands.remove(t_com)
        self.handle_pending_commands()
    def handle_pending_commands(self):
        self.log("%s, packages_list is %s" % (logging_tools.get_plural("pending command", len(self.pending_commands)),
                                              "valid" if self.packages_valid else "invalid"))
        while self.packages_valid and self.pending_commands and not self.package_commands:
            # now the fun starts, we have a list of commands and a valid local package list
            first_com = self.pending_commands.pop(0)
            cur_com = first_com["command"].text
            self.log("try to handle %s" % (cur_com))
            if cur_com in ["send_info"]:
                self.log("... ignoring", logging_tools.LOG_LEVEL_WARN)
            elif cur_com in ["package_list"]:
                if len(first_com.xpath(None, ".//ns:packages/ns:package")):
                    #cur_pack = p_list[0]
                    #cur_pack.getparent().remove(cur_pack)
                    # reinsert
                    #self.pending_commands.insert(0, first_com)
                    self.add_package_command(first_com)
                else:
                    self.log("empty package_list, removing")
    
class server_process(threading_tools.process_pool):
    def __init__(self):
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
            )
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "package_client.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                       zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        # init environment
        self._init_environment()
        self._init_msi_block()
        self.register_exception("int_error"  , self._int_error)
        self.register_exception("term_error" , self._int_error)
        self.register_exception("alarm_error", self._alarm_error)
        # set lockfile
        process_tools.set_lockfile_msg(LF_NAME, "connect...")
        # log buffer
        self._show_config()
        # log limits
        self._log_limits()
        self._init_network_sockets()
        self.register_func("send_to_server", self._send_to_server)
        self.add_process(install_process("install"), start=True)
        self.send_to_process("install",
                             "get_rpm_list")
        if False:
            # automounter check counter
            self.__automounter_checks = 0
            self.__automounter_valid = not self.__glob_config["CHECK_AUTOMOUNTER"]
            self.__am_checker = process_tools.automount_checker()
            # register funcs
            #self.register_func("set_target_retry_speed", self._set_target_retry_speed)
            #self.register_func("new_pid", self._new_pid)
            #self.register_func("threads_alive", self._threads_alive)
            #self.register_func("force_exit", self._int_error)
            self.register_func("start_sge_execd", self._start_sge_execd)
            #self.__last_hello_call = time.time()
            #self.__last_tqi_was_clean = False
        # sge start option
        self.__sge_execd_started = False
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                cur_lev, cur_what = self.__log_cache.pop(0)
                self.__log_template.log(cur_lev, cur_what)
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_environment(self):
        # Debian fix to get full package names, sigh ...
        os.environ["COLUMNS"] = "2000"
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-client")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/package-client start"
            msi_block.stop_command = "/etc/init.d/package-client force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _log_limits(self):
        # read limits
        r_dict = {}
        try:
            import resource
        except ImportError:
            self.log("cannot import resource", logging_tools.LOG_LEVEL_CRITICAL)
        else:
            available_resources = [key for key in dir(resource) if key.startswith("RLIMIT")]
            for av_r in available_resources:
                try:
                    r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
                except ValueError:
                    r_dict[av_r] = "invalid resource"
                except:
                    r_dict[av_r] = None
            if r_dict:
                res_keys = sorted(r_dict.keys())
                self.log("%s defined" % (logging_tools.get_plural("limit", len(res_keys))))
                res_list = logging_tools.new_form_list()
                for key in res_keys:
                    val = r_dict[key]
                    if type(val) == type(""):
                        info_str = val
                    elif type(val) == type(()):
                        info_str = "%8d (hard), %8d (soft)" % val
                    else:
                        info_str = "None (error?)"
                    res_list.append([logging_tools.form_entry(key, header="key"),
                                     logging_tools.form_entry(info_str, header="value")])
                for line in str(res_list).split("\n"):
                    self.log(line)
            else:
                self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)
    def _init_network_sockets(self):
        #client = self.zmq_context.socket(zmq.ROUTER)
        #client.setsockopt(zmq.IDENTITY, "package-client:%s" % (process_tools.get_machine_name()))
        #client.setsockopt(zmq.HWM, 256)
        #conn_str = "tcp://*:%d" % (global_config["COM_PORT"])
        #client.bind(conn_str)
        #self.log("bind to %s" % (conn_str))
        #self.com_socket = client
        #self.register_poller(self.com_socket, zmq.POLLIN, self._recv)
        # connect to server
        srv_port = self.zmq_context.socket(zmq.DEALER)
        srv_port.setsockopt(zmq.LINGER, 1000)
        srv_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        #srv_port.setsockopt(zmq.SUBSCRIBE, "")
        conn_str = "tcp://%s:%d" % (global_config["PACKAGE_SERVER"],
                                    global_config["SERVER_PUB_PORT"])
        srv_port.connect(conn_str)
        #pull_port = self.zmq_context.socket(zmq.PUSH)
        #pull_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        self.register_poller(srv_port, zmq.POLLIN, self._recv)
        srv_port.send_unicode(unicode(get_srv_command(command="register")))
        srv_port.send_unicode(unicode(get_srv_command(command="get_package_list")))
        srv_port.send_unicode(unicode(get_srv_command(command="get_rsync_list")))
        self.srv_port = srv_port
        self.log("connected to %s" % (conn_str))
    def _send_to_server(self, src_proc, *args, **kwargs):
        src_pid, com_name, send_com = args
        self.log("sending %s to server" % (com_name))
        self.srv_port.send_unicode(send_com)
    def _recv(self, zmq_sock):
        batch_list = []
        while True:
            data = []
            while True:
                try:
                    data.append(server_command.srv_command(source=zmq_sock.recv_unicode()))
                except:
                    self.log("error decoding command: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                if not zmq_sock.getsockopt(zmq.RCVMORE):
                    break
            batch_list.extend(data)
            if not zmq_sock.poll(zmq.POLLIN):
                break
        batch_list = self._optimize_list(batch_list)
        self.send_to_process("install",
                             "command_batch",
                             [unicode(cur_com) for cur_com in batch_list])
    def _optimize_list(self, in_list):
        #print [cur_el["command"].text for cur_el in in_list]
        #print in_list[0].pretty_print()
        return in_list
    def _threads_alive(self):
        self.log("All threads alive")
        if not self.__automounter_valid:
            if self.__glob_config["CHECK_AUTOMOUNTER"]:
                self.__automounter_checks += 1
                self.log("checking automounter (iteration %d of %d)" % (self.__automounter_checks,
                                                                        self.__glob_config["MAX_AUTOMOUNTER_CHECKS"]))
                if self.__automounter_checks > self.__glob_config["MAX_AUTOMOUNTER_CHECKS"]:
                    self.log("Checked automounter for %s, giving up" % (logging_tools.get_plural("time", self.__glob_config["MAX_AUTOMOUNTER_CHECKS"])),
                             logging_tools.LOG_LEVEL_CRITICAL)
                    self._int_error("automounter failure")
                else:
                    self.__automounter_valid = self._check_automounter()
                    if not self.__automounter_valid:
                        self.log("Automounter not valid (iteration %d of %d), restarting and delaying check for %s" % (self.__automounter_checks,
                                                                                                                       self.__glob_config["MAX_AUTOMOUNTER_CHECKS"],
                                                                                                                       logging_tools.get_plural("second", self.__glob_config["AUTOMOUNTER_WAIT_TIME"])),
                                 logging_tools.LOG_LEVEL_WARN)
                        stat, log_lines = process_tools.submit_at_command(self.__am_checker.get_restart_command())
                        for log_line in log_lines:
                            self.log(log_line)
                        self.__comsend_queue.put(("delay", (self.__glob_config["AUTOMOUNTER_WAIT_TIME"], self.get_own_queue(), "threads_alive")))
                    else:
                        self.log("Automounter valid")
        if self.__automounter_valid:
            self.__comsend_queue.put("get_package_list")
            self.__comsend_queue.put("get_rsync_list")
    def _check_automounter(self):
        self.log("checking automounter settings")
        if self.__am_checker.valid():
            self.__am_checker.check()
            am_ok = self.__am_checker.automounter_ok()
        else:
            self.log("am_checker settings not valid, settings am_status to False")
            am_ok = False
        self.log("status of automounter is %s" % (str(am_ok)))
        return am_ok
##    def _set_target_retry_speed(self, speed):
##        if speed != self.__act_speed:
##            if self["exit_requested"] and speed > self.__act_speed:
##                # only decrease retry-speed when exiting
##                pass
##            else:
##                self.log("changing target_retry_speed from %d to %d (seconds)" % (self.__act_speed, speed))
##                self.__act_speed = speed
##                self.__ns.set_timeout(speed)
    def _int_error(self, err_cause):
        self.__exit_cause = err_cause
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("got int_error, err_cause is '%s'" % (err_cause), logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
    def _alarm_error(self, err_cause):
        self.__comsend_queue.put("reload")
##    def loop_function(self):
##        self.__ns.step()
##        self._show_tqi()
##        act_time = time.time()
##        if abs(self.__last_hello_call - act_time) > 2:
##            self.__last_hello_call = act_time
##            self.__comsend_queue.put("hello")
##    def _show_tqi(self):
##        tqi_dict = self.get_thread_queue_info()
##        tq_names = sorted(tqi_dict.keys())
##        tqi_info = [(t_name,
##                     tqi_dict[t_name][1],
##                     tqi_dict[t_name][0]) for t_name in tq_names if tqi_dict[t_name][1]]
##        if tqi_info:
##            self.log("tqi: %s" % (", ".join(["%s: %3d of %3d" % (t_name, t_used, t_total) for (t_name, t_used, t_total) in tqi_info])))
##            self.__last_tqi_was_clean = False
##        else:
##            if not self.__last_tqi_was_clean:
##                self.__last_tqi_was_clean = True
##                self.log("tqi: clean")
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.srv_port.close()
        #self.com_socket.close()
        self.__log_template.close()
    def _start_sge_execd(self):
        if not self.__sge_execd_started:
            if self.__glob_config["START_SGE_EXECD"]:
                sge_execd = self.__glob_config["SGE_EXECD_LOCATION"]
                if os.path.isfile(sge_execd):
                    # check if already running
                    sge_dict = dict([(value["name"], key) for key, value in process_tools.get_proc_list().iteritems() if value["name"].startswith("sge")])
                    if sge_dict.has_key("sge_execd"):
                        self.log("sge_execd already running with pid %d" % (sge_dict["sge_execd"]),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("starting sge_execd from %s" % (sge_execd))
                        stat, log_lines = process_tools.submit_at_command("%s start" % (sge_execd), 1)
                        for log_line in log_lines:
                            self.log(log_line)
                    self.__sge_execd_started = True
                else:
                    self.log("file %s for start_sge_execd() not found" % (sge_execd),
                             logging_tools.LOG_LEVEL_ERROR)
    
global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    process_tools.delete_lockfile(LF_NAME, None, 0)
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("PID_NAME"               , configfile.str_c_var("%s/%s" % (prog_name, prog_name))),
        ("DEBUG"                  , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"              , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("VERBOSE"                , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("KILL_RUNNING"           , configfile.bool_c_var(True)),
        ("POLL_INTERVALL"         , configfile.int_c_var(5, help_string="poll intervall")),
        ("EXIT_ON_FAIL"           , configfile.bool_c_var(False, help_string="exit on fail [%(default)s]")),
        ("COM_PORT"               , configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="node to bind to [%(default)d]")),
        ("SERVER_PUB_PORT"          , configfile.int_c_var(P_SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"         , configfile.int_c_var(P_SERVER_PULL_PORT, help_string="server pull port [%(default)d]")),
        ("LOG_DESTINATION"        , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"               , configfile.str_c_var(prog_name)),
        ("CHECK_AUTOMOUNTER"      , configfile.bool_c_var(True, help_string="check automounter [%(default)s]")),
        ("MAX_AUTOMOUNTER_CHECKS" , configfile.int_c_var(5, help_string="number of automounter checks [%(default)d]")),
        ("AUTOMOUNTER_WAIT_TIME"  , configfile.int_c_var(30, help_string="time to wait for automounter [%(default)d]")),
        ("START_SGE_EXECD"        , configfile.bool_c_var(True, help_string="start sge_execd after successfull install [%(default)s]")),
        ("SGE_EXECD_LOCATION"     , configfile.str_c_var("/etc/init.d/sgeexecd", help_string="location of sge_execd script [%(default)s")),
        ("VAR_DIR"                , configfile.str_c_var("/var/lib/cluster/package-client", help_string="location of var-directory [%(default)s]")),
        ("PACKAGE_SERVER_FILE"    , configfile.str_c_var("/etc/packageserver", help_string="filename where packageserver location is stored [%(default)s]"))
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False,
                                               partial=False)
    ps_file_name = global_config["PACKAGE_SERVER_FILE"]
    if not os.path.isfile(ps_file_name):
        try:
            file(ps_file_name, "w").write("localhost\n")
        except:
            print "error writing to %s: %s" % (ps_file_name, process_tools.get_except_info())
            sys.exit(5)
        else:
            pass
    try:
        global_config.add_config_entries([
            ("PACKAGE_SERVER", configfile.str_c_var(file(ps_file_name, "r").read().strip().split("\n")[0].strip()))
        ])
    except:
        print "error reading from %s: %s" % (ps_file_name, process_tools.get_except_info())
        sys.exit(5)
    global_config.add_config_entries([("DEBIAN", configfile.bool_c_var(os.path.isfile("/etc/debian_version")))])
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    process_tools.fix_directories(0, 0, [global_config["VAR_DIR"]])
    process_tools.renice()
    if not global_config["DEBUG"]:
        process_tools.become_daemon(mother_hook = process_tools.wait_for_lockfile, mother_hook_args = (LF_NAME, 5, 200))
    else:
        print "Debugging %s on %s" % (prog_name, process_tools.get_machine_name())
        # no longer needed
        #global_config["LOG_DESTINATION"] = "stdout"
    ret_code = server_process().loop()
    process_tools.delete_lockfile(LF_NAME, None, 0)
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
