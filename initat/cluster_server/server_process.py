#!/usr/bin/python-init -Ot
#
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
from initat.cluster_server.background import usv_server, quota
from initat.cluster_server.backup_process import backup_process
from initat.cluster_server.config import global_config
import cluster_location
import config_tools
import configfile
import datetime
import initat.cluster_server
import logging_tools
import os
import process_tools
import server_command
import threading_tools
import time
import uuid_tools
import zmq

class server_process(threading_tools.process_pool):
    def __init__(self, options):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__run_command = True if global_config["COMMAND"].strip() else False
        if self.__run_command:
            # rewrite LOG_NAME and PID_NAME
            global_config["PID_NAME"] = "%s-direct-%s-%d" % (
                global_config["PID_NAME"],
                "%04d%02d%02d-%02d:%02d" % tuple(time.localtime()[0:5]),
                os.getpid())
            global_config["LOG_NAME"] = "%s-direct-%s" % (
                global_config["LOG_NAME"],
                global_config["COMMAND"])
        self.__pid_name = global_config["PID_NAME"]
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_func("bg_finished", self._bg_finished)
        self._log_config()
        self._check_uuid()
        self._load_modules()
        self._init_capabilities()
        self.__options = options
        self._set_next_backup_time(True)
        connection.close()
        if self.__run_command:
            self.register_timer(self._run_command, 3600, instant=True)
        else:
            self._init_network_sockets()
            self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _set_next_backup_time(self, first=False):
        self.__next_backup_dt = datetime.datetime.now().replace(microsecond=0)
        if global_config["BACKUP_DATABASE"] and first:
            self.log("initiate immediate backup run")
            self.__next_backup_dt = (self.__next_backup_dt + datetime.timedelta(seconds=2))
        else:
            self.__next_backup_dt = (self.__next_backup_dt + datetime.timedelta(days=0)).replace(hour=2, minute=0, second=0)
        while self.__next_backup_dt < datetime.datetime.now():
            self.__next_backup_dt += datetime.timedelta(days=1)
        self.log("setting %s backup-time to %s" % (
            "first" if first else "next",
            self.__next_backup_dt))
    def _bg_finished(self, *args, **kwargs):
        func_name = args[2]
        self.log("background task for '%s' finished" % (func_name))
        initat.cluster_server.command_dict[func_name].Meta.cur_running -= 1
    def _init_capabilities(self):
        self.log("init server capabilities")
        self.__server_cap_dict = {
            "usv_server" : usv_server.usv_server_stuff(self),
            "quota"      : quota.quota_stuff(self),
            # "dummy"      : dummy_stuff(self),
            }
        self.__cap_list = []
        for key, _value in self.__server_cap_dict.iteritems():
            _sql_info = config_tools.server_check(server_type=key)
            if _sql_info.effective_device:
                self.__cap_list.append(key)
            self.log("capability %s: %s" % (key, "enabled" if key in self.__cap_list else "disabled"))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
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
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3, process_name="main")
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
        self.log(" - cluster_device_uuid is '%s'" % (uuid_tools.get_uuid().get_urn()))
        my_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        file_uuid = uuid_tools.get_uuid().get_urn().split(":")[2]
        if file_uuid != my_dev.uuid:
            self.log("UUID differs from DB entry (%s [file] != %s [DB]), correcting DB entry" % (
                file_uuid,
                my_dev.uuid), logging_tools.LOG_LEVEL_ERROR)
            my_dev.uuid = file_uuid
            my_dev.save()
        # uuid is also stored as device variable
        _uuid_var = cluster_location.db_device_variable(global_config["SERVER_IDX"], "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
        # recognize for which devices i am responsible
        dev_r = cluster_location.device_recognition()
        if dev_r.device_dict:
            self.log(" - i am also host for %s: %s" % (logging_tools.get_plural("virtual device", len(dev_r.device_dict.keys())),
                                                       ", ".join(sorted([cur_dev.name for cur_dev in dev_r.device_dict.itervalues()]))))
            for cur_dev in dev_r.device_dict.itervalues():
                cluster_location.db_device_variable(cur_dev, "device_uuid", description="UUID of device", value=uuid_tools.get_uuid().get_urn())
                cluster_location.db_device_variable(cur_dev, "is_virtual", description="Flag set for Virtual Machines", value=1)
    def loop_end(self):
        if not self.__run_command:
            if self.com_socket:
                self.log("closing socket")
                self.com_socket.close()
            if self.vector_socket:
                self.vector_socket.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.__log_template.close()
    def _init_network_sockets(self):
        self.__connection_dict = {}
        self.__discovery_dict = {}
        self.bind_id = "%s:clusterserver:" % (uuid_tools.get_uuid().get_urn())
        if self.__run_command:
            client = None
        else:
            client = self.zmq_context.socket(zmq.ROUTER)
            client.setsockopt(zmq.IDENTITY, self.bind_id)
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.RCVHWM, 256)
            client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
            client.setsockopt(zmq.RECONNECT_IVL, 200)
            client.setsockopt(zmq.TCP_KEEPALIVE, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            try:
                client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
            except zmq.core.error.ZMQError:
                self.log("error binding to %d: %s" % (
                    global_config["COM_PORT"],
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                self.register_poller(client, zmq.POLLIN, self._recv_command)
        self.com_socket = client
        # connection to local collserver socket
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket
        self.log("connected vector_socket to %s" % (conn_str))
    def _recv_command(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(data) == 2:
            srv_com = server_command.srv_command(source=data[1])
            self._process_command(srv_com)
            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log("data stream has wrong length (%d) != 2" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _client_connect_timeout(self, sock):
        self.log("connect timeout", logging_tools.LOG_LEVEL_ERROR)
        self.set_error("error connect timeout")
        self._int_error("timeout")
        sock.close()
    def _run_command(self):
        self.log("direct command %s" % (global_config["COMMAND"]))
        cur_com = server_command.srv_command(command=global_config["COMMAND"])
        cur_com["command"].attrib["via_comline"] = "1"
        for keyval in self.__options.OPTION_KEYS:
            try:
                key, value = keyval.split(":", 1)
            except:
                self.log("error parsing option_key from '%s': %s" % (
                    keyval,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_com["server_key:%s" % (key)] = value
        self._process_command(cur_com)
        self["return_value"] = int(cur_com["result"].attrib["state"])
        self["exit_requested"] = True
        # show result
        print cur_com["result"].attrib["reply"]
    def _process_command(self, srv_com):
        com_name = srv_com["command"].text
        self.log("executing command %s" % (com_name))
        srv_com["result"] = None
        srv_com["result"].attrib.update({
            "reply" : "no reply set",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
        if com_name in initat.cluster_server.modules.command_dict:
            com_obj = initat.cluster_server.modules.command_dict[com_name]
            # check config status
            do_it, srv_origin, err_str = com_obj.check_config(global_config, global_config["FORCE"])
            self.log("checking the config gave: %s (%s) %s" % (str(do_it),
                                                               srv_origin,
                                                               err_str))
            # print srv_com.pretty_print()
            if do_it:
                try:
                    found_keys = [key for key in com_obj.Meta.needed_option_keys if "server_key:%s" % (key) in srv_com]
                except:
                    srv_com["result"].attrib.update({
                        "reply" : "error parsing options_keys: %s" % (process_tools.get_except_info()),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                        })
                else:
                    if set(found_keys) != set(com_obj.Meta.needed_option_keys):
                        srv_com["result"].attrib.update({
                            "reply" : "error option keys found (%s) != needed (%s)" % (
                                ", ".join(sorted(list(set(found_keys)))) or "none",
                                ", ".join(sorted(list(set(com_obj.Meta.needed_option_keys))))),
                            "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                            })
                    else:
                        # salt com_obj with some settings
                        option_dict = dict([(key, srv_com["*server_key:%s" % (key)]) for key in com_obj.Meta.needed_option_keys])
                        cur_inst = com_obj(srv_com, option_dict)
                        cur_inst.write_start_log()
                        cur_inst()
                        cur_inst.write_end_log()
            else:
                srv_com["result"].attrib.update({
                    "reply" : "error %s" % (err_str),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                    })
        else:
            srv_com["result"].attrib.update({
                "reply" : "command %s not known" % (com_name),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL),
                })
        self.log("result for %s was (%d) %s" % (
            com_name,
            int(srv_com["result"].attrib["state"]),
            srv_com["result"].attrib["reply"]))
    def _update(self):
        cur_time = time.time()
        cur_dt = datetime.datetime.now().replace(microsecond=0)
        if not global_config["DEBUG"]:
            cur_dt = cur_dt.replace(minute=0, second=0)
        if cur_dt == self.__next_backup_dt:
            self._set_next_backup_time()
            self.log("start DB-backup")
            self.add_process(backup_process("backup_process"), start=True)
            self.send_to_process(
                "backup_process",
                "start_backup",
            )
            connection.close()
        drop_com = server_command.srv_command(command="set_vector")
        for cap_name in self.__cap_list:
            self.__server_cap_dict[cap_name](cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))
    def send_broadcast(self, bc_com):
        self.log("init broadcast command '%s'" % (bc_com))
        # FIXME
        return
        dc = self.__db_con.get_connection('SQL_ACCESS')
        dc.execute("SELECT n.netdevice_idx FROM netdevice n WHERE n.device=%d" % (global_config["SERVER_IDX"]))
        my_netdev_idxs = [db_rec["netdevice_idx"] for db_rec in dc.fetchall()]
        if my_netdev_idxs:
            dc.execute("SELECT d.name, i.ip, h.value FROM device d INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN device_group dg INNER JOIN device_type dt INNER JOIN " + \
                       "hopcount h INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_idx=n.device AND i.netdevice=n.netdevice_idx AND dg.device_group_idx=d.device_group AND " + \
                       "dc.new_config=c.new_config_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND c.name='server' AND d.device_type=dt.device_type_idx AND dt.identifier='H' AND " + \
                       "h.s_netdevice=n.netdevice_idx AND (%s) ORDER BY h.value, d.name" % (" OR ".join(["h.d_netdevice=%d" % (db_rec) for db_rec in my_netdev_idxs])))
            serv_ip_dict = dict([(db_rec["name"], db_rec["ip"]) for db_rec in dc.fetchall()])
            to_send_ids = []
            for srv_name, ip_addr in serv_ip_dict.iteritems():
                conn_str = "tcp://%s:%d" % (ip_addr, global_config["COM_PORT"])
                if conn_str not in self.__connection_dict:
                    # discovery
                    discovery_id = "%s_%s_%d" % (process_tools.get_machine_name(),
                                                 ip_addr,
                                                 global_config["COM_PORT"])
                    if discovery_id not in self.__discovery_dict:
                        self.log("init discovery socket for %s (id is %s)" % (conn_str,
                                                                              discovery_id))
                        new_sock = self.zmq_context.socket(zmq.DEALER)
                        new_sock.setsockopt(zmq.IDENTITY, discovery_id)
                        new_sock.setsockopt(zmq.LINGER, 0)
                        self.__discovery_dict[discovery_id] = new_sock
                        new_sock.connect(conn_str)
                        self.register_poller(new_sock, zmq.POLLIN, self._recv_discovery)
                        discovery_cmd = server_command.srv_command(command="get_0mq_id")
                        discovery_cmd["discovery_id"] = discovery_id
                        discovery_cmd["conn_str"] = conn_str
                        discovery_cmd["broadcast_command"] = bc_com
                        new_sock.send_unicode(unicode(discovery_cmd))
                        # set connection_dict entry to None
                        self.__connection_dict[conn_str] = None
                    else:
                        self.log("discovery already in progress for %s" % (conn_str),
                                 logging_tools.LOG_LEVEL_WARN)
                elif self.__connection_dict[conn_str] is None:
                    self.log("0mq discovery still in progress for %s" % (conn_str))
                else:
                    self.log("send to %s (%s)" % (conn_str,
                                                  self.__connection_dict[conn_str]))
                    to_send_ids.append(self.__connection_dict[conn_str])
            if to_send_ids:
                my_uuid = uuid_tools.get_uuid().get_urn()
                self.log("sending to %s: %s" % (logging_tools.get_plural("target", len(to_send_ids)),
                                                ", ".join(to_send_ids)))
                srv_com = server_command.srv_command(command=bc_com)
                srv_com["servers_visited"] = None
                srv_com["command"].attrib["broadcast"] = "1"
                srv_com["src_uuid"] = my_uuid
                srv_com["servers_visited"].append(srv_com.builder("server", my_uuid))
                for send_id in to_send_ids:
                    if send_id == my_uuid:
                        self._process_command(srv_com)
                    else:
                        # FIXME, send_broadcast not fully implemented, need 2nd server to test, AL 20120401
                        self.com_socket.send_unicode(send_id, zmq.SNDMORE)
                        self.com_socket.send_unicode(unicode(srv_com))
                # pprint.pprint(serv_ip_dict)
                # print unicode(srv_com)
        else:
            self.log("no local netdevices found", logging_tools.LOG_LEVEL_ERROR)
        dc.release()
    def _recv_discovery(self, sock):
        result = server_command.srv_command(source=sock.recv_unicode())
        discovery_id = result["discovery_id"].text
        t_0mq_id = result["zmq_id"].text
        conn_str = result["conn_str"].text
        bc_com = result["broadcast_command"].text
        self.log("got 0MQ_id '%s' for discovery_id '%s' (connection string %s, bc_command %s)" % (
            t_0mq_id,
            discovery_id,
            conn_str,
            bc_com))
        self.__connection_dict[conn_str] = t_0mq_id
        self.log("closing discovery socket for %s" % (conn_str))
        self.unregister_poller(self.__discovery_dict[discovery_id], zmq.POLLIN)
        self.__discovery_dict[discovery_id].close()
        del self.__discovery_dict[discovery_id]
        try:
            if self.__connection_dict[conn_str] != uuid_tools.get_uuid().get_urn():
                self.com_socket.connect(conn_str)
            else:
                self.log("no connection to self", logging_tools.LOG_LEVEL_WARN)
        except:
            self.log("error connecting to %s: %s" % (conn_str,
                                                     process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("connected to %s" % (conn_str))
        self.send_broadcast(bc_com)
    def get_client_ret_state(self):
        return self.__client_error, self.__client_ret_str
    def _load_modules(self):
        self.log("init modules from cluster_server")
        if initat.cluster_server.modules.error_log:
            self.log("%s while loading:" % (logging_tools.get_plural("error", len(initat.cluster_server.modules.error_log))),
                     logging_tools.LOG_LEVEL_ERROR)
            for line_num, err_line in enumerate(initat.cluster_server.modules.error_log):
                self.log("%2d : %s" % (line_num + 1,
                                       err_line),
                         logging_tools.LOG_LEVEL_ERROR)
        del_names = []
        for com_name in initat.cluster_server.modules.command_names:
            act_sc = initat.cluster_server.modules.command_dict[com_name]
            if not act_sc.Meta.disabled:
                if hasattr(act_sc, "_call"):
                    act_sc.link(self)
                    self.log(
                        "   com %-30s, %s%s, %s, %s, %s, %s" % (
                            act_sc.name,
                            logging_tools.get_plural("config", len(act_sc.Meta.needed_configs)),
                            " (%s)" % (
                                ", ".join(act_sc.Meta.needed_configs)) if act_sc.Meta.needed_configs else "",
                            "blocking" if act_sc.Meta.blocking else "not blocking",
                            "%s: %s" % (
                                logging_tools.get_plural("option key", len(act_sc.Meta.needed_option_keys)),
                                ", ".join(act_sc.Meta.needed_option_keys)) if act_sc.Meta.needed_option_keys else "no option keys",
                            "%s: %s" % (
                                logging_tools.get_plural("config key", len(act_sc.Meta.needed_config_keys)),
                                ", ".join(act_sc.Meta.needed_config_keys)) if act_sc.Meta.needed_config_keys else "no config keys",
                            "background" if act_sc.Meta.background else "foreground",
                        )
                    )
                else:
                    self.log("command %s has no _call function" % (com_name), logging_tools.LOG_LEVEL_ERROR)
                    del_names.append(com_name)
            else:
                self.log("command %s is disabled" % (com_name))
        for del_name in del_names:
            initat.cluster_server.modules.command_names.remove(del_name)
            del initat.cluster_server.modules.command_dict[del_name]
        self.log("Found %s" % (logging_tools.get_plural("command", len(initat.cluster_server.modules.command_names))))
