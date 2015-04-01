# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel
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
""" cluster-server, server process """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.cluster_server.capabilities import capability_process
from initat.cluster_server.backup_process import backup_process
from initat.cluster_server.config import global_config
from initat.cluster_server.notify import notify_mixin
import cluster_location
import configfile
import datetime
import initat.cluster_server.modules
from initat.cluster_server.modules.cs_base_class import BackgroundProcess
import logging_tools
import os
import process_tools
import server_command
import server_mixins
import threading_tools
import time
import uuid_tools
import zmq


class server_process(threading_tools.process_pool, notify_mixin, server_mixins.network_bind_mixin):
    def __init__(self, options):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__run_command = True if global_config["COMMAND"].strip() else False
        # close DB conncetion (daemonize)
        if self.__run_command:
            # rewrite LOG_NAME and PID_NAME
            global_config["PID_NAME"] = "{}-direct-{}-{:d}".format(
                global_config["PID_NAME"],
                "%04d%02d%02d-%02d:%02d" % tuple(time.localtime()[0:5]),
                os.getpid())
            global_config["LOG_NAME"] = "{}-direct-{}".format(
                global_config["LOG_NAME"],
                global_config["COMMAND"])
        self.__pid_name = global_config["PID_NAME"]
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        connection.close()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("bg_finished", self._bg_finished)
        self._log_config()
        self._check_uuid()
        self._load_modules()
        self.__options = options
        self._set_next_backup_time(True)
        if self.__run_command:
            self.register_timer(self._run_command, 3600, instant=True)
        else:
            self._init_network_sockets()
            if not self["exit_requested"]:
                self.init_notify_framework(global_config)
                self.add_process(capability_process("capability_process"), start=True)
                connection.close()
                self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    @property
    def log_template(self):
        return self.__log_template

    def _set_next_backup_time(self, first=False):
        self.__next_backup_dt = datetime.datetime.now().replace(microsecond=0)
        if global_config["BACKUP_DATABASE"] and first:
            self.log("initiate immediate backup run")
            self.__next_backup_dt = None
        else:
            self.__next_backup_dt = (self.__next_backup_dt + datetime.timedelta(days=0)).replace(hour=2, minute=0, second=0)
        if self.__next_backup_dt:
            while self.__next_backup_dt < datetime.datetime.now():
                self.__next_backup_dt += datetime.timedelta(days=1)
        self.log("setting {} backup-time to {}".format(
            "first" if first else "next",
            self.__next_backup_dt if self.__next_backup_dt else "now"))

    def _bg_finished(self, *args, **kwargs):
        func_name = args[2]
        self.log("background task for '{}' finished".format(func_name))
        initat.cluster_server.modules.command_dict[func_name].Meta.cur_running -= 1

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(u" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _re_insert_config(self):
        if self.__run_command:
            self.log("running command, skipping re-insert of config", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("re-insert config")
            cluster_location.write_config("server", global_config)

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=1)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.add_actual_pid(configfile.get_manager_pid(), mult=1, process_name="manager")
            self.__msi_block.save_block()

    def process_exit(self, src_process, src_pid):
        process_tools.remove_pids(self.__pid_name, src_pid)
        process_tools.remove_pids(self.__pid_name, configfile.get_manager_pid(), mult=1)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(src_pid)
            self.__msi_block.remove_actual_pid(configfile.get_manager_pid(), mult=1)
            self.__msi_block.save_block()
        if src_process == "backup_process" and global_config["BACKUP_DATABASE"]:
            self.log("backup process finished, exiting")
            self["exit_requested"] = True

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        if not global_config["COMMAND"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info(self.__pid_name)
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
            msi_block.start_command = "/etc/init.d/cluster-server start"
            msi_block.stop_command = "/etc/init.d/cluster-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def _check_uuid(self):
        self.log("uuid checking")
        self.log(" - cluster_device_uuid is '{}'".format(uuid_tools.get_uuid().get_urn()))
        my_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        file_uuid = uuid_tools.get_uuid().get_urn().split(":")[2]
        if file_uuid != my_dev.uuid:
            self.log(
                "UUID differs from DB entry ({} [file] != {} [DB]), correcting DB entry".format(
                    file_uuid,
                    my_dev.uuid
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            my_dev.uuid = file_uuid
            my_dev.save()
        # uuid is also stored as device variable
        _uuid_var = cluster_location.db_device_variable(
            global_config["SERVER_IDX"],
            "device_uuid",
            description="UUID of device",
            value=uuid_tools.get_uuid().get_urn()
        )
        # recognize for which devices i am responsible
        dev_r = cluster_location.device_recognition()
        self.device_r = dev_r
        if dev_r.device_dict:
            self.log(
                " - i am also host for {}: {}".format(
                    logging_tools.get_plural("virtual device", len(dev_r.device_dict.keys())),
                    ", ".join(sorted([cur_dev.name for cur_dev in dev_r.device_dict.itervalues()]))
                )
            )
            for cur_dev in dev_r.device_dict.itervalues():
                cluster_location.db_device_variable(cur_dev, "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
                cluster_location.db_device_variable(cur_dev, "is_virtual", description="Flag set for Virtual Machines", value=1)

    def loop_end(self):
        if not self.__run_command:
            self.network_unbind()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.__log_template.close()

    def _init_network_sockets(self):
        self.__connection_dict = {}
        self.__discovery_dict = {}
        # connections to other servers
        self.__other_server_dict = {}
        self.bind_id = get_server_uuid("server")
        self.virtual_sockets = []
        if self.__run_command:
            self.main_socket = None
        else:
            try:
                self.network_bind(
                    server_type="server",
                    bind_port=global_config["COM_PORT"],
                    need_all_binds=global_config["NEED_ALL_NETWORK_BINDS"],
                    pollin=self._recv_command,
                    bind_to_localhost=True,
                )
            except:
                self.log("error while bind: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                self["exit_requested"] = True

    def _recv_command(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        if len(data) == 2:
            srv_com = server_command.srv_command(source=data[1])
            if self._process_command(srv_com):
                zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log(
                "data stream has wrong length ({}) != 2".format(len(data)),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _client_connect_timeout(self, sock):
        self.log("connect timeout", logging_tools.LOG_LEVEL_ERROR)
        self.set_error("error connect timeout")
        self._int_error("timeout")
        sock.close()

    def _run_command(self):
        self.log("direct command {}".format(global_config["COMMAND"]))
        cur_com = server_command.srv_command(command=global_config["COMMAND"])
        cur_com["command"].attrib["via_comline"] = "1"
        for keyval in self.__options.OPTION_KEYS:
            try:
                key, value = keyval.split(":", 1)
            except:
                self.log(
                    "error parsing option_key from '{}': {}".format(
                        keyval,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                cur_com["server_key:{}".format(key)] = value
        self._process_command(cur_com)
        self["return_value"] = int(cur_com["result"].attrib["state"])
        self["exit_requested"] = True
        # show result
        print cur_com["result"].attrib["reply"]
        if global_config["SHOW_RESULT"]:
            print cur_com.pretty_print()

    def _execute_command(self, srv_com):
        com_name = srv_com["command"].text
        # set executed flag to distinguish between calls to virtual server and result calls
        srv_com["executed"] = "1"
        if com_name in initat.cluster_server.modules.command_dict:
            srv_com.set_result(
                "no reply set",
                server_command.SRV_REPLY_STATE_CRITICAL,
            )
            com_obj = initat.cluster_server.modules.command_dict[com_name]
            # check config status
            do_it, srv_origin, err_str = com_obj.check_config(global_config, global_config["FORCE"])
            self.log(
                "checking the config gave: {} ({}) {}".format(
                    str(do_it),
                    srv_origin,
                    err_str
                )
            )
            # print srv_com.pretty_print()
            if do_it:
                try:
                    found_keys = [key for key in com_obj.Meta.needed_option_keys if "server_key:{}".format(key) in srv_com]
                except:
                    srv_com.set_result(
                        "error parsing options_keys: {}".format(process_tools.get_except_info()),
                        server_command.SRV_REPLY_STATE_CRITICAL
                    )
                else:
                    if set(found_keys) != set(com_obj.Meta.needed_option_keys):
                        srv_com.set_result(
                            "error option keys found ({}) != needed ({})".format(
                                ", ".join(sorted(list(set(found_keys)))) or "none",
                                ", ".join(sorted(list(set(com_obj.Meta.needed_option_keys))))
                            ),
                            server_command.SRV_REPLY_STATE_CRITICAL
                        )
                    else:
                        # salt com_obj with some settings
                        option_dict = dict([(key, srv_com["*server_key:{}".format(key)]) for key in com_obj.Meta.needed_option_keys])
                        cur_inst = com_obj(srv_com, option_dict)
                        cur_inst.write_start_log()
                        cur_inst()
                        cur_inst.write_end_log()
            else:
                srv_com.set_result(
                    err_str,
                    server_command.SRV_REPLY_STATE_CRITICAL
                )
            self.log(u"result for {} was ({:d}) {}".format(
                com_name,
                int(srv_com["result"].attrib["state"]),
                srv_com["result"].attrib["reply"]))
        else:
            self.log("unknown command {}".format(com_name))
            # to avoid flooding of log
            time.sleep(1)
            srv_com.set_result(
                "command {} not known".format(com_name),
                server_command.SRV_REPLY_STATE_CRITICAL
            )

    def _process_command(self, srv_com):
        _send_return = True
        com_name = srv_com["command"].text
        self.log("executing command {}".format(com_name))
        if self.notify_waiting_for_job(srv_com):
            self.notify_handle_result(srv_com)
            _send_return = False
        else:
            if com_name in ["wf_notify"]:
                self.check_notify()
                _send_return = False
            else:
                self._execute_command(srv_com)
        return _send_return

    def _update(self):
        cur_dt = datetime.datetime.now().replace(microsecond=0)
        if not global_config["DEBUG"]:
            cur_dt = cur_dt.replace(minute=0, second=0)
        if cur_dt == self.__next_backup_dt or self.__next_backup_dt is None:
            self._set_next_backup_time()
            self.log("start DB-backup")
            self.add_process(backup_process("backup_process"), start=True)
            self.send_to_process(
                "backup_process",
                "start_backup",
            )
            connection.close()

    def send_to_server(self, conn_str, srv_uuid, srv_com, **kwargs):
        _success = True
        local = kwargs.get("local", False)
        if local:
            self._execute_command(srv_com)
            self.notify_handle_result(srv_com)
        else:
            if conn_str not in self.__other_server_dict:
                self.log("connecting to {} (uuid {})".format(conn_str, srv_uuid))
                self.__other_server_dict = srv_uuid
                self.main_socket.connect(conn_str)
            try:
                self.main_socket.send_unicode(srv_uuid, zmq.SNDMORE)  # @UndefinedVariable
                self.main_socket.send_unicode(unicode(srv_com))
            except:
                self.log("cannot send to {}: {}".format(conn_str, process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                _success = False
        return _success

    def _recv_discovery(self, sock):
        result = server_command.srv_command(source=sock.recv_unicode())
        discovery_id = result["discovery_id"].text
        t_0mq_id = result["zmq_id"].text
        conn_str = result["conn_str"].text
        bc_com = result["broadcast_command"].text
        self.log(
            "got 0MQ_id '{}' for discovery_id '{}'.format(connection string {}, bc_command {})".format(
                t_0mq_id,
                discovery_id,
                conn_str,
                bc_com
            )
        )
        self.__connection_dict[conn_str] = t_0mq_id
        self.log("closing discovery socket for {}".format(conn_str))
        self.unregister_poller(self.__discovery_dict[discovery_id], zmq.POLLIN)  # @UndefinedVariable
        self.__discovery_dict[discovery_id].close()
        del self.__discovery_dict[discovery_id]
        try:
            if self.__connection_dict[conn_str] != uuid_tools.get_uuid().get_urn():
                self.main_socket.connect(conn_str)
            else:
                self.log(
                    "no connection to self",
                    logging_tools.LOG_LEVEL_WARN
                )
        except:
            self.log(
                "error connecting to {}: {}".format(
                    conn_str,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log("connected to {}".format(conn_str))

    def get_client_ret_state(self):
        return self.__client_error, self.__client_ret_str

    def _load_modules(self):
        self.log("init modules from cluster_server")
        if initat.cluster_server.modules.error_log:
            self.log(
                "{} while loading:".format(
                    logging_tools.get_plural("error", len(initat.cluster_server.modules.error_log))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            for line_num, err_line in enumerate(initat.cluster_server.modules.error_log):
                self.log(
                    "{:2d} : {}".format(
                        line_num + 1,
                        err_line),
                    logging_tools.LOG_LEVEL_ERROR)
        del_names = []
        for com_name in initat.cluster_server.modules.command_names:
            act_sc = initat.cluster_server.modules.command_dict[com_name]
            if not act_sc.Meta.disabled:
                if hasattr(act_sc, "_call"):
                    act_sc.link(self)
                    self.log(
                        "   com {:<30s}, {}{}, {}, {}, {}, {}".format(
                            act_sc.name,
                            logging_tools.get_plural("config", len(act_sc.Meta.needed_configs)),
                            " ({})".format(
                                ", ".join(act_sc.Meta.needed_configs)) if act_sc.Meta.needed_configs else "",
                            "blocking" if act_sc.Meta.blocking else "not blocking",
                            "{}: {}".format(
                                logging_tools.get_plural("option key", len(act_sc.Meta.needed_option_keys)),
                                ", ".join(act_sc.Meta.needed_option_keys)) if act_sc.Meta.needed_option_keys else "no option keys",
                            "{}: {}".format(
                                logging_tools.get_plural("config key", len(act_sc.Meta.needed_config_keys)),
                                ", ".join(act_sc.Meta.needed_config_keys)) if act_sc.Meta.needed_config_keys else "no config keys",
                            "background" if act_sc.Meta.background else "foreground",
                        )
                    )
                else:
                    self.log("command {} has no _call function".format(com_name), logging_tools.LOG_LEVEL_ERROR)
                    del_names.append(com_name)
            else:
                self.log("command {} is disabled".format(com_name))
        for del_name in del_names:
            initat.cluster_server.modules.command_names.remove(del_name)
            del initat.cluster_server.modules.command_dict[del_name]
        self.log("Found {}".format(logging_tools.get_plural("command", len(initat.cluster_server.modules.command_names))))
