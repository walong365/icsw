# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2009,2012-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

import os

import zmq
from django.db.models import Q

import initat.mother
import initat.mother.command
import initat.mother.control
import initat.mother.kernel
import initat.tools.server_mixins
from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import network, status, LogSource
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.constants import CLUSTER_DIR
from initat.icsw.service.instance import InstanceXML
from initat.snmp.process import SNMPProcess
from initat.tools import server_mixins, server_command, \
    threading_tools, uuid_tools, logging_tools, process_tools, service_tools, \
    configfile
from initat.tools.server_mixins import RemoteCall, RemoteCallProcess, RemoteCallMixin
from .config import global_config
from .dhcp_config import DHCPConfigMixin


@RemoteCallProcess
class ServerProcess(server_mixins.ICSWBasePool, RemoteCallMixin, DHCPConfigMixin):
    def __init__(self):
        _long_host_name, mach_name = process_tools.get_fqdn()
        threading_tools.icswProcessPool.__init__(self, "main", zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.CC.init(icswServiceEnum.mother_server, global_config)
        self.CC.check_config()
        # close db connection (for daemonizing)
        db_tools.close_connection()
        self.debug = global_config["DEBUG"]
        self.srv_helper = service_tools.ServiceHelper(self.log)
        self.__hs_port = InstanceXML(quiet=True).get_port_dict("hoststatus", command=True)
        # log config
        self.CC.read_config_from_db(
            [
                ("TFTP_LINK", configfile.StringConfigVar("/tftpboot")),
                ("TFTP_DIR", configfile.StringConfigVar(os.path.join(CLUSTER_DIR, "system", "tftpboot"))),
                ("CLUSTER_DIR", configfile.StringConfigVar(CLUSTER_DIR)),
                # in 10th of seconds
                ("NODE_BOOT_DELAY", configfile.IntegerConfigVar(50)),
                ("FANCY_PXE_INFO", configfile.BoolConfigVar(False)),
                ("SERVER_SHORT_NAME", configfile.StringConfigVar(mach_name)),
                ("WRITE_DHCP_CONFIG", configfile.BoolConfigVar(True)),
                ("DHCP_AUTHORITATIVE", configfile.BoolConfigVar(False)),
                ("DHCP_ONLY_BOOT_NETWORKS", configfile.BoolConfigVar(True)),
                ("MODIFY_NFS_CONFIG", configfile.BoolConfigVar(True)),
                ("NEED_ALL_NETWORK_BINDS", configfile.BoolConfigVar(True)),
            ]
        )
        global_config.add_config_entries(
            [
                ("CONFIG_DIR", configfile.StringConfigVar(os.path.join(global_config["TFTP_DIR"], "config"))),
                ("ETHERBOOT_DIR", configfile.StringConfigVar(os.path.join(global_config["TFTP_DIR"], "etherboot"))),
                ("KERNEL_DIR", configfile.StringConfigVar(os.path.join(global_config["TFTP_DIR"], "kernels"))),
                ("SHARE_DIR", configfile.StringConfigVar(os.path.join(global_config["CLUSTER_DIR"], "share", "mother"))),
                ("NODE_SOURCE_IDX", configfile.IntegerConfigVar(LogSource.new("node").pk)),
            ]
        )
        self.CC.log_config()
        self.CC.re_insert_config()
        # prepare directories
        self._prepare_directories()
        # check netboot functionality
        self._check_netboot_functionality()
        # check nfs exports
        self._check_nfs_exports()
        # modify syslog config
        self._enable_syslog_config()
        # dhcp config
        self.write_dhcp_config()
        # check status entries
        self._check_status_entries()
        self.register_func("contact_hoststatus", self._contact_hoststatus)
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '{}'".format(my_uuid.urn))
        if self._init_network_sockets():
            self.add_process(initat.mother.kernel.KernelSyncProcess("kernel"), start=True)
            self.add_process(initat.mother.command.ExternalCommandProcess("command"), start=True)
            self.add_process(initat.mother.control.NodeControlProcess("control"), start=True)
            self.add_process(initat.mother.control.ICMPProcess("icmp"), start=True)
            db_tools.close_connection()
            conf_dict = {
                key: global_config[key] for key in ["LOG_NAME", "LOG_DESTINATION", "VERBOSE"]
            }
            self.add_process(SNMPProcess("snmp_process", conf_dict=conf_dict), start=True)
            # send initial commands
            self.send_to_process(
                "kernel",
                "srv_command",
                str(server_command.srv_command(command="check_kernel_dir", insert_all_found="1"))
            )
            # restart hoststatus
            self.send_to_process("command", "delay_command", "/etc/init.d/hoststatus restart", delay_time=5)
            self.send_to_process("control", "refresh", refresh=False)
        else:
            self._int_error("bind problem")

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def loop_end(self):
        # config_control.close_clients()
        self._disable_syslog_config()

    def loop_post(self):
        self.network_unbind()
        self.network_unbind(main_socket_name="pull_socket")
        self.CC.close()

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=global_config["NEED_ALL_NETWORK_BINDS"],
            pollin=self.remote_call,
            service_type_enum=icswServiceEnum.mother_server,
        )
        self.connection_set = set()
        self.connection_status = {}
        return True

    @RemoteCall(
        id_filter="^.*syslog_scan$",
        msg_type=initat.tools.server_mixins.RemoteCallMessageType.flat,
        target_process="control",
        send_async_return=False,
    )
    def syslog_line(self, payload, **kwargs):
        return payload.decode("utf-8")

    @RemoteCall(
        id_filter="^.*:(tell_mother|hoststatus):.*$",
        target_process="control",
    )
    # received and required commands
    def node_status(self, srv_com, **kwargs):
        # remove node with namespace, hack
        _id_el = srv_com.tree.find(".//ns:async_helper_id", namespaces={"ns": server_command.XML_NS})
        _id_el.getparent().remove(_id_el)
        srv_com = server_command.add_namespace(str(srv_com))
        srv_com["async_helper_id"] = _id_el.text
        return srv_com

    @RemoteCall(target_process="control")
    def nodestatus(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="control")
    def refresh(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="control")
    def soft_control(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="command")
    def hard_control(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="kernel")
    def rescan_kernels(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = self.bind_id
        srv_com.set_result("0MQ_ID is {}".format(self.bind_id), server_command.SRV_REPLY_STATE_OK)
        return srv_com

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.CC.msi_block, global_config)

    def _contact_hoststatus(self, src_id, src_pid, zmq_id, com_str, target_ip):
        dst_addr = "tcp://{}:{:d}".format(target_ip, self.__hs_port)
        if dst_addr not in self.connection_set:
            self.log("adding connection {}".format(dst_addr))
            self.connection_set.add(dst_addr)
            self.main_socket.connect(dst_addr)
        # print "done"
        zmq_id = "{}:hoststatus:".format(zmq_id)
        try:
            self.main_socket.send_unicode(zmq_id, zmq.SNDMORE)
            self.main_socket.send_unicode(str(com_str))
        except:
            self._log_con_error(zmq_id, dst_addr, process_tools.get_except_info())
        else:
            self._log_con_ok(zmq_id, dst_addr)
            if self.debug:
                self.log("sent '{}' to {} ({})".format(com_str, zmq_id, dst_addr))

    def _log_con_error(self, zmq_id, dst_addr, _error):
        _key = (zmq_id, dst_addr)
        if _key in self.connection_status:
            if self.connection_status[_key] != _error:
                self.connection_status[_key] = _error
                self._log_con(zmq_id, dst_addr, "switched to error state: {}".format(_error))
            else:
                # nothing changed
                pass
        else:
            self.connection_status[_key] = _error
            self._log_con(zmq_id, dst_addr, "is in error state: {}".format(_error))

    def _log_con_ok(self, zmq_id, dst_addr):
        _key = (zmq_id, dst_addr)
        if _key in self.connection_status:
            if self.connection_status[_key]:
                self.connection_status[_key] = ""
                self._log_con(zmq_id, dst_addr, "is now ok")
            else:
                # nothing changed
                pass
        else:
            self.connection_status[_key] = ""
            self._log_con(zmq_id, dst_addr, "is ok")

    def _log_con(self, zmq_id, dst_addr, info):
        self.log(
            "connection to {}@{} {}".format(
                zmq_id,
                dst_addr,
                info,
            ),
            logging_tools.LOG_LEVEL_ERROR if info.count("error") else logging_tools.LOG_LEVEL_OK
        )

    def _prepare_directories(self):
        self.log("Checking directories ...")
        for d_dir in [
            global_config["TFTP_DIR"],
            global_config["ETHERBOOT_DIR"],
            global_config["CONFIG_DIR"],
            global_config["KERNEL_DIR"],
        ]:
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
            cur_uc = str(mod_status)
            if mod_status.status in map_dict:
                for key, value in map_dict[mod_status.status]:
                    setattr(mod_status, key, value)
                mod_status.allow_boolean_modify = False
                new_uc = str(mod_status)
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
            valid_nets = network.objects.filter(Q(network_type__identifier__in=valid_nt_ids))
            exp_dict = {
                "etherboot": "ro",
                "kernels": "ro",
                "images": "ro",
                "config": "rw"
            }
            new_exports = {}
            exp_nets = ["{}/{}".format(cur_net.network, cur_net.netmask) for cur_net in valid_nets]
            if exp_nets:
                for exp_dir, rws in exp_dict.items():
                    act_exp_dir = os.path.join(global_config["TFTP_DIR"], exp_dir)
                    if act_exp_dir not in act_exports:
                        new_exports[act_exp_dir] = " ".join(["{}({},no_root_squash,async,no_subtree_check)".format(exp_net, rws) for exp_net in exp_nets])
            if new_exports:
                open(exp_file, "a").write("\n".join(["{:<30s} {}".format(x, y) for x, y in new_exports.items()] + [""]))
                # hm, dangerous, FIXME
                for _srv_name in self.srv_helper.find_services(".*nfs.*serv.*"):
                    self.srv_helper.service_command(_srv_name, "restart")

    def _enable_syslog_config(self):
        syslog_srvcs = self.srv_helper.find_services(".*syslog", active=True)
        self.__syslog_type = None
        if syslog_srvcs:
            self.__syslog_type = syslog_srvcs[0]
            self.log("syslog type found: {}".format(self.__syslog_type))
            # hack for old sles11sp3 (liebherr)
            if self.__syslog_type.count("rsys") or (self.__syslog_type in ["syslog"] and process_tools.get_machine_name() in ["lwnsu62020"]):
                self._enable_rsyslog()
            else:
                self.log("syslog-type {} not supported".format(self.__syslog_type), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("found no valid syslog service", logging_tools.LOG_LEVEL_ERROR)

    def _disable_syslog_config(self):
        if self.__syslog_type == "rsyslogd":
            self._disable_rsyslog()
        else:
            self.log("syslog-type {} not supported".format(self.__syslog_type), logging_tools.LOG_LEVEL_ERROR)

    def _enable_rsyslog(self):
        from initat.mother import syslog_scan
        _scan_file = syslog_scan.__file__.replace(".pyc", ".py ").replace(".pyo", ".py")
        rsyslog_lines = [
            "$ModLoad omprog",
            "$RepeatedMsgReduction off",
            "$actionomprogbinary {}".format(_scan_file),
            "",
            "if $programname contains_i 'dhcp' then :omprog:",
            "",
        ]
        # fix rights
        os.chmod(_scan_file, 0o755)
        slcn = "/etc/rsyslog.d/mother.conf"
        open(slcn, "w").write("\n".join(rsyslog_lines))
        self._restart_syslog()

    def _disable_rsyslog(self):
        slcn = "/etc/rsyslog.d/mother.conf"
        if os.path.isfile(slcn):
            os.unlink(slcn)
        self._restart_syslog()

    def _restart_syslog(self):
        for _srv_name in self.srv_helper.find_services(self.__syslog_type):
            self.srv_helper.service_command(_srv_name, "restart")

    def _check_netboot_functionality(self):
        syslinux_dir = os.path.join(global_config["SHARE_DIR"], "syslinux")
        global_config.add_config_entries(
            [
                (
                    "PXELINUX.0",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "bios", "core", "pxelinux.0"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "BOOTX64.EFI",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "efi64", "efi", "syslinux.efi"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "LDLINUX.E64",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "efi64", "com32", "elflink", "ldlinux", "ldlinux.e64"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "BOOTIA32.EFI",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "efi32", "efi", "syslinux.efi"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "MEMDISK",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "bios", "memdisk", "memdisk"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "LDLINUX.C32",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "bios", "com32", "elflink", "ldlinux", "ldlinux.c32"), "rb").read(),
                        source="filesystem"
                    )
                ),
                (
                    "MBOOT.C32",
                    configfile.BlobConfigVar(
                        open(os.path.join(syslinux_dir, "bios", "com32", "mboot", "mboot.c32"), "rb").read(),
                        source="filesystem"
                    )
                )
            ]
        )
