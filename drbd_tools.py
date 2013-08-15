#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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
""" module to parse the drbd status """

import os
import server_command
import stat
import sys

class drbd_config(object):
    def __init__(self, config_name="/etc/drbd.conf", status_name="/proc/drbd", **args):
        self.__config_name = config_name
        self.__status_name = status_name
        if args.has_key("data"):
            self.__config_dict = server_command.net_to_sys(args["data"])
        else:
            self._init()
            self._parse_all()
    def _parse_all(self):
        if os.path.isfile(self.__config_name):
            self.__config_dict["config_present"] = True
            mod_time = os.stat(self.__config_name)[stat.ST_MTIME]
            if mod_time != self.__config_dict["last_check"]:
                self.__config_dict["last_check"] = mod_time
                self._parse_config()
        else:
            self.__config_dict["config_present"] = False
        self._parse_status()
    def _init(self):
        # config dict with empty timestamp
        self.__config_dict = {"last_check"     : 0,
                              "config_present" : False,
                              "status_present" : False}
    def __nonzero__(self):
        return True if self.__config_dict["last_check"] else False
    def _parse_config(self):
        # config dict
        c_dict = self.__config_dict
        # clear config_dict
        c_dict["resources"] = {}
        c_dict["devices"] = {}
        stream = (" ".join([line.strip() for line in file(self.__config_name, "r").read().split("\n") if not line.lstrip().startswith("#")])).strip()
        if stream.count("{") != stream.count("}"):
            raise SyntaxError, "cannot parse stream from %s" % (self.__config_name)
        # add depth info
        c_list, act_depth, sub_stream = ([], 0, "")
        for char in stream:
            if char in ["{", "}"]:
                sub_stream = sub_stream.strip()
                if sub_stream:
                    last_is_config = sub_stream.endswith(";")
                    stream_parts = self._split_enhanced(sub_stream, ";")
                    for stream_part in stream_parts[:-1]:
                        c_list.append((act_depth, stream_part.strip(), True))
                    if not last_is_config:
                        c_list.append((act_depth, stream_parts[-1].strip(), False))
                    sub_stream = ""
                if char == "{":
                    act_depth += 1
                elif char == "}":
                    act_depth -= 1
            else:
                sub_stream = "%s%s" % (sub_stream, char)
        conf_way = []
        for act_depth, act_stream, config_line in c_list:
            conf_way = conf_way[:act_depth]
            if act_depth == 0:
                c_dict[act_stream] = {}
                conf_way = [act_stream]
            else:
                sub_conf = c_dict
                for conf_key in conf_way:
                    sub_conf = sub_conf[conf_key]
                if config_line:
                    if act_stream.count(" "):
                        config_key, config_value = act_stream.split(None, 1)
                    else:
                        config_key, config_value = (act_stream, True)
                    sub_conf[config_key] = config_value
                else:
                    sub_conf[act_stream] = {}
                conf_way.append(act_stream)
        # local hostname
        hostname = os.uname()[1]
        # reorder resources
        res_keys = [key for key in c_dict.iterkeys() if key.startswith("resource ")]
        for key in res_keys:
            res_name = key.split(None, 1)[1]
            c_dict[key]["hosts"] = {}
            host_keys = [sub_key for sub_key in c_dict[key].keys() if sub_key.startswith("on ")]
            for host_key in host_keys:
                c_dict[key]["hosts"][host_key.split()[1]] = c_dict[key][host_key]
                del c_dict[key][host_key]
            c_dict[key]["localhost"] = c_dict[key]["hosts"][hostname]
            c_dict["devices"][c_dict[key]["localhost"]["device"]] = res_name
            c_dict["resources"][res_name] = c_dict[key]
            del c_dict[key]
    def _parse_status(self):
        if os.path.isfile(self.__status_name):
            self.__config_dict["status_present"] = True
            stat_lines = [line.strip().split() for line in file(self.__status_name, "r").read().split("\n") if line.strip()]
            act_device = None
            for line in stat_lines:
                if line[0].endswith(":") and line[0][:-1].isdigit():
                    act_device = self.__config_dict["resources"][self.__config_dict["devices"]["/dev/drbd%d" % (int(line[0][:-1]))]]["localhost"]
                    # copy line info to dict
                    act_device["connection_state"] = line[1].split(":")[1].lower()
                    if act_device["connection_state"] == "unconfigured":
                        pass
                    else:
                        act_device["state"] = tuple(line[2].split(":")[1].lower().split("/"))
                        act_device["data_state"] = tuple(line[3].split(":")[1].lower().split("/"))
                        if len(line) == 5:
                            # protocol not set
                            act_device["protocol"] = " "
                        else:
                            act_device["protocol"] = line[4]
                        act_device["flags"] = line[-1]
                elif act_device:
                    if line[0].startswith("finish"):
                        line = None
                        # resync info
                    elif line[0].startswith("["):
                        act_device["resync_percentage"] = line[2][:-1]
                        line = None
                    elif line[0].endswith(":"):
                        pre_key = "%s." % (line.pop(0)[:-1])
                    else:
                        pre_key = ""
                    if line:
                        for sub_key, value in [part.split(":") for part in line]:
                            if value.count("/"):
                                act_device["%s%s" % (pre_key, sub_key)] = tuple([int(sub_value) for sub_value in value.split("/")])
                            else:
                                act_device["%s%s" % (pre_key, sub_key)] = int(value) if value.isdigit() else value
                    # pprint.pprint(act_device)
        else:
            self.__config_dict["status_present"] = True
    def _split_enhanced(self, in_str, split_char, escape_chars=['"']):
        parts, act_stream, escaped = ([], "", False)
        for char in in_str:
            if char == split_char and not escaped:
                parts.append(act_stream)
                act_stream = ""
            elif char in escape_chars:
                act_stream = "%s%s" % (act_stream, char)
                escaped = not escaped
            else:
                act_stream = "%s%s" % (act_stream, char)
        parts.append(act_stream)
        return parts
    def __getitem__(self, key):
        return self.__config_dict[key]
    def get_config_dict(self):
        return self.__config_dict
    def get_net_data(self):
        return server_command.sys_to_net(self.__config_dict)

def _test_code():
    dc = drbd_config()
    print len(dc.get_net_data())
    # if dc:
    #    pprint.pprint(dc["devices"])
    #    pprint.pprint(dc["resources"])

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _test_code()
    sys.exit(1)
