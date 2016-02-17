# Copyright (C) 2001-2008,2010,2012-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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
""" machine vector stuff """

import copy
import json
import os
import re
import shutil
import time

from lxml import etree
from lxml.builder import E

from initat.host_monitoring import hm_classes, limits
from initat.tools import logging_tools, process_tools, server_command, config_store
from ..constants import MACHVECTOR_CS_NAME


class _general(hm_classes.hm_module):
    class Meta:
        priority = 5

    def __init__(self, *args, **kwargs):
        hm_classes.hm_module.__init__(self, *args, **kwargs)

    def init_module(self):
        if hasattr(self.main_proc, "register_vector_receiver"):
            # at first init the machine_vector
            self._init_machine_vector()
            # then start the polling loop, 30 seconds default timeout (defined in main.py) poll time
            _mpc = self.main_proc.CC.CS["hm.machvector.poll.time"]
            self.log("machvector poll_counter is {:d} seconds".format(_mpc))
            self.main_proc.register_timer(self._update_machine_vector, _mpc, instant=True)

    def reload(self):
        self.machine_vector.reload()

    def close_module(self):
        if hasattr(self.main_proc, "register_vector_receiver"):
            if hasattr(self, "machine_vector"):
                self.machine_vector.close()

    def _init_machine_vector(self):
        self.machine_vector = machine_vector(self)

    def init_machine_vector(self, mvect):
        pass

    def _update_machine_vector(self):
        self.machine_vector.update()


class get_mvector_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--raw", dest="raw", action="store_true", default=False)

    def __call__(self, srv_com, cur_ns):
        self.module.machine_vector.store_xml(srv_com)

    def interpret(self, srv_com, cur_ns):
        if cur_ns.arguments:
            re_list = [re.compile(_arg) for _arg in cur_ns.arguments]
        else:
            re_list = []
        cur_vector = srv_com["data:machine_vector"]
        if cur_ns.raw:
            return limits.nag_STATE_OK, etree.tostring(cur_vector)  # @UndefinedVariable
        else:
            vector_keys = sorted(srv_com.xpath(".//ns:mve/@name", start_el=cur_vector, smart_strings=False))
            used_keys = [key for key in vector_keys if any([cur_re.search(key) for cur_re in re_list]) or not re_list]
            ret_array = [
                "Machinevector id {}, {}, {} shown:".format(
                    cur_vector.attrib["version"],
                    logging_tools.get_plural("key", len(vector_keys)),
                    logging_tools.get_plural("key", len(used_keys)),
                )
            ]
            out_list = logging_tools.new_form_list()
            max_num_keys = 0
            _list = []
            for mv_num, mv_key in enumerate(vector_keys):
                if mv_key in used_keys:
                    cur_xml = srv_com.xpath("//ns:mve[@name='{}']".format(mv_key), start_el=cur_vector, smart_strings=False)[0]
                    _mv = hm_classes.mvect_entry(
                        cur_xml.attrib.pop("name"),
                        **cur_xml.attrib
                    )
                    _list.append((mv_num, _mv))
                    max_num_keys = max(max_num_keys, _mv.num_keys)
            for mv_num, entry in _list:
                out_list.append(entry.get_form_entry(mv_num, max_num_keys))
            ret_array.extend(unicode(out_list).split("\n"))
            return limits.nag_STATE_OK, "\n".join(ret_array)


class machine_vector(object):
    def __init__(self, module):
        self.module = module
        # actual dictionary, including full-length dictionary keys
        self.__act_dict = {}
        # actual keys, last keys
        self.__act_keys = set()
        # init external_sources
        # self.__alert_dict, self.__alert_dict_time = ({}, time.time())
        # key is in fact the timestamp
        self.__act_key, self.__changed = (0, True)
        self.__verbosity = module.main_proc.global_config["VERBOSE"]
        # socket dict for mv-sending
        self.__socket_dict = {}
        # read machine vector config
        self.read_config()
        module.main_proc.register_vector_receiver(self._recv_vector)
        # check flags
        for module in module.main_proc.module_list:
            if hasattr(module, "set_machine_vector_flags"):
                if self.__verbosity:
                    self.log("calling set_machine_vector_flags for module '{}'".format(module.name))
                try:
                    module.set_machine_vector_flags(self)
                except:
                    self.log("error: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                    raise
        mv_flags = [key for key in self.cs.keys() if not isinstance(self.cs[key], dict)]
        # show and set vector flags
        self.log("{} defined".format(logging_tools.get_plural("vector flag", mv_flags)))
        for key in sorted(mv_flags):
            self.log(
                "  {:<10s} : {}".format(
                    key,
                    "enabled" if self.cs[key] else "disabled",
                )
            )
        # init MV
        for module in module.main_proc.module_list:
            if hasattr(module, "init_machine_vector") and module.enabled:
                if self.__verbosity:
                    self.log("calling init_machine_vector for module '{}'".format(module.name))
                try:
                    module.init_machine_vector(self)
                except:
                    self.log("error: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                    raise
        self.cs.write()
        self._remove_old_dirs()

    def read_config(self):
        # close sockets
        for _send_id, sock in self.__socket_dict.iteritems():
            self.log("closing socket with id {}".format(_send_id))
            sock.close()
        self.__socket_dict = {}
        _conf_name = "/etc/sysconfig/host-monitoring.d/machvector.xml"
        if config_store.ConfigStore.exists(MACHVECTOR_CS_NAME):
            self.cs = config_store.ConfigStore(MACHVECTOR_CS_NAME, log_com=self.log, prefix="mv")
        else:
            if os.path.isfile(_conf_name):
                # migrate old config
                try:
                    xml_struct = etree.fromstring(file(_conf_name, "r").read())  # @UndefinedVariable
                except:
                    self.log(
                        "cannot read {}: {}".format(
                            _conf_name,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    xml_struct = None
            else:
                xml_struct = None
            _def_config = {
                "target": "localhost",
                "send_every": 30,
                "enabled": True,
                "immediate": False,
                "send_name": "",
                "full_info_every": 10,
                "port": 8002,
                "format": "xml",
            }
            if xml_struct is not None:
                # rewrite current config
                _cs = config_store.ConfigStore(MACHVECTOR_CS_NAME, log_com=self.log, prefix="mv", read=False)
                for mv_idx, mv_target in enumerate(xml_struct.xpath(".//mv_target", smart_strings=False)):
                    _attr = mv_target.attrib
                    self.log("migrating old machvector {:d} ({})".format(mv_idx, str(_attr)))
                    _dict = {
                        "target": _attr.get("target", "localhost"),
                        "send_every": int(_attr.get("send_every", "30")),
                        "enabled": True if _attr.get("enabled", "yes")[0].lower() in ["1", "t", "y"] else False,
                        "immediate": True if _attr.get("immediate", "no")[0].lower() in ["1", "t", "y"] else False,
                        "send_name": _attr.get("send_name", ""),
                        "full_info_every": int(_attr.get("full_info_every", "10")),
                        "port": int(_attr.get("port", "8002")),
                        "format": _attr.get("format", "xml"),
                    }
                    for _key, _value in _def_config.iteritems():
                        if _key not in _dict:
                            _dict[_key] = _value
                    _cs["{:d}".format(mv_idx)] = _dict
                # flags
                for _flag in xml_struct.xpath(".//mv_flags/mv_flag"):
                    _cs[_flag.attrib["name"]] = True if _flag.attrib.get("enabled", "yes")[0].lower() in ["1", "t", "y"] else False
            else:
                # create new dummy config
                _cs = config_store.ConfigStore(MACHVECTOR_CS_NAME, log_com=self.log, prefix="mv", read=False)
                _cs["0"] = _def_config
            self.cs = _cs
            self.cs.write()

        p_pool = self.module.main_proc
        for send_id in self.cs.keys():
            _struct = self.cs[send_id]
            if isinstance(_struct, dict):
                if _struct["enabled"]:
                    _struct["sent"] = 0
                    p_pool.register_timer(
                        self._send_vector,
                        _struct.get("send_every", 30),
                        data=send_id,
                        instant=_struct.get("immediate", False),
                    )
                    # zmq sending, to collectd
                    t_sock = process_tools.get_socket(
                        p_pool.zmq_context,
                        "PUSH",
                        linger=0,
                        sndhwm=16,
                        backlog=4,
                        # to stop 0MQ trashing the target socket
                        reconnect_ivl=1000,
                        reconnect_ivl_max=30000
                    )
                    target_str = "tcp://{}:{:d}".format(
                        _struct.get("target", "127.0.0.1"),
                        _struct.get("port", 8002),
                    )
                    self.log("creating zmq.PUSH socket for {}".format(target_str))
                    try:
                        t_sock.connect(target_str)
                        self.__socket_dict[send_id] = t_sock
                    except:
                        self.log(
                            "error connecting to {}: {}".format(
                                target_str,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    self.cs[send_id] = _struct
        self.cs.write()

    def reload(self):
        self.log("reloading machine vector")
        self.read_config()

    def _remove_old_dirs(self):
        # delete external directories
        old_dir = "/tmp/.machvect_es"
        if os.path.isdir(old_dir):
            try:
                shutil.rmtree(old_dir)
            except:
                self.log(
                    "error removing old external directory {}: {}".format(
                        old_dir,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("removed old external directory {}".format(old_dir))

    def _send_vector(self, *args, **kwargs):
        send_id = args[0]
        _struct = self.cs[send_id]
        _p_until = _struct.get("pause_until", 0)
        cur_time = int(time.time())
        # print "_", _p_until, cur_time
        if _p_until:
            if _p_until > cur_time:
                return
            else:
                self.log("clearing pause_until")
                del _struct["pause_until"]
        cur_id = _struct["sent"]
        full = cur_id % _struct.get("full_info_every", 10) == 0
        cur_id += 1
        _struct["sent"] = cur_id
        try:
            fqdn, _short_name = process_tools.get_fqdn()
        except:
            fqdn = process_tools.get_machine_name()
        send_format = _struct.get("format", "xml")
        if send_format == "xml":
            send_vector = self.build_xml(E, simple=not full)
            send_vector.attrib["name"] = _struct.get("send_name", fqdn) or fqdn
            send_vector.attrib["interval"] = "{:d}".format(_struct.get("send_every"))
            send_vector.attrib["uuid"] = self.module.main_proc.zeromq_id
        else:
            send_vector = self.build_json(simple=not full)
            send_vector[1]["name"] = _struct.get("send_name", fqdn) or fqdn
            send_vector[1]["interval"] = _struct.get("send_every")
            send_vector[1]["uuid"] = self.module.main_proc.zeromq_id
        # send to server
        t_host, t_port = (
            _struct.get("target", "127.0.0.1"),
            _struct.get("port", 8002),
        )
        try:
            if send_format == "xml":
                self.__socket_dict[send_id].send_unicode(unicode(etree.tostring(send_vector)))  # @UndefinedVariable
            else:
                # print json.dumps(send_vector)
                self.__socket_dict[send_id].send_unicode(json.dumps(send_vector))
        except:
            exc_info = process_tools.get_except_info()
            # ignore errors
            self.log(
                "error sending to ({}, {:d}): {}".format(
                    t_host,
                    t_port,
                    exc_info
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if exc_info.count("int_error"):
                raise
            else:
                # problem sending, wait 2 minutes
                _diff_t = 120
                _w_time = cur_time + _diff_t
                self.log(
                    "setting pause_until to {:d} (+{:d} seconds)".format(
                        _w_time,
                        _diff_t
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                _struct["pause_until"] = _w_time
        self.cs[send_id] = _struct

    def close(self):
        for _s_id, t_sock in self.__socket_dict.iteritems():
            t_sock.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.module.main_proc.log("[mvect] {}".format(what), log_level)

    def _recv_vector(self, zmq_sock):
        try:
            rcv_com = server_command.srv_command(source=zmq_sock.recv_unicode())
        except:
            self.log("error interpreting data as srv_command: {}".format(process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            for in_vector in rcv_com.xpath(".//*[@type='vector']", smart_strings=False):
                for values_list in in_vector:
                    for cur_value in values_list:
                        self.set_from_external(hm_classes.mvect_entry(**cur_value.attrib))
            self.check_timeout()
            self.check_changed()

    def set_from_external(self, mvec):
        if mvec.name not in self:
            # register entry
            self.__act_dict[mvec.name] = mvec
            self.__changed = True
        else:
            # only update value
            self[mvec.name].update_from_mvec(mvec)

    def register_entry(self, name, default, info, unit="1", base=1, factor=1, **kwargs):
        # name is the key (first.second.third.fourth)
        # default is a default value
        # info is a description of the entry
        # unit is the (SI ;-))-symbol for the entry
        # base is the divider to derive the k/M/G-Values (1, 1000 or 1024)
        # factor is a number the values have to be multipilicated with in order to lead to a meaningful number (for example memory or df)
        self.__changed = True
        self.__act_dict[name] = hm_classes.mvect_entry(name, default=default, info=info, unit=unit, base=base, factor=factor)

    def get(self, name, default_value=None):
        return self.__act_dict.get(name, default_value)

    def __getitem__(self, key):
        return self.__act_dict[key]

    def has_key(self, key):
        return key in self.__act_dict

    def keys(self):
        return self.__act_dict.keys()

    def __contains__(self, key):
        return key in self.__act_dict

    def unregister_tree(self, key_prefix):
        self.__changed = True
        del_keys = [key for key in self.keys() if key.startswith(key_prefix)]
        for del_key in del_keys:
            del self.__act_dict[del_key]

    def unregister_entry(self, name):
        self.__changed = True
        if name in self.__act_dict:
            # print "Unregister "+name
            del self.__act_dict[name]
        else:
            self.log("Error: entry {} not defined".format(name), logging_tools.LOG_LEVEL_ERROR)

    def __setitem__(self, name, value):
        self.__act_dict[name].update(value)

    def _reg_update(self, log_t, name, value):
        if name in self.__act_dict:
            self.__act_dict[name].update(value)
        else:
            log_t.error("Error: unknown machvector-name '{}'".format(name))

    def _optimize_list(self, in_list):
        new_list = []
        for entry in in_list:
            if new_list and new_list[-1][0] == entry[0]:
                new_list[-1][1].append(entry[1:])
            else:
                if len(entry) > 1:
                    new_list.append([entry[0], [entry[1:]]])
                else:
                    new_list.append([entry[0], []])
        new_list = [
            [
                entry[0], self._optimize_list(entry[1])
            ] if len(entry) > 1 else entry for entry in new_list
        ]
        return new_list

    def _beautify_list(self, in_list):
        return ",".join(
            [
                "{}{}".format(
                    entry[0],
                    ".({})".format(
                        self._beautify_list(entry[1])
                    ) if entry[1] else ""
                ) for entry in in_list
            ]
        )

    def optimize_list(self, in_list):
        in_list = [entry.split(".") for entry in sorted(in_list)]
        return self._beautify_list(self._optimize_list(in_list))

    def check_changed(self):
        if self.__changed:
            # attention ! dict.keys() != copy.deppcopy(dict).keys()
            last_keys = copy.deepcopy(self.__act_keys)
            self.__act_keys = set(self.__act_dict.keys())
            self.__changed = False
            new_key = int(time.time())
            if new_key == self.__act_key:
                new_key += 1
            self.__act_key = new_key
            new_keys = self.__act_keys - last_keys
            lost_keys = last_keys - self.__act_keys
            if new_keys:
                self.log(
                    "{}: {}".format(
                        logging_tools.get_plural("new key", len(new_keys)),
                        self.optimize_list(new_keys),
                    )
                )
            if lost_keys:
                self.log(
                    "{}: {}".format(
                        logging_tools.get_plural("lost key", len(lost_keys)),
                        self.optimize_list(lost_keys),
                    )
                )
            self.log(
                "Machine_vector has changed, setting actual key to {:d} ({:d} keys)".format(
                    self.__act_key,
                    len(self.__act_dict)
                )
            )

    def check_timeout(self):
        cur_time = time.time()
        rem_keys = [key for key, value in self.__act_dict.iteritems() if value.check_timeout(cur_time)]
        if rem_keys:
            self.log(
                "removing {} because of timeout: {}".format(
                    logging_tools.get_plural("key", len(rem_keys)),
                    ", ".join(sorted(rem_keys))
                )
            )
            for rem_key in rem_keys:
                self.unregister_entry(rem_key)
            self.__changed = True

    def store_xml(self, srv_com):
        srv_com["data"] = self.build_xml(srv_com.builder)

    def build_json(self, simple=False):
        mach_vect = [
            "machine_vector",
            {
                "version": self.__act_key,
                "time": int(time.time()),
                "simple": 1 if simple else 0
            }
        ]
        if simple:
            mach_vect.extend([cur_mve.build_simple_json() for cur_mve in self.__act_dict.itervalues()])
        else:
            mach_vect.extend([cur_mve.build_json() for cur_mve in self.__act_dict.itervalues()])
        return mach_vect

    def build_xml(self, builder, simple=False):
        mach_vect = builder(
            "machine_vector",
            version="{:d}".format(self.__act_key),
            time="{:d}".format(int(time.time())),
            simple="1" if simple else "0",
        )
        if simple:
            mach_vect.extend([cur_mve.build_simple_xml(builder) for cur_mve in self.__act_dict.itervalues()])
        else:
            mach_vect.extend([cur_mve.build_xml(builder) for cur_mve in self.__act_dict.itervalues()])
        return mach_vect

    def get_send_mvector(self):
        return (time.time(), self.__act_key, [self.__act_dict[key].value for key in self.__act_keys])
    # def flush_cache(self, name):
    #    self.__dict_list[name] = []

    def get_actual_key(self):
        return self.__act_key

    def get_act_dict(self):
        return self.__act_dict

    def update(self):  # , esd=""):
        self.check_changed()
        # copy ref_dict to act_dict
        [value.update_default() for value in self.__act_dict.itervalues()]
        self.check_timeout()
        # if esd:
        #    self.check_external_sources(log_t, esd)
        # self.check_for_alert_file_change(log_t)
        for module in self.module.main_proc.module_list:
            if hasattr(module, "update_machine_vector"):
                module.update_machine_vector(self)
        self.check_changed()
        # self.check_for_alerts(log_t)


def pretty_print(val, base):
    pf_idx = 0
    if base != 1:
        while val > base * 4:
            pf_idx += 1
            val = float(val) / base
    return val, ["", "k", "M", "G", "T", "E", "P"][pf_idx]


def pretty_print2(value):
    if "u" in value:
        act_v, p_str = pretty_print(value["v"] * value["f"], value["b"])
        unit = value["u"]
    else:
        act_v, p_str = (value["v"], "")
        unit = "???"
    if type(act_v) in [type(0), type(0L)]:
        val = "{:<10d}   ".format(int(act_v))
    else:
        val = "{:13.2f}".format(float(act_v))
    return val, p_str, unit


def build_info_string(ref, info):
    ret_str = info
    refp = ref.split(".")
    for idx in range(len(refp)):
        ret_str = ret_str.replace("${}".format(idx + 1), refp[idx])
    return ret_str
