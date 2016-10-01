# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel (mallinger@init.at, lang-nevyjel@init.at)
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw
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
import os
import sys
import traceback
import urllib
import urllib2

from lxml import etree

from initat.cluster.backbone import license_file_reader
from initat.cluster.backbone.models import License, device_variable
from initat.constants import VERSION_CS_NAME
from initat.tools import process_tools, hfp_tools, config_store, logging_tools

__all__ = [
    "main",
]


if process_tools.get_machine_name() in ["eddie"]:
    REGISTRATION_URL = "http://localhost:8081/icsw/api/v2/GetLicenseFile"
else:
    REGISTRATION_URL = "http://www.initat.org/cluster/registration"


def show_license_info(opts):
    def len_info(type_str, in_f):
        if len(in_f):
            return "{} ({})".format(
                logging_tools.get_plural(type_str, len(in_f)),
                ", ".join(sorted(list(in_f))),
            )
        else:
            return "no {}".format(type_str)

    _infos = License.objects.get_license_info()
    print("License info, {}:".format(logging_tools.get_plural("entry", len(_infos))))
    for _info in _infos:
        _cl_info = sorted(list(set(_info["cluster_licenses"].keys()) | set(_info["parameters"].keys())))
        print("")
        print("-" * 40)
        print("")
        print(
            "Customer: {}, name: {}, type: {}, {}".format(
                _info["customer"],
                _info["name"],
                _info["type_name"],
                len_info("Cluster", _cl_info),
            )
        )
        for _cl_name in _cl_info:
            _sets = {"lics": set(), "paras": set()}
            for _skey, _dkey in [("cluster_licenses", "lics"), ("parameters", "paras")]:
                # import pprint
                # pprint.pprint(_info)
                for _entry in _info.get(_skey, {}).get(_cl_name, []):
                    # print _entry
                    _sets[_dkey].add(_entry["id"])
            print(
                "Cluster {}: {}, {}".format(
                    _cl_name,
                    len_info("License", _sets["lics"]),
                    len_info("Parameter", _sets["paras"]),
                )
            )


def _install_license(content):
    try:
        content_xml = etree.fromstring(content)
    except:
        print("Error interpreting license: {}".format(process_tools.get_except_info()))
        sys.exit(-1)

    for message_xml in content_xml.xpath("//messages/message"):
        prefix = {
            20: "",
            30: "Warning: ",
            40: "Error: "
        }.get(int(message_xml.get('log_level')), "")
        print("{}{}".format(prefix, message_xml.text))

    code = int(content_xml.find("header").get("code"))
    if code < 40:  # no error
        lic_file_node = content_xml.xpath("//values/value[@name='license_file']")
        if len(lic_file_node):
            lic_file_content = lic_file_node[0].text
            # validate
            # NOTE: this check currently isn't functional as the license file contains the creation time
            if License.objects.license_exists(lic_file_content):
                print("License file already added.")
            else:
                license_file_reader.LicenseFileReader(lic_file_content)
                new_lic = License(file_name="uploaded_via_command_line", license_file=lic_file_content)
                new_lic.save()
                print("Successfully added license file: {}".format(unicode(new_lic)))
    else:
        print ("Exiting due to errors.")
        sys.exit(1)


def install_license_file(opts):
    if not os.path.exists(opts.licensefile):
        print("Licensefile {} not readable".format(opts.licensefile))
        sys.exit(0)
    _install_license(file(opts.licensefile, "r").read())


def register_cluster(opts):

    cluster_id = device_variable.objects.get_cluster_id()
    _dict = {
        'username': opts.user,
        'password': opts.password,
        'cluster_name': opts.cluster_name,
        'cluster_id': cluster_id,
        "fingerprint": hfp_tools.get_server_fp(serialize=True),
    }
    _vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
    for _df in ["database", "software", "models"]:
        _dict["{}_version".format(_df)] = _vers[_df]

    data = urllib.urlencode(_dict)

    try:
        res = urllib2.urlopen(REGISTRATION_URL, data)
    except urllib2.URLError as e:
        print("Error while accessing registration: {}".format(e))
        traceback.print_exc(e)
        sys.exit(1)
    else:
        content = res.read()
        _install_license(content)


def show_cluster_id(opts):
    if opts.raw:
        print(device_variable.objects.get_cluster_id())
    else:
        print("")
        print("ClusterID: {}".format(device_variable.objects.get_cluster_id()))
        _vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
        for _df in ["database", "software", "models"]:
            print("{} version: {}".format(_df.title(), _vers[_df]))
        print("")
    if not opts.without_fp:
        _valid, _log = hfp_tools.server_dict_is_valid(hfp_tools.get_server_fp())
        if not _valid:
            print(_log)
        else:
            print(_log)
            print("")
            print("Current Server Fingerprint:")
            print("")
            print hfp_tools.get_server_fp(serialize=True)


def main(opts):
    if opts.subcom == "register_cluster":
        register_cluster(opts)
    elif opts.subcom == "install_license_file":
        install_license_file(opts)
    elif opts.subcom == "show_cluster_id":
        show_cluster_id(opts)
    elif opts.subcom == "show_license_info":
        show_license_info(opts)
    else:
        print("unknown subcom '{}'".format(opts.subcom))
