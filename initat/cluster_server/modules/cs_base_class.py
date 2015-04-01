# Copyright (C) 2007,2012-2014 Andreas Lang-Nevyjel
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

""" base classes for cluster-server modules """

from django.db import connection
from initat.cluster_server.config import global_config
import config_tools
import io_stream_helper
import logging_tools
import pprint  # @UnusedImport
import process_tools
import server_command
import threading_tools
import time


class BackgroundProcess(threading_tools.process_obj):
    class Meta:
        background = False
        show_execution_time = True

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        self.register_func("set_option_dict", self._set_option_dict)
        self.register_func("set_srv_com", self._set_srv_com)
        self.register_func("start_command", self._start_command)
        connection.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _set_option_dict(self, opt_dict, **kwargs):
        self.option_dict = opt_dict

    def _set_srv_com(self, srv_com, **kwargs):
        self.srv_com = server_command.srv_command(source=srv_com)

    def _start_command(self, com_name, **kwargs):
        self.log("starting command '{}'".format(com_name))
        # print [key for key in sys.modules.keys() if key.count("cluster_s")]
        import initat.cluster_server.modules
        ex_code = initat.cluster_server.modules.command_dict[com_name]
        loc_inst = com_instance(ex_code, self.srv_com, self.option_dict, self.Meta, self.zmq_context)
        loc_inst.log = self.log
        loc_inst()
        del loc_inst.log
        ret_state, ret_str = (
            int(loc_inst.srv_com["result"].attrib["state"]),
            loc_inst.srv_com["result"].attrib["reply"],
        )
        self.log("state ({:d}): {}".format(ret_state, ret_str))
        self.send_pool_message("bg_finished", com_name)
        self["exit_requested"] = False

    def loop_post(self):
        self.__log_template.close()


class com_instance(object):
    bg_idx = 0

    def __init__(self, sc_obj, srv_com, option_dict, meta_struct, zmq_context):
        self.sc_obj = sc_obj
        self.srv_com = srv_com
        self.option_dict = option_dict
        self.Meta = meta_struct
        self.zmq_context = zmq_context
        if self.Meta.background:
            self.Meta.cur_running += 1
            com_instance.bg_idx += 1
            self.new_bg_name = "bg_{}_{:d}".format(self.sc_obj.name, com_instance.bg_idx)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.sc_obj.log(u"[ci] {}".format(what), log_level)

    def write_start_log(self):
        if self.Meta.write_log:
            self.log(u"Got command {}, {}: {}".format(
                self.srv_com["command"].text,
                logging_tools.get_plural("config", len(self.Meta.actual_configs)),
                ", ".join(self.Meta.actual_configs) or "none"))

    def write_end_log(self):
        if self.Meta.write_log:
            # FIXME
            pass

    def __call__(self):
        if self.Meta.background:
            if self.Meta.cur_running < self.Meta.max_instances:
                self.Meta.cur_running += 1
                com_instance.bg_idx += 1
                self.sc_obj.main_proc.send_to_process(
                    self.new_bg_name,
                    "set_option_dict",
                    self.option_dict)
                self.sc_obj.main_proc.send_to_process(
                    self.new_bg_name,
                    "set_srv_com",
                    unicode(self.srv_com),
                )
                self.sc_obj.main_proc.send_to_process(
                    self.new_bg_name,
                    "start_command",
                    self.sc_obj.name,
                )
                connection.close()
                self.srv_com.set_result(
                    "sent to background"
                )
            else:
                self.srv_com.set_result(
                    "too many instances running ({:d} of {:d})".format(self.Meta.cur_running, self.Meta.max_instances),
                    server_command.SRV_REPLY_STATE_ERROR
                )
        else:
            db_debug = global_config["DATABASE_DEBUG"]
            if db_debug:
                pre_queries = len(connection.queries)
            self.start_time = time.time()
            try:
                result = self.sc_obj._call(self)
            except:
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    self.log(line, logging_tools.LOG_LEVEL_CRITICAL)
                self.srv_com.set_result(
                    process_tools.get_except_info(exc_info.except_info),
                    server_command.SRV_REPLY_STATE_CRITICAL
                )
                # write to logging-server
                err_h = io_stream_helper.io_stream(
                    "/var/lib/logging-server/py_err_zmq",
                    zmq_context=self.zmq_context)
                err_h.write("\n".join(exc_info.log_lines))
                err_h.close()
            else:
                if result is not None:
                    self.log("command got an (unexpected) result: '{}'".format(str(result)),
                             logging_tools.LOG_LEVEL_ERROR)
            self.end_time = time.time()
            if int(self.srv_com["result"].attrib["state"]):
                self.log(
                    u"result is ({:d}) {}".format(
                        int(self.srv_com["result"].attrib["state"]),
                        self.srv_com["result"].attrib["reply"]
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            if self.Meta.show_execution_time:
                self.log("run took {}".format(logging_tools.get_diff_time_str(self.end_time - self.start_time)))
                self.srv_com["result"].attrib["reply"] = u"{} in {}".format(
                    self.srv_com["result"].attrib["reply"],
                    logging_tools.get_diff_time_str(self.end_time - self.start_time))
            if db_debug:
                self.log("queries executed : {:d}".format(len(connection.queries) - pre_queries))


class server_com(object):
    class Meta:
        # callable via net
        available_via_net = True
        # restartable
        background = False
        # is blocking
        blocking = True
        # needed configurations
        needed_configs = []
        # actual configs
        actual_configs = []
        # needed options keys
        needed_option_keys = []
        # write log entries
        write_log = True
        # show execution time
        show_execution_time = True
        # keys needed in config
        needed_config_keys = []
        # public via network
        public_via_net = True
        # maximum number of instances
        max_instances = 1
        # current number of instances
        cur_running = 0
        # is disbaled
        disabled = False

    def __init__(self):
        # copy Meta keys
        for key in dir(server_com.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(server_com.Meta, key))

    def link(self, main_proc):
        self.main_proc = main_proc

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.main_proc.log(u"[com] {}".format(what), log_level)

    def check_config(self, loc_config, force=False):
        self.server_idx, self.act_config_name = (0, "")
        doit, srv_origin, err_str = (False, "---", "OK")
        if self.Meta.needed_configs:
            for act_c in self.Meta.needed_configs:
                sql_info = config_tools.server_check(server_type="{}".format(act_c))
                if sql_info.effective_device:
                    doit, srv_origin = (True, sql_info.server_origin)
                    if not self.server_idx:
                        self.server_device_name = sql_info.effective_device.name
                        self.server_idx, self.act_config_name = (sql_info.effective_device.pk, sql_info.effective_device.name)
            if doit:
                self.Meta.actual_configs = self.Meta.needed_configs
            else:
                if force:
                    doit = True
                else:
                    err_str = "Server {} has no {} attribute".format(loc_config["SERVER_SHORT_NAME"], " or ".join(self.Meta.needed_configs))
        else:
            doit = True
        if doit and self.Meta.needed_config_keys:
            for key in self.Meta.needed_config_keys:
                if key not in loc_config:
                    self.log("key '{}' not defined in config".format(key), logging_tools.LOG_LEVEL_ERROR)
                    doit = False
        if doit and srv_origin == "---":
            srv_origin = "yes"
        return (doit, srv_origin, err_str)

    def __call__(self, srv_com, option_dict):
        return com_instance(self, srv_com, option_dict, self.Meta, self.main_proc.zmq_context)
