# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" base class for host-monitoring modules """

import argparse
import pickle
import marshal
import subprocess
import time

from initat.tools import logging_tools, server_command


def net_to_sys(in_val):
    try:
        result = pickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise
    return result


def sys_to_net(in_val):
    return pickle.dumps(in_val)


class CacheObject(object):
    def __init__(self, key):
        self.key = key
        self.valid_until = None
        # retrieval pending
        self.retrieval_pending = False
        self.clients = []

    def register_retrieval_client(self, client):
        self.clients.append(client)

    def store_object(self, obj, valid_until):
        self.obj = obj
        self.valid_until = valid_until
        self.retrieval_pending = False
        self._resolve_clients()

    def _resolve_clients(self):
        for _c in self.clients:
            _c.resolve_cache(self.obj)
        self.clients = []

    def is_valid(self):
        if self.valid_until:
            return time.time() < self.valid_until
        else:
            return False


class HMCCache(object):
    def __init__(self, timeout):
        self._timeout = timeout
        self._cache = {}

    def store_object(self, key, obj):
        cur_time = time.time()
        self._cache[key].store_object(obj, cur_time + self._timeout)

    def start_retrieval(self, key):
        self._cache[key].retrieval_pending = True

    def load_object(self, key):
        return self._cache[key].obj

    def cache_valid(self, key):
        if key not in self._cache:
            self._cache[key] = CacheObject(key)
        return self._cache[key].is_valid()

    def retrieval_pending(self, key):
        return self._cache[key].retrieval_pending

    def register_retrieval_client(self, key, client):
        return self._cache[key].register_retrieval_client(client)


class HMCCacheMixin(object):
    class Meta:
        cache_timeout = 10

    def _cache_init(self):
        if not hasattr(self, "_HMC"):
            self._HMC = HMCCache(self.Meta.cache_timeout)

    def start_retrieval(self, key):
        # to flag start of external object generation
        self._cache_init()
        self._HMC.start_retrieval(key)

    def store_object(self, key, obj):
        self._cache_init()
        self._HMC.store_object(key, obj)

    def load_object(self, key):
        return self._HMC.load_object(key)

    def cache_valid(self, key):
        self._cache_init()
        # return True if the given key is in the cache and valid
        return self._HMC.cache_valid(key)

    def retrieval_pending(self, key):
        return self._HMC.retrieval_pending(key)

    def register_retrieval_client(self, key, client):
        return self._HMC.register_retrieval_client(key, client)


class subprocess_struct(object):
    __slots__ = [
        "srv_com", "command", "command_line", "com_num", "popen", "srv_process",
        "cb_func", "_init_time", "terminated", "__nfts", "__return_sent", "__finished",
        "multi_command", "run_info", "src_id"
    ]

    class Meta:
        max_usage = 2
        direct = False
        max_runtime = 300
        use_popen = True
        verbose = False
        id_str = "not_set"

    def __init__(self, srv_com, com_line, cb_func=None):
        # copy Meta keys
        for key in dir(subprocess_struct.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(subprocess_struct.Meta, key))
        self.srv_com = srv_com
        self.command = srv_com["command"].text
        self.command_line = com_line
        self.multi_command = isinstance(self.command_line, list)
        self.com_num = 0
        self.popen = None
        self.srv_process = None
        self.cb_func = cb_func
        self._init_time = time.time()
        # if not a popen call
        self.terminated = False
        # flag for not_finished info
        self.__nfts = None
        # return already sent
        self.__return_sent = False
        # finished
        self.__finished = False

    def run(self):
        run_info = {}
        if self.multi_command:
            if self.command_line:
                cur_cl = self.command_line[self.com_num]
                if isinstance(cur_cl, tuple):
                    # in case of tuple
                    run_info["comline"] = cur_cl[0]
                else:
                    run_info["comline"] = cur_cl
                run_info["command"] = cur_cl
                run_info["run"] = self.com_num
                self.com_num += 1
            else:
                run_info["comline"] = None
        else:
            run_info["comline"] = self.command_line
        self.run_info = run_info
        if run_info["comline"]:
            # if comline is None we do nothing, no server_reply is set
            if self.Meta.verbose:
                self.log("popen '{}'".format(run_info["comline"]))
            self.popen = subprocess.Popen(run_info["comline"], shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            self.started()

    def set_send_stuff(self, srv_proc, src_id, zmq_sock):
        self.srv_process = srv_proc
        self.src_id = src_id
        self.zmq_sock = zmq_sock

    def started(self):
        pass

    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None

    def finished(self):
        if self.run_info["comline"] is None:
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        elif not hasattr(self, "popen"):
            # calling finished () after popen has been delete, strange bug
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        else:
            self.run_info["result"] = self.popen.poll()
            if self.Meta.verbose:
                if self.run_info["result"] is None:
                    cur_time = time.time()
                    if not self.__nfts or abs(self.__nfts - cur_time) > 1:
                        self.__nfts = cur_time
                        self.log("not finished")
                else:
                    self.log("finished with {}".format(str(self.run_info["result"])))
            fin = False
            if self.run_info["result"] is not None:
                self.process()
                if self.multi_command:
                    if self.com_num == len(self.command_line):
                        # last command
                        fin = True
                    else:
                        # next command
                        self.run()
                else:
                    fin = True
        self.__finished = fin
        return fin

    def process(self):
        if self.cb_func:
            self.cb_func(self)
        else:
            self.srv_com.set_result("default process() call", server_command.SRV_REPLY_STATE_ERROR)

    def terminate(self):
        # popen may not be set or None
        if getattr(self, "popen", None):
            self.popen.kill()
        if getattr(self, "srv_com", None):
            self.srv_com.set_result(
                "runtime ({}) exceeded".format(logging_tools.get_plural("second", self.Meta.max_runtime)),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def send_return(self):
        if not self.__return_sent:
            self.__return_sent = True
            if self.srv_process:
                self.srv_process._send_return(self.zmq_sock, self.src_id, self.srv_com)
                del self.srv_com
                del self.zmq_sock
                del self.srv_process
        if self.__finished:
            if hasattr(self, "popen") and self.popen:
                del self.popen


class hm_module(object):
    class Meta:
        priority = 0

    def __init__(self, name, mod_obj):
        self.name = name
        self.obj = mod_obj
        self.enabled = True
        self.__commands = {}
        self.base_init()

    def add_command(self, com_name, call_obj):
        if isinstance(call_obj, type):
            if com_name.endswith("_command"):
                com_name = com_name[:-8]
            new_co = call_obj(com_name)
            new_co.module = self
            self.__commands[com_name] = new_co

    @property
    def commands(self):
        return self.__commands

    def register_server(self, main_proc):
        self.main_proc = main_proc
        for _com_name, _com in self.__commands.items():
            _com.flush_log_cache()

    def base_init(self):
        # called directly after init (usefull for collclient)
        pass

    def init_module(self):
        pass

    def close_module(self):
        pass

    def reload(self):
        return "N/A"

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.main_proc.log("[{}] {}".format(self.name, what), log_level)

    def __unicode__(self):
        return "module {}, priority {:d}".format(self.name, self.Meta.priority)


class hm_command(object):
    info_str = ""

    def __init__(self, name, **kwargs):
        super(hm_command, self).__init__()
        self.__log_cache = []
        self.name = name
        # argument parser
        self.parser = argparse.ArgumentParser(
            description="description: {}".format(self.info_str) if self.info_str else "",
            add_help=False,
            prog="collclient.py --host HOST {}".format(self.name),
        )
        parg_flag = kwargs.get("positional_arguments", False)
        # used to pass commandline arguments to the server
        self.partial = kwargs.get("partial", False)
        if parg_flag is not False:
            if parg_flag is True:
                # self.parser.add_argument("arguments", nargs="*", help="additional arguments")
                self.parser.add_argument("arguments", nargs="*", help=kwargs.get("arguments_name", "additional arguments"))
            elif parg_flag == 1:
                # self.parser.add_argument("arguments", nargs="+", help="additional arguments")
                self.parser.add_argument("arguments", nargs="+", help=kwargs.get("arguments_name", "additional arguments"))
            else:
                raise ValueError("positional_argument flag not in [1, True, False]")
        # monkey patch parsers
        self.parser.exit = self._parser_exit
        self.parser.error = self._parser_error

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if hasattr(self, "module"):
            self.module.main_proc.log("[{}] {}".format(self.name, what), log_level)
        else:
            self.__log_cache.append((what, log_level))

    def flush_log_cache(self):
        if self.__log_cache:
            for _what, _level in self.__log_cache:
                self.log(_what, _level)
                self.__log_cache = []

    def _parser_exit(self, status=0, message=None):
        raise ValueError(status, message)

    def _parser_error(self, message):
        raise ValueError(2, message)

    def handle_commandline(self, arg_list):
        # for arguments use "--" to separate them from the commandline arguments
        if self.partial:
            res_ns, unknown = self.parser.parse_known_args(arg_list)
        else:
            res_ns, unknown = self.parser.parse_args(arg_list), []
        if hasattr(res_ns, "arguments"):
            unknown.extend(res_ns.arguments)
        return res_ns, unknown


class mvect_entry(object):
    __slots__ = [
        "name", "default", "info", "unit", "base", "value", "factor", "v_type", "valid_until"
    ]

    def __init__(self, name, **kwargs):
        self.name = name
        # info, description for user
        self.info = kwargs["info"]
        # unit, can be 1, B, ...
        self.unit = kwargs.get("unit", "1")
        # base, 1, 1000 or 1024
        self.base = int(kwargs.get("base", 1))
        # factor to mulitply value with to get real value
        self.factor = int(kwargs.get("factor", 1))
        if "v_type" in kwargs:
            self.factor = int(self.factor)
            self.base = int(self.base)
            # value
            self.v_type = kwargs["v_type"]
            if self.v_type == "i":
                self.value = int(kwargs["value"])
            elif self.v_type == "f":
                self.value = float(kwargs["value"])
            else:
                self.value = kwargs["value"]
            self.default = self.value
        else:
            # default value, to get type
            self.default = kwargs["default"]
            # value
            self.value = kwargs.get("value", self.default)
            self.v_type = {
                type(0): "i",
                type(0): "i",
                type(0.0): "f",
            }.get(type(self.default), "s")
        self.valid_until = kwargs.get("valid_until", None)
        if self.valid_until:
            self.valid_until = int(self.valid_until)

    def update_from_mvec(self, in_mv):
        self.value = in_mv.value
        self.valid_until = in_mv.valid_until

    def update(self, value, **kwargs):
        if value is None:
            # unknown
            self.value = value
        elif isinstance(value, type(self.default)):
            self.value = value
        else:
            try:
                if self.v_type == "i":
                    # is integer
                    self.value = int(value)
                elif self.v_type == "f":
                    self.value = float(value)
                else:
                    self.value = value
            except:
                # cast to None
                self.value = None
        if "valid_until" in kwargs:
            self.valid_until = int(kwargs["valid_until"])

    def update_default(self):
        # init value with default value for entries without valid_until settings
        if not self.valid_until:
            self.value = self.default

    def check_timeout(self, cur_time):
        return True if (self.valid_until and cur_time > self.valid_until) else False

    @property
    def num_keys(self):
        return self.name.count(".") + 1

    def get_form_entry(self, idx, max_num_keys):
        act_line = []
        sub_keys = (self.name.split(".") + [""] * max_num_keys)[0:max_num_keys]
        for key_idx, sub_key in zip(range(max_num_keys), sub_keys):
            act_line.append(logging_tools.form_entry("{}{}".format("" if (key_idx == 0 or sub_key == "") else ".", sub_key), header="key{:d}".format(key_idx)))
        # check for unknow
        if self.value is None:
            # unknown value
            act_pf, val_str = ("", "<unknown>")
        else:
            act_pf, val_str = self._get_val_str(self.value * self.factor)
        act_line.extend(
            [
                logging_tools.form_entry_right(val_str, header="value"),
                logging_tools.form_entry_right(act_pf, header=" "),
                logging_tools.form_entry(self.unit, header="unit"),
                logging_tools.form_entry("({:3d})".format(idx), header="idx"),
                logging_tools.form_entry("{:d}".format(self.valid_until) if self.valid_until else "---", header="valid_until"),
                logging_tools.form_entry(self._build_info_string(), header="info")
            ]
        )
        return act_line

    def _get_val_str(self, val):
        act_pf = ""
        pf_list = ["k", "M", "G", "T", "E", "P"]
        _div = False
        if self.base != 1:
            while val > self.base * 4:
                _div = True
                if not pf_list:
                    # infinity
                    act_pf = "I"
                    break
                act_pf = pf_list.pop(0)
                val = float(val) / self.base
        if self.v_type == "f" or _div:
            val_str = "{:>14.3f}".format(val)
        elif self.v_type == "i":
            val_str = "{:>10d}    ".format(int(val))
        else:
            val_str = "{:<14s}".format(str(val))
        return act_pf, val_str

    def _build_info_string(self):
        ret_str = self.info
        ref_p = self.name.split(".")
        for idx in range(len(ref_p)):
            ret_str = ret_str.replace("${:d}".format(idx + 1), ref_p[idx])
        return ret_str

    def build_simple_xml(self, builder):
        return builder("m", n=self.name, v=str(self.value))

    def build_simple_json(self):
        return (self.name, str(self.value))

    def build_xml(self, builder):
        kwargs = {
            "name": self.name,
            "info": self.info,
            "unit": self.unit,
            "v_type": self.v_type,
            "value": str(self.value)
        }
        for key, ns_value in [
            ("valid_until", None),
            ("base", 1),
            ("factor", 1)
        ]:
            if getattr(self, key) != ns_value:
                kwargs[key] = "{:d}".format(int(getattr(self, key)))
        return builder("mve", **kwargs)

    def build_json(self):
        return {
            "name": self.name,
            "info": self.info,
            "unit": self.unit,
            "v_type": self.v_type,
            "value": str(self.value),
            "base": self.base,
            "factor": self.factor,
        }
