#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2015 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import os

import zmq

from initat.cluster.backbone import db_tools
from initat.icsw.service.instance import InstanceXML
from initat.tools import cluster_location, configfile, logging_tools, \
    config_tools, process_tools, server_command, server_mixins, threading_tools
from initat.tools.server_mixins import RemoteCall
from .config import global_config
from .repository_process import RepoProcess
from .structs import Client


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
        )
        self.CC.init("package-server", global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        self.__pc_port = InstanceXML(quiet=True).get_port_dict("package-client", command=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self._re_insert_config()
        self.__msi_block = self._init_msi_block()
        self._init_clients()
        self._init_network_sockets()
        self.add_process(RepoProcess("repo"), start=True)
        # close DB connection
        db_tools.close_connection()
        # not needed, 0MQ is smart enough to keep the connections alive
        # self.reconnect_to_clients()
        self.send_to_process("repo", "rescan_repos")

    def _init_clients(self):
        Client.init(self)

    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("package_server", global_config)

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got SIGHUP, rescanning repositories")
        self.send_to_process("repo", "rescan_all")

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def loop_end(self):
        for c_name in Client.name_set:
            cur_c = Client.get(c_name)
            if cur_c is None:
                self.log("no client found for '{}'".format(c_name), logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_c.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.CC.close()

    def _init_network_sockets(self):
        self.socket_dict = {}
        self.network_bind(
            server_type="package",
            bind_port=global_config["COMMAND_PORT"],
            need_all_binds=False,
            pollin=self.remote_call,
            ext_call=True,
        )

    def connect_client(self, device, ip):
        _conn_str = "tcp://{}:{:d}".format(ip, self.__pc_port)
        self.log("connecting to {}".format(_conn_str))
        # not needed and not called (reconnect_clients is commented out)
        # self.main_socket.connect(_conn_str)

    def send_reply(self, t_uid, srv_com):
        send_sock = self.main_socket
        _ok = True
        try:
            send_sock.send_unicode(t_uid, zmq.SNDMORE | zmq.NOBLOCK)
            send_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)
        except:
            self.log("error sending to {}: {}".format(t_uid, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            _ok = False
        return _ok

    def _send_command(self, command, dev_list=None, **kwargs):
        send_list = dev_list or Client.name_set
        self.log(
            "send command {} to {} ({})".format(
                command,
                logging_tools.get_plural("client", len(send_list)),
                ", ".join(["{}={}".format(key, value) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs",
            )
        )
        send_com = server_command.srv_command(command=command, **kwargs)
        ok_list, error_list = ([], [])
        for target_name in send_list:
            cur_c = Client.get(target_name)
            if cur_c is not None:
                if self.send_reply(cur_c.uid, send_com):
                    ok_list.append(target_name)
                else:
                    error_list.append(target_name)
            else:
                self.log("no client with name '{}' found".format(target_name), logging_tools.LOG_LEVEL_WARN)
                error_list.append(target_name)
        return ok_list, error_list

    def reconnect_to_clients(self):
        router_obj = config_tools.router_object(self.log)
        self.log("reconnecting to {}".format(logging_tools.get_plural("client", len(Client.name_set))))
        all_servers = config_tools.device_with_config("package_server")
        if "package_server" not in all_servers:
            self.log("no package_server defined, strange...", logging_tools.LOG_LEVEL_ERROR)
        else:
            _pserver = all_servers["package_server"][0]
            if _pserver.effective_device.pk != global_config["SERVER_IDX"]:
                self.log(
                    "effective_device pk differs from SERVER_IDX: {:d} != {:d}".format(
                        _pserver.effective_device.pk,
                        global_config["SERVER_IDX"]
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                for target_name in Client.name_set:
                    cur_c = Client.get(target_name)
                    dev_sc = config_tools.server_check(
                        device=cur_c.device,
                        config="",
                        server_type="node",
                        fetch_network_info=True
                    )
                    act_routing_info = _pserver.get_route_to_other_device(
                        router_obj,
                        dev_sc,
                        allow_route_to_other_networks=True,
                        prefer_production_net=True,
                    )
                    if act_routing_info:
                        _ip = act_routing_info[0][3][1][0]
                        self.log("found routing_info for {}, IP is {}".format(unicode(cur_c.device), _ip))
                        self.connect_client(cur_c.device, _ip)
                        # self.send_reply(cur_c.uid, server_command.srv_command(command="hello"))
                    else:
                        self.log("no routing_info found for {}".format(unicode(cur_c.device)))

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.__msi_block, global_config)

    @RemoteCall(target_process="repo")
    def reload_searches(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="repo")
    def rescan_repos(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def sync_repos(self, srv_com, **kwargs):
        all_devs = list(Client.name_set)
        self.log(
            "sending sync_repos to {}".format(
                logging_tools.get_plural("device", len(all_devs))
            )
        )
        if all_devs:
            self._send_command("sync_repos", dev_list=all_devs)
        srv_com.set_result(
            "send sync_repos to {}".format(
                logging_tools.get_plural("device", len(all_devs))
            )
        )
        return srv_com

    @RemoteCall()
    def clear_caches(self, srv_com, **kwargs):
        all_devs = list(Client.name_set)
        if os.getuid():
            self.log("root privileges required to clear cache", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.send_to_process("repo", "clear_cache", unicode(srv_com))
        self.log("sending clear_cache to %s" % (logging_tools.get_plural("device", len(all_devs))))
        if all_devs:
            self._send_command("clear_cache", dev_list=all_devs)
        srv_com.set_result(
            "send clear_cache to {}".format(
                logging_tools.get_plural("device", len(all_devs))
            )
        )
        return srv_com

    @RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = kwargs["bind_id"]
        srv_com.set_result("0MQ_ID is {}".format(kwargs["bind_id"]))
        return srv_com

    @RemoteCall()
    def new_config(self, srv_com, **kwargs):
        com_uuids = srv_com.xpath(".//ns:device_command/@uuid", smart_strings=False)
        if not com_uuids:
            valid_devs = list(Client.name_set)
            self.log(
                "no devices requested, using {} found".format(
                    logging_tools.get_plural("device", len(valid_devs))
                )
            )
        else:
            full_uuids = [Client.full_uuid(uuid) for uuid in com_uuids]
            valid_uuids = [uuid for uuid in full_uuids if uuid in Client.uuid_set]
            valid_devs = [Client.get(uuid).name for uuid in valid_uuids]
            self.log(
                "{} requested, {} found: {}".format(
                    logging_tools.get_plural("device", len(com_uuids)),
                    logging_tools.get_plural("device", len(valid_devs)),
                    logging_tools.reduce_list(valid_devs) or "---",
                )
            )
        for cur_uuid in com_uuids:
            # update config_sent attribte
            srv_com.xpath(
                ".//ns:device_command[@uuid='{}']".format(cur_uuid),
                smart_strings=False
            )[0].attrib["config_sent"] = "1" if cur_uuid in valid_uuids else "0"
        if valid_devs:
            ok_list, error_list = self._send_command("new_config", dev_list=valid_devs)
            if error_list:
                _state = server_command.SRV_REPLY_STATE_ERROR
            else:
                _state = server_command.SRV_REPLY_STATE_OK
            _log_str = "sent update to {} ({})".format(
                logging_tools.get_plural("device", len(valid_devs)),
                ", ".join(
                    [
                        _entry for _entry in [
                            "{:d} OK".format(len(ok_list)) if ok_list else "",
                            "{}: {}".format(
                                logging_tools.get_plural("error", len(error_list)),
                                logging_tools.reduce_list(error_list),
                            ) if error_list else "",
                        ] if _entry.strip()
                    ]
                )
            )
            self.log(_log_str, server_command.srv_reply_to_log_level(_state))
            srv_com.set_result(
                _log_str,
                _state,
            )
        else:
            srv_com.set_result(
                "no devices registered", server_command.SRV_REPLY_STATE_WARN
            )
        return srv_com

    @RemoteCall(id_filter="^.*:(pclient):.*$")
    def client_command(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    @RemoteCall(id_filter="^.*:(package-client):.*$")
    def client_command(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    @RemoteCall()
    def register(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    @RemoteCall()
    def get_repo_list(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    @RemoteCall()
    def package_info(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    @RemoteCall()
    def get_package_list(self, srv_com, **kwargs):
        return self._client_command(srv_com, **kwargs)

    def _client_command(self, srv_com, **kwargs):
        c_uid = kwargs["src_id"]
        cur_com = srv_com["command"].text
        if (not c_uid.endswith(":pclient:")) and (not c_uid.endswith(":package-client:")):
            c_uid = "{}:package-client:".format(c_uid)
        if cur_com == "register":
            srv_com = Client.register(c_uid, srv_com["source"].attrib["host"])
        else:
            try:
                cur_client = Client.get(c_uid)
            except KeyError:
                srv_com.update_source()
                # srv_com["result"] = None
                self.log("got command '{}' from {}".format(cur_com, c_uid))
                # check for normal command
                if cur_com == "get_0mq_id":
                    srv_com["zmq_id"] = kwargs["bind_id"]
                    srv_com.set_result("0MQ_ID is {}".format(kwargs["bind_id"]))
                else:
                    self.log(
                        "unknown uuid {} (command {}), not known".format(
                            c_uid,
                            cur_com,
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                    srv_com.set_result("unknown command '{}'".format(cur_com), server_command.SRV_REPLY_STATE_ERROR)
            else:
                srv_com = cur_client.new_command(srv_com)
        return srv_com
