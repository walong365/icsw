# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2009,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" mother daemon """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import network, status
from initat.cluster.backbone.routing import get_server_uuid
from initat.mother.config import global_config
from initat.snmp.process import snmp_process
from lxml import etree  # @UnresolvedImports
from initat.tools import cluster_location
from initat.tools import configfile
import initat.mother
import initat.mother.command
import initat.mother.command
import initat.mother.control
import initat.mother.kernel
from initat.tools import logging_tools
import os
from initat.tools import process_tools
import psutil
from initat.tools import server_command
from initat.tools import threading_tools
from initat.tools import uuid_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # close db connection (for daemonizing)
        connection.close()
        self.log("open")
        # log config
        self._log_config()
        self._re_insert_config()
        # prepare directories
        self._prepare_directories()
        # check netboot functionality
        init_ok = self._check_netboot_functionality()
        # check nfs exports
        self._check_nfs_exports()
        # modify syslog config
        self._enable_syslog_config()
        # check status entries
        self._check_status_entries()
        self.__msi_block = self._init_msi_block()
        self._init_subsys()
        self.register_func("send_return", self._send_return)
        self.register_func("contact_hoststatus", self._contact_hoststatus)
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '{}'".format(my_uuid.get_urn()))
        # self.log("threads: {:d}".format(psutil.Process(pid=os.getpid()).get_num_threads()))
        if self._init_network_sockets():
            self.add_process(initat.mother.kernel.kernel_sync_process("kernel"), start=True)
            self.add_process(initat.mother.command.external_command_process("command"), start=True)
            self.add_process(initat.mother.control.node_control_process("control"), start=True)
            self.add_process(initat.mother.control.direct_process("direct"), start=True)
            conf_dict = {key: global_config[key] for key in ["LOG_NAME", "LOG_DESTINATION", "VERBOSE"]}
            self.add_process(snmp_process("snmp_process", conf_dict=conf_dict), start=True)
            connection.close()
            # self.add_process(build_process("build"), start=True)
            # self.register_func("client_update", self._client_update)
            # send initial commands
            self.send_to_process(
                "kernel",
                "srv_command",
                unicode(server_command.srv_command(command="check_kernel_dir", insert_all_found="1"))
            )
            # restart hoststatus
            self.send_to_process("command", "delay_command", "/etc/init.d/hoststatus restart", delay_time=5)
            self.send_to_process("control", "refresh")
            # self.send_to_process("control", "alter_macaddr")
            # self.__log_queue.put(("delay_request", (self.get_own_queue(), "restart_hoststatus", 5)))
        else:
            init_ok = False
        if not init_ok:
            self._int_error("bind problem")

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=6)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("mother")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=6, process_name="manager")
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def _init_subsys(self):
        self.log("init subsystems")

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("mother_server", global_config)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def loop_end(self):
        # config_control.close_clients()
        self._disable_syslog_config()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()

    def _init_network_sockets(self):
        success = True
        my_0mq_id = get_server_uuid("mother")
        self.bind_id = my_0mq_id
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", "ROUTER", global_config["SERVER_PUB_PORT"], self._new_com),
            ("pull", "PULL", global_config["SERVER_PULL_PORT"], self._new_com),
        ]:
            client = process_tools.get_socket(
                self.zmq_context,
                sock_type,
                identity=self.bind_id,
            )
            # client = self.zmq_context.socket(sock_type)
            # client.setsockopt(zmq.IDENTITY, self.bind_id)
            # client.setsockopt(zmq.LINGER, 100)
            # client.setsockopt(zmq.SNDHWM, 256)
            # client.setsockopt(zmq.RCVHWM, 256)
            # client.setsockopt(zmq.BACKLOG, 1)
            # client.setsockopt(zmq.TCP_KEEPALIVE, 1)
            # client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            # if key == "router":
            #    # set mandatory flag
            #    client.setsockopt(zmq.ROUTER_MANDATORY, 1)
            conn_str = "tcp://*:{:d}".format(bind_port)
            try:
                client.bind(conn_str)
            except zmq.ZMQError:
                self.log(
                    "error binding to {}{{{}}}: {}".format(
                        conn_str,
                        sock_type,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                client.close()
                success = False
            else:
                self.log("bind to port {}{{{}}}".format(
                    conn_str,
                    sock_type))
                self.register_poller(client, zmq.POLLIN, target_func)  # @UndefinedVariable
                self.socket_dict[key] = client
        self.connection_set = set()
        return success

    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            # print "UUID", data[0]
            if data[0].endswith("syslog_scan"):
                self.send_to_process("control", "syslog_line", data[1])
            else:
                try:
                    srv_com = server_command.srv_command(source=data[1])
                except:
                    self.log("cannot interpret '{}': {}".format(data[1][:40], process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                    zmq_sock.send_unicode("error interpreting")
                else:
                    try:
                        cur_com = srv_com["command"].text
                    except:
                        cur_com = None
                        for node_ct in ["nodeinfo", "nodestatus"]:
                            if srv_com.tree.find(node_ct) is not None:
                                node_text = srv_com.tree.findtext(node_ct)
                                t_proc = "control"
                                cur_com = node_ct
                                self.log("got command {}, sending to {} process".format(cur_com, t_proc))
                                self.send_to_process(
                                    t_proc,
                                    cur_com,
                                    data[0],
                                    node_text)
                        if cur_com is None:
                            self.log(
                                "got command '{}' from {}, ignoring".format(
                                    etree.tostring(srv_com.tree),  # @UndefinedVariable
                                    data[0]
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                    else:
                        srv_com.update_source()
                        if cur_com in ["status", "refresh", "soft_control"]:  # alter_macaddr
                            t_proc = "control"
                            self.log("got command {}, sending to {} process".format(cur_com, t_proc))
                            self.send_to_process(
                                t_proc,
                                cur_com,
                                data[0],
                                unicode(srv_com))
                        elif cur_com == "get_0mq_id":
                            srv_com["zmq_id"] = self.bind_id
                            srv_com.set_result("0MQ_ID is {}".format(self.bind_id), server_command.SRV_REPLY_STATE_OK)
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                            zmq_sock.send_unicode(unicode(srv_com))
                        elif cur_com == "server_status":
                            srv_com.set_result("up and running", server_command.SRV_REPLY_STATE_OK)
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                            zmq_sock.send_unicode(unicode(srv_com))
                        elif cur_com in ["hard_control"]:
                            srv_com.set_result("ok handled hc command", server_command.SRV_REPLY_STATE_OK)
                            t_proc = "command"
                            self.log("got command {}, sending to {} process".format(cur_com, t_proc))
                            self.send_to_process(
                                t_proc,
                                cur_com,
                                data[0],
                                unicode(srv_com))
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                            zmq_sock.send_unicode(unicode(srv_com))
                        elif cur_com in ["rescan_kernels"]:
                            t_proc = "kernel"
                            self.send_to_process(
                                t_proc,
                                cur_com,
                                data[0],
                                unicode(srv_com),
                                )
                            # srv_com.set_result("sent %s to kernel process" % (cur_com))
                            # zmq_sock.send_unicode(data[0], zmq.SNDMORE)
                            # zmq_sock.send_unicode(unicode(srv_com))
                        else:
                            srv_com.set_result("unknown command '{}'".format(cur_com), server_command.SRV_REPLY_STATE_ERROR)
                            zmq_sock.send_unicode(data[0], zmq.SNDMORE)  # @UndefinedVariable
                            zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log("wrong number of data chunks ({:d} != 2), data is '{}'".format(len(data), data[:20]),
                     logging_tools.LOG_LEVEL_ERROR)

    def _send_return(self, src_id, src_pid, zmq_id, srv_com, *args):
        self.log("returning 0MQ message to {} ({} ...)".format(zmq_id, srv_com[0:16]))
        if zmq_id.endswith(":hoststatus:"):
            self.log("refuse to send return to {}".format(zmq_id), logging_tools.LOG_LEVEL_ERROR)
        else:
            try:
                self.socket_dict["router"].send_unicode(zmq_id, zmq.SNDMORE)  # @UndefinedVariable
                self.socket_dict["router"].send_unicode(unicode(srv_com))
            except:
                self.log(
                    u"error sending to {}: {}".format(
                        zmq_id,
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )

    def _contact_hoststatus(self, src_id, src_pid, zmq_id, com_str, target_ip):
        dst_addr = "tcp://{}:2002".format(target_ip)
        if dst_addr not in self.connection_set:
            self.log("adding connection {}".format(dst_addr))
            self.connection_set.add(dst_addr)
            self.socket_dict["router"].connect(dst_addr)
        # print "done"
        zmq_id = "{}:hoststatus:".format(zmq_id)
        try:
            self.socket_dict["router"].send_unicode(zmq_id, zmq.SNDMORE)  # @UndefinedVariable
            self.socket_dict["router"].send_unicode(unicode(com_str))
        except:
            self.log(
                u"error sending to {} ({}): {}".format(
                    zmq_id,
                    dst_addr,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log("sent '{}' to {} ({})".format(com_str, zmq_id, dst_addr))
    # utility calls

    def _prepare_directories(self):
        self.log("Checking directories ...")
        for d_dir in [global_config["TFTP_DIR"],
                      global_config["ETHERBOOT_DIR"],
                      global_config["CONFIG_DIR"],
                      global_config["KERNEL_DIR"]]:
            if not os.path.isdir(d_dir):
                self.log("trying to create directory {}".format(d_dir))
                try:
                    os.makedirs(d_dir)
                except:
                    pass
        for d_link, s_link in [(global_config["TFTP_LINK"], global_config["TFTP_DIR"])]:
            if not os.path.islink(d_link):
                self.log("Trying to create link from {} to {}".format(d_link, s_link))
                try:
                    os.symlink(s_link, d_link)
                except:
                    pass

    def _check_status_entries(self):
        map_dict = {
            "memtest": [
                ("prod_link", False),
                ("memory_test", True),
                ("boot_local", False),
                ("do_install", False),
                ("is_clean", False)],
            "boot_local": [
                ("prod_link", False),
                ("memory_test", False),
                ("boot_local", True),
                ("do_install", False),
                ("is_clean", False)],
            "boot_clean": [
                ("prod_link", True),
                ("memory_test", False),
                ("boot_local", False),
                ("do_install", False),
                ("is_clean", True)],
            "boot": [
                ("prod_link", True),
                ("memory_test", False),
                ("boot_local", False),
                ("do_install", False),
                ("is_clean", False)],
            "installation_clean": [
                ("prod_link", True),
                ("memory_test", False),
                ("boot_local", False),
                ("do_install", True),
                ("is_clean", True)],
            "installation": [
                ("prod_link", True),
                ("memory_test", False),
                ("boot_local", False),
                ("do_install", True),
                ("is_clean", False)]
        }
        for mod_status in status.objects.filter(Q(allow_boolean_modify=True)):
            cur_uc = unicode(mod_status)
            if mod_status.status in map_dict:
                for key, value in map_dict[mod_status.status]:
                    setattr(mod_status, key, value)
                mod_status.allow_boolean_modify = False
                new_uc = unicode(mod_status)
                self.log("changed from {} to {}".format(cur_uc, new_uc))
                mod_status.save()
            else:
                self.log("unknown status '{}' ({})".format(mod_status.status, cur_uc), logging_tools.LOG_LEVEL_ERROR)

    def _check_nfs_exports(self):
        if global_config["MODIFY_NFS_CONFIG"]:
            exp_file = "/etc/exports"
            if os.path.isfile(exp_file):
                act_exports = {
                    part[0]: " ".join(part[1:]) for part in [
                        line.strip().split() for line in open(exp_file, "r").read().split("\n")
                    ] if len(part) > 1 and part[0].startswith("/")
                }
                self.log("found /etc/exports file with {}:".format(logging_tools.get_plural("export entry", len(act_exports))))
                exp_keys = sorted(act_exports.keys())
                my_fm = logging_tools.form_list()
                for act_exp in exp_keys:
                    where = act_exports[act_exp]
                    my_fm.add_line([act_exp, where])
                if my_fm:
                    for line in str(my_fm).split("\n"):
                        self.log("  - {}".format(line))
            else:
                self.log("found no /etc/exports file, creating new one ...")
                act_exports = {}
            valid_nt_ids = ["p", "b"]
            valid_nets = network.objects.filter(Q(network_type__identifier__in=valid_nt_ids))  # @UndefinedVariable
            exp_dict = {
                "etherboot": "ro",
                "kernels": "ro",
                "images": "ro",
                "config": "rw"
            }
            new_exports = {}
            exp_nets = ["{}/{}".format(cur_net.network, cur_net.netmask) for cur_net in valid_nets]
            if exp_nets:
                for exp_dir, rws in exp_dict.iteritems():
                    act_exp_dir = os.path.join(global_config["TFTP_DIR"], exp_dir)
                    if act_exp_dir not in act_exports:
                        new_exports[act_exp_dir] = " ".join(["{}({},no_root_squash,async,no_subtree_check)".format(exp_net, rws) for exp_net in exp_nets])
            if new_exports:
                open(exp_file, "a").write("\n".join(["{:<30s} {}".format(x, y) for x, y in new_exports.iteritems()] + [""]))
                # hm, dangerous, FIXME
                _command = "/etc/init.d/nfsserver restart"
                process_tools.call_command(_command, self.log, close_fds=True)

    def _enable_syslog_config(self):
        syslog_exe_dict = {value.pid: value.exe() for value in psutil.process_iter() if value.is_running() and value.exe().count("syslog")}
        syslog_type = None
        for key, value in syslog_exe_dict.iteritems():
            self.log("syslog process found: {}".format(key))
            if value.endswith("rsyslogd"):
                syslog_type = "rsyslogd"
            elif value.endswith("syslog-ng"):
                syslog_type = "syslog-ng"
        self.log("syslog type found: {}".format(syslog_type or "none"))
        self.__syslog_type = syslog_type
        if self.__syslog_type == "rsyslogd":
            self._enable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
            self._enable_syslog_ng()

    def _disable_syslog_config(self):
        if self.__syslog_type == "rsyslogd":
            self._disable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
            self._disable_syslog_ng()

    def _enable_rsyslog(self):
        from initat.mother import syslog_scan
        rsyslog_lines = [
            "$ModLoad omprog",
            "$RepeatedMsgReduction off",
            "$actionomprogbinary {}".format(syslog_scan.__file__.replace(".pyc", ".py ").replace(".pyo", ".py")),  # @UndefinedVariable
            "",
            "if $programname contains_i 'dhcp' then :omprog:",
            ""]
        slcn = "/etc/rsyslog.d/mother.conf"
        file(slcn, "w").write("\n".join(rsyslog_lines))
        self._reload_syslog()

    def _disable_rsyslog(self):
        slcn = "/etc/rsyslog.d/mother.conf"
        if os.path.isfile(slcn):
            os.unlink(slcn)
        self._reload_syslog()

    def _enable_syslog_ng(self):
        self.log("syslog-ng is no longer supported", logging_tools.LOG_LEVEL_ERROR)

    def _disable_syslog_ng(self):
        self.log("syslog-ng is no longer supported", logging_tools.LOG_LEVEL_ERROR)

    def _reload_syslog(self):
        syslog_rc = None
        syslog_found = False
        for syslog_rc in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng", "/etc/init.d/rsyslog"]:
            if os.path.isfile(syslog_rc):
                syslog_found = True
                break
        if syslog_found:
            self.log("found syslog script at %s, restarting" % (syslog_rc))
            restart_com = "%s restart" % (syslog_rc)
        else:
            self.log("no syslog script found, reloading via systemd")
            restart_com = "/usr/bin/systemctl restart syslog.service"
        process_tools.call_command(restart_com, log_com=self.log, close_fds=True)

    def _check_netboot_functionality(self):
        global_config.add_config_entries([
            ("PXEBOOT", configfile.bool_c_var(False, source="default")),
            ("XENBOOT", configfile.bool_c_var(False, source="default"))])
        pxe_paths = [os.path.join(global_config["SHARE_DIR"], "syslinux/pxelinux.0")]
        nb_ok = False
        for pxe_path in pxe_paths:
            if os.path.isfile(pxe_path):
                try:
                    pxelinux_0 = open(pxe_path, "r").read()
                except:
                    self.log("Cannot read pxelinux.0 from %s" % (pxe_path), logging_tools.LOG_LEVEL_WARN)
                else:
                    pxe_dir = os.path.dirname(pxe_path)
                    global_config.add_config_entries(
                        [
                            ("PXEBOOT", configfile.bool_c_var(True, source="filesystem")),
                            ("PXELINUX_0", configfile.blob_c_var(pxelinux_0, source="filesystem")),
                            ("MEMDISK", configfile.blob_c_var(file(os.path.join(pxe_dir, "memdisk"), "rb").read(), source="filesystem")),
                            ("LDLINUX", configfile.blob_c_var(file(os.path.join(pxe_dir, "ldlinux.c32"), "rb").read(), source="filesystem")),
                        ]
                    )
                    self.log("Found pxelinux.0 and ldlinux.c32 in {}".format(pxe_dir))
                    nb_ok = True
                    break
            else:
                self.log("Found no pxelinux.0 in {}".format(pxe_path), logging_tools.LOG_LEVEL_WARN)
        if not nb_ok:
            self.log("cannot provide netboot functionality", logging_tools.LOG_LEVEL_CRITICAL)
        mb32_paths = [os.path.join(global_config["SHARE_DIR"], "syslinux/mboot.c32")]
        for mb32_path in mb32_paths:
            if os.path.isfile(mb32_path):
                try:
                    mb32_0 = open(mb32_path, "r").read()
                except:
                    self.log("Cannot read mboot.c32 from %s" % (mb32_path), logging_tools.LOG_LEVEL_WARN)
                else:
                    global_config.add_config_entries(
                        [
                            ("XENBOOT", configfile.bool_c_var(True, source="filesystem")),
                            ("MBOOT.C32", configfile.blob_c_var(mb32_0, source="filesystem"))
                        ]
                    )
                    self.log("Found mboot.c32 in %s" % (mb32_path))
                    break
            else:
                self.log("Found no mboot.c32 in %s" % (mb32_path), logging_tools.LOG_LEVEL_WARN)
        return nb_ok
