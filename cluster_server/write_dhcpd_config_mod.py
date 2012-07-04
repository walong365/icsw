#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2012 Andreas Lang-Nevyjel
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
""" writes the dhcpd.conf in /etc """

import sys
import cs_base_class
import process_tools
import os
import server_command

class write_dhcpd_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["auto_etc_hosts"]
        needed_option_keys = ["authoritative"]
    def _call(self):
        dc = self.dc
        # open for all networks belonging to this server and sharing the same netdevice as the bootnet
        dc.execute("SELECT i.ip, nw.network, nw.netmask, nw.gateway, nw.gw_pri, n.netdevice_idx, nt.identifier, nw.name, nw.network_idx FROM netip i, device d, netdevice n, network nw, network_type nt WHERE " + \
                               "d.device_idx=%d AND i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier='b'" % (self.server_idx))
        if dc.rowcount > 1:
            self.srv_com["result"].attrib.update({
                "reply" : "error more than one boot-net found for '%s'" % (self.global_config["SERVER_SHORT_NAME"]),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        elif not dc.rowcount:
            self.srv_com["result"].attrib.update({
                "reply" : "error no boot-net found for '%s'" % (self.global_config["SERVER_SHORT_NAME"]),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            net = dc.fetchone()
            dc.execute("SELECT i.ip, nw.network, nw.netmask, nt.identifier, nw.gateway, nw.gw_pri, nw.name, nw.network_idx FROM netip i, network nw, network_type nt WHERE i.netdevice=%d AND " % (net["netdevice_idx"]) + \
                                   "i.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND (nt.identifier!='l' AND nt.identifier != 'b')")
            add_nets = list(dc.fetchall())
            if os.path.isdir("/etc/dhp3"):
                dhcpd_f = file("/etc/dhcp3/dhcpd.conf", "w")
            else:
                dhcpd_f = file("/etc/dhcpd.conf", "w")
            dhcpd_f.write("ddns-update-style none;\n")
            dhcpd_f.write("omapi-port 7911;\n")
            dhcpd_f.write("ddns-domainname \"%s\";\n" % (self.global_config["SERVER_SHORT_NAME"]))
            dhcpd_f.write("allow booting;\nallow bootp;\n\n")
            if self.srv_com["authoritative"].text.lower() in ["1", "true", "yes"]:
                dhcpd_f.write("authoritative;\n")
            # get gateway and domain-servers for the various nets
            gw_pri, gateway = (-10000, "0.0.0.0")
            for act_net in [net] + add_nets:
                if act_net["gw_pri"] > gw_pri:
                    gw_pri, gateway = (act_net["gw_pri"], act_net["gateway"])
                for key, configs, add_dict in [("domain-name-servers", ["name_server", "name_slave"], {}),
                                               ("ntp-servers", ["xntp_server"], {}),
                                               ("nis-servers", ["yp_server"], {"domainname" : "nis-domain"})]:
                    dc.execute("SELECT d.name, i.ip FROM device d INNER JOIN netip i INNER JOIN netdevice n INNER JOIN device_config dc INNER JOIN new_config c INNER JOIN " + \
                                           "device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND n.device = d.device_idx AND i.netdevice=n.netdevice_idx AND " + \
                                           "i.network=%d AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND (%s)" % (act_net["network_idx"], " OR ".join(["c.name='%s'" % (x) for x in configs])))
                    if dc.rowcount:
                        hosts, opts = ([(x["ip"], x["name"]) for x in dc.fetchall()], {})
                        for sql_key, dhcp_key in add_dict.iteritems():
                            for tname in ["int", "str"]:
                                sql_str = "SELECT cs.value FROM config_%s cs INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device d INNER JOIN device_group dg LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND cs.name='%s' AND cs.new_config=c.new_config_idx AND (%s) AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND (%s)" % (tname, sql_key, " OR ".join(["c.name='%s'" % (x) for x in configs]), " OR ".join(["d.name='%s'" % (x) for x in [y[1] for y in hosts]]))
                                dc.execute(sql_str)
                                if dc.rowcount:
                                    opts[dhcp_key] = dc.fetchone()["value"]
                        act_net[key] = {"hosts" : hosts, "opts" : opts}
                #act_net["dns"] = 
            dhcpd_f.write("shared-network %s {\n" % (self.global_config["SERVER_SHORT_NAME"]))
            dhcpd_f.write("  option routers %s;\n" % (gateway))
            for act_net in [net] + add_nets:
                dhcpd_f.write("  subnet %s netmask %s {\n" % (act_net["network"], act_net["netmask"]))
                if act_net["identifier"] == "b":
                    dhcpd_f.write("    authoritative ;\n")
                dhcpd_f.write("    next-server %s;\n" % (act_net["ip"]))
                for key in ["domain-name-servers", "ntp-servers", "nis-servers"]:
                    if act_net.get(key):
                        dhcpd_f.write("    option %s %s;\n" % (key, ", ".join(["%s" % (x[0]) for x in act_net[key]["hosts"]])))
                        for o_key, o_value in act_net[key]["opts"].iteritems():
                            dhcpd_f.write("    option %s %s;\n" % (o_key, o_value))
                dhcpd_f.write("    server-identifier %s;\n" % (act_net["ip"]))
                dhcpd_f.write("    option domain-name \"%s\";\n" % (act_net["name"]))
                dhcpd_f.write("  }\n")
            dhcpd_f.write("}\n")
            # create netbotz-dhcp entries
            dc.execute("SELECT n.macadr, i.ip, d.name FROM netdevice n, netip i, device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='NB' AND n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND d.bootserver=%d" % (self.server_idx))
            if dc.rowcount:
                dhcpd_f.write("\ngroup netbotz {\n")
                for netbotz in dc.fetchall():
                    dhcpd_f.write("  host %s {\n    hardware ethernet %s;\n    fixed-address %s;\n  }\n" % (netbotz["name"], netbotz["macadr"], netbotz["ip"]))
                dhcpd_f.write("}\n")
            dhcpd_f.close()
            ret_state = None
            for s_name in ["dhcp3-server", "dhcpd"]:
                if os.path.isfile("/etc/init.d/%s" % (s_name)):
                    cstat, log_f = process_tools.submit_at_command("/etc/init.d/nscd restart", 1)
                    for log_line in log_f:
                        self.log(log_f)
                    if cstat:
                        ret_state, ret_str = (
                            server_command.SRV_REPLY_STATE_ERROR,
                            "error wrote dhcpd-config, unable to submit at-command (%d, please check logs)" % (cstat))
                    else:
                        ret_state, ret_str = (
                            server_command.SRV_REPLY_STATE_OK,
                            "ok wrote dhcpd-config and successfully submitted configuration")
            if ret_state is None:
                ret_state, ret_str = (
                    server_command.SRV_REPLY_STATE_ERROR,
                    "error no valid dhcp-server found")
            self.srv_com["result"].attrib.update({
                "reply" : ret_str,
                "state" : "%d" % (ret_state)})
            
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
