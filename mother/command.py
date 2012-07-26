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

class simple_command(object):
    sc_idx = 0
    com_list = []
    def __init__(self, process, com_str, **kwargs):
        self.process = process
        simple_command.sc_idx += 1
        self.idx = simple_command.sc_idx
        self.com_str = com_str
        self.delay_time = kwargs["delay_time"]
        self.start_time, self.popen = (None, None)
        self.max_run_time = kwargs.get("max_run_time", 30)
        self.log("init command '%s', delay is %s" % (self.com_str,
                                                     logging_tools.get_plural("second", self.delay_time)))
        self.process.register_timer(self.call, self.delay_time, oneshot=True)
        simple_command.com_list.append(self)
    @staticmethod
    def check():
        cur_time = time.time()
        new_list = []
        for com in simple_command.com_list:
            keep = True
            if com.start_time:
                if com.finished():
                    com.done()
                    keep = False
                elif abs(cur_time - com.start_time) > com.max_run_time:
                    com.log("maximum runtime exceeded, killing", logging_tools.LOG_LEVEL_ERROR)
                    keep = False
                    com.terminate()
            if keep:
                new_list.append(com)
        simple_command.com_list = new_list
    @staticmethod
    def idle():
        return True if not simple_command.com_list else False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.process.log("[sc %d] %s" % (self.idx, what), log_level)
    def terminate(self):
        if self.popen:
            del self.popen
    def finished(self):
        self.result = self.popen.poll()
        return self.result != None
    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None
    def done(self):
        self.end_time = time.time()
        self.process.sc_finished(self)
    def call(self):
        self.start_time = time.time()
        self.popen = subprocess.Popen(self.com_str, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        
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
        self.kernel_dev = config_tools.server_check(server_type="mother")
        if "b" in self.kernel_dev.identifier_ip_lut:
            self.__kernel_ip = self.kernel_dev.identifier_ip_lut["b"][0]
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
        print simple_command.idle()
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        new_sc = simple_command(self, args[0], delay_time=kwargs.get("delay_time", 0))
    def _server_com(self, s_com):
        dst_call = {"alter_macadr"  : self._adw_macadr,
                    "delete_macadr" : self._adw_macadr,
                    "write_macadr"  : self._adw_macadr,
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
    def _remove_macadr(self, machdat):
        # removes macadr from dhcp-server
        om_shell_coms = ["delete"]
        for om_shell_com in om_shell_coms:
            om_array = ['server 127.0.0.1',
                        'port 7911',
                        'connect',
                        'new host',
                        'set name = "%s"' % (machdat["name"])]
            if om_shell_com == "write":
                om_array.extend(['set hardware-address = %s' % (machdat["macadr"]),
                                 'set hardware-type = 1',
                                 'set ip-address=%s' % (machdat["ip"])])
                om_array.extend(['set statements = "'+
                                 'supersede host-name = \\"%s\\" ;' % (machdat["name"])+
                                 'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                 'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (machdat["ip"])+
                                 '} "'])
                om_array.append('create')
            elif om_shell_com == "delete":
                om_array.extend(['open',
                                 'remove'])
            else:
                self.log("Internal error: Unknown om_shell command %s" % (om_shell_com), logging_tools.LOG_LEVEL_ERROR)
            #print om_array
            self.log("starting omshell for command %s" % (om_shell_com))
            (errnum, outstr) = commands.getstatusoutput("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)))
            self.log("got (%d) %s" % (errnum, logging_tools.get_plural("line", len(outstr.split("\n")))))
    def _adw_macadr(self, com_name, s_com):
        nodes = s_com.get_nodes()
        self.log("got command %s (key %s), %s%s" % (s_com.get_command(),
                                                    s_com.get_key() and "set" or "not set",
                                                    logging_tools.get_plural("node", len(nodes)),
                                                    nodes and ": %s" % (logging_tools.compress_list(nodes)) or ""))
        dc = self.__db_con.get_connection(SQL_ACCESS)
        sql_str = "SELECT nd.macadr,d.name,i.ip,d.dhcp_written,d.dhcp_write,d.dhcp_error, nd.dhcp_device,nt.identifier,nd.netdevice_idx FROM " + \
                  "netdevice nd, device d, netip i, network nw, network_type nt WHERE nd.device=d.device_idx AND i.netdevice=nd.netdevice_idx AND ((d.bootnetdevice=nd.netdevice_idx AND nt.identifier='b') OR nd.dhcp_device=1) " + \
                  "AND nw.network_type=nt.network_type_idx AND i.network=nw.network_idx AND d.bootserver=%d" % (self.__loc_config["MOTHER_SERVER_IDX"])
        all_rets_dict = {}
        if len(nodes):
            sql_str = "%s AND (%s)" % (sql_str,
                                       " OR ".join(["d.name='%s'" % (x) for x in nodes]))
            for node_name in nodes:
                all_rets_dict[node_name] = "warn no SQL-result"
        dc.execute(sql_str)
        mach_dict = {}
        for sql_rec in dc.fetchall():
            if not mach_dict.has_key(sql_rec["name"]):
                mach_dict[sql_rec["name"]] = sql_rec
            else:
                if sql_rec["identifier"] == "b" and mach_dict[sql_rec["name"]]["identifier"] != "b":
                    mach_dict[sql_rec["name"]]["ip"] = sql_rec["ip"]
        empty_result = True
        # additional flags 
        add_flags = []
        for machdat in mach_dict.values():
            empty_result = False
            #print "-----------------------------"
            #print com_name, "::", machdat
            if self.__ad_struct.has_key(machdat["name"]):
                mach = self.__ad_struct[machdat["name"]]
                if mach.maint_ip:
                    ip_to_write, ip_to_write_src = (mach.maint_ip, "maint_ip")
                elif machdat["dhcp_device"]:
                    if len(mach.ip_dict.keys()) == 1:
                        ip_to_write, ip_to_write_src = (mach.ip_dict.keys()[0], "first ip of ip_dict.keys()")
                    else:
                        ip_to_write, ip_to_write_src = (None, "")
                else:
                    ip_to_write, ip_to_write_src = (None, "")
                mach.incr_use_count("dhcp_command")
                dhcp_written, dhcp_write, dhcp_last_error = (machdat["dhcp_written"], machdat["dhcp_write"], machdat["dhcp_error"])
                # list of om_shell commands
                om_shell_coms, err_lines = ([], [])
                #print mach.name, com_name, force_flag, dhcp_write, dhcp_written
                # try to determine om_shell_coms
                if com_name == "alter_macadr":
                    if dhcp_written:
                        if dhcp_write and ip_to_write:
                            om_shell_coms = ["delete", "write"]
                        else:
                            om_shell_coms = ["delete"]
                    else:
                        if dhcp_write and ip_to_write:
                            om_shell_coms = ["write"]
                        else:
                            om_shell_coms = ["delete"]
                elif com_name == "write_macadr":
                    if dhcp_write and ip_to_write:
                        om_shell_coms = ["write"]
                    else:
                        om_shell_coms = []
                elif com_name == "delete_macadr":
                    if dhcp_write:
                        om_shell_coms = ["delete"]
                    else:
                        om_shell_coms = []
                mach.log("transformed dhcp_com %s to %s: %s (%s)" % (com_name,
                                                                     logging_tools.get_plural("om_shell_command", len(om_shell_coms)),
                                                                     ", ".join(om_shell_coms),
                                                                     ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"))
                # global success of all commands
                g_success = 1
                # dict of dev_fields to change
                dev_sql_fields = {}
                for om_shell_com in om_shell_coms:
                    om_array = ['server 127.0.0.1',
                                'port 7911',
                                'connect',
                                'new host',
                                'set name = "%s"' % (machdat["name"])]
                    if om_shell_com == "write":
                        om_array.extend(['set hardware-address = %s' % (machdat["macadr"]),
                                         'set hardware-type = 1',
                                         'set ip-address=%s' % (machdat["ip"])])
                        om_array.extend(['set statements = "'+
                                         'supersede host-name = \\"%s\\" ;' % (machdat["name"])+
                                         'if substring (option vendor-class-identifier, 0, 9) = \\"PXEClient\\" { '+
                                         'filename = \\"etherboot/%s/pxelinux.0\\" ; ' % (ip_to_write)+
                                         '} "'])
                        om_array.append('create')
                    elif om_shell_com == "delete":
                        om_array.extend(['open',
                                         'remove'])
                    else:
                        self.log("Internal error: Unknown om_shell command %s" % (om_shell_com), logging_tools.LOG_LEVEL_ERROR)
                    #print om_array
                    mach.log("starting omshell for command %s (%s)" % (om_shell_com,
                                                                       ip_to_write and "ip %s from %s" % (ip_to_write, ip_to_write_src) or "no ip"))
                    (errnum, outstr) = commands.getstatusoutput("echo -e '%s' | /usr/bin/omshell" % ("\n".join(om_array)))
                    #print errnum, outstr
                    if errnum == 0:
                        for line in [x.strip()[2:].strip() for x in outstr.split("\n") if x.strip().startswith(">")]:
                            if len(line):
                                if not line.startswith(">") and not line.startswith("obj:"):
                                    omm = self.__om_error_re.match(line)
                                    if omm:
                                        #print mach.name, ":", omm.group(1), "*", omm.group(2)
                                        #print om_array
                                        errnum, g_success, errline = (1, 0, line)
                                        errfac, errstr = (omm.group(1), omm.group(2))
                                elif re.match("^.*connection refused.*$", line):
                                    errnum, g_success, errline = (1, 0, line)
                                    errfac, errstr = ("connection refused", "server")
                    else:
                        g_success = 0
                        errline, errstr, errfac = ("command error", "error", "omshell")
                    if errnum:
                        mach.log("omshell for command %s returned error %s (%s)" % (om_shell_com, errline, errstr), logging_tools.LOG_LEVEL_ERROR)
                        mach.log("error: %s" % (errline), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        mach.log("finished omshell for command %s successfully" % (om_shell_com))
                    # error handling
                    #print "++++", act_com, "---", mach.name, dhcp_written
                    new_dhcp_written = None
                    if errnum:
                        if errstr == "key conflict":
                            new_dhcp_written = 0
                        elif errstr == "already exists":
                            new_dhcp_written = 1
                        elif errstr == "not found":
                            new_dhcp_written = 0
                        errline = "dhcp-error: %s (%s)" % (errstr, errfac)
                        err_lines.append("%s: %s" % (om_shell_com, errline))
                    else:
                        err_lines.append("%s: ok" % (om_shell_com))
                        if om_shell_com == "write":
                            new_dhcp_written = 1
                        elif om_shell_com == "delete":
                            new_dhcp_written = 0
                    if new_dhcp_written is not None:
                        dhcp_written = new_dhcp_written
                        dev_sql_fields["dhcp_written"] = dhcp_written
                    if dhcp_write:
                        dhw_0 = "write"
                    else:
                        dhw_0 = "no write"
                    if dhcp_written:
                        dhw_1 = "written"
                    else:
                        dhw_1 = "not written"
                    mach.log("dhcp_info: %s/%s, mac-address is %s" % (dhw_0, dhw_1, machdat["macadr"]))
                if g_success:
                    loc_result = "ok done"
                else:
                    loc_result = "error: %s" % ("/".join(err_lines))
                if not om_shell_coms:
                    om_shell_coms = ["<nothing>"]
                dhcp_act_error = loc_result
                if dhcp_act_error != dhcp_last_error:
                    dev_sql_fields["dhcp_error"] = dhcp_act_error
                mach.log("dhcp command(s) %s (om: %s) result: %s" % (com_name,
                                                                     ", ".join(om_shell_coms),
                                                                     loc_result))
                all_rets_dict[machdat["name"]] = loc_result
                if dev_sql_fields:
                    dev_sql_keys = dev_sql_fields.keys()
                    sql_str, sql_tuple = ("UPDATE device SET %s WHERE name=%%s" % (", ".join(["%s=%%s" % (x) for x in dev_sql_keys])),
                                          tuple([dev_sql_fields[x] for x in dev_sql_keys] + [mach.name]))
                    dc.execute(sql_str, sql_tuple)
                mach.decr_use_count("dhcp_command")
            else:
                self.log("error maintenance IP (write_macadr) not set for node %s" % (machdat["name"]), logging_tools.LOG_LEVEL_ERROR)
                all_rets_dict[machdat["name"]] = "error maintenance IP (write_macadr) not set for node %s" % (machdat["name"])
        if empty_result:
            self.log("SQL-Query %s gave empty result ?" % (sql_str), logging_tools.LOG_LEVEL_WARN)
        if s_com.get_key():
            res_com = server_command.server_reply()
            res_com.set_node_results(all_rets_dict)
            if empty_result:
                res_com.set_warn_result("empty SQL result")
            else:
                res_com.set_ok_result("ok")
            s_com.get_queue().put(("result_ready", (s_com, res_com)))
        dc.release()
