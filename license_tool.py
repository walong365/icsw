#!/usr/bin/python-init -Otu
#
# Copyright (C) 2012,2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# encoding: -*- utf8 -*-
#
# This file is part of init-license-tools
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

""" ask license server and return XML-represenation of license situation """

import sys
import subprocess
import logging_tools
import time
from lxml import etree
from lxml.builder import E
import datetime
import argparse

class license_check(object):
    def __init__(self, **kwargs):
        self.log_com = kwargs.get("log_com", None)
        self.lmutil_path = kwargs.get("lmutil_path", "/opt/cluster/bin/lmutil")
        self.server_addr = kwargs.get("server", "localhost")
        if self.server_addr.startswith("/"):
            self.server_addr = file(self.server_addr, "r").read().strip().split()[0]
        self.server_port = kwargs.get("port", "1055")
        if type(self.server_port) not in [int, long]:
            if self.server_port.startswith("/"):
                self.server_port = file(self.server_port, "r").read().strip().split()[0]
            self.server_port = int(self.server_port)
        self.log("license server at %s (port %d)" % (self.server_addr, self.server_port))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        what = u"[lc] %s" % (what)
        if self.log_com:
            self.log_com(log_level, what)
        else:
            logging_tools.my_syslog("[%d] %s" % (log_level, what))
    def call_external(self, com_line):
        popen = subprocess.Popen(com_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ret_code = popen.wait()
        return ret_code, popen.stdout.read()
    def check(self):
        s_time = time.time()
        self.log("starting check")
        ext_code, ext_lines = self.call_external("%s lmstat -a -c %d@%s" % (
            self.lmutil_path,
            self.server_port,
            self.server_addr))
        ret_struct = E.license_info(server_address=self.server_addr,
                                    server_port="%d" % (self.server_port))
        if ext_code:
            ret_struct.attrib.update({
                "state" : "%d" % (logging_tools.LOG_LEVEL_ERROR),
                "info"  : "%s" % (ext_lines)})
            line_num = 0
        else:
            ret_struct.attrib.update({
                "state" : "%d" % (logging_tools.LOG_LEVEL_OK),
                "info"  : "call successfull"})
            ret_struct.append(E.license_servers())
            ret_struct.append(E.licenses())
            found_server = set()
            cur_lic, cur_srv = (None, None)
            cur_year = datetime.datetime.now().year
            # populate structure
            for line_num, line in enumerate(ext_lines.split("\n")):
                if not line.strip():
                    continue
                lline = line.lower()
                lparts = lline.strip().split()
                if lline.count("license server status"):
                    server_info = lparts[-1]
                    server_port, server_addr = server_info.split("@")
                    found_server.add(server_addr)
                    cur_srv = E.server(info=server_info, address=server_addr, port=server_port)
                    ret_struct.find("license_servers").append(cur_srv)
                if cur_srv is not None:
                    if lline.count("license file"):
                        cur_srv.append(E.license_file(" ".join(lparts[4:])))
                if lline.strip().startswith("users of"):
                    cur_srv = None
                    cur_lic_version = None
                    cur_lic = E.license(name=lparts[2][:-1],
                                        issued=lparts[5],
                                        used=lparts[10],
                                        reserved="0",
                                        free="%d" % (int(lparts[5]) - int(lparts[10])))
                    ret_struct.find("licenses").append(cur_lic)
                if cur_lic is not None:
                    if "\"%s\"" % (cur_lic.attrib["name"]) == lparts[0]:
                        cur_lic_version = E.version(
                            version=lparts[1].replace(",", ""),
                            vendor=lparts[-1],
                            floating="false")
                        cur_lic.append(cur_lic_version)
                    else:
                        if cur_lic_version is not None:
                            if lparts[0] == "floating":
                                cur_lic_version.attrib["floating"] = "true"
                            elif lparts[1].count("reservation"):
                                if cur_lic_version.find("reservations") is None:
                                    cur_lic_version.append(E.reservations())
                                cur_lic_version.find("reservations").append(E.reservation(
                                    num=lparts[0],
                                    target=" ".join(lparts[3:])
                                ))
                                cur_lic.attrib["reserved"] = "%d" % (int(cur_lic.attrib["reserved"]) + int(lparts[0]))
                            else:
                                if cur_lic_version.find("usages") is None:
                                    cur_lic_version.append(E.usages())
                                # add usage
                                if lparts[-1].count("license"):
                                    num_lics = int(lparts[-2])
                                    lparts.pop(-1)
                                    lparts.pop(-1)
                                    lparts[-1] = lparts[-1][:-1]
                                else:
                                    num_lics = 1
                                start_data = " ".join(lparts[7:])
                                # remove linger info (if present)
                                start_data = (start_data.split("(")[0]).strip()
                                co_datetime = datetime.datetime.strptime(
                                    "%d %s" % (cur_year,
                                               start_data.title()), "%Y %a %m/%d %H:%M")
                                cur_lic_version.find("usages").append(E.usage(
                                    num="%d" % (num_lics),
                                    user=lparts[0],
                                    client_long=lparts[1],
                                    client_short=lparts[2],
                                    client_version=lparts[3][1:-1],
                                    checkout_time="%.2f" % (time.mktime(co_datetime.timetuple())),
                                ))
        e_time = time.time()
        ret_struct.attrib["run_time"] = "%.3f" % (e_time - s_time)
        self.log("done, %d lines in %s" % (line_num, logging_tools.get_diff_time_str(e_time - s_time)))
        return ret_struct
        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1055, help="license server [%(default)d]")
    parser.add_argument("--server", type=str, default="localhost", help="license port [%(default)s]")
    parser.add_argument("--mode", type=str, default="xml", choices=["xml", "check", "csv"], help="output mode [%(default)s]")
    parser.add_argument("--check-eval", type=str, default="true", help="check string, should return true or false")
    opts = parser.parse_args()
    my_lc = license_check(
        server=opts.server,
        port=opts.port,
    )
    xml_res = my_lc.check()
    ret_code = 0
    if opts.mode == "xml":
        print etree.tostring(xml_res, pretty_print=True)
    elif opts.mode == "check":
        glob_dict = {}
        for cur_lic in xml_res.findall(".//license"):
            lic_name = cur_lic.attrib["name"]
            for attr_name in ["issued", "used", "free", "reserved"]:
                glob_dict["%s_%s" % (lic_name, attr_name)] = int(cur_lic.attrib[attr_name])
        ret_val = eval(opts.check_eval, glob_dict)
        if not ret_val:
            ret_code = 1
    elif opts.mode == "csv":
        for cur_lic in xml_res.findall(".//license"):
            print ",".join(
                [
                    cur_lic.attrib["name"],
                    cur_lic.attrib["issued"],
                    cur_lic.attrib["used"],
                    cur_lic.attrib["free"],
                    cur_lic.attrib["reserved"],
                ]
            )
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
    