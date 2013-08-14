#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" server process for md-config-server """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import cluster_location
import codecs
import commands
import configfile
import logging_tools
import mk_livestatus
import process_tools
import re
import server_command
import threading_tools
import time
import uuid_tools
import zmq

from initat.md_config_server.config import global_config
from initat.md_config_server.build import build_process
from initat.md_config_server.status import status_process
from initat.md_config_server import constants

try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

from django.db.models import Q
from django.db import connection, connections
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
     mon_ext_host, mon_check_command, mon_period, mon_contact, \
     mon_contactgroup, mon_service_templ, netdevice, network, network_type, net_ip, \
     user, mon_host_cluster, mon_service_cluster, config, md_check_data_store, category, \
     category_tree, TOP_MONITORING_CATEGORY, mon_notification, config_str, config_int, host_check_command

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        self.__enable_livestatus = global_config["ENABLE_LIVESTATUS"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out" : (1, "md-config-server.out"),
                "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        connection.close()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._check_notification()
        self._check_nagios_version()
        self._check_relay_version()
        self._log_config()
        self._init_network_sockets()
        self.register_func("register_slave", self._register_slave)
        self.register_func("send_command", self._send_command)
        self.__external_cmd_file = None
        self.register_func("external_cmd_file", self._set_external_cmd_file)
        # self.add_process(db_verify_process("db_verify"), start=True)
        self.add_process(build_process("build"), start=True)
        self.add_process(status_process("status"), start=True)
        self._init_em()
        self.register_timer(self._check_db, 3600, instant=True)
        self.register_timer(self._check_for_redistribute, 30 if global_config["DEBUG"] else 300)
        self.register_timer(self._update, 30, instant=True)
        if global_config["BUILD_CONFIG_ON_STARTUP"]:
            self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")
    def _check_db(self):
        self.send_to_process("db_verify", "validate")
    def _check_for_redistribute(self):
        self.send_to_process("build", "check_for_redistribute")
    def _init_em(self):
        self.__esd, self.__nvn = ("/tmp/.machvect_es", "nagios_ov")
        init_ok = False
        if os.path.isdir(self.__esd):
            ofile = "%s/%s.mvd" % (self.__esd, self.__nvn)
            try:
                file(ofile, "w").write("\n".join([
                    "nag.tot:0:Number of devices monitored by %s:1:1:1" % (global_config["MD_TYPE"]),
                    "nag.up:0:Number of devices up:1:1:1",
                    "nag.down:0:Number of devices down:1:1:1",
                    "nag.unknown:0:Number of devices unknown:1:1:1",
                    ""]))
            except:
                self.log("cannot write %s: %s" % (ofile, process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                init_ok = True
        self.__em_ok = init_ok
    def _update(self):
        res_dict = {}
        if self.__enable_livestatus:
            if mk_livestatus:
                sock_name = "/opt/%s/var/live" % (global_config["MD_TYPE"])
                cur_s = mk_livestatus.Socket(sock_name)
                try:
                    query = cur_s.query("GET hosts\nColumns: name state\n")
                except:
                    self.log("cannot query socket %s: %s" % (sock_name, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    q_list = [int(value["state"]) for value in query.get_list()]
                    res_dict = dict([(s_name, q_list.count(value)) for s_name, value in [
                        ("unknown", constants.NAG_HOST_UNKNOWN),
                        ("up"     , constants.NAG_HOST_UP),
                        ("down"   , constants.NAG_HOST_DOWN)]])
                    res_dict["tot"] = sum(res_dict.values())
                # cur_s.peer.close()
                del cur_s
            else:
                self.log("mk_livestatus enabled but module not loaded", logging_tools.LOG_LEVEL_ERROR)
        else:
            # old code, ask SQL Server
            sql_str = "SELECT nhs.current_state AS host_status, nh.display_name AS host_name FROM %s_hoststatus nhs, %s_hosts nh WHERE nhs.host_object_id=nh.host_object_id" % (
                global_config["MD_TYPE"],
                global_config["MD_TYPE"])
            cursor = connections["monitor"].cursor()
            nag_suc = cursor.execute(sql_str)
            nag_dict = dict([(db_rec[1], db_rec[0]) for db_rec in cursor.fetchall()])
            res_dict = {"tot"  : len(nag_dict.keys()),
                        "up"   : nag_dict.values().count(constants.NAG_HOST_UP),
                        "down" : nag_dict.values().count(constants.NAG_HOST_DOWN)}
            res_dict["unknown"] = res_dict["tot"] - (res_dict["up"] + res_dict["down"])
            cursor.close()
        if res_dict:
            self.log("%s status is: %d up, %d down, %d unknown (%d total)" % (
                global_config["MD_TYPE"],
                res_dict["up"],
                res_dict["down"],
                res_dict["unknown"],
                res_dict["tot"]))
            if not self.__em_ok:
                self._init_em()
            if self.__em_ok:
                ofile = "%s/%s.mvv" % (self.__esd, self.__nvn)
                try:
                    file(ofile, "w").write("\n".join(["nag.tot:i:%d" % (res_dict["tot"]),
                                                      "nag.up:i:%d" % (res_dict["up"]),
                                                      "nag.down:i:%d" % (res_dict["down"]),
                                                      "nag.unknown:i:%d" % (res_dict["unknown"]),
                                                      ""]))
                except:
                    self.log("cannot write to file %s: %s" % (ofile,
                                                              process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    pass
        else:
            self.log("empty result dict for _update()", logging_tools.LOG_LEVEL_WARN)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        cluster_location.write_config("monitor_server", global_config)
    def _check_nagios_version(self):
        start_time = time.time()
        md_version, md_type = ("unknown", "unknown")
        for t_daemon in ["icinga", "icinga-init", "nagios", "nagios-init"]:
            if os.path.isfile("/etc/debian_version"):
                cstat, cout = commands.getstatusoutput("dpkg -s %s" % (t_daemon))
                if not cstat:
                    deb_version = [y for y in [x.strip() for x in cout.split("\n")] if y.startswith("Version")]
                    if deb_version:
                        md_version = deb_version[0].split(":")[1].strip()
                    else:
                        self.log("No Version-info found in dpkg-list", logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package %s not found in dpkg-list" % (t_daemon), logging_tools.LOG_LEVEL_ERROR)
            else:
                cstat, cout = commands.getstatusoutput("rpm -q %s" % (t_daemon))
                if not cstat:
                    rpm_m = re.match("^%s-(?P<version>.*)$" % (t_daemon), cout.split()[0].strip())
                    if rpm_m:
                        md_version = rpm_m.group("version")
                    else:
                        self.log("Cannot parse %s" % (cout.split()[0].strip()), logging_tools.LOG_LEVEL_WARN)
                else:
                    self.log("Package %s not found in RPM db" % (t_daemon), logging_tools.LOG_LEVEL_ERROR)
            if md_version != "unknown":
                md_type = t_daemon.split("-")[0]
                break
        # save to local config
        if md_version[0].isdigit():
            global_config.add_config_entries([
                ("MD_TYPE"          , configfile.str_c_var(md_type)),
                ("MD_VERSION"       , configfile.int_c_var(int(md_version.split(".")[0]))),
                ("MD_RELEASE"       , configfile.int_c_var(int(md_version.split(".")[1]))),
                ("MD_VERSION_STRING", configfile.str_c_var(md_version)),
                ("MD_BASEDIR"       , configfile.str_c_var("/opt/%s" % (md_type))),
                ("MAIN_CONFIG_NAME" , configfile.str_c_var(md_type)),
                ("MD_LOCK_FILE"     , configfile.str_c_var("%s.lock" % (md_type))),
            ])
        # device_variable local to the server
        dv = cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_version", description="Version of the Monitor-daemon pacakge", value=md_version)
# #        if dv.is_set():
# #            dv.set_value(md_version)
# #            dv.update(dc)
        cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_version", description="Version of the Monitor-daemon RPM", value=md_version, force_update=True)
        cluster_location.db_device_variable(global_config["SERVER_IDX"], "md_type", description="Type of the Monitor-daemon RPM", value=md_type, force_update=True)
        if md_version == "unknown":
            self.log("No installed monitor-daemon found (version set to %s)" % (md_version), logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed monitor-daemon %s, version %s" % (md_type, md_version))
        end_time = time.time()
        self.log("monitor-daemon version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _check_relay_version(self):
        start_time = time.time()
        relay_version = "unknown"
        if os.path.isfile("/etc/debian_version"):
            cstat, cout = commands.getstatusoutput("dpkg -s host-relay")
            if not cstat:
                deb_version = [y for y in [x.strip() for x in cout.split("\n")] if y.startswith("Version")]
                if deb_version:
                    relay_version = deb_version[0].split(":")[1].strip()
                else:
                    self.log("No Version-info found in dpkg-list", logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("Package host-relay not found in dpkg-list", logging_tools.LOG_LEVEL_ERROR)
        else:
            cstat, cout = commands.getstatusoutput("rpm -q host-relay")
            if not cstat:
                rpm_m = re.match("^host-relay-(?P<version>.*)$", cout.split()[0].strip())
                if rpm_m:
                    relay_version = rpm_m.group("version")
                else:
                    self.log("Cannot parse %s" % (cout.split()[0].strip()), logging_tools.LOG_LEVEL_WARN)
            else:
                self.log("Package host-relay not found in RPM db", logging_tools.LOG_LEVEL_ERROR)
        if relay_version != "unknown":
            relay_split = [int(value) for value in relay_version.split("-")[0].split(".")]
            has_snmp_relayer = False
            if relay_split[0] > 0 or (len(relay_split) == 2 and (relay_split[0] == 0 and relay_split[1] > 4)):
                has_snmp_relayer = True
            if has_snmp_relayer:
                global_config.add_config_entries([("HAS_SNMP_RELAYER", configfile.bool_c_var(True))])
                self.log("host-relay package has snmp-relayer, rewriting database entries for nagios")
        # device_variable local to the server
        if relay_version == "unknown":
            self.log("No installed host-relay found", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("Discovered installed host-relay version %s" % (relay_version))
        end_time = time.time()
        self.log("host-relay version discovery took %s" % (logging_tools.get_diff_time_str(end_time - start_time)))
    def _check_notification(self):
        cur_not = mon_notification.objects.all().count()
        if cur_not:
            self.log("%s defined, skipping check" % (logging_tools.get_plural("notification", cur_not)))
        else:
            if "NOTIFY_BY_EMAIL_LINE01" in global_config:
                self.log("rewriting notifications from global_config")
                str_dict = {
                    "sms" : {
                        "host"    : ("", [global_config["HOST_NOTIFY_BY_SMS_LINE01"]]),
                        "service" : ("", [global_config["NOTIFY_BY_SMS_LINE01"]]),
                        },
                    "mail" : {
                        "host"    : (
                            global_config["HOST_NOTIFY_BY_EMAIL_SUBJECT"],
                            [global_config["HOST_NOTIFY_BY_EMAIL_LINE%02d" % (idx)] for idx in xrange(1, 16)],
                            ),
                        "service" : (
                            global_config["NOTIFY_BY_EMAIL_SUBJECT"],
                            [global_config["NOTIFY_BY_EMAIL_LINE%02d" % (idx)] for idx in xrange(1, 16)],
                            ),
                    }
                }
                for key in global_config.keys():
                    if key.count("NOTIFY_BY") and (key.count("LINE") or key.count("SUBJECT")):
                        src = global_config.get_source(key)
                        if src.count("::"):
                            t_type, pk = src.split("::")
                            var_obj = {"str_table" : config_str,
                                       "int_table" : config_int}.get(t_type, None)
                            if var_obj:
                                try:
                                    var_obj.objects.get(Q(pk=pk)).delete()
                                except:
                                    self.log("cannot delete var %s: %s" % (key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                                else:
                                    self.log("deleted variable %s" % (key))
                                    del global_config[key]
                            else:
                                self.log("unknown source_table %s for %s" % (t_type, key), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            self.log("cannot parse source %s of %s" % (src, key), logging_tools.LOG_LEVEL_ERROR)
            else:
                # default dict
                str_dict = {
                    'mail': {
                        'host': (
                            u'Host $HOSTSTATE$ alert for $HOSTNAME$@$INIT_CLUSTER_NAME$',
                            [
                                u'***** $INIT_MONITOR_INFO$ *****',
                                u'',
                                u'Notification Type: $NOTIFICATIONTYPE$',
                                u'',
                                u'Cluster: $INIT_CLUSTER_NAME$',
                                u'Host   : $HOSTNAME$',
                                u'State  : $HOSTSTATE$',
                                u'Address: $HOSTADDRESS$',
                                u'Info   : $HOSTOUTPUT$',
                                u'',
                                u'Date/Time: $LONGDATETIME$',
                                u'',
                                u'',
                                u'',
                                u''
                                ]
                        ),
                        'service': (
                            u'$NOTIFICATIONTYPE$ alert - $HOSTNAME$@$INIT_CLUSTER_NAME$ ($HOSTALIAS$)/$SERVICEDESC$ is $SERVICESTATE$',
                            [
                                u'***** $INIT_MONITOR_INFO$ *****',
                                u'',
                                u'Notification Type: $NOTIFICATIONTYPE$',
                                u'',
                                u'Cluster: $INIT_CLUSTER_NAME$',
                                u'Service: $SERVICEDESC$',
                                u'Host   : $HOSTALIAS$',
                                u'Address: $HOSTADDRESS$',
                                u'State  : $SERVICESTATE$',
                                u'',
                                u'Date/Time: $LONGDATETIME$',
                                u'',
                                u'Additional Info:',
                                u'',
                                u'$SERVICEOUTPUT$'
                                ]
                            )
                        },
                    'sms': {
                        'host': (
                            '', [
                                u'$HOSTSTATE$ alert for $HOSTNAME$ ($HOSTADDRESS$)'
                                ]
                            ),
                        'service': (
                            '',
                            [
                                u'$NOTIFICATIONTYPE$ alert - $SERVICEDESC$ is $SERVICESTATE$ on $HOSTNAME$'
                            ]
                        )
                    }
                }
            for channel, s_dict in str_dict.iteritems():
                for not_type, (subject, content) in s_dict.iteritems():
                    mon_notification.objects.create(
                        name="%s-notify-by-%s" % (not_type, channel),
                        channel=channel,
                        not_type=not_type,
                        subject=subject,
                        content="\n".join(content)
                    )
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=4)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("md-config-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4)
            msi_block.start_command = "/etc/init.d/md-config-server start"
            msi_block.stop_command = "/etc/init.d/md-config-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _register_slave(self, *args, **kwargs):
        src_proc, src_id, slave_ip, slave_uuid = args
        conn_str = "tcp://%s:%d" % (slave_ip,
                                    2004)
        if conn_str not in self.__slaves:
            self.log("connecting to slave on %s (%s)" % (conn_str, slave_uuid))
            self.com_socket.connect(conn_str)
            self.__slaves[conn_str] = slave_uuid
    def _handle_ocp_event(self, in_com):
        com_type = in_com["command"].text
        targ_list = [cur_arg.text for cur_arg in in_com.xpath(None, ".//ns:arguments")[0]]
        target_com = {
            "ocsp-event" : "PROCESS_SERVICE_CHECK_RESULT",
            "ochp-event" : "PROCESS_HOST_CHECK_RESULT"}[com_type]
        # rewrite state information
        state_idx, error_state = (1, 1) if com_type == "ochp-event" else (2, 2)
        targ_list[state_idx] = "%d" % ({
            "ok"          : 0,
            "up"          : 0,
            "warning"     : 1,
            "down"        : 1,
            "unreachable" : 2,
            "critical"    : 2,
            "unknown"     : 3}.get(targ_list[state_idx].lower(), error_state))
        if com_type == "ocsp-event":
            pass
        else:
            pass
        out_line = "[%d] %s;%s\n" % (
            int(time.time()),
            target_com,
            ";".join(targ_list))
        if self.__external_cmd_file:
            try:
                codecs.open(self.__external_cmd_file, "w", "utf-8").write(out_line)
            except:
                self.log("error writing to %s: %s" % (
                    self.__external_cmd_file,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                raise
        else:
            self.log("no external cmd_file defined", logging_tools.LOG_LEVEL_ERROR)
    def _send_command(self, *args, **kwargs):
        src_proc, src_id, full_uuid, srv_com = args
        self.log("init send of %s bytes to %s" % (len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)
    def _set_external_cmd_file(self, *args, **kwargs):
        src_proc, src_id, ext_name = args
        self.log("setting external cmd_file to '%s'" % (ext_name))
        self.__external_cmd_file = ext_name
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "%s:monitor_master" % (uuid_tools.get_uuid().get_urn()))
        client.setsockopt(zmq.SNDHWM, 256)
        client.setsockopt(zmq.RCVHWM, 256)
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
            self.__slaves = {}
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(in_data) == 2:
            src_id, data = in_data
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log("error interpreting command: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                # send something back
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                self.com_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event"]:
                    self.log("got command '%s' from '%s'" % (
                        cur_com,
                        srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = False
                if cur_com == "rebuild_host_config":
                    send_return = True
                    self.send_to_process("build", "rebuild_config", cache_mode=srv_com.get("cache_mode", "DYNAMIC"))
                elif cur_com == "get_node_status":
                    self.send_to_process("status", "get_node_status", src_id, unicode(srv_com))
                elif cur_com == "get_host_config":
                    self.send_to_process("build", "build_host_config", src_id, unicode(srv_com))
                elif cur_com == "sync_http_users":
                    send_return = True
                    self.send_to_process("build", "sync_http_users")
                elif cur_com in ["ocsp-event", "ochp-event"]:
                    self._handle_ocp_event(srv_com)
                elif cur_com in ["file_content_result"]:
                    self.send_to_process("build", "file_content_info", unicode(srv_com))
                else:
                    self.log("got unknown command '%s'" % (cur_com), logging_tools.LOG_LEVEL_ERROR)
                if send_return:
                    srv_com["result"] = None
                    # blabla
                    srv_com["result"].attrib.update({"reply" : "ok processed command %s" % (cur_com),
                                                     "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.com_socket.send_unicode(unicode(srv_com))
                else:
                    del cur_com
        else:
            self.log(
                "wrong count of input data frames: %d, first one is %s" % (
                    len(in_data),
                    in_data[0]),
                logging_tools.LOG_LEVEL_ERROR)
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.com_socket.close()
        self.__log_template.close()
    def thread_loop_post(self):
        if self.__em_ok:
            for f_name in ["%s/%s.mvd" % (self.__esd, self.__nvn),
                           "%s/%s.mvv" % (self.__esd, self.__nvn)]:
                if os.path.isfile(f_name):
                    try:
                        os.unlink(f_name)
                    except:
                        self.log("cannot delete file %s: %s" % (f_name,
                                                                process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

