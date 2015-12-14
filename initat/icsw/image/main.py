#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to cluster-backbone-tools
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

import os
import sys

from initat.cluster.backbone.models import image
from initat.cluster.frontend.helper_functions import XMLWrapper
from initat.icsw.service import instance
from initat.tools import logging_tools, server_command, net_tools


def query_local_server(inst, cmd):
    _port = inst.get_port_dict("server", ptype="command")
    _result = net_tools.zmq_connection(
        "icsw_image_{:d}".format(os.getpid())
    ).add_connection(
        "tcp://localhost:{:d}".format(_port),
        server_command.srv_command(
            command=cmd
        ),
    )
    if _result is None:
        print("Unable to send '{}' to local cluster-server".format(cmd))
        sys.exit(1)
    _ret, _state = _result.get_log_tuple()
    if _state != logging_tools.LOG_LEVEL_OK:
        print(
            "a problem occured ({}): {}".format(
                logging_tools.get_log_level_str(_state),
                _ret
            )
        )
        sys.exit(_state)
    return _result


def scan_for_images(opt_ns):
    _inst = instance.InstanceXML()
    result = query_local_server(_inst, "get_image_list")
    images = result.xpath(".//ns:image_list/ns:image")
    print("Found {}:".format(logging_tools.get_plural("image", len(images))))
    for _image in images:
        print(
            "    {:<40s}, arch={}, version={}".format(
                _image.text,
                _image.get("arch", "???"),
                _image.get("version", "???"),
            )
        )
    if opt_ns.mode == "take":
        if not opt_ns.image_name:
            print("Need an image name")
            sys.exit(1)
        _xml_wrapper = XMLWrapper()
        image.take_image(_xml_wrapper, result, opt_ns.image_name)
        _xml_wrapper.show()


def list_images(opt_ns):
    images = image.objects.all().order_by("name")
    print("{} defined:".format(logging_tools.get_plural("image", len(images))))
    _list = logging_tools.new_form_list()
    for _image in images:
        _list.append(
            [
                logging_tools.form_entry(unicode(_image), header="info"),
                logging_tools.form_entry(_image.version, header="version"),
                logging_tools.form_entry(_image.release, header="release"),
                logging_tools.form_entry("yes" if _image.build_lock else "--", header="locked"),
            ]
        )
    print unicode(_list)


def main(opt_ns):
    if opt_ns.mode in ["scan", "take"]:
        scan_for_images(opt_ns)
    elif opt_ns.mode in ["list"]:
        list_images(opt_ns)
    elif opt_ns.mode in ["build"]:
        from .build import build_main
        build_main(opt_ns)
