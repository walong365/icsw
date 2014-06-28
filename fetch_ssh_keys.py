#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001-2007,2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" fetches the various ssh-keys from devices and inserts them into the database """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db.models import Q
from initat.cluster.backbone.models import device, device_variable
import argparse
import base64
import ipvx_tools
import logging_tools
import net_tools
    import server_command

# also used in generators.py

SSH_TYPES = [("rsa1", 1024), ("dsa", 1024), ("rsa", 1024), ("ecdsa", 521)]

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--ip", type=str, default="", help="IP-address of device [%(default)s]")
    my_parser.add_argument("--port", type=int, default=2001, help="port to connect to [%(default)s]")
    my_parser.add_argument("--ssh-dir", type=str, default="/etc/ssh", help="directoy to scan [%(default)s]")
    my_parser.add_argument("--key-prefix", type=str, default="ssh_host_", help="key prefix [%(default)s]")
    my_parser.add_argument("--overwrite", default=False, action="store_true", help="overwrite existing keys [%(default)s]")
    opts = my_parser.parse_args()
    try:
        t_ip = ipvx_tools.ipv4(opts.ip)
    except:
        print("cannot parse IP address '{}'".format(opts.ip))
        sys.exit(1)
    devices = device.objects.filter(Q(netdevice__net_ip__ip=t_ip))
    if not len(devices):
        print("no device with IP '{}' found".format(opts.ip))
        sys.exit(2)
    elif len(devices) > 1:
        print("more than 1 device with IP '{}' found: {}".format(opts.ip, ", ".join([unicode(_dev) for _dev in devices])))
        sys.exit(3)
    _dev = devices[0]
    print("contacting '{}' with IP '{}'".format(_dev, opts.ip))
    _conn_str = "tcp://{}:{:d}".format(opts.ip, opts.port)
    _srv_com = server_command.srv_command(command="get_dir_tree", start_dir=opts.ssh_dir)
    _reply = net_tools.zmq_connection("fetch_ssh_keys").add_connection(_conn_str, _srv_com)
    if _reply is None:
        print("got no result")
        sys.exit(4)
    _raw_names = _reply.xpath(".//directory/file/@name")
    _files = [_name.replace(".pub", "_pub") for _name in _raw_names if _name.startswith(opts.key_prefix)]
    if not _files:
        print("no found files starting with {} beneath {}".format(opts.key_prefix, opts.ssh_dir))
        print("{} found: {}".format(logging_tools.get_plural("file", len(_raw_names)), ", ".join(sorted(_raw_names))))
        sys.exit(5)
    keys_found = {}
    fn_dict = {}
    for _key_type, _bit_size in SSH_TYPES:
        if _key_type == "rsa1":
            _key_name = "ssh_host_key"
        else:
            _key_name = "ssh_host_{}_key".format(_key_type)
        fn_dict[_key_type] = _key_name
        fn_dict[_key_name] = _key_type
        if _key_name in _files and "{}_pub".format(_key_name) in _files:
            keys_found[_key_type] = {"pub" : None, "priv" : None}
        else:
            print "ssh key_type {} not found".format(_key_type)
    if not keys_found:
        print("no ssh_keys of any type found")
        sys.exit(6)
    _srv_com = server_command.srv_command(command="get_file_content")
    _bld = _srv_com.builder()
    _files = _bld.files()
    for _key_type in keys_found.iterkeys():
        _key_name = fn_dict[_key_type]
        _files.append(_bld.file(name=os.path.join(opts.ssh_dir, "{}".format(_key_name)), base64="1"))
        _files.append(_bld.file(name=os.path.join(opts.ssh_dir, "{}.pub".format(_key_name))))
    _srv_com["files"] = _files
    _reply = net_tools.zmq_connection("fetch_ssh_keys").add_connection(_conn_str, _srv_com)
    if _reply is None:
        print "got no result"
        sys.exit(7)
    result_dict = {}
    for entry in _reply.xpath(".//ns:files/ns:file[@error='0']"):
        f_name = os.path.basename(entry.get("name"))
        if f_name.endswith(".pub"):
            _kind = "pub"
            f_name = f_name[:-4]
        else:
            _kind = "priv"
        content = base64.b64decode(entry.text) if int(entry.get("base64", "0")) else entry.text
        _key_type = fn_dict[f_name]
        result_dict.setdefault(_key_type, {"priv" : None, "pub" : None})[_kind] = content
    complete_keys = [key for key, value in result_dict.iteritems() if value["priv"] and value["pub"]]
    incomplete_keys = [key for key, value in result_dict.iteritems() if not value["priv"] or not value["pub"]]
    if incomplete_keys:
        print("*** found incomplete keys: {}".format(", ".join(incomplete_keys)))
    if complete_keys:
        print("found {}: {}".format(logging_tools.get_plural("complete key", len(complete_keys)), ", ".join(sorted(complete_keys))))
        for _key_type in complete_keys:
            var_names = {
                "priv" : fn_dict[_key_type].replace("_host_key", "_host_rsa1_key"),
                "pub" : "{}_pub".format(fn_dict[_key_type].replace("_host_key", "_host_rsa1_key")),
            }
            for _kind in ["priv", "pub"]:
                try:
                    cur_var = device_variable.objects.get(Q(device=_dev) & Q(name=var_names[_kind]))
                except device_variable.DoesNotExist:
                    cur_var = device_variable(
                        device=_dev,
                        name=var_names[_kind],
                        var_type="b",
                        description="SSH key {}".format(var_names[_kind]),
                        val_blob=base64.b64encode(result_dict[_key_type][_kind]),
                    )
                    cur_var.save()
                    print "stored new dv for {}".format(var_names[_kind])
                else:
                    if opts.overwrite:
                        cur_var.val_blob = base64.b64encode(result_dict[_key_type][_kind])
                        cur_var.save()
                        print "changed dv for {}".format(var_names[_kind])
                    else:
                        print("dv {} already present".format(var_names[_kind]))

if __name__ == "__main__":
    main()

