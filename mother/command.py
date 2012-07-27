#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Andreas Lang-Nevyjel, init.at
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
""" external commands (dhcp, ipmi) parts of mother """


import threading_tools
import logging_tools
from mother.config import global_config
import config_tools
import commands
import time
import subprocess
from django.db import connection
from django.db.models import Q
from init.cluster.backbone.models import device, network
from mother.command_tools import simple_command
        
class external_command_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        simple_command.setup(self)
        self.sc = config_tools.server_check(server_type="mother")
        if "b" in self.sc.identifier_ip_lut:
            self.__kernel_ip = self.sc.identifier_ip_lut["b"][0].ip
            self.log("IP address in boot-net is %s" % (self.__kernel_ip))
        else:
            self.__kernel_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.register_func("delay_command", self._delay_command)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _delay_command(self, *args, **kwargs):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        new_sc = simple_command(args[0], delay_time=kwargs.get("delay_time", 0))
    def _server_com(self, s_com):
        dst_call = {"alter_macadr"  : self._adw_macaddr,
                    "delete_macadr" : self._adw_macaddr,
                    "write_macadr"  : self._adw_macaddr,
                    "syslog_line"   : self._syslog_line}.get(s_com.get_command(), None)
        if dst_call:
            dst_call(s_com.get_command(), s_com)
        else:
            self.log("Unknown server_message_command: %s" % (s_com.get_command()), logging_tools.LOG_LEVEL_ERROR)
        if s_com.get_option_dict().has_key("SIGNAL_MAIN_THREAD"):
            self.send_pool_message(s_com.get_option_dict()["SIGNAL_MAIN_THREAD"])
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.unregister_timer(self._check_commands)
    def sc_finished(self, sc_com):
        self.log("simple command done")
        print sc_com.read()
    def _syslog_line(self, com_name, s_com):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        server_opts = s_com.get_option_dict()
        sm_type     = server_opts["sm_type"]
        ip          = server_opts["ip"]
        mac         = server_opts["mac"]
        full_string = server_opts["message"]
        mach_idx = 0
        if ip:
            if self.__ad_struct.has_key(ip):
                mach = self.__ad_struct[ip]
                mach.incr_use_count("syslog line")
                dc.execute("SELECT d.device_idx, s.status, d.name, d.bootserver, n.devname, n.macadr, d.dhcp_mac, n.netdevice_idx, d.newkernel, d.new_kernel, d.kernel_append, d.stage1_flavour FROM device d INNER JOIN netdevice n INNER JOIN netip i LEFT JOIN status s ON d.newstate=s.status_idx WHERE i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND i.ip='%s'" % (ip))
                dev_list = dc.fetchall()
                if len(dev_list):
                    first_dev = dev_list[0]
                    boot_server, dev_name = (first_dev["bootserver"], first_dev["name"])
                    if boot_server != self.__loc_config["MOTHER_SERVER_IDX"]:
                        self.log("Not responsible for device '%s' (ip %s); bootserver has idx %d" % (dev_name, ip, boot_server))
                    else:
                        mach_idx = mach.device_idx
                        if first_dev["dhcp_mac"]:
                            dc.execute("UPDATE device SET dhcp_mac=0 WHERE name='%s'" % (mach.name))
                            mach.log("Clearing dhcp_mac flag for device '%s' (using ip %s)" % (dev_name, ip))
                        #else:
                        #    mach.log("dhcp_mac flag for device '%s' (using ip %s) already cleared" % (dev_name, ip))
                        mach.device_log_entry(5,
                                              "i",
                                              "got ipaddr (%s)" % (sm_type),
                                              self.__queue_dict["sql_queue"],
                                              self.__loc_config["LOG_SOURCE_IDX"])
                        mach.set_recv_state("got IPaddress via DHCP", self.__queue_dict["sql_queue"])
                        if first_dev["status"] in self.__loc_config["LIST_TAG_KERNEL"]:
                            if not first_dev["stage1_flavour"]:
                                first_dev["stage1_flavour"] = "lo"
                                mach.log("setting stage1_flavour to '%s'" % (first_dev["stage1_flavour"]))
                                dc.execute("UPDATE device SET stage1_flavour=%s WHERE device_idx=%s", (first_dev["stage1_flavour"],
                                                                                                       first_dev["device_idx"]))
                            new_kernel_stuff = get_kernel_stuff(dc, self.__glob_config, first_dev["newkernel"], first_dev["new_kernel"])
                            mach.write_kernel_config(self.__queue_dict["sql_queue"],
                                                     new_kernel_stuff,
                                                     first_dev["kernel_append"],
                                                     self.__server_ip["ip"],
                                                     self.__server_ip["netmask"],
                                                     self.__loc_config,
                                                     first_dev["stage1_flavour"],
                                                     True)
                        elif first_dev["status"] in self.__loc_config["LIST_DOSBOOT"]:
                            # we dont handle dosboot right now, FIXME
                            pass
                        elif first_dev["status"] in self.__loc_config["LIST_MEMTEST"]:
                            mach.write_memtest_config()
                        elif first_dev["status"] in self.__loc_config["LIST_BOOTLOCAL"]:
                            mach.write_localboot_config()
                        # check if the macadr from the database matches the received mac
                        if first_dev["macadr"] != mac:
                            mach.log("got wrong macadr (DHCP: %s, database: %s), fixing " % (mac, first_dev["macadr"]),
                                     logging_tools.LOG_LEVEL_WARN)
                            dc.execute("UPDATE netdevice SET macadr='00:00:00:00:00:00' WHERE macadr='%s'" % (mac))
                            dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac, first_dev["netdevice_idx"]))
                else:
                    mach.log("Device with IP %s not found in database" % (ip))
                mach.decr_use_count("syslog line")
        if sm_type == "DISCOVER":
            if re.match("^.*no free leases.*$", full_string):
                dc.execute("SELECT d.name, nd.devname, nd.netdevice_idx, d.bootserver, d.dhcp_mac, d.bootnetdevice FROM netdevice nd, device d WHERE nd.device=d.device_idx AND nd.macadr='%s'" % (mac))
                mac_list = dc.fetchall()
                if len(mac_list):
                    mac_entry = mac_list[0]
                    if mac_entry["bootserver"] and mac_entry["bootserver"] != self.__loc_config["MOTHER_SERVER_IDX"]:
                        # dhcp-DISCOVER request need not to be answered (other Server responsible)
                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "OTHER", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                        self.log("DHCPDISCOVER for macadr %s (device %s, %s): other bootserver (%d)" % (mac, mac_entry["name"], mac_entry["devname"], mac_entry["bootserver"]))
                    else:
                        # dhcp-DISCOVER request can not be answered (macadress already used in DB)
                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "REJECT", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                        self.log("DHCPDISCOVER for macadr %s (device %s%s, %s%s): address already used" % (mac,
                                                                                                           mac_entry["name"],
                                                                                                           mac_entry["dhcp_mac"] and "[is greedy]" or "",
                                                                                                           mac_entry["devname"],
                                                                                                           mac_entry["netdevice_idx"] == mac_entry["bootnetdevice"] and "[is bootdevice]" or "[is not bootdevice]"))
                        if mac_entry["netdevice_idx"] != mac_entry["bootnetdevice"]:
                            dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "MODIFY", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                            self.log("deleting macadr of netdevice %s on device %s (%s)" % (mac_entry["devname"],
                                                                                            mac_entry["name"],
                                                                                            mac))
                            dc.execute("UPDATE netdevice SET macadr='00:00:00:00:00:00' WHERE netdevice_idx=%d" % (mac_entry["netdevice_idx"]))
                            self._remove_macadr({"name"   : mac_entry["name"],
                                                 "ip"     : "",
                                                 "macadr" : mac})
                        else:
                            dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "REJECT", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                else:
                    dc.execute("SELECT nd.netdevice_idx, d.name, d.device_idx, d.bootserver FROM netdevice nd, device d WHERE d.dhcp_mac=1 AND d.bootnetdevice=nd.netdevice_idx AND nd.device=d.device_idx ORDER by d.name")
                    ndidx_list = dc.fetchall()
                    if len(ndidx_list):
                        for nd in ndidx_list:
                            if nd["bootserver"]:
                                if nd["bootserver"] == self.__loc_config["MOTHER_SERVER_IDX"]:
                                    ins_idx = nd["netdevice_idx"]
                                    dev_name = nd["name"]
                                    dc.execute("SELECT macadr FROM mac_ignore WHERE macadr='%s'" % (mac))
                                    if dc.rowcount:
                                        self.log("Ignoring MAC-Adress '%s' (in ignore-list)" % (mac))
                                        dc.execute("INSERT INTO macbootlog VALUES (0, %s, %s, %s, %s, %s, null)", (0, sm_type, "IGNORELIST", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                                    else:
                                        self.log("Setting bootmacaddress of device '%s' to '%s'" % (dev_name, mac))
                                        dc.execute("UPDATE device SET dhcp_mac=0 WHERE name='%s'" % (dev_name))
                                        dc.execute("UPDATE netdevice SET macadr='%s' WHERE netdevice_idx=%d" % (mac, ins_idx))
                                        dc.execute("SELECT d.device_idx FROM device d WHERE d.name='%s'" % (dev_name))
                                        didx = dc.fetchone()["device_idx"]
                                        sql_str, sql_tuple = mysql_tools.get_device_log_entry_part(didx, self.__loc_config["NODE_SOURCE_IDX"], 0, self.__loc_config["LOG_STATUS"]["i"]["log_status_idx"], mac)
                                        dc.execute("INSERT INTO devicelog VALUES(%s)" % (sql_str), sql_tuple)
                                        self.get_thread_queue().put(("server_com", server_command.server_command(command="alter_macadr", nodes=[dev_name])))
                                        # set the mac-address
                                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (nd["device_idx"], sm_type, "SET", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                                    break
                                else:
                                    self.log("Not responsible for device '%s' (ip %s); bootserver has idx %d" % (nd["name"], ip, nd["bootserver"]))
                                    break
                            else:
                                self.log("Greedy device %s has no bootserver associated" % (nd["name"]), nd["name"])
                    else:
                        # ignore mac-address (no greedy devices)
                        dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "IGNORE", mac, self.__loc_config["LOG_SOURCE_IDX"]))
                        self.log("No greedy devices found for MAC-Address %s" % (mac))
            else:
                # dhcp-DISCOVER request got an answer
                dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (0, sm_type, "---", mac, self.__loc_config["LOG_SOURCE_IDX"]))
        else:
            # non dhcp-DISCOVER request
            dc.execute("INSERT INTO macbootlog VALUES(0, %s, %s, %s, %s, %s, null)", (mach_idx, sm_type, ip, mac, self.__loc_config["LOG_SOURCE_IDX"]))
        dc.release()
