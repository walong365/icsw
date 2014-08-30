#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
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
""" cluster-config-server, server part """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.cluster_config_server.build_process import build_process
from initat.cluster_config_server.config import global_config
from initat.cluster_config_server.config_control import config_control
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import cluster_location
import configfile
import logging_tools
import process_tools
import server_command
import threading_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._re_insert_config()
        self._log_config()
        self.__msi_block = self._init_msi_block()
        self._init_subsys()
        self._init_network_sockets()
        self.add_process(build_process("build"), start=True)
        connection.close()
        self.register_func("client_update", self._client_update)
        self.register_func("complex_result", self._complex_result)
        self.__run_idx = 0
        self.__pending_commands = {}

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _init_subsys(self):
        self.log("init subsystems")
        config_control.init(self)

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _re_insert_config(self):
        cluster_location.write_config("config_server", global_config)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("cluster-config-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/cluster-config-server start"
            msi_block.stop_command = "/etc/init.d/cluster-config-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def loop_end(self):
        config_control.close_clients()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()

    def _init_network_sockets(self):
        my_0mq_id = get_server_uuid("config")
        self.bind_id = my_0mq_id
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PORT"] , self._new_com),
        ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, my_0mq_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.RCVHWM, 256)
            client.setsockopt(zmq.SNDHWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
            client.setsockopt(zmq.RECONNECT_IVL, 200)
            client.setsockopt(zmq.TCP_KEEPALIVE, 1)
            client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.ZMQError:
                self.log(
                    "error binding to {}{{{:d}}}: {}".format(
                        conn_str,
                        sock_type,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                client.close()
            else:
                self.log(
                    "bind to port {}{{{:d}}}".format(
                        conn_str,
                        sock_type
                    )
                )
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client

    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            try:
                cur_com = srv_com["command"].text
            except:
                if srv_com.tree.find("nodeinfo") is not None:
                    node_text = srv_com.tree.findtext("nodeinfo")
                    src_id = data[0].split(":")[0]
                    if not config_control.has_client(src_id):
                        try:
                            new_dev = device.objects.get(Q(uuid=src_id) | Q(uuid__startswith=src_id[:-5]))
                        except device.DoesNotExist:
                            self.log("no device with UUID %s found in database" % (src_id),
                                     logging_tools.LOG_LEVEL_ERROR)
                            cur_c = None
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
                            zmq_sock.send_unicode("error unknown UUID")
                        else:
                            cur_c = config_control.add_client(new_dev)
                    else:
                        cur_c = config_control.get_client(src_id)
                    if cur_c is not None:
                        cur_c.handle_nodeinfo(data[0], node_text)
                else:
                    self.log(
                        "got command '{}' from {}, ignoring".format(etree.tostring(srv_com.tree), data[0]),
                        logging_tools.LOG_LEVEL_ERROR)
            else:
                srv_com.update_source()
                if cur_com == "register":
                    self._register_client(c_uid, srv_com)
                elif cur_com == "get_0mq_id":
                    srv_com["result"] = None
                    srv_com["zmq_id"] = self.bind_id
                    srv_com["result"].attrib.update({
                        "reply" : "0MQ_ID is %s" % (self.bind_id),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                    self._send_simple_return(c_uid, unicode(srv_com))
                elif cur_com == "status":
                    srv_com["result"] = None
                    srv_com["result"].attrib.update({
                        "reply" : "up and running",
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                    self._send_simple_return(c_uid, unicode(srv_com))
                else:
                    if c_uid.endswith("webfrontend"):
                        # special command from webfrontend, FIXME
                        srv_com["command"].attrib["source"] = "external"
                        self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                    else:
                        try:
                            cur_client = None  # client.get(c_uid)
                        except KeyError:
                            self.log("unknown uid %s, not known" % (c_uid),
                                     logging_tools.LOG_LEVEL_CRITICAL)
                        else:
                            if cur_client is None:
                                self.log("cur_client is None (command: %s)" % (cur_com), logging_tools.LOG_LEVEL_WARN)
                            else:
                                cur_client.new_command(srv_com)
        else:
            self.log("wrong number of data chunks (%d != 2), data is '%s'" % (len(data), data[:20]),
                     logging_tools.LOG_LEVEL_ERROR)

    def _handle_wfe_command(self, zmq_sock, c_uid, srv_com):
        cur_com = srv_com["command"].text
        self.__run_idx += 1
        srv_com["command"].attrib["run_idx"] = "%d" % (self.__run_idx)
        srv_com["command"].attrib["uuid"] = c_uid
        self.__pending_commands[self.__run_idx] = srv_com
        # get device names
        device_list = device.objects.select_related("domain_tree_node").filter(Q(pk__in=[cur_dev.attrib["pk"] for cur_dev in srv_com["devices:devices"]]))
        self.log("got command %s for %s: %s" % (
            cur_com,
            logging_tools.get_plural("device", len(device_list)),
            ", ".join([unicode(cur_dev) for cur_dev in device_list])))
        dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device_list])
        # set device state
        for cur_dev in srv_com["devices:devices"]:
            cur_dev.attrib["command"] = cur_com
            cur_dev.attrib["internal_state"] = "pre_init"
            cur_dev.attrib["run_idx"] = "%d" % (self.__run_idx)
            cur_dev.text = unicode(dev_dict[int(cur_dev.attrib["pk"])])
            cur_dev.attrib["short_name"] = dev_dict[int(cur_dev.attrib["pk"])].name
            cur_dev.attrib["name"] = dev_dict[int(cur_dev.attrib["pk"])].full_name
        self._handle_command(self.__run_idx)

    def create_config(self, queue_id, s_req):
        # create a build_config request
        cur_com = server_command.srv_command(command="build_config")
        cur_com["devices"] = cur_com.builder(
            "devices",
            cur_com.builder("device", pk="%d" % (s_req.cc.device.pk))
        )
        cur_com["command"].attrib["source"] = "config_control"
        self._handle_wfe_command(None, str(queue_id), cur_com)

    def _handle_command(self, run_idx):
        cur_com = self.__pending_commands[run_idx]
        for cur_dev in cur_com["devices:devices"]:
            if cur_dev.attrib["internal_state"] == "pre_init":
                cur_dev.attrib["internal_state"] = "generate_config"
                self.send_to_process(
                    "build",
                    cur_dev.attrib["internal_state"],
                    dict(cur_dev.attrib),
                    )
        num_pending = len(cur_com.xpath(".//ns:device[not(@internal_state='done')]", smart_strings=False))
        if not num_pending:
            self.log("nothing pending, sending return")
            self._send_return(cur_com)
            del self.__pending_commands[run_idx]

    def _send_return(self, cur_com):
        if cur_com["command"].attrib["source"] == "external":
            self._send_simple_return(cur_com["command"].attrib["uuid"], unicode(cur_com))
        else:
            config_control.complex_result(int(cur_com["command"].attrib["uuid"]), unicode(cur_com))

    def _send_simple_return(self, zmq_id, send_str):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(zmq_id, zmq.SNDMORE)
        send_sock.send_unicode(unicode(send_str))

    def _client_update(self, *args, **kwargs):
        _src_proc, _src_id, upd_dict = args
        run_idx = upd_dict.get("run_idx", -1)
        if run_idx in self.__pending_commands:
            cur_com = self.__pending_commands[run_idx]
            cur_dev = cur_com.xpath(".//ns:device[@name='%s']" % (upd_dict["name"]), smart_strings=False)[0]
            for key, value in upd_dict.iteritems():
                if key.endswith("_dict"):
                    new_dict = E.info_dict()
                    for s_key, s_value in value.iteritems():
                        # very hackish, fixme
                        new_dict.append(E.entry("\n".join(s_value), key=s_key))
                    cur_dev.append(new_dict)
                elif key.endswith("_tuple_list"):
                    new_tl = getattr(E, key)()
                    parent_value, parent_key = (None, None)
                    for s_key, s_value in value:
                        key_parts = s_key.split(".", 1)
                        if len(key_parts) == 1:
                            new_value = E.var(value=s_value, key=s_key)
                            new_tl.append(new_value)
                            parent_value, parent_key = (new_value, key_parts[0])  # equal to s_key
                        else:
                            if key_parts[0] != parent_key:
                                new_value = E.var(key=key_parts[0])
                                new_tl.append(new_value)
                                parent_value, parent_key = (new_value, key_parts[0])
                            parent_value.append(E.var(value=s_value, key=key_parts[1]))
                    cur_dev.append(new_tl)
                else:
                    if type(value) in [int, long]:
                        cur_dev.attrib[key] = "%d" % (value)
                    else:
                        cur_dev.attrib[key] = value
            self._handle_command(run_idx)
        else:
            self.log("got client_update with unknown run_idx %d" % (upd_dict["run_idx"]),
                     logging_tools.LOG_LEVEL_ERROR)

    def _complex_result(self, src_proc, src_id, queue_id, result, **kwargs):
        config_control.complex_result(queue_id, result)
