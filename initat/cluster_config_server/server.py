# Copyright (C) 2001-2008,2012-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, server part """

import os

import zmq
from django.db.models import Q
from lxml import etree
from lxml.builder import E

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.icsw.service.instance import InstanceXML
from initat.tools import configfile, logging_tools, process_tools, server_command, \
    threading_tools, server_mixins
from .build_process import BuildProcess
from .config import global_config
from .config_control import ConfigControl


class server_process(server_mixins.ICSWBasePool):
    def __init__(self):
        threading_tools.icswProcessPool.__init__(self, "main", zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.CC.init(icswServiceEnum.config_server, global_config)
        self.CC.check_config()
        self.CC.read_config_from_db(
            [
                ("TFTP_DIR", configfile.str_c_var("/tftpboot")),
                ("MONITORING_PORT", configfile.int_c_var(InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True))),
                ("LOCALHOST_IS_EXCLUSIVE", configfile.bool_c_var(True)),
                ("HOST_CACHE_TIME", configfile.int_c_var(10 * 60)),
                ("WRITE_REDHAT_HWADDR_ENTRY", configfile.bool_c_var(True)),
                ("ADD_NETDEVICE_LINKS", configfile.bool_c_var(False)),
            ]
        )
        global_config.add_config_entries(
            [
                ("CONFIG_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "config"))),
                ("IMAGE_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "images"))),
                ("KERNEL_DIR", configfile.str_c_var(os.path.join(global_config["TFTP_DIR"], "kernels"))),
            ]
        )
        self.__pid_name = global_config["PID_NAME"]
        # close DB connection (daemonize)
        db_tools.close_connection()
        self.CC.re_insert_config()
        self._log_config()
        self._init_subsys()
        self._init_network_sockets()
        self.add_process(BuildProcess("build"), start=True)
        db_tools.close_connection()
        self.register_func("client_update", self._client_update)
        self.register_func("complex_result", self._complex_result)
        self.__run_idx = 0
        self.__pending_commands = {}

    def _init_subsys(self):
        self.log("init subsystems")
        ConfigControl.init(self)

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

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def loop_end(self):
        ConfigControl.close_clients()

    def loop_post(self):
        for open_sock in self.socket_dict.values():
            open_sock.close()
        self.CC.close()

    def _init_network_sockets(self):
        my_0mq_id = get_server_uuid("config")
        self.bind_id = my_0mq_id
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["COMMAND_PORT"], self._new_com),
        ]:
            client = self.zmq_context.socket(sock_type)
            try:
                client.setsockopt(zmq.IDENTITY, my_0mq_id)
            except TypeError:
                client.setsockopt_string(zmq.IDENTITY, my_0mq_id)
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
                    if not ConfigControl.has_client(src_id):
                        try:
                            new_dev = device.objects.get(Q(uuid=src_id) | Q(uuid__startswith=src_id[:-5]))
                        except device.DoesNotExist:
                            self.log(
                                "no device with UUID {} found in database".format(src_id),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            cur_c = None
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)
                            zmq_sock.send_unicode("error unknown UUID")
                        else:
                            cur_c = ConfigControl.add_client(new_dev)
                    else:
                        cur_c = ConfigControl.get_client(src_id)
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
                    srv_com["zmq_id"] = self.bind_id
                    srv_com.set_result(
                        "0MQ_ID is {}".format(self.bind_id),
                    )
                    self._send_simple_return(c_uid, str(srv_com))
                elif cur_com == "status":
                    srv_com.set_result(
                        "up and running"
                    )
                    self._send_simple_return(c_uid, str(srv_com))
                else:
                    if c_uid.endswith("webfrontend"):
                        # special command from webfrontend, FIXME
                        srv_com["command"].attrib["source"] = "external"
                        self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                    else:
                        try:
                            cur_client = None  # client.get(c_uid)
                        except KeyError:
                            self.log(
                                "unknown uid {}, not known".format(c_uid),
                                logging_tools.LOG_LEVEL_CRITICAL
                            )
                        else:
                            if cur_client is None:
                                self.log("cur_client is None (command: {})".format(cur_com), logging_tools.LOG_LEVEL_WARN)
                            else:
                                cur_client.new_command(srv_com)
        else:
            self.log(
                "wrong number of data chunks ({:d} != 2), data is '{}'".format(len(data), data[:20]),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _handle_wfe_command(self, zmq_sock, c_uid, srv_com):
        cur_com = srv_com["command"].text
        self.__run_idx += 1
        srv_com["command"].attrib["run_idx"] = "{:d}".format(self.__run_idx)
        srv_com["command"].attrib["uuid"] = c_uid
        self.__pending_commands[self.__run_idx] = srv_com
        # get device names
        device_list = device.objects.select_related("domain_tree_node").filter(Q(pk__in=[cur_dev.attrib["pk"] for cur_dev in srv_com["devices:devices"]]))
        self.log(
            "got command {} for {}: {}".format(
                cur_com,
                logging_tools.get_plural("device", len(device_list)),
                ", ".join([str(cur_dev) for cur_dev in device_list])
            )
        )
        dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device_list])
        # set device state
        for cur_dev in srv_com["devices:devices"]:
            cur_dev.attrib["command"] = cur_com
            cur_dev.attrib["internal_state"] = "pre_init"
            cur_dev.attrib["run_idx"] = "%d" % (self.__run_idx)
            cur_dev.text = str(dev_dict[int(cur_dev.attrib["pk"])])
            cur_dev.attrib["short_name"] = dev_dict[int(cur_dev.attrib["pk"])].name
            cur_dev.attrib["name"] = dev_dict[int(cur_dev.attrib["pk"])].full_name
        self._handle_command(self.__run_idx)

    def create_config(self, queue_id, s_req):
        # create a build_config request
        cur_com = server_command.srv_command(command="build_config")
        cur_com["devices"] = cur_com.builder(
            "devices",
            cur_com.builder("device", pk="{:d}".format(s_req.cc.device.pk))
        )
        cur_com["command"].attrib["source"] = "config_control"
        self._handle_wfe_command(None, str(queue_id), cur_com)

    def _handle_command(self, run_idx):
        cur_com = self.__pending_commands[run_idx]
        num_devs = 0
        for cur_dev in cur_com["devices:devices"]:
            num_devs += 1
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
            cur_com.set_result(
                "built config for {}".format(logging_tools.get_plural("device", num_devs)),
            )
            self._send_return(cur_com)
            del self.__pending_commands[run_idx]

    def _send_return(self, cur_com):
        if cur_com["command"].attrib["source"] == "external":
            self._send_simple_return(cur_com["command"].attrib["uuid"], str(cur_com))
        else:
            ConfigControl.complex_result(int(cur_com["command"].attrib["uuid"]), str(cur_com))

    def _send_simple_return(self, zmq_id, send_str):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(zmq_id, zmq.SNDMORE)
        send_sock.send_unicode(str(send_str))

    def _client_update(self, *args, **kwargs):
        _src_proc, _src_id, upd_dict = args
        run_idx = upd_dict.get("run_idx", -1)
        if run_idx in self.__pending_commands:
            cur_com = self.__pending_commands[run_idx]
            cur_dev = cur_com.xpath(".//ns:device[@name='{}']".format(upd_dict["name"]), smart_strings=False)[0]
            for key, value in upd_dict.items():
                if key.endswith("_dict"):
                    new_dict = E.info_dict()
                    for s_key, s_value in value.items():
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
                    if isinstance(value, int):
                        cur_dev.attrib[key] = "%d" % (value)
                    else:
                        cur_dev.attrib[key] = value
            self._handle_command(run_idx)
        else:
            self.log(
                "got client_update with unknown run_idx {:d}".format(upd_dict["run_idx"]),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _complex_result(self, src_proc, src_id, queue_id, result, **kwargs):
        ConfigControl.complex_result(queue_id, result)
