#!/usr/bin/python-init -Otu
#
# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# encoding: -*- utf8 -*-
#
# This file is part of init-license-tools
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
""" ask license server and return an XML-represenation of license situation """



import argparse
import sys

from lxml import etree

from initat.tools import logging_tools, sge_license_tools


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1055, help="license server [%(default)d]")
    parser.add_argument("--server", type=str, default="localhost", help="license port [%(default)s]")
    parser.add_argument("--license-file", type=str, default="", help="to query multiple servers, format is {PORT@ADDR}:{PORT@ADDR} [%(default)s]")
    parser.add_argument("--mode", type=str, default="xml", choices=["xml", "check", "csv", "list"], help="output mode [%(default)s]")
    parser.add_argument("--check-eval", type=str, default="true", help="check string, should return true or false")
    opts = parser.parse_args()
    if opts.license_file:
        my_lc = sge_license_tools.LicenseCheck(
            license_file=opts.license_file
        )
    else:
        my_lc = sge_license_tools.LicenseCheck(
            server=opts.server,
            port=opts.port,
        )
    xml_res = my_lc.check()
    ret_code = 0
    if opts.mode == "xml":
        print(etree.tostring(xml_res, pretty_print=True))  # @UndefinedVariable
    elif opts.mode == "check":
        glob_dict = {}
        for cur_lic in xml_res.findall(".//license"):
            lic_name = cur_lic.attrib["name"]
            for attr_name in ["issued", "used", "free", "reserved"]:
                glob_dict["{}_{}".format(lic_name, attr_name)] = int(cur_lic.attrib[attr_name])
        ret_val = eval(opts.check_eval, glob_dict)
        if not ret_val:
            ret_code = 1
    elif opts.mode == "csv":
        print(",".join(["name", "issued", "used", "free", "reserved"]))
        for cur_lic in xml_res.findall(".//license"):
            print(
                ",".join(
                    [
                        cur_lic.attrib["name"],
                        cur_lic.attrib["issued"],
                        cur_lic.attrib["used"],
                        cur_lic.attrib["free"],
                        cur_lic.attrib["reserved"],
                    ]
                )
            )
    elif opts.mode == "list":
        out_form = logging_tools.NewFormList()
        for cur_lic in xml_res.findall(".//license"):
            out_form.append(
                [
                    logging_tools.form_entry(cur_lic.attrib["name"], header="name"),
                    logging_tools.form_entry_right(cur_lic.attrib["issued"], header="issued"),
                    logging_tools.form_entry_right(cur_lic.attrib["used"], header="used"),
                    logging_tools.form_entry_right(cur_lic.attrib["free"], header="free"),
                    logging_tools.form_entry_right(cur_lic.attrib["reserved"], header="reserved"),
                ]
            )
        print(str(out_form))
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
